"""Integration tests for migrate_shape_d_split.py against the Firestore emulator.

These tests are skipped by default and only run when ``FIRESTORE_EMULATOR_HOST`` is set:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=ken-e-dev \\
    pytest api/tests/integration/test_migrate_shape_d_split_emulator.py -v

Covers:
  1. AC-5: every migrated accounts/{account_id} doc has organization_id back-reference.
  2. AC-8: re-running the script is a no-op (skipped counts == all accounts).
  3. Risk-5: org-level fields (name, agency, created_at) are byte-identical before/after.
  4. --dry-run: no destination docs are created.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip gate
# ---------------------------------------------------------------------------
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")

pytestmark = pytest.mark.skipif(
    not FIRESTORE_EMULATOR_HOST,
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    """Build a Firestore client pointing to the emulator."""
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _seed_doc(client: Any, collection: str, doc_id: str, data: dict[str, Any]) -> None:
    client.collection(collection).document(doc_id).set(data)


def _get_doc(client: Any, collection: str, doc_id: str) -> dict[str, Any] | None:
    snap = client.collection(collection).document(doc_id).get()
    return snap.to_dict() if snap.exists else None


def _delete_docs(client: Any, collection: str, *doc_ids: str) -> None:
    for doc_id in doc_ids:
        try:
            client.collection(collection).document(doc_id).delete()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def emulator_client() -> Any:
    return _firestore_client()


@pytest.fixture(autouse=True)
def cleanup(emulator_client: Any, run_id: str) -> Generator[None, None, None]:
    """Delete all test-owned docs after each test."""
    # Collect ids during test via run_id suffix convention
    yield
    # Org docs
    _delete_docs(
        emulator_client,
        "organizations",
        f"org_realistic_{run_id}",
        f"org_minimal_{run_id}",
        f"org_full_{run_id}",
        f"org_partial_{run_id}",
    )
    # Account docs that the migration would have written
    _delete_docs(
        emulator_client,
        "accounts",
        f"acc_alpha_{run_id}",
        f"acc_beta_{run_id}",
        f"acc_gamma_{run_id}",
        f"acc_preexisting_{run_id}",
        f"acc_full_{run_id}",
        f"acc_partial_a_{run_id}",
        f"acc_partial_b_{run_id}",
    )


# ---------------------------------------------------------------------------
# Fixtures data builders
# ---------------------------------------------------------------------------


def _realistic_org(run_id: str) -> dict[str, Any]:
    return {
        "name": "Realistic Org",
        "agency": "Acme Agency",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "accounts": {
            f"acc_alpha_{run_id}": {
                "account_settings": {"overview_kpis": {"income_kpi": "m_123"}},
                "funnels": {
                    "organization": {
                        "1": {
                            "name": "Awareness",
                            "channels": {
                                "google_ads": {"tactics": {"paid_search": {}}}
                            },
                        },
                        "2": {"name": "Consideration"},
                    },
                    "big_bets": {
                        "bet_1": {
                            "1": {"name": "Launch"},
                            "2": {"name": "Scale"},
                        },
                    },
                },
            },
            f"acc_beta_{run_id}": {
                "account_settings": {},
                "funnels": {"organization": {"1": {"name": "Awareness"}}},
            },
        },
    }


def _minimal_org(run_id: str) -> dict[str, Any]:
    return {
        "name": "Minimal Org",
        "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "accounts": {
            f"acc_gamma_{run_id}": {
                "account_settings": {},
                "funnels": {},
            },
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_live_run_creates_destination_docs_with_org_backref(
    emulator_client: Any, run_id: str
) -> None:
    """AC-5: every migrated accounts/{account_id} doc has organization_id back-reference.

    Seeds 2 orgs (3 total accounts) plus a pre-existing accounts doc with a
    display_name field.  Runs migration live.  Asserts:
    - Each of the 3 source accounts has a destination doc.
    - organization_id == source org id.
    - account_settings and funnels match source payloads.
    - shape_d_migrated_at is set and is a valid ISO timestamp.
    - The pre-existing display_name on acc_preexisting is preserved if that
      account appears in an org's accounts map (merge=True semantics).
    """
    from migrate_shape_d_split import run_migration

    realistic_id = f"org_realistic_{run_id}"
    minimal_id = f"org_minimal_{run_id}"

    realistic_data = _realistic_org(run_id)
    minimal_data = _minimal_org(run_id)

    # Seed org docs
    _seed_doc(emulator_client, "organizations", realistic_id, realistic_data)
    _seed_doc(emulator_client, "organizations", minimal_id, minimal_data)

    # Seed a pre-existing accounts doc with an unrelated display_name
    # (not in any org's accounts map for this test — just proves unrelated accounts untouched)
    _seed_doc(
        emulator_client,
        "accounts",
        f"acc_preexisting_{run_id}",
        {"display_name": "Pre-existing Account"},
    )

    summary = run_migration(emulator_client, dry_run=False)

    # --- AC-5 assertions ---
    alpha_doc = _get_doc(emulator_client, "accounts", f"acc_alpha_{run_id}")
    beta_doc = _get_doc(emulator_client, "accounts", f"acc_beta_{run_id}")
    gamma_doc = _get_doc(emulator_client, "accounts", f"acc_gamma_{run_id}")

    assert alpha_doc is not None, "acc_alpha destination doc missing"
    assert beta_doc is not None, "acc_beta destination doc missing"
    assert gamma_doc is not None, "acc_gamma destination doc missing"

    # organization_id back-reference
    assert alpha_doc["organization_id"] == realistic_id, (
        f"acc_alpha organization_id mismatch: {alpha_doc['organization_id']!r}"
    )
    assert beta_doc["organization_id"] == realistic_id
    assert gamma_doc["organization_id"] == minimal_id

    # Payload fields match source
    assert (
        alpha_doc["account_settings"]
        == realistic_data["accounts"][f"acc_alpha_{run_id}"]["account_settings"]
    )
    assert (
        alpha_doc["funnels"]
        == realistic_data["accounts"][f"acc_alpha_{run_id}"]["funnels"]
    )

    assert beta_doc["account_settings"] == {}
    assert (
        beta_doc["funnels"]
        == realistic_data["accounts"][f"acc_beta_{run_id}"]["funnels"]
    )

    # shape_d_migrated_at is present and parseable
    for doc, label in [(alpha_doc, "alpha"), (beta_doc, "beta"), (gamma_doc, "gamma")]:
        migrated_at = doc.get("shape_d_migrated_at")
        assert migrated_at is not None, f"acc_{label} missing shape_d_migrated_at"
        datetime.fromisoformat(migrated_at)  # raises if not a valid ISO string

    # Summary counts
    assert summary.copied == 3, f"expected 3 copied, got {summary.copied}"
    assert summary.errors == 0, f"unexpected errors: {summary.errors}"

    # Pre-existing unrelated account is untouched (not in any org's accounts map)
    preexisting = _get_doc(emulator_client, "accounts", f"acc_preexisting_{run_id}")
    assert preexisting is not None
    assert preexisting.get("display_name") == "Pre-existing Account"


@pytest.mark.integration
def test_rerun_is_noop(emulator_client: Any, run_id: str) -> None:
    """AC-8: re-running the script produces zero new writes.

    Seeds 1 org / 2 accounts, runs migration once, then runs again.
    Second run: all accounts should be skipped; shape_d_migrated_at unchanged.
    """
    from migrate_shape_d_split import run_migration

    realistic_id = f"org_realistic_{run_id}"
    realistic_data = _realistic_org(run_id)
    _seed_doc(emulator_client, "organizations", realistic_id, realistic_data)

    # First run
    summary1 = run_migration(emulator_client, dry_run=False)
    assert summary1.copied == 2
    assert summary1.errors == 0

    # Capture shape_d_migrated_at from first run
    alpha_first = _get_doc(emulator_client, "accounts", f"acc_alpha_{run_id}")
    assert alpha_first is not None
    migrated_at_first = alpha_first["shape_d_migrated_at"]

    # Second run
    summary2 = run_migration(emulator_client, dry_run=False)
    assert summary2.copied == 0, f"second run should copy 0, got {summary2.copied}"
    assert summary2.skipped == 2, f"second run should skip 2, got {summary2.skipped}"
    assert summary2.errors == 0

    # shape_d_migrated_at unchanged (idempotency: no overwrite occurred)
    alpha_second = _get_doc(emulator_client, "accounts", f"acc_alpha_{run_id}")
    assert alpha_second is not None
    assert alpha_second["shape_d_migrated_at"] == migrated_at_first, (
        "shape_d_migrated_at changed on second run — write occurred when it should not have"
    )


@pytest.mark.integration
def test_org_level_fields_untouched(emulator_client: Any, run_id: str) -> None:
    """Risk-5: org-level fields (name, agency, created_at) are byte-identical before/after.

    Proves the migration script never writes back to organizations/{org_id}.
    """
    from migrate_shape_d_split import run_migration

    realistic_id = f"org_realistic_{run_id}"
    realistic_data = _realistic_org(run_id)
    _seed_doc(emulator_client, "organizations", realistic_id, realistic_data)

    minimal_id = f"org_minimal_{run_id}"
    _seed_doc(emulator_client, "organizations", minimal_id, _minimal_org(run_id))

    # Capture org docs before migration
    org_before_realistic = _get_doc(emulator_client, "organizations", realistic_id)
    org_before_minimal = _get_doc(emulator_client, "organizations", minimal_id)

    run_migration(emulator_client, dry_run=False)

    # Org docs after migration
    org_after_realistic = _get_doc(emulator_client, "organizations", realistic_id)
    org_after_minimal = _get_doc(emulator_client, "organizations", minimal_id)

    # Org-level fields unchanged (serialize both to JSON for comparison, ignoring datetime serialisation)
    def _org_top_level(d: dict[str, Any] | None) -> dict[str, Any]:
        if d is None:
            return {}
        return {k: json.dumps(v, default=str) for k, v in d.items() if k != "accounts"}

    assert _org_top_level(org_before_realistic) == _org_top_level(
        org_after_realistic
    ), "org-level fields changed on realistic org after migration"
    assert _org_top_level(org_before_minimal) == _org_top_level(org_after_minimal), (
        "org-level fields changed on minimal org after migration"
    )


@pytest.mark.integration
def test_dry_run_writes_nothing(emulator_client: Any, run_id: str) -> None:
    """--dry-run: no destination docs are created."""
    from migrate_shape_d_split import run_migration

    realistic_id = f"org_realistic_{run_id}"
    _seed_doc(emulator_client, "organizations", realistic_id, _realistic_org(run_id))

    summary = run_migration(emulator_client, dry_run=True)

    # No destination docs should exist
    alpha = _get_doc(emulator_client, "accounts", f"acc_alpha_{run_id}")
    beta = _get_doc(emulator_client, "accounts", f"acc_beta_{run_id}")
    assert alpha is None, f"acc_alpha was written in dry-run mode: {alpha}"
    assert beta is None, f"acc_beta was written in dry-run mode: {beta}"

    # Summary records as "WOULD COPY" — dry-run logic tracks them
    assert summary.errors == 0


@pytest.mark.integration
def test_merge_semantics_preserve_existing_fields(
    emulator_client: Any, run_id: str
) -> None:
    """merge=True: existing unrelated fields on accounts/{account_id} are preserved.

    Seeds acc_alpha with a display_name field, then runs the migration.
    After migration, display_name should still be present alongside the new fields.
    """
    from migrate_shape_d_split import run_migration

    realistic_id = f"org_realistic_{run_id}"
    realistic_data = _realistic_org(run_id)
    _seed_doc(emulator_client, "organizations", realistic_id, realistic_data)

    # Pre-seed acc_alpha with an unrelated field
    _seed_doc(
        emulator_client,
        "accounts",
        f"acc_alpha_{run_id}",
        {"display_name": "My Account", "some_other_field": 42},
    )

    run_migration(emulator_client, dry_run=False)

    alpha = _get_doc(emulator_client, "accounts", f"acc_alpha_{run_id}")
    assert alpha is not None
    # Unrelated fields preserved
    assert alpha.get("display_name") == "My Account", (
        "display_name was overwritten; merge=True semantics broken"
    )
    assert alpha.get("some_other_field") == 42
    # New fields present
    assert alpha.get("organization_id") == realistic_id
    assert "shape_d_migrated_at" in alpha


# ---------------------------------------------------------------------------
# Delete-pass integration tests (--confirm-delete-field)
# ---------------------------------------------------------------------------


def _org_top_level(d: dict[str, Any] | None) -> dict[str, Any]:
    """Return all org-level fields except 'accounts', serialised for comparison."""
    if d is None:
        return {}
    return {k: json.dumps(v, default=str) for k, v in d.items() if k != "accounts"}


@pytest.mark.integration
def test_confirm_delete_field_removes_accounts_field(
    emulator_client: Any, run_id: str
) -> None:
    """AC-4: after --confirm-delete-field, fully-migrated org has no accounts field.

    Seeds two orgs:
    - org_full: all accounts fully migrated → accounts field removed.
    - org_partial: one account doc missing → accounts field retained.

    Asserts that other org-level fields (name, agency, created_at) are unchanged.
    """
    from migrate_shape_d_split import run_delete_field_pass

    full_id = f"org_full_{run_id}"
    partial_id = f"org_partial_{run_id}"

    acc_full = f"acc_full_{run_id}"
    acc_partial_a = f"acc_partial_a_{run_id}"
    acc_partial_b = f"acc_partial_b_{run_id}"

    settings_full = {"overview_kpis": {"income_kpi": "m_100"}}
    funnels_full = {"organization": {"1": {"name": "Awareness"}}}

    settings_pa = {"kpi": "m_2"}
    funnels_pa = {}

    # Seed org_full with 1 account — fully migrated
    _seed_doc(
        emulator_client,
        "organizations",
        full_id,
        {
            "name": "Full Org",
            "agency": "Full Agency",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "accounts": {
                acc_full: {"account_settings": settings_full, "funnels": funnels_full},
            },
        },
    )
    _seed_doc(
        emulator_client,
        "accounts",
        acc_full,
        {
            "organization_id": full_id,
            "account_settings": settings_full,
            "funnels": funnels_full,
            "shape_d_migrated_at": "2026-05-11T00:00:00+00:00",
        },
    )

    # Seed org_partial with 2 accounts, but only acc_partial_a is migrated
    _seed_doc(
        emulator_client,
        "organizations",
        partial_id,
        {
            "name": "Partial Org",
            "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "accounts": {
                acc_partial_a: {"account_settings": settings_pa, "funnels": funnels_pa},
                acc_partial_b: {"account_settings": {"kpi": "m_99"}, "funnels": {}},
            },
        },
    )
    _seed_doc(
        emulator_client,
        "accounts",
        acc_partial_a,
        {
            "organization_id": partial_id,
            "account_settings": settings_pa,
            "funnels": funnels_pa,
            "shape_d_migrated_at": "2026-05-11T00:00:00+00:00",
        },
    )
    # acc_partial_b intentionally NOT seeded in accounts/ — verification gate must catch this

    # Capture org-level fields before the delete-pass
    org_full_before = _get_doc(emulator_client, "organizations", full_id)
    org_partial_before = _get_doc(emulator_client, "organizations", partial_id)

    summary = run_delete_field_pass(emulator_client, dry_run=False)

    # org_full: accounts field should be gone
    org_full_after = _get_doc(emulator_client, "organizations", full_id)
    assert org_full_after is not None
    assert "accounts" not in org_full_after, (
        f"org_full still has accounts field after delete-pass: {org_full_after}"
    )

    # org_partial: accounts field should still be there (gate blocked deletion)
    org_partial_after = _get_doc(emulator_client, "organizations", partial_id)
    assert org_partial_after is not None
    assert "accounts" in org_partial_after, (
        "org_partial's accounts field was wrongly deleted despite missing migration"
    )

    # org-level fields (name, agency, created_at) must be unchanged for both orgs
    assert _org_top_level(org_full_before) == _org_top_level(org_full_after), (
        "org_full non-accounts fields changed after delete-pass"
    )
    assert _org_top_level(org_partial_before) == _org_top_level(org_partial_after), (
        "org_partial non-accounts fields changed after delete-pass"
    )

    # Summary counters
    assert summary.orgs_field_deleted == 1
    assert summary.orgs_skipped_unmigrated == 1
    assert summary.orgs_already_clean == 0


@pytest.mark.integration
def test_confirm_delete_field_is_idempotent(emulator_client: Any, run_id: str) -> None:
    """Running --confirm-delete-field twice on an already-cleaned org is a no-op.

    First pass removes the accounts field; second pass records already_clean=1
    and makes no further writes.
    """
    from migrate_shape_d_split import run_delete_field_pass

    full_id = f"org_full_{run_id}"
    acc_full = f"acc_full_{run_id}"

    settings = {"kpi": "m_1"}
    funnels: dict[str, Any] = {}

    _seed_doc(
        emulator_client,
        "organizations",
        full_id,
        {
            "name": "Idempotent Org",
            "accounts": {
                acc_full: {"account_settings": settings, "funnels": funnels},
            },
        },
    )
    _seed_doc(
        emulator_client,
        "accounts",
        acc_full,
        {
            "organization_id": full_id,
            "account_settings": settings,
            "funnels": funnels,
            "shape_d_migrated_at": "2026-05-11T00:00:00+00:00",
        },
    )

    # First pass — should delete the accounts field
    summary1 = run_delete_field_pass(emulator_client, dry_run=False)
    assert summary1.orgs_field_deleted == 1
    assert summary1.orgs_already_clean == 0

    org_after_first = _get_doc(emulator_client, "organizations", full_id)
    assert org_after_first is not None
    assert "accounts" not in org_after_first, (
        "accounts field should be gone after first pass"
    )

    # Second pass — org already has no accounts field → already_clean
    summary2 = run_delete_field_pass(emulator_client, dry_run=False)
    assert summary2.orgs_field_deleted == 0
    assert summary2.orgs_already_clean == 1
    assert summary2.orgs_skipped_unmigrated == 0
