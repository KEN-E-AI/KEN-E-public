"""
Agent factory package for KEN-E.

Phase 1: config loader (load_agent_config, list_account_agent_configs, MergedAgentConfig)
         and build_agent() (AH-15) — turns a MergedAgentConfig into a working LlmAgent.
Phase 2: MCP toolset construction (build_toolset_for_doc, load_all_mcp_toolsets,
         load_toolsets_for_specialist, MCPFactoryError, MCPSchemaError).
Phase 2 placeholder: build_hierarchy() — implemented in AH-17.
"""

from app.adk.agents.agent_factory.builder import build_agent
from app.adk.agents.agent_factory.config_loader import (
    AgentFactoryConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    FirestoreConnectionError,
    MergedAgentConfig,
    list_account_agent_configs,
    load_agent_config,
)
from app.adk.agents.agent_factory.mcp import (
    MCPFactoryError,
    MCPSchemaError,
    build_toolset_for_config,
    build_toolset_for_doc,
    load_all_mcp_toolsets,
    load_toolsets_for_specialist,
)

__all__ = [
    "AgentFactoryConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "FirestoreConnectionError",
    "MCPFactoryError",
    "MCPSchemaError",
    "MergedAgentConfig",
    "build_agent",
    "build_toolset_for_config",
    "build_toolset_for_doc",
    "list_account_agent_configs",
    "load_agent_config",
    "load_all_mcp_toolsets",
    "load_toolsets_for_specialist",
    # Reserved for AH-17 — not yet implemented:
    # "build_hierarchy",
]
