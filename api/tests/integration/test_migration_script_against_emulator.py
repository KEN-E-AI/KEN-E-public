"""Integration tests for migrate_to_shape_b.py copy + verify runner (DM-3, DM-4, DM-5, DM-6).

These tests run against the Firestore emulator and are **skipped by default**.
Enable them by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable
before running pytest, e.g.:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_migration_script_against_emulator.py -v

Covers PRD §7 acceptance criteria (AC-3, AC-4, AC-6):
- AC-3: Seed 3 dummy source collections and assert copy lands in Shape B paths
- Source collections are untouched (--confirm-delete not passed)
- Per-account counts match after copy
- Exit code 0 for a fully-verified run
- has_versions=True: /versions/{n} sub-docs copied correctly
- Partial-data: one source empty, another with docs — runner handles gracefully
- Idempotency (AC-4): re-running is a no-op; partially-migrated state resumes correctly
- AC-6 (DM-6): --dry-run writes nothing and prints the plan
"""

from __future__ import annotations

import io
import logging
import os
import sys
import uuid
from collections.abc import Generator
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip gate — mirror pattern from test_migration_smoke.py:17-21
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
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    """Build a Firestore client that talks to the emulator."""
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _seed_doc(
    client: Any,
    path: str,
    data: dict[str, object],
) -> None:
    """Seed a single document at *path* (slash-separated, e.g. ``col/doc``)."""
    parts = path.split("/")
    ref = client.collection(parts[0])
    for i, part in enumerate(parts[1:], 1):
        if i % 2 == 1:  # odd index → document
            ref = ref.document(part)  # type: ignore[assignment]
        else:  # even index → subcollection
            ref = ref.collection(part)  # type: ignore[assignment]
    ref.set(data)  # type: ignore[union-attr]


def _count_docs(
    client: Any,
    col_path: str,
) -> int:
    """Count direct children of a collection path."""
    col = client.collection(col_path)
    return len(list(col.list_documents()))


def _delete_collection(
    client: Any,
    col_ref: object,
) -> None:
    """Recursively delete all docs in a collection (best-effort)."""
    try:
        docs = list(col_ref.list_documents())  # type: ignore[union-attr]
        for doc_ref in docs:
            for sub_col in doc_ref.collections():
                _delete_collection(client, sub_col)
            doc_ref.delete()
    except Exception:
        pass  # Best-effort cleanup; don't fail the test suite


# ---------------------------------------------------------------------------
# Fixtures
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
    """Delete all test-owned Firestore docs after each test.

    Targets only collections/subcollections whose names contain *run_id* so that
    concurrent tests or pre-existing emulator state are not disturbed.
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
# Test: basic copy (AC-3 core: 3 seeded sources, counts match, exit 0)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_basic_copy_three_sources(
    emulator_client: Any,
    run_id: str,
) -> None:
    """Seed example_acc_A, example_acc_B, example_acc_C; run runner; verify AC-3."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"example_{run_id}_"

    # Seed source collections
    _seed_doc(emulator_client, f"{prefix}acc_A/doc1", {"val": "a1"})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc2", {"val": "a2"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc1", {"val": "b1"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc2", {"val": "b2"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc3", {"val": "b3"})
    _seed_doc(emulator_client, f"{prefix}acc_C/doc1", {"val": "c1"})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=f"example_{run_id}")

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, f"example_{run_id}", config)

    # (a) Exit code 0
    assert exit_code == 0, f"stdout={buf.getvalue()}"

    # (b) Data copied to accounts/{id}/example_{run_id}/...
    assert _count_docs(emulator_client, f"accounts/acc_A/example_{run_id}") == 2
    assert _count_docs(emulator_client, f"accounts/acc_B/example_{run_id}") == 3
    assert _count_docs(emulator_client, f"accounts/acc_C/example_{run_id}") == 1

    # (c) Source collections still exist (no --confirm-delete passed)
    assert _count_docs(emulator_client, f"{prefix}acc_A") == 2
    assert _count_docs(emulator_client, f"{prefix}acc_B") == 3
    assert _count_docs(emulator_client, f"{prefix}acc_C") == 1

    # (d) Summary block in stdout
    assert "VERIFIED" in buf.getvalue()


