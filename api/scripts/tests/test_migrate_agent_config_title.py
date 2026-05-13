"""Unit tests for ``api/scripts/migrate_agent_config_title.py``.

Pure-logic tests for ``compute_patch`` (carries the idempotency guarantee)
plus an end-to-end pass through ``migrate`` using a tiny in-memory Firestore
stand-in.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from api.scripts.migrate_agent_config_title import (
    _looks_like_snake_case_id,
    _title_case_from_identifier,
    compute_patch,
    migrate,
)

# ---------------------------------------------------------------------------
# Tests: _title_case_from_identifier
# ---------------------------------------------------------------------------


def test_title_case_replaces_underscores_and_capitalises() -> None:
    assert _title_case_from_identifier("business_researcher") == "Business Researcher"


def test_title_case_handles_single_word() -> None:
    assert _title_case_from_identifier("planner") == "Planner"


def test_title_case_passes_through_pre_titled() -> None:
    # No underscores, already pretty: still Title-Cased.
    assert _title_case_from_identifier("Already Nice") == "Already Nice"


# ---------------------------------------------------------------------------
# Tests: _looks_like_snake_case_id
# ---------------------------------------------------------------------------


def test_snake_case_recognised() -> None:
    assert _looks_like_snake_case_id("business_researcher")
    assert _looks_like_snake_case_id("ken_e_chatbot")
    assert _looks_like_snake_case_id("a")


def test_human_strings_not_snake_case() -> None:
    assert not _looks_like_snake_case_id("Dave")
    assert not _looks_like_snake_case_id("Business Researcher")
    assert not _looks_like_snake_case_id("Ken-E")  # hyphen not allowed
    assert not _looks_like_snake_case_id("123_invalid")  # must start with letter


# ---------------------------------------------------------------------------
# Tests: compute_patch
# ---------------------------------------------------------------------------


def test_patch_legacy_doc_with_snake_case_name() -> None:
    """Pre-migration doc: legacy name mirrors config_id, no title."""
    patch = compute_patch("business_researcher", {"name": "business_researcher"})

    assert patch == {"title": "Business Researcher", "name": None}


def test_patch_doc_with_missing_name_and_missing_title() -> None:
    """Edge case: no name at all. Derive title from config_id."""
    patch = compute_patch("competitive_researcher", {})

    assert patch == {"title": "Competitive Researcher"}


def test_patch_preserves_human_set_name() -> None:
    """If the existing name is human-set (not snake_case), keep it."""
    patch = compute_patch("business_researcher", {"name": "Dave"})

    # Title is derived from config_id (not from "Dave"), name preserved.
    assert patch == {"title": "Business Researcher"}


def test_patch_no_op_for_fully_migrated_doc() -> None:
    """Idempotency: title set + null name → no patch."""
    patch = compute_patch(
        "business_researcher",
        {"title": "Business Researcher", "name": None},
    )

    assert patch == {}


def test_patch_no_op_for_human_name_with_title_set() -> None:
    """Idempotency: title set + human name → no patch."""
    patch = compute_patch(
        "business_researcher",
        {"title": "Business Researcher", "name": "Dave"},
    )

    assert patch == {}


def test_patch_clears_snake_case_name_even_when_title_set() -> None:
    """Doc has title already, but stale snake_case name lingers."""
    patch = compute_patch(
        "business_researcher",
        {"title": "Business Researcher", "name": "business_researcher"},
    )

    assert patch == {"name": None}


# ---------------------------------------------------------------------------
# Fake Firestore stand-in for end-to-end ``migrate`` test
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any]) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeDoc:
    def __init__(self, snapshot: _FakeSnapshot) -> None:
        self.id = snapshot.id

        def _write_back(patch: dict[str, Any]) -> None:
            snapshot._data.update(patch)

        self.update = MagicMock(side_effect=_write_back)


class _FakeCollection:
    def __init__(self, snapshots: list[_FakeSnapshot]) -> None:
        self._snapshots = snapshots
        self._docs: dict[str, _FakeDoc] = {s.id: _FakeDoc(s) for s in snapshots}

    def stream(self) -> list[_FakeSnapshot]:
        return list(self._snapshots)

    def document(self, doc_id: str) -> _FakeDoc:
        return self._docs[doc_id]

    def list_documents(self) -> list[Any]:
        # Treat snapshots as doc refs with an ``id`` attribute.
        return list(self._snapshots)


class _FakeAccountsCollection:
    """Stand-in for the ``accounts`` collection plus its agent_configs subcols."""

    def __init__(self, per_account: dict[str, dict[str, dict[str, Any]]]) -> None:
        # per_account: { account_id: { config_id: doc_data } }
        self._per_account = per_account
        self._snapshots = [
            _FakeSnapshot(aid, {}) for aid in per_account
        ]
        self._subcols: dict[str, _FakeCollection] = {
            aid: _FakeCollection(
                [_FakeSnapshot(cid, data) for cid, data in cfgs.items()]
            )
            for aid, cfgs in per_account.items()
        }

    def list_documents(self) -> list[Any]:
        return list(self._snapshots)

    def document(self, account_id: str) -> Any:
        outer = self

        class _AccountDocRef:
            def collection(_self, sub: str) -> _FakeCollection:
                assert sub == "agent_configs"
                return outer._subcols[account_id]

        return _AccountDocRef()


class FakeMigrateDb:
    def __init__(
        self,
        globals_: dict[str, dict[str, Any]],
        per_account: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> None:
        self._global_col = _FakeCollection(
            [_FakeSnapshot(sid, data) for sid, data in globals_.items()]
        )
        self._accounts_col = _FakeAccountsCollection(per_account or {})

    def collection(self, name: str) -> Any:
        if name == "agent_configs":
            return self._global_col
        if name == "accounts":
            return self._accounts_col
        raise AssertionError(f"Unexpected collection: {name}")


# ---------------------------------------------------------------------------
# Tests: migrate (end-to-end)
# ---------------------------------------------------------------------------


def test_migrate_dry_run_writes_nothing_and_counts_correctly() -> None:
    db = FakeMigrateDb(
        globals_={
            "business_researcher": {"name": "business_researcher"},
            "competitive_researcher": {"title": "Competitive Researcher", "name": None},
        },
    )

    counts = migrate(project_id="ken-e-dev", dry_run=True, db=db)

    assert counts == {"patched": 0, "would_patch": 1, "unchanged": 1, "errors": 0}


def test_migrate_live_patches_then_is_idempotent() -> None:
    db = FakeMigrateDb(
        globals_={
            "business_researcher": {"name": "business_researcher"},
            "marketing_researcher": {"name": "marketing_researcher"},
        },
        per_account={
            "acc_abc": {
                "custom_abc12345": {"name": "Customer Whisperer"},  # human name
            },
        },
    )

    # First run patches everything.
    first = migrate(project_id="ken-e-dev", dry_run=False, db=db)
    assert first["patched"] == 3
    assert first["unchanged"] == 0
    assert first["errors"] == 0

    # Second run sees the migrated state → zero writes.
    second = migrate(project_id="ken-e-dev", dry_run=False, db=db)
    assert second["patched"] == 0
    assert second["unchanged"] == 3
    assert second["errors"] == 0
