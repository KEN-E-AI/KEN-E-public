"""Unit tests for the build-time skill metadata sidecar.

Pure tests — no ADK fixtures, no I/O.  The sidecar's contract is:
* ``record_skill_build_metadata`` merges fields into the per-``(account_id, name)``
  bucket.
* ``get_skill_build_metadata`` returns a copy (caller mutation must not affect
  storage).
* Keyed by ``(account_id, agent.name)`` — isolated across accounts that share a
  specialist name, and stable across ADK 2.0 per-invocation clones (same name).
* Entries are evicted when the owning agent is garbage-collected, with a
  content-hash-change handoff guard so a stale object cannot delete fresh data.
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Iterator

import pytest

from app.adk.agents.agent_factory import skill_metadata as sm
from app.adk.agents.agent_factory.skill_metadata import (
    get_skill_build_metadata,
    record_skill_build_metadata,
)


@pytest.fixture(autouse=True)
def _reset_metadata_state() -> Iterator[None]:
    """Isolate the module-global sidecar dicts + canary flag between tests."""
    sm._metadata.clear()
    sm._owner.clear()
    sm._soft_cap_warned = False
    yield
    sm._metadata.clear()
    sm._owner.clear()
    sm._soft_cap_warned = False


class _FakeAgent:
    """Minimal stand-in for an LlmAgent with a stable ``name`` attribute.

    A plain class (no ``__slots__``) so it supports ``weakref`` — required by the
    sidecar's finalizer-based eviction.
    """

    def __init__(self, name: str = "test_agent") -> None:
        self.name = name


# ---------------------------------------------------------------------------
# Roundtrip / merge / copy semantics
# ---------------------------------------------------------------------------


def test_record_and_get_roundtrip() -> None:
    agent = _FakeAgent("agent_a")
    record_skill_build_metadata(agent, "acct_1", skill_load_total_failure=True)
    assert get_skill_build_metadata(agent, "acct_1") == {
        "skill_load_total_failure": True
    }


def test_get_returns_empty_dict_for_unknown_agent() -> None:
    agent = _FakeAgent("unknown_agent")
    assert get_skill_build_metadata(agent, "acct_1") == {}


def test_record_merges_fields_across_calls() -> None:
    agent = _FakeAgent("agent_merge")
    record_skill_build_metadata(agent, "acct_1", skill_load_total_failure=True)
    record_skill_build_metadata(agent, "acct_1", extra="info")
    assert get_skill_build_metadata(agent, "acct_1") == {
        "skill_load_total_failure": True,
        "extra": "info",
    }


def test_record_later_call_overwrites_same_key() -> None:
    agent = _FakeAgent("agent_overwrite")
    record_skill_build_metadata(agent, "acct_1", status="a")
    record_skill_build_metadata(agent, "acct_1", status="b")
    assert get_skill_build_metadata(agent, "acct_1") == {"status": "b"}


def test_get_returns_copy_caller_mutation_does_not_persist() -> None:
    agent = _FakeAgent("agent_copy")
    record_skill_build_metadata(agent, "acct_1", skill_load_total_failure=True)
    snapshot = get_skill_build_metadata(agent, "acct_1")
    snapshot["skill_load_total_failure"] = False
    snapshot["injected"] = "x"
    assert get_skill_build_metadata(agent, "acct_1") == {
        "skill_load_total_failure": True
    }


# ---------------------------------------------------------------------------
# Account isolation — the headline regression guard
# ---------------------------------------------------------------------------


def test_same_name_different_accounts_are_isolated() -> None:
    """Two accounts sharing a specialist name must NOT share a metadata slot.

    Specialists are cached per (doc_id, account_id), so account A and account B
    produce distinct agent objects with the same ``name``.  If the sidecar were
    keyed by name alone, B's build would clobber A's slot and A's turn would seed
    skills_allowed_tools from B's skill_name_index — silently degrading A's skill
    tool-allowlist open.  Keying by (account_id, name) keeps them isolated.
    """
    agent_a = _FakeAgent("ga_specialist")
    agent_b = _FakeAgent("ga_specialist")  # same name, different account

    record_skill_build_metadata(
        agent_a, "acct_a", skill_name_index={"a_skill": {"skill_id": "sk_a"}}
    )
    record_skill_build_metadata(
        agent_b, "acct_b", skill_name_index={"b_skill": {"skill_id": "sk_b"}}
    )

    # B building after A must not clobber A's slot, and vice-versa.
    assert get_skill_build_metadata(agent_a, "acct_a") == {
        "skill_name_index": {"a_skill": {"skill_id": "sk_a"}}
    }
    assert get_skill_build_metadata(agent_b, "acct_b") == {
        "skill_name_index": {"b_skill": {"skill_id": "sk_b"}}
    }
    # The key is (account_id, name): a lookup with the wrong account_id resolves
    # the OTHER account's slot, never a silently merged one — which is exactly
    # why callers (builder, skill_spans) must pass the matching account_id.
    assert get_skill_build_metadata(agent_a, "acct_b") == {
        "skill_name_index": {"b_skill": {"skill_id": "sk_b"}}
    }


# ---------------------------------------------------------------------------
# Clone stability — ADK 2.0 per-invocation model_copy()
# ---------------------------------------------------------------------------


def test_clone_with_same_name_and_account_resolves_original_metadata() -> None:
    """ADK 2.0 clones carry the same name (different id()) — clone lookup hits."""
    original = _FakeAgent("ga_specialist")
    record_skill_build_metadata(
        original, "acct_1", skill_name_index={"seo": {"skill_id": "sk_1"}}
    )

    clone = _FakeAgent("ga_specialist")  # same name, different object identity
    assert clone is not original
    assert id(clone) != id(original)
    assert get_skill_build_metadata(clone, "acct_1") == {
        "skill_name_index": {"seo": {"skill_id": "sk_1"}}
    }


def test_two_agents_get_isolated_buckets() -> None:
    a = _FakeAgent("agent_isolated_a")
    b = _FakeAgent("agent_isolated_b")
    record_skill_build_metadata(a, "acct_1", skill_load_total_failure=True)
    record_skill_build_metadata(b, "acct_1", skill_load_total_failure=False)
    assert get_skill_build_metadata(a, "acct_1") == {"skill_load_total_failure": True}
    assert get_skill_build_metadata(b, "acct_1") == {"skill_load_total_failure": False}


def test_account_id_present_in_backing_key() -> None:
    """Verify internal storage uses (account_id, name) as the key."""
    agent = _FakeAgent("key_smoke_agent")
    record_skill_build_metadata(agent, "acct_1", x=1)
    assert ("acct_1", "key_smoke_agent") in sm._metadata


# ---------------------------------------------------------------------------
# Eviction + content-hash handoff
# ---------------------------------------------------------------------------


def test_metadata_is_garbage_collected_with_agent() -> None:
    """Dropping the agent reference fires the finalizer and removes the entry."""
    agent = _FakeAgent("gc_agent")
    record_skill_build_metadata(agent, "acct_1", skill_load_total_failure=True)
    key = ("acct_1", "gc_agent")
    assert key in sm._metadata

    del agent
    gc.collect()

    assert key not in sm._metadata
    assert key not in sm._owner


def test_rebuild_same_key_overwrites_and_handoff_does_not_delete_fresh_data() -> None:
    """A fresh build (e.g. config change) re-claims the slot; the stale object's
    finalizer must not delete the new data when it is later collected."""
    first = _FakeAgent("rebuilt_specialist")
    record_skill_build_metadata(first, "acct_1", skill_name_index={"old": {}})

    second = _FakeAgent("rebuilt_specialist")  # same (account, name), new object
    record_skill_build_metadata(second, "acct_1", skill_name_index={"new": {}})

    # Newest build wins the slot.
    assert get_skill_build_metadata(second, "acct_1") == {
        "skill_name_index": {"new": {}}
    }

    # Collecting the stale first object must NOT wipe the fresh entry.
    del first
    gc.collect()
    assert get_skill_build_metadata(second, "acct_1") == {
        "skill_name_index": {"new": {}}
    }

    # Collecting the current owner clears it.
    del second
    gc.collect()
    assert ("acct_1", "rebuilt_specialist") not in sm._metadata


# ---------------------------------------------------------------------------
# Soft-cap canary
# ---------------------------------------------------------------------------


def test_soft_cap_canary_warns_once_past_threshold(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crossing _METADATA_SOFT_CAP emits exactly one WARNING (leak canary).

    Agents are held alive in a list so finalizers do not evict mid-test.
    """
    monkeypatch.setattr(sm, "_METADATA_SOFT_CAP", 5)
    logger_name = "app.adk.agents.agent_factory.skill_metadata"
    held: list[_FakeAgent] = []

    with caplog.at_level(logging.WARNING, logger=logger_name):
        # Fill up to the cap exactly — no warning yet (len == cap, not > cap).
        for i in range(sm._METADATA_SOFT_CAP):
            agent = _FakeAgent(f"spec_{i}")
            held.append(agent)
            record_skill_build_metadata(agent, "acct_1", x=i)
        assert [r for r in caplog.records if r.levelno == logging.WARNING] == []

        # Two more distinct keys cross the cap; the canary fires exactly once.
        for name in ("spec_overflow_1", "spec_overflow_2"):
            agent = _FakeAgent(name)
            held.append(agent)
            record_skill_build_metadata(agent, "acct_1", x=0)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "skill_metadata_dict_exceeded_expected_bound" in warnings[0].getMessage()
    assert held  # keep references alive until assertions complete
