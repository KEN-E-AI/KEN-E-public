"""Pydantic models for agent configurations stored in Firestore.

These models define the schema for documents in the ``agent_configs/{id}``
collection. They are consumed by:

* ``routers.agent_configs`` — admin CRUD endpoints (GET/PUT)
* ``app.adk.agents.strategy_agent.config_loader`` — agent loading at module import
* ``app.adk.agents.utils.config_cache`` (forthcoming, per Sprint 6 Decision B)

See Sprint 6 Design Decisions in Notion for rationale:

* Decision A — Firestore config schema
* Decision B — 60 s TTL hot-reload cache for instruction/temperature
* Decision C — Per-config history subcollection for audit trail
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.utils.trace_metadata import SEMVER_PATTERN

# Supported model identifiers. Updated as new Gemini/OpenAI models are released.
SUPPORTED_MODELS: frozenset[str] = frozenset(
    {
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
        # OpenAI models (used by formatters)
        "gpt-4o",
        "gpt-4o-2024-08-06",
        "gpt-4o-mini",
        "o1-preview",
        "o1-mini",
    }
)

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


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
    """Complete agent configuration as stored in Firestore."""

    name: str = Field(..., description="Agent name")
    model: str = Field(..., description="Model identifier")
    description: str = Field(..., description="Agent description")
    instruction: str = Field(..., description="Agent instruction/prompt")
    generate_content_config: GenerateContentConfig
    metadata: AgentConfigMetadata


class AgentConfigUpdate(BaseModel):
    """Request body for PUT /api/v1/agent-configs/{id}.

    All fields except ``updated_by`` are optional to allow partial updates.
    """

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
        None,
        description="Version string in semver format (e.g., v1.0.0)",
    )

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("v"):
            v = f"v{v}"
        if not SEMVER_PATTERN.match(v):
            raise ValueError(
                f"Invalid version '{v}'. "
                f"Please use semver format, e.g. v1.0.0 or v2.1.3"
            )
        return v

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
        """``updated_by`` must look like an email address."""
        if not _EMAIL_PATTERN.match(v):
            raise ValueError("updated_by must be a valid email address")
        return v

    @field_validator("model")
    @classmethod
    def validate_model_exists(cls, v: str | None) -> str | None:
        """Validate model ID is a known Gemini or OpenAI model."""
        if v is None:
            return v

        if v not in SUPPORTED_MODELS:
            gemini_models = sorted(
                m for m in SUPPORTED_MODELS if m.startswith("gemini")
            )
            openai_models = sorted(
                m for m in SUPPORTED_MODELS if not m.startswith("gemini")
            )
            raise ValueError(
                f"Model '{v}' is not supported.\n"
                f"Supported Gemini models: {', '.join(gemini_models)}\n"
                f"Supported OpenAI models: {', '.join(openai_models)}"
            )

        return v


class ConfigAuditEntry(BaseModel):
    """Audit-trail entry for a single config change.

    Written to a per-config history subcollection at
    ``{collection}/{id}/history/{timestamp}`` after every successful PUT.

    ``doc_type`` distinguishes between agent configs and MCP server configs so
    a single reader can reconstruct history across both domains.

    See Sprint 6 Decision C for rationale.
    """

    action: str = Field(
        ..., description="One of: created, updated, deleted, viewed, reverted"
    )
    doc_type: str = Field(..., description="One of: agent_config, mcp_server_config")
    doc_id: str = Field(..., description="ID of the config document being audited")

    user_id: str = Field(..., description="Firebase UID of the user making the change")
    user_email: str = Field(..., description="Email of the user making the change")
    timestamp: str = Field(..., description="ISO-8601 timestamp of the change")
    request_id: str | None = Field(
        None, description="X-Request-Id for tracing, if available"
    )

    version_before: str | None = Field(
        None, description="Semver version of the config before this change"
    )
    version_after: str = Field(
        ..., description="Semver version of the config after this change"
    )

    fields_changed: list[str] = Field(
        default_factory=list,
        description="List of field names that changed (e.g., ['instruction', 'temperature'])",
    )
    changes: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Per-field before/after dictionary, e.g. "
            "{'temperature': {'before': 0.3, 'after': 0.5}}."
        ),
    )


__all__ = [
    "SUPPORTED_MODELS",
    "AgentConfig",
    "AgentConfigMetadata",
    "AgentConfigUpdate",
    "ConfigAuditEntry",
    "GenerateContentConfig",
]
