"""Unit tests for app.adk.agents.orchestration.supervisor (AH-133).

Covers AH-133 AC-3 and AC-4:
  - compute_dependency_levels: happy paths + cycle + dangling-dep
  - validate_ledger: happy path + unknown specialist + cyclic + over-cap +
    empty-known-set fallback
  - SUPERVISOR_INSTRUCTION_FRAGMENT: content anchors
  - get_supervisor_function_tools: returns two tools after module import
"""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# TestComputeDependencyLevels
# ---------------------------------------------------------------------------


class TestComputeDependencyLevels:
    def _run(self, items: list[dict[str, Any]]) -> Any:
        from app.adk.agents.orchestration.supervisor import compute_dependency_levels

        return compute_dependency_levels(items)

    def test_empty_input_returns_empty_list(self) -> None:
        assert self._run([]) == []

    def test_single_task_no_deps(self) -> None:
        result = self._run([{"item_id": "a", "depends_on": []}])
        assert result == [["a"]]

    def test_linear_chain(self) -> None:
        # a → b → c  (c depends on b; b depends on a)
        items = [
            {"item_id": "a", "depends_on": []},
            {"item_id": "b", "depends_on": ["a"]},
            {"item_id": "c", "depends_on": ["b"]},
        ]
        result = self._run(items)
        assert result == [["a"], ["b"], ["c"]]

    def test_parallel_siblings_at_same_level(self) -> None:
        # a and b both at level 0; c depends on both
        items = [
            {"item_id": "a", "depends_on": []},
            {"item_id": "b", "depends_on": []},
            {"item_id": "c", "depends_on": ["a", "b"]},
        ]
        result = self._run(items)
        assert result == [["a", "b"], ["c"]]

    def test_mixed_dag(self) -> None:
        # Level 0: a, b
        # Level 1: c (depends on a), d (depends on b)
        # Level 2: e (depends on c, d)
        items = [
            {"item_id": "a", "depends_on": []},
            {"item_id": "b", "depends_on": []},
            {"item_id": "c", "depends_on": ["a"]},
            {"item_id": "d", "depends_on": ["b"]},
            {"item_id": "e", "depends_on": ["c", "d"]},
        ]
        result = self._run(items)
        assert result == [["a", "b"], ["c", "d"], ["e"]]

    def test_missing_depends_on_treated_as_empty(self) -> None:
        items = [{"item_id": "a"}]
        result = self._run(items)
        assert result == [["a"]]

    def test_none_depends_on_treated_as_empty(self) -> None:
        items = [{"item_id": "a", "depends_on": None}]
        result = self._run(items)
        assert result == [["a"]]

    def test_two_node_cycle_returns_error(self) -> None:
        items = [
            {"item_id": "a", "depends_on": ["b"]},
            {"item_id": "b", "depends_on": ["a"]},
        ]
        result = self._run(items)
        assert isinstance(result, str)
        assert result.startswith("ERROR:")
        assert "cyclic" in result.lower()

    def test_three_node_cycle_returns_error(self) -> None:
        items = [
            {"item_id": "a", "depends_on": ["c"]},
            {"item_id": "b", "depends_on": ["a"]},
            {"item_id": "c", "depends_on": ["b"]},
        ]
        result = self._run(items)
        assert isinstance(result, str)
        assert result.startswith("ERROR:")
        assert "cyclic" in result.lower()

    def test_dangling_dependency_returns_error(self) -> None:
        items = [
            {"item_id": "a", "depends_on": ["nonexistent"]},
        ]
        result = self._run(items)
        assert isinstance(result, str)
        assert result.startswith("ERROR:")
        assert "nonexistent" in result
        assert "unknown item_id" in result

    def test_output_is_sorted_for_determinism(self) -> None:
        # Both z and a are at level 0 — must come out sorted.
        items = [
            {"item_id": "z", "depends_on": []},
            {"item_id": "a", "depends_on": []},
        ]
        result = self._run(items)
        assert result == [["a", "z"]]


