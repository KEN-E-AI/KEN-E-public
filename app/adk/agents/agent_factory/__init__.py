"""
Agent factory package for KEN-E.

Phase 1: config loader (load_agent_config, list_account_agent_configs, MergedAgentConfig)
         and build_agent() (AH-15) — turns a MergedAgentConfig into a working LlmAgent.
Phase 2: MCP toolset construction (build_toolset_for_doc, load_all_mcp_toolsets,
         load_toolsets_for_specialist, MCPFactoryError, MCPSchemaError).
Phase 2: Curated tool-roster resolution (resolve_specialist_roster,
         count_specialist_tool_roster, RosterCapExceededError,
         MAX_TOOLS_PER_SPECIALIST) (AH-13).
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
from app.adk.agents.agent_factory.dispatch import (
    assemble_available_specialists_block,
    generate_dispatch_functions,
)
from app.adk.agents.agent_factory.mcp import (
    MCPFactoryError,
    MCPSchemaError,
    build_toolset_for_config,
    build_toolset_for_doc,
    load_all_mcp_toolsets,
    load_toolsets_for_specialist,
)
from app.adk.agents.agent_factory.roster import (
    MAX_TOOLS_PER_SPECIALIST,
    RosterCapExceededError,
    count_specialist_tool_roster,
    resolve_specialist_roster,
)

__all__ = [
    "MAX_TOOLS_PER_SPECIALIST",
    "AgentFactoryConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "FirestoreConnectionError",
    "MCPFactoryError",
    "MCPSchemaError",
    "MergedAgentConfig",
    "RosterCapExceededError",
    "assemble_available_specialists_block",
    "build_agent",
    "build_toolset_for_config",
    "build_toolset_for_doc",
    "count_specialist_tool_roster",
    "generate_dispatch_functions",
    "list_account_agent_configs",
    "load_agent_config",
    "load_all_mcp_toolsets",
    "load_toolsets_for_specialist",
    "resolve_specialist_roster",
    # Reserved for AH-17 — not yet implemented:
    # "build_hierarchy",
]
