"""
ADK Agents Package
Exports multi-agent implementation with MCP integration
"""

# Single agent implementation (news only)
from .company_news_chatbot.agent import root_agent as news_only_agent

# Strategy docs supervisor implementation (strategy generation for account creation)
from .create_strategy_docs_supervisor import create_strategy_docs_supervisor

# KEN-E chat agent (news + analytics for frontend chat)
from .ken_e_agent import ken_e_agent

# Google Analytics agent
from .google_analytics_agent_v4 import google_analytics_agent_v4

# Default export is the KEN-E agent for chat
root_agent = ken_e_agent
multi_agent_root = create_strategy_docs_supervisor  # Alias for compatibility

__all__ = [
    "root_agent",
    "multi_agent_root",
    "create_strategy_docs_supervisor",
    "ken_e_agent",
    "news_only_agent",
    "google_analytics_agent_v4",
]
