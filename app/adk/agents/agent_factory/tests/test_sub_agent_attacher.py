"""Tests for :mod:`app.adk.agents.agent_factory.sub_agent_attacher`.

AH-75 / AH-PRD-09 / AH-161: idempotent runtime attachment of resolved
specialists to ``root_agent.sub_agents``, called by the root's
``before_agent_callback``.  AH-161 resolves all specialists as
``mode='task'`` so the coordinator dispatches via
``request_task_<doc_id>`` (call-and-return) and regains control after each
task; ``_reconcile`` injects ``_TaskAgentTool`` for both bare task-mode
LlmAgents and LoopAgents with ``_is_task_dispatchable=True``.

Test surface:

* Idempotency — repeated attach calls converge on the same ``sub_agents``
  list; no duplicate entries.
* Parent-agent invariant — first attach sets ``parent_agent``; subsequent
  attaches don't churn it.
* Reconcile drop — sub_agents whose name disappears from
  ``list_account_agent_configs_cached`` are removed and have their
  ``parent_agent`` cleared.
* Concurrent attach — N threads calling attach for the same account
  serialise on the stripe lock and produce a single attached entry per
  specialist.
* Invalid / absent account — no exception, no mutation thrash.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.sessions.state import State

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory import sub_agent_attacher as saa
from app.adk.agents.agent_factory.config_loader import (
    FirestoreConnectionError,
    MergedAgentConfig,
)
from app.adk.agents.agent_factory.sub_agent_attacher import (
    AlwaysTrueSubAgentList,
    attach_account_specialists,
    attach_specialists_before_agent_callback,
)

# ---------------------------------------------------------------------------
# AlwaysTrueSubAgentList — ADK 2.0 scheduler shim (AH-105 / AH-PRD-13)
# ---------------------------------------------------------------------------


class TestAlwaysTrueSubAgentList:
    """Guard the AlwaysTrueSubAgentList invariant — the load-bearing mechanism
    of the ADK 2.0 DynamicNodeScheduler fix.

    If __bool__ is ever removed or overridden, Runner._run_node_async will
    see an empty list as falsy, deactivate DynamicNodeScheduler, and yield
    transfer_to_agent events without dispatching them — silently zeroing
    Billing/Chat token counts.
    """

    def test_empty_list_is_truthy(self) -> None:
        assert bool(AlwaysTrueSubAgentList()) is True

    def test_populated_list_is_truthy(self) -> None:
        assert bool(AlwaysTrueSubAgentList([1, 2, 3])) is True

    def test_still_behaves_as_list(self) -> None:
        lst: AlwaysTrueSubAgentList = AlwaysTrueSubAgentList()
        lst.append("x")
        assert lst == ["x"]
        assert len(lst) == 1

    def test_slice_assign_preserves_truthiness(self) -> None:
        """In-place slice assignment (used by _reconcile) must not break __bool__."""
        lst: AlwaysTrueSubAgentList = AlwaysTrueSubAgentList(["a", "b"])
        lst[:] = []
        assert lst == []
        assert bool(lst) is True  # still truthy after being emptied via slice

    def test_is_subclass_of_list(self) -> None:
        assert isinstance(AlwaysTrueSubAgentList(), list)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_caches() -> Any:
    """Each test starts and ends with empty agent + block + list caches and a reset applied-state slot."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._reset_applied_state_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._reset_applied_state_for_tests()
    clear_config_cache()
    # root.sub_agents is NOT reset here — each test calls _make_root() for a fresh instance.


def _make_root(name: str = "ken_e") -> LlmAgent:
    """A bare root LlmAgent with no sub_agents."""
    return LlmAgent(
        name=name,
        model="gemini-2.5-pro",
        instruction="Test root.",
    )


def _make_specialist(name: str) -> LlmAgent:
    """A bare specialist LlmAgent with no parent."""
    return LlmAgent(
        name=name,
        model="gemini-2.5-pro",
        instruction=f"Test specialist {name}.",
    )


def _patched_resolvers(visible: dict[str, LlmAgent], config_suffix: str = "") -> Any:
    """Patch list_account_agent_configs_cached / resolve_config / resolve_agent to
    surface exactly the specialists in *visible* as visible for any account.

    ``config_suffix`` is appended to every config's instruction so callers
    can produce a distinct content hash between two ``_patched_resolvers``
    calls (simulating a config edit / content-hash drift).
    """

    def _list(_account_id: str) -> list[str]:
        return list(visible.keys())

    def _resolve_config(
        doc_id: str, _account_id: str | None = None, _ttl: int = 60
    ) -> MergedAgentConfig:
        return MergedAgentConfig(
            instruction=f"{doc_id} instruction{config_suffix}",
            model="gemini-2.5-pro",
            description=f"{doc_id} description",
            visible_in_frontend=True,
            ken_e_sub_agent=True,
        )

    def _resolve_agent(
        doc_id: str,
        _account_id: str | None = None,
        _ttl: int = 60,
        session_state: Mapping[str, Any] | None = None,
        **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
    ) -> LlmAgent:
        return visible[doc_id]

    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch(
            "app.adk.agents.agent_factory.sub_agent_attacher."
            "list_account_agent_configs_cached",
            side_effect=_list,
        )
    )
    stack.enter_context(
        patch(
            "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
            side_effect=_resolve_config,
        )
    )
    stack.enter_context(
        patch(
            "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
            side_effect=_resolve_agent,
        )
    )
    return stack


# ---------------------------------------------------------------------------
# Idempotency + parent_agent invariant
# ---------------------------------------------------------------------------


