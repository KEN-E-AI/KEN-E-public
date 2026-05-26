"""Integration tests for chat_artifact_orphan_scan.py.

Tests exercise the scan_for_gcs_blob_orphans orchestrator against a real
Firestore emulator.  GCS I/O is replaced by a lightweight _FakeStorageClient
so no actual bucket operations are made.

Run with:
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 pytest tests/integration/chat/test_artifact_orphan_scan.py -v
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Skip entire module when emulator is absent
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="FIRESTORE_EMULATOR_HOST not set; skipping Firestore integration tests",
)

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
_API_SRC = _SCRIPTS_DIR.parent / "src"
_REPO_ROOT = _SCRIPTS_DIR.parent.parent
for _p in (str(_SCRIPTS_DIR), str(_API_SRC), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import chat_artifact_orphan_scan as cli  # noqa: E402
from kene_api.chat.artifacts import _artifact_id  # noqa: E402

# ---------------------------------------------------------------------------
# Emulator client helpers
# ---------------------------------------------------------------------------
_TEST_BUCKET = "test-artifact-bucket"
_APP_NAME = cli.APP_NAME  # "ken_e_chatbot"
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")


# ---------------------------------------------------------------------------
# Firestore emulator helpers
# ---------------------------------------------------------------------------


def _emulator_client():
    from google.cloud import firestore as _fs

    return _fs.Client(project=_PROJECT)


# ---------------------------------------------------------------------------
# Fake GCS helpers
# ---------------------------------------------------------------------------


class _FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeStorageClient:
    """Minimal storage.Client replacement that returns a configured blob list."""

    def __init__(self, blobs: list[_FakeBlob]) -> None:
        self._blobs = blobs

    def list_blobs(self, bucket_name: str, prefix: str = "") -> list[_FakeBlob]:
        return [b for b in self._blobs if b.name.startswith(prefix)]

    def bucket(self, bucket_name: str) -> None:
        raise AssertionError("bucket() should not be called by the report-only scan")


def _blob_name(user_id: str, session_id: str, filename: str, version: int = 0) -> str:
    return f"{_APP_NAME}/{user_id}/{session_id}/{filename}/{version}"


# ---------------------------------------------------------------------------
# Firestore seeding helpers
# ---------------------------------------------------------------------------


def _seed_session(
    db,
    account_id: str,
    session_id: str,
    user_id: str,
) -> None:
    """Seed a chat_sessions side-table document."""
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(
        {
            "session_id": session_id,
            "account_id": account_id,
            "user_id": user_id,
            "deleted_at": None,
        }
    )


def _seed_artifact(
    db,
    account_id: str,
    session_id: str,
    filename: str,
    version: int = 0,
) -> None:
    """Seed a ChatArtifactIndex document."""
    art_id = _artifact_id(session_id, filename, version)
    db.document(
        f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{art_id}"
    ).set(
        {
            "artifact_id": art_id,
            "session_id": session_id,
            "filename": filename,
            "version": version,
        }
    )


# ---------------------------------------------------------------------------
# Teardown fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_emulator() -> Iterator[None]:
    """Delete all seeded documents (including subcollections) after each test."""
    db = _emulator_client()
    yield
    for coll in db.collections():
        for doc in coll.stream():
            db.recursive_delete(doc.reference)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllClean:
    """Blob with matching session AND artifact doc → all_clean, zero orphans."""

    def test_all_clean_blob(self) -> None:
        db = _emulator_client()
        account_id, session_id, user_id = "acc_clean", "sess_clean", "uid_clean"
        filename, version = "report.pdf", 0

        _seed_session(db, account_id, session_id, user_id)
        _seed_artifact(db, account_id, session_id, filename, version)

        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name(user_id, session_id, filename, version))]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["scanned_blobs"] == 1
        assert summary["missing_metadata"] == 0
        assert summary["missing_session"] == 0
        assert summary["errored"] == 0


class TestMissingMetadata:
    """Session exists but no artifact doc → missing_metadata orphan."""

    def test_missing_metadata_blob(self) -> None:
        db = _emulator_client()
        account_id, session_id, user_id = "acc_meta", "sess_meta", "uid_meta"
        filename, version = "data.csv", 0

        _seed_session(db, account_id, session_id, user_id)
        # deliberately NOT seeding the artifact doc

        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name(user_id, session_id, filename, version))]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["scanned_blobs"] == 1
        assert summary["missing_metadata"] == 1
        assert summary["missing_session"] == 0
        assert summary["errored"] == 0


class TestMissingSession:
    """No side-table row at all → missing_session orphan."""

    def test_missing_session_blob(self) -> None:
        db = _emulator_client()
        # No Firestore documents seeded

        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name("uid_orphan", "sess_orphan", "file.txt", 0))]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["scanned_blobs"] == 1
        assert summary["missing_session"] == 1
        assert summary["missing_metadata"] == 0
        assert summary["errored"] == 0


class TestMalformedPath:
    """Blob whose name doesn't match GCS path schema → malformed_paths, not scanned."""

    def test_malformed_path_skipped(self) -> None:
        db = _emulator_client()
        storage = _FakeStorageClient([_FakeBlob(f"{_APP_NAME}/too/few/segments")])
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["malformed_paths"] == 1
        assert summary["scanned_blobs"] == 0
        assert summary["errored"] == 0

    def test_non_integer_version_is_malformed(self) -> None:
        db = _emulator_client()
        storage = _FakeStorageClient(
            [_FakeBlob(f"{_APP_NAME}/uid/sess/file.pdf/notanumber")]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["malformed_paths"] == 1
        assert summary["scanned_blobs"] == 0


class TestLimitFlag:
    """--limit N caps the total GCS blobs enumerated."""

    def test_limit_one_processes_exactly_one_blob(self) -> None:
        db = _emulator_client()
        # Three orphan blobs seeded but limit=1 should stop after the first.
        blobs = [
            _FakeBlob(_blob_name("uid_a", "sess_a", "a.pdf", 0)),
            _FakeBlob(_blob_name("uid_b", "sess_b", "b.pdf", 0)),
            _FakeBlob(_blob_name("uid_c", "sess_c", "c.pdf", 0)),
        ]
        storage = _FakeStorageClient(blobs)
        summary = cli.scan_for_gcs_blob_orphans(
            db, storage, bucket_name=_TEST_BUCKET, limit=1
        )

        # Only 1 blob was processed (the other 2 were never reached).
        assert summary["scanned_blobs"] == 1
        assert summary["missing_metadata"] + summary["missing_session"] == 1


class TestAccountIdFilter:
    """--account-id restricts the scan to one account."""

    def test_filter_excludes_other_accounts(self) -> None:
        db = _emulator_client()
        target_account = "acc_target"
        other_account = "acc_other"

        _seed_session(db, target_account, "sess_t", "uid_t")
        _seed_session(db, other_account, "sess_o", "uid_o")
        # No artifact docs → both would be missing_metadata if unfiltered

        storage = _FakeStorageClient(
            [
                _FakeBlob(_blob_name("uid_t", "sess_t", "t.pdf", 0)),
                _FakeBlob(_blob_name("uid_o", "sess_o", "o.pdf", 0)),
            ]
        )
        summary = cli.scan_for_gcs_blob_orphans(
            db, storage, account_id=target_account, bucket_name=_TEST_BUCKET
        )

        # Only the target account blob is counted.
        assert summary["scanned_blobs"] == 1
        assert summary["missing_metadata"] == 1

    def test_filter_with_no_matching_blobs_returns_zeros(self) -> None:
        db = _emulator_client()
        _seed_session(db, "acc_other", "sess_other", "uid_other")

        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name("uid_other", "sess_other", "f.pdf", 0))]
        )
        summary = cli.scan_for_gcs_blob_orphans(
            db, storage, account_id="acc_nobody", bucket_name=_TEST_BUCKET
        )

        assert summary["scanned_blobs"] == 0
        assert summary["missing_metadata"] == 0
        assert summary["missing_session"] == 0