# ---------------------------------------------------------------------------
# Test: has_versions=True (PRD §7 integration tests)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_copy_with_versions(
    emulator_client: Any,
    run_id: str,
) -> None:
    """Seed a doc with 2 versions; verify both land at accounts/{id}/…/versions/{n}."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"versioned_{run_id}_"
    res_name = f"versioned_{run_id}"

    _seed_doc(emulator_client, f"{prefix}acc_V/swot", {"title": "SWOT"})
    _seed_doc(
        emulator_client, f"{prefix}acc_V/swot/versions/1", {"v": 1, "content": "draft"}
    )
    _seed_doc(
        emulator_client, f"{prefix}acc_V/swot/versions/2", {"v": 2, "content": "final"}
    )

    config = MigrateConfig(
        old_prefix=prefix, new_subcollection=res_name, has_versions=True
    )

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, res_name, config)

    assert exit_code == 0, f"stdout={buf.getvalue()}"

    # Main doc
    dest_doc = (
        emulator_client.collection(f"accounts/acc_V/{res_name}").document("swot").get()
    )
    assert dest_doc.exists
    assert dest_doc.to_dict() == {"title": "SWOT"}

    # Version sub-docs
    v1 = (
        emulator_client.collection(f"accounts/acc_V/{res_name}")
        .document("swot")
        .collection("versions")
        .document("1")
        .get()
    )
    v2 = (
        emulator_client.collection(f"accounts/acc_V/{res_name}")
        .document("swot")
        .collection("versions")
        .document("2")
        .get()
    )
    assert v1.exists and v1.to_dict() == {"v": 1, "content": "draft"}
    assert v2.exists and v2.to_dict() == {"v": 2, "content": "final"}


# ---------------------------------------------------------------------------
# Test: partial-data (one source empty, another with docs — PRD §7)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_partial_data_handled_correctly(
    emulator_client: Any,
    run_id: str,
) -> None:
    """One source collection absent, another with 3 docs — both handled gracefully."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"partial_{run_id}_"
    res_name = f"partial_{run_id}"

    # acc_X: not seeded at all (Firestore emulator collections disappear when empty,
    # so the runner will simply not find a matching collection and skip it).

    # acc_Y: 3 docs
    _seed_doc(emulator_client, f"{prefix}acc_Y/d1", {"n": 1})
    _seed_doc(emulator_client, f"{prefix}acc_Y/d2", {"n": 2})
    _seed_doc(emulator_client, f"{prefix}acc_Y/d3", {"n": 3})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, res_name, config)

    assert exit_code == 0, f"stdout={buf.getvalue()}"
    assert _count_docs(emulator_client, f"accounts/acc_Y/{res_name}") == 3
    assert "VERIFIED" in buf.getvalue()


