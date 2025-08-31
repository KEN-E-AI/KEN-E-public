#!/usr/bin/env python3
"""
Strategy Orchestrator Agent for Vertex AI Agent Engine
This module imports and exposes the new strategy orchestrator for deployment.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import the new strategy orchestrator instead of the old create_strategy_docs
from agents.strategy_agent.orchestrator import app, strategy_agent

# Export for ADK deployment - ADK looks for 'app' or 'root_agent'
root_agent = strategy_agent
agent = strategy_agent  # Also export as 'agent' for compatibility

# Export all required names
__all__ = ["app", "strategy_agent", "root_agent", "agent"]

print("✅ Strategy orchestrator loaded (replacing old create_strategy_docs)")
