"""Unit tests for ``agent_tool_registry`` (AH-98).

The registry is the bridge between the static catalogue (``tools.yaml``
``agent_tools:`` entries) and the actual ``AgentTool`` instances the agent
factory attaches to a specialist. Mirrors ``test_function_tool_registry`` but
for agent-as-a-tool instances.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from app.adk.tools.registry.agent_tool_registry import (
    clear_agent_tool_registry,
    get_agent_tool,
    register_agent_tool,
    resolve_agent_tools,
)


@pytest.fixture(autouse=True)
def _clean_registry_between_tests():
    """Process-global registry — clear between tests to avoid leakage."""
    clear_agent_tool_registry()
    yield
    clear_agent_tool_registry()


def _stub_agent_tool(agent_name: str = "google_search_agent") -> AgentTool:
    return AgentTool(
        agent=Agent(name=agent_name, model="gemini-2.5-flash", description="stub")
    )


class TestRegisterAgentTool:
    def test_registers_and_returns_instance(self):
        tool = _stub_agent_tool()
        register_agent_tool("google_search", tool)
        assert get_agent_tool("google_search") is tool

    def test_stamps_registered_name_onto_tool(self):
        # The roster filter matches AgentTool.name against ``agent.{name}`` in
        # tool_ids. AgentTool.name defaults to the wrapped agent's name
        # ("google_search_agent"), so the registry must stamp the catalogue name
        # or the filter would silently drop the tool.
        tool = _stub_agent_tool(agent_name="google_search_agent")
        assert tool.name == "google_search_agent"
        register_agent_tool("google_search", tool)
        assert get_agent_tool("google_search").name == "google_search"

    def test_rejects_non_agent_tool(self):
        with pytest.raises(TypeError):
            register_agent_tool("google_search", object())  # type: ignore[arg-type]

    def test_overwriting_logs_at_warning(self, caplog: pytest.LogCaptureFixture):
        register_agent_tool("google_search", _stub_agent_tool())
        first = get_agent_tool("google_search")
        with caplog.at_level(logging.WARNING):
            register_agent_tool("google_search", _stub_agent_tool())
        second = get_agent_tool("google_search")
        assert first is not second
        assert any(
            "is being re-registered" in r.message and r.levelname == "WARNING"
            for r in caplog.records
        )


class TestGetAgentTool:
    def test_returns_none_for_unknown_name(self):
        assert get_agent_tool("nonexistent") is None


class TestResolveAgentTools:
    """``resolve_agent_tools`` is the resolver specialist_runtime calls."""

    def _registry_with_catalogue(self, names: list[str]) -> MagicMock:
        registry = MagicMock()
        registry.list_agent_tools.return_value = [
            SimpleNamespace(name=n) for n in names
        ]
        return registry

    def test_returns_registered_tools_in_catalogue_order(self):
        register_agent_tool("alpha", _stub_agent_tool("a"))
        register_agent_tool("beta", _stub_agent_tool("b"))
        registry = self._registry_with_catalogue(["alpha", "beta"])

        resolved = resolve_agent_tools(registry)

        assert [t.name for t in resolved] == ["alpha", "beta"]
        assert resolved[0] is get_agent_tool("alpha")

    def test_skips_catalogue_entries_with_no_registered_instance(
        self, caplog: pytest.LogCaptureFixture
    ):
        register_agent_tool("alpha", _stub_agent_tool("a"))
        registry = self._registry_with_catalogue(["alpha", "missing_instance"])

        with caplog.at_level(logging.WARNING):
            resolved = resolve_agent_tools(registry)

        assert [t.name for t in resolved] == ["alpha"]
        warning_messages = [
            r.message for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any("missing_instance" in m for m in warning_messages)

    def test_returns_empty_when_catalogue_empty(self):
        register_agent_tool("alpha", _stub_agent_tool("a"))
        registry = self._registry_with_catalogue([])

        assert resolve_agent_tools(registry) == []


class TestClearAgentToolRegistry:
    def test_clears_all(self):
        register_agent_tool("alpha", _stub_agent_tool("a"))
        clear_agent_tool_registry()
        assert get_agent_tool("alpha") is None
