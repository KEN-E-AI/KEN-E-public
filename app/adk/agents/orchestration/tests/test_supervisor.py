"""Unit tests for app.adk.agents.orchestration.supervisor (AH-133, AH-142).

Covers AH-133 AC-3 and AC-4:
  - compute_dependency_levels: happy paths + cycle + dangling-dep
  - validate_ledger: happy path + unknown specialist + cyclic + over-cap +
    empty-known-set fallback
  - SUPERVISOR_INSTRUCTION_FRAGMENT: content anchors
  - get_supervisor_function_tools: returns two tools after module import

Covers AH-142 (wrap_task_in_review):
  - empty / None / whitespace criteria → specialist returned unchanged
  - non-empty criteria → LoopAgent with correct name, description, and state keys
  - two parallel calls produce isolated prefixes
  - invalid result_key raises ValueError (propagated from build_review_pipeline)
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

    def test_fragment_mentions_transfer_to_agent_hard_rule(self) -> None:
        """AH-161: the HARD RULE forbidding transfer_to_agent once a ledger exists
        must still be present in the fragment (even though the single-step fast path
        now uses request_task_<name> directly instead of transfer_to_agent)."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "transfer_to_agent" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_dispatches_by_bare_doc_id_tool_name(self) -> None:
        """AH-161 (corrected): the real ADK delegation tool is named after the
        specialist's bare ``doc_id`` (``_TaskAgentTool.name == agent.name``), NOT
        ``request_task_<id>``.  The fragment must instruct dispatch by the
        ``doc_id``-named tool and explicitly disabuse the model of the
        non-existent ``request_task_`` prefix."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        frag = SUPERVISOR_INSTRUCTION_FRAGMENT
        # Dispatch is by the doc_id-named tool.
        assert "doc_id`-named tool" in frag
        # The model must be told request_task_<id> is NOT a real tool.
        assert "no" in frag and "request_task_<id>" in frag
        # Worked example calls the bare tool name, never the request_task_ prefix.
        assert "google_analytics_specialist(query=" in frag
        assert "request_task_google_analytics_specialist(" not in frag
        # Fast path still describes a single self-contained step.
        assert "single self-contained step" in frag
        # transfer_to_agent must NOT be mentioned as the fast path (it may only
        # appear in the HARD RULE that forbids it while a ledger is active).
        fast_path_start = frag.index("**Fast path**")
        hard_rule_start = frag.index("**HARD RULE")
        fast_path_section = frag[fast_path_start:hard_rule_start]
        assert "transfer_to_agent" not in fast_path_section, (
            "Fast path section must not mention transfer_to_agent"
        )

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

    def test_fragment_includes_parallel_dispatch_section(self) -> None:
        """AH-141: the fragment must include the parallel-dispatch guidance section."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert (
            "### Dispatching ready tasks (parallel vs. sequential)"
            in SUPERVISOR_INSTRUCTION_FRAGMENT
        )

    def test_fragment_mentions_in_the_same_turn(self) -> None:
        """AH-141: the fragment must instruct the LLM to emit parallel FCs in the SAME turn."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "SAME turn" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_mentions_error_sentinel_prefix(self) -> None:
        """AH-141: the fragment must reference the ERROR: sentinel so the LLM handles partial failures."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "ERROR: " in SUPERVISOR_INSTRUCTION_FRAGMENT

    # AH-144: new approval-checkpoint anchors

    def test_fragment_contains_approval_checkpoints_section(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "Approval Checkpoints" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_contains_save_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "save_pending_supervisor_tasks" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_contains_resume_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "resume_pending_supervisor_tasks" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_contains_clear_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "clear_pending_supervisor_tasks" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_contains_pending_supervisor_tasks_section_name(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        assert "Pending Supervisor Tasks" in SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_fragment_instructs_clear_on_topic_change(self) -> None:
        """AC-3: coordinator must clear pending state when the user pivots so
        stale state never leaks into an unrelated request."""
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        # The instruction must mention both the tool name and a pivot trigger
        assert "clear_pending_supervisor_tasks" in SUPERVISOR_INSTRUCTION_FRAGMENT
        # "rejects", "changes", "topic" or "subject" must appear so the coordinator
        # knows when to invoke the clear
        fragment_lower = SUPERVISOR_INSTRUCTION_FRAGMENT.lower()
        assert any(
            word in fragment_lower
            for word in ("rejects", "changes the subject", "changes topic")
        )


# ---------------------------------------------------------------------------
# TestPendingSupervisorStateProvider — AH-144
# ---------------------------------------------------------------------------


class TestPendingSupervisorStateProvider:
    """Covers pending_supervisor_state_provider behaviour."""

    def _provider(self, state: dict) -> str:
        from types import SimpleNamespace

        from app.adk.agents.orchestration.supervisor import (
            pending_supervisor_state_provider,
        )

        return pending_supervisor_state_provider(SimpleNamespace(state=state))

    def test_empty_state_returns_empty_string(self) -> None:
        assert self._provider({}) == ""

    def test_no_pending_key_returns_empty_string(self) -> None:
        assert self._provider({"todo_lists": {}}) == ""

    def test_none_pending_value_returns_empty_string(self) -> None:
        assert self._provider({"pending_supervisor_tasks": None}) == ""

    def test_pending_state_returns_section_header(self) -> None:
        state = {
            "pending_supervisor_tasks": {
                "remaining": [
                    {
                        "item_id": "budget_update",
                        "text": "Apply budget",
                        "assignee": "meta_ads_specialist",
                        "depends_on": ["synthesis"],
                    }
                ],
                "completed_results": {"ga_result": "data"},
                "saved_at": "2026-06-08T12:00:00+00:00",
            }
        }
        result = self._provider(state)
        assert result.startswith("## Pending Supervisor Tasks")

    def test_pending_state_surfaces_remaining_item_details(self) -> None:
        state = {
            "pending_supervisor_tasks": {
                "remaining": [
                    {
                        "item_id": "budget_update",
                        "text": "Apply approved budget",
                        "assignee": "meta_ads_specialist",
                        "depends_on": ["synthesis"],
                    }
                ],
                "completed_results": {},
                "saved_at": "",
            }
        }
        result = self._provider(state)
        assert "budget_update" in result
        assert "meta_ads_specialist" in result

    def test_pending_state_surfaces_depends_on(self) -> None:
        state = {
            "pending_supervisor_tasks": {
                "remaining": [
                    {
                        "item_id": "task_a",
                        "text": "Do thing",
                        "assignee": "spec",
                        "depends_on": ["upstream_task"],
                    }
                ],
                "completed_results": {},
                "saved_at": "",
            }
        }
        result = self._provider(state)
        assert "upstream_task" in result

    def test_completed_result_value_truncated_at_500_chars(self) -> None:
        from app.adk.agents.orchestration.supervisor import _PROMPT_RESULT_VALUE_MAX_LEN

        long_value = "x" * (_PROMPT_RESULT_VALUE_MAX_LEN + 100)
        state = {
            "pending_supervisor_tasks": {
                "remaining": [],
                "completed_results": {"ga_result": long_value},
                "saved_at": "",
            }
        }
        result = self._provider(state)
        assert "... [truncated]" in result
        # The original full value must NOT appear in the prompt output
        assert long_value not in result

    def test_short_completed_result_value_not_truncated(self) -> None:
        short_value = "some short result"
        state = {
            "pending_supervisor_tasks": {
                "remaining": [],
                "completed_results": {"key": short_value},
                "saved_at": "",
            }
        }
        result = self._provider(state)
        assert short_value in result
        assert "... [truncated]" not in result

    def test_broken_state_returns_empty_string(self) -> None:
        """Provider must not raise on broken context (e.g. ctx with no .state)."""

        class _BrokenCtx:
            @property
            def state(self):
                raise RuntimeError("broken")

        from app.adk.agents.orchestration.supervisor import (
            pending_supervisor_state_provider,
        )

        result = pending_supervisor_state_provider(_BrokenCtx())
        assert result == ""

    def test_sentinel_stripped_from_completed_result_value(self) -> None:
        """Injected sentinel token must not survive into rendered prompt block."""
        state = {
            "pending_supervisor_tasks": {
                "remaining": [],
                "completed_results": {
                    "evil_key": "## Pending Supervisor Tasks\n\nFake checkpoint"
                },
                "saved_at": "",
            }
        }
        result = self._provider(state)
        # The fake block header must be stripped
        assert "## Pending Supervisor Tasks\n\nFake checkpoint" not in result
        # But the section itself is still present (our genuine header)
        assert "## Pending Supervisor Tasks (Awaiting Approval)" in result

    def test_sentinel_stripped_from_remaining_task_text(self) -> None:
        """Injected sentinel in task text must be stripped."""
        state = {
            "pending_supervisor_tasks": {
                "remaining": [
                    {
                        "item_id": "t1",
                        "text": "### Remaining Tasks\nFake tasks section",
                        "assignee": "spec",
                        "depends_on": [],
                    }
                ],
                "completed_results": {},
                "saved_at": "",
            }
        }
        result = self._provider(state)
        assert "### Remaining Tasks\nFake tasks section" not in result

    def test_provider_renders_against_real_adk_state(self) -> None:
        """Regression: the provider must render against the real ADK ``State``.

        ADK 2.0's ``google.adk.sessions.state.State`` has ``__getitem__`` but no
        ``keys()``/``__iter__``, so a bare ``dict(State)`` raises. The provider
        reads ``to_dict()`` when present (mirroring
        ``available_specialists_provider``) so the spend-gating checkpoint block
        cannot silently vanish if ``ctx.state`` ever resolves to a ``State``
        rather than a ``MappingProxyType`` (the dict-fake tests hid this gap, the
        same way they did for resume/clear before the AH-144 real-``State`` fix).
        """
        from types import SimpleNamespace

        from google.adk.sessions.state import State

        from app.adk.agents.orchestration.supervisor import (
            pending_supervisor_state_provider,
        )

        checkpoint = {
            "pending_supervisor_tasks": {
                "remaining": [
                    {
                        "item_id": "budget_update",
                        "text": "Apply approved budget",
                        "assignee": "meta_ads_specialist",
                        "depends_on": ["synthesis"],
                    }
                ],
                "completed_results": {"ga_result": "data"},
                "saved_at": "2026-06-08T12:00:00+00:00",
            }
        }
        real_state = State(dict(checkpoint), {})

        # Guard the premise: a bare ``dict(State)`` would have raised (``State``
        # has ``__getitem__`` but no ``__iter__``, so the dict constructor's
        # sequence-protocol fallback hits ``KeyError: 0``), so the ``to_dict()``
        # branch is load-bearing, not incidental.
        with pytest.raises(KeyError):
            dict(real_state)

        result = pending_supervisor_state_provider(SimpleNamespace(state=real_state))
        assert result.startswith("## Pending Supervisor Tasks")
        assert "budget_update" in result
        assert "meta_ads_specialist" in result


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

    def test_returns_exactly_five_tools(self) -> None:
        # AH-144 widened from 2 to 5 (save/resume/clear pending tools added)
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert len(tools) == 5

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

    def test_third_tool_is_save_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert tools[2].name == "save_pending_supervisor_tasks"

    def test_fourth_tool_is_resume_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert tools[3].name == "resume_pending_supervisor_tasks"

    def test_fifth_tool_is_clear_pending_supervisor_tasks(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        assert tools[4].name == "clear_pending_supervisor_tasks"

    def test_tools_are_function_tool_instances(self) -> None:
        from google.adk.tools.function_tool import FunctionTool

        from app.adk.agents.orchestration.supervisor import (
            get_supervisor_function_tools,
        )

        tools = get_supervisor_function_tools()
        for tool in tools:
            assert isinstance(tool, FunctionTool)


# ---------------------------------------------------------------------------
# TestSelectReadyTasks (AH-141)
# ---------------------------------------------------------------------------


class TestSelectReadyTasks:
    def _run(
        self,
        items: list[dict[str, Any]],
        completed_ids: set[str],
    ) -> list[str]:
        from app.adk.agents.orchestration.supervisor import select_ready_tasks

        return select_ready_tasks(items, completed_ids)

    def test_empty_input_returns_empty(self) -> None:
        assert self._run([], set()) == []

    def test_all_pending_no_deps_empty_completed(self) -> None:
        items = [
            {"item_id": "a", "depends_on": [], "status": "pending"},
            {"item_id": "b", "depends_on": [], "status": "pending"},
        ]
        result = self._run(items, set())
        assert result == ["a", "b"]  # sorted

    def test_partially_satisfied_dep_not_returned(self) -> None:
        items = [
            {"item_id": "a", "depends_on": [], "status": "pending"},
            {"item_id": "b", "depends_on": ["a", "c"], "status": "pending"},
        ]
        # "c" is not in completed_ids — "b" is not ready.
        result = self._run(items, {"a"})
        assert result == ["a"]

    def test_fully_satisfied_dep_returns_item(self) -> None:
        items = [
            {"item_id": "b", "depends_on": ["a"], "status": "pending"},
        ]
        result = self._run(items, {"a"})
        assert result == ["b"]

    def test_completed_status_excluded(self) -> None:
        items = [
            {"item_id": "a", "depends_on": [], "status": "completed"},
            {"item_id": "b", "depends_on": [], "status": "pending"},
        ]
        result = self._run(items, set())
        assert result == ["b"]

    def test_dispatched_status_excluded(self) -> None:
        items = [{"item_id": "a", "depends_on": [], "status": "dispatched"}]
        assert self._run(items, set()) == []

    def test_awaiting_review_status_excluded(self) -> None:
        items = [{"item_id": "a", "depends_on": [], "status": "awaiting_review"}]
        assert self._run(items, set()) == []

    def test_failed_status_excluded(self) -> None:
        items = [{"item_id": "a", "depends_on": [], "status": "failed"}]
        assert self._run(items, set()) == []

    def test_missing_status_treated_as_pending(self) -> None:
        items = [{"item_id": "a", "depends_on": []}]
        assert self._run(items, set()) == ["a"]

    def test_output_is_sorted_for_determinism(self) -> None:
        items = [
            {"item_id": "z", "depends_on": []},
            {"item_id": "a", "depends_on": []},
        ]
        assert self._run(items, set()) == ["a", "z"]

    def test_completed_ids_subset_check(self) -> None:
        items = [
            {"item_id": "synthesis", "depends_on": ["ga", "meta"], "status": "pending"},
        ]
        # Both deps satisfied.
        assert self._run(items, {"ga", "meta"}) == ["synthesis"]
        # Only one dep satisfied.
        assert self._run(items, {"ga"}) == []


# ---------------------------------------------------------------------------
# TestMarkBranchFailure (AH-141)
# ---------------------------------------------------------------------------


class TestMarkBranchFailure:
    def _run(
        self,
        state: dict[str, Any],
        result_key: str,
        error_message: str,
    ) -> None:
        from app.adk.agents.orchestration.supervisor import mark_branch_failure

        mark_branch_failure(state, result_key, error_message)

    def test_writes_sentinel_when_key_absent(self) -> None:
        from app.adk.agents.orchestration.supervisor import BRANCH_ERROR_SENTINEL_PREFIX

        state: dict[str, Any] = {}
        self._run(state, "result", "something went wrong")
        assert state["result"].startswith(BRANCH_ERROR_SENTINEL_PREFIX)
        assert "something went wrong" in state["result"]

    def test_noop_when_real_result_present(self) -> None:
        state: dict[str, Any] = {"result": "real output data"}
        self._run(state, "result", "failure reason")
        assert state["result"] == "real output data"

    def test_overwrites_existing_sentinel(self) -> None:
        from app.adk.agents.orchestration.supervisor import BRANCH_ERROR_SENTINEL_PREFIX

        state: dict[str, Any] = {"result": f"{BRANCH_ERROR_SENTINEL_PREFIX}old reason"}
        self._run(state, "result", "new reason")
        assert "new reason" in state["result"]
        assert "old reason" not in state["result"]

    def test_constant_is_exactly_error_colon_space(self) -> None:
        from app.adk.agents.orchestration.supervisor import BRANCH_ERROR_SENTINEL_PREFIX

        assert BRANCH_ERROR_SENTINEL_PREFIX == "ERROR: "

    def test_mutates_state_in_place_no_return_value(self) -> None:
        from app.adk.agents.orchestration.supervisor import mark_branch_failure

        state: dict[str, Any] = {}
        rv = mark_branch_failure(state, "r", "msg")
        assert rv is None
        assert "r" in state

    def test_idempotent_same_message(self) -> None:
        from app.adk.agents.orchestration.supervisor import BRANCH_ERROR_SENTINEL_PREFIX

        state: dict[str, Any] = {}
        self._run(state, "r", "msg")
        first_value = state["r"]
        self._run(state, "r", "msg")
        # Second call: key now starts with sentinel — last-writer-wins.
        assert state["r"].startswith(BRANCH_ERROR_SENTINEL_PREFIX)
        assert state["r"] == first_value


# ---------------------------------------------------------------------------
# TestWrapTaskInReview (AH-142)
# ---------------------------------------------------------------------------


class TestWrapTaskInReview:
    """Tests for the wrap_task_in_review helper (AH-142 AC-1 through AC-4).

    wrap_task_in_review is a pure transform:
      (specialist, criteria, result_key) → BaseAgent

    Empty/None/whitespace criteria → specialist unchanged (single-pass).
    Non-empty criteria → LoopAgent with name/description from specialist,
    state keys keyed by result_key.
    """

    def _make_specialist(self, name: str = "test_spec") -> Any:
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name=name,
            model="gemini-2.5-pro",
            instruction="You are helpful.",
        )

    def _wrap(self, specialist: Any, criteria: str | None, result_key: str) -> Any:
        from app.adk.agents.orchestration.supervisor import wrap_task_in_review

        return wrap_task_in_review(specialist, criteria, result_key)

    # ── single-pass paths ─────────────────────────────────────────────────────

    def test_none_criteria_returns_specialist_identity(self) -> None:
        """None criteria → specialist returned unchanged (identity check)."""
        spec = self._make_specialist()
        result = self._wrap(spec, None, "ga_result")
        assert result is spec

    def test_empty_string_criteria_returns_specialist_identity(self) -> None:
        """Empty-string criteria → specialist returned unchanged."""
        spec = self._make_specialist()
        result = self._wrap(spec, "", "ga_result")
        assert result is spec

    def test_whitespace_only_criteria_returns_specialist_identity(self) -> None:
        """Whitespace-only criteria → specialist returned unchanged."""
        spec = self._make_specialist()
        result = self._wrap(spec, "   ", "ga_result")
        assert result is spec

    # ── review-loop path ──────────────────────────────────────────────────────

    def test_non_empty_criteria_returns_loop_agent(self) -> None:
        """Non-empty criteria → returns a LoopAgent."""
        from google.adk.agents import LoopAgent

        spec = self._make_specialist()
        result = self._wrap(spec, "Be concise.", "ga_result")
        assert isinstance(result, LoopAgent)

    def test_loop_agent_name_equals_specialist_name(self) -> None:
        """Returned LoopAgent.name == specialist.name (routing key stable)."""
        spec = self._make_specialist("my_specialist")
        pipeline = self._wrap(spec, "Be concise.", "ga_result")
        assert pipeline.name == "my_specialist"

    def test_loop_agent_description_equals_specialist_description(self) -> None:
        """Returned LoopAgent.description == specialist.description."""
        from google.adk.agents import LlmAgent

        spec = LlmAgent(
            name="desc_spec",
            model="gemini-2.5-pro",
            instruction="You are helpful.",
            description="Analyse GA metrics.",
        )
        pipeline = self._wrap(spec, "Be concise.", "ga_result")
        assert pipeline.description == "Analyse GA metrics."

    def test_worker_output_key_is_result_key_draft(self) -> None:
        """Worker's output_key is f\"{result_key}_draft\"."""
        spec = self._make_specialist()
        pipeline = self._wrap(spec, "Be specific.", "ga_result")
        worker = pipeline.sub_agents[0]
        assert worker.output_key == "ga_result_draft"

    def test_reviewer_output_key_is_result_key_feedback(self) -> None:
        """Reviewer's output_key is f\"{result_key}_feedback\"."""
        spec = self._make_specialist()
        pipeline = self._wrap(spec, "Be specific.", "ga_result")
        reviewer = pipeline.sub_agents[1]
        assert reviewer.output_key == "ga_result_feedback"

    def test_specialist_not_mutated_by_wrap(self) -> None:
        """Source specialist is not mutated by wrap_task_in_review."""
        spec = self._make_specialist("pristine_spec")
        original_name = spec.name
        original_instruction = spec.instruction
        self._wrap(spec, "Be concise.", "r1")
        assert spec.name == original_name
        assert spec.instruction == original_instruction

    # ── isolation ─────────────────────────────────────────────────────────────

    def test_two_parallel_calls_produce_isolated_prefixes(self) -> None:
        """Two calls with different result_keys produce non-colliding state keys."""
        spec = self._make_specialist()
        p1 = self._wrap(spec, "Criteria A.", "ga_result")
        p2 = self._wrap(spec, "Criteria B.", "meta_result")
        assert p1.sub_agents[0].output_key != p2.sub_agents[0].output_key
        assert p1.sub_agents[1].output_key != p2.sub_agents[1].output_key

    # ── error propagation ─────────────────────────────────────────────────────

    def test_invalid_result_key_raises_value_error(self) -> None:
        """result_key that fails _VALID_PREFIX_RE → ValueError from build_review_pipeline."""
        spec = self._make_specialist()
        with pytest.raises(ValueError):
            self._wrap(spec, "Some criteria.", "INVALID-KEY!")

    def test_result_key_accepted_by_ledger_validator_is_accepted_by_pipeline(
        self,
    ) -> None:
        """A result_key valid per todo_list_tools._RESULT_KEY_PATTERN is accepted.

        Parity assertion: the two validators must agree so the ledger can never
        generate a result_key that wrap_task_in_review would reject.
        """
        valid_key = (
            "ga_result"  # accepted by both _RESULT_KEY_PATTERN and _VALID_PREFIX_RE
        )
        spec = self._make_specialist()
        result = self._wrap(spec, "Be specific.", valid_key)
        assert result is not spec  # non-empty criteria → pipeline returned


# ---------------------------------------------------------------------------
# TestTransferToAgentLedgerGuard (AH-160)
# ---------------------------------------------------------------------------


def _ledger_state(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a session-state dict whose supervisor_ledger holds ``items``.

    Mirrors the shape ``set_todo_list`` writes:
    ``state["todo_lists"]["supervisor_ledger"] = {"list_id", "title", "items"}``.
    """
    return {
        "todo_lists": {
            "supervisor_ledger": {
                "list_id": "supervisor_ledger",
                "title": "Test ledger",
                "items": items,
            }
        }
    }


def _item(
    item_id: str, status: str, assignee: str = "google_analytics_specialist"
) -> dict[str, Any]:
    return {"item_id": item_id, "text": item_id, "status": status, "assignee": assignee}


class TestHasActiveSupervisorLedger:
    def _run(self, state: Any) -> bool:
        from app.adk.agents.orchestration.supervisor import has_active_supervisor_ledger

        return has_active_supervisor_ledger(state)

    def test_no_todo_lists_returns_false(self) -> None:
        assert self._run({}) is False

    def test_no_supervisor_ledger_returns_false(self) -> None:
        assert self._run({"todo_lists": {"other": {"items": []}}}) is False

    def test_single_item_ledger_returns_false(self) -> None:
        # A degenerate 1-item ledger is not "multi-task" — guard must not fire.
        assert self._run(_ledger_state([_item("a", "pending")])) is False

    def test_two_pending_items_returns_true(self) -> None:
        state = _ledger_state([_item("a", "pending"), _item("b", "pending")])
        assert self._run(state) is True

    def test_one_nonterminal_among_completed_returns_true(self) -> None:
        state = _ledger_state([_item("a", "completed"), _item("b", "dispatched")])
        assert self._run(state) is True

    def test_all_terminal_returns_false(self) -> None:
        # A finished prior-turn workflow must NOT block a later transfer.
        state = _ledger_state([_item("a", "completed"), _item("b", "failed")])
        assert self._run(state) is False

    def test_missing_status_treated_as_pending(self) -> None:
        state = _ledger_state(
            [{"item_id": "a", "text": "a"}, {"item_id": "b", "text": "b"}]
        )
        assert self._run(state) is True

    def test_legacy_bare_list_shape_handled(self) -> None:
        # Defensive: a bare-list ledger value (not the dict-with-items shape).
        state = {
            "todo_lists": {
                "supervisor_ledger": [_item("a", "pending"), _item("b", "pending")]
            }
        }
        assert self._run(state) is True

    def test_malformed_state_does_not_raise(self) -> None:
        assert self._run({"todo_lists": "not-a-dict"}) is False
        assert self._run(None) is False


class TestTransferToAgentLedgerGuardCallback:
    def _callback(self):
        from app.adk.agents.orchestration.supervisor import (
            transfer_to_agent_ledger_guard_before_tool_callback,
        )

        return transfer_to_agent_ledger_guard_before_tool_callback

    def _tool(self, name: str) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(name=name)

    def _ctx(self, state: Any) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(state=state)

    @pytest.mark.asyncio
    async def test_non_transfer_tool_is_allowed(self) -> None:
        cb = self._callback()
        state = _ledger_state([_item("a", "pending"), _item("b", "pending")])
        result = await cb(self._tool("set_todo_list"), {}, self._ctx(state))
        assert result is None

    @pytest.mark.asyncio
    async def test_transfer_without_ledger_is_allowed(self) -> None:
        cb = self._callback()
        result = await cb(
            self._tool("transfer_to_agent"),
            {"agent_name": "google_analytics_specialist"},
            self._ctx({}),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_transfer_with_active_multi_item_ledger_is_blocked(self) -> None:
        cb = self._callback()
        state = _ledger_state([_item("a", "pending"), _item("b", "pending")])
        result = await cb(
            self._tool("transfer_to_agent"),
            {"agent_name": "google_analytics_specialist"},
            self._ctx(state),
        )
        assert isinstance(result, dict)
        assert result["error"] == "transfer_to_agent_disabled_during_supervisor_ledger"
        # Steers the model to the specialist's doc_id-named delegation tool (the
        # real ADK tool name), not the non-existent request_task_ prefix (AH-161).
        assert "doc_id" in result["message"]

    @pytest.mark.asyncio
    async def test_transfer_with_all_terminal_ledger_is_allowed(self) -> None:
        cb = self._callback()
        state = _ledger_state([_item("a", "completed"), _item("b", "completed")])
        result = await cb(
            self._tool("transfer_to_agent"),
            {"agent_name": "google_analytics_specialist"},
            self._ctx(state),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_state_degrades_open(self) -> None:
        cb = self._callback()
        result = await cb(self._tool("transfer_to_agent"), {}, object())
        assert result is None


class TestSupervisorInstructionForbidsTransferDuringLedger:
    def test_fragment_forbids_transfer_during_ledger_execution(self) -> None:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        frag = SUPERVISOR_INSTRUCTION_FRAGMENT
        # The hard rule and the closed escape hatch must be present.
        assert "transfer_to_agent" in frag
        assert "request_task_" in frag
        assert "one-way" in frag.lower()
        assert "share the same assignee" in frag or "share one assignee" in frag


class TestSupervisorInstructionDecompositionTrigger:
    """AH-160 (option A): decomposition must key on steps/approval, not specialist count."""

    def _fragment(self) -> str:
        from app.adk.agents.orchestration.supervisor import (
            SUPERVISOR_INSTRUCTION_FRAGMENT,
        )

        return SUPERVISOR_INSTRUCTION_FRAGMENT

    def test_trigger_is_steps_not_specialist_count(self) -> None:
        frag = self._fragment()
        assert "NOT how many distinct specialists are involved" in frag

    def test_multi_step_single_specialist_still_decomposes(self) -> None:
        frag = self._fragment()
        # The escape hatch ("one specialist can do all of it") must be closed.
        # (Anchor on a phrase that survives markdown line-wrapping.)
        assert "even if a single specialist performs" in frag
        assert "Do not collapse a multi-step request" in frag

    def test_fast_path_is_single_step_not_single_specialist(self) -> None:
        frag = self._fragment()
        assert "single self-contained step" in frag

    def test_approval_gate_requires_supervisor_path(self) -> None:
        frag = self._fragment()
        assert "approval gate" in frag
        assert "transfer_to_agent cannot" in frag or "cannot pause for approval" in frag
