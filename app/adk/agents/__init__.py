"""
ADK Agents Package
Exports multi-agent implementation with MCP integration
"""

# Single agent implementation (news only)
from .company_news_chatbot.agent import root_agent as news_only_agent

# Strategy docs supervisor implementation (news + analytics + strategy with MCP support)
from .create_strategy_docs_supervisor import create_strategy_docs_supervisor
from .google_analytics_agent_v4 import google_analytics_agent_v4

# Default export is the strategy docs supervisor with MCP
root_agent = create_strategy_docs_supervisor
multi_agent_root = create_strategy_docs_supervisor  # Alias for compatibility

__all__ = [
    'root_agent',
    'multi_agent_root',
    'create_strategy_docs_supervisor',
    'news_only_agent',
    'google_analytics_agent_v4'
]