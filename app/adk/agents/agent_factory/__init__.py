"""
Agent factory package for KEN-E.

Phase 1: config loader (load_agent_config, list_account_agent_configs, MergedAgentConfig)
         and build_agent() (AH-15) — turns a MergedAgentConfig into a working LlmAgent.
Phase 2: MCP toolset construction (build_toolset_for_doc, load_all_mcp_toolsets,
         load_toolsets_for_specialist, MCPFactoryError, MCPSchemaError).
Phase 2: Curated tool-roster resolution (resolve_specialist_roster,
         count_specialist_tool_roster, RosterCapExceededError,
         MAX_TOOLS_PER_SPECIALIST) (AH-13).
Phase 2 (AH-PRD-09): delegate_to_specialist unified dispatch tool (AH-60);
         root-only build_hierarchy() — 1 Firestore read at deploy time;
         specialists resolved per-turn by specialist_runtime (AH-59).
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
    delegate_to_specialist,
    generate_dispatch_functions,
)
from app.adk.agents.agent_factory.hierarchy import ROOT_CONFIG_ID, build_hierarchy
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
    "ROOT_CONFIG_ID",
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
    "build_hierarchy",
    "build_toolset_for_config",
    "build_toolset_for_doc",
    "count_specialist_tool_roster",
    "delegate_to_specialist",
    "generate_dispatch_functions",
    "list_account_agent_configs",
    "load_agent_config",
    "load_all_mcp_toolsets",
    "load_toolsets_for_specialist",
    "resolve_specialist_roster",
]
