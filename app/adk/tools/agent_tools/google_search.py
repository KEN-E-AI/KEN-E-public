"""Google web search agent tool (AH-98).

``create_google_search_agent()`` builds a leaf ``Agent`` holding the ADK built-in
``google_search`` tool. The built-in tool cannot be combined with other tools or
an ``output_schema`` in the same agent, so it lives in a dedicated leaf agent and
is exposed to other agents as an ``AgentTool`` (agent-as-a-tool).

This module also registers that ``AgentTool`` under the catalogue name
``google_search`` so it can be assigned to any agent via ``tool_ids`` (opt-in;
see the ``agent_tools:`` entry in ``tools.yaml``). The strategy researchers
import ``create_google_search_agent`` from here too (re-exported by
``app/adk/agents/strategy_agent/agents.py``) so there is a single definition.
"""

from __future__ import annotations

import logging

from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from app.adk.tools.registry.agent_tool_registry import register_agent_tool

logger = logging.getLogger(__name__)


def create_google_search_agent() -> Agent:
    """Create the Google search leaf agent (built-in ``google_search``, isolated)."""
    return Agent(
        name="google_search_agent",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )


# ---------------------------------------------------------------------------
# Registry wiring (side-effect on import)
# ---------------------------------------------------------------------------

register_agent_tool("google_search", AgentTool(agent=create_google_search_agent()))


__all__ = ["create_google_search_agent"]
