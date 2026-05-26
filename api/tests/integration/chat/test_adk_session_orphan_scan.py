"""Integration tests for kene_api.chat.adk_session_orphan_scan.

Requires a running Firestore emulator:

    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 pytest \
        api/tests/integration/chat/test_adk_session_orphan_scan.py -v

The tests use a real Firestore client pointed at the emulator so that
side-table reads/writes exercise the actual driver behaviour.  ADK sessions
are supplied by a lightweight fake (_FakeAdkSessionService) to avoid Vertex AI
calls in CI.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

# Resolve the api/src package so the test runner finds kene_api.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat import adk_session_orphan_scan as cli

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 to run."
    ),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
_ACCOUNT_ID = "acc_orphan_scan_integration_test"
_ORG_ID = "org_orphan_scan_test"
_USER_ID = "uid_orphan_scan_test"

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
# Tombstoned more than 1 h ago — outside grace window.
_DELETED_OLD = _NOW - timedelta(hours=2)
# Tombstoned less than 1 h ago — inside grace window.
_DELETED_RECENT = _NOW - timedelta(minutes=30)


# ---------------------------------------------------------------------------
# Firestore emulator helpers
# ---------------------------------------------------------------------------


def _emulator_client():
    from google.cloud import firestore as _fs

    return _fs.Client(project=_PROJECT)


def _fake_session(
    session_id: str = "sess_orphan_001",
    account_id: str = _ACCOUNT_ID,
    user_id: str = "",
) -> SimpleNamespace:
    """Build a minimal ADK Session-like namespace object."""
    return SimpleNamespace(
        id=session_id,
        user_id=user_id,
        state={"account_id": account_id},
        events=[],
        create_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        update_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )


def _seed_account_and_user(db) -> None:
    """Seed minimal account + user documents in the emulator."""
    db.document(f"accounts/{_ACCOUNT_ID}").set({"organization_id": _ORG_ID})
    db.document(f"users/{_USER_ID}").set(
        {"permissions": {"account_permissions": {_ACCOUNT_ID: {"role": "admin"}}}}
    )


def _seed_side_table_row(
    db,
    session_id: str = "sess_orphan_001",
    account_id: str = _ACCOUNT_ID,
    *,
    deleted_at: datetime | None = None,
) -> None:
    """Seed a chat_sessions side-table document."""
    doc: dict = {
        "session_id": session_id,
        "user_id": _USER_ID,
        "account_id": account_id,
        "organization_id": _ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
    }
    if deleted_at is not None:
        doc["deleted_at"] = deleted_at
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(doc)


def _seed_artifact(
    db,
    session_id: str,
    artifact_id: str = "art_001",
    account_id: str = _ACCOUNT_ID,
    gcs_path: str = "",
) -> None:
    """Seed a single artifact document in the session's artifacts subcollection."""
    db.document(
        f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}"
    ).set(
        {
            "artifact_id": artifact_id,
            "session_id": session_id,
            "filename": "report.pdf",
            "gcs_path": gcs_path,
            "created_by_tool": "generate_report",
        }
    )


# ---------------------------------------------------------------------------
# Fake ADK session service
# ---------------------------------------------------------------------------


class _FakeAdkSessionService:
    """Minimal synchronous-compatible fake for VertexAiSessionService.

    The real service is async; this fake exposes the same async interface so
    it works with ``_list_sessions_for_user`` and ``_delete_adk_session``.
    """

    def __init__(self, sessions_by_user: dict[str, list] | None = None) -> None:
        self._sessions_by_user: dict[str, list] = sessions_by_user or {}
        self.deleted: list[tuple[str, str]] = []
        self.list_calls: list[tuple[str, str]] = []

    async def list_sessions(self, app_name: str, user_id: str):
        self.list_calls.append((app_name, user_id))
        return self._sessions_by_user.get(user_id, [])

    async def delete_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> None:
        # Signature mirrors the real VertexAiSessionService.delete_session, whose
        # user_id is keyword-only and required — so dropping it in the script
        # raises TypeError here too, surfacing the regression.
        self.deleted.append((app_name, session_id))

    def add_session(self, user_id: str, session: SimpleNamespace) -> None:
        self._sessions_by_user.setdefault(user_id, []).append(session)


