"""
Agent Engine app configuration for multi-agent supervisor v2.
"""

from vertexai.preview import reasoning_engines
from .multi_agent_supervisor_v2 import supervisor_agent_v2

# Create the ADK app for deployment
app = reasoning_engines.AdkApp(
    agent=supervisor_agent_v2,
    enable_tracing=True
)