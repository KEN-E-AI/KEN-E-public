"""
Agent configuration management endpoints.

Provides CRUD operations for strategy agent configurations stored in Firestore.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from google.cloud import firestore
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/agent-configs", tags=["agent-configs"])


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
async def list_agent_configs() -> list[str]:
    """
    List all available agent configuration IDs.

    Returns:
        List of config document IDs
    """
    try:
        db = firestore.Client(project="ken-e-dev")
        configs = db.collection("agent_configs").stream()

        config_ids = [config.id for config in configs]

        return sorted(config_ids)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list agent configs: {str(e)}"
        )


@router.get("/{config_id}", response_model=AgentConfig)
async def get_agent_config(config_id: str) -> AgentConfig:
    """
    Get a specific agent configuration.

    Args:
        config_id: Agent config document ID (e.g., 'business_researcher')

    Returns:
        Agent configuration with all fields

    Raises:
        404: Config not found
        500: Firestore error
    """
    try:
        db = firestore.Client(project="ken-e-dev")
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

        config_data = doc.to_dict()

        # Parse into AgentConfig model
        return AgentConfig(**config_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent config: {str(e)}"
        )


@router.put("/{config_id}", response_model=AgentConfig)
async def update_agent_config(
    config_id: str, update: AgentConfigUpdate
) -> AgentConfig:
    """
    Update an agent configuration.

    Automatically increments version and updates metadata.

    Args:
        config_id: Agent config document ID
        update: Fields to update

    Returns:
        Updated agent configuration

    Raises:
        404: Config not found
        500: Firestore error
    """
    try:
        db = firestore.Client(project="ken-e-dev")
        doc_ref = db.collection("agent_configs").document(config_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=404, detail=f"Config '{config_id}' not found"
            )

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
            # Parse current version and increment (e.g., v1.0 -> v1.1)
            current_version = current_metadata.get("version", "v1.0")
            try:
                # Parse v1.2 -> major=1, minor=2
                version_parts = current_version.lstrip("v").split(".")
                major = int(version_parts[0])
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                new_version = f"v{major}.{minor + 1}"
            except (ValueError, IndexError):
                new_version = "v1.1"  # Fallback

        # Update metadata
        updates["metadata.version"] = new_version
        updates["metadata.updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["metadata.updated_by"] = update.updated_by

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

        return AgentConfig(**updated_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent config: {str(e)}"
        )
