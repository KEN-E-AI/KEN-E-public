"""Unit tests for app.adk.agents.agent_factory.roster.

All tests are self-contained and do not require live GCP, ADK, or ToolRegistry
YAML files.  Registry behaviour is exercised via _FakeRegistry / _fake_tool().
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.adk.agents.agent_factory.mcp import MCPFactoryError
from app.adk.agents.agent_factory.roster import (
    MAX_TOOLS_PER_SPECIALIST,
    RosterCapExceededError,
    count_specialist_tool_roster,
    per_server_allowed_tools,
    resolve_specialist_roster,
)

# ---------------------------------------------------------------------------
# Fake registry helpers
# ---------------------------------------------------------------------------


def _fake_tool(mcp_server: str | None) -> MagicMock:
    """Return a minimal ToolDefinition-like object with an mcp_server attribute."""
    t = MagicMock()
    t.mcp_server = mcp_server
    return t


def _fake_agent_tool_def(name: str, *, default_global: bool = False) -> MagicMock:
    """Minimal ToolDefinition-like for an ``agent_tools:`` catalogue entry."""
    t = MagicMock()
    t.name = name
    t.default_global = default_global
    return t


def _agent_tool(name: str) -> MagicMock:
    """Minimal AgentTool-like instance exposing a ``name`` attribute."""
    t = MagicMock()
    t.name = name
    return t


class _FakeRegistry:
    """In-memory stand-in for ToolRegistry that returns a fixed tool list."""

    def __init__(
        self,
        tools: list[MagicMock],
        agent_tool_defs: list[MagicMock] | None = None,
    ) -> None:
        self._tools = tools
        self._agent_tool_defs = agent_tool_defs or []

    def list_tools(self) -> list[MagicMock]:
        return list(self._tools)

    def list_agent_tools(self) -> list[MagicMock]:
        return list(self._agent_tool_defs)


def _registry_for(*server_tool_pairs: tuple[str, int]) -> _FakeRegistry:
    """Build a registry where each (server_id, n) pair contributes n tools."""
    tools: list[MagicMock] = []
    for server_id, n in server_tool_pairs:
        tools.extend(_fake_tool(server_id) for _ in range(n))
    return _FakeRegistry(tools)


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_max_tools_per_specialist_is_30(self) -> None:
        assert MAX_TOOLS_PER_SPECIALIST == 30


# ---------------------------------------------------------------------------
# TestRosterCapExceededError
# ---------------------------------------------------------------------------


class TestRosterCapExceededError:
    def test_is_subclass_of_mcp_factory_error(self) -> None:
        assert issubclass(RosterCapExceededError, MCPFactoryError)

    def test_can_be_raised_and_caught_as_mcp_factory_error(self) -> None:
        with pytest.raises(MCPFactoryError):
            raise RosterCapExceededError("boom")

    def test_message_is_preserved(self) -> None:
        err = RosterCapExceededError("specialist 'x' exceeded cap")
        assert "specialist 'x' exceeded cap" in str(err)


# ---------------------------------------------------------------------------
# TestCountSpecialistToolRoster
# ---------------------------------------------------------------------------


class TestCountSpecialistToolRoster:
    def test_five_function_tools_no_mcp_servers_returns_5(self) -> None:
        registry = _registry_for()
        function_tools = [MagicMock() for _ in range(5)]

        result = count_specialist_tool_roster(
            "my_specialist",
            mcp_server_ids=[],
            function_tools=function_tools,
            registry=registry,
        )

        assert result == 5

    def test_eight_registry_entries_plus_22_function_tools_returns_30(self) -> None:
        # Neutral server id: this test exercises the count arithmetic at the cap
        # (8 mcp + 22 function = 30), not any real server's catalogue size.
        registry = _registry_for(("example_mcp", 8))
        function_tools = [MagicMock() for _ in range(22)]

        result = count_specialist_tool_roster(
            "capacity_specialist",
            mcp_server_ids=["example_mcp"],
            function_tools=function_tools,
            registry=registry,
        )

        assert result == 30

    def test_unknown_server_falls_back_to_count_1(self) -> None:
        registry = _registry_for()
        result = count_specialist_tool_roster(
            "unknown_specialist",
            mcp_server_ids=["unknown_server"],
            function_tools=[],
            registry=registry,
        )

        assert result == 1

    def test_unknown_server_emits_warning_log_naming_server(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        registry = _registry_for()

        with caplog.at_level(
            logging.WARNING, logger="app.adk.agents.agent_factory.roster"
        ):
            count_specialist_tool_roster(
                "any_specialist",
                mcp_server_ids=["totally_unknown_server"],
                function_tools=[],
                registry=registry,
            )

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("totally_unknown_server" in m for m in warning_messages)

    def test_two_specialists_sharing_same_mcp_server_each_get_same_count(self) -> None:
        registry = _registry_for(("shared_mcp", 5))
        function_tools_a = [MagicMock() for _ in range(3)]
        function_tools_b = [MagicMock() for _ in range(7)]

        count_a = count_specialist_tool_roster(
            "specialist_a",
            mcp_server_ids=["shared_mcp"],
            function_tools=function_tools_a,
            registry=registry,
        )
        count_b = count_specialist_tool_roster(
            "specialist_b",
            mcp_server_ids=["shared_mcp"],
            function_tools=function_tools_b,
            registry=registry,
        )

        assert count_a == 5 + 3
        assert count_b == 5 + 7

    def test_sharing_does_not_mutate_registry_between_calls(self) -> None:
        """Counting for specialist_a must not inflate the count for specialist_b."""
        registry = _registry_for(("shared_mcp", 4))

        count_specialist_tool_roster(
            "specialist_a",
            mcp_server_ids=["shared_mcp"],
            function_tools=[],
            registry=registry,
        )
        count_after_first = count_specialist_tool_roster(
            "specialist_b",
            mcp_server_ids=["shared_mcp"],
            function_tools=[],
            registry=registry,
        )

        assert count_after_first == 4

    def test_code_execution_flag_is_not_a_parameter_and_cannot_alter_count(
        self,
    ) -> None:
        """Built-in flags such as code_execution_enabled are not accepted by
        count_specialist_tool_roster and therefore have no effect on the count."""
        registry = _registry_for(("some_mcp", 3))
        function_tools = [MagicMock() for _ in range(2)]

        base_count = count_specialist_tool_roster(
            "spec",
            mcp_server_ids=["some_mcp"],
            function_tools=function_tools,
            registry=registry,
        )

        assert base_count == 5
        assert not hasattr(count_specialist_tool_roster, "code_execution_enabled")

    def test_multiple_servers_counts_are_summed(self) -> None:
        registry = _registry_for(("server_a", 10), ("server_b", 15))
        function_tools = [MagicMock() for _ in range(3)]

        result = count_specialist_tool_roster(
            "multi_server_specialist",
            mcp_server_ids=["server_a", "server_b"],
            function_tools=function_tools,
            registry=registry,
        )

        assert result == 10 + 15 + 3

    def test_zero_tools_zero_servers_returns_0(self) -> None:
        registry = _registry_for()

        result = count_specialist_tool_roster(
            "empty_specialist",
            mcp_server_ids=[],
            function_tools=[],
            registry=registry,
        )

        assert result == 0

    def test_count_includes_agent_tools(self) -> None:
        registry = _registry_for(("srv", 2))
        result = count_specialist_tool_roster(
            "spec",
            mcp_server_ids=["srv"],
            function_tools=[MagicMock()],
            agent_tools=[MagicMock(), MagicMock()],
            registry=registry,
        )

        assert result == 2 + 1 + 2


# ---------------------------------------------------------------------------
# TestResolveSpecialistRoster
# ---------------------------------------------------------------------------


class TestResolveSpecialistRoster:
    def test_30_logical_tools_at_cap_succeeds(self) -> None:
        registry = _registry_for(("ga_mcp", 8))
        mcp_toolset = MagicMock(name="ga_toolset")
        function_tools = [MagicMock() for _ in range(22)]

        result = resolve_specialist_roster(
            "analytics_specialist",
            mcp_toolsets={"ga_mcp": mcp_toolset},
            function_tools=function_tools,
            mcp_server_ids=["ga_mcp"],
            registry=registry,
        )

        assert result is not None

    def test_31_logical_tools_raises_roster_cap_exceeded_error(self) -> None:
        registry = _registry_for(("ga_mcp", 9))
        mcp_toolset = MagicMock(name="ga_toolset")
        function_tools = [MagicMock() for _ in range(22)]

        with pytest.raises(RosterCapExceededError) as exc_info:
            resolve_specialist_roster(
                "overloaded_specialist",
                mcp_toolsets={"ga_mcp": mcp_toolset},
                function_tools=function_tools,
                mcp_server_ids=["ga_mcp"],
                registry=registry,
            )

        assert "overloaded_specialist" in str(exc_info.value)
        assert "31" in str(exc_info.value)

    def test_result_ordering_mcp_toolsets_before_function_tools(self) -> None:
        registry = _registry_for(("server_x", 2), ("server_y", 3))
        ts_x = MagicMock(name="toolset_x")
        ts_y = MagicMock(name="toolset_y")
        ft_1 = MagicMock(name="func_tool_1")
        ft_2 = MagicMock(name="func_tool_2")

        result = resolve_specialist_roster(
            "ordered_specialist",
            mcp_toolsets={"server_x": ts_x, "server_y": ts_y},
            function_tools=[ft_1, ft_2],
            mcp_server_ids=["server_x", "server_y"],
            registry=registry,
        )

        assert result == [ts_x, ts_y, ft_1, ft_2]

    def test_mcp_toolset_dict_insertion_order_preserved(self) -> None:
        registry = _registry_for(("alpha", 1), ("beta", 1), ("gamma", 1))
        ts_alpha = MagicMock(name="ts_alpha")
        ts_beta = MagicMock(name="ts_beta")
        ts_gamma = MagicMock(name="ts_gamma")
        ft = MagicMock(name="ft")

        result = resolve_specialist_roster(
            "order_check",
            mcp_toolsets={"alpha": ts_alpha, "beta": ts_beta, "gamma": ts_gamma},
            function_tools=[ft],
            mcp_server_ids=["alpha", "beta", "gamma"],
            registry=registry,
        )

        assert result[:3] == [ts_alpha, ts_beta, ts_gamma]
        assert result[3] is ft

    def test_empty_tools_and_empty_mcp_server_ids_returns_empty_list(self) -> None:
        registry = _registry_for()

        result = resolve_specialist_roster(
            "empty_specialist",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            registry=registry,
        )

        assert result == []

    def test_registry_none_calls_get_default_registry(self) -> None:
        fake_default_registry = _registry_for()

        with patch(
            "app.adk.tools.registry.tool_registry.get_default_registry"
        ) as mock_get_default:
            mock_get_default.return_value = fake_default_registry

            result = resolve_specialist_roster(
                "default_reg_specialist",
                mcp_toolsets={},
                function_tools=[],
                mcp_server_ids=[],
                registry=None,
            )

        mock_get_default.assert_called_once()
        assert result == []

    def test_registry_none_import_get_default_registry_path(self) -> None:
        """roster.py defers the import inside the function body, so the patch
        target is the canonical home of get_default_registry, not the roster
        module namespace (which never binds the name at module level)."""
        fake_default_registry = _registry_for(("srv", 2))
        ts = MagicMock(name="toolset")

        with patch(
            "app.adk.tools.registry.tool_registry.get_default_registry",
            return_value=fake_default_registry,
        ):
            result = resolve_specialist_roster(
                "lazy_import_spec",
                mcp_toolsets={"srv": ts},
                function_tools=[],
                mcp_server_ids=["srv"],
                registry=None,
            )

        assert result == [ts]

    def test_exactly_at_cap_does_not_raise(self) -> None:
        registry = _registry_for(("capped_mcp", 30))
        ts = MagicMock(name="capped_toolset")

        result = resolve_specialist_roster(
            "at_cap_specialist",
            mcp_toolsets={"capped_mcp": ts},
            function_tools=[],
            mcp_server_ids=["capped_mcp"],
            registry=registry,
        )

        assert ts in result

    def test_one_over_cap_raises(self) -> None:
        registry = _registry_for(("over_mcp", 31))
        ts = MagicMock(name="over_toolset")

        with pytest.raises(RosterCapExceededError):
            resolve_specialist_roster(
                "over_cap_specialist",
                mcp_toolsets={"over_mcp": ts},
                function_tools=[],
                mcp_server_ids=["over_mcp"],
                registry=registry,
            )

    def test_error_message_contains_specialist_name_and_count(self) -> None:
        registry = _registry_for(("srv", 1))
        function_tools = [MagicMock() for _ in range(MAX_TOOLS_PER_SPECIALIST + 1)]

        with pytest.raises(RosterCapExceededError) as exc_info:
            resolve_specialist_roster(
                "my_named_specialist",
                mcp_toolsets={"srv": MagicMock()},
                function_tools=function_tools,
                mcp_server_ids=["srv"],
                registry=registry,
            )

        message = str(exc_info.value)
        assert "my_named_specialist" in message
        expected_count = 1 + len(function_tools)
        assert str(expected_count) in message

    # ------------------------------------------------------------------
    # Input validation: duplicate server IDs
    # ------------------------------------------------------------------

    def test_duplicate_server_ids_raises_value_error(self) -> None:
        registry = _registry_for(("analytics_mcp", 10))
        ts = MagicMock(name="ts")

        with pytest.raises(ValueError, match="duplicate"):
            resolve_specialist_roster(
                "dup_spec",
                mcp_toolsets={"analytics_mcp": ts},
                function_tools=[],
                mcp_server_ids=["analytics_mcp", "analytics_mcp"],
                registry=registry,
            )

    def test_duplicate_server_ids_error_message_names_the_specialist(self) -> None:
        registry = _registry_for(("srv", 1))
        ts = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            resolve_specialist_roster(
                "named_dup_specialist",
                mcp_toolsets={"srv": ts},
                function_tools=[],
                mcp_server_ids=["srv", "srv"],
                registry=registry,
            )

        assert "named_dup_specialist" in str(exc_info.value)

    # ------------------------------------------------------------------
    # Input validation: blank / empty server IDs
    # ------------------------------------------------------------------

    def test_empty_string_server_id_raises_value_error(self) -> None:
        registry = _registry_for(("real_mcp", 3))
        ts = MagicMock()

        with pytest.raises(ValueError, match="empty or blank"):
            resolve_specialist_roster(
                "blank_id_spec",
                mcp_toolsets={"real_mcp": ts, "": MagicMock()},
                function_tools=[],
                mcp_server_ids=["real_mcp", ""],
                registry=registry,
            )

    def test_whitespace_only_server_id_raises_value_error(self) -> None:
        registry = _registry_for(("real_mcp", 2))
        ts = MagicMock()

        with pytest.raises(ValueError, match="empty or blank"):
            resolve_specialist_roster(
                "ws_id_spec",
                mcp_toolsets={"real_mcp": ts, "   ": MagicMock()},
                function_tools=[],
                mcp_server_ids=["real_mcp", "   "],
                registry=registry,
            )

    # ------------------------------------------------------------------
    # Input validation: mcp_server_ids must match mcp_toolsets keys
    # ------------------------------------------------------------------

    def test_mismatched_server_ids_and_toolsets_raises_value_error(self) -> None:
        registry = _registry_for(("server_a", 2))
        ts = MagicMock()

        with pytest.raises(ValueError):
            resolve_specialist_roster(
                "mismatch_spec",
                mcp_toolsets={"server_a": ts},
                function_tools=[],
                mcp_server_ids=["server_b"],
                registry=registry,
            )

    # ------------------------------------------------------------------
    # TOCTOU: mutations after call do not affect returned list
    # ------------------------------------------------------------------

    def test_mutation_of_mcp_toolsets_after_call_does_not_affect_result(self) -> None:
        registry = _registry_for(("srv", 1))
        ts = MagicMock(name="original_toolset")
        toolsets: dict = {"srv": ts}

        result = resolve_specialist_roster(
            "toctou_spec",
            mcp_toolsets=toolsets,
            function_tools=[],
            mcp_server_ids=["srv"],
            registry=registry,
        )

        # Mutate the source dict after the call — returned list must be unaffected.
        toolsets["srv"] = MagicMock(name="replacement_toolset")

        assert result == [ts]

    def test_mutation_of_function_tools_after_call_does_not_affect_result(self) -> None:
        registry = _registry_for(("srv", 1))
        ft = MagicMock(name="original_ft")
        function_tools = [ft]

        result = resolve_specialist_roster(
            "toctou_ft_spec",
            mcp_toolsets={"srv": MagicMock()},
            function_tools=function_tools,
            mcp_server_ids=["srv"],
            registry=registry,
        )

        # Mutate the source list after the call.
        function_tools.append(MagicMock(name="injected_ft"))

        assert ft in result
        assert len(result) == 2  # 1 toolset + 1 original function tool


class TestResolveSpecialistRosterWithToolIds:
    """AH-PRD-06: per-agent ``tool_ids`` allowlist branch in the resolver."""

    def test_tool_ids_none_preserves_legacy_behaviour(self) -> None:
        registry = _registry_for(("server_x", 2))
        ts = MagicMock(name="ts_x")
        result = resolve_specialist_roster(
            "legacy_spec",
            mcp_toolsets={"server_x": ts},
            function_tools=[],
            mcp_server_ids=["server_x"],
            tool_ids=None,
            registry=registry,
        )
        assert result == [ts]

    def test_tool_ids_empty_returns_empty_roster(self) -> None:
        registry = _registry_for(("server_x", 2))
        ts = MagicMock(name="ts_x")
        result = resolve_specialist_roster(
            "empty_tool_ids_spec",
            mcp_toolsets={"server_x": ts},
            function_tools=[],
            mcp_server_ids=["server_x"],
            tool_ids=[],
            registry=registry,
        )
        assert result == []

    def test_tool_ids_filters_to_listed_server_tools(self) -> None:
        # Within-toolset filtering happens at construction (hierarchy.py
        # passes ``allowed_tool_names`` to ``build_toolset_for_doc``); the
        # resolver just keeps or drops whole toolsets and prunes function
        # tools. So a toolset whose server appears in tool_ids passes
        # through unchanged.
        registry = _registry_for(("server_x", 2))
        ts = MagicMock(name="ts_x")
        result = resolve_specialist_roster(
            "filtered_spec",
            mcp_toolsets={"server_x": ts},
            function_tools=[],
            mcp_server_ids=["server_x"],
            tool_ids=["server_x.tool_one"],
            registry=registry,
        )
        assert result == [ts]

    def test_tool_ids_drops_toolset_with_no_allowed_tools(self) -> None:
        registry = _registry_for(("server_x", 1), ("server_y", 1))
        ts_x = MagicMock(name="ts_x")
        ts_y = MagicMock(name="ts_y")
        result = resolve_specialist_roster(
            "drop_server_spec",
            mcp_toolsets={"server_x": ts_x, "server_y": ts_y},
            function_tools=[],
            mcp_server_ids=["server_x", "server_y"],
            tool_ids=["server_x.tool_one"],
            registry=registry,
        )
        # server_y has no entries in tool_ids and is dropped entirely (the
        # resolver's belt-and-suspenders drop — hierarchy.py wouldn't have
        # included it in the first place).
        assert result == [ts_x]

    def test_tool_ids_filters_function_tools_by_name(self) -> None:
        registry = _registry_for()
        ft_a = MagicMock(name="ft_a")
        ft_a.name = "create_visualization"
        ft_b = MagicMock(name="ft_b")
        ft_b.name = "other_tool"
        result = resolve_specialist_roster(
            "fn_filter_spec",
            mcp_toolsets={},
            function_tools=[ft_a, ft_b],
            mcp_server_ids=[],
            tool_ids=["function.create_visualization"],
            registry=registry,
        )
        assert result == [ft_a]

    def test_tool_ids_combined_mcp_and_function_filtering(self) -> None:
        registry = _registry_for(("server_x", 1))
        ts_x = MagicMock(name="ts_x")
        ft = MagicMock(name="ft")
        ft.name = "create_visualization"
        result = resolve_specialist_roster(
            "combined_spec",
            mcp_toolsets={"server_x": ts_x},
            function_tools=[ft],
            mcp_server_ids=["server_x"],
            tool_ids=[
                "server_x.tool_one",
                "function.create_visualization",
            ],
            registry=registry,
        )
        assert ts_x in result and ft in result

    def test_tool_ids_skips_validation_block(self) -> None:
        """When ``tool_ids`` is set, the legacy ``mcp_server_ids must match
        toolsets.keys()`` validation is bypassed since the resolver is now
        filtering toolsets rather than requiring an exact match. This lets
        callers pass an authoritative server-id list while letting the
        allowlist do the narrowing."""
        registry = _registry_for(("server_x", 1))
        ts_x = MagicMock(name="ts_x")
        # Note: mcp_server_ids includes an extra entry that's not in toolsets
        # — would normally raise ValueError. With tool_ids set, it shouldn't.
        result = resolve_specialist_roster(
            "skip_validation_spec",
            mcp_toolsets={"server_x": ts_x},
            function_tools=[],
            mcp_server_ids=["server_x", "server_y"],
            tool_ids=["server_x.tool_one"],
            registry=registry,
        )
        assert result == [ts_x]

    def test_defensive_cap_check_when_tool_ids_over_limit(self) -> None:
        """A non-router caller (migration / seeder / test) that supplies
        more tool_ids than ``MAX_TOOLS_PER_SPECIALIST`` must be rejected at
        the construction boundary — the API gate is not the only line of
        defense. (Review item #2.)"""
        registry = _registry_for(("server_x", 1))
        too_many = [f"server_x.tool_{i:02d}" for i in range(31)]
        with pytest.raises(RosterCapExceededError, match="exceeds the 30-tool cap"):
            resolve_specialist_roster(
                "over_cap_via_tool_ids",
                mcp_toolsets={"server_x": MagicMock()},
                function_tools=[],
                mcp_server_ids=["server_x"],
                tool_ids=too_many,
                registry=registry,
            )


class TestPerServerAllowedToolsReservedPrefix:
    """AH-98: the ``agent.`` prefix is reserved like ``function.`` — it must not
    be grouped as an MCP server, or ``agent.google_search`` would be mistaken for
    a server literally named ``agent``."""

    def test_agent_prefix_not_treated_as_mcp_server(self) -> None:
        assert per_server_allowed_tools(["agent.google_search"]) == {}

    def test_function_prefix_still_reserved(self) -> None:
        assert per_server_allowed_tools(["function.create_visualization"]) == {}

    def test_mixed_prefixes_only_mcp_grouped(self) -> None:
        result = per_server_allowed_tools(
            ["srv.tool_a", "agent.google_search", "function.viz"]
        )
        assert result == {"srv": ["tool_a"]}


class TestResolveSpecialistRosterWithAgentTools:
    """AH-98: agent-as-a-tool (``agent.{name}``) resolution + opt-in attach."""

    def test_opt_in_via_tool_ids_attaches_agent_tool(self) -> None:
        registry = _FakeRegistry([])
        gs = _agent_tool("google_search")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=[gs],
            tool_ids=["agent.google_search"],
            registry=registry,
        )
        assert result == [gs]

    def test_tool_ids_none_excludes_non_default_global_agent_tool(self) -> None:
        # google_search ships opt-in (default_global=False) -> not attached when
        # the agent hasn't customised tool_ids. This is the core opt-in guarantee.
        registry = _FakeRegistry(
            [], agent_tool_defs=[_fake_agent_tool_def("google_search")]
        )
        gs = _agent_tool("google_search")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=[gs],
            tool_ids=None,
            registry=registry,
        )
        assert result == []

    def test_tool_ids_none_includes_default_global_agent_tool(self) -> None:
        registry = _FakeRegistry(
            [], agent_tool_defs=[_fake_agent_tool_def("auto_tool", default_global=True)]
        )
        at = _agent_tool("auto_tool")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=[at],
            tool_ids=None,
            registry=registry,
        )
        assert result == [at]

    def test_tool_ids_empty_excludes_agent_tool(self) -> None:
        registry = _FakeRegistry([])
        gs = _agent_tool("google_search")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=[gs],
            tool_ids=[],
            registry=registry,
        )
        assert result == []

    def test_agent_tool_not_listed_is_excluded(self) -> None:
        registry = _FakeRegistry([])
        gs = _agent_tool("google_search")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={},
            function_tools=[],
            mcp_server_ids=[],
            agent_tools=[gs],
            tool_ids=["function.create_visualization"],
            registry=registry,
        )
        assert result == []

    def test_ordering_mcp_then_function_then_agent(self) -> None:
        registry = _registry_for(("srv", 1))
        ts = MagicMock(name="ts")
        ft = MagicMock(name="ft")
        ft.name = "create_visualization"
        at = _agent_tool("google_search")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={"srv": ts},
            function_tools=[ft],
            mcp_server_ids=["srv"],
            agent_tools=[at],
            tool_ids=[
                "srv.tool_one",
                "function.create_visualization",
                "agent.google_search",
            ],
            registry=registry,
        )
        assert result == [ts, ft, at]

    def test_no_agent_tools_arg_is_backward_compatible(self) -> None:
        # Existing callers that don't pass agent_tools keep working unchanged.
        registry = _registry_for(("srv", 1))
        ts = MagicMock(name="ts")
        result = resolve_specialist_roster(
            "spec",
            mcp_toolsets={"srv": ts},
            function_tools=[],
            mcp_server_ids=["srv"],
            tool_ids=None,
            registry=registry,
        )
        assert result == [ts]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