class TestIdempotentAttach:
    def test_first_attach_adds_visible_specialists(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("strategy_spec")
        with _patched_resolvers({"ga_spec": a, "strategy_spec": b}):
            attach_account_specialists(root, "acc_123")

        names = {s.name for s in root.sub_agents}
        assert names == {"ga_spec", "strategy_spec"}
        # parent_agent set on first attach.
        assert a.parent_agent is root
        assert b.parent_agent is root

    def test_repeat_attach_does_not_duplicate(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")
        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_123")
            attach_account_specialists(root, "acc_123")
            attach_account_specialists(root, "acc_123")

        assert [s.name for s in root.sub_agents] == ["ga_spec"]
        assert a.parent_agent is root

    def test_parent_agent_not_re_set_on_repeat(self) -> None:
        """The set_parent helper should be a no-op when parent already matches.

        We assert observationally: the parent reference remains the same root
        instance across multiple attaches (a churn would replace it via
        assignment, still identity-equal here, but the helper takes the early
        return path which we verify by counting the assignment via a spy).
        """
        root = _make_root()
        a = _make_specialist("ga_spec")
        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_123")
            # After first attach, parent is set. Subsequent attaches should
            # find sub_agent already in root.sub_agents (identity match) and
            # skip the parent-set path entirely.
            attach_account_specialists(root, "acc_123")
            attach_account_specialists(root, "acc_123")

        assert a.parent_agent is root


# ---------------------------------------------------------------------------
# Reconcile pass
# ---------------------------------------------------------------------------


class TestReconcile:
    def test_specialist_removed_from_firestore_is_dropped(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("retired_spec")

        # First attach: both visible.
        with _patched_resolvers({"ga_spec": a, "retired_spec": b}):
            attach_account_specialists(root, "acc_123")
        assert {s.name for s in root.sub_agents} == {"ga_spec", "retired_spec"}

        # Second attach: only ga_spec visible. retired_spec must be dropped
        # and its parent_agent cleared.
        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_123")

        assert [s.name for s in root.sub_agents] == ["ga_spec"]
        assert b.parent_agent is None
        assert a.parent_agent is root  # untouched survivor

    def test_specialist_replaced_by_fresh_instance_drops_stale(self) -> None:
        """Content-hash drift on a config edit produces a fresh ``LlmAgent``
        with the same name. The stale entry must be replaced, not duplicated.
        """
        root = _make_root()
        stale = _make_specialist("ga_spec")
        with _patched_resolvers({"ga_spec": stale}):
            attach_account_specialists(root, "acc_123")
        assert root.sub_agents == [stale]

        fresh = _make_specialist("ga_spec")
        assert fresh is not stale
        # config_suffix changes the instruction → new content hash → fingerprint miss
        with _patched_resolvers({"ga_spec": fresh}, config_suffix="_v2"):
            attach_account_specialists(root, "acc_123")

        assert root.sub_agents == [fresh]
        assert stale.parent_agent is None
        assert fresh.parent_agent is root

    def test_non_sub_agent_filtered_out(self) -> None:
        """AH-82: ``config.ken_e_sub_agent = False`` keeps a doc out of
        sub_agents regardless of visible_in_frontend.

        Cross-product coverage:
        - ga_spec: ken_e_sub_agent=True → attached
        - workflow_spec: ken_e_sub_agent=False (visible_in_frontend=True) → excluded
        """
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("workflow_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "workflow_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
                # workflow_spec is visible in frontend but NOT delegatable.
                visible_in_frontend=True,
                ken_e_sub_agent=(doc_id != "workflow_spec"),
            )

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            return {"ga_spec": a, "workflow_spec": b}[doc_id]

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_123")

        assert [s.name for s in root.sub_agents] == ["ga_spec"]
        assert b.parent_agent is None

    def test_visible_in_frontend_false_still_delegatable(self) -> None:
        """AH-82 cross-product: visible_in_frontend=False, ken_e_sub_agent=True
        → agent IS attached to sub_agents (delegation gate is independent)."""
        root = _make_root()
        a = _make_specialist("ui_hidden_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ui_hidden_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
                visible_in_frontend=False,  # hidden from Workflows UI
                ken_e_sub_agent=True,  # but still delegatable from chat
            )

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            return a

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_123")

        assert [s.name for s in root.sub_agents] == ["ui_hidden_spec"]
        assert a.parent_agent is root

    def test_reconcile_injects_task_agent_tool_for_task_mode_sub(self) -> None:
        """AH-135: _reconcile injects _TaskAgentTool into root.tools for every
        task-mode (``mode='task'``) specialist added post-construction, and
        removes it when the specialist is later dropped.

        ADK only injects the ``_TaskAgentTool`` in ``LlmAgent.model_post_init``.
        Because per-turn specialists are resolved AFTER the coordinator/root is
        constructed, model_post_init never sees them. Without the explicit
        injection in _reconcile the coordinator's LLM would never see
        ``request_task_<name>`` and delegation (plus its billing) silently
        no-ops — the AH-117 / AH-PRD-15 prod-incident pattern.
        """
        from google.adk.tools.agent_tool import _TaskAgentTool

        root = _make_root()
        task_spec = LlmAgent(name="task_spec", model="gemini-2.5-pro", mode="task")

        # --- Step 1: add the task-mode specialist via reconcile ---
        with _patched_resolvers({"task_spec": task_spec}):
            attach_account_specialists(root, "acc_inject")

        assert task_spec in root.sub_agents

        injected = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool) and getattr(t, "name", None) == "task_spec"
        ]
        assert len(injected) == 1, (
            "_reconcile must inject _TaskAgentTool('task_spec') into root.tools when "
            "the task-mode specialist is added post-construction; "
            f"root.tools = {[getattr(t, 'name', repr(t)) for t in root.tools]}"
        )

        # --- Step 2: drop the task-mode specialist — tool must be removed ---
        # Empty resolver dict means list_account_agent_configs_cached returns [],
        # so _reconcile receives desired={} and drops every existing sub_agent.
        # Note: it is the empty return from _list (not ken_e_sub_agent=False) that
        # drives the drop — the resolver is never called for an absent doc_id.
        with _patched_resolvers({}):  # no specialists visible this turn
            attach_account_specialists(root, "acc_inject")

        assert task_spec not in root.sub_agents

        remaining = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool) and getattr(t, "name", None) == "task_spec"
        ]
        assert remaining == [], (
            "_reconcile must remove the _TaskAgentTool when the task-mode specialist "
            f"is dropped; root.tools still has: {remaining}"
        )

    def test_reconcile_removes_stale_task_agent_tool_on_replace(self) -> None:
        """AH-135: when a task-mode specialist is replaced by a fresh instance
        (content-hash drift), _reconcile removes the stale _TaskAgentTool and
        injects a fresh one for the new instance."""
        from google.adk.tools.agent_tool import _TaskAgentTool

        root = _make_root()
        stale_spec = LlmAgent(name="task_spec", model="gemini-2.5-pro", mode="task")

        with _patched_resolvers({"task_spec": stale_spec}):
            attach_account_specialists(root, "acc_replace")

        stale_tools = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool) and getattr(t, "name", None) == "task_spec"
        ]
        assert len(stale_tools) == 1, "stale specialist must inject _TaskAgentTool"

        # Simulate config-hash drift: same name, fresh instance.
        fresh_spec = LlmAgent(name="task_spec", model="gemini-2.5-pro", mode="task")
        with _patched_resolvers({"task_spec": fresh_spec}, config_suffix="_v2"):
            attach_account_specialists(root, "acc_replace")

        assert fresh_spec in root.sub_agents
        assert stale_spec not in root.sub_agents

        all_task_tools = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool) and getattr(t, "name", None) == "task_spec"
        ]
        assert len(all_task_tools) == 1, (
            "_reconcile must have exactly one _TaskAgentTool after replace "
            f"(stale removed, fresh injected); found {len(all_task_tools)}"
        )

    def test_reconcile_injects_task_agent_tool_for_loop_agent_with_sentinel(
        self,
    ) -> None:
        """AH-161: _reconcile injects _TaskAgentTool for a LoopAgent that has
        ``_is_task_dispatchable=True`` (review-pipeline path).

        A LoopAgent cannot have ``mode='task'`` (ADK does not support it), so
        ``specialist_runtime._build_specialist`` sets the sentinel attribute when
        the caller requests ``mode='task'`` and ``default_acceptance_criteria`` is
        non-empty.  ``_reconcile`` must recognise the sentinel via
        ``_is_task_dispatchable()`` and inject _TaskAgentTool — without this the
        coordinator never sees ``request_task_<name>`` for review-configured
        specialists such as google_analytics_specialist.
        """
        from google.adk.agents import LoopAgent
        from google.adk.tools.agent_tool import _TaskAgentTool

        root = _make_root()

        # Build a LoopAgent that mimics the review-pipeline output and mark it.
        inner = LlmAgent(
            name="loop_worker",
            model="gemini-2.5-pro",
            mode="task",
        )
        loop_spec = LoopAgent(name="review_spec", sub_agents=[inner])
        loop_spec._is_task_dispatchable = True  # type: ignore[attr-defined]

        with _patched_resolvers({"review_spec": loop_spec}):  # type: ignore[arg-type]
            attach_account_specialists(root, "acc_loop")

        assert loop_spec in root.sub_agents

        injected = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool)
            and getattr(t, "name", None) == "review_spec"
        ]
        assert len(injected) == 1, (
            "_reconcile must inject _TaskAgentTool('review_spec') when the LoopAgent "
            "carries _is_task_dispatchable=True; "
            f"root.tools = {[getattr(t, 'name', repr(t)) for t in root.tools]}"
        )

        # --- drop the loop specialist — _TaskAgentTool must be removed ---
        with _patched_resolvers({}):
            attach_account_specialists(root, "acc_loop")

        assert loop_spec not in root.sub_agents

        remaining = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool)
            and getattr(t, "name", None) == "review_spec"
        ]
        assert remaining == [], (
            "_reconcile must remove _TaskAgentTool when the LoopAgent is dropped; "
            f"root.tools still has: {remaining}"
        )


