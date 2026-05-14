"""Tests for the shared seed-script helper (AH-41 PR review follow-up).

These tests cover the upsert behavior contract once, so the per-script
test files can focus on matrix snapshots of each agent's *_CONFIG dict
without re-asserting create / update / idempotency / dry-run / error
paths for every script.
"""

from __future__ import annotations

import logging

import pytest

from app.adk.agents.scripts import _seed_helpers
from app.adk.agents.scripts._seed_helpers import (
    AUDIT_FIELDS,
    AUDIT_FIELDS_FORMATTER,
    AUDIT_FIELDS_RESEARCHER,
    AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER,
    AUDIT_FIELDS_USER_FACING_RESEARCHER,
    upsert_agent_config,
)
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

# ---------------------------------------------------------------------------
# Profile constants — matrix invariants
# ---------------------------------------------------------------------------


def test_audit_fields_tuple_has_eight_fields() -> None:
    assert len(AUDIT_FIELDS) == 8


def test_user_facing_researcher_profile_has_all_audit_fields_and_nothing_else() -> None:
    assert set(AUDIT_FIELDS_USER_FACING_RESEARCHER.keys()) == set(AUDIT_FIELDS)


def test_strategy_pipeline_researcher_profile_has_all_audit_fields_and_nothing_else() -> (
    None
):
    assert set(AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER.keys()) == set(AUDIT_FIELDS)


def test_formatter_profile_has_all_audit_fields_and_nothing_else() -> None:
    assert set(AUDIT_FIELDS_FORMATTER.keys()) == set(AUDIT_FIELDS)


def test_user_facing_researcher_profile_is_visible_and_copyable() -> None:
    """User-facing researchers (chatbot, news, GA) are picker-driven."""
    assert AUDIT_FIELDS_USER_FACING_RESEARCHER["available_to_copy"] is True
    assert AUDIT_FIELDS_USER_FACING_RESEARCHER["visible_in_frontend"] is True
    assert AUDIT_FIELDS_USER_FACING_RESEARCHER["automatically_available"] is True


def test_strategy_pipeline_researcher_profile_is_hidden_and_not_copyable() -> None:
    """AH-PRD-08: the 4 strategy-pipeline researchers (business /
    competitive / marketing / brand) are account-creation-only and
    constructed via a legacy loader that ignores picker selections, so
    they're hidden from the Workflows UI to avoid offering a
    configuration surface that has no effect."""
    assert AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER["available_to_copy"] is False
    assert AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER["visible_in_frontend"] is False
    assert AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER["automatically_available"] is True


def test_researcher_alias_points_at_user_facing_profile() -> None:
    """``AUDIT_FIELDS_RESEARCHER`` is kept as a deprecation alias for one
    release so existing user-facing migration scripts (chatbot, news,
    GA) keep importing cleanly. The alias must resolve to the explicit
    user-facing profile."""
    assert AUDIT_FIELDS_RESEARCHER is AUDIT_FIELDS_USER_FACING_RESEARCHER


def test_formatter_profile_is_hidden_and_not_copyable() -> None:
    """Formatters are internal review-loop stages: hidden + non-copyable."""
    assert AUDIT_FIELDS_FORMATTER["available_to_copy"] is False
    assert AUDIT_FIELDS_FORMATTER["visible_in_frontend"] is False
    assert AUDIT_FIELDS_FORMATTER["automatically_available"] is True


# ---------------------------------------------------------------------------
# upsert_agent_config — create / update / idempotency
# ---------------------------------------------------------------------------


def test_upsert_creates_doc_when_missing() -> None:
    fake = FakeFirestoreClient()
    full_config = {
        "name": "test_agent",
        "model": "gemini-2.5-pro",
        "instruction": "You are a test agent.",
        **AUDIT_FIELDS_RESEARCHER,
    }
    ok = upsert_agent_config(full_config, "test_agent", "test-project", db=fake)
    assert ok is True
    doc = fake.get_doc("agent_configs", "test_agent")
    assert doc is not None
    for field in AUDIT_FIELDS:
        assert field in doc
    assert doc["model"] == "gemini-2.5-pro"


