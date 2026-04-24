"""MCP Server Configuration with environment variable resolution.

This module provides configuration models for MCP server connections,
supporting both stdio (local process) and SSE (remote HTTP) connection types.

Environment variables in YAML configs use ${VAR_NAME} syntax and are
automatically resolved using the shared.secrets module.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from shared.secrets import get_env_or_secret
from shared.structured_logging import get_structured_logger, log_context

logger = get_structured_logger(__name__)


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

    Note: ``${VAR}`` resolution happens in the loader (see
    :func:`_resolve_env_vars_in_dict`) **before** this model is constructed,
    so runtime ``env`` values are already resolved strings. The admin
    router path does NOT run the loader, so it sees literal ``${VAR}``
    strings end-to-end (Sprint 6 secret-leak fix).
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

    Note: ``${VAR}`` resolution happens in the loader (see
    :func:`_resolve_env_vars_in_dict`) **before** this model is constructed.
    The admin router deliberately bypasses the loader so literal ``${VAR}``
    strings flow through GET/PUT/audit without leaking resolved secrets
    (Sprint 6 secret-leak fix).
    """

    connection_type: Literal["sse"] = "sse"
    url: str = Field(..., description="SSE endpoint URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="HTTP headers to include"
    )
    timeout_seconds: int = Field(
        30, ge=5, le=300, description="Connection timeout in seconds"
    )


class MCPServerConfig(BaseModel):
    """Complete configuration for an MCP server.

    Defines all metadata needed to manage an MCP server connection,
    including connection parameters and resource estimates.

    Example YAML:
        google_analytics_mcp:
          description: "Google Analytics 4 data access"
          category: "analytics"
          tool_count: 12
          estimated_tokens: 1800
          keywords: ["analytics", "ga4", "traffic"]
          connection:
            connection_type: stdio
            command: "npx"
            args: ["-y", "@anthropic/mcp-server-google-analytics"]
          enabled: true
    """

    name: str = Field(..., description="Unique server identifier")
    description: str = Field(..., description="Human-readable description")
    category: str = Field(..., description="Tool category (e.g., 'analytics', 'crm')")
    tool_count: int = Field(0, ge=0, description="Expected number of tools")
    estimated_tokens: int = Field(
        1000, ge=0, description="Estimated context tokens for tool definitions"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Search keywords for discovery"
    )
    connection: StdioConnectionConfig | SseConnectionConfig = Field(
        ..., discriminator="connection_type"
    )
    enabled: bool = Field(True, description="Whether server is enabled")
    auth_type: str | None = Field(
        None, description="Auth type: 'ga_oauth' for per-user OAuth via header_provider"
    )

    @model_validator(mode="after")
    def validate_config(self) -> MCPServerConfig:
        """Validate the complete configuration."""
        if isinstance(self.connection, SseConnectionConfig):
            if not self.connection.url:
                raise ValueError(f"SSE server '{self.name}' requires a non-empty URL")
        return self


class MCPConfigLoader:
    """Loads and validates MCP server configurations from YAML.

    Supports environment variable resolution for secrets and
    provides validation with clear error messages.

    Usage:
        loader = MCPConfigLoader()
        configs = loader.load()
        ga_config = loader.get_server("google_analytics_mcp")
    """

    def __init__(self, config_path: Path | None = None):
        """Initialize the config loader.

        Args:
            config_path: Path to YAML config file. Defaults to mcp_servers.yaml
                        in the config subdirectory of this module.
        """
        self.config_path = (
            config_path or Path(__file__).parent / "config" / "mcp_servers.yaml"
        )
        self._configs: dict[str, MCPServerConfig] = {}

    @property
    def configs(self) -> dict[str, MCPServerConfig]:
        """Get loaded server configurations."""
        if not self._configs:
            self.load()
        return dict(self._configs)

    def load(self) -> dict[str, MCPServerConfig]:
        """Load configurations from YAML file.

        Returns:
            Dictionary mapping server names to their configurations.

        Raises:
            FileNotFoundError: If config file doesn't exist and is required.
        """
        if not self.config_path.exists():
            logger.warning(
                f"MCP config not found: {self.config_path}",
                extra=log_context(
                    component="mcp_config",
                    action="load_warning",
                    extra={"path": str(self.config_path)},
                ),
            )
            return {}

        with open(self.config_path) as f:
            raw_config = yaml.safe_load(f)

        if not raw_config:
            logger.warning("MCP config file is empty")
            return {}

        servers = raw_config.get("servers", {})
        for name, config in servers.items():
            try:
                config["name"] = name
                # Resolve ${VAR} patterns before Pydantic construction — the
                # connection sub-models used to do this via field validators
                # but that leaked resolved secrets through the admin PUT/GET
                # path. Resolution is now an explicit loader concern.
                config = _resolve_env_vars_in_dict(config)
                self._configs[name] = MCPServerConfig(**config)
                logger.info(
                    f"Loaded MCP server config: {name}",
                    extra=log_context(
                        component="mcp_config",
                        action="load_server",
                        extra={
                            "server_name": name,
                            "category": config.get("category"),
                            "enabled": config.get("enabled", True),
                        },
                    ),
                )
            except Exception as e:
                logger.error(
                    f"Invalid MCP config for '{name}': {e}",
                    extra=log_context(
                        component="mcp_config",
                        action="load_error",
                        error_message=str(e),
                        extra={"server_name": name},
                    ),
                )

        return self._configs

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get configuration for a specific server.

        Args:
            name: Server identifier

        Returns:
            Server configuration or None if not found
        """
        if not self._configs:
            self.load()
        return self._configs.get(name)

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Get all enabled server configurations.

        Returns:
            List of enabled server configurations
        """
        if not self._configs:
            self.load()
        return [c for c in self._configs.values() if c.enabled]

    def get_servers_by_category(self, category: str) -> list[MCPServerConfig]:
        """Get all servers in a specific category.

        Args:
            category: Category to filter by (e.g., 'analytics', 'crm')

        Returns:
            List of server configurations in the category
        """
        if not self._configs:
            self.load()
        return [
            c for c in self._configs.values() if c.category == category and c.enabled
        ]

    def reload(self) -> dict[str, MCPServerConfig]:
        """Force reload configurations from disk.

        Returns:
            Fresh dictionary of configurations
        """
        self._configs = {}
        return self.load()


