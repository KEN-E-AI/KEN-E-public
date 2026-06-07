"""Tests for the Google web search agent tool (AH-98 / AH-114).

AH-114: the module-bottom side effect now registers a task-mode ``LlmAgent``
(via ``register_agent_subagent``) instead of an ``AgentTool``. Tests updated
to assert the task-mode contract; ``create_google_search_agent`` is unchanged.

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly rather than
clearing the registry first.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent, LlmAgent

# Importing the module registers the task-mode subagent as a side effect.
import app.adk.tools.agent_tools.google_search as gs
from app.adk.tools.registry.agent_tool_registry import get_agent_subagent


def test_create_google_search_agent_returns_leaf_agent():
    """create_google_search_agent is unchanged — strategy_agent still uses it."""
    agent = gs.create_google_search_agent()
    assert isinstance(agent, Agent)
    # Leaf name unchanged so the strategy researchers are unaffected.
    assert agent.name == "google_search_agent"


def test_create_google_search_subagent_returns_task_mode_llm_agent():
    """AH-114: new task-mode constructor for the ADK 2.0 chat tree."""
    agent = gs.create_google_search_subagent()
    assert isinstance(agent, LlmAgent)
    assert agent.name == "google_search"
    assert agent.mode == "task"


def test_import_registers_agent_subagent_under_catalogue_name():
    """The import-time side effect registers a task-mode LlmAgent — not an AgentTool.

    AH-114: registry no longer stores AgentTool instances; the catalogue name
    maps to a task-mode LlmAgent so the roster resolver (AH-115) can attach it
    to sub_agents= and benefit from native event propagation (AH-99 probe-1/4).
    """
    importlib.reload(gs)
    agent = get_agent_subagent("google_search")
    assert isinstance(agent, LlmAgent)
    assert agent.name == "google_search"
    assert agent.mode == "task"
