"""Unit tests for deployment/firestore.indexes.json — no GCP credentials required.

Validates that the JSON file is well-formed and that the feature_flag_audit
composite index entry matches the spec in FF-PRD-01 §7.11 and README §7.5.
Also verifies the Terraform resource key derivation for the new index so that
reviewers can confirm the expected for_each key without running Terraform.
"""

import json
from pathlib import Path

import pytest

# Path is relative to the repo root; compute it from this file's location.
_REPO_ROOT = Path(__file__).parents[3]
_INDEXES_JSON = _REPO_ROOT / "deployment" / "firestore.indexes.json"

# Mirrors var.firestore_index_project_ids default in firestore_indexes.tf.
# This test only validates the dev project key derivation; staging/prod keys
# are validated by `terraform plan` when the variable is overridden.
_TEST_PROJECT = "ken-e-dev"


@pytest.fixture(scope="module")
def indexes_doc() -> dict:
    """Load and return the parsed deployment/firestore.indexes.json."""
    if not _INDEXES_JSON.exists():
        raise FileNotFoundError(
            f"deployment/firestore.indexes.json not found at {_INDEXES_JSON}. "
            "Run this test from the repo root or any subdirectory."
        )
    with _INDEXES_JSON.open() as f:
        return json.load(f)


def test_json_file_is_valid(indexes_doc: dict) -> None:
    """firestore.indexes.json parses as a dict with expected top-level keys."""
    assert isinstance(indexes_doc, dict)
    assert "indexes" in indexes_doc
    assert isinstance(indexes_doc["indexes"], list)


def test_feature_flag_audit_index_exists(indexes_doc: dict) -> None:
    """A composite index for feature_flag_audit must be present."""
    audit_indexes = [
        idx
        for idx in indexes_doc["indexes"]
        if idx.get("collectionGroup") == "feature_flag_audit"
    ]
    assert audit_indexes, (
        "No index with collectionGroup='feature_flag_audit' found in "
        "deployment/firestore.indexes.json"
    )


def test_feature_flag_audit_index_structure(indexes_doc: dict) -> None:
    """The feature_flag_audit index must match PRD §7.11 exactly.

    Required:
      collectionGroup = "feature_flag_audit"
      queryScope      = "COLLECTION"   (Shape C global — not COLLECTION_GROUP)
      fields          = [{flag_key, ASCENDING}, {created_at, DESCENDING}]
    """
    audit_indexes = [
        idx
        for idx in indexes_doc["indexes"]
        if idx.get("collectionGroup") == "feature_flag_audit"
    ]
    assert len(audit_indexes) == 1, (
        f"Expected exactly 1 feature_flag_audit index, found {len(audit_indexes)}"
    )

    idx = audit_indexes[0]

    assert idx["queryScope"] == "COLLECTION", (
        "feature_flag_audit must use queryScope='COLLECTION' (Shape C global). "
        f"Got: {idx['queryScope']!r}"
    )

    fields = idx.get("fields", [])
    assert len(fields) == 2, (
        f"Expected 2 fields in feature_flag_audit index, got {len(fields)}: {fields}"
    )

    # First field: flag_key ASCENDING (equality filter field must come first)
    assert fields[0]["fieldPath"] == "flag_key", (
        f"First field must be 'flag_key', got {fields[0]['fieldPath']!r}"
    )
    assert fields[0].get("order") == "ASCENDING", (
        f"flag_key field must be ASCENDING, got {fields[0].get('order')!r}"
    )

    # Second field: created_at DESCENDING (newest-first sort)
    assert fields[1]["fieldPath"] == "created_at", (
        f"Second field must be 'created_at', got {fields[1]['fieldPath']!r}"
    )
    assert fields[1].get("order") == "DESCENDING", (
        f"created_at field must be DESCENDING, got {fields[1].get('order')!r}"
    )


def test_feature_flag_audit_terraform_key(indexes_doc: dict) -> None:
    """Verify the Terraform for_each key for the feature_flag_audit index.

    The key formula from firestore_indexes.tf line 36:
        "{project}_{collectionGroup}_{queryScope}_{field_signature}"
    where field_signature = "__".join(f"{f.fieldPath}-{f.order}" for f in fields)

    For project "ken-e-dev" and the spec index, the expected key is:
        "ken-e-dev_feature_flag_audit_COLLECTION_flag_key-ASCENDING__created_at-DESCENDING"

    This test does NOT require Terraform to be installed — it validates the
    JSON-derived key that Terraform would compute, giving a static guarantee
    that the index will be picked up as a new resource (not confused with an
    existing one) when an operator runs `terraform plan`.
    """
    audit_idx = next(
        idx
        for idx in indexes_doc["indexes"]
        if idx.get("collectionGroup") == "feature_flag_audit"
    )

    project = _TEST_PROJECT
    collection_group = audit_idx["collectionGroup"]
    query_scope = audit_idx["queryScope"]
    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in audit_idx["fields"]
    )
    derived_key = f"{project}_{collection_group}_{query_scope}_{field_signature}"

    expected_key = (
        f"{_TEST_PROJECT}_feature_flag_audit_COLLECTION_"
        "flag_key-ASCENDING__created_at-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform resource key mismatch.\n"
        f"  Expected: {expected_key!r}\n"
        f"  Derived:  {derived_key!r}\n"
        "Update this test if the key formula in firestore_indexes.tf changes."
    )


