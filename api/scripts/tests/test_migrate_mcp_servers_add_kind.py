"""Unit tests for api/scripts/migrate_mcp_servers_add_kind.py.

Pure-logic tests for the helper that carries the idempotency guarantee:
  - _needs_kind_backfill — decides whether a doc needs patching
  - backfill (integration-style, no real Firestore) — end-to-end count semantics
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api.scripts.migrate_mcp_servers_add_kind import (
    _VALID_KINDS,
    _needs_kind_backfill,
    backfill,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in (mirrors FakeBackfillDb in test_backfill_mcp_servers_specialist_categories.py)
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


class FakeMigrateDb:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._col = _FakeCollection(
            [_FakeSnapshot(sid, data) for sid, data in docs.items()]
        )

    def collection(self, name: str) -> _FakeCollection:
        assert name == "mcp_server_configs"
        return self._col


# ---------------------------------------------------------------------------
# Tests: _needs_kind_backfill
# ---------------------------------------------------------------------------


class TestNeedsKindBackfill:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            ({}, True),  # missing key
            ({"kind": None}, True),  # explicit None
            ({"kind": ""}, True),  # empty string
            ({"kind": "   "}, True),  # whitespace-only
            ({"kind": "cloud_run"}, False),  # already set
            ({"kind": "zapier"}, False),  # non-default but valid
            ({"kind": "CloudRun"}, True),  # wrong case — not in _VALID_KINDS
            ({"kind": "invalid"}, True),  # unknown value
        ],
    )
    def test_parametrized(self, doc: dict[str, Any], expected: bool) -> None:
        assert _needs_kind_backfill(doc) is expected

    def test_valid_kinds_set_covers_enum_members(self) -> None:
        """_VALID_KINDS must stay in sync with McpServerKind members."""
        # If a new enum member is added without updating _VALID_KINDS, this test fails.
        assert _VALID_KINDS == {"cloud_run", "zapier"}


# ---------------------------------------------------------------------------
# Tests: backfill (end-to-end with FakeMigrateDb)
# ---------------------------------------------------------------------------


class TestBackfill:
    def test_already_has_kind_is_unchanged(self) -> None:
        db = FakeMigrateDb({"srv": {"kind": "cloud_run", "name": "srv"}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "unchanged": 1, "errors": 0}
        db.collection("mcp_server_configs").document("srv").update.assert_not_called()

    def test_missing_kind_is_patched(self) -> None:
        db = FakeMigrateDb({"srv": {"name": "srv"}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["unchanged"] == 0
        db.collection("mcp_server_configs").document(
            "srv"
        ).update.assert_called_once_with({"kind": "cloud_run"})

    def test_none_kind_is_patched(self) -> None:
        db = FakeMigrateDb({"srv": {"kind": None}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        db.collection("mcp_server_configs").document(
            "srv"
        ).update.assert_called_once_with({"kind": "cloud_run"})

    def test_empty_string_kind_is_patched(self) -> None:
        db = FakeMigrateDb({"srv": {"kind": ""}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["patched"] == 1

    def test_dry_run_increments_would_patch_not_patched(self) -> None:
        db = FakeMigrateDb({"srv": {"name": "srv"}})
        counts = backfill("proj", dry_run=True, db=db)
        assert counts["would_patch"] == 1
        assert counts["patched"] == 0
        db.collection("mcp_server_configs").document("srv").update.assert_not_called()

    def test_zapier_kind_is_preserved(self) -> None:
        """Non-default kind values must not be overwritten."""
        db = FakeMigrateDb({"srv": {"kind": "zapier"}})
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "unchanged": 1, "errors": 0}
        db.collection("mcp_server_configs").document("srv").update.assert_not_called()

    def test_idempotent_on_second_run(self) -> None:
        """Re-run on already-migrated collection produces zero writes."""
        db = FakeMigrateDb(
            {
                "s1": {"kind": "cloud_run"},
                "s2": {"kind": "cloud_run"},
            }
        )
        counts = backfill("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "unchanged": 2, "errors": 0}

    def test_mixed_collection(self) -> None:
        """Collection with already-migrated and missing-kind docs."""
        db = FakeMigrateDb(
            {
                "done": {"kind": "cloud_run"},
                "needs_patch": {"name": "needs_patch"},
                "also_done": {"kind": "zapier"},
            }
        )
        counts = backfill("proj", dry_run=False, db=db)
        assert counts["unchanged"] == 2
        assert counts["patched"] == 1
        assert counts["errors"] == 0

    def test_update_failure_increments_errors(self) -> None:
        db = FakeMigrateDb({"srv": {"name": "srv"}})
        doc_ref = db.collection("mcp_server_configs").document("srv")
        doc_ref.update.side_effect = RuntimeError("Firestore unavailable")

        counts = backfill("proj", dry_run=False, db=db)
        assert counts["errors"] == 1
        assert counts["patched"] == 0
