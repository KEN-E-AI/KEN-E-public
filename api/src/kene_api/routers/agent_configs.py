"""
Agent configuration management endpoints.

Provides CRUD operations for strategy agent configurations stored in Firestore.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field

from ..auth import UserContext
from ..auth.user_context import get_current_user_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent-configs", tags=["agent-configs"])

# Allowed agent config IDs (security: prevent path traversal and unauthorized access)
ALLOWED_CONFIG_IDS = {
    "business_researcher",
    "business_formatter",
    "competitive_researcher",
    "competitive_formatter",
    "marketing_researcher",
    "marketing_formatter",
    "brand_researcher",
    "brand_formatter",
}


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
    """Request to update an agent configuration."""

    instruction: str | None = None
    model: str | None = None
    description: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    version: str | None = None
    variant_name: str | None = None
    experiment_id: str | None = None
    updated_by: str = Field(..., description="Email of person making update")
    notes: str = Field(default="", description="Notes about this change")


@router.get("/", response_model=list[str])
async def list_agent_configs(
    user: UserContext = Depends(get_current_user_context),
) -> list[str]:
    """
    List all available agent configuration IDs.

    Requires super admin authentication.

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
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        db = firestore.Client(project=project_id)
        configs = db.collection("agent_configs").stream()

        config_ids = [config.id for config in configs]

        logger.info(f"User {user.email} listed {len(config_ids)} agent configs")

        return sorted(config_ids)

    except Exception as e:
        logger.error(f"Failed to list agent configs: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to list agent configurations"
        )


@router.get("/{config_id}", response_model=AgentConfig)
async def get_agent_config(
    config_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> AgentConfig:
    """
    Get a specific agent configuration.

    Requires super admin authentication.

    Args:
        config_id: Agent config document ID (e.g., 'business_researcher')
        user: Current authenticated user context

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
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        db = firestore.Client(project=project_id)
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
        logger.error(f"Failed to get agent config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve agent configuration"
        )


@router.put("/{config_id}", response_model=AgentConfig)
async def update_agent_config(
    config_id: str,
    update: AgentConfigUpdate,
    user: UserContext = Depends(get_current_user_context),
) -> AgentConfig:
    """
    Update an agent configuration.

    Automatically increments version and updates metadata.
    Requires super admin authentication.

    Args:
        config_id: Agent config document ID
        update: Fields to update
        user: Current authenticated user context

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
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        db = firestore.Client(project=project_id)
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Configuration not found")

        # Get current config
        current_config = doc.to_dict()
        current_metadata = current_config.get("metadata", {})

        # Build update dict
        updates: dict[str, Any] = {}

        # Update config fields
        if update.instruction is not None:
            updates["instruction"] = update.instruction

        if update.model is not None:
            updates["model"] = update.model

        if update.description is not None:
            updates["description"] = update.description

        # Update generate_content_config
        if update.temperature is not None or update.max_output_tokens is not None:
            gen_config = current_config.get("generate_content_config", {})

            if update.temperature is not None:
                gen_config["temperature"] = update.temperature

            if update.max_output_tokens is not None:
                gen_config["max_output_tokens"] = update.max_output_tokens

            updates["generate_content_config"] = gen_config

        # Auto-increment version if not provided
        if update.version is not None:
            new_version = update.version
        else:
            # Parse current version and increment with validation (e.g., v1.0 -> v1.1)
            current_version = current_metadata.get("version", "v1.0")
            try:
                if not current_version.startswith("v"):
                    raise ValueError("Version must start with 'v'")

                version_parts = current_version[1:].split(".")
                if len(version_parts) != 2:
                    raise ValueError("Version must be in format vX.Y")

                major = int(version_parts[0])
                minor = int(version_parts[1])

                # Bounds checking (security: prevent integer overflow issues)
                if major > 999 or minor > 999:
                    raise ValueError("Version numbers must be <= 999")

                new_version = f"v{major}.{minor + 1}"
            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Invalid version format {current_version}: {e}, using fallback"
                )
                new_version = "v1.1"  # Fallback

        # Sanitize updated_by field (security: prevent injection)
        safe_updated_by = (
            update.updated_by.replace(".", "_").replace("$", "_")[:100]
            if update.updated_by
            else "unknown"
        )

        # Update metadata
        updates["metadata.version"] = new_version
        updates["metadata.updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["metadata.updated_by"] = safe_updated_by

        if update.variant_name is not None:
            updates["metadata.variant_name"] = update.variant_name

        if update.experiment_id is not None:
            updates["metadata.experiment_id"] = update.experiment_id

        if update.notes:
            updates["metadata.notes"] = update.notes

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
        logger.error(f"Failed to update agent config {config_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to update agent configuration"
        )
