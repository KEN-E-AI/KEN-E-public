"""
Agent factory package for KEN-E.

Phase 1: config loader (load_agent_config, list_account_agent_configs, MergedAgentConfig)
         and build_agent() (AH-15) — turns a MergedAgentConfig into a working LlmAgent.
Phase 2: MCP toolset construction (build_toolset_for_doc, load_all_mcp_toolsets,
         load_toolsets_for_specialist, MCPFactoryError, MCPSchemaError).
Phase 2: Curated tool-roster resolution (resolve_specialist_roster,
         count_specialist_tool_roster, RosterCapExceededError,
         MAX_TOOLS_PER_SPECIALIST) (AH-13).
Phase 2: Available Specialists block (AH-14).
Phase 2 (AH-PRD-09 + AH-75): root-only build_hierarchy() — 1 Firestore read at
         deploy time; specialists resolved per-turn by specialist_runtime (AH-59)
         and attached to root.sub_agents per turn by sub_agent_attacher (AH-75).
         The root carries no specialist-dispatch tool; ADK's native
         transfer_to_agent is used, which propagates specialist events through
         the outer Runner's event stream natively.
SK-PRD-02: SandboxPool — process-wide pool of AgentEngineSandboxCodeExecutor instances
           keyed by (account_id, config_id), with LRU cap + idle TTL + striped locks.
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
from app.adk.agents.agent_factory.sandbox_pool import SandboxPool
from app.adk.agents.agent_factory.skill_metadata import (
    get_skill_build_metadata,
    record_skill_build_metadata,
)
from app.adk.agents.agent_factory.sub_agent_attacher import (
    attach_account_specialists,
    attach_specialists_before_agent_callback,
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
    "SandboxPool",
    "assemble_available_specialists_block",
    "attach_account_specialists",
    "attach_specialists_before_agent_callback",
    "build_agent",
    "build_hierarchy",
    "build_toolset_for_config",
    "build_toolset_for_doc",
    "count_specialist_tool_roster",
    "generate_dispatch_functions",
    "get_skill_build_metadata",
    "list_account_agent_configs",
    "load_agent_config",
    "load_all_mcp_toolsets",
    "load_toolsets_for_specialist",
    "record_skill_build_metadata",
    "resolve_specialist_roster",
]