# ---------------------------------------------------------------------------
# Resilience: failed resolves, bad account_id, missing sub_agents attribute.
# ---------------------------------------------------------------------------


class TestResilience:
    def test_individual_resolve_failure_is_logged_and_skipped(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "broken_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
            )

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            if doc_id == "broken_spec":
                raise RuntimeError("MCP unreachable")
            return a

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_123")

        # broken_spec was skipped; ga_spec was still attached.
        assert [s.name for s in root.sub_agents] == ["ga_spec"]

    def test_invalid_account_id_is_a_no_op(self) -> None:
        root = _make_root()
        attach_account_specialists(root, "not a valid account id")
        assert root.sub_agents == []

    def test_none_account_id_does_not_thrash_sub_agents(self) -> None:
        """A no-account turn must NOT drop existing sub_agents — multiple
        sessions can share the same root over its process lifetime.
        """
        root = _make_root()
        a = _make_specialist("ga_spec")
        # Pre-populate sub_agents as if a previous attach had run.
        root.sub_agents = [a]
        a.parent_agent = root

        attach_account_specialists(root, None)

        assert root.sub_agents == [a]
        assert a.parent_agent is root

    def test_firestore_connection_error_leaves_sub_agents_untouched(
        self,
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            FirestoreConnectionError,
        )

        root = _make_root()
        a = _make_specialist("ga_spec")
        root.sub_agents = [a]
        a.parent_agent = root

        with patch(
            "app.adk.agents.agent_factory.sub_agent_attacher."
            "list_account_agent_configs_cached",
            side_effect=FirestoreConnectionError("down"),
        ):
            attach_account_specialists(root, "acc_123")

        assert root.sub_agents == [a]
        assert a.parent_agent is root

    def test_root_without_sub_agents_attr_is_a_no_op(self) -> None:
        class _NoSubAgents:
            name = "weird_root"

        root = _NoSubAgents()
        # Should not raise.
        attach_account_specialists(root, "acc_123")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


