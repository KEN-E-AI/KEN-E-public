"""
Agent Engine app configuration for KEN-E chat agent.
"""

from vertexai.preview import reasoning_engines

# Try different import patterns for deployment compatibility
try:
    # Try relative import first (for local testing)
    from .ken_e_agent import ken_e_agent
except ImportError:
    try:
        # Try absolute import with agents prefix
        from agents.ken_e_agent import ken_e_agent
    except ImportError:
        # Try direct import (for deployment where files are copied to root)
        from ken_e_agent import ken_e_agent

# Create the ADK app for deployment
app = reasoning_engines.AdkApp(agent=ken_e_agent, enable_tracing=True)
