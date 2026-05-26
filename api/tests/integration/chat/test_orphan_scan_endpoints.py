"""Integration tests: POST /api/v1/internal/chat/orphan-scan/{gcs,adk-session} (CH-PRD-05 AC-11).

These tests exercise the HTTP routing and OIDC-auth layer only.  The
underlying scan orchestrators (``run_gcs_orphan_scan`` /
``run_adk_session_orphan_scan``) are patched to return canned summaries so
the suite does not require a Firestore emulator, GCS bucket, or Vertex AI
ADK session service.

``CHAT_INTERNAL_OIDC_SKIP=true`` is set by the fixture so tests pass without
real Google service-account credentials.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

_GCS_SUMMARY: dict[str, int] = {
    "scanned_blobs": 42,
    "missing_metadata": 0,
    "missing_session": 1,
    "malformed_paths": 0,
    "duration_ms": 1234,
    "errored": 0,
}

_ADK_SUMMARY: dict[str, int] = {
    "tombstoned_cleaned": 3,
    "tombstoned_in_grace": 1,
    "missing_orphans": 0,
    "all_clean": 10,
    "errored": 0,
}

_ADK_SUMMARY_WITH_ERRORS: dict[str, int] = {
    "tombstoned_cleaned": 0,
    "tombstoned_in_grace": 0,
    "missing_orphans": 0,
    "all_clean": 0,
    "errored": 2,
}


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    os.environ.setdefault("CHAT_INTERNAL_OIDC_SKIP", "true")
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")

    from src.kene_api.dependencies import get_firestore_client

    get_firestore_client.cache_clear()

    from src.kene_api.main import app

    with TestClient(app) as c:
        yield c


_AUTH_HEADER = {"Authorization": "Bearer dummy-skip-token"}


class TestGcsOrphanScanEndpoint:
    def test_returns_200_with_summary(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.routers.chat.run_gcs_orphan_scan",
            new=AsyncMock(return_value=_GCS_SUMMARY),
        ):
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/gcs",
                headers=_AUTH_HEADER,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["scanned_blobs"] == 42
        assert body["missing_session"] == 1
        assert body["errored"] == 0

    def test_returns_200_even_when_errored_nonzero(self, client: TestClient) -> None:
        errored_summary = {**_GCS_SUMMARY, "errored": 3}
        with patch(
            "src.kene_api.routers.chat.run_gcs_orphan_scan",
            new=AsyncMock(return_value=errored_summary),
        ):
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/gcs",
                headers=_AUTH_HEADER,
            )
        assert response.status_code == 200
        assert response.json()["errored"] == 3

    def test_missing_auth_returns_401(self, client: TestClient) -> None:
        saved = os.environ.pop("CHAT_INTERNAL_OIDC_SKIP", None)
        try:
            response = client.post("/api/v1/internal/chat/orphan-scan/gcs")
        finally:
            if saved is not None:
                os.environ["CHAT_INTERNAL_OIDC_SKIP"] = saved
            else:
                os.environ["CHAT_INTERNAL_OIDC_SKIP"] = "true"
        assert response.status_code == 401


class TestAdkSessionOrphanScanEndpoint:
    def test_returns_200_with_summary(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.routers.chat.run_adk_session_orphan_scan",
            new=AsyncMock(return_value=_ADK_SUMMARY),
        ) as mock_scan:
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/adk-session",
                headers=_AUTH_HEADER,
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tombstoned_cleaned"] == 3
        assert body["all_clean"] == 10
        # dry_run defaults to False
        mock_scan.assert_called_once_with(dry_run=False)

    def test_dry_run_query_param_passed_through(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.routers.chat.run_adk_session_orphan_scan",
            new=AsyncMock(return_value=_ADK_SUMMARY),
        ) as mock_scan:
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/adk-session?dry_run=true",
                headers=_AUTH_HEADER,
            )
        assert response.status_code == 200
        mock_scan.assert_called_once_with(dry_run=True)

    def test_returns_200_even_when_errored_nonzero(self, client: TestClient) -> None:
        with patch(
            "src.kene_api.routers.chat.run_adk_session_orphan_scan",
            new=AsyncMock(return_value=_ADK_SUMMARY_WITH_ERRORS),
        ):
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/adk-session",
                headers=_AUTH_HEADER,
            )
        assert response.status_code == 200
        assert response.json()["errored"] == 2

    def test_missing_auth_returns_401(self, client: TestClient) -> None:
        saved = os.environ.pop("CHAT_INTERNAL_OIDC_SKIP", None)
        try:
            response = client.post(
                "/api/v1/internal/chat/orphan-scan/adk-session"
            )
        finally:
            if saved is not None:
                os.environ["CHAT_INTERNAL_OIDC_SKIP"] = saved
            else:
                os.environ["CHAT_INTERNAL_OIDC_SKIP"] = "true"
        assert response.status_code == 401