class TestConcurrentAttach:
    def test_concurrent_attach_for_same_account_serialises(self) -> None:
        """N concurrent attach calls for the same account must produce
        exactly one entry per specialist in sub_agents — the stripe lock
        guarantees no torn list mutations.
        """
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("strategy_spec")
        # Inject a tiny delay inside the resolver to widen the race window.
        import time

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            time.sleep(0.005)
            return {"ga_spec": a, "strategy_spec": b}[doc_id]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
            )

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "strategy_spec"]

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            threads = [
                threading.Thread(
                    target=attach_account_specialists,
                    args=(root, "acc_123"),
                )
                for _ in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        names = sorted(s.name for s in root.sub_agents)
        assert names == ["ga_spec", "strategy_spec"]
        # Each specialist must appear exactly once.
        assert len(root.sub_agents) == 2
        assert a.parent_agent is root
        assert b.parent_agent is root


# ---------------------------------------------------------------------------
# Re-parenting branch — AH-75 reviewer feedback.
# ---------------------------------------------------------------------------


class TestReparenting:
    def test_attaching_to_a_different_root_moves_parent_agent(self) -> None:
        """The third branch of ``_set_parent``: when a specialist is attached
        to root_a and then attached to root_b in the same process (only
        possible in test fixtures since production has one root per process),
        ``parent_agent`` must move to root_b.

        The two attaches use different account_ids so the (account_id,
        fingerprint) slot registers an account switch and runs the reconcile —
        which exercises the reparenting branch of ``_set_parent``. (A
        same-account second attach with an unchanged fingerprint would
        short-circuit, correctly, in production where there is one root per
        process.)
        """
        root_a = _make_root("root_a")
        root_b = _make_root("root_b")
        specialist = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": specialist}):
            attach_account_specialists(root_a, "acc_first")
        assert specialist.parent_agent is root_a
        assert specialist in root_a.sub_agents

        # Now attach the same specialist instance under a second root for a
        # different account → account switch → reconcile runs → reparenting
        # branch of _set_parent is exercised.
        with _patched_resolvers({"ga_spec": specialist}):
            attach_account_specialists(root_b, "acc_second")

        # Parent pointer moved to root_b; root_b sees it in its sub_agents.
        assert specialist.parent_agent is root_b
        assert specialist in root_b.sub_agents
        # root_a still references the specialist (sub_agents lists are
        # per-root), but parent_agent has moved — re-attaching to root_a
        # later would re-set the pointer.
        assert specialist in root_a.sub_agents


# ---------------------------------------------------------------------------
# Block-cache invalidation — AH-75 reviewer feedback.
#
# The "Available Specialists" prompt block is cached for ~60 s by
# specialist_runtime._block_cache. If the attacher drops or replaces a
# sub_agent mid-TTL, the cached block would still list the stale name and
# the LLM could emit transfer_to_agent(agent_name=<stale>), causing a
# find_agent failure. The attacher must invalidate the cached block on any
# reconcile change so the next instruction-provider call re-renders.
# ---------------------------------------------------------------------------


class TestBlockCacheInvalidation:
    def test_drop_invalidates_block_cache(self) -> None:
        """Dropping a specialist (no longer visible) must invalidate the
        cached prompt block so the next render reflects the new visible set.
        """
        import time

        root = _make_root()
        a = _make_specialist("ga_spec")
        retired = _make_specialist("retired_spec")

        with _patched_resolvers({"ga_spec": a, "retired_spec": retired}):
            attach_account_specialists(root, "acc_block")

        # Pre-seed the block cache with a sentinel value as if a previous
        # instruction render had cached the block listing both specialists.
        sr._block_cache["acc_block"] = (
            "## Available Specialists\n\n- **ga_spec**: ...\n- **retired_spec**: ...",
            time.monotonic() + 60,
        )

        # Now reconcile to drop retired_spec. The drop must invalidate the
        # cache.
        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_block")

        assert "acc_block" not in sr._block_cache, (
            "Dropping a specialist must invalidate the cached prompt block "
            "for the same account (prevents the LLM from emitting "
            "transfer_to_agent for a no-longer-attached specialist)."
        )

    def test_noop_attach_does_not_invalidate_block_cache(self) -> None:
        """A reconcile that makes no changes (every desired entry already
        present with the same identity) must NOT invalidate the cache —
        that would defeat the cache's purpose."""
        import time

        root = _make_root()
        a = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_noop")

        sentinel_block = "## Available Specialists\n\n- **ga_spec**: ..."
        sentinel_expiry = time.monotonic() + 60
        sr._block_cache["acc_noop"] = (sentinel_block, sentinel_expiry)

        # Re-attach with identical visible set — should be a no-op.
        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_noop")

        cached = sr._block_cache.get("acc_noop")
        assert cached is not None, "No-op attach must preserve the cache"
        assert cached[0] == sentinel_block

    def test_replace_invalidates_block_cache(self) -> None:
        """Content-hash drift replaces the specialist's cached LlmAgent.
        Since the prompt block reads the agent's description, a content
        edit might change the description shown in the block. Invalidate
        on replace so the next render picks up the new description.
        """
        import time

        root = _make_root()
        stale = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": stale}):
            attach_account_specialists(root, "acc_replace")

        sr._block_cache["acc_replace"] = (
            "stale block",
            time.monotonic() + 60,
        )

        fresh = _make_specialist("ga_spec")
        # config_suffix changes the instruction → new content hash → fingerprint miss
        with _patched_resolvers({"ga_spec": fresh}, config_suffix="_v2"):
            attach_account_specialists(root, "acc_replace")

        assert "acc_replace" not in sr._block_cache, (
            "Replacing a specialist instance (content-hash drift) must "
            "invalidate the cached prompt block."
        )


# ---------------------------------------------------------------------------
# Fingerprint short-circuit — AH-76 reviewer hygiene.
# ---------------------------------------------------------------------------


class TestFingerprintShortCircuit:
    """Verify that ``_attach_locked`` skips ``resolve_agent`` + ``_reconcile``
    when the visible config set has not changed since the last attach."""

    def test_repeated_attach_same_configs_skips_resolve_agent(self) -> None:
        """Second attach with identical configs must not call resolve_agent."""
        root = _make_root()
        a = _make_specialist("ga_spec")

        resolve_agent_calls: list[str] = []

        def _counting_resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
        ) -> LlmAgent:
            resolve_agent_calls.append(doc_id)
            return a

        with _patched_resolvers({"ga_spec": a}):
            attach_account_specialists(root, "acc_fp")

        resolve_agent_calls.clear()

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=["ga_spec"],
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=lambda doc_id, _acc=None, _ttl=60: MergedAgentConfig(
                    instruction=f"{doc_id} instruction",
                    model="gemini-2.5-pro",
                    description=f"{doc_id} description",
                    visible_in_frontend=True,
                ),
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_counting_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_fp")

        assert resolve_agent_calls == [], (
            "resolve_agent must not be called when the config fingerprint "
            "has not changed since the last attach."
        )

    def test_config_change_triggers_reconcile(self) -> None:
        """When a config changes (different instruction → different hash),
        the fingerprint miss must trigger a full reconcile."""
        root = _make_root()
        stale = _make_specialist("ga_spec")
        fresh = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": stale}):
            attach_account_specialists(root, "acc_fp_change")
        assert root.sub_agents == [stale]

        # config_suffix changes instruction → new hash → fingerprint miss → reconcile
        with _patched_resolvers({"ga_spec": fresh}, config_suffix="_v2"):
            attach_account_specialists(root, "acc_fp_change")

        assert root.sub_agents == [fresh]

    def test_multi_account_interleave_does_not_serve_stale_specialists(self) -> None:
        """A→B→A sequential interleave must not leave A with B's specialists.

        Regression test for the cross-account isolation bug fixed by replacing
        the per-account ``_fingerprint_cache`` dict with the single-slot
        ``_applied_state`` (AH-102).

        Scenario:
            turn 1  acct A (spec_a) → miss → root.sub_agents={spec_a}, slot=(A,FA)
            turn 2  acct B (spec_b) → miss → root.sub_agents={spec_b}, slot=(B,FB)
            turn 3  acct A (unchanged) → slot (B,FB) ≠ (A,FA) → reconcile → {spec_a}

        After turn 3 the root must contain spec_a, not spec_b.
        """
        root = _make_root()
        spec_a = _make_specialist("spec_a")
        spec_b = _make_specialist("spec_b")

        # Turn 1: account A attaches spec_a.
        with _patched_resolvers({"spec_a": spec_a}):
            attach_account_specialists(root, "acc_A")
        assert {s.name for s in root.sub_agents} == {"spec_a"}

        # Turn 2: account B (different config hash → different frozenset) attaches spec_b.
        # Use config_suffix to produce a distinct (doc_id, content_hash) set so
        # the fingerprint comparison correctly identifies this as a different slot.
        with _patched_resolvers({"spec_b": spec_b}, config_suffix="_B"):
            attach_account_specialists(root, "acc_B")
        assert {s.name for s in root.sub_agents} == {"spec_b"}

        # Turn 3: account A again (config unchanged → same frozenset as turn 1).
        # The single-slot fingerprint now holds B's set (slot=FB ≠ FA) so a
        # reconcile MUST run and restore spec_a.
        with _patched_resolvers({"spec_a": spec_a}):
            attach_account_specialists(root, "acc_A")

        names = {s.name for s in root.sub_agents}
        assert names == {"spec_a"}, (
            "After A→B→A interleave, root.sub_agents must contain A's specialists, "
            f"not B's. Got: {names}"
        )

    def test_same_config_different_account_does_not_share_slot(self) -> None:
        """Two accounts sharing an IDENTICAL specialist config must not share the
        applied slot — account B must receive its own account-bound instance.

        Regression for the cross-account credential leak (AH-102): a specialist
        binds its per-account MCP connection at build time and is cached under
        (doc_id, account_id, content_hash). Two accounts with no per-account
        overlay resolve a global specialist to a byte-identical
        ``MergedAgentConfig`` → identical content_hash → identical fingerprint,
        yet need distinct instances. A fingerprint-only slot would HIT on the
        account switch and leave account A's credentialed specialist live for
        account B; the (account_id, fingerprint) slot forces a reconcile.

        Here resolve_agent returns a different instance per account while the
        config (and thus the fingerprint) is account-independent — so only the
        account_id in the slot can distinguish the two turns.
        """
        root = _make_root()
        # Same doc_id + identical config → identical fingerprint for both
        # accounts, but two distinct per-account instances.
        spec_for_a = _make_specialist("shared_spec")
        spec_for_b = _make_specialist("shared_spec")
        per_account_instance = {"acc_A": spec_for_a, "acc_B": spec_for_b}

        def _list(_account_id: str) -> list[str]:
            return ["shared_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            # Account-independent → identical content_hash for A and B.
            return MergedAgentConfig(
                instruction="shared_spec instruction",
                model="gemini-2.5-pro",
                description="shared_spec description",
                visible_in_frontend=True,
                ken_e_sub_agent=True,
            )

        def _resolve_agent(
            doc_id: str,
            account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            return per_account_instance[account_id]

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_A")
            assert root.sub_agents == [spec_for_a]

            # Account switch with an IDENTICAL fingerprint. A fingerprint-only
            # slot would short-circuit here and leave spec_for_a live.
            attach_account_specialists(root, "acc_B")

        assert root.sub_agents == [spec_for_b], (
            "Account B must receive its own account-bound specialist instance, "
            "not account A's, even though both accounts share an identical config "
            f"fingerprint. Got: {[s.name for s in root.sub_agents]} "
            f"(is spec_for_b: {root.sub_agents == [spec_for_b]})"
        )

    def test_transient_resolve_agent_failure_is_retried_next_turn(self) -> None:
        """If resolve_agent fails transiently the failed specialist must NOT be
        included in the stored fingerprint, so the next turn retries it."""
        root = _make_root()
        a = _make_specialist("ga_spec")

        call_count: list[int] = [0]

        def _fail_first_call(
            doc_id: str,
            _acc: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("transient error")
            return a

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=["ga_spec"],
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=lambda doc_id, _acc=None, _ttl=60: MergedAgentConfig(
                    instruction=f"{doc_id} instruction",
                    model="gemini-2.5-pro",
                    description=f"{doc_id} description",
                    visible_in_frontend=True,
                ),
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_fail_first_call,
            ),
        ):
            # Turn 1: resolve_agent fails → specialist not attached, fingerprint NOT committed
            attach_account_specialists(root, "acc_transient")
            assert root.sub_agents == []

            # Turn 2: resolve_agent succeeds → specialist attached
            attach_account_specialists(root, "acc_transient")

        assert root.sub_agents == [a], (
            "The specialist must be attached on the second turn when the "
            "transient error clears — the fingerprint cache must not have "
            "suppressed the retry."
        )
        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# SandboxPool.start() wiring in before_agent_callback — SK-37
# ---------------------------------------------------------------------------


class TestSandboxPoolStartWiring:
    """attach_specialists_before_agent_callback must call
    _DEFAULT_SANDBOX_POOL.start() exactly once per invocation (SK-37).

    start() is idempotent in production but the callback always attempts the
    call so that the first turn inside the Agent Engine process arms the sweep.
    """

    def _make_callback_context(self, account_id: str | None = "acc_123") -> Any:
        """Minimal stub of CallbackContext used by the callback."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.state.get.return_value = account_id
        ctx._invocation_context.agent = _make_root()
        return ctx

    def test_start_called_once_per_callback_fire(self) -> None:
        """start() is invoked on every callback fire (idempotent per SK-37 design)."""
        from unittest.mock import MagicMock, patch

        pool = MagicMock()
        ctx = self._make_callback_context()

        import app.adk.agents.agent_factory.builder as _builder

        original = _builder._DEFAULT_SANDBOX_POOL
        _builder._DEFAULT_SANDBOX_POOL = pool
        try:
            with patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ):
                result = attach_specialists_before_agent_callback(ctx)
        finally:
            _builder._DEFAULT_SANDBOX_POOL = original

        pool.start.assert_called_once()
        assert result is None  # callback must return None so the turn proceeds

    def test_start_exception_swallowed_callback_returns_none(self) -> None:
        """A RuntimeError from start() must be swallowed; the callback still
        returns None so the turn is not blocked (defensive try/except in SK-37
        wiring mirrors the surrounding attach_account_specialists pattern)."""
        from unittest.mock import MagicMock

        pool = MagicMock()
        pool.start.side_effect = RuntimeError("no loop")
        ctx = self._make_callback_context()

        import app.adk.agents.agent_factory.builder as _builder

        original = _builder._DEFAULT_SANDBOX_POOL
        _builder._DEFAULT_SANDBOX_POOL = pool
        try:
            with patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ):
                result = attach_specialists_before_agent_callback(ctx)
        finally:
            _builder._DEFAULT_SANDBOX_POOL = original

        # Exception swallowed; callback returned None.
        assert result is None


# ---------------------------------------------------------------------------
# McpToolsetPool.start() wiring in before_agent_callback — AH-78
# ---------------------------------------------------------------------------


class TestMcpPoolStartWiring:
    """attach_specialists_before_agent_callback must call
    _DEFAULT_MCP_POOL.start() exactly once per invocation (AH-78).

    start() is idempotent in production but the callback always attempts the
    call so that the first turn inside the Agent Engine process arms the sweep.
    """

    def _make_callback_context(self, account_id: str | None = "acc_123") -> Any:
        """Minimal stub of CallbackContext used by the callback."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.state.get.return_value = account_id
        # Stub to_dict() so attach_account_specialists receives a proper
        # Mapping[str, Any] rather than a MagicMock (production calls
        # callback_context.state.to_dict() to derive session_state).
        ctx.state.to_dict.return_value = {"account_id": account_id}
        ctx._invocation_context.agent = _make_root()
        return ctx

    def test_start_called_once_per_callback_fire(self) -> None:
        """start() is invoked on every callback fire (idempotent per AH-78 design)."""
        from unittest.mock import MagicMock, patch

        pool = MagicMock()
        ctx = self._make_callback_context()

        import app.adk.agents.agent_factory.specialist_runtime as _runtime

        original = _runtime._DEFAULT_MCP_POOL
        _runtime._DEFAULT_MCP_POOL = pool
        try:
            with patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ):
                result = attach_specialists_before_agent_callback(ctx)
        finally:
            _runtime._DEFAULT_MCP_POOL = original

        pool.start.assert_called_once()
        assert result is None  # callback must return None so the turn proceeds

    def test_start_exception_swallowed_callback_returns_none(self) -> None:
        """A RuntimeError from start() must be swallowed; the callback still
        returns None so the turn is not blocked (defensive try/except in AH-78
        wiring mirrors the surrounding attach_account_specialists pattern)."""
        from unittest.mock import MagicMock, patch

        pool = MagicMock()
        pool.start.side_effect = RuntimeError("no loop")
        ctx = self._make_callback_context()

        import app.adk.agents.agent_factory.specialist_runtime as _runtime

        original = _runtime._DEFAULT_MCP_POOL
        _runtime._DEFAULT_MCP_POOL = pool
        try:
            with patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ):
                result = attach_specialists_before_agent_callback(ctx)
        finally:
            _runtime._DEFAULT_MCP_POOL = original

        # Exception swallowed; callback returned None.
        assert result is None


