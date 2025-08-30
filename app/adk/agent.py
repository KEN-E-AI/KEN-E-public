#!/usr/bin/env python3
"""
ADK Multi-Agent Supervisor with MCP Integration
Production-ready agent with Google Analytics MCP server support
"""

# Import from the create strategy docs agent file
from create_strategy_docs import agent, root_agent, app

# Export for ADK deployment
__all__ = ['agent', 'root_agent', 'app']