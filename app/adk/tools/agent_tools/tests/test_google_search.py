"""Tests for the Google web search agent tool (AH-98).

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly rather than
clearing the registry first.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

# Importing the module registers the AgentTool as a side effect.
import app.adk.tools.agent_tools.google_search as gs
from app.adk.tools.registry.agent_tool_registry import get_agent_tool


def test_create_google_search_agent_returns_leaf_agent():
    agent = gs.create_google_search_agent()
    assert isinstance(agent, Agent)
    # Leaf name unchanged so the strategy researchers are unaffected.
    assert agent.name == "google_search_agent"


def test_import_registers_agent_tool_under_catalogue_name():
    # The process-global registry can be cleared by other test modules' teardown
    # (it's a shared singleton). Reload re-runs the module's registration side
    # effect deterministically — this is exactly the import-time path
    # hierarchy.py depends on in production.
    importlib.reload(gs)
    tool = get_agent_tool("google_search")
    assert isinstance(tool, AgentTool)
    # Stamped to the catalogue name so the roster filter (agent.google_search)
    # matches, even though the wrapped agent is named google_search_agent.
    assert tool.name == "google_search"
    assert tool.agent.name == "google_search_agent"
