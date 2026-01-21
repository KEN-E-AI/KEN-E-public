"""
ADK Agents Package
Exports multi-agent implementation with MCP integration

Uses lazy loading to avoid initializing agents at import time,
which improves test performance and allows tests to run without
all environment variables set.
"""

__all__ = [
    "create_strategy_docs_supervisor",
    "google_analytics_agent_v4",
    "ken_e_agent",
    "multi_agent_root",
    "news_only_agent",
    "root_agent",
]

# Cache for lazy-loaded agents
_agent_cache = {}


def __getattr__(name: str):
    """Lazy load agents on first access.

    This prevents all agents from initializing when the package is imported,
    which allows tests to import utils modules without triggering agent
    initialization that requires environment variables.
    """
    if name in _agent_cache:
        return _agent_cache[name]

    if name == "news_only_agent":
        from .company_news_chatbot.agent import root_agent as news_only_agent
        _agent_cache[name] = news_only_agent
        return news_only_agent

    elif name == "create_strategy_docs_supervisor":
        from .create_strategy_docs_supervisor import create_strategy_docs_supervisor
        _agent_cache[name] = create_strategy_docs_supervisor
        return create_strategy_docs_supervisor

    elif name == "ken_e_agent":
        from .ken_e_agent import ken_e_agent
        _agent_cache[name] = ken_e_agent
        return ken_e_agent

    elif name == "google_analytics_agent_v4":
        from .google_analytics_agent_v4 import google_analytics_agent_v4
        _agent_cache[name] = google_analytics_agent_v4
        return google_analytics_agent_v4

    elif name == "root_agent":
        # Default export is KEN-E agent
        return __getattr__("ken_e_agent")

    elif name == "multi_agent_root":
        # Alias for compatibility
        return __getattr__("create_strategy_docs_supervisor")

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
