"""Unit tests for app.adk.agents.agent_factory.skill_metadata.

Pure tests — no ADK fixtures, no I/O.  The sidecar's only contract is:
* ``record_skill_build_metadata`` merges fields into the per-agent bucket.
* ``get_skill_build_metadata`` returns a copy (caller mutation must not affect storage).
* When the agent is GC'd, its entry is dropped (no unbounded growth).
"""

from __future__ import annotations

import gc

from app.adk.agents.agent_factory.skill_metadata import (
    _metadata,
    get_skill_build_metadata,
    record_skill_build_metadata,
)


class _FakeAgent:
    """Minimal stand-in for an LlmAgent.  Must support weakref (default for
    plain classes).  Hashability is not required by the sidecar."""


def test_record_and_get_roundtrip() -> None:
    agent = _FakeAgent()
    record_skill_build_metadata(agent, skill_load_total_failure=True)
    assert get_skill_build_metadata(agent) == {"skill_load_total_failure": True}


def test_get_returns_empty_dict_for_unknown_agent() -> None:
    agent = _FakeAgent()
    assert get_skill_build_metadata(agent) == {}


def test_record_merges_fields_across_calls() -> None:
    agent = _FakeAgent()
    record_skill_build_metadata(agent, skill_load_total_failure=True)
    record_skill_build_metadata(agent, extra="info")
    assert get_skill_build_metadata(agent) == {
        "skill_load_total_failure": True,
        "extra": "info",
    }


def test_record_later_call_overwrites_same_key() -> None:
    agent = _FakeAgent()
    record_skill_build_metadata(agent, status="a")
    record_skill_build_metadata(agent, status="b")
    assert get_skill_build_metadata(agent) == {"status": "b"}


def test_get_returns_copy_caller_mutation_does_not_persist() -> None:
    agent = _FakeAgent()
    record_skill_build_metadata(agent, skill_load_total_failure=True)
    snapshot = get_skill_build_metadata(agent)
    snapshot["skill_load_total_failure"] = False
    snapshot["injected"] = "bad"
    # Original bucket must be untouched
    assert get_skill_build_metadata(agent) == {"skill_load_total_failure": True}


def test_metadata_is_garbage_collected_with_agent() -> None:
    """Dropping the agent reference fires the finalizer and removes the entry."""
    agent = _FakeAgent()
    record_skill_build_metadata(agent, skill_load_total_failure=True)
    agent_id = id(agent)
    assert agent_id in _metadata

    del agent
    gc.collect()

    assert agent_id not in _metadata


def test_two_agents_get_isolated_buckets() -> None:
    a = _FakeAgent()
    b = _FakeAgent()
    record_skill_build_metadata(a, skill_load_total_failure=True)
    record_skill_build_metadata(b, skill_load_total_failure=False)
    assert get_skill_build_metadata(a) == {"skill_load_total_failure": True}
    assert get_skill_build_metadata(b) == {"skill_load_total_failure": False}