def _resolve_env_pattern(value: str) -> str:
    """Resolve ${VAR_NAME} patterns in a string.

    Uses shared.secrets.get_env_or_secret for resolution, which supports:
    - Raw environment variables
    - sm:// Secret Manager format
    - Full GCP Secret Manager paths

    Args:
        value: String potentially containing ${VAR_NAME} patterns

    Returns:
        String with all patterns resolved

    Examples:
        >>> _resolve_env_pattern("Bearer ${API_KEY}")
        'Bearer actual_api_key_value'

        >>> _resolve_env_pattern("no_vars_here")
        'no_vars_here'
    """
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([^}]+)\}"

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        resolved = get_env_or_secret(var_name, "")
        if not resolved:
            logger.warning(
                f"Environment variable '{var_name}' not found, using empty string"
            )
        return resolved or ""

    return re.sub(pattern, replacer, value)


def _resolve_env_vars_in_dict(data: Any) -> Any:
    """Recursively resolve ``${VAR}`` patterns in every string in ``data``.

    Used by loaders (:class:`MCPConfigLoader.load`,
    :func:`FirestoreMCPLoader._doc_to_runtime_config`) to materialize
    secrets before constructing :class:`MCPServerConfig`. The admin router
    deliberately does NOT call this helper — it keeps literal ``${VAR}``
    strings end-to-end so GET/PUT responses, Firestore writes, and audit
    diffs never carry resolved secrets.
    """
    if isinstance(data, str):
        return _resolve_env_pattern(data)
    if isinstance(data, dict):
        return {k: _resolve_env_vars_in_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars_in_dict(v) for v in data]
    return data


# Singleton loader instance. Typed as the base loader interface; the concrete
# implementation is either ``MCPConfigLoader`` (YAML) or ``FirestoreMCPLoader``
# depending on the ``MCP_CONFIG_SOURCE`` env var.
_config_loader: MCPConfigLoader | None = None


def get_mcp_config_loader() -> MCPConfigLoader:
    """Get the singleton MCP config loader.

    The ``MCP_CONFIG_SOURCE`` env var selects the backing store:

    * ``"yaml"`` (default during the Sprint 6 transition) — reads from
      ``mcp_servers.yaml``. Preserves legacy behavior for local dev and for
      environments where the Firestore migration (Story 1.1.4-2) hasn't run yet.
    * ``"firestore"`` — reads from ``mcp_server_configs/{id}`` via
      ``FirestoreMCPLoader``, which falls back to YAML on connection errors.
      Operators should flip the env var after running the migration script
      against a given environment.

    Both loaders expose the same public surface (``.load``, ``.reload``,
    ``.configs``, ``.get_server``, ``.get_enabled_servers``,
    ``.get_servers_by_category``), so ``MCPServerManager`` consumes either
    without changes.

    Returns:
        Shared loader singleton (duck-typed as ``MCPConfigLoader``).
    """
    global _config_loader
    if _config_loader is None:
        source = os.getenv("MCP_CONFIG_SOURCE", "yaml").strip().lower()
        if source == "firestore":
            # Local import to keep google.cloud.firestore out of the YAML-only
            # code path (useful for tests that don't install firestore).
            from .firestore_loader import FirestoreMCPLoader

            _config_loader = FirestoreMCPLoader()  # type: ignore[assignment]
            logger.info(
                "MCP config source: firestore",
                extra=log_context(
                    component="mcp_config",
                    action="loader_selected",
                    extra={"source": "firestore"},
                ),
            )
        else:
            if source not in ("yaml", ""):
                logger.warning(
                    f"Unknown MCP_CONFIG_SOURCE={source!r}; defaulting to yaml",
                    extra=log_context(
                        component="mcp_config",
                        action="loader_unknown_source",
                        extra={"source": source},
                    ),
                )
            _config_loader = MCPConfigLoader()
            logger.info(
                "MCP config source: yaml",
                extra=log_context(
                    component="mcp_config",
                    action="loader_selected",
                    extra={"source": "yaml"},
                ),
            )
        _config_loader.load()
    return _config_loader


def reset_mcp_config_loader() -> None:
    """Reset the singleton loader (primarily for tests)."""
    global _config_loader
    _config_loader = None