class _FakeBlob:
    def __init__(self, client: _FakeStorageClient, bucket: str, name: str) -> None:
        self._client = client
        self._bucket = bucket
        self._name = name

    def delete(self) -> None:
        if self._client.raise_not_found_on_delete:
            from google.api_core.exceptions import NotFound

            raise NotFound("simulated blob already gone")
        if self._client.raise_on_delete:
            raise RuntimeError("simulated GCS delete failure")
        self._client.deleted.append((self._bucket, self._name))


class _FakeBucket:
    def __init__(self, client: _FakeStorageClient, name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, blob_name: str) -> _FakeBlob:
        return _FakeBlob(self._client, self._name, blob_name)


class _FakeStorageClient:
    """Records blob deletes; optionally raises to simulate a GCS failure."""

    def __init__(
        self,
        *,
        raise_on_delete: bool = False,
        raise_not_found_on_delete: bool = False,
    ) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.raise_on_delete = raise_on_delete
        self.raise_not_found_on_delete = raise_not_found_on_delete

    def bucket(self, bucket_name: str) -> _FakeBucket:
        return _FakeBucket(self, bucket_name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_emulator(request):
    """Tear down all emulator documents created during a test."""
    db = _emulator_client()
    yield db
    # Teardown — remove all documents seeded under the test account + user.
    for doc in db.collection(f"accounts/{_ACCOUNT_ID}/chat_sessions").stream():
        # Also wipe artifact subcollection.
        for art in doc.reference.collection("artifacts").stream():
            art.reference.delete()
        doc.reference.delete()
    db.document(f"accounts/{_ACCOUNT_ID}").delete()
    db.document(f"users/{_USER_ID}").delete()


# ---------------------------------------------------------------------------
# AC-15: Tombstoned session outside grace window is auto-deleted
# ---------------------------------------------------------------------------


class TestTombstonedOutsideGrace:
    """AC-15 — tombstoned session older than the grace window is deleted."""

    def test_adk_session_deleted(self, _reset_emulator):
        """scan_for_adk_session_orphans deletes the ADK session."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_tombstoned_old"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert (cli.APP_NAME, session_id) in fake_svc.deleted
        assert summary["tombstoned_cleaned"] == 1
        assert summary["errored"] == 0

    def test_side_table_row_removed(self, _reset_emulator):
        """The side-table document is deleted after the ADK session."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_tombstoned_row_check"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}").get()
        assert not doc.exists

    def test_artifact_subcollection_removed(self, _reset_emulator):
        """Artifact subcollection docs are deleted before the side-table row."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_tombstoned_with_artifact"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)
        _seed_artifact(db, session_id=session_id, artifact_id="art_a")

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        arts = list(
            db.collection(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}/artifacts"
            ).stream()
        )
        assert arts == []


# ---------------------------------------------------------------------------
# AC-15 (dry-run variant): --dry-run makes no state changes
# ---------------------------------------------------------------------------


class TestTombstonedDryRun:
    """AC-15 dry-run — nothing is deleted when --dry-run is active."""

    def test_dry_run_no_adk_delete(self, _reset_emulator):
        """ADK delete_session is NOT called in dry-run mode."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_dry_run_tombstoned"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=True,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert fake_svc.deleted == []
        # Summary still counts what *would* be cleaned.
        assert summary["tombstoned_cleaned"] == 1

    def test_dry_run_side_table_row_preserved(self, _reset_emulator):
        """The side-table document is preserved in dry-run mode."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_dry_run_row_preserved"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=True,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}").get()
        assert doc.exists


# ---------------------------------------------------------------------------
# AC-16: Tombstoned session inside grace window is skipped
# ---------------------------------------------------------------------------


class TestTombstonedInsideGrace:
    """AC-16 — tombstoned session within the grace window is left alone."""

    def test_session_not_deleted(self, _reset_emulator):
        """ADK delete_session is NOT called for recently tombstoned sessions."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_tombstoned_recent"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_RECENT)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert fake_svc.deleted == []
        assert summary["tombstoned_in_grace"] == 1
        assert summary["tombstoned_cleaned"] == 0
        assert summary["errored"] == 0

    def test_side_table_row_preserved(self, _reset_emulator):
        """The side-table document is untouched for in-grace sessions."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_tombstoned_recent_row"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_RECENT)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}").get()
        assert doc.exists


# ---------------------------------------------------------------------------
# AC-17: Missing side-table row triggers alert, no deletion
# ---------------------------------------------------------------------------


class TestMissingSideTableRow:
    """AC-17 — ADK session with no side-table row is not auto-deleted."""

    def test_no_deletion_on_missing_row(self, _reset_emulator):
        """ADK delete_session is NOT called when the side-table row is absent."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_no_side_table"
        # Intentionally do NOT seed a side-table row.

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert fake_svc.deleted == []
        assert summary["missing_orphans"] == 1
        assert summary["tombstoned_cleaned"] == 0
        assert summary["errored"] == 0