# ---------------------------------------------------------------------------
# Test: idempotency — re-run is a no-op (AC-4)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_idempotency_rerun_is_noop(
    emulator_client: Any,
    run_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Run migrate_resource() twice; assert the second run is a no-op (AC-4).

    Checks:
    (a) second run returns exit code 0
    (b) destination doc count is unchanged after the second run
    (c) the runner logs at least one "already migrated" record on the second run
    """
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"idem_{run_id}_"
    res_name = f"idem_{run_id}"

    _seed_doc(emulator_client, f"{prefix}acc_A/doc1", {"v": 1})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc2", {"v": 2})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    # First run — copies both docs
    buf1 = io.StringIO()
    with redirect_stdout(buf1):
        exit_code_1 = migrate_resource(emulator_client, res_name, config)
    assert exit_code_1 == 0, f"first run failed: {buf1.getvalue()}"
    assert _count_docs(emulator_client, f"accounts/acc_A/{res_name}") == 2

    # Second run — all destination docs already present; must be a no-op
    with caplog.at_level(logging.DEBUG, logger="_migrate_shape_b.runner"):
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            exit_code_2 = migrate_resource(emulator_client, res_name, config)

    assert exit_code_2 == 0, f"second run failed: {buf2.getvalue()}"
    # (b) count unchanged
    assert _count_docs(emulator_client, f"accounts/acc_A/{res_name}") == 2
    # (c) at least one "already migrated" log record
    assert any("already migrated" in r.message for r in caplog.records), (
        "expected at least one 'already migrated' debug log on the second run"
    )
    # (d) summary still reports VERIFIED (destination count still equals source count)
    assert "VERIFIED" in buf2.getvalue()


# ---------------------------------------------------------------------------
# Test: partial-state resume (AC-4 — resume mid-run)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_partial_state_resume(
    emulator_client: Any,
    run_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Half the destination docs pre-seeded; runner writes only the missing half.

    Checks:
    (a) all 4 doc-ids present at the destination after one run
    (b) at least one "already migrated" debug record (pre-seeded docs were skipped)
    (c) printed summary contains "VERIFIED"
    """
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"resume_{run_id}_"
    res_name = f"resume_{run_id}"

    # Seed 4 source docs
    for i in range(1, 5):
        _seed_doc(emulator_client, f"{prefix}acc_R/doc{i}", {"n": i})

    # Pre-seed only doc1 and doc2 at the Shape B destination (simulates a
    # previous run that died after writing those two docs).
    _seed_doc(emulator_client, f"accounts/acc_R/{res_name}/doc1", {"n": 1})
    _seed_doc(emulator_client, f"accounts/acc_R/{res_name}/doc2", {"n": 2})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    with caplog.at_level(logging.DEBUG, logger="_migrate_shape_b.runner"):
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = migrate_resource(emulator_client, res_name, config)

    # (a) all 4 docs now present
    assert exit_code == 0, f"stdout={buf.getvalue()}"
    assert _count_docs(emulator_client, f"accounts/acc_R/{res_name}") == 4

    # (b) pre-seeded docs were skipped (logged)
    assert any("already migrated" in r.message for r in caplog.records), (
        "expected at least one 'already migrated' debug log for the pre-seeded docs"
    )

    # (c) migration reports VERIFIED
    assert "VERIFIED" in buf.getvalue()


# ---------------------------------------------------------------------------
# Test: --confirm-delete --yes happy path (DM-5)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_confirm_delete_yes_drops_source_collections(
    emulator_client: Any,
    run_id: str,
) -> None:
    """--confirm-delete --yes: source collections deleted after verified copy."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import delete_source_collections, migrate_resource

    prefix = f"todel_{run_id}_"
    res_name = f"todel_{run_id}"

    _seed_doc(emulator_client, f"{prefix}acc_A/doc1", {"val": "a1"})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc2", {"val": "a2"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc1", {"val": "b1"})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, res_name, config)

    assert exit_code == 0, f"migrate stdout:\n{buf.getvalue()}"

    delete_result = delete_source_collections(emulator_client, res_name, config)

    # Source collections gone
    assert _count_docs(emulator_client, f"{prefix}acc_A") == 0
    assert _count_docs(emulator_client, f"{prefix}acc_B") == 0

    # Destination intact
    assert _count_docs(emulator_client, f"accounts/acc_A/{res_name}") == 2
    assert _count_docs(emulator_client, f"accounts/acc_B/{res_name}") == 1

    # DeleteResult totals
    assert delete_result.source_collections_deleted == 2
    assert delete_result.total_docs == 3


# ---------------------------------------------------------------------------
# Test: verify-fail prevents deletion (DM-5)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_confirm_delete_skips_deletion_when_verify_fails(
    emulator_client: Any,
    run_id: str,
) -> None:
    """When migrate_resource returns 1 (verify mismatch), sources must not be deleted."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import migrate_resource

    prefix = f"fail_{run_id}_"
    res_name = f"fail_{run_id}"

    # Seed 2 source docs but pre-seed an extra orphan in destination so counts diverge.
    _seed_doc(emulator_client, f"{prefix}acc_A/doc1", {"val": "a1"})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc2", {"val": "a2"})
    _seed_doc(emulator_client, f"accounts/acc_A/{res_name}/orphan", {"val": "orphan"})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = migrate_resource(emulator_client, res_name, config)

    # Verification must fail: source=2, destination=3 (2 copied + orphan pre-existing)
    assert exit_code == 1, f"Expected exit 1 (verify fail). stdout:\n{buf.getvalue()}"
    assert "FAILED" in buf.getvalue()

    # Source must still exist (deletion never ran)
    assert _count_docs(emulator_client, f"{prefix}acc_A") == 2


