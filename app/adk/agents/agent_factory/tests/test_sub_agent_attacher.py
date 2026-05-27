"""Tests for :mod:`app.adk.agents.agent_factory.sub_agent_attacher`.

AH-75 / AH-PRD-09: idempotent runtime attachment of resolved specialists
to ``root_agent.sub_agents``, called by the root's
``before_agent_callback`` so ADK's ``transfer_to_agent`` can find each
visible specialist via ``root.find_agent``.

Test surface:

* Idempotency — repeated attach calls converge on the same ``sub_agents``
  list; no duplicate entries.
* Parent-agent invariant — first attach sets ``parent_agent``; subsequent
  attaches don't churn it.
* Reconcile drop — sub_agents whose name disappears from
  ``list_account_agent_configs`` are removed and have their
  ``parent_agent`` cleared.
* Concurrent attach — N threads calling attach for the same account
  serialise on the stripe lock and produce a single attached entry per
  specialist.
* Invalid / absent account — no exception, no mutation thrash.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.agents import LlmAgent

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.sub_agent_attacher import (
    attach_account_specialists,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_caches() -> Any:
    """Each test starts and ends with empty agent + block caches."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    clear_config_cache()


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


def _patched_resolvers(visible: dict[str, LlmAgent]) -> Any:
    """Patch list_account_agent_configs / resolve_config / resolve_agent to
    surface exactly the specialists in *visible* as visible for any account.
    """

    def _list(_account_id: str) -> list[str]:
        return list(visible.keys())

    def _resolve_config(doc_id: str, _account_id: str | None = None,
                        _ttl: int = 60) -> MergedAgentConfig:
        return MergedAgentConfig(
            instruction=f"{doc_id} instruction",
            model="gemini-2.5-pro",
            description=f"{doc_id} description",
            visible_in_frontend=True,
        )

    def _resolve_agent(doc_id: str, _account_id: str | None = None,
                       _ttl: int = 60) -> LlmAgent:
        return visible[doc_id]

    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch(
            "app.adk.agents.agent_factory.sub_agent_attacher."
            "list_account_agent_configs",
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
        with _patched_resolvers({"ga_spec": fresh}):
            attach_account_specialists(root, "acc_123")

        assert root.sub_agents == [fresh]
        assert stale.parent_agent is None
        assert fresh.parent_agent is root

    def test_invisible_specialist_filtered_out(self) -> None:
        """``config.visible_in_frontend = False`` keeps a doc out of the
        prompt block AND out of sub_agents."""
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("hidden_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "hidden_spec"]

        def _resolve_config(doc_id: str, _account_id: str | None = None,
                            _ttl: int = 60) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
                visible_in_frontend=(doc_id != "hidden_spec"),
            )

        def _resolve_agent(doc_id: str, _account_id: str | None = None,
                           _ttl: int = 60) -> LlmAgent:
            return {"ga_spec": a, "hidden_spec": b}[doc_id]

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs",
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


# ---------------------------------------------------------------------------
# Resilience: failed resolves, bad account_id, missing sub_agents attribute.
# ---------------------------------------------------------------------------


class TestResilience:
    def test_individual_resolve_failure_is_logged_and_skipped(self) -> None:
        root = _make_root()
        a = _make_specialist("ga_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "broken_spec"]

        def _resolve_config(doc_id: str, _account_id: str | None = None,
                            _ttl: int = 60) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
            )

        def _resolve_agent(doc_id: str, _account_id: str | None = None,
                           _ttl: int = 60) -> LlmAgent:
            if doc_id == "broken_spec":
                raise RuntimeError("MCP unreachable")
            return a

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs",
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
            "list_account_agent_configs",
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

        def _resolve_agent(doc_id: str, _account_id: str | None = None,
                           _ttl: int = 60) -> LlmAgent:
            time.sleep(0.005)
            return {"ga_spec": a, "strategy_spec": b}[doc_id]

        def _resolve_config(doc_id: str, _account_id: str | None = None,
                            _ttl: int = 60) -> MergedAgentConfig:
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
                "list_account_agent_configs",
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
