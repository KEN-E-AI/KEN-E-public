"""
ADK Agents Package
Exports multi-agent implementation with MCP integration

Uses AgentRegistry for lazy loading to avoid initializing agents at import
time, which improves test performance and allows tests to run without
all environment variables set.
"""

from .registry import get_registry

__all__ = [
    "create_strategy_docs_supervisor",
    "google_analytics_agent_v4",
    "ken_e_agent",
    "multi_agent_root",
    "news_only_agent",
    "root_agent",
]

# Map exported names to registry names.
# "news_only_agent" is a legacy alias for the "news" agent.
_EXPORT_TO_REGISTRY = {
    "ken_e_agent": "ken_e",
    "news_only_agent": "news",
    "google_analytics_agent_v4": "google_analytics",
    "create_strategy_docs_supervisor": "strategy",
    "root_agent": "root_agent",          # alias -> ken_e
    "multi_agent_root": "multi_agent_root",  # alias -> strategy
}


def __getattr__(name: str):
    """Lazy load agents via the registry on first access."""
    registry_name = _EXPORT_TO_REGISTRY.get(name)
    if registry_name is not None:
        return get_registry().get(registry_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
