"""
Agent Engine app configuration for create strategy docs supervisor.
"""

from vertexai.preview import reasoning_engines

# Try different import patterns for deployment compatibility
try:
    # Try relative import first (for local testing)
    from .create_strategy_docs_supervisor import create_strategy_docs_supervisor
except ImportError:
    try:
        # Try absolute import with agents prefix
        from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor
    except ImportError:
        # Try direct import (for deployment where files are copied to root)
        from create_strategy_docs_supervisor import create_strategy_docs_supervisor

# Create the ADK app for deployment
app = reasoning_engines.AdkApp(
    agent=create_strategy_docs_supervisor,
    enable_tracing=True
)