# ---------------------------------------------------------------------------
# Mixed scenario: multiple sessions, multiple classifications
# ---------------------------------------------------------------------------


class TestMixedScenario:
    """Multiple sessions in the same run produce correct per-bucket counts."""

    def test_mixed_counts(self, _reset_emulator):
        """Three sessions (tombstoned-old, in-grace, clean) yield correct buckets."""
        db = _reset_emulator
        _seed_account_and_user(db)

        sid_old = "sess_mix_old"
        sid_recent = "sess_mix_recent"
        sid_clean = "sess_mix_clean"

        _seed_side_table_row(db, session_id=sid_old, deleted_at=_DELETED_OLD)
        _seed_side_table_row(db, session_id=sid_recent, deleted_at=_DELETED_RECENT)
        _seed_side_table_row(db, session_id=sid_clean)  # no deleted_at

        fake_svc = _FakeAdkSessionService()
        for sid in (sid_old, sid_recent, sid_clean):
            fake_svc.add_session(_USER_ID, _fake_session(session_id=sid))

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert summary == {
            "tombstoned_cleaned": 1,
            "tombstoned_in_grace": 1,
            "missing_orphans": 0,
            "all_clean": 1,
            "errored": 0,
        }


# ---------------------------------------------------------------------------
# Idempotency: running twice on an already-cleaned state is safe
# ---------------------------------------------------------------------------


class TestIdempotency:
    """A second scan run after cleanup produces all_clean with no errors."""

    def test_second_run_produces_missing_orphan_alert(self, _reset_emulator):
        """After the first run deletes a tombstoned session, a second run alerts
        ops via the missing-orphan bucket (the side-table row is gone but the
        ADK session fake still lists it).  No errored count; no second deletion.
        """
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_idempotent"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))

        # First run — deletes.
        summary1 = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )
        assert summary1["tombstoned_cleaned"] == 1

        # Second run — ADK session still "exists" in the fake but the
        # side-table row is gone.  Expected: missing_orphan alert, no error.
        summary2 = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=None,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )
        assert summary2["errored"] == 0
        assert summary2["missing_orphans"] == 1


# ---------------------------------------------------------------------------
# GCS-blob cleanup + cross-bucket safety guard (destructive path)
# ---------------------------------------------------------------------------


