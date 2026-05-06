"""Unit tests for api/scripts/backfill_mcp_servers_specialist_categories.py.

Pure-logic tests for the three helpers that carry the idempotency guarantee:
  - _needs_backfill  — decides whether a doc needs patching
  - _derive_categories — derives the backfill value from 'category'
  - backfill (integration-style, no real Firestore) — end-to-end count semantics
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import helpers from the script (importable as a module)
# ---------------------------------------------------------------------------
from api.scripts.backfill_mcp_servers_specialist_categories import (
    _derive_categories,
    _needs_backfill,
    backfill,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in (same pattern as FakeMCPDb in test_mcp.py)
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeDoc:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id
        self.update = MagicMock()


class _FakeCollection:
    def __init__(self, snapshots: list[_FakeSnapshot]) -> None:
        self._snapshots = snapshots
        self._docs: dict[str, _FakeDoc] = {s.id: _FakeDoc(s.id) for s in snapshots}

    def stream(self) -> list[_FakeSnapshot]:
        return list(self._snapshots)

    def document(self, doc_id: str) -> _FakeDoc:
        if doc_id not in self._docs:
            self._docs[doc_id] = _FakeDoc(doc_id)
        return self._docs[doc_id]


class FakeBackfillDb:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._col = _FakeCollection(
            [_FakeSnapshot(sid, data) for sid, data in docs.items()]
        )

    def collection(self, name: str) -> _FakeCollection:
        assert name == "mcp_server_configs"
        return self._col


# ---------------------------------------------------------------------------
# Tests: _needs_backfill
# ---------------------------------------------------------------------------


class TestNeedsBackfill:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            ({}, True),  # missing key
            ({"specialist_categories": None}, True),  # explicit None
            ({"specialist_categories": []}, True),  # empty list
            ({"specialist_categories": ["google_analytics"]}, False),  # already set
            ({"specialist_categories": ["a", "b"]}, False),  # multiple categories
        ],
    )
    def test_parametrized(self, doc: dict[str, Any], expected: bool) -> None:
        assert _needs_backfill(doc) is expected


# ---------------------------------------------------------------------------
# Tests: _derive_categories
# ---------------------------------------------------------------------------


class TestDeriveCategories:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            ({"category": "google_analytics"}, ["google_analytics"]),  # normal
            ({"category": "  google_ads  "}, ["google_ads"]),  # strips whitespace
            ({"category": ""}, None),  # empty string → skip
            ({"category": "   "}, None),  # whitespace-only → skip
            ({"category": None}, None),  # None → skip
            ({"category": 123}, None),  # non-string → skip
            ({}, None),  # missing key → skip
        ],
    )
    def test_parametrized(
        self, doc: dict[str, Any], expected: list[str] | None
    ) -> None:
        assert _derive_categories(doc) == expected


# ---------------------------------------------------------------------------
# Tests: backfill (end-to-end with FakeBackfillDb)
# ---------------------------------------------------------------------------


class TestBackfill:
    def test_already_has_categories_is_unchanged(self) -> None:
        db = FakeBackfillDb(
            {"srv": {"specialist_categories": ["google_analytics"], "category": "google_analytics"}}
        )
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "skipped": 0, "unchanged": 1, "errors": 0}
        db.collection("mcp_server_configs").document("srv").update.assert_not_called()

    def test_missing_categories_with_category_field_is_patched(self) -> None:
        db = FakeBackfillDb({"srv": {"category": "google_ads"}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["unchanged"] == 0
        db.collection("mcp_server_configs").document("srv").update.assert_called_once_with(
            {"specialist_categories": ["google_ads"]}
        )

    def test_dry_run_increments_would_patch_not_patched(self) -> None:
        db = FakeBackfillDb({"srv": {"category": "google_analytics"}})
        counts = backfill("proj", dry_run=True, db=db)
        assert counts["would_patch"] == 1
        assert counts["patched"] == 0
        db.collection("mcp_server_configs").document("srv").update.assert_not_called()

    def test_missing_both_fields_is_skipped(self) -> None:
        db = FakeBackfillDb({"srv": {"name": "some_server"}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["skipped"] == 1
        assert counts["patched"] == 0

    def test_idempotent_on_second_run(self) -> None:
        """Re-run on already-migrated collection produces zero writes."""
        db = FakeBackfillDb(
            {
                "s1": {"specialist_categories": ["google_analytics"]},
                "s2": {"specialist_categories": ["google_ads"]},
            }
        )
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "skipped": 0, "unchanged": 2, "errors": 0}

    def test_mixed_collection(self) -> None:
        """Collection with already-migrated, backfillable, and un-backfillable docs."""
        db = FakeBackfillDb(
            {
                "done": {"specialist_categories": ["ga"]},
                "needs_patch": {"category": "google_ads"},
                "no_data": {"name": "mystery"},
            }
        )
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["unchanged"] == 1
        assert counts["patched"] == 1
        assert counts["skipped"] == 1
        assert counts["errors"] == 0

    def test_update_failure_increments_errors(self) -> None:
        db = FakeBackfillDb({"srv": {"category": "google_ads"}})
        doc_ref = db.collection("mcp_server_configs").document("srv")
        doc_ref.update.side_effect = RuntimeError("Firestore unavailable")

        counts = backfill("proj", dry_run=False, db=db)
        assert counts["errors"] == 1
        assert counts["patched"] == 0
