"""
Agent configuration management endpoints.

Provides CRUD operations for strategy agent configurations stored in Firestore.

Pydantic models for the ``agent_configs/{id}`` schema live in
``kene_api.models.agent_config_models``; this module re-exports them for
backwards compatibility with pre-Sprint-6 callers.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore

from app.utils.trace_metadata import parse_semver, validate_semver

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore
from ..models.agent_config_models import (
    AgentConfig,
    AgentConfigMetadata,
    AgentConfigUpdate,
    ConfigAuditEntry,
    GenerateContentConfig,
)

__all__ = [
    "ALLOWED_CONFIG_IDS",
    "AgentConfig",
    "AgentConfigMetadata",
    "AgentConfigUpdate",
    "ConfigAuditEntry",
    "GenerateContentConfig",
    "router",
]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-configs", tags=["agent-configs"])

# Allowlist of valid Firestore config doc IDs for agent configurations.
# These correspond to the config_doc_id and sub_config_doc_ids in
# app/adk/agents/registry.py. Keep in sync when agents are added/removed.
ALLOWED_CONFIG_IDS: set[str] = {
    "ken_e_chatbot",
    "company_news_agent",
    "google_analytics_agent",
    "business_researcher",
    "business_formatter",
    "competitive_researcher",
    "competitive_formatter",
    "marketing_researcher",
    "marketing_formatter",
    "brand_researcher",
    "brand_formatter",
}


def _increment_version(current_version: str) -> str:
    """
    Increment version patch number (semver format).

    Auto-increment bumps the patch version. Major/minor bumps are manual.
    Handles both legacy 2-part (vX.Y) and semver 3-part (vX.Y.Z) formats.

    Args:
        current_version: Current version string (e.g., "v1.0.0", "v1.2")

    Returns:
        Incremented semver version string (e.g., "v1.0.1")

    Raises:
        ValueError: If version format is not parseable
    """
    version = current_version.strip() if current_version else ""
    if not version.startswith("v"):
        version = f"v{version}" if version else ""

    # Strip prerelease suffix for incrementing (e.g., "v1.0.0-beta" → "v1.0.0")
    base = version[1:].split("-", 1)[0] if version.startswith("v") else ""
    parts = base.split(".") if base else []

    if len(parts) == 2:
        major, minor, patch = int(parts[0]), int(parts[1]), 0
    elif len(parts) == 3:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(
            f"Cannot increment version '{current_version}': "
            f"expected vX.Y or vX.Y.Z format"
        )

    return f"v{major}.{minor}.{patch + 1}"


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
        # Note: format validation already done by Pydantic field_validator
        current_version_str = current_metadata.get("version")

        if update.version:
            new_version = validate_semver(update.version)

            # Prevent version downgrade
            if current_version_str:
                try:
                    current_parsed = parse_semver(validate_semver(current_version_str))
                    new_parsed = parse_semver(new_version)
                    if new_parsed < current_parsed:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Version downgrade not allowed: "
                            f"{new_version} < {validate_semver(current_version_str)}. "
                            f"Version must be greater than the current version.",
                        )
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot compare versions: current stored version "
                        f"'{current_version_str}' is not valid semver. "
                        f"Please contact an admin to fix the stored version. "
                        f"Error: {e}",
                    ) from e
        else:
            if not current_version_str:
                raise HTTPException(
                    status_code=400,
                    detail="No version found in config metadata. "
                    "Please set a version manually (e.g., v1.0.0).",
                )
            try:
                new_version = _increment_version(current_version_str)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot auto-increment version: {e}. "
                    f"Current stored version '{current_version_str}' "
                    f"is not valid semver. Please set a valid version manually "
                    f"(e.g., v1.0.0).",
                ) from e

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
