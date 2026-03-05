"""
Agent configuration management endpoints.

Provides CRUD operations for strategy agent configurations stored in Firestore.
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field, field_validator

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-configs", tags=["agent-configs"])

# Derive allowed config IDs from the agent registry (single source of truth)
from app.adk.agents.registry import get_registry

ALLOWED_CONFIG_IDS = get_registry().get_all_config_doc_ids()


class AgentConfigMetadata(BaseModel):
    """Metadata for an agent configuration."""

    version: str = Field(..., description="Version number (e.g., v1.0, v1.1)")
    variant_name: str = Field(..., description="Descriptive variant name")
    experiment_id: str = Field(
        default="baseline", description="Experiment grouping identifier"
    )
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")
    updated_by: str = Field(..., description="Email or identifier of last updater")
    notes: str = Field(default="", description="Change notes or description")


class GenerateContentConfig(BaseModel):
    """Generation configuration for the agent."""

    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=2500, ge=100, le=65535)


class AgentConfig(BaseModel):
    """Complete agent configuration."""

    name: str = Field(..., description="Agent name")
    model: str = Field(..., description="Model identifier")
    description: str = Field(..., description="Agent description")
    instruction: str = Field(..., description="Agent instruction/prompt")
    generate_content_config: GenerateContentConfig
    metadata: AgentConfigMetadata


class AgentConfigUpdate(BaseModel):
    """Request to update an agent configuration with validation."""

    instruction: str | None = Field(
        None,
        min_length=10,
        max_length=50000,
        description="Agent instruction/prompt",
    )

    model: str | None = Field(
        None,
        pattern=r"^(gemini-[\d]+-[\w-]+|gemini-[\d\.]+[-\w]+|gpt-[\w-]+|o1-[\w-]+)$",
        description="Model identifier (Gemini or OpenAI model)",
    )

    description: str | None = Field(
        None, min_length=10, max_length=1000, description="Agent description"
    )

    temperature: float | None = Field(
        None, ge=0.0, le=1.0, description="Generation temperature (0.0-1.0)"
    )

    max_output_tokens: int | None = Field(
        None,
        ge=100,
        le=65535,
        description="Maximum output tokens (100-65535)",
    )

    version: str | None = Field(
        None, pattern=r"^v\d+\.\d+$", description="Version string in format vX.Y"
    )

    variant_name: str | None = Field(
        None, min_length=1, max_length=100, description="Descriptive variant name"
    )

    experiment_id: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Experiment grouping identifier",
    )

    updated_by: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email of person making update",
    )

    notes: str = Field(
        default="", max_length=5000, description="Notes about this change"
    )

    @field_validator("updated_by")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate updated_by looks like an email."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("updated_by must be a valid email address")
        return v

    @field_validator("model")
    @classmethod
    def validate_model_exists(cls, v: str | None) -> str | None:
        """Validate model ID is a known Gemini or OpenAI model."""
        if v is None:
            return v

        # List of supported models (update as new models are released)
        SUPPORTED_MODELS = {
            # Gemini 3 models (latest, preview)
            "gemini-3-flash-preview",
            "gemini-3-pro-preview",
            # Gemini 2.x models (current stable)
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            # Gemini 1.5 models (stable fallback)
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            # OpenAI models (for formatters)
            "gpt-4o",
            "gpt-4o-2024-08-06",
            "gpt-4o-mini",
            "o1-preview",
            "o1-mini",
        }

        if v not in SUPPORTED_MODELS:
            # Separate Gemini and OpenAI models for better error message
            gemini_models = {m for m in SUPPORTED_MODELS if m.startswith("gemini")}
            openai_models = {m for m in SUPPORTED_MODELS if not m.startswith("gemini")}

            error_msg = (
                f"Model '{v}' is not supported.\n"
                f"Supported Gemini models: {', '.join(sorted(gemini_models))}\n"
                f"Supported OpenAI models: {', '.join(sorted(openai_models))}"
            )
            raise ValueError(error_msg)

        return v


def _increment_version(current_version: str) -> str:
    """
    Increment version number with validation.

    Args:
        current_version: Current version string (e.g., "v1.0")

    Returns:
        Incremented version string (e.g., "v1.1")

    Example:
        >>> _increment_version("v1.0")
        "v1.1"
        >>> _increment_version("v1.999")
        "v1.1000"
        >>> _increment_version("v1.1000")
        "v1.1"  # Fallback due to bounds check (1000 > 999)
    """
    try:
        if not current_version.startswith("v"):
            raise ValueError("Version must start with 'v'")

        version_parts = current_version[1:].split(".")
        if len(version_parts) != 2:
            raise ValueError("Version must be in format vX.Y")

        major = int(version_parts[0])
        minor = int(version_parts[1])

        if major > 999 or minor > 999:
            raise ValueError("Version numbers must be <= 999")

        return f"v{major}.{minor + 1}"
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid version format {current_version}: {e}, using fallback")
        return "v1.1"


def _sanitize_updated_by(email: str) -> str:
    """
    Sanitize updated_by field to prevent Firestore injection.

    Firestore doesn't allow dots or dollar signs in field names,
    so we sanitize the email to prevent potential issues.

    Args:
        email: Email address to sanitize

    Returns:
        Sanitized email string (max 100 chars, dots/dollars replaced)
    """
    if not email:
        return "unknown"

    return email.replace(".", "_").replace("$", "_")[:100]


def _build_firestore_updates(
    instruction: str | None = None,
    model: str | None = None,
    description: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    version: str | None = None,
    updated_at: str | None = None,
    updated_by: str | None = None,
    variant_name: str | None = None,
    experiment_id: str | None = None,
    notes: str | None = None,
    current_gen_config: dict[str, int | float] | None = None,
) -> dict[str, str | int | float | dict[str, int | float]]:
    """
    Build type-safe Firestore update dictionary.

    Args:
        instruction: New instruction text
        model: New model identifier
        description: New description
        temperature: New temperature value
        max_output_tokens: New max tokens value
        version: New version string
        updated_at: Update timestamp
        updated_by: Email of updater
        variant_name: New variant name
        experiment_id: New experiment ID
        notes: Change notes
        current_gen_config: Current generation config for merging

    Returns:
        Dictionary with Firestore update format (dot notation for nested fields)
    """
    updates: dict[str, str | int | float | dict[str, int | float]] = {}

    if instruction is not None:
        updates["instruction"] = instruction

    if model is not None:
        updates["model"] = model

    if description is not None:
        updates["description"] = description

    if temperature is not None or max_output_tokens is not None:
        gen_config: dict[str, int | float] = (
            current_gen_config.copy() if current_gen_config else {}
        )
        if temperature is not None:
            gen_config["temperature"] = temperature
        if max_output_tokens is not None:
            gen_config["max_output_tokens"] = max_output_tokens
        updates["generate_content_config"] = gen_config

    if version is not None:
        updates["metadata.version"] = version

    if updated_at is not None:
        updates["metadata.updated_at"] = updated_at

    if updated_by is not None:
        updates["metadata.updated_by"] = updated_by

    if variant_name is not None:
        updates["metadata.variant_name"] = variant_name

    if experiment_id is not None:
        updates["metadata.experiment_id"] = experiment_id

    if notes is not None:
        updates["metadata.notes"] = notes

    return updates


@router.get("/", response_model=list[str])
async def list_agent_configs(
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> list[str]:
    """
    List all available agent configuration IDs.

    Requires super admin authentication.

    Args:
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        List of config document IDs

    Raises:
        401: Not authenticated
        403: Not a super admin
        500: Firestore error
    """
    # Only super admins can access agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config access attempt by user {user.user_id} ({user.email})"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access agent configurations",
        )

    try:
        configs = db.collection("agent_configs").stream()
        config_ids = [config.id for config in configs]

        logger.info(f"User {user.email} listed {len(config_ids)} agent configs")

        return sorted(config_ids)

    except Exception as e:
        logger.error(f"Failed to list agent configs: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to list agent configurations"
        ) from e


@router.get("/{config_id}", response_model=AgentConfig)
async def get_agent_config(
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> AgentConfig:
    """
    Get a specific agent configuration.

    Requires super admin authentication.

    Args:
        config_id: Agent config document ID (e.g., 'business_researcher')
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        Agent configuration with all fields

    Raises:
        400: Invalid config_id
        401: Not authenticated
        403: Not a super admin
        404: Config not found
        500: Firestore error
    """
    # Only super admins can access agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config read attempt by user {user.user_id} ({user.email}) for {config_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access agent configurations",
        )

    # Validate config_id against allowlist (security: prevent path traversal)
    if config_id not in ALLOWED_CONFIG_IDS:
        logger.warning(f"Invalid config_id attempted: {config_id} by user {user.email}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_id. Must be one of: {', '.join(sorted(ALLOWED_CONFIG_IDS))}",
        )

    try:
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Configuration not found")

        config_data = doc.to_dict()

        # Parse into AgentConfig model
        logger.info(f"User {user.email} retrieved config: {config_id}")
        return AgentConfig(**config_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent config {config_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve agent configuration"
        ) from e


@router.put("/{config_id}", response_model=AgentConfig)
async def update_agent_config(
    config_id: str,
    update: AgentConfigUpdate,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> AgentConfig:
    """
    Update an agent configuration.

    Automatically increments version and updates metadata.
    Requires super admin authentication.

    Args:
        config_id: Agent config document ID
        update: Fields to update
        user: Current authenticated user context
        db: Firestore client (injected dependency)

    Returns:
        Updated agent configuration

    Raises:
        400: Invalid config_id or invalid version format
        401: Not authenticated
        403: Not a super admin
        404: Config not found
        500: Firestore error
    """
    # Only super admins can modify agent configs
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized agent config update attempt by user {user.user_id} ({user.email}) for {config_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can modify agent configurations",
        )

    # Validate config_id against allowlist (security: prevent path traversal)
    if config_id not in ALLOWED_CONFIG_IDS:
        logger.warning(
            f"Invalid config_id update attempted: {config_id} by user {user.email}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config_id. Must be one of: {', '.join(sorted(ALLOWED_CONFIG_IDS))}",
        )

    try:
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Get current config
        current_config = doc.to_dict()
        current_metadata = current_config.get("metadata", {})

        # Determine new version
        new_version = (
            update.version
            if update.version
            else _increment_version(current_metadata.get("version", "v1.0"))
        )

        # Sanitize updated_by field
        safe_updated_by = _sanitize_updated_by(update.updated_by)

        # Build type-safe updates using helper function
        updates = _build_firestore_updates(
            instruction=update.instruction,
            model=update.model,
            description=update.description,
            temperature=update.temperature,
            max_output_tokens=update.max_output_tokens,
            version=new_version,
            updated_at=datetime.now(timezone.utc).isoformat(),
            updated_by=safe_updated_by,
            variant_name=update.variant_name,
            experiment_id=update.experiment_id,
            notes=update.notes,
            current_gen_config=current_config.get("generate_content_config", {}),
        )

        # Apply updates
        doc_ref.update(updates)

        # Fetch and return updated config
        updated_doc = doc_ref.get()
        updated_data = updated_doc.to_dict()

        logger.info(
            f"User {user.email} updated config {config_id} to version {new_version}"
        )

        return AgentConfig(**updated_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent config {config_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update agent configuration"
        ) from e