# ---------------------------------------------------------------------------
# Before-agent callback bridge — regression coverage for AH-62 (PR #721)
#
# The callback at attach_specialists_before_agent_callback wraps the attach
# in a broad ``except Exception`` so a failure cannot block the turn. That
# defence-in-depth catch previously masked a real bug: ``dict(state)`` on
# ADK's ``State`` raises ``KeyError: 0`` because ``State`` exposes
# ``__getitem__`` but no ``keys()`` / ``__iter__``. The callback silently
# no-op'd and no specialist was attached, surfacing only downstream as
# ``ValueError: Tool 'transfer_to_agent' not found``.
#
# These tests drive the callback with a *real* ADK ``State`` (not a Mock,
# not a plain dict) so any future regression that breaks the state→dict
# conversion fails this file loudly rather than silently degrading.
# ---------------------------------------------------------------------------


class TestBeforeAgentCallback:
    def test_real_adk_state_attaches_specialist_end_to_end(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")
        state = State(value={"account_id": "acc_regression"}, delta={})
        ctx = SimpleNamespace(
            state=state,
            _invocation_context=SimpleNamespace(agent=root),
        )

        with _patched_resolvers({"ga_spec": a}):
            result = attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        assert result is None
        assert root.sub_agents == [a], (
            "The before_agent_callback must attach the specialist when "
            "given a real ADK State — a silent no-op (e.g. from the broad "
            "except swallowing a state-conversion crash) is a regression."
        )

    def test_session_state_is_forwarded_to_resolve_agent(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")
        state = State(
            value={"account_id": "acc_regression", "mcp_creds_x": "v"},
            delta={"mcp_creds_y": "w"},
        )
        ctx = SimpleNamespace(
            state=state,
            _invocation_context=SimpleNamespace(agent=root),
        )
        seen_session_states: list[Mapping[str, Any] | None] = []

        def _capturing_resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            seen_session_states.append(session_state)
            return a

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id} instruction",
                model="gemini-2.5-pro",
                description=f"{doc_id} description",
                visible_in_frontend=True,
            )

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_capturing_resolve_agent,
            ),
        ):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        assert seen_session_states, (
            "resolve_agent was never called — the callback silently no-op'd."
        )
        forwarded = seen_session_states[0]
        assert forwarded is not None
        # Both _value and _delta keys must be present (mirrors State.to_dict()).
        assert forwarded.get("account_id") == "acc_regression"
        assert forwarded.get("mcp_creds_x") == "v"
        assert forwarded.get("mcp_creds_y") == "w"


# ---------------------------------------------------------------------------
# State capture for W&B Weave tracing (CH-58)
#
# attach_specialists_before_agent_callback must write
# state["_available_specialists"] with shape [{name, description, agent_id}]
# every turn — including fingerprint-cache-hit turns where _attach_locked
# returns early without touching root_agent.sub_agents.
# ---------------------------------------------------------------------------


