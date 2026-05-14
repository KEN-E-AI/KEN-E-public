"""Unit tests for api/scripts/migrate_strategy_pipeline_visibility.py (AH-PRD-08).

Pure-logic tests for ``_fields_needing_patch`` plus integration-style
tests for ``migrate`` against an in-memory Firestore stand-in. The stand-in
mirrors the pattern used in ``test_migrate_agent_config_flags.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api.scripts.migrate_strategy_pipeline_visibility import (
    FIELDS_TO_HIDE,
    STRATEGY_PIPELINE_RESEARCHERS,
    _fields_needing_patch,
    migrate,
)

# ---------------------------------------------------------------------------
# Fake Firestore stand-in
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, exists: bool, data: dict[str, Any]) -> None:
        self.id = doc_id
        self.exists = exists
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeDocRef:
    def __init__(self, doc_id: str, store: dict[str, dict[str, Any]]) -> None:
        self._doc_id = doc_id
        self._store = store

        def _write_back(patch: dict[str, Any]) -> None:
            self._store.setdefault(self._doc_id, {}).update(patch)

        self.update = MagicMock(side_effect=_write_back)

    def get(self) -> _FakeSnapshot:
        exists = self._doc_id in self._store
        return _FakeSnapshot(self._doc_id, exists, self._store.get(self._doc_id, {}))


class _FakeCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store
        self._refs: dict[str, _FakeDocRef] = {}

    def document(self, doc_id: str) -> _FakeDocRef:
        if doc_id not in self._refs:
            self._refs[doc_id] = _FakeDocRef(doc_id, self._store)
        return self._refs[doc_id]


class FakeMigrateDb:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self._store = dict(docs)
        self._col = _FakeCollection(self._store)

    def collection(self, name: str) -> _FakeCollection:
        assert name == "agent_configs"
        return self._col


# ---------------------------------------------------------------------------
# Pure-logic: _fields_needing_patch
# ---------------------------------------------------------------------------


class TestFieldsNeedingPatch:
    @pytest.mark.parametrize(
        "doc, expected",
        [
            # Both flags absent
            ({}, list(FIELDS_TO_HIDE)),
            # Both flags True (the "before" state on already-deployed dev/staging/prod)
            (
                {"visible_in_frontend": True, "available_to_copy": True},
                list(FIELDS_TO_HIDE),
            ),
            # Both flags False (the "after" state — already migrated)
            (
                {"visible_in_frontend": False, "available_to_copy": False},
                [],
            ),
            # Mixed state — only one flag needs flipping
            (
                {"visible_in_frontend": False, "available_to_copy": True},
                ["available_to_copy"],
            ),
            # ``None`` is treated as needing patch
            (
                {"visible_in_frontend": None, "available_to_copy": False},
                ["visible_in_frontend"],
            ),
        ],
    )
    def test_parametrized(self, doc: dict[str, Any], expected: list[str]) -> None:
        assert _fields_needing_patch(doc) == expected


# ---------------------------------------------------------------------------
# Integration: migrate
# ---------------------------------------------------------------------------


def _all_visible_state() -> dict[str, dict[str, Any]]:
    """Seed every researcher doc in the pre-AH-PRD-08 (visible) state."""
    return {
        doc_id: {
            "name": doc_id,
            "model": "gemini-2.5-pro",
            "instruction": "existing",
            "visible_in_frontend": True,
            "available_to_copy": True,
        }
        for doc_id in STRATEGY_PIPELINE_RESEARCHERS
    }


class TestMigrate:
    def test_pre_ahprd08_state_patches_all_four_docs(self) -> None:
        db = FakeMigrateDb(_all_visible_state())
        counts = migrate("proj", dry_run=False, db=db)
        assert counts == {
            "patched": 4,
            "would_patch": 0,
            "unchanged": 0,
            "missing": 0,
            "errors": 0,
        }
        for doc_id in STRATEGY_PIPELINE_RESEARCHERS:
            ref = db.collection("agent_configs").document(doc_id)
            ref.update.assert_called_once_with(
                {"visible_in_frontend": False, "available_to_copy": False}
            )

    def test_already_migrated_state_is_unchanged(self) -> None:
        db = FakeMigrateDb(
            {
                doc_id: {
                    "name": doc_id,
                    "visible_in_frontend": False,
                    "available_to_copy": False,
                }
                for doc_id in STRATEGY_PIPELINE_RESEARCHERS
            }
        )
        counts = migrate("proj", dry_run=False, db=db)
        assert counts == {
            "patched": 0,
            "would_patch": 0,
            "unchanged": 4,
            "missing": 0,
            "errors": 0,
        }
        for doc_id in STRATEGY_PIPELINE_RESEARCHERS:
            db.collection("agent_configs").document(doc_id).update.assert_not_called()

    def test_dry_run_increments_would_patch_and_writes_nothing(self) -> None:
        db = FakeMigrateDb(_all_visible_state())
        counts = migrate("proj", dry_run=True, db=db)
        assert counts["would_patch"] == 4
        assert counts["patched"] == 0
        for doc_id in STRATEGY_PIPELINE_RESEARCHERS:
            db.collection("agent_configs").document(doc_id).update.assert_not_called()

    def test_idempotent_on_second_run(self) -> None:
        """Re-running on a partially migrated db converges and then stays put."""
        db = FakeMigrateDb(_all_visible_state())

        first = migrate("proj", dry_run=False, db=db)
        assert first["patched"] == 4

        # The fake's update side-effect wrote patches back into the store,
        # so the second migration sees correct values.
        second = migrate("proj", dry_run=False, db=db)
        assert second == {
            "patched": 0,
            "would_patch": 0,
            "unchanged": 4,
            "missing": 0,
            "errors": 0,
        }

    def test_partial_migration_patches_only_remaining_flags(self) -> None:
        """One doc has visible_in_frontend=False but available_to_copy=True;
        the script flips only the latter."""
        db = FakeMigrateDb(
            {
                "business_researcher": {
                    "name": "business_researcher",
                    "visible_in_frontend": False,
                    "available_to_copy": True,
                },
                "competitive_researcher": {
                    "name": "competitive_researcher",
                    "visible_in_frontend": False,
                    "available_to_copy": False,
                },
                "marketing_researcher": {
                    "name": "marketing_researcher",
                    "visible_in_frontend": False,
                    "available_to_copy": False,
                },
                "brand_researcher": {
                    "name": "brand_researcher",
                    "visible_in_frontend": False,
                    "available_to_copy": False,
                },
            }
        )
        counts = migrate("proj", dry_run=False, db=db)
        assert counts["patched"] == 1
        assert counts["unchanged"] == 3
        # Only the one stale flag is in the patch — visible_in_frontend stays False.
        db.collection("agent_configs").document(
            "business_researcher"
        ).update.assert_called_once_with({"available_to_copy": False})

    def test_missing_doc_counts_as_missing_not_error(self) -> None:
        """An environment that hasn't run upload_baseline_configs.py yet
        has no docs to patch. That's a non-fatal signal, not an error."""
        db = FakeMigrateDb({})
        counts = migrate("proj", dry_run=False, db=db)
        assert counts["missing"] == 4
        assert counts["errors"] == 0
        assert counts["patched"] == 0

    def test_update_failure_increments_errors(self) -> None:
        db = FakeMigrateDb(_all_visible_state())
        doc_ref = db.collection("agent_configs").document("business_researcher")
        doc_ref.update.side_effect = RuntimeError("Firestore unavailable")

        counts = migrate("proj", dry_run=False, db=db)
        assert counts["errors"] == 1
        # The other three docs still get patched.
        assert counts["patched"] == 3