# ---------------------------------------------------------------------------
# TestValidateLedger
# ---------------------------------------------------------------------------


class TestValidateLedger:
    def _items_4task(self) -> list[dict[str, Any]]:
        """AC-2 budget-optimisation example: 4-task ledger matching the PRD."""
        return [
            {
                "item_id": "ga_engagement",
                "text": "Pull GA engagement data",
                "assignee": "google_analytics_specialist",
                "query": "weekly bounce rate",
                "criteria": "≥4 weeks of data",
                "depends_on": [],
                "result_key": "ga_result",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
            {
                "item_id": "meta_spend",
                "text": "Pull Meta Ads spend",
                "assignee": "meta_ads_specialist",
                "query": "last-4-week spend per campaign",
                "criteria": "spend data present",
                "depends_on": [],
                "result_key": "meta_result",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
            {
                "item_id": "synthesis",
                "text": "Identify best-performing campaigns",
                "assignee": "google_analytics_specialist",
                "query": "identify top 3 campaigns",
                "criteria": "recommendations actionable",
                "depends_on": ["ga_engagement", "meta_spend"],
                "result_key": "synthesis_result",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
            {
                "item_id": "budget_update",
                "text": "Apply approved budget increases",
                "assignee": "meta_ads_specialist",
                "query": "apply budget changes",
                "criteria": "requires_approval; budgets updated",
                "depends_on": ["synthesis"],
                "result_key": "budget_update_result",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
        ]

    def _run(
        self,
        items: list[dict[str, Any]],
        known: set[str],
        max_items: int = 12,
    ) -> str | None:
        from app.adk.agents.orchestration.supervisor import validate_ledger

        return validate_ledger(items, known, max_items)

    def test_happy_path_4task_budget_optimisation(self) -> None:
        known = {"google_analytics_specialist", "meta_ads_specialist"}
        result = self._run(self._items_4task(), known)
        assert result is None

    def test_unknown_specialist_returns_error(self) -> None:
        items = self._items_4task()
        known = {"google_analytics_specialist"}  # meta_ads_specialist missing
        result = self._run(items, known)
        assert result is not None
        assert result.startswith("ERROR:")
        assert "meta_ads_specialist" in result
        assert "unknown specialist" in result.lower()

    def test_cyclic_ledger_returns_error(self) -> None:
        items = [
            {
                "item_id": "a",
                "text": "A",
                "assignee": "ga",
                "query": "q",
                "criteria": "c",
                "depends_on": ["b"],
                "result_key": "ra",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
            {
                "item_id": "b",
                "text": "B",
                "assignee": "ga",
                "query": "q",
                "criteria": "c",
                "depends_on": ["a"],
                "result_key": "rb",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
        ]
        known = {"ga"}
        result = self._run(items, known)
        assert result is not None
        assert result.startswith("ERROR:")
        assert "cyclic" in result.lower()

    def test_over_cap_returns_error(self) -> None:
        items = [
            {
                "item_id": f"task_{i}",
                "text": f"Task {i}",
                "assignee": "ga",
                "query": "q",
                "criteria": "c",
                "depends_on": [],
                "result_key": f"r{i}",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            }
            for i in range(13)
        ]
        known = {"ga"}
        result = self._run(items, known)
        assert result is not None
        assert result.startswith("ERROR:")
        assert "soft cap" in result

    def test_cap_boundary_exactly_12_succeeds(self) -> None:
        items = [
            {
                "item_id": f"task_{i}",
                "text": f"Task {i}",
                "assignee": "ga",
                "query": "q",
                "criteria": "c",
                "depends_on": [],
                "result_key": f"r{i}",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            }
            for i in range(12)
        ]
        known = {"ga"}
        result = self._run(items, known)
        assert result is None

    def test_empty_known_set_skips_specialist_check(self) -> None:
        """When known_specialist_ids is empty (Firestore-degraded), skip the
        unknown-specialist check — do NOT block the coordinator."""
        items = [
            {
                "item_id": "a",
                "text": "A",
                "assignee": "totally_unknown_specialist",
                "query": "q",
                "criteria": "c",
                "depends_on": [],
                "result_key": "ra",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            }
        ]
        result = self._run(items, known=set())
        assert result is None

    def test_duplicate_item_id_returns_error(self) -> None:
        items = [
            {
                "item_id": "dup",
                "text": "First",
                "assignee": "ga",
                "query": "q",
                "criteria": "c",
                "depends_on": [],
                "result_key": "r1",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
            {
                "item_id": "dup",
                "text": "Second",
                "assignee": "ga",
                "query": "q2",
                "criteria": "c2",
                "depends_on": [],
                "result_key": "r2",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            },
        ]
        known = {"ga"}
        result = self._run(items, known)
        assert result is not None
        assert result.startswith("ERROR:")
        assert "duplicate item_id" in result

    def test_unknown_specialist_error_does_not_disclose_known_list(self) -> None:
        """The error message must NOT include the list of known specialist IDs."""
        items = self._items_4task()
        known = {"google_analytics_specialist"}
        result = self._run(items, known)
        assert result is not None
        # The known specialist list must not be disclosed as a repr-list.
        assert "[" not in result

    def test_cap_check_runs_before_specialist_check(self) -> None:
        """Cap error takes priority over unknown-specialist error."""
        items = [
            {
                "item_id": f"task_{i}",
                "text": f"Task {i}",
                "assignee": "unknown_spec",
                "query": "q",
                "criteria": "c",
                "depends_on": [],
                "result_key": f"r{i}",
                "status": "pending",
                "completed": False,
                "completed_at": None,
            }
            for i in range(13)
        ]
        known = {"known_spec"}
        result = self._run(items, known)
        assert result is not None
        assert "soft cap" in result  # cap error, not unknown-specialist error


# ---------------------------------------------------------------------------
# TestSupervisorInstructionFragment
# ---------------------------------------------------------------------------


class TestSupervisorInstructionFragment:
    def test_fragment_starts_with_expected_header(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert SUPERVISOR_INSTRUCTION_FRAGMENT.startswith("## Multi-Task Decomposition")

    def test_fragment_mentions_transfer_to_agent_for_single_specialist(self) -> None:
        """AC-2: single-specialist queries must fall through to transfer_to_agent."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "transfer_to_agent" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_mentions_requires_approval(self) -> None:
        """Spend-changing tasks must include the requires_approval marker."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "requires_approval" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_mentions_cap_of_12(self) -> None:
        """The 12-item soft cap must be referenced explicitly."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "12" in SUPERVISOR_INSTRUCTION_FRAGMENT


# ---------------------------------------------------------------------------
# TestGetSupervisorFunctionTools
# ---------------------------------------------------------------------------


class TestGetSupervisorFunctionTools:
    @pytest.fixture(autouse=True)
    def _ensure_todo_tools_registered(self) -> None:
        """Ensure the todo-list tools' registration side effect has fired.

        ``get_supervisor_function_tools`` resolves them from the process-global
        function-tool registry; importing the module registers them
        idempotently. A plain import (no ``reload``) is sufficient now that no
        suite clears the registry on teardown — ``test_todo_list_tools`` and the
        registry's own suite snapshot-restore it instead.
        """
        import app.adk.tools.todo_list_tools  # noqa: F401  # registration side effect

    def test_returns_exactly_two_tools(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert len(tools) == 2

    def test_first_tool_is_set_todo_list(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert tools[0].name == "set_todo_list"

    def test_second_tool_is_update_todo_list(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert tools[1].name == "update_todo_list"

    def test_tools_are_function_tool_instances(self) -> None:
        from google.adk.tools.function_tool import FunctionTool

        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        for tool in tools:
            assert isinstance(tool, FunctionTool)
