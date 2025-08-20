#!/usr/bin/env python3
"""
ADK Multi-Agent Supervisor with MCP Integration
Production-ready agent with Google Analytics MCP server support
"""

# Import the stateless multi-agent supervisor with full MCP integration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.multi_agent_supervisor_v2 import supervisor_agent_v2

# Export for ADK deployment
agent = supervisor_agent_v2
root_agent = supervisor_agent_v2

# Wrap with AdkApp for proper deployment
from vertexai.preview import reasoning_engines

app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True
)