"""
Agent Engine app configuration for multi-agent supervisor v2.
"""

from vertexai.preview import reasoning_engines

# Try different import patterns for deployment compatibility
try:
    # Try relative import first (for local testing)
    from .multi_agent_supervisor_v2 import supervisor_agent_v2
except ImportError:
    try:
        # Try absolute import with agents prefix
        from agents.multi_agent_supervisor_v2 import supervisor_agent_v2
    except ImportError:
        # Try direct import (for deployment where files are copied to root)
        from multi_agent_supervisor_v2 import supervisor_agent_v2

# Create the ADK app for deployment
app = reasoning_engines.AdkApp(
    agent=supervisor_agent_v2,
    enable_tracing=True
)