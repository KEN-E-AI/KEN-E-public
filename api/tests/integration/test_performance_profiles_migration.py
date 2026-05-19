"""Integration test for the ``performance_profiles`` migration resource (DM-34).

Pins the production ``RESOURCES["performance_profiles"]`` registry entry and exercises
the copy → verify → confirm-delete pipeline against the Firestore emulator.  Acts as
a regression guard for DM-40 (the dev-data migration for ``performance_profiles``): any
future bad edit to the ``performance_profiles`` entry in resources.py (e.g. wrong
``old_prefix``) will be caught here before the live migration runs on real data.

Enable by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_performance_profiles_migration.py -v
"""

from __future__ import annotations

import io
import os
import sys
import uuid
from collections.abc import Generator
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip gate — mirrors test_migration_script_against_emulator.py:40-47
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Path bootstrap — mirrors test_migration_script_against_emulator.py:52-54
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_RESOURCE_NAME = "performance_profiles"


# ---------------------------------------------------------------------------
# Helpers — same idiom as test_migration_script_against_emulator.py:62-107
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        raise RuntimeError(
            "_firestore_client() must only be called with FIRESTORE_EMULATOR_HOST set"
        )
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _seed_doc(client: Any, path: str, data: dict[str, object]) -> None:
    """Seed a single document at *path* (slash-separated, e.g. ``col/doc``)."""
    parts = path.split("/")
    ref = client.collection(parts[0])
    for i, part in enumerate(parts[1:], 1):
        if i % 2 == 1:
            ref = ref.document(part)  # type: ignore[assignment]
        else:
            ref = ref.collection(part)  # type: ignore[assignment]
    ref.set(data)  # type: ignore[union-attr]


def _count_docs(client: Any, col_path: str) -> int:
    """Count direct children of a collection path."""
    return len(list(client.collection(col_path).list_documents()))


