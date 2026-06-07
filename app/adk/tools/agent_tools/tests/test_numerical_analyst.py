"""Tests for the numerical analyst agent tool (AH-149 / AH-114 / AH-PRD-15 re-plan).

AH-PRD-15 re-plan (AH-121): the module-bottom side effect now registers an
*isolated* ``AgentTool`` (via ``register_isolated_agent_tool``) instead of a
task-mode ``LlmAgent``. Gemini 2.5+ rejects code execution alongside the function
tool that ``mode='task'`` injects (the same ``400 ... all search tools`` class as
google_search), so the code-execution leaf must be isolated in an AgentTool
sub-runner. The dropped ``usage_metadata`` (#3984) is recovered by the leaf's
``capture_agent_tool_usage`` after_model_callback.

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent, LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.tools.agent_tool import AgentTool

# Importing the module registers the isolated AgentTool as a side effect.
import app.adk.tools.agent_tools.numerical_analyst as na
from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
from app.adk.tools.registry.agent_tool_registry import (
    get_agent_subagent,
    get_isolated_agent_tool,
)


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


def test_create_numerical_analyst_agent_tool_isolates_code_exec_and_bills() -> None:
    """The chat-tree factory wraps an isolated, billed code-exec leaf in an AgentTool."""
    tool = na.create_numerical_analyst_agent_tool()
    assert isinstance(tool, AgentTool)
    assert tool.name == "numerical_analyst"
    leaf = tool.agent
    assert leaf.after_model_callback is capture_agent_tool_usage
    assert isinstance(leaf.code_executor, BuiltInCodeExecutor)
    # No function tools alongside the built-in code executor.
    assert (leaf.tools or []) == []


def test_import_registers_isolated_agent_tool_not_task_mode() -> None:
    """The import-time side effect registers an isolated AgentTool, NOT a task-mode leaf.

    AH-PRD-15 re-plan: numerical_analyst lives on the isolated lane (``AgentTool`` in
    ``.tools``) and is absent from the task-mode lane.
    """
    importlib.reload(na)
    tool = get_isolated_agent_tool("numerical_analyst")
    assert isinstance(tool, AgentTool)
    assert tool.name == "numerical_analyst"
    assert isinstance(tool.agent.code_executor, BuiltInCodeExecutor)
    assert tool.agent.after_model_callback is capture_agent_tool_usage
    # Not on the task-mode lane.
    assert get_agent_subagent("numerical_analyst") is None
