"""
Agent factory package for KEN-E.

Phase 1: config loader (load_agent_config, list_account_agent_configs, MergedAgentConfig).
Phase 1 placeholder: build_agent() — implemented in AH-15.
Phase 2 placeholder: build_hierarchy() — implemented in AH-17.
"""

from app.adk.agents.agent_factory.config_loader import (
    AgentFactoryConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    FirestoreConnectionError,
    MergedAgentConfig,
    list_account_agent_configs,
    load_agent_config,
)

__all__ = [
    "AgentFactoryConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "FirestoreConnectionError",
    "MergedAgentConfig",
    "list_account_agent_configs",
    "load_agent_config",
    # Reserved for AH-15 / AH-17 — not yet implemented:
    # "build_agent",
    # "build_hierarchy",
]
