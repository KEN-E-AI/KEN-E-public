"""
Shared agent components for strategy system.

This module has been refactored to use split agent architecture:
- Individual strategy agents are now in separate files (business_agents.py, competitive_agents.py, etc.)
- Each strategy uses researcher (with tools) + formatter (with schema) pattern
- This file contains only shared components used across all strategies
"""

import logging

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.genai import types

# Set up logging
logger = logging.getLogger(__name__)


# ============================================================================
# SHARED COMPONENTS
# ============================================================================


def create_google_search_agent() -> Agent:
    """Create the Google search sub-agent used by all strategy agents."""
    return Agent(
        name="google_search_agent",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )


__all__ = [
    "create_google_search_agent",
]
