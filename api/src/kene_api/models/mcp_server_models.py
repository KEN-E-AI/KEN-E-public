"""Pydantic models for MCP server configs stored in Firestore.

Defines the schema for documents in the ``mcp_server_configs/{server_id}``
collection. Consumed by the forthcoming ``FirestoreMCPLoader`` (Story 1.1.4-2)
and admin CRUD endpoints (Story 1.1.4-3).

The **connection sub-models** (``StdioConnectionConfig`` / ``SseConnectionConfig``)
are imported unchanged from ``shared.mcp_connection_config`` to keep a single
source of truth for connection shape — both YAML and Firestore loaders share
the same runtime-critical connection discriminator.

See Sprint 6 Design Decisions in Notion:

* Decision A — preserves existing ``MCPServerConfig`` shape, adds the three
  aspirational fields (``integration_type``, ``hosting``, ``specialist_categories``)
  plus a ``metadata`` sub-object mirroring agent configs.
* Decision C — ``ConfigAuditEntry`` (in ``agent_config_models``) handles audit
  history for this collection too, discriminated via ``doc_type``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.mcp_connection_config import (
    SseConnectionConfig,
    StdioConnectionConfig,
)

from .agent_config_models import SUPPORTED_MODELS as _SUPPORTED_MODELS  # noqa: F401

# Map from ``auth_type`` (on the MCP server config) to the ADK session-state
# key that holds the per-user credential payload. Consumed by
# ``make_header_provider`` in ``app/adk/agents/agent_factory/header_provider.py``.
#
# Only ``ga_oauth`` is wired today; the other entries are reserved for
# integrations enabled by Sprint 6+ migrations (HubSpot, Google Ads).
CREDENTIAL_KEYS: dict[str, str] = {
    "ga_oauth": "ga_credentials",
    "google_ads_oauth": "google_ads_credentials",
    "hubspot_oauth": "hubspot_credentials",
}


IntegrationType = Literal["mcp", "sdk", "provider_mcp"]
HostingType = Literal["self", "provider"]


class MCPServerMetadata(BaseModel):
    """Metadata for an MCP server config (mirrors ``AgentConfigMetadata``)."""

    version: str = Field(..., description="Semver version, e.g. v1.0.0")
    variant_name: str = Field(..., description="Descriptive variant name")
    experiment_id: str = Field(
        default="baseline", description="Experiment grouping identifier"
    )
    created_at: str = Field(..., description="ISO-8601 timestamp of creation")
    updated_at: str = Field(..., description="ISO-8601 timestamp of last update")
    updated_by: str = Field(..., description="Email of the user who last updated")
    notes: str = Field(default="", description="Change notes")


class MCPServerFirestoreConfig(BaseModel):
    """Complete MCP server config as stored in ``mcp_server_configs/{id}``.

    Preserves every field the runtime uses today (via ``MCPConfigLoader`` /
    ``MCPServerManager``) plus the three registry-level fields added in
    Sprint 6: ``integration_type``, ``hosting``, ``specialist_categories``.
    """

    name: str = Field(..., description="Unique server identifier")
    description: str = Field(
        default="", description="Human-readable description (admin-visible)"
    )

    integration_type: IntegrationType = Field(
        default="mcp",
        description=(
            "Backing integration style. 'mcp' is the only type wired today; "
            "'sdk' and 'provider_mcp' are reserved for future integrations."
        ),
    )
    hosting: HostingType = Field(
        ...,
        description=(
            "'self' when KEN-E runs the server locally (stdio); 'provider' "
            "when a third-party hosts it (sse)."
        ),
    )
    specialist_categories: list[str] = Field(
        ...,
        min_length=1,
        description="Specialist categories this server groups into",
    )

    tool_count: int = Field(default=0, ge=0, description="Expected number of tools")
    estimated_tokens: int = Field(
        default=1000,
        ge=0,
        description="Estimated context tokens for tool definitions.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Search keywords for tool discovery",
    )

    connection: StdioConnectionConfig | SseConnectionConfig = Field(
        ...,
        discriminator="connection_type",
        description="Connection params; discriminated by connection_type",
    )

    auth_type: str | None = Field(
        default=None,
        description=(
            "Auth scheme identifier. Must be a key in CREDENTIAL_KEYS or None. "
            "Drives ``make_header_provider`` dispatch in the agent factory."
        ),
    )

    enabled: bool = Field(
        default=True, description="Whether this server is wired into agents"
    )

    metadata: MCPServerMetadata

    @field_validator("auth_type")
    @classmethod
    def _validate_auth_type(cls, v: str | None) -> str | None:
        """``auth_type`` must be None or a known credential-key mapping."""
        if v is None:
            return v
        if v not in CREDENTIAL_KEYS:
            raise ValueError(
                f"Unknown auth_type '{v}'. "
                f"Supported: {sorted(CREDENTIAL_KEYS)} or null."
            )
        return v

    @model_validator(mode="after")
    def _validate_hosting_matches_connection(
        self,
    ) -> MCPServerFirestoreConfig:
        """``hosting`` must agree with the connection's discriminator.

        stdio ↔ self (KEN-E runs the subprocess); sse ↔ provider (third-party
        hosts it). Mismatches indicate migration errors.
        """
        is_stdio = isinstance(self.connection, StdioConnectionConfig)
        is_sse = isinstance(self.connection, SseConnectionConfig)

        if is_stdio and self.hosting != "self":
            raise ValueError(
                "stdio connections must have hosting='self' "
                "(KEN-E runs the subprocess locally)"
            )
        if is_sse and self.hosting != "provider":
            raise ValueError(
                "sse connections must have hosting='provider' "
                "(third-party server hosts the endpoint)"
            )

        if is_sse and not self.connection.url:
            # Mirror the existing guard in MCPServerConfig.validate_config.
            raise ValueError(f"SSE server '{self.name}' requires a non-empty URL")

        return self


class MCPServerConfigUpdate(BaseModel):
    """Request body for PUT /api/v1/mcp-server-configs/{server_id}.

    All fields except ``updated_by`` are optional (partial update). Fields
    not present are left unchanged. Connection sub-object is atomic — if
    provided, it fully replaces the existing connection.
    """

    description: str | None = Field(
        default=None, max_length=1000, description="Server description"
    )

    integration_type: IntegrationType | None = Field(
        default=None, description="Integration style (mcp|sdk|provider_mcp)"
    )
    hosting: HostingType | None = Field(
        default=None, description="'self' or 'provider'"
    )
    specialist_categories: list[str] | None = Field(
        default=None,
        min_length=1,
        description="Specialist categories (must be non-empty if provided)",
    )

    tool_count: int | None = Field(default=None, ge=0)
    estimated_tokens: int | None = Field(default=None, ge=0)
    keywords: list[str] | None = Field(default=None)

    connection: StdioConnectionConfig | SseConnectionConfig | None = Field(
        default=None,
        discriminator="connection_type",
        description="Replaces connection entirely if provided",
    )

    auth_type: str | None = Field(
        default=None, description="null or a key in CREDENTIAL_KEYS"
    )
    enabled: bool | None = Field(default=None)

    version: str | None = Field(default=None, description="Semver version, e.g. v1.0.1")
    variant_name: str | None = Field(default=None, min_length=1, max_length=100)
    experiment_id: str | None = Field(default=None, min_length=1, max_length=100)

    updated_by: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email of person making update",
    )
    notes: str = Field(default="", max_length=5000)

    @field_validator("auth_type")
    @classmethod
    def _validate_auth_type(cls, v: str | None) -> str | None:
        # Pydantic treats explicit None the same as "field not set" in this
        # context (since the field default is None). Callers wanting to
        # *clear* auth_type must use a dedicated DELETE or null-sentinel
        # pattern, which is out of scope for Sprint 6.
        if v is None:
            return v
        if v not in CREDENTIAL_KEYS:
            raise ValueError(
                f"Unknown auth_type '{v}'. "
                f"Supported: {sorted(CREDENTIAL_KEYS)} or null."
            )
        return v


__all__ = [
    "CREDENTIAL_KEYS",
    "HostingType",
    "IntegrationType",
    "MCPServerConfigUpdate",
    "MCPServerFirestoreConfig",
    "MCPServerMetadata",
    # Re-exported from app/ for callers that want a single import surface.
    "SseConnectionConfig",
    "StdioConnectionConfig",
]
