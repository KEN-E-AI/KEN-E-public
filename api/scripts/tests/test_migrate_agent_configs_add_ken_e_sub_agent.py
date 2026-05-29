"""Unit tests for api/scripts/migrate_agent_configs_add_ken_e_sub_agent.py.

Pure-logic and fake-Firestore tests covering:
- _needs_ken_e_sub_agent_backfill — idempotency predicate
- _is_unlisted_formatter — pre-flight enumeration helper
- backfill (integration-style, no real Firestore) — end-to-end count semantics
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api.scripts.migrate_agent_configs_add_ken_e_sub_agent import (
    STRATEGY_PIPELINE_AGENTS,
    _is_unlisted_formatter,
    _needs_ken_e_sub_agent_backfill,
    backfill,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self.exists = data is not None
        self._data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeDocRef:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data
        self.update = MagicMock()

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id, self._data)


class _FakeCollection:
    def __init__(self, docs: dict[str, dict[str, Any] | None]) -> None:
        self._docs = docs
        self._refs: dict[str, _FakeDocRef] = {
            doc_id: _FakeDocRef(doc_id, data) for doc_id, data in docs.items()
        }

    def document(self, doc_id: str) -> _FakeDocRef:
        if doc_id not in self._refs:
            # Simulate a missing doc: exists=False on get()
            self._refs[doc_id] = _FakeDocRef(doc_id, None)
        return self._refs[doc_id]

    def stream(self) -> list[_FakeSnapshot]:
        return [
            _FakeSnapshot(d, self._docs[d])
            for d in self._docs
            if self._docs[d] is not None
        ]


class FakeMigrateDb:
    """In-memory Firestore stand-in for migration tests."""

    def __init__(self, agent_docs: dict[str, dict[str, Any] | None]) -> None:
        """``agent_docs`` maps doc_id → Firestore data (or None for missing)."""
        self._col = _FakeCollection(agent_docs)

    def collection(self, name: str) -> _FakeCollection:
        assert name == "agent_configs"
        return self._col


# ---------------------------------------------------------------------------
# Tests: _needs_ken_e_sub_agent_backfill
# ---------------------------------------------------------------------------


class TestNeedsKenESubAgentBackfill:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            ({}, True),  # field absent → needs patch
            ({"ken_e_sub_agent": None}, True),  # explicit None → needs patch
            ({"ken_e_sub_agent": True}, True),  # True → needs patch (set to False)
            ({"ken_e_sub_agent": False}, False),  # already False → unchanged
        ],
    )
    def test_parametrized(self, doc: dict[str, Any], expected: bool) -> None:
        assert _needs_ken_e_sub_agent_backfill(doc) is expected


# ---------------------------------------------------------------------------
# Tests: _is_unlisted_formatter
# ---------------------------------------------------------------------------


class TestIsUnlistedFormatter:
    def test_unlisted_formatter_returns_true(self) -> None:
        assert _is_unlisted_formatter("news_formatter") is True

    def test_listed_formatter_returns_false(self) -> None:
        """Strategy-pipeline formatters are in the explicit list and must not be flagged."""
        assert _is_unlisted_formatter("business_formatter") is False
        assert _is_unlisted_formatter("competitive_formatter") is False

    def test_non_formatter_returns_false(self) -> None:
        assert _is_unlisted_formatter("google_analytics_agent") is False
        assert _is_unlisted_formatter("business_researcher") is False

    def test_formatter_suffix_required(self) -> None:
        assert _is_unlisted_formatter("formatter_prefix") is False


# ---------------------------------------------------------------------------
# Tests: STRATEGY_PIPELINE_AGENTS constant
# ---------------------------------------------------------------------------


class TestStrategyPipelineAgents:
    def test_contains_all_eight_agents(self) -> None:
        expected = {
            "business_researcher",
            "business_formatter",
            "competitive_researcher",
            "competitive_formatter",
            "marketing_researcher",
            "marketing_formatter",
            "brand_researcher",
            "brand_formatter",
        }
        assert set(STRATEGY_PIPELINE_AGENTS) == expected


# ---------------------------------------------------------------------------
# Tests: backfill (end-to-end with FakeMigrateDb)
# ---------------------------------------------------------------------------


def _all_strategy_docs(
    extra: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, dict[str, Any] | None]:
    """Build a doc map with all 8 strategy agents having the given value + any extras."""
    docs: dict[str, dict[str, Any] | None] = {}
    for agent_id in STRATEGY_PIPELINE_AGENTS:
        docs[agent_id] = {
            "instruction": f"{agent_id} instruction.",
            "model": "gemini-2.5-pro",
        }
    if extra:
        docs.update(extra)
    return docs


class TestBackfill:
    def test_all_absent_fields_are_patched(self) -> None:
        """All 8 strategy-pipeline agents lacking ken_e_sub_agent are patched."""
        db = FakeMigrateDb(_all_strategy_docs())
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 8
        assert counts["unchanged"] == 0
        assert counts["missing"] == 0
        assert counts["errors"] == 0
        # Verify the actual write on one agent
        db.collection("agent_configs").document(
            "business_formatter"
        ).update.assert_called_once_with({"ken_e_sub_agent": False})

    def test_already_false_is_unchanged(self) -> None:
        """A doc with ken_e_sub_agent=False already is not rewritten."""
        docs = {
            agent: {
                "instruction": "x.",
                "model": "gemini-2.5-pro",
                "ken_e_sub_agent": False,
            }
            for agent in STRATEGY_PIPELINE_AGENTS
        }
        db = FakeMigrateDb(docs)
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {
            "patched": 0,
            "would_patch": 0,
            "unchanged": 8,
            "missing": 0,
            "errors": 0,
        }
        for agent_id in STRATEGY_PIPELINE_AGENTS:
            db.collection("agent_configs").document(agent_id).update.assert_not_called()

    def test_explicit_true_is_patched(self) -> None:
        """A doc with ken_e_sub_agent=True still needs patching."""
        docs = {
            "business_formatter": {
                "instruction": "x.",
                "model": "gemini-2.5-pro",
                "ken_e_sub_agent": True,
            }
        }
        # Remaining 7 have no field (also need patching)
        for agent_id in STRATEGY_PIPELINE_AGENTS:
            if agent_id not in docs:
                docs[agent_id] = {"instruction": "x.", "model": "gemini-2.5-pro"}
        db = FakeMigrateDb(docs)
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 8
        db.collection("agent_configs").document(
            "business_formatter"
        ).update.assert_called_once_with({"ken_e_sub_agent": False})

    def test_dry_run_increments_would_patch_not_patched(self) -> None:
        """Dry run must log intent but not write."""
        db = FakeMigrateDb(_all_strategy_docs())
        counts = backfill("proj", dry_run=True, db=db)
        assert counts["would_patch"] == 8
        assert counts["patched"] == 0
        for agent_id in STRATEGY_PIPELINE_AGENTS:
            db.collection("agent_configs").document(agent_id).update.assert_not_called()

    def test_missing_doc_increments_missing_counter_not_error(self) -> None:
        """A doc that doesn't exist in Firestore goes to missing, not errors."""
        # Only populate one of the 8 agents; the rest are missing.
        docs: dict[str, dict[str, Any] | None] = {
            "business_researcher": {"instruction": "x.", "model": "gemini-2.5-pro"}
        }
        # The FakeMigrateDb returns exists=False for any doc_id not in the dict.
        for agent_id in STRATEGY_PIPELINE_AGENTS:
            if agent_id not in docs:
                docs[agent_id] = None
        db = FakeMigrateDb(docs)
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["missing"] == 7
        assert counts["errors"] == 0

    def test_update_failure_increments_errors(self) -> None:
        """A Firestore write failure increments errors without crashing."""
        db = FakeMigrateDb(_all_strategy_docs())
        failing_ref = db.collection("agent_configs").document("business_formatter")
        failing_ref.update.side_effect = RuntimeError("Firestore unavailable")

        counts = backfill("proj", dry_run=False, db=db)
        assert counts["errors"] == 1
        assert counts["patched"] == 7  # the other 7 still succeed

    def test_idempotent_second_run(self) -> None:
        """Re-running on already-migrated collection produces zero writes."""
        docs = {
            agent: {
                "instruction": "x.",
                "model": "gemini-2.5-pro",
                "ken_e_sub_agent": False,
            }
            for agent in STRATEGY_PIPELINE_AGENTS
        }
        db = FakeMigrateDb(docs)
        # First run
        counts1 = backfill("proj", dry_run=False, db=db)
        assert counts1["unchanged"] == 8
        # No writes on second run either (all still False)
        counts2 = backfill("proj", dry_run=False, db=db)
        assert counts2["unchanged"] == 8
        assert counts2["patched"] == 0

    def test_enumerate_other_formatters_no_side_effects_on_counts(self) -> None:
        """enumerate_other_formatters=True logs but does not alter patch counts."""
        docs = _all_strategy_docs(
            extra={
                "news_formatter": {"instruction": "news.", "model": "gemini-2.5-pro"}
            }
        )
        db = FakeMigrateDb(docs)
        counts = backfill(
            "proj",
            dry_run=True,
            db=db,
            enumerate_other_formatters=True,
        )
        # Only the 8 strategy agents are counted; news_formatter is listed but not patched.
        assert counts["would_patch"] == 8
        assert counts["patched"] == 0
        # news_formatter's update is NOT called (enumerate mode is read-only)
        db.collection("agent_configs").document(
            "news_formatter"
        ).update.assert_not_called()