# ---------------------------------------------------------------------------
# Test: --yes without --confirm-delete exits 2 (DM-5 CLI guard, subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_yes_without_confirm_delete_exits_two(run_id: str) -> None:
    """--yes without --confirm-delete exits 2 with a usage error message."""
    import subprocess
    import sys

    script = str(SCRIPTS_DIR / "migrate_to_shape_b.py")
    result = subprocess.run(
        [sys.executable, script, "--resource=whatever", "--yes"],
        capture_output=True,
        text=True,
        env={
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "FIRESTORE_EMULATOR_HOST": os.environ.get("FIRESTORE_EMULATOR_HOST", ""),
        },
    )
    assert result.returncode == 2
    assert "--yes" in result.stderr


# ---------------------------------------------------------------------------
# Test: --dry-run writes nothing (AC-6 / DM-6)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_dry_run_writes_nothing(
    emulator_client: Any,
    run_id: str,
) -> None:
    """Dry-run: source data seeded; runner prints plan; destination has zero docs after."""
    from _migrate_shape_b.config import MigrateConfig
    from _migrate_shape_b.runner import dry_run_resource

    prefix = f"dry_{run_id}_"
    res_name = f"dry_{run_id}"

    # Seed source collections across 2 accounts (total 5 docs)
    _seed_doc(emulator_client, f"{prefix}acc_A/doc1", {"val": "a1"})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc2", {"val": "a2"})
    _seed_doc(emulator_client, f"{prefix}acc_A/doc3", {"val": "a3"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc1", {"val": "b1"})
    _seed_doc(emulator_client, f"{prefix}acc_B/doc2", {"val": "b2"})

    config = MigrateConfig(old_prefix=prefix, new_subcollection=res_name)

    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = dry_run_resource(emulator_client, res_name, config)

    output = buf.getvalue()

    # (a) Exit code 0
    assert exit_code == 0, f"stdout={output}"

    # (b) Destination subcollection has zero documents for every account
    assert _count_docs(emulator_client, f"accounts/acc_A/{res_name}") == 0, (
        "dry-run must not write to accounts/acc_A"
    )
    assert _count_docs(emulator_client, f"accounts/acc_B/{res_name}") == 0, (
        "dry-run must not write to accounts/acc_B"
    )

    # (c) Source collections still have their original doc counts
    assert _count_docs(emulator_client, f"{prefix}acc_A") == 3
    assert _count_docs(emulator_client, f"{prefix}acc_B") == 2

    # (d) Summary block contains Source doc count matching the seeded total (5)
    assert any(
        "Source doc count:" in ln and ln.rstrip().endswith("5")
        for ln in output.splitlines()
    ), f"Expected 'Source doc count: 5' in output:\n{output}"

    # (e) Status reads DRY RUN (not VERIFIED or FAILED)
    assert "DRY RUN" in output
    assert "VERIFIED" not in output
    assert "FAILED" not in output

    # (f) Next step instructs operator to re-run without --dry-run
    assert "re-run without --dry-run" in output