def _delete_collection(client: Any, col_ref: object) -> None:
    """Recursively delete all docs in a collection (best-effort)."""
    try:
        for doc_ref in list(col_ref.list_documents()):  # type: ignore[union-attr]
            for sub_col in doc_ref.collections():
                _delete_collection(client, sub_col)
            doc_ref.delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixtures — same idiom as test_migration_script_against_emulator.py:115-147
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_id() -> str:
    """Unique suffix for each test run to prevent cross-test pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def emulator_client() -> Any:
    return _firestore_client()


@pytest.fixture(autouse=True)
def cleanup_store(emulator_client: Any, run_id: str) -> Generator[None, None, None]:
    """Delete test-owned Firestore docs after each test.

    Source collections (names include ``run_id``) are cleaned directly.  The
    fixed-name ``performance_profiles`` destination subcollection is not matched
    by the ``sub_col.id`` check below, but since ``run_id`` is embedded in each
    synthetic account_id slug (e.g. ``acc_{run_id}_a``), destination paths are
    unique per test run and there is no cross-test pollution.
    """
    yield

    # Remove source-side top-level collections (names contain run_id)
    for col_ref in emulator_client.collections():
        if run_id in col_ref.id:
            _delete_collection(emulator_client, col_ref)

    # Remove destination subcollections under accounts/* (subcollection name contains run_id)
    try:
        for doc_ref in emulator_client.collection("accounts").list_documents():
            for sub_col in doc_ref.collections():
                if run_id in sub_col.id:
                    _delete_collection(emulator_client, sub_col)
    except Exception:
        pass  # Best-effort


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_performance_profiles_copy_and_verify(
    emulator_client: Any,
    run_id: str,
) -> None:
    """Production registry config copies data from Shape A to Shape B paths.

    Seeds two source collections with the realistic production naming pattern
    (``performance_profiles_acc_<hex>/{doc_id}``) and asserts that
    ``migrate_resource()`` copies every document to the correct Shape B
    destination.  The test pins ``RESOURCES["performance_profiles"]``—not a
    synthetic per-test ``MigrateConfig``—so any future registry drift is caught
    here before DM-40 attempts the live dev migration.

    Account IDs are uniformly ``acc_<uuid>`` in production
    (api/src/kene_api/routers/accounts.py:65,72,87), so the only real
    source-collection pattern is ``performance_profiles_acc_<hex>``.  ``run_id``
    is embedded in the synthetic account_id slug rather than the prefix because
    the production ``old_prefix`` is fixed at ``"performance_profiles_"``.
    """
    from _migrate_shape_b.resources import RESOURCES
    from _migrate_shape_b.runner import migrate_resource

    config = RESOURCES[_RESOURCE_NAME]
    # Guard: if the registry entry changes to a wrong prefix, this assertion
    # fires before a potentially data-losing migration step runs in DM-40.
    assert config.old_prefix == "performance_profiles_", (
        f"RESOURCES['{_RESOURCE_NAME}'].old_prefix changed — review DM-40 before proceeding"
    )
    assert config.new_subcollection == "performance_profiles"
    assert config.has_versions is False

    account_a = f"acc_{run_id}_a"
    account_b = f"acc_{run_id}_b"
    # Source names match production pattern: performance_profiles_{account_id}
    src_a = f"performance_profiles_{account_a}"
    src_b = f"performance_profiles_{account_b}"

    # Different doc counts per account to catch per-account copy errors.
    _seed_doc(
        emulator_client,
        f"{src_a}/prof_1",
        {"type": "baseline", "account_id": account_a},
    )
    _seed_doc(
        emulator_client, f"{src_a}/prof_2", {"type": "weekly", "account_id": account_a}
    )
    _seed_doc(
        emulator_client,
        f"{src_b}/prof_1",
        {"type": "baseline", "account_id": account_b},
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, _RESOURCE_NAME, config)

    output = buf.getvalue()
    assert exit_code == 0, f"stdout={output}"
    assert "VERIFIED" in output

    # Both accounts' docs land at the correct Shape B destinations.
    assert (
        _count_docs(emulator_client, f"accounts/{account_a}/performance_profiles") == 2
    )
    assert (
        _count_docs(emulator_client, f"accounts/{account_b}/performance_profiles") == 1
    )

    # Source collections are untouched (--confirm-delete not passed).
    assert _count_docs(emulator_client, src_a) == 2
    assert _count_docs(emulator_client, src_b) == 1


@pytest.mark.integration
def test_performance_profiles_confirm_delete_removes_sources(
    emulator_client: Any,
    run_id: str,
) -> None:
    """delete_source_collections() removes source collections; destination is intact.

    Exercises the ``--confirm-delete`` codepath for the ``performance_profiles``
    resource: after a verified copy, both source collections are deleted and the
    destination subcollections remain unchanged.
    """
    from _migrate_shape_b.resources import RESOURCES
    from _migrate_shape_b.runner import delete_source_collections, migrate_resource

    config = RESOURCES[_RESOURCE_NAME]

    account_a = f"acc_{run_id}_a"
    account_b = f"acc_{run_id}_b"
    src_a = f"performance_profiles_{account_a}"
    src_b = f"performance_profiles_{account_b}"

    _seed_doc(
        emulator_client,
        f"{src_a}/prof_1",
        {"type": "baseline", "account_id": account_a},
    )
    _seed_doc(
        emulator_client, f"{src_a}/prof_2", {"type": "weekly", "account_id": account_a}
    )
    _seed_doc(
        emulator_client,
        f"{src_b}/prof_1",
        {"type": "baseline", "account_id": account_b},
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, _RESOURCE_NAME, config)
    assert exit_code == 0, f"migrate stdout:\n{buf.getvalue()}"

    delete_result = delete_source_collections(emulator_client, _RESOURCE_NAME, config)

    # Source collections empty after deletion.
    assert _count_docs(emulator_client, src_a) == 0
    assert _count_docs(emulator_client, src_b) == 0

    # Destination subcollections intact.
    assert (
        _count_docs(emulator_client, f"accounts/{account_a}/performance_profiles") == 2
    )
    assert (
        _count_docs(emulator_client, f"accounts/{account_b}/performance_profiles") == 1
    )

    # Deletion summary correctly accounts for both source collections and all docs.
    assert delete_result.source_collections_deleted == 2
    assert delete_result.total_docs == 3
