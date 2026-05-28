"""Integration tests: chat_v2_enabled flag gate on POST /api/v1/internal/chat/side-table/update.

Verifies AC-17 (PRD §7): with chat_v2_enabled=false the endpoint returns 404;
with chat_v2_enabled=true it proceeds normally; OIDC auth fires before the flag
check (missing token → 401, not 404).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_internal_side_table_update_flag_gate.py -v

`CHAT_INTERNAL_OIDC_SKIP=true` lets the happy-path tests skip real OIDC
credential validation. `test_auth_fires_before_flag_gate` temporarily unsets it
to exercise the 401 path before any flag evaluation.
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

_ACCOUNT_ID = "acc_ch19_flag_gate_test"
_SESSION_ID = "sess_ch19_flag_gate_001"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers (copied from test_internal_side_table_update_oidc.py per Decision A4
# in the approved Implementation Plan — refactoring into a shared module is
# premature while only two files use these helpers)
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _seed_chat_session(db: Any) -> None:
    """Write a minimal ChatSessionMetadata doc for the test session."""
    from src.kene_api.models.chat import ChatSessionMetadata

    metadata = ChatSessionMetadata(
        session_id=_SESSION_ID,
        user_id="uid_ch19_test",
        account_id=_ACCOUNT_ID,
        organization_id="org_ch19_test",
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
    for doc in db.collection("chat_idempotency_keys").stream():
        doc.reference.delete()


def _purge_session(db: Any) -> None:
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()


def _set_flag(db: Any, key: str, *, default_enabled: bool) -> None:
    """Write (or overwrite) a minimal feature_flags/{key} doc."""
    db.collection("feature_flags").document(key).set(
        {
            "key": key,
            "description": f"test flag {key}",
            "default_enabled": default_enabled,
            "is_active": True,
            "targeting_rules": {
                "user_emails": [],
                "email_domains": [],
                "organization_ids": [],
                "account_ids": [],
                "rollout_percentage": 0,
            },
            "bucketing_entity": "account",
            "owner": "test@ken-e.ai",
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        }
    )


def _delete_flag(db: Any, key: str) -> None:
    db.collection("feature_flags").document(key).delete()


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": _SESSION_ID,
        "account_id": _ACCOUNT_ID,
        "delta": {"message_count": {"_increment": 1}},
        "idempotency_key": "ch19-gate-test-001",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Module-scoped TestClient (reused across all tests in this file)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """TestClient wired to the real Firestore emulator (no MagicMock)."""
    os.environ.setdefault("CHAT_INTERNAL_OIDC_SKIP", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")

    from src.kene_api.chat.side_table import get_chat_side_table_service
    from src.kene_api.dependencies import get_firestore_client
    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_firestore_client.cache_clear()
    get_chat_side_table_service.cache_clear()
    get_feature_flag_service.cache_clear()

    from src.kene_api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_emulator_state() -> Generator[None, None, None]:
    """Seed the chat_sessions doc; clear flag and idempotency state before each test."""
    db = _emulator_client()
    _purge_idempotency_keys(db)
    _purge_session(db)
    _seed_chat_session(db)
    _delete_flag(db, "chat_v2_enabled")

    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_feature_flag_service.cache_clear()

    yield

    _purge_idempotency_keys(db)
    _purge_session(db)
    _delete_flag(db, "chat_v2_enabled")
    get_feature_flag_service.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSideTableUpdateFlagGate:
    def test_flag_absent_returns_404(self, client: TestClient) -> None:
        """With no chat_v2_enabled doc (unknown flag), evaluates to False → 404."""
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key="ch19-absent-001"),
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"

    def test_flag_present_default_disabled_returns_404(
        self, client: TestClient
    ) -> None:
        """Flag doc present but default_enabled=False → evaluates to False → 404."""
        db = _emulator_client()
        _set_flag(db, "chat_v2_enabled", default_enabled=False)

        from src.kene_api.services.feature_flag_service import get_feature_flag_service

        get_feature_flag_service.cache_clear()

        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key="ch19-disabled-001"),
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"

    def test_flag_present_default_enabled_returns_200(self, client: TestClient) -> None:
        """Flag doc present with default_enabled=True → endpoint proceeds → 200."""
        db = _emulator_client()
        _set_flag(db, "chat_v2_enabled", default_enabled=True)

        from src.kene_api.services.feature_flag_service import get_feature_flag_service

        get_feature_flag_service.cache_clear()

        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key="ch19-enabled-001"),
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "applied"

    def test_auth_fires_before_flag_gate(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing Authorization header must return 401, NOT 404.

        This proves OIDC auth runs before the flag check — a caller without a
        valid token gets an auth error, not a misleading 'feature disabled' 404.

        The `is_feature_enabled` mock raises `AssertionError` if called, making
        it impossible for the test to pass vacuously: if the flag gate ran before
        auth the test would explode with AssertionError, not return 401.
        """
        # Disable the OIDC skip so the real auth dependency fires.
        monkeypatch.setenv("CHAT_INTERNAL_OIDC_SKIP", "false")

        def _flag_must_not_be_called(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError(
                "is_feature_enabled was called before OIDC auth completed — "
                "the auth-before-flag ordering invariant has been broken."
            )

        monkeypatch.setattr(
            "src.kene_api.routers.chat.is_feature_enabled",
            _flag_must_not_be_called,
        )

        # The flag is absent → if flag ran first, we'd see an AssertionError 500.
        # The real 401 confirms auth runs first.
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json=_payload(idempotency_key="ch19-noauth-001"),
            # No Authorization header
        )
        assert response.status_code == 401