def test_upsert_merges_into_existing_doc_preserving_extras() -> None:
    """merge=True writes seed keys, leaves other keys intact."""
    fake = FakeFirestoreClient(
        stores={
            "agent_configs": {
                "test_agent": {
                    "name": "test_agent",
                    "model": "gemini-2.0-flash",  # legacy
                    "instruction": "legacy",
                    "temperature": 0.5,
                    "ad_hoc_admin_ui_field": "preserved",
                }
            }
        }
    )
    seed = {
        "model": "gemini-2.5-pro",  # overwrites legacy
        **AUDIT_FIELDS_RESEARCHER,
    }
    ok = upsert_agent_config(seed, "test_agent", "test-project", db=fake)
    assert ok is True
    doc = fake.get_doc("agent_configs", "test_agent")
    assert doc is not None
    # Seed keys overwritten.
    assert doc["model"] == "gemini-2.5-pro"
    for field in AUDIT_FIELDS:
        assert field in doc
    # Out-of-band field preserved (not in seed dict).
    assert doc["ad_hoc_admin_ui_field"] == "preserved"
    # Pre-existing fields not in seed dict preserved.
    assert doc["instruction"] == "legacy"
    assert doc["temperature"] == 0.5


def test_upsert_is_idempotent_across_two_runs() -> None:
    fake = FakeFirestoreClient()
    config = {"name": "test_agent", **AUDIT_FIELDS_RESEARCHER}
    upsert_agent_config(config, "test_agent", "test-project", db=fake)
    first = fake.get_doc("agent_configs", "test_agent")
    upsert_agent_config(config, "test_agent", "test-project", db=fake)
    second = fake.get_doc("agent_configs", "test_agent")
    assert first == second


# ---------------------------------------------------------------------------
# Dry-run and error paths
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write() -> None:
    fake = FakeFirestoreClient()
    ok = upsert_agent_config(
        {"name": "test_agent", **AUDIT_FIELDS_RESEARCHER},
        "test_agent",
        "test-project",
        db=fake,
        dry_run=True,
    )
    assert ok is True
    assert fake.get_doc("agent_configs", "test_agent") is None


def test_upsert_returns_false_on_firestore_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the lazy firestore.Client construction fails, return False."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated firestore failure")

    # Patch the firestore.Client used inside upsert_agent_config when db
    # is None. The helper does the import lazily so we patch the module
    # via monkeypatch on google.cloud.firestore.Client.
    from google.cloud import firestore

    monkeypatch.setattr(firestore, "Client", _boom)

    ok = upsert_agent_config(
        {"name": "test_agent", **AUDIT_FIELDS_RESEARCHER},
        "test_agent",
        "test-project",
    )
    assert ok is False


# ---------------------------------------------------------------------------
# Sparse-doc warning on clean-env create
# ---------------------------------------------------------------------------


def test_sparse_audit_only_seed_warns_when_creating(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Creating a new doc whose keys are a subset of AUDIT_FIELDS should
    emit a warning — this guards the 6 audit-fields-only entries in
    upload_baseline_configs.py against accidental clean-env runs that
    would produce un-bootable sparse docs."""
    fake = FakeFirestoreClient()
    with caplog.at_level(logging.WARNING, logger=_seed_helpers.__name__):
        ok = upsert_agent_config(
            dict(AUDIT_FIELDS_RESEARCHER),
            "missing_agent",
            "test-project",
            db=fake,
        )
    assert ok is True
    sparse_warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "sparse" in r.getMessage().lower()
    ]
    assert len(sparse_warnings) == 1, (
        "Sparse-doc warning must fire exactly once when creating a doc "
        f"with only audit fields. Got: {[r.getMessage() for r in caplog.records]}"
    )


def test_sparse_warning_does_not_fire_when_doc_already_exists(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Updating an existing doc with audit-fields-only must NOT warn.
    This is the AH-41 happy path: live envs already have full docs and
    we're just adding the 8 audit fields."""
    fake = FakeFirestoreClient(
        stores={
            "agent_configs": {
                "existing_agent": {
                    "name": "existing_agent",
                    "model": "gemini-2.5-pro",
                    "instruction": "existing live instruction",
                }
            }
        }
    )
    with caplog.at_level(logging.WARNING, logger=_seed_helpers.__name__):
        upsert_agent_config(
            dict(AUDIT_FIELDS_RESEARCHER),
            "existing_agent",
            "test-project",
            db=fake,
        )
    sparse_warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "sparse" in r.getMessage().lower()
    ]
    assert sparse_warnings == []


def test_sparse_warning_does_not_fire_for_full_config(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Creating a full config (with model + instruction + audit fields)
    must NOT warn — only audit-fields-only seeds should trigger it."""
    fake = FakeFirestoreClient()
    full = {
        "name": "full_agent",
        "model": "gemini-2.5-pro",
        "instruction": "full instruction",
        **AUDIT_FIELDS_RESEARCHER,
    }
    with caplog.at_level(logging.WARNING, logger=_seed_helpers.__name__):
        upsert_agent_config(full, "full_agent", "test-project", db=fake)
    sparse_warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "sparse" in r.getMessage().lower()
    ]
    assert sparse_warnings == []
