"""Integration tests for GET /conversations/{session_id}/artifacts.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_get_artifacts_endpoint.py -v
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_ID = "acc_ch45_test"
_SESSION_ID = "sess_ch45_real_001"
_USER_ID = "user_ch45_test"
_ORG_ID = "org_ch45_test"
_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
_GCS_PATH = (
    "gs://ken-e-dev-files-us/ken_e_chatbot/user_01/sess_ch45_real_001/report.pdf/0"
)


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _seed_session(
    db: Any,
    *,
    session_id: str = _SESSION_ID,
    user_id: str = _USER_ID,
    account_id: str = _ACCOUNT_ID,
    organization_id: str = _ORG_ID,
    deleted_at: datetime | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    doc = {
        "session_id": session_id,
        "user_id": user_id,
        "account_id": account_id,
        "organization_id": organization_id,
        "model_id": "gemini-2.5-flash",
        "created_at": now,
        "updated_at": now,
        "last_viewed_at": None,
        "deleted_at": deleted_at,
    }
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(doc)


def _seed_artifact(
    db: Any,
    artifact_id: str,
    filename: str = "report.pdf",
    gcs_path: str = _GCS_PATH,
    *,
    session_id: str = _SESSION_ID,
    account_id: str = _ACCOUNT_ID,
    created_at: datetime | None = None,
) -> None:
    ts = created_at or _NOW
    doc = {
        "artifact_id": artifact_id,
        "session_id": session_id,
        "filename": filename,
        "mime_type": "application/pdf",
        "size_bytes": 1024,
        "version": 0,
        "gcs_path": gcs_path,
        "created_by_tool": "build_report",
        "created_at": ts,
    }
    db.document(
        f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}"
    ).set(doc)


def _make_mock_storage_client(
    fake_url: str = "https://storage.googleapis.com/signed",
) -> MagicMock:
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = fake_url
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    return mock_client


class TestGetArtifactsEndpointIntegration:
    """Integration tests using the Firestore emulator."""

    def setup_method(self) -> None:
        self.db = _emulator_client()
        self.db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()
        artifacts_ref = self.db.collection(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts"
        )
        for doc in artifacts_ref.stream():
            doc.reference.delete()

    def _run_handler(
        self,
        session_id: str = _SESSION_ID,
        user_id: str = _USER_ID,
        storage_client: MagicMock | None = None,
    ) -> Any:
        import asyncio

        from src.kene_api.auth.models import UserContext
        from src.kene_api.chat.side_table import ChatSessionSideTableService
        from src.kene_api.routers import chat as chat_module

        svc = ChatSessionSideTableService(db=self.db)
        mock_client = storage_client or _make_mock_storage_client()

        user_ctx = UserContext(
            user_id=user_id,
            email="test@example.com",
            organization_permissions={},
            account_permissions={},
        )

        async def _call() -> Any:
            with (
                patch.object(
                    chat_module, "get_chat_side_table_service", return_value=svc
                ),
                patch.object(chat_module, "WEAVE_AVAILABLE", False),
                patch(
                    "src.kene_api.chat.artifacts._get_storage_client",
                    return_value=mock_client,
                ),
            ):
                from src.kene_api.routers.chat import get_session_artifacts

                return await get_session_artifacts(
                    session_id=session_id,
                    user_context=user_ctx,
                )

        return asyncio.run(_call())

    def test_empty_subcollection_returns_empty_items(self) -> None:
        """AC: Empty artifact subcollection returns items=[]."""
        _seed_session(self.db)
        resp = self._run_handler()
        assert resp.items == []

    def test_two_artifacts_both_returned_with_signed_urls(self) -> None:
        """AC: Two artifacts yield two items each with signed_url and expiry."""
        _seed_session(self.db)
        _seed_artifact(self.db, "art_001", created_at=_NOW + timedelta(seconds=10))
        _seed_artifact(self.db, "art_002", created_at=_NOW)

        fake_url = "https://storage.googleapis.com/signed-url"
        resp = self._run_handler(storage_client=_make_mock_storage_client(fake_url))

        assert len(resp.items) == 2
        for item in resp.items:
            assert item.signed_url == fake_url
            assert item.signed_url_expires_at > datetime.now(timezone.utc)
        artifact_ids = {item.artifact_index.artifact_id for item in resp.items}
        assert artifact_ids == {"art_001", "art_002"}

    def test_artifacts_sorted_newest_first(self) -> None:
        """Artifacts are returned ordered by created_at DESC."""
        _seed_session(self.db)
        newer_ts = _NOW + timedelta(seconds=60)
        _seed_artifact(self.db, "art_older", created_at=_NOW)
        _seed_artifact(self.db, "art_newer", created_at=newer_ts)

        resp = self._run_handler()

        assert len(resp.items) == 2
        assert resp.items[0].artifact_index.artifact_id == "art_newer"
        assert resp.items[1].artifact_index.artifact_id == "art_older"

    def test_404_when_session_missing_from_side_table(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(session_id="sess_does_not_exist")

        assert exc_info.value.status_code == 404

    def test_404_when_session_belongs_to_different_user(self) -> None:
        from fastapi import HTTPException

        _seed_session(self.db, user_id="other_user")

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler(user_id="different_user")

        assert exc_info.value.status_code == 404

    def test_404_for_tombstoned_session(self) -> None:
        """Sessions with deleted_at set are treated as not-found."""
        from fastapi import HTTPException

        _seed_session(self.db, deleted_at=datetime.now(timezone.utc))

        with pytest.raises(HTTPException) as exc_info:
            self._run_handler()

        assert exc_info.value.status_code == 404

    def test_signing_failure_drops_artifact_continues(self) -> None:
        """A signing failure drops the row but returns the others."""
        _seed_session(self.db)
        _seed_artifact(self.db, "art_good", gcs_path=_GCS_PATH)
        _seed_artifact(self.db, "art_bad", gcs_path="not-a-valid-gcs-path")

        resp = self._run_handler()

        # Only the valid artifact should appear
        assert len(resp.items) == 1
        assert resp.items[0].artifact_index.artifact_id == "art_good"
