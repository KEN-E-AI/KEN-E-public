"""MCP connection sub-models shared between the agent runtime and the API.

These pydantic schemas describe how an MCP server is reached (stdio process
vs. SSE endpoint). Both ``MCPServerConfig`` (agent runtime, in
``app.adk.mcp_config.config``) and ``MCPServerFirestoreConfig`` (admin API,
in ``kene_api.models.mcp_server_models``) embed the union of these types,
so they must live in the one Python module both services can import.

Note: ``${VAR}`` resolution happens in the loader (see
``_resolve_env_vars_in_dict`` in ``app.adk.mcp_config.config``) **before**
these models are constructed, so runtime ``env`` / ``url`` values are
already-resolved strings. The admin router deliberately bypasses the
loader, so it sees literal ``${VAR}`` strings end-to-end (Sprint 6
secret-leak fix).
"""

from __future__ import annotations

from enum import auto
from typing import Literal

from pydantic import BaseModel, Field

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11 compat — StrEnum shipped in 3.11
    import enum

    class StrEnum(str, enum.Enum):  # type: ignore[no-redef]
        pass


class McpServerKind(StrEnum):
    """Identifies how an MCP server is hosted/reached.

    Open enum — adding new members is non-breaking. Existing Firestore docs
    that lack the ``kind`` field default to ``cloud_run`` (see migration
    script ``api/scripts/migrate_mcp_servers_add_kind.py``).
    """

    cloud_run = auto()  # KEN-E-hosted Cloud Run sidecar (default)
    zapier = auto()  # Zapier-hosted MCP endpoint


__all__ = [
    "MCPConnectionParams",
    "McpServerKind",
    "SseConnectionConfig",
    "StdioConnectionConfig",
]


class MCPConnectionParams(BaseModel):
    """Base connection parameters for MCP servers."""

    pass


class StdioConnectionConfig(MCPConnectionParams):
    """Configuration for stdio-based MCP connections (local processes).

    Stdio connections start a local process that communicates via stdin/stdout.
    Typically used for MCP servers installed via npm or running locally.

    Example:
        connection:
          connection_type: stdio
          command: "npx"
          args: ["-y", "@anthropic/mcp-server-google-analytics"]
          env:
            GA_PROPERTY_ID: "${GA_PROPERTY_ID}"
    """

    connection_type: Literal["stdio"] = "stdio"
    command: str = Field(..., description="Command to run (e.g., 'npx', 'python')")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the process"
    )
    working_dir: str | None = Field(None, description="Working directory for process")


class SseConnectionConfig(MCPConnectionParams):
    """Configuration for SSE-based MCP connections (remote servers).

    SSE connections connect to remote MCP servers over HTTP using
    Server-Sent Events for bidirectional communication.

    Example:
        connection:
          connection_type: sse
          url: "${HUBSPOT_MCP_URL}"
          headers:
            Authorization: "Bearer ${HUBSPOT_API_KEY}"
          timeout_seconds: 30
    """

    connection_type: Literal["sse"] = "sse"
    url: str = Field(..., description="SSE endpoint URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP headers to include"
    )
    timeout_seconds: int = Field(
        30, ge=5, le=300, description="Connection timeout in seconds"
    )
