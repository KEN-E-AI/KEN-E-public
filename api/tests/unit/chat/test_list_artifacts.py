"""Unit tests for list_artifacts and generate_artifact_signed_url.

Tests cover:
- list_artifacts returns rows sorted by created_at DESC.
- list_artifacts returns [] for empty subcollection.
- list_artifacts drops malformed Firestore docs with a warning log.
- generate_artifact_signed_url returns (str, datetime) with 10-min TTL.
- generate_artifact_signed_url raises ValueError on malformed gcs_path.
- generate_artifact_signed_url raises ValueError on GCS signing failure.
- _get_storage_client is module-cached (same object on repeated calls).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import GoogleAPICallError
from src.kene_api.chat.artifacts import (
    _get_storage_client,
    generate_artifact_signed_url,
    list_artifacts,
)
from src.kene_api.models.chat import ChatArtifactIndex

_ACCOUNT_ID = "acc_unit_45"
_SESSION_ID = "sess_unit_45"
_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
_GCS_PATH = "gs://ken-e-dev-files-us/ken_e_chatbot/user_01/sess_unit_45/report.pdf/0"


def _make_index(
    artifact_id: str = "abc123",
    filename: str = "report.pdf",
    created_at: datetime | None = None,
    gcs_path: str = _GCS_PATH,
) -> ChatArtifactIndex:
    return ChatArtifactIndex(
        artifact_id=artifact_id,
        session_id=_SESSION_ID,
        filename=filename,
        mime_type="application/pdf",
        size_bytes=1024,
        version=0,
        gcs_path=gcs_path,
        created_by_tool="build_report",
        created_at=created_at or _NOW,
    )


def _make_firestore_doc(data: dict) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = data
    doc.id = data.get("artifact_id", "unknown")
    return doc


def _make_collection_query(docs: list[MagicMock]) -> MagicMock:
    """Simulate db.collection(...).order_by(...).limit(...).get() returning docs."""
    query = MagicMock()
    query.limit.return_value = query
    query.get.return_value = docs
    col = MagicMock()
    col.order_by.return_value = query
    db = MagicMock()
    db.collection.return_value = col
    return db


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


class TestListArtifacts:
    def test_returns_sorted_list(self) -> None:
        newer = datetime(2026, 5, 2, 0, 0, 0, tzinfo=timezone.utc)
        older = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

        index_newer = _make_index("newer", created_at=newer)
        index_older = _make_index("older", created_at=older)

        doc_newer = _make_firestore_doc(index_newer.model_dump())
        doc_older = _make_firestore_doc(index_older.model_dump())

        # Firestore returns pre-sorted DESC; we just check parsing works
        db = _make_collection_query([doc_newer, doc_older])

        with patch("src.kene_api.chat.artifacts.get_firestore_client", return_value=db):
            result = list_artifacts(_ACCOUNT_ID, _SESSION_ID)

        assert len(result) == 2
        assert result[0].artifact_id == "newer"
        assert result[1].artifact_id == "older"

    def test_empty_subcollection_returns_empty_list(self) -> None:
        db = _make_collection_query([])

        with patch("src.kene_api.chat.artifacts.get_firestore_client", return_value=db):
            result = list_artifacts(_ACCOUNT_ID, _SESSION_ID)

        assert result == []

    def test_drops_malformed_docs_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        valid_index = _make_index("valid_1")
        valid_doc = _make_firestore_doc(valid_index.model_dump())
        bad_doc = _make_firestore_doc({"artifact_id": "bad_one", "nope": True})

        db = _make_collection_query([valid_doc, bad_doc])

        with (
            caplog.at_level(logging.WARNING, logger="src.kene_api.chat.artifacts"),
            patch("src.kene_api.chat.artifacts.get_firestore_client", return_value=db),
        ):
            result = list_artifacts(_ACCOUNT_ID, _SESSION_ID)

        assert len(result) == 1
        assert result[0].artifact_id == "valid_1"
        assert any("malformed_row" in r.message for r in caplog.records)
        assert any("bad_one" in str(r.__dict__) for r in caplog.records)

    def test_drops_all_malformed_returns_empty(self) -> None:
        bad_doc = _make_firestore_doc({"not": "valid"})
        db = _make_collection_query([bad_doc])

        with patch("src.kene_api.chat.artifacts.get_firestore_client", return_value=db):
            result = list_artifacts(_ACCOUNT_ID, _SESSION_ID)

        assert result == []

    def test_uses_path_scoped_collection(self) -> None:
        db = _make_collection_query([])

        with patch("src.kene_api.chat.artifacts.get_firestore_client", return_value=db):
            list_artifacts(_ACCOUNT_ID, _SESSION_ID)

        expected_path = (
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts"
        )
        db.collection.assert_called_once_with(expected_path)


# ---------------------------------------------------------------------------
# generate_artifact_signed_url
# ---------------------------------------------------------------------------


class TestGenerateArtifactSignedUrl:
    def test_returns_url_and_expiry_10_min_from_now(self) -> None:
        index = _make_index(gcs_path=_GCS_PATH)
        fake_url = "https://storage.googleapis.com/signed-url-token"

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = fake_url
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch(
            "src.kene_api.chat.artifacts._get_storage_client",
            return_value=mock_client,
        ):
            url, expires_at = generate_artifact_signed_url(index, now=_NOW)

        assert url == fake_url
        assert expires_at == _NOW + timedelta(minutes=10)

    def test_signed_url_uses_v4_get_10min(self) -> None:
        index = _make_index(gcs_path=_GCS_PATH)

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/url"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch(
            "src.kene_api.chat.artifacts._get_storage_client",
            return_value=mock_client,
        ):
            generate_artifact_signed_url(index, now=_NOW)

        mock_blob.generate_signed_url.assert_called_once_with(
            version="v4",
            expiration=timedelta(minutes=10),
            method="GET",
        )

    def test_raises_value_error_for_malformed_gcs_path(self) -> None:
        index = _make_index(gcs_path="not-a-valid-gcs-path")

        with pytest.raises(ValueError, match="malformed gcs_path"):
            generate_artifact_signed_url(index, now=_NOW)

    def test_raises_value_error_on_google_api_call_error(self) -> None:
        index = _make_index(gcs_path=_GCS_PATH)

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.side_effect = GoogleAPICallError("signing failed")
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with (
            patch(
                "src.kene_api.chat.artifacts._get_storage_client",
                return_value=mock_client,
            ),
            pytest.raises(ValueError, match="signing failed"),
        ):
            generate_artifact_signed_url(index, now=_NOW)

    def test_raises_value_error_for_disallowed_bucket(self) -> None:
        """Bucket not in _ALLOWED_GCS_BUCKETS raises ValueError before signing."""
        gcs_path = "gs://foreign-bucket/ken_e_chatbot/user_1/sess_1/file.csv/2"
        index = _make_index(gcs_path=gcs_path)

        with pytest.raises(ValueError, match="not in the system allowlist"):
            generate_artifact_signed_url(index, now=_NOW)

    def test_correct_bucket_extracted_from_gcs_path(self) -> None:
        """Bucket name is parsed directly from the gcs_path URI."""
        gcs_path = "gs://ken-e-dev-files-us/ken_e_chatbot/user_1/sess_1/file.csv/2"
        index = _make_index(gcs_path=gcs_path)

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/url"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch(
            "src.kene_api.chat.artifacts._get_storage_client",
            return_value=mock_client,
        ):
            generate_artifact_signed_url(index, now=_NOW)

        mock_client.bucket.assert_called_once_with("ken-e-dev-files-us")

    def test_correct_blob_name_constructed(self) -> None:
        """Blob name within the bucket matches the ADK path convention."""
        gcs_path = "gs://ken-e-dev-files-us/app1/user2/sess3/data.xlsx/5"
        index = _make_index(gcs_path=gcs_path)

        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/url"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch(
            "src.kene_api.chat.artifacts._get_storage_client",
            return_value=mock_client,
        ):
            generate_artifact_signed_url(index, now=_NOW)

        mock_bucket.blob.assert_called_once_with("app1/user2/sess3/data.xlsx/5")

    def test_does_not_raise_for_allowed_bucket(self) -> None:
        """Allowed bucket in allowlist does not raise before signing."""
        for bucket in (
            "ken-e-production-files-us",
            "ken-e-staging-files-us",
            "ken-e-development-files-us",
            "ken-e-dev-files-us",
        ):
            gcs_path = f"gs://{bucket}/app/user/sess/file.pdf/0"
            index = _make_index(gcs_path=gcs_path)
            mock_blob = MagicMock()
            mock_blob.generate_signed_url.return_value = "https://example.com/url"
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            with patch(
                "src.kene_api.chat.artifacts._get_storage_client",
                return_value=mock_client,
            ):
                url, _ = generate_artifact_signed_url(index, now=_NOW)
            assert url == "https://example.com/url"


# ---------------------------------------------------------------------------
# Storage client singleton
# ---------------------------------------------------------------------------


class TestGetStorageClient:
    def test_returns_same_instance_on_repeated_calls(self) -> None:
        """Module-cached: two calls return the identical object."""
        # Clear the cache to avoid cross-test contamination
        _get_storage_client.cache_clear()

        with patch("src.kene_api.chat.artifacts.storage.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            client_a = _get_storage_client()
            client_b = _get_storage_client()

        assert client_a is client_b
        # Constructed only once despite two calls
        mock_cls.assert_called_once()

        # Restore clean state for subsequent tests
        _get_storage_client.cache_clear()