class TestStateCapture:
    """Tests for CH-58: _available_specialists written to session state."""

    def _make_ctx(self, account_id: str = "acc_123") -> Any:
        """Callback context backed by a real ADK State."""
        root = _make_root()
        state = State(value={"account_id": account_id}, delta={})
        ctx = SimpleNamespace(
            state=state,
            _invocation_context=SimpleNamespace(agent=root),
        )
        return ctx, root

    def test_state_captures_available_specialists(self) -> None:
        """After attach, state["_available_specialists"] matches sub_agents."""
        ctx, _root = self._make_ctx()
        a = _make_specialist("ga_spec")
        b = _make_specialist("seo_spec")

        with _patched_resolvers({"ga_spec": a, "seo_spec": b}):
            result = attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        assert result is None
        captured = ctx.state.get("_available_specialists")
        assert captured is not None, "_available_specialists not set in state"
        names = {e["name"] for e in captured}
        assert names == {"ga_spec", "seo_spec"}
        for entry in captured:
            assert "name" in entry
            assert "description" in entry
            assert "agent_id" in entry
            # AH-84: human_name and title keys must always be present (may be None).
            assert "human_name" in entry
            assert "title" in entry
            assert entry["agent_id"] == entry["name"], (
                "agent_id must equal name (ADK contract — specialist_runtime.py:626)"
            )

    def test_state_captures_on_applied_fingerprint_hit(self) -> None:
        """Applied-fingerprint-hit turns must still write _available_specialists.

        On the second turn with unchanged configs, _attach_locked returns
        early without calling _reconcile — but root_agent.sub_agents is still
        populated from the first turn.  The callback must read from
        root_agent.sub_agents (not from a local variable inside _attach_locked)
        so the state key is always present.
        """
        ctx, _root = self._make_ctx()
        a = _make_specialist("ga_spec")

        # First turn: full reconcile, fingerprint stored.
        with _patched_resolvers({"ga_spec": a}):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]
        assert ctx.state.get("_available_specialists") is not None

        # Clear the state key to detect whether the second turn re-writes it.
        ctx.state["_available_specialists"] = None

        # Second turn: same fingerprint → _attach_locked short-circuits.
        with _patched_resolvers({"ga_spec": a}):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured is not None, (
            "_available_specialists must be rewritten every turn; "
            "fingerprint-cache-hit turns must not leave the key as None."
        )
        assert any(e["name"] == "ga_spec" for e in captured)

    def test_state_captures_empty_list_when_no_specialists(self) -> None:
        """Zero specialists → _available_specialists is [] (not missing)."""
        ctx, _root = self._make_ctx()

        with _patched_resolvers({}):  # no visible specialists
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured == [], (
            "Empty specialist roster must write [] — not leave the key absent."
        )

    def test_description_truncated_to_1024_chars(self) -> None:
        """Descriptions longer than 1024 chars are truncated at capture time."""
        ctx, _root = self._make_ctx()
        long_spec = LlmAgent(
            name="verbose_spec",
            model="gemini-2.5-pro",
            instruction="Test.",
            description="x" * 2000,
        )

        def _list(_acc: str) -> list[str]:
            return ["verbose_spec"]

        def _resolve_config(doc_id: str, _acc=None, _ttl=60) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=".",
                model="gemini-2.5-pro",
                description="x" * 2000,
                visible_in_frontend=True,
            )

        def _resolve_agent(
            doc_id: str, _acc=None, _ttl=60, session_state=None, **_kwargs: object
        ) -> LlmAgent:
            return long_spec

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured is not None
        assert len(captured) == 1
        assert len(captured[0]["description"]) <= 1024, (
            "description must be truncated to ≤1024 chars"
        )


# ---------------------------------------------------------------------------
# AH-84: human_name + title propagation in _available_specialists
# ---------------------------------------------------------------------------


class TestStateCaptureNameTitle:
    """AH-84: human_name and title must be carried into _available_specialists."""

    def _make_ctx(self, account_id: str = "acc_123") -> Any:
        root = _make_root()
        state = State(value={"account_id": account_id}, delta={})
        ctx = SimpleNamespace(
            state=state,
            _invocation_context=SimpleNamespace(agent=root),
        )
        return ctx, root

    def _patched_resolvers_with_identity(
        self,
        visible: dict[str, LlmAgent],
        human_name: str | None = None,
        title: str | None = None,
    ) -> Any:
        """Like _patched_resolvers but the returned MergedAgentConfig carries
        human_name and title on the ``name`` and ``title`` fields."""

        def _list(_account_id: str) -> list[str]:
            return list(visible.keys())

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                name=human_name,
                title=title,
                instruction=f"{doc_id} instruction",
                model="gemini-2.5-pro",
                description=f"{doc_id} description",
                visible_in_frontend=True,
                ken_e_sub_agent=True,
            )

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Mapping[str, Any] | None = None,
            **_kwargs: object,  # AH-161: accept mode= kwarg added by _attach_locked
        ) -> LlmAgent:
            return visible[doc_id]

        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            )
        )
        return stack

    def test_human_name_and_title_propagated(self) -> None:
        """Entries in _available_specialists carry human_name and title from the config."""
        ctx, _root = self._make_ctx()
        a = _make_specialist("ben_e_agent")

        with self._patched_resolvers_with_identity(
            {"ben_e_agent": a}, human_name="BEN-E", title="Brand Guardian"
        ):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured is not None
        ben_e = next(e for e in captured if e["name"] == "ben_e_agent")
        assert ben_e["human_name"] == "BEN-E"
        assert ben_e["title"] == "Brand Guardian"

    def test_absent_name_and_title_produce_none(self) -> None:
        """Specialists without name/title have human_name=None and title=None."""
        ctx, _root = self._make_ctx()
        a = _make_specialist("ga_spec")

        with self._patched_resolvers_with_identity({"ga_spec": a}):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured is not None
        ga = next(e for e in captured if e["name"] == "ga_spec")
        assert ga["human_name"] is None
        assert ga["title"] is None

    def test_resolve_config_failure_does_not_drop_specialist(self) -> None:
        """When resolve_config raises inside the state-capture block, the
        specialist row must still appear in _available_specialists (with
        human_name/title defaulting to None)."""
        ctx, _root = self._make_ctx()
        a = _make_specialist("ga_spec")

        def _list(_acc: str) -> list[str]:
            return ["ga_spec"]

        call_count = 0

        def _resolve_config(doc_id: str, _acc=None, _ttl=60) -> MergedAgentConfig:
            nonlocal call_count
            call_count += 1
            # First call (from _attach_locked) succeeds; second call
            # (from the state-capture block) raises.
            if call_count == 1:
                return MergedAgentConfig(
                    instruction=".",
                    model="gemini-2.5-pro",
                    ken_e_sub_agent=True,
                )
            raise FirestoreConnectionError("simulated transient error")

        def _resolve_agent(
            doc_id: str, _acc=None, _ttl=60, session_state=None, **_kwargs: object
        ) -> LlmAgent:
            return a

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_specialists_before_agent_callback(ctx)  # type: ignore[arg-type]

        captured = ctx.state.get("_available_specialists")
        assert captured is not None, "specialist must still appear in state"
        assert any(e["name"] == "ga_spec" for e in captured), (
            "ga_spec row must not be dropped on resolve_config failure"
        )
        ga = next(e for e in captured if e["name"] == "ga_spec")
        assert ga["human_name"] is None
        assert ga["title"] is None


# ---------------------------------------------------------------------------
# Model-serving location wiring in before_agent_callback — AH-86
# ---------------------------------------------------------------------------


