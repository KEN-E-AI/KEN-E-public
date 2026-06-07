"""Tests for the Google web search agent tool (AH-98 / AH-114 / AH-PRD-15 re-plan).

AH-PRD-15 re-plan (AH-121): the module-bottom side effect now registers an
*isolated* ``AgentTool`` (via ``register_isolated_agent_tool``) instead of a
task-mode ``LlmAgent``. The built-in ``google_search`` grounding tool cannot
share its LLM request with the function tool that ``mode='task'`` injects
(``400 ... all search tools``), so it must be isolated in an AgentTool sub-runner.
The dropped ``usage_metadata`` (#3984) is recovered by the leaf's
``capture_agent_tool_usage`` after_model_callback.

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent, LlmAgent
from google.adk.tools.agent_tool import AgentTool

# Importing the module registers the isolated AgentTool as a side effect.
import app.adk.tools.agent_tools.google_search as gs
from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
from app.adk.tools.registry.agent_tool_registry import (
    get_agent_subagent,
    get_isolated_agent_tool,
)


def test_create_google_search_agent_returns_leaf_agent():
    """create_google_search_agent is unchanged — strategy_agent still uses it."""
    agent = gs.create_google_search_agent()
    assert isinstance(agent, Agent)
    # Leaf name unchanged so the strategy researchers are unaffected.
    assert agent.name == "google_search_agent"


def test_create_google_search_agent_tool_isolates_search_and_bills():
    """The chat-tree factory wraps an isolated, billed search leaf in an AgentTool."""
    tool = gs.create_google_search_agent_tool()
    assert isinstance(tool, AgentTool)
    # AgentTool.name == leaf.name == catalogue name → matches agent.google_search.
    assert tool.name == "google_search"
    leaf = tool.agent
    assert leaf.after_model_callback is capture_agent_tool_usage
    # Exactly one tool, the built-in grounding tool — no injected sibling.
    assert len(leaf.tools) == 1


def test_create_google_search_subagent_still_constructs_dormant_task_mode():
    """The task-mode constructor is retained (dormant) but no longer registered."""
    agent = gs.create_google_search_subagent()
    assert isinstance(agent, LlmAgent)
    assert agent.name == "google_search"
    assert agent.mode == "task"


def test_import_registers_isolated_agent_tool_not_task_mode():
    """The import-time side effect registers an isolated AgentTool, NOT a task-mode leaf.

    AH-PRD-15 re-plan: google_search lives on the isolated lane (``AgentTool`` in
    ``.tools``) and is absent from the task-mode lane.
    """
    importlib.reload(gs)
    tool = get_isolated_agent_tool("google_search")
    assert isinstance(tool, AgentTool)
    assert tool.name == "google_search"
    assert tool.agent.after_model_callback is capture_agent_tool_usage
    # Not on the task-mode lane.
    assert get_agent_subagent("google_search") is None
