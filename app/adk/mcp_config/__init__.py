"""MCP Server management module for KEN-E agents.

This module provides:
- MCPServerConfig: Configuration models for MCP server connections
- MCPConfigLoader: YAML-based configuration loading with validation
- MCPServerManager: Lazy-loading server management with health monitoring
"""

from .config import (
    MCPConfigLoader,
    MCPConnectionParams,
    MCPServerConfig,
    SseConnectionConfig,
    StdioConnectionConfig,
    get_mcp_config_loader,
)
from .manager import (
    LoadedServer,
    MCPServerManager,
    get_mcp_manager,
    reset_mcp_manager,
)

__all__ = [
    "LoadedServer",
    "MCPConfigLoader",
    "MCPConnectionParams",
    "MCPServerConfig",
    "MCPServerManager",
    "SseConnectionConfig",
    "StdioConnectionConfig",
    "get_mcp_config_loader",
    "get_mcp_manager",
    "reset_mcp_manager",
]