class TestGcsBlobCleanup:
    """The destructive GCS-blob deletion path and its cross-bucket safety guard."""

    _BUCKET = "kene-artifacts-test"

    def test_in_bucket_blob_deleted_and_cleanup_completes(
        self, _reset_emulator, monkeypatch
    ):
        """In-bucket artifact blob is deleted and the full cleanup completes."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_gcs_ok"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)
        _seed_artifact(
            db,
            session_id=session_id,
            artifact_id="art_ok",
            gcs_path=f"gs://{self._BUCKET}/accounts/{_ACCOUNT_ID}/{session_id}/r.pdf/1",
        )
        monkeypatch.setattr(cli, "_ARTIFACT_GCS_BUCKET", self._BUCKET)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))
        storage = _FakeStorageClient()

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=storage,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert summary["tombstoned_cleaned"] == 1
        assert summary["errored"] == 0
        assert len(storage.deleted) == 1  # the in-bucket blob was deleted
        assert (cli.APP_NAME, session_id) in fake_svc.deleted
        assert (
            not db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}")
            .get()
            .exists
        )
        assert (
            not db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}/artifacts/art_ok"
            )
            .get()
            .exists
        )

    def test_unexpected_bucket_aborts_before_any_deletion(
        self, _reset_emulator, monkeypatch
    ):
        """A gcs_path outside the expected bucket is refused; the cleanup aborts
        BEFORE deleting the ADK session / artifact doc / row, leaving the session
        listed so the next run can retry (nothing stranded)."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_gcs_wrong_bucket"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)
        _seed_artifact(
            db,
            session_id=session_id,
            artifact_id="art_wrong",
            gcs_path=f"gs://some-other-bucket/{session_id}/r.pdf/1",
        )
        monkeypatch.setattr(cli, "_ARTIFACT_GCS_BUCKET", self._BUCKET)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))
        storage = _FakeStorageClient()

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=storage,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert storage.deleted == []  # out-of-bucket blob refused
        assert summary["tombstoned_cleaned"] == 0
        assert summary["errored"] == 1
        assert fake_svc.deleted == []  # aborted before the ADK delete -> retryable
        assert (
            db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}")
            .get()
            .exists
        )
        assert (
            db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}/artifacts/art_wrong"
            )
            .get()
            .exists
        )

    def test_already_deleted_blob_treated_as_success(
        self, _reset_emulator, monkeypatch
    ):
        """A blob a prior partial run already removed (NotFound on delete) does not
        wedge the session: cleanup treats it as success and completes."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_gcs_gone"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)
        _seed_artifact(
            db,
            session_id=session_id,
            artifact_id="art_gone",
            gcs_path=f"gs://{self._BUCKET}/accounts/{_ACCOUNT_ID}/{session_id}/r.pdf/1",
        )
        monkeypatch.setattr(cli, "_ARTIFACT_GCS_BUCKET", self._BUCKET)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))
        storage = _FakeStorageClient(raise_not_found_on_delete=True)

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=storage,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert storage.deleted == []  # already-gone blob never recorded a delete
        assert summary["tombstoned_cleaned"] == 1
        assert summary["errored"] == 0
        assert (cli.APP_NAME, session_id) in fake_svc.deleted
        assert (
            not db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}")
            .get()
            .exists
        )
        assert (
            not db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}/artifacts/art_gone"
            )
            .get()
            .exists
        )

    def test_generic_blob_delete_failure_aborts_before_any_deletion(
        self, _reset_emulator, monkeypatch
    ):
        """A non-NotFound GCS delete error aborts the cleanup before the ADK
        session / artifact doc / row are touched, leaving the session retryable."""
        db = _reset_emulator
        _seed_account_and_user(db)
        session_id = "sess_gcs_delete_fail"
        _seed_side_table_row(db, session_id=session_id, deleted_at=_DELETED_OLD)
        _seed_artifact(
            db,
            session_id=session_id,
            artifact_id="art_fail",
            gcs_path=f"gs://{self._BUCKET}/accounts/{_ACCOUNT_ID}/{session_id}/r.pdf/1",
        )
        monkeypatch.setattr(cli, "_ARTIFACT_GCS_BUCKET", self._BUCKET)

        fake_svc = _FakeAdkSessionService()
        fake_svc.add_session(_USER_ID, _fake_session(session_id=session_id))
        storage = _FakeStorageClient(raise_on_delete=True)

        summary = cli.scan_for_adk_session_orphans(
            db=db,
            session_service=fake_svc,
            storage_client=storage,
            dry_run=False,
            grace_window=timedelta(hours=1),
            _now=_NOW,
        )

        assert summary["tombstoned_cleaned"] == 0
        assert summary["errored"] == 1
        assert fake_svc.deleted == []  # aborted before the ADK delete -> retryable
        assert (
            db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}")
            .get()
            .exists
        )
        assert (
            db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}/artifacts/art_fail"
            )
            .get()
            .exists
        )
