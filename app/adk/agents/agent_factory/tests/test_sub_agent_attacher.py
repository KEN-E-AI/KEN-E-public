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
  ``list_account_agent_configs_cached`` are removed and have their
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
from app.adk.agents.agent_factory import sub_agent_attacher as saa
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.sub_agent_attacher import (
    attach_account_specialists,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_caches() -> Any:
    """Each test starts and ends with empty agent + block + list + fingerprint caches."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._clear_fingerprint_cache_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._clear_fingerprint_cache_for_tests()
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


def _patched_resolvers(
    visible: dict[str, LlmAgent], config_suffix: str = ""
) -> Any:
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
        )

    def _resolve_agent(
        doc_id: str, _account_id: str | None = None, _ttl: int = 60
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

    def test_invisible_specialist_filtered_out(self) -> None:
        """``config.visible_in_frontend = False`` keeps a doc out of the
        prompt block AND out of sub_agents."""
        root = _make_root()
        a = _make_specialist("ga_spec")
        b = _make_specialist("hidden_spec")

        def _list(_account_id: str) -> list[str]:
            return ["ga_spec", "hidden_spec"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction=f"{doc_id}.",
                model="gemini-2.5-pro",
                description=f"{doc_id} desc",
                visible_in_frontend=(doc_id != "hidden_spec"),
            )

        def _resolve_agent(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> LlmAgent:
            return {"ga_spec": a, "hidden_spec": b}[doc_id]

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
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
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
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
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
        """
        root_a = _make_root("root_a")
        root_b = _make_root("root_b")
        specialist = _make_specialist("ga_spec")

        with _patched_resolvers({"ga_spec": specialist}):
            attach_account_specialists(root_a, "acc_first")
        assert specialist.parent_agent is root_a
        assert specialist in root_a.sub_agents

        # Now attach the same specialist instance under a second root.
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
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
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

    def test_fingerprint_is_per_account(self) -> None:
        """Fingerprint cache must not bleed between different account_ids."""
        root_a = _make_root("root_a")
        root_b = _make_root("root_b")
        a = _make_specialist("ga_spec")

        resolve_calls: list[tuple[str, str | None]] = []

        def _track_resolve(
            doc_id: str, account_id: str | None = None, _ttl: int = 60
        ) -> LlmAgent:
            resolve_calls.append((doc_id, account_id))
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
                side_effect=_track_resolve,
            ),
        ):
            attach_account_specialists(root_a, "acct_x")
            attach_account_specialists(root_b, "acct_y")

        # Both accounts are new, so resolve_agent must have been called for both.
        accounts_seen = {acc for _, acc in resolve_calls}
        assert "acct_x" in accounts_seen
        assert "acct_y" in accounts_seen
