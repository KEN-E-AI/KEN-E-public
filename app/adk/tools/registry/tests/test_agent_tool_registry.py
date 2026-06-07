"""Unit tests for ``agent_tool_registry`` (AH-98 / AH-114).

AH-114 migrates the registry from ``AgentTool`` storage to task-mode
``LlmAgent`` *factory* storage. The tests here verify the new contract:

  * ``register_agent_subagent`` / ``get_agent_subagent`` / ``resolve_agent_subagents``
    are the primary API. ``register_agent_subagent`` takes a factory (zero-arg
    callable producing a fresh ``LlmAgent``), not a built instance.
  * ``get_agent_subagent`` / ``resolve_agent_subagents`` mint a *fresh*, parentless
    ``LlmAgent`` per call (ADK 2.0 forbids attaching one sub-agent to >1 parent).
  * ``register_agent_tool`` raises ``NotImplementedError`` (removed).
  * ``resolve_agent_tools`` returns ``[]`` and warns once per process (shim).
  * ``clear_agent_tool_registry`` clears the registry and resets the warn latch.

No ``AgentTool`` instance is ever stored or returned — the registry's new
strict-type check enforces this at registration time.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.adk.agents import LlmAgent

from app.adk.tools.registry.agent_tool_registry import (
    clear_agent_tool_registry,
    get_agent_subagent,
    get_agent_tool,
    register_agent_subagent,
    register_agent_tool,
    resolve_agent_subagents,
    resolve_agent_tools,
    task_mode_supported,
)


@pytest.fixture(autouse=True)
def _clean_registry_between_tests():
    """Process-global registry — clear between tests to avoid leakage.

    Also resets the ``_warned`` latch so deprecation-warning assertions
    are independent across tests.
    """
    clear_agent_tool_registry()
    yield
    clear_agent_tool_registry()


def _stub_subagent(name: str = "google_search") -> LlmAgent:
    """Create a minimal valid task-mode LlmAgent for testing."""
    return LlmAgent(
        name=name,
        model="gemini-2.5-flash",
        mode="task",
        description="stub",
        instruction="stub",
    )


def _registry_with_catalogue(names: list[str]) -> MagicMock:
    registry = MagicMock()
    registry.list_agent_tools.return_value = [SimpleNamespace(name=n) for n in names]
    return registry


# ---------------------------------------------------------------------------
# TestRegisterAgentSubagent
# ---------------------------------------------------------------------------


class TestRegisterAgentSubagent:
    def test_registers_and_returns_instance(self):
        # A constant factory: every read returns the same object, so identity holds.
        agent = _stub_subagent("google_search")
        register_agent_subagent("google_search", lambda: agent)
        assert get_agent_subagent("google_search") is agent

    def test_rejects_agent_tool_with_type_error(self):
        """A factory producing an AgentTool must be rejected — the point of AH-114."""
        try:
            from google.adk.agents import Agent
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable on this ADK version")

        leaf = Agent(
            name="google_search_agent", model="gemini-2.5-flash", description="stub"
        )
        agent_tool = AgentTool(agent=leaf)
        with pytest.raises(TypeError, match="AgentTool"):
            register_agent_subagent("google_search", lambda: agent_tool)  # type: ignore[arg-type,return-value]

    def test_rejects_non_llm_agent_with_type_error(self):
        with pytest.raises(TypeError):
            register_agent_subagent("google_search", lambda: object())  # type: ignore[arg-type,return-value]

    def test_rejects_non_task_mode_with_value_error(self):
        chat_agent = LlmAgent(
            name="google_search",
            model="gemini-2.5-flash",
            mode="chat",
            description="stub",
            instruction="stub",
        )
        with pytest.raises(ValueError, match="mode='task'"):
            register_agent_subagent("google_search", lambda: chat_agent)

    def test_rejects_name_mismatch_with_value_error(self):
        agent = LlmAgent(
            name="wrong_name",
            model="gemini-2.5-flash",
            mode="task",
            description="stub",
            instruction="stub",
        )
        with pytest.raises(ValueError, match="does not match"):
            register_agent_subagent("google_search", lambda: agent)

    def test_overwriting_logs_at_warning(self, caplog: pytest.LogCaptureFixture):
        first_agent = _stub_subagent("google_search")
        second_agent = _stub_subagent("google_search")
        register_agent_subagent("google_search", lambda: first_agent)
        first = get_agent_subagent("google_search")
        with caplog.at_level(logging.WARNING):
            register_agent_subagent("google_search", lambda: second_agent)
        second = get_agent_subagent("google_search")
        assert first is first_agent
        assert second is second_agent
        assert first is not second
        assert any(
            "re-registered" in r.message and r.levelname == "WARNING"
            for r in caplog.records
        )

    def test_no_agent_tool_ever_stored(self):
        """Structural guard: no AgentTool instance can be in the registry after registration."""
        register_agent_subagent(
            "google_search", lambda: _stub_subagent("google_search")
        )
        stored = get_agent_subagent("google_search")
        assert isinstance(stored, LlmAgent)
        try:
            from google.adk.tools.agent_tool import AgentTool

            assert not isinstance(stored, AgentTool)
        except ImportError:
            pass  # No AgentTool class — nothing to check.


# ---------------------------------------------------------------------------
# TestGetAgentSubagent
# ---------------------------------------------------------------------------


class TestGetAgentSubagent:
    def test_returns_none_for_unknown_name(self):
        assert get_agent_subagent("nonexistent") is None

    def test_calls_factory_on_each_read(self):
        # A constant factory returns the same object, so identity holds.
        agent = _stub_subagent("alpha")
        register_agent_subagent("alpha", lambda: agent)
        assert get_agent_subagent("alpha") is agent

    def test_returns_fresh_parentless_instance_each_call(self):
        """A constructing factory yields a distinct, parentless instance per call.

        ADK 2.0 forbids re-parenting a sub-agent, so the registry must never hand
        out a shared instance that a roster would then mount.
        """
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        first = get_agent_subagent("alpha")
        second = get_agent_subagent("alpha")
        assert first is not second
        assert first is not None and first.parent_agent is None
        assert second is not None and second.parent_agent is None


# ---------------------------------------------------------------------------
# TestResolveAgentSubagents
# ---------------------------------------------------------------------------


class TestResolveAgentSubagents:
    def test_returns_registered_agents_in_catalogue_order(self):
        # Constant factories so the resolved instance matches get_agent_subagent.
        alpha = _stub_subagent("alpha")
        beta = _stub_subagent("beta")
        register_agent_subagent("alpha", lambda: alpha)
        register_agent_subagent("beta", lambda: beta)
        registry = _registry_with_catalogue(["alpha", "beta"])

        resolved = resolve_agent_subagents(registry)

        assert [a.name for a in resolved] == ["alpha", "beta"]
        assert resolved[0] is get_agent_subagent("alpha")

    def test_skips_catalogue_entries_with_no_registered_instance(
        self, caplog: pytest.LogCaptureFixture
    ):
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        registry = _registry_with_catalogue(["alpha", "missing_instance"])

        with caplog.at_level(logging.WARNING):
            resolved = resolve_agent_subagents(registry)

        assert [a.name for a in resolved] == ["alpha"]
        assert any(
            "missing_instance" in r.message
            for r in caplog.records
            if r.levelname == "WARNING"
        )

    def test_returns_empty_when_catalogue_empty(self):
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        registry = _registry_with_catalogue([])
        assert resolve_agent_subagents(registry) == []

    def test_returns_llm_agents_not_agent_tools(self):
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        registry = _registry_with_catalogue(["alpha"])

        resolved = resolve_agent_subagents(registry)

        assert all(isinstance(a, LlmAgent) for a in resolved)
        try:
            from google.adk.tools.agent_tool import AgentTool

            assert not any(isinstance(a, AgentTool) for a in resolved)
        except ImportError:
            pass

    def test_mints_fresh_parentless_instances_each_call(self):
        """Each resolve builds new, parentless agents — the load-bearing invariant.

        ADK 2.0's ``BaseAgent.__set_parent_agent_for_sub_agents`` raises
        ``already has a parent`` if the same sub-agent instance is mounted on a
        second roster. Returning fresh instances per call is what lets one
        catalogue entry (e.g. ``numerical_analyst``) be attached to multiple
        specialists and survive hot-reload rebuilds.
        """
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        registry = _registry_with_catalogue(["alpha"])

        first = resolve_agent_subagents(registry)[0]
        second = resolve_agent_subagents(registry)[0]

        assert first is not second
        assert first.parent_agent is None
        assert second.parent_agent is None


# ---------------------------------------------------------------------------
# TestLegacyShim — register_agent_tool / resolve_agent_tools
# ---------------------------------------------------------------------------


class TestLegacyShim:
    def test_register_agent_tool_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="AH-114"):
            register_agent_tool("google_search", object())  # type: ignore[arg-type]

    def test_resolve_agent_tools_returns_empty_list(self):
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        registry = _registry_with_catalogue(["alpha"])

        result = resolve_agent_tools(registry)

        assert result == []

    def test_resolve_agent_tools_warns_once_per_process(
        self, caplog: pytest.LogCaptureFixture
    ):
        registry = _registry_with_catalogue([])

        with caplog.at_level(logging.WARNING):
            resolve_agent_tools(registry)
            resolve_agent_tools(registry)
            resolve_agent_tools(registry)

        warnings = [
            r
            for r in caplog.records
            if r.levelname == "WARNING" and "deprecated" in r.message.lower()
        ]
        # Exactly one warning despite three calls (warn-once latch).
        assert len(warnings) == 1

    def test_get_agent_tool_delegates_to_get_agent_subagent(self):
        """get_agent_tool is a forwarding alias to get_agent_subagent."""
        agent = _stub_subagent("google_search")
        register_agent_subagent("google_search", lambda: agent)
        assert get_agent_tool("google_search") is agent


# ---------------------------------------------------------------------------
# TestClearAgentToolRegistry
# ---------------------------------------------------------------------------


class TestClearAgentToolRegistry:
    def test_clears_all_registered_agents(self):
        register_agent_subagent("alpha", lambda: _stub_subagent("alpha"))
        clear_agent_tool_registry()
        assert get_agent_subagent("alpha") is None

    def test_resets_warn_latch(self, caplog: pytest.LogCaptureFixture):
        registry = _registry_with_catalogue([])

        # First call — emits one warning.
        with caplog.at_level(logging.WARNING):
            resolve_agent_tools(registry)
        caplog.clear()

        # clear_agent_tool_registry resets the latch.
        clear_agent_tool_registry()

        # Second call — emits the warning again (latch was reset).
        with caplog.at_level(logging.WARNING):
            resolve_agent_tools(registry)
        warnings = [
            r
            for r in caplog.records
            if r.levelname == "WARNING" and "deprecated" in r.message.lower()
        ]
        assert len(warnings) == 1


class TestTaskModeSupported:
    """Capability gate that keeps the 1.34.x strategy deploy tree importable.

    Producer modules build ``LlmAgent(mode='task')`` and register it at import
    time. On ADK 1.34.x ``LlmAgent`` has no ``mode`` field (Pydantic raises
    ``extra_forbidden``), so the strategy deploy-tree smoke test crashes on
    import unless the construction is gated on this check. See AH-PRD-15 §2.
    """

    def test_true_when_llm_agent_declares_mode_field(self):
        """Installed ADK is 2.0+, where ``mode`` is a declared LlmAgent field."""
        assert "mode" in LlmAgent.model_fields
        assert task_mode_supported() is True

    def test_false_when_llm_agent_lacks_mode_field(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Simulated ADK 1.34.x — no ``mode`` field, so task-mode is unsupported."""
        without_mode = {k: v for k, v in LlmAgent.model_fields.items() if k != "mode"}
        monkeypatch.setattr(LlmAgent, "model_fields", without_mode)
        assert task_mode_supported() is False


