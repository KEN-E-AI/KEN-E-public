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


class _FakeRegistry:
    """In-memory stand-in for ToolRegistry that returns a fixed tool list."""

    def __init__(self, tools: list[MagicMock]) -> None:
        self._tools = tools

    def list_tools(self) -> list[MagicMock]:
        return list(self._tools)


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
        registry = _registry_for(("google_analytics_mcp", 8))
        function_tools = [MagicMock() for _ in range(22)]

        result = count_specialist_tool_roster(
            "analytics_specialist",
            mcp_server_ids=["google_analytics_mcp"],
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