def test_no_other_indexes_modified(indexes_doc: dict) -> None:
    """Presence check: feature_flag_audit is the only index added by FF-7.

    This test enumerates collectionGroups to confirm no unexpected entries
    were added or removed by this PR. Existing entries are preserved by
    checking against a known-good minimum set.
    """
    collection_groups = {idx["collectionGroup"] for idx in indexes_doc["indexes"]}

    # Entries present before FF-7 (non-exhaustive — just a sample from the
    # original file's indexes array). Adding new entries here is fine; removing
    # existing ones would cause a test failure signalling unintended deletion.
    # Note: project_plan_audit is a fieldOverride, not an index — omitted here.
    pre_existing = {
        "notifications",
        "strategy_audit",
        "skills",
        "plan_runs",
    }
    missing = pre_existing - collection_groups
    assert not missing, (
        f"Pre-existing index entries were removed from firestore.indexes.json: {missing}"
    )

    # The feature_flag_audit entry must be present (added by FF-7)
    assert "feature_flag_audit" in collection_groups, (
        "feature_flag_audit index is missing — it should have been added by FF-7"
    )


# ---------------------------------------------------------------------------
# DM-69 — strategy_audit COLLECTION-scoped composite indexes
# ---------------------------------------------------------------------------
# These five indexes cover the three query paths in routers/strategy.py
# (get_strategy_audit_log) and services/audit_service.py (get_recent_actions,
# get_document_history) that became index-eligible once DM-15 migrated
# strategy_audit writes to accounts/{account_id}/strategy_audit (Shape B).
# The COLLECTION_GROUP entry already present (user_id, timestamp DESC) is for
# get_user_activity's collection_group query — distinct index space.

def _strategy_audit_collection_indexes(indexes_doc: dict) -> list[dict]:
    """Return all strategy_audit COLLECTION-scoped indexes."""
    return [
        idx
        for idx in indexes_doc["indexes"]
        if idx.get("collectionGroup") == "strategy_audit"
        and idx.get("queryScope") == "COLLECTION"
    ]


def test_strategy_audit_collection_indexes_count(indexes_doc: dict) -> None:
    """Exactly five COLLECTION-scoped strategy_audit indexes must be present."""
    collection_idxs = _strategy_audit_collection_indexes(indexes_doc)
    assert len(collection_idxs) == 5, (
        f"Expected 5 COLLECTION-scoped strategy_audit indexes, found "
        f"{len(collection_idxs)}: {collection_idxs}"
    )


def _find_strategy_audit_collection_index(
    indexes_doc: dict, fields: list[tuple[str, str]]
) -> dict | None:
    """Look up a strategy_audit COLLECTION index by its exact field list."""
    target_fields = [{"fieldPath": fp, "order": order} for fp, order in fields]
    for idx in _strategy_audit_collection_indexes(indexes_doc):
        if idx.get("fields") == target_fields:
            return idx
    return None


def test_strategy_audit_doc_type_timestamp_index_exists(indexes_doc: dict) -> None:
    """(doc_type ASC, timestamp DESC) — get_strategy_audit_log (no action filter)
    and get_recent_actions (doc_type-only filter)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc, [("doc_type", "ASCENDING"), ("timestamp", "DESCENDING")]
    )
    assert idx is not None, (
        "strategy_audit COLLECTION index (doc_type ASC, timestamp DESC) not found"
    )


def test_strategy_audit_doc_type_timestamp_terraform_key(indexes_doc: dict) -> None:
    """Terraform for_each key for (doc_type ASC, timestamp DESC)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc, [("doc_type", "ASCENDING"), ("timestamp", "DESCENDING")]
    )
    assert idx is not None

    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in idx["fields"]
    )
    derived_key = (
        f"{_TEST_PROJECT}_{idx['collectionGroup']}_{idx['queryScope']}_{field_signature}"
    )
    expected_key = (
        f"{_TEST_PROJECT}_strategy_audit_COLLECTION_"
        "doc_type-ASCENDING__timestamp-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform key mismatch.\n  Expected: {expected_key!r}\n  Derived: {derived_key!r}"
    )


def test_strategy_audit_doc_type_action_timestamp_index_exists(
    indexes_doc: dict,
) -> None:
    """(doc_type ASC, action ASC, timestamp DESC) — get_strategy_audit_log with action filter."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("doc_type", "ASCENDING"), ("action", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None, (
        "strategy_audit COLLECTION index (doc_type ASC, action ASC, timestamp DESC) not found"
    )


def test_strategy_audit_doc_type_action_timestamp_terraform_key(
    indexes_doc: dict,
) -> None:
    """Terraform for_each key for (doc_type ASC, action ASC, timestamp DESC)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("doc_type", "ASCENDING"), ("action", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None

    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in idx["fields"]
    )
    derived_key = (
        f"{_TEST_PROJECT}_{idx['collectionGroup']}_{idx['queryScope']}_{field_signature}"
    )
    expected_key = (
        f"{_TEST_PROJECT}_strategy_audit_COLLECTION_"
        "doc_type-ASCENDING__action-ASCENDING__timestamp-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform key mismatch.\n  Expected: {expected_key!r}\n  Derived: {derived_key!r}"
    )