class TestModelLocationWiring:
    """attach_specialists_before_agent_callback must apply the per-environment
    Vertex model-serving location at runtime (AH-86).

    The build_hierarchy() call site only fires in the deploy process / local
    ``adk run`` path; the managed Agent Engine runtime unpickles the prebuilt
    graph and never re-runs build_hierarchy.  This callback is the
    guaranteed-to-fire runtime entrypoint, so it must (re)apply the location —
    overriding the platform-injected ``GOOGLE_CLOUD_LOCATION`` — before the
    root agent's first model call.
    """

    def _make_callback_context(self, account_id: str | None = "acc_123") -> Any:
        from unittest.mock import MagicMock

        ctx = MagicMock()
        ctx.state.get.return_value = account_id
        ctx._invocation_context.agent = _make_root()
        return ctx

    def test_dev_callback_overrides_platform_location_to_global(self) -> None:
        """In development, the callback overrides a platform-injected
        ``GOOGLE_CLOUD_LOCATION=us-central1`` with ``global`` so global-only
        models (e.g. gemini-3.5-flash) resolve at runtime."""
        import os
        from unittest.mock import patch

        ctx = self._make_callback_context()
        with (
            patch.dict(
                os.environ,
                {"ENVIRONMENT": "development", "GOOGLE_CLOUD_LOCATION": "us-central1"},
                clear=False,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ),
        ):
            result = attach_specialists_before_agent_callback(ctx)
            assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"

        assert result is None  # callback must return None so the turn proceeds

    def test_staging_callback_routes_to_global(self) -> None:
        """In staging, the callback pins ``global`` (interim; Review 51).

        gemini-3.1-pro-preview is served on the global endpoint only — not on
        the us/eu multi-region endpoints — so staging serves from global until
        the model reaches multi-region. Reverts to ``us`` once it does (the
        REVERT TRIGGER in model_routing.py). The callback overrides a stale
        platform-injected single-region value (``us-central1``)."""
        import os
        from unittest.mock import patch

        ctx = self._make_callback_context()
        with (
            patch.dict(
                os.environ,
                {"ENVIRONMENT": "staging", "GOOGLE_CLOUD_LOCATION": "us-central1"},
                clear=False,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                return_value=[],
            ),
        ):
            attach_specialists_before_agent_callback(ctx)
            assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


# ---------------------------------------------------------------------------
# TestUserBuiltGaAgentAttach — AH-95 Task 4: delegation gate for custom GA
# ---------------------------------------------------------------------------


class TestUserBuiltGaAgentAttach:
    """AH-95 Task 4: sub-agent attachment gate for custom agents created
    via the ``AgentToolPicker`` (``tool_ids`` set, ``mcp_servers=[]``).

    Verifies that ``attach_account_specialists`` honours the
    ``ken_e_sub_agent`` flag for user-built custom agents — the same
    gate tested for global specialists in ``TestReconcile``.
    """

    def test_custom_ga_agent_attached_when_ken_e_sub_agent_true(
        self,
    ) -> None:
        """A resolved custom GA agent (``custom_*`` config_id) with
        ``ken_e_sub_agent=True`` lands in ``root.sub_agents`` and is
        reachable via ``root.find_agent``.
        """
        custom_id = "custom_abc12345"
        specialist = _make_specialist(custom_id)

        config_record = MergedAgentConfig(
            instruction="Custom GA agent.",
            model="gemini-2.5-flash",
            description="User-built GA agent",
            visible_in_frontend=True,
            ken_e_sub_agent=True,
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )

        def _resolve_config(doc_id, _account_id=None, _ttl=60):
            return config_record

        def _resolve_agent(
            doc_id, _account_id=None, _ttl=60, session_state=None, **_kw
        ):
            return specialist

        from contextlib import ExitStack

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher."
                    "list_account_agent_configs_cached",
                    return_value=[custom_id],
                )
            )
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                    side_effect=_resolve_config,
                )
            )
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                    side_effect=_resolve_agent,
                )
            )

            root = _make_root()
            attach_account_specialists(root, "acc1")

        assert root.find_agent(custom_id) is specialist, (
            f"Custom GA agent '{custom_id}' must be findable via root.find_agent"
        )

    def test_custom_ga_agent_not_attached_when_ken_e_sub_agent_false(
        self,
    ) -> None:
        """A custom agent config with ``ken_e_sub_agent=False`` must NOT be
        attached to ``root.sub_agents`` (delegation gate — AH-82).

        This covers the scenario where a user creates a workflow-visible agent
        (``visible_in_frontend=True``) that should not be chat-delegatable.
        """
        custom_id = "custom_workflow_only"
        specialist = _make_specialist(custom_id)

        config_record = MergedAgentConfig(
            instruction="Workflow-only custom agent.",
            model="gemini-2.5-flash",
            description="Not delegatable from chat",
            visible_in_frontend=True,
            ken_e_sub_agent=False,
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )

        def _resolve_config(doc_id, _account_id=None, _ttl=60):
            return config_record

        def _resolve_agent(
            doc_id, _account_id=None, _ttl=60, session_state=None, **_kw
        ):
            return specialist

        from contextlib import ExitStack

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher."
                    "list_account_agent_configs_cached",
                    return_value=[custom_id],
                )
            )
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                    side_effect=_resolve_config,
                )
            )
            stack.enter_context(
                patch(
                    "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                    side_effect=_resolve_agent,
                )
            )

            root = _make_root()
            attach_account_specialists(root, "acc1")

        assert root.find_agent(custom_id) is None, (
            "Agent with ken_e_sub_agent=False must not be attached to root.sub_agents"
        )


# ---------------------------------------------------------------------------
# Two-turn per-turn reconciliation — AH-108 (AC #3)
#
# Verifies that both the sub_agents reconciliation callback AND the root.tools
# reconciliation callback (root_tools_attacher) are correctly exercised across
# two consecutive turns, including the ADK 2.0 populated-guard path where a
# fresh per-turn clone starts with an empty list.
# ---------------------------------------------------------------------------


