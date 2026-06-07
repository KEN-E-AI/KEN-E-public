"""Tests for the numerical analyst agent tool (AH-149 / AH-114).

AH-114: the module-bottom side effect now registers a task-mode ``LlmAgent``
(via ``register_agent_subagent``) instead of an ``AgentTool``. Tests updated
to assert the task-mode contract; ``create_numerical_analyst_agent`` is unchanged.

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly rather than
clearing the registry first.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent, LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor

# Importing the module registers the task-mode subagent as a side effect.
import app.adk.tools.agent_tools.numerical_analyst as na
from app.adk.tools.registry.agent_tool_registry import get_agent_subagent


def test_create_numerical_analyst_agent_returns_leaf_agent() -> None:
    """create_numerical_analyst_agent is unchanged per AH-114 scope boundary."""
    agent = na.create_numerical_analyst_agent()
    assert isinstance(agent, Agent)
    assert agent.name == "numerical_analyst_agent"


def test_numerical_analyst_agent_has_code_executor() -> None:
    agent = na.create_numerical_analyst_agent()
    assert isinstance(agent.code_executor, BuiltInCodeExecutor)


def test_numerical_analyst_agent_has_no_other_tools() -> None:
    agent = na.create_numerical_analyst_agent()
    # The agent must carry no function tools or MCP toolsets — only code_executor.
    # tools list may be None or empty; never non-empty (would re-introduce the
    # Gemini 2.5+ multi-tool 400 error).
    tools = agent.tools or []
    assert tools == [], (
        f"numerical_analyst_agent must have no tools (only code_executor); "
        f"got {tools!r}"
    )


def test_create_numerical_analyst_subagent_returns_task_mode_llm_agent() -> None:
    """AH-114: new task-mode constructor for the ADK 2.0 chat tree."""
    agent = na.create_numerical_analyst_subagent()
    assert isinstance(agent, LlmAgent)
    assert agent.name == "numerical_analyst"
    assert agent.mode == "task"


def test_numerical_analyst_subagent_has_code_executor() -> None:
    """mode='task' is orthogonal to code_executor — the leaf's executor is unaffected."""
    agent = na.create_numerical_analyst_subagent()
    assert isinstance(agent.code_executor, BuiltInCodeExecutor)


def test_import_registers_agent_subagent_under_catalogue_name() -> None:
    """The import-time side effect registers a task-mode LlmAgent — not an AgentTool.

    AH-114: registry no longer stores AgentTool instances. The catalogue name
    maps to a task-mode LlmAgent with code_executor so the roster resolver (AH-115)
    can attach it to sub_agents= and benefit from native event propagation.
    """
    importlib.reload(na)
    agent = get_agent_subagent("numerical_analyst")
    assert isinstance(agent, LlmAgent)
    assert agent.name == "numerical_analyst"
    assert agent.mode == "task"
    assert isinstance(agent.code_executor, BuiltInCodeExecutor)