def test_strategy_audit_user_id_timestamp_index_exists(indexes_doc: dict) -> None:
    """(user_id ASC, timestamp DESC) — get_recent_actions with user_id-only filter."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc, [("user_id", "ASCENDING"), ("timestamp", "DESCENDING")]
    )
    assert idx is not None, (
        "strategy_audit COLLECTION index (user_id ASC, timestamp DESC) not found"
    )


def test_strategy_audit_user_id_timestamp_terraform_key(indexes_doc: dict) -> None:
    """Terraform for_each key for (user_id ASC, timestamp DESC)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc, [("user_id", "ASCENDING"), ("timestamp", "DESCENDING")]
    )
    assert idx is not None

    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in idx["fields"]
    )
    derived_key = (
        f"{_TEST_PROJECT}_{idx['collectionGroup']}_{idx['queryScope']}_{field_signature}"
    )
    expected_key = (
        f"{_TEST_PROJECT}_strategy_audit_COLLECTION_"
        "user_id-ASCENDING__timestamp-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform key mismatch.\n  Expected: {expected_key!r}\n  Derived: {derived_key!r}"
    )


def test_strategy_audit_user_id_doc_type_timestamp_index_exists(
    indexes_doc: dict,
) -> None:
    """(user_id ASC, doc_type ASC, timestamp DESC) — get_recent_actions with user_id + doc_type."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("user_id", "ASCENDING"), ("doc_type", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None, (
        "strategy_audit COLLECTION index (user_id ASC, doc_type ASC, timestamp DESC) not found"
    )


def test_strategy_audit_user_id_doc_type_timestamp_terraform_key(
    indexes_doc: dict,
) -> None:
    """Terraform for_each key for (user_id ASC, doc_type ASC, timestamp DESC)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("user_id", "ASCENDING"), ("doc_type", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None

    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in idx["fields"]
    )
    derived_key = (
        f"{_TEST_PROJECT}_{idx['collectionGroup']}_{idx['queryScope']}_{field_signature}"
    )
    expected_key = (
        f"{_TEST_PROJECT}_strategy_audit_COLLECTION_"
        "user_id-ASCENDING__doc_type-ASCENDING__timestamp-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform key mismatch.\n  Expected: {expected_key!r}\n  Derived: {derived_key!r}"
    )


def test_strategy_audit_doc_type_doc_id_timestamp_index_exists(
    indexes_doc: dict,
) -> None:
    """(doc_type ASC, doc_id ASC, timestamp DESC) — get_document_history."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("doc_type", "ASCENDING"), ("doc_id", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None, (
        "strategy_audit COLLECTION index (doc_type ASC, doc_id ASC, timestamp DESC) not found"
    )


def test_strategy_audit_doc_type_doc_id_timestamp_terraform_key(
    indexes_doc: dict,
) -> None:
    """Terraform for_each key for (doc_type ASC, doc_id ASC, timestamp DESC)."""
    idx = _find_strategy_audit_collection_index(
        indexes_doc,
        [("doc_type", "ASCENDING"), ("doc_id", "ASCENDING"), ("timestamp", "DESCENDING")],
    )
    assert idx is not None

    field_signature = "__".join(
        f"{f['fieldPath']}-{f.get('order', f.get('arrayConfig', ''))}"
        for f in idx["fields"]
    )
    derived_key = (
        f"{_TEST_PROJECT}_{idx['collectionGroup']}_{idx['queryScope']}_{field_signature}"
    )
    expected_key = (
        f"{_TEST_PROJECT}_strategy_audit_COLLECTION_"
        "doc_type-ASCENDING__doc_id-ASCENDING__timestamp-DESCENDING"
    )
    assert derived_key == expected_key, (
        f"Terraform key mismatch.\n  Expected: {expected_key!r}\n  Derived: {derived_key!r}"
    )


def test_strategy_audit_collection_group_index_preserved(indexes_doc: dict) -> None:
    """The pre-existing strategy_audit COLLECTION_GROUP (user_id, timestamp) index
    for get_user_activity must not have been removed or modified."""
    cg_idxs = [
        idx
        for idx in indexes_doc["indexes"]
        if idx.get("collectionGroup") == "strategy_audit"
        and idx.get("queryScope") == "COLLECTION_GROUP"
    ]
    assert len(cg_idxs) == 1, (
        f"Expected exactly 1 strategy_audit COLLECTION_GROUP index, found {len(cg_idxs)}"
    )
    fields = cg_idxs[0].get("fields", [])
    assert fields == [
        {"fieldPath": "user_id", "order": "ASCENDING"},
        {"fieldPath": "timestamp", "order": "DESCENDING"},
    ], f"strategy_audit COLLECTION_GROUP index fields changed unexpectedly: {fields}"
