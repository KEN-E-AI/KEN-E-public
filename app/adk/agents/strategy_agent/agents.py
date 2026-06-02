"""
Shared agent components for strategy system.

This module uses a split agent architecture:
- Individual strategy agents live in separate files (business_agents.py,
  competitive_agents.py, etc.); each strategy uses a researcher (with tools) +
  formatter (with schema) pattern.
- The shared Google-search leaf agent moved to
  ``app/adk/tools/agent_tools/google_search.py`` (AH-98) so the catalogued
  agent-as-a-tool and the strategy researchers share one definition. It is
  re-exported here for backward compatibility with existing imports
  (``from .agents import create_google_search_agent``).
"""

from app.adk.tools.agent_tools.google_search import create_google_search_agent

__all__ = [
    "create_google_search_agent",
]
