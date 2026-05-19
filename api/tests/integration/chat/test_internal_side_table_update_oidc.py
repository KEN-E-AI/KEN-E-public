"""Integration tests: POST /api/v1/internal/chat/side-table/update (CH-PRD-01 §7 AC-16).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_internal_side_table_update_oidc.py -v

`CHAT_INTERNAL_OIDC_SKIP=true` is set by the auth fixture for the happy-path
tests so the suite does not require real Google service-account credentials.
`test_missing_auth_returns_401` temporarily unsets it to exercise the real
verification path's missing-header branch.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)


_ACCOUNT_ID = "acc_ch11_test"
_SESSION_ID = "sess_ch11_test_001"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _seed_chat_session(db: Any) -> None:
    """Write a minimal ChatSessionMetadata doc for the test session."""
    from src.kene_api.models.chat import ChatSessionMetadata

    metadata = ChatSessionMetadata(
        session_id=_SESSION_ID,
        user_id="uid_ch11_test",
        account_id=_ACCOUNT_ID,
        organization_id="org_ch11_test",
        model_id="gemini-2.5-flash",
        context_window_max=1_048_576,
        message_count=0,
        created_at=_NOW,
        updated_at=_NOW,
    )
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").set(
        metadata.model_dump()
    )


def _purge_idempotency_keys(db: Any) -> None:
    """Best-effort wipe of the chat_idempotency_keys collection."""
    for doc in db.collection("chat_idempotency_keys").stream():
        doc.reference.delete()


def _purge_session(db: Any) -> None:
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """TestClient wired to the real Firestore emulator (no MagicMock)."""
    os.environ.setdefault("CHAT_INTERNAL_OIDC_SKIP", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")

    # Reset any singleton clients that prior tests may have warmed against a
    # different project so this run picks up FIRESTORE_EMULATOR_HOST cleanly.
    from src.kene_api.chat.side_table import get_chat_side_table_service
    from src.kene_api.dependencies import get_firestore_client

    get_firestore_client.cache_clear()
    get_chat_side_table_service.cache_clear()

    from src.kene_api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_emulator_state() -> Generator[None, None, None]:
    """Seed the chat_sessions doc and clear idempotency keys before each test."""
    db = _emulator_client()
    _purge_idempotency_keys(db)
    _seed_chat_session(db)
    yield
    _purge_idempotency_keys(db)
    _purge_session(db)


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": _SESSION_ID,
        "account_id": _ACCOUNT_ID,
        "delta": {"message_count": {"_increment": 1}},
        "idempotency_key": "test-idem-key-001",
    }
    base.update(overrides)
    return base


class TestSideTableUpdateOIDC:
    def test_returns_200_applied_on_first_call(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(),
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "applied"

        # Verify the delta was applied to the side-table doc.
        db = _emulator_client()
        snap = db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
        ).get()
        assert snap.exists
        assert snap.to_dict()["message_count"] == 1

    def test_duplicate_idempotency_key_returns_duplicate(
        self, client: TestClient
    ) -> None:
        payload = _payload(idempotency_key="dup-key-001")
        first = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=payload,
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert first.status_code == 200
        assert first.json()["status"] == "applied"

        second = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=payload,
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"

        # message_count must not have advanced past 1.
        db = _emulator_client()
        snap = db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
        ).get()
        assert snap.to_dict()["message_count"] == 1

    def test_missing_auth_returns_401(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Flip OIDC_SKIP off so the real auth path runs and a missing header 401s.
        monkeypatch.setenv("CHAT_INTERNAL_OIDC_SKIP", "false")
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key="no-auth-test"),
        )
        assert response.status_code == 401

    def test_invalid_request_body_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json={"session_id": "only-session"},
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 422

    def test_idempotency_key_too_long_returns_422(self, client: TestClient) -> None:
        long_key = "x" * 300
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key=long_key),
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 422
