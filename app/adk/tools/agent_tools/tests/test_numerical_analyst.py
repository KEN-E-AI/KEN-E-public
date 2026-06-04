"""Tests for the numerical analyst agent tool (AH-149).

Importing the module is the production registration path (the side effect
hierarchy.py relies on), so these tests exercise it directly rather than
clearing the registry first.
"""

from __future__ import annotations

import importlib

from google.adk.agents import Agent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.tools.agent_tool import AgentTool

# Importing the module registers the AgentTool as a side effect.
import app.adk.tools.agent_tools.numerical_analyst as na
from app.adk.tools.registry.agent_tool_registry import get_agent_tool


def test_create_numerical_analyst_agent_returns_leaf_agent() -> None:
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


def test_import_registers_agent_tool_under_catalogue_name() -> None:
    # The process-global registry can be cleared by other test modules' teardown
    # (it's a shared singleton). Reload re-runs the module's registration side
    # effect deterministically — this is exactly the import-time path
    # hierarchy.py depends on in production.
    importlib.reload(na)
    tool = get_agent_tool("numerical_analyst")
    assert isinstance(tool, AgentTool)
    # Stamped to the catalogue name so the roster filter (agent.numerical_analyst)
    # matches, even though the wrapped agent is named numerical_analyst_agent.
    assert tool.name == "numerical_analyst"
    assert tool.agent.name == "numerical_analyst_agent"


def test_registered_agent_tool_agent_has_code_executor() -> None:
    importlib.reload(na)
    tool = get_agent_tool("numerical_analyst")
    assert tool is not None
    assert isinstance(tool.agent.code_executor, BuiltInCodeExecutor)
