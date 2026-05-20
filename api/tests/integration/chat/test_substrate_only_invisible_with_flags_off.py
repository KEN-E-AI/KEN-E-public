"""Integration test: AC-18 — no user-visible change with all Chat flags off.

Verifies that with chat_v2_enabled, chat_status_detail_enabled, and
chat_categories_enabled all absent from Firestore (evaluating to False),
the public-facing chat endpoints are unaffected by the flag gate introduced
in CH-19.  The gate only covers the internal ADK-callback endpoint; public
endpoints must remain accessible regardless of flag state.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_substrate_only_invisible_with_flags_off.py -v
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Module-level import ensures the FastAPI app (and all its dependency bindings,
# including get_firestore_service in user_context.py) is imported during test
# *collection*, before the session-scoped `mock_firebase_auth` fixture in
# api/tests/conftest.py patches src.kene_api.firestore.get_firestore_service
# with a MagicMock(return_value=...).  Without this, running the file in
# isolation causes user_context.py to bind to that MagicMock; FastAPI's
# analyze_param() does not skip VAR_POSITIONAL/VAR_KEYWORD parameters and
# instead promotes them to required query params named "args"/"kwargs",
# producing 422 on every request to an endpoint that depends on
# get_current_user_context.
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_CHAT_FLAG_KEYS = (
    "chat_v2_enabled",
    "chat_status_detail_enabled",
    "chat_categories_enabled",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _delete_all_chat_flags(db: Any) -> None:
    for key in _CHAT_FLAG_KEYS:
        db.collection("feature_flags").document(key).delete()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """TestClient with real Firestore emulator for flag evaluation.

    ADK calls are patched at the module level so tests do not require a live
    Vertex AI Agent Engine.
    """
    os.environ.setdefault("CHAT_INTERNAL_OIDC_SKIP", "true")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")

    from src.kene_api.chat.side_table import get_chat_side_table_service
    from src.kene_api.dependencies import get_firestore_client
    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_firestore_client.cache_clear()
    get_chat_side_table_service.cache_clear()
    get_feature_flag_service.cache_clear()

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _flags_absent() -> Generator[None, None, None]:
    """Ensure all three Chat flags are absent (not in Firestore) for every test."""
    db = _emulator_client()
    _delete_all_chat_flags(db)

    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_feature_flag_service.cache_clear()

    yield

    _delete_all_chat_flags(db)
    get_feature_flag_service.cache_clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSubstrateOnlyInvisibleWithFlagsOff:
    """Public chat endpoints must work normally when all Chat flags are absent."""

    def test_list_conversations_returns_200_not_404(self, client: TestClient) -> None:
        """GET /conversations is not flag-gated; absent flags must not produce 404."""
        mock_conversations: list[Any] = []
        with patch(
            "src.kene_api.routers.chat.agent_client.get_user_conversations",
            new=AsyncMock(return_value=mock_conversations),
        ):
            response = client.get(
                "/api/v1/chat/conversations",
                headers={"Authorization": "Bearer test-firebase-token"},
            )

        assert response.status_code == 200
        body = response.json()
        assert "conversations" in body
        assert body["conversations"] == []

    def test_create_conversation_returns_200_not_404(self, client: TestClient) -> None:
        """POST /conversations is not flag-gated; absent flags must not produce 404."""
        response = client.post(
            "/api/v1/chat/conversations",
            json={"conversation_name": "AC-18 substrate test"},
            headers={"Authorization": "Bearer test-firebase-token"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "session_id" in body
        assert body["session_id"].startswith("pending_")

    def test_get_conversation_history_returns_non_flag_gate_response(
        self, client: TestClient
    ) -> None:
        """GET /conversations/{id}/history is not flag-gated.

        Absent flags must not cause a 404 that is attributable to the flag gate.
        A 404 from ADK (session not found) is acceptable and distinct from the
        flag-gate 404 whose detail is exactly 'Not Found'.
        """
        mock_history: dict[str, Any] = {"events": [], "session_id": "test-session"}
        with patch(
            "src.kene_api.routers.chat.agent_client.get_conversation_history",
            new=AsyncMock(return_value=mock_history),
        ):
            response = client.get(
                "/api/v1/chat/conversations/test-session-id/history",
                headers={"Authorization": "Bearer test-firebase-token"},
            )

        assert response.status_code == 200
        assert response.json()["events"] == []

    def test_internal_endpoint_returns_404_when_flag_absent(
        self, client: TestClient
    ) -> None:
        """Contrast: the internal endpoint IS flag-gated and returns 404 when flag absent.

        This verifies that the gate is localised to the correct endpoint and that
        the flag evaluation itself works correctly in the emulator context.
        """
        response = client.post(
            "/api/v1/internal/chat/side-table/update",
            json={
                "session_id": "sess_ac18_contrast",
                "account_id": "acc_ac18_contrast",
                "delta": {"message_count": {"_increment": 1}},
                "idempotency_key": "ac18-contrast-key-001",
            },
            headers={"Authorization": "Bearer dummy-skip-token"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"
