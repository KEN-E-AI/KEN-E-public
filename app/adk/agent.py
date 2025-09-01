#!/usr/bin/env python3
"""
Create Strategy Docs Supervisor for Vertex AI Agent Engine
This module imports and exposes the strategy document creation supervisor for deployment.
"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import the strategy docs supervisor
from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor

# Export for ADK deployment - ADK looks for 'app' or 'root_agent'
root_agent = create_strategy_docs_supervisor
agent = create_strategy_docs_supervisor  # Also export as 'agent' for compatibility

# Export all required names
__all__ = ["create_strategy_docs_supervisor", "root_agent", "agent"]

print("✅ Create strategy docs supervisor loaded")