# ---------------------------------------------------------------------------
# TestIsolatedAgentToolLane (AH-PRD-15 re-plan)
# ---------------------------------------------------------------------------


def _iso_tool(name: str = "google_search"):
    """Build a minimal valid isolated AgentTool (leaf carries the billing callback)."""
    from google.adk.agents import Agent
    from google.adk.tools.agent_tool import AgentTool

    from app.adk.agents.agent_tool_billing import capture_agent_tool_usage

    leaf = Agent(
        name=name,
        model="gemini-2.5-flash",
        description="stub",
        instruction="stub",
        after_model_callback=capture_agent_tool_usage,
    )
    return AgentTool(agent=leaf)


class TestIsolatedAgentToolLane:
    def test_registers_and_resolves(self):
        from app.adk.tools.registry.agent_tool_registry import (
            get_isolated_agent_tool,
            register_isolated_agent_tool,
            resolve_isolated_agent_tools,
        )

        register_isolated_agent_tool(
            "google_search", lambda: _iso_tool("google_search")
        )
        got = get_isolated_agent_tool("google_search")
        assert type(got).__name__ == "AgentTool" and got.name == "google_search"
        resolved = resolve_isolated_agent_tools(
            _registry_with_catalogue(["google_search"])
        )
        assert [t.name for t in resolved] == ["google_search"]

    def test_rejects_non_agent_tool(self):
        from app.adk.tools.registry.agent_tool_registry import (
            register_isolated_agent_tool,
        )

        with pytest.raises(TypeError):
            register_isolated_agent_tool(
                "google_search", lambda: _stub_subagent("google_search")
            )

    def test_rejects_missing_billing_callback(self):
        from google.adk.agents import Agent
        from google.adk.tools.agent_tool import AgentTool

        from app.adk.tools.registry.agent_tool_registry import (
            register_isolated_agent_tool,
        )

        leaf = Agent(name="google_search", model="gemini-2.5-flash", description="stub")
        with pytest.raises(ValueError, match="capture_agent_tool_usage"):
            register_isolated_agent_tool("google_search", lambda: AgentTool(agent=leaf))

    def test_rejects_name_mismatch(self):
        from app.adk.tools.registry.agent_tool_registry import (
            register_isolated_agent_tool,
        )

        with pytest.raises(ValueError, match="does not match"):
            register_isolated_agent_tool(
                "google_search", lambda: _iso_tool("other_name")
            )

    def test_cross_lane_isolated_then_task_raises(self):
        from app.adk.tools.registry.agent_tool_registry import (
            register_agent_subagent,
            register_isolated_agent_tool,
        )

        register_isolated_agent_tool(
            "google_search", lambda: _iso_tool("google_search")
        )
        with pytest.raises(ValueError, match="isolated-AgentTool lane"):
            register_agent_subagent(
                "google_search", lambda: _stub_subagent("google_search")
            )

    def test_cross_lane_task_then_isolated_raises(self):
        from app.adk.tools.registry.agent_tool_registry import (
            register_agent_subagent,
            register_isolated_agent_tool,
        )

        register_agent_subagent(
            "google_search", lambda: _stub_subagent("google_search")
        )
        with pytest.raises(ValueError, match="task-mode lane"):
            register_isolated_agent_tool(
                "google_search", lambda: _iso_tool("google_search")
            )
