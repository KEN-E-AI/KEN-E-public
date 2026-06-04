"""Unit tests for migrate_ga_split_numerical_analyst.py (AH-149).

Coverage map:
  (a) Dry-run exits 0 without any Firestore I/O.
  (b) Idempotent: running twice leaves the four targeted fields unchanged on
      the second run (values are already correct after the first run).
  (c) Unrelated existing fields on the doc survive untouched.
  (d) The four targeted fields are written with the correct values on a
      first-run against a doc that has the old shape.
  (e) Running against a missing doc (create path) also succeeds.
"""

from __future__ import annotations

import copy
import sys
from unittest.mock import patch

import pytest

from app.adk.agents.scripts import migrate_ga_split_numerical_analyst as script
from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
    _GA_MCP_TOOL_IDS,
    GA_SPECIALIST_INSTRUCTION,
)
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

_COLL = script.AGENT_CONFIGS_COLLECTION
_DOC = script.GA_SPECIALIST_DOC_ID


def _build_fake_db_old_shape() -> FakeFirestoreClient:
    """Pre-seed with the pre-AH-149 GA specialist doc shape."""
    return FakeFirestoreClient(
        stores={
            _COLL: {
                _DOC: {
                    "model": "gemini-2.0-flash",
                    "code_execution_enabled": True,
                    "tool_ids": None,
                    "instruction": "old instruction",
                    # Unrelated fields that must survive.
                    "temperature": 0.2,
                    "reviewer_model": None,
                    "ken_e_sub_agent": True,
                }
            }
        }
    )


def _build_fake_db_new_shape() -> FakeFirestoreClient:
    """Pre-seed with the post-AH-149 GA specialist doc shape (already patched)."""
    return FakeFirestoreClient(
        stores={
            _COLL: {
                _DOC: {
                    "model": "gemini-2.5-flash",
                    "code_execution_enabled": False,
                    "tool_ids": list(_GA_MCP_TOOL_IDS),
                    "instruction": GA_SPECIALIST_INSTRUCTION,
                    "temperature": 0.2,
                    "reviewer_model": None,
                    "ken_e_sub_agent": True,
                }
            }
        }
    )


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    fake_db: FakeFirestoreClient,
    *,
    dry_run: bool = False,
) -> int:
    """Run ``main()`` with the given fake DB via the --project-id flag."""
    argv = ["script", "--project-id", "ken-e-dev"]
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    with patch("google.cloud.firestore.Client", return_value=fake_db):
        return script.main()


# ---------------------------------------------------------------------------
# (a) Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_returns_zero_without_firestore_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--dry-run must exit 0 and never construct a real Firestore client."""
    monkeypatch.setattr(
        sys, "argv", ["script", "--project-id", "ken-e-dev", "--dry-run"]
    )
    firestore_calls: list[bool] = []

    def _never(*args: object, **kwargs: object) -> None:
        firestore_calls.append(True)
        raise AssertionError("Firestore client must not be constructed in --dry-run")

    with patch("google.cloud.firestore.Client", side_effect=_never):
        result = script.main()

    assert result == 0
    assert firestore_calls == []


# ---------------------------------------------------------------------------
# (b) Idempotency
# ---------------------------------------------------------------------------


def test_idempotent_second_run_leaves_values_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running the migration twice must produce the same targeted field values."""
    fake_db = _build_fake_db_old_shape()

    result1 = _run_main(monkeypatch, fake_db)
    assert result1 == 0

    doc_after_first = copy.deepcopy(fake_db.get_doc(_COLL, _DOC))
    assert doc_after_first is not None

    result2 = _run_main(monkeypatch, fake_db)
    assert result2 == 0

    doc_after_second = copy.deepcopy(fake_db.get_doc(_COLL, _DOC))
    assert doc_after_second is not None

    for field in ("model", "code_execution_enabled", "tool_ids", "instruction"):
        assert doc_after_first[field] == doc_after_second[field], (
            f"Field {field!r} changed between first and second run: "
            f"{doc_after_first[field]!r} → {doc_after_second[field]!r}"
        )


# ---------------------------------------------------------------------------
# (c) Unrelated fields survive
# ---------------------------------------------------------------------------


def test_unrelated_fields_preserved_after_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fields not in the four-field patch must survive the migration unchanged."""
    fake_db = _build_fake_db_old_shape()

    _run_main(monkeypatch, fake_db)

    doc = fake_db.get_doc(_COLL, _DOC)
    assert doc is not None
    assert doc["temperature"] == 0.2, "temperature must be preserved"
    assert doc["reviewer_model"] is None, "reviewer_model must be preserved"
    assert doc["ken_e_sub_agent"] is True, "ken_e_sub_agent must be preserved"


# ---------------------------------------------------------------------------
# (d) Correct values written (first run from old shape)
# ---------------------------------------------------------------------------


def test_four_fields_written_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The four targeted fields must have the expected AH-149 values after the migration."""
    fake_db = _build_fake_db_old_shape()

    result = _run_main(monkeypatch, fake_db)
    assert result == 0

    doc = fake_db.get_doc(_COLL, _DOC)
    assert doc is not None

    assert doc["code_execution_enabled"] is False, (
        "code_execution_enabled must be False after migration"
    )
    assert doc["model"] == "gemini-2.5-flash", (
        f"model must be 'gemini-2.5-flash'; got {doc['model']!r}"
    )
    tool_ids = doc["tool_ids"]
    assert isinstance(tool_ids, list), "tool_ids must be a list"
    assert len(tool_ids) == 5, f"tool_ids must have 5 entries; got {len(tool_ids)}"
    assert "agent.numerical_analyst" in tool_ids, (
        "tool_ids must contain 'agent.numerical_analyst'"
    )
    assert sum(1 for t in tool_ids if t.startswith("google_analytics_mcp.")) == 4, (
        "tool_ids must contain 4 google_analytics_mcp.* entries"
    )
    assert doc["instruction"] == GA_SPECIALIST_INSTRUCTION, (
        "instruction must match the GA_SPECIALIST_INSTRUCTION from the seed module"
    )


# ---------------------------------------------------------------------------
# (e) Create path (doc does not exist)
# ---------------------------------------------------------------------------


def test_create_path_succeeds_when_doc_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migration must succeed even when the target doc does not yet exist."""
    fake_db = FakeFirestoreClient()  # empty — no pre-seeded doc

    result = _run_main(monkeypatch, fake_db)
    assert result == 0

    doc = fake_db.get_doc(_COLL, _DOC)
    assert doc is not None, "doc must be created even when it was absent"
    assert doc["code_execution_enabled"] is False
    assert doc["model"] == "gemini-2.5-flash"