class TestEmptyBucket:
    """No blobs at all → all summary counters are zero."""

    def test_empty_bucket_returns_zero_summary(self) -> None:
        db = _emulator_client()
        storage = _FakeStorageClient([])
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["scanned_blobs"] == 0
        assert summary["missing_metadata"] == 0
        assert summary["missing_session"] == 0
        assert summary["malformed_paths"] == 0
        assert summary["errored"] == 0


class TestAccountIdFilterMissingSession:
    """--account-id filter excludes missing_session blobs (ownership unconfirmable)."""

    def test_missing_session_excluded_when_account_filter_set(self) -> None:
        db = _emulator_client()
        # No session seeded — blob's session_id resolves to None.
        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name("uid_anon", "sess_anon", "f.pdf", 0))]
        )
        summary = cli.scan_for_gcs_blob_orphans(
            db, storage, account_id="acc_filter", bucket_name=_TEST_BUCKET
        )

        # Blob is excluded (can't confirm it belongs to acc_filter) — all zeros.
        assert summary["scanned_blobs"] == 0
        assert summary["missing_session"] == 0

    def test_missing_session_reported_without_account_filter(self) -> None:
        db = _emulator_client()
        storage = _FakeStorageClient(
            [_FakeBlob(_blob_name("uid_anon", "sess_anon", "f.pdf", 0))]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["missing_session"] == 1


class TestInvalidPathComponents:
    """Blobs with invalid user_id or filename are counted as errored, not scanned."""

    def test_invalid_user_id_counted_as_errored(self) -> None:
        db = _emulator_client()
        # user_id contains '@' — passes segment count but fails _FIRESTORE_ID_RE
        storage = _FakeStorageClient(
            [_FakeBlob(f"{_APP_NAME}/evil@user/sess_ok/file.pdf/0")]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["errored"] == 1
        assert summary["scanned_blobs"] == 0

    def test_invalid_filename_counted_as_errored(self) -> None:
        db = _emulator_client()
        # filename contains newline — fails _FILENAME_RE
        storage = _FakeStorageClient(
            [_FakeBlob(f"{_APP_NAME}/uid_ok/sess_ok/file\nname/0")]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["errored"] == 1
        assert summary["scanned_blobs"] == 0


class TestSessionAccountCache:
    """Multiple blobs in the same session reuse the cached account_id lookup."""

    def test_multiple_blobs_same_session_classified_correctly(self) -> None:
        db = _emulator_client()
        account_id, session_id, user_id = "acc_cached", "sess_cached", "uid_cached"

        _seed_session(db, account_id, session_id, user_id)
        # Only one artifact doc; second blob is an orphan.
        _seed_artifact(db, account_id, session_id, "file1.pdf", 0)

        storage = _FakeStorageClient(
            [
                _FakeBlob(_blob_name(user_id, session_id, "file1.pdf", 0)),
                _FakeBlob(_blob_name(user_id, session_id, "file2.pdf", 0)),
            ]
        )
        summary = cli.scan_for_gcs_blob_orphans(db, storage, bucket_name=_TEST_BUCKET)

        assert summary["scanned_blobs"] == 2
        assert summary["missing_metadata"] == 1  # file2.pdf has no artifact doc
        assert summary["missing_session"] == 0
        assert summary["errored"] == 0
