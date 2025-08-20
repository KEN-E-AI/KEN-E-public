"""
ADK Agents Package
Exports multi-agent implementation with MCP integration
"""

# Single agent implementation (news only)
from .company_news_chatbot.agent import root_agent as news_only_agent

# Stateless multi-agent implementation (news + analytics with MCP support)
from .multi_agent_supervisor_v2 import supervisor_agent_v2
from .google_analytics_agent_v4 import google_analytics_agent_v4

# Default export is the stateless multi-agent version with MCP
root_agent = supervisor_agent_v2
multi_agent_root = supervisor_agent_v2  # Alias for compatibility

__all__ = [
    'root_agent',
    'multi_agent_root',
    'supervisor_agent_v2',
    'news_only_agent',
    'google_analytics_agent_v4'
]