"""Unit tests for api/scripts/migrate_agent_config_flags.py.

Pure-logic tests for the helpers that carry the idempotency guarantee:
  - _missing_flags  — decides which flags need to be patched
  - _default_for_flag — always returns True
  - migrate (integration-style, no real Firestore) — end-to-end count semantics
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import helpers from the script (importable as a module)
# ---------------------------------------------------------------------------
from api.scripts.migrate_agent_config_flags import (
    FLAGS,
    _default_for_flag,
    _missing_flags,
    migrate,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in (same pattern as FakeBackfillDb in
# test_backfill_mcp_servers_specialist_categories.py)
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
        assert name == "agent_configs"
        return self._col


# ---------------------------------------------------------------------------
# Tests: _missing_flags
# ---------------------------------------------------------------------------


class TestMissingFlags:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            # All three flags absent entirely
            ({}, ["available_to_copy", "automatically_available", "visible_in_frontend"]),
            # One flag explicitly None, others are present bools
            (
                {
                    "available_to_copy": None,
                    "automatically_available": True,
                    "visible_in_frontend": True,
                },
                ["available_to_copy"],
            ),
            # All three flags present as bools → nothing missing
            (
                {
                    "available_to_copy": True,
                    "automatically_available": True,
                    "visible_in_frontend": True,
                },
                [],
            ),
            # All three flags present as False bools → still not missing
            (
                {
                    "available_to_copy": False,
                    "automatically_available": False,
                    "visible_in_frontend": False,
                },
                [],
            ),
            # One flag is None, others are True
            (
                {
                    "available_to_copy": True,
                    "automatically_available": None,
                    "visible_in_frontend": True,
                },
                ["automatically_available"],
            ),
        ],
    )
    def test_parametrized(self, doc: dict[str, Any], expected: list[str]) -> None:
        assert _missing_flags(doc) == expected


# ---------------------------------------------------------------------------
# Tests: _default_for_flag
# ---------------------------------------------------------------------------


class TestDefaultForFlag:
    def test_all_flag_names_return_true(self) -> None:
        for flag in FLAGS:
            assert _default_for_flag(flag) is True

    def test_available_to_copy_returns_true(self) -> None:
        assert _default_for_flag("available_to_copy") is True

    def test_automatically_available_returns_true(self) -> None:
        assert _default_for_flag("automatically_available") is True

    def test_visible_in_frontend_returns_true(self) -> None:
        assert _default_for_flag("visible_in_frontend") is True

    def test_arbitrary_string_returns_true(self) -> None:
        assert _default_for_flag("some_other_flag") is True


# ---------------------------------------------------------------------------
# Tests: migrate (end-to-end with FakeMigrateDb)
# ---------------------------------------------------------------------------


class TestMigrate:
    def test_all_flags_present_is_unchanged(self) -> None:
        db = FakeMigrateDb(
            {
                "agent1": {
                    "available_to_copy": True,
                    "automatically_available": False,
                    "visible_in_frontend": True,
                }
            }
        )
        counts = migrate("proj", dry_run=False, db=db)
        assert counts == {"patched": 0, "would_patch": 0, "unchanged": 1, "errors": 0}
        db.collection("agent_configs").document("agent1").update.assert_not_called()

    def test_missing_all_flags_is_patched(self) -> None:
        db = FakeMigrateDb({"agent1": {}})
        counts = migrate("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["unchanged"] == 0
        assert counts["errors"] == 0
        assert counts["would_patch"] == 0
        db.collection("agent_configs").document("agent1").update.assert_called_once_with(
            {
                "available_to_copy": True,
                "automatically_available": True,
                "visible_in_frontend": True,
            }
        )

    def test_dry_run_increments_would_patch_not_patched(self) -> None:
        db = FakeMigrateDb({"agent1": {}})
        counts = migrate("proj", dry_run=True, db=db)
        assert counts["would_patch"] == 1
        assert counts["patched"] == 0
        assert counts["errors"] == 0
        db.collection("agent_configs").document("agent1").update.assert_not_called()

    def test_idempotent_on_second_run(self) -> None:
        """Re-run on already-migrated collection produces zero writes."""
        # First run: patches the doc
        db_first = FakeMigrateDb({"agent1": {}})
        counts_first = migrate("proj", dry_run=False, db=db_first)
        assert counts_first["patched"] == 1

        # Second run: use a fresh db where all flags are already set
        db_second = FakeMigrateDb(
            {
                "agent1": {
                    "available_to_copy": True,
                    "automatically_available": True,
                    "visible_in_frontend": True,
                }
            }
        )
        counts_second = migrate("proj", dry_run=False, db=db_second)
        assert counts_second == {"patched": 0, "would_patch": 0, "unchanged": 1, "errors": 0}
        db_second.collection("agent_configs").document("agent1").update.assert_not_called()

    def test_partial_migration_patches_only_missing_keys(self) -> None:
        """Doc has available_to_copy=False (a valid bool) but missing the other two."""
        db = FakeMigrateDb(
            {"agent1": {"available_to_copy": False}}
        )
        counts = migrate("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["unchanged"] == 0
        # Only the two missing flags should be in the patch; False is preserved
        db.collection("agent_configs").document("agent1").update.assert_called_once_with(
            {
                "automatically_available": True,
                "visible_in_frontend": True,
            }
        )

    def test_update_failure_increments_errors(self) -> None:
        db = FakeMigrateDb({"agent1": {}})
        doc_ref = db.collection("agent_configs").document("agent1")
        doc_ref.update.side_effect = RuntimeError("Firestore unavailable")

        counts = migrate("proj", dry_run=False, db=db)
        assert counts["errors"] == 1
        assert counts["patched"] == 0