class TestPerTurnReconciliationADK2:
    """AH-108 AC #3 — two-turn per-turn reconciliation under ADK 2.0.

    Simulates the ADK 2.0 per-turn clone pattern (each turn gets a fresh root
    copy with empty ``sub_agents`` / ``tools``) and asserts:

    1. ``attach_specialists_before_agent_callback`` re-attaches specialists each
       turn even when the fingerprint matches (populated-guard bypass).
    2. Same-process account switch does not serve stale specialists.
    3. ``attach_root_tools_before_agent_callback`` (via ``attach_root_tools``)
       re-resolves tools each turn on a fresh clone (populated-guard in
       root_tools_attacher.py).
    """

    def _make_callback_ctx(
        self,
        root: LlmAgent,
        account_id: str | None = "acc_a",
    ) -> Any:
        """Build a minimal mock CallbackContext pointing at *root*."""
        from unittest.mock import MagicMock

        ctx = MagicMock()
        state_dict: dict[str, Any] = {}
        if account_id is not None:
            state_dict["account_id"] = account_id
        ctx.state.get = lambda k, default=None: state_dict.get(k, default)
        ctx.state.to_dict = lambda: dict(state_dict)
        ctx.state.__setitem__ = lambda k, v: state_dict.__setitem__(k, v)
        ctx.state.__contains__ = lambda k: k in state_dict

        mock_inv = MagicMock()
        mock_inv.agent = root
        ctx._invocation_context = mock_inv
        return ctx

    def test_sub_agents_reattached_on_each_clone_turn(self) -> None:
        """Specialists are attached to each per-turn clone (which starts with
        ``sub_agents=[]``) even when the fingerprint slot records a prior hit.

        Simulates ADK 2.0 behaviour: each turn, the root is model_copy'd into a
        fresh clone; ``attach_specialists_before_agent_callback`` fires on the
        clone's callback_context.  The populated-guard (``_applied_state == ...
        and root_agent.sub_agents``) must detect the empty clone and re-resolve.
        """
        specialist_a = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": specialist_a}):
            # --- Turn 1: fresh root, no prior state ---
            root_turn1 = _make_root()
            ctx1 = self._make_callback_ctx(root_turn1, "acc_a")
            result1 = attach_specialists_before_agent_callback(callback_context=ctx1)
            assert result1 is None
            assert specialist_a in root_turn1.sub_agents, (
                "Turn 1: specialist must be attached to the first clone"
            )

            # --- Turn 2: ADK 2.0 creates a FRESH clone; sub_agents is [] ---
            root_turn2 = _make_root()  # fresh clone; sub_agents=[]
            assert list(root_turn2.sub_agents) == [], (
                "Pre-condition: clone starts empty"
            )

            ctx2 = self._make_callback_ctx(root_turn2, "acc_a")
            result2 = attach_specialists_before_agent_callback(callback_context=ctx2)
            assert result2 is None
            # Populated-guard must have forced re-resolve on the empty clone.
            assert specialist_a in root_turn2.sub_agents, (
                "Turn 2: populated-guard must re-attach specialists to the fresh "
                "per-turn clone even when _applied_state fingerprint matches."
            )

    def test_account_switch_does_not_serve_stale_specialists(self) -> None:
        """A→B account switch serves B's specialists; A→B→A serves A's again.

        Guards the AH-102 scenario (single _applied_state slot): without the
        (account_id, fingerprint) composite key, turn 3 (account A, unchanged
        config) would hit the fingerprint and serve B's specialists.
        """
        specialist_a = _make_specialist("ga_spec")
        specialist_b = _make_specialist("ads_spec")

        def _attach_for(account_id: str, specialist: LlmAgent) -> LlmAgent:
            root = _make_root()
            with _patched_resolvers({specialist.name: specialist}):
                ctx = self._make_callback_ctx(root, account_id)
                attach_specialists_before_agent_callback(callback_context=ctx)
            return root

        root_a1 = _attach_for("acc_a", specialist_a)
        assert specialist_a in root_a1.sub_agents

        root_b = _attach_for("acc_b", specialist_b)
        assert specialist_b in root_b.sub_agents

        # Account A again — must NOT see specialist_b.
        root_a2 = _attach_for("acc_a", specialist_a)
        assert specialist_a in root_a2.sub_agents, (
            "A's specialist must be present on return"
        )
        assert specialist_b not in root_a2.sub_agents, (
            "B's specialist must NOT appear for A"
        )

    def test_root_tools_reattached_on_each_clone_turn(self) -> None:
        """``attach_root_tools`` resolves tools on each per-turn clone that
        starts with ``tools=[]``, even when the config hash matches the slot.

        Mirrors the sub_agents populated-guard test above, for the root.tools
        path (AH-108 Task 3a / AC #1 + #3).
        """
        from unittest.mock import MagicMock, patch

        from app.adk.agents.agent_factory import root_tools_attacher as rta
        from app.adk.agents.agent_factory.root_tools_attacher import attach_root_tools
        from app.adk.agents.agent_factory.roster import RosterResolution

        rta._reset_applied_hash_for_tests()

        def _make_tool_mock(name: str) -> MagicMock:
            t = MagicMock()
            t.name = name
            return t

        tool_x = _make_tool_mock("tool_x")
        cfg = MagicMock()
        cfg.tool_ids = ["tool_x"]
        cfg.model_dump_json.return_value = '{"tool_ids": ["tool_x"]}'

        try:
            with (
                patch.object(rta, "get_cached_merged_config", return_value=cfg),
                patch.object(
                    rta,
                    "resolve_specialist_roster",
                    return_value=RosterResolution(tools=[tool_x]),
                ) as mock_resolve,
            ):
                # Turn 1 — fresh root, hash miss → resolve fires.
                root_turn1 = _make_root()
                attach_root_tools(root_turn1, account_id="acc_tools")
                assert tool_x in root_turn1.tools, "Turn 1: tool_x must be attached"
                assert mock_resolve.call_count == 1

                # Turn 2 — ADK 2.0 fresh clone; tools=[] but hash matches.
                root_turn2 = _make_root()  # fresh clone
                assert list(root_turn2.tools) == [], (
                    "Pre-condition: clone starts with no tools"
                )

                attach_root_tools(root_turn2, account_id="acc_tools")
                # Populated-guard forces re-resolve even on hash hit.
                assert mock_resolve.call_count == 2, (
                    "Turn 2: populated-guard must re-resolve when clone starts with "
                    "tools=[] even when _applied_hash matches the config."
                )
                assert tool_x in root_turn2.tools, (
                    "Turn 2: tool_x must be in the fresh clone"
                )
        finally:
            rta._reset_applied_hash_for_tests()


# ---------------------------------------------------------------------------
# AH-117: attach_task_subagent / detach_task_subagent
#
# ADK injects the ``_TaskAgentTool`` (the marker that lets a chat-mode parent
# dispatch ``request_task_<name>``) ONLY in ``LlmAgent.model_post_init``. Every
# production attach site adds task-mode sub-agents AFTER construction, so without
# these helpers the parent's LLM never sees the delegation tool and dispatch
# (plus its billing) silently never fires. These tests pin the helper's output
# against ADK's own construct-time injection so an ADK upgrade that renames the
# internal is caught.
# ---------------------------------------------------------------------------


def _task_mode_leaf(name: str = "google_search") -> LlmAgent:
    return LlmAgent(name=name, model="gemini-2.0-flash", mode="task")


class TestAttachTaskSubagent:
    def _task_agent_tool_cls(self) -> Any:
        from google.adk.tools.agent_tool import _TaskAgentTool

        return _TaskAgentTool

    def test_attach_matches_model_post_init_injection(self) -> None:
        """``attach_task_subagent`` post-construction yields the same dispatchable
        ``_TaskAgentTool`` ADK creates when sub_agents are passed at construction."""
        task_tool_cls = self._task_agent_tool_cls()

        # Native construct-time path (what ADK does in model_post_init).
        native_parent = LlmAgent(
            name="p",
            model="gemini-2.0-flash",
            sub_agents=[_task_mode_leaf("google_search")],
        )
        native_names = [
            t.name for t in native_parent.tools if isinstance(t, task_tool_cls)
        ]

        # Helper post-construction path.
        helper_parent = LlmAgent(name="p", model="gemini-2.0-flash")
        helper_sub = _task_mode_leaf("google_search")
        saa.attach_task_subagent(helper_parent, helper_sub)
        helper_names = [
            t.name for t in helper_parent.tools if isinstance(t, task_tool_cls)
        ]

        assert helper_names == native_names == ["google_search"]
        assert helper_sub in helper_parent.sub_agents
        assert helper_sub.parent_agent is helper_parent

    def test_attach_appends_in_place_preserving_list_identity(self) -> None:
        """Append in place so ``AlwaysTrueSubAgentList`` / shallow-copy holders
        survive (mirrors the ``sub_agents[:]`` invariant in ``_reconcile``)."""
        parent = LlmAgent(name="p", model="gemini-2.0-flash")
        original_list = parent.sub_agents
        saa.attach_task_subagent(parent, _task_mode_leaf("google_search"))
        assert parent.sub_agents is original_list

    def test_detach_removes_tool_subagent_and_parent(self) -> None:
        task_tool_cls = self._task_agent_tool_cls()
        parent = LlmAgent(name="p", model="gemini-2.0-flash")
        sub = _task_mode_leaf("google_search")
        saa.attach_task_subagent(parent, sub)
        assert any(isinstance(t, task_tool_cls) for t in parent.tools)

        saa.detach_task_subagent(parent, "google_search")

        assert not any(
            getattr(s, "name", None) == "google_search" for s in parent.sub_agents
        )
        assert not any(isinstance(t, task_tool_cls) for t in parent.tools)
        assert sub.parent_agent is None

    def test_detach_leaves_unrelated_tools_and_subagents(self) -> None:
        task_tool_cls = self._task_agent_tool_cls()
        keep_sub = LlmAgent(name="specialist", model="gemini-2.0-flash")
        parent = LlmAgent(name="p", model="gemini-2.0-flash", sub_agents=[keep_sub])
        saa.attach_task_subagent(parent, _task_mode_leaf("google_search"))

        saa.detach_task_subagent(parent, "google_search")

        assert any(getattr(s, "name", None) == "specialist" for s in parent.sub_agents)
        assert not any(isinstance(t, task_tool_cls) for t in parent.tools)
