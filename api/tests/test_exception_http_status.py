"""DM-106: consistent exception→HTTP status mapping across routers.

- A Neo4j driver connectivity failure (``ServiceUnavailable``) must surface as a
  graceful 503 with a clean body — never a raw 500 + ASGI traceback.
- A missing conversation must return 404, not get rewrapped as 500 by a generic
  ``except Exception``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app
from src.kene_api.routers.notifications_v2 import get_notification_service


def _super_admin_user() -> MagicMock:
    # Empty accessible_accounts → get_notifications takes the super-admin branch
    # that runs db.execute_query OUTSIDE the try (the escape path).
    user = MagicMock()
    user.user_id = "u_test"
    user.is_super_admin = True
    user.accessible_accounts = []
    user.organization_permissions = {}
    return user


def _regular_user() -> MagicMock:
    # Non-empty accessible_accounts → skips the account-id pre-fetch and fails
    # inside the main fetch try block instead.
    user = MagicMock()
    user.user_id = "u_test"
    user.is_super_admin = False
    user.accessible_accounts = ["acc_1"]
    user.organization_permissions = {}
    return user


@pytest.fixture
def client():
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def _assert_clean_503(response) -> None:
    assert response.status_code == 503
    # No information disclosure: neither a traceback nor the raw exception class.
    assert "Traceback" not in response.text
    assert "ServiceUnavailable" not in response.text
    assert "Database service unavailable" in response.json()["detail"]


class TestNeo4jUnavailableReturns503:
    """AC: GET /api/v1/notifications/ returns 503 (not 500) when Neo4j is down."""

    def test_escape_path_returns_503(self, client):
        """Super-admin path: ServiceUnavailable from the pre-fetch query escapes
        the route and is caught by the app-wide handler."""
        db = MagicMock()
        db.execute_query = AsyncMock(side_effect=ServiceUnavailable("dead port"))
        app.dependency_overrides[get_current_user_context] = _super_admin_user
        app.dependency_overrides[get_neo4j_service] = lambda: db
        app.dependency_overrides[get_notification_service] = lambda: MagicMock()

        _assert_clean_503(client.get("/api/v1/notifications/"))

    def test_fetch_path_returns_503(self, client):
        """Regular-user path: ServiceUnavailable from the main fetch is re-raised
        (not swallowed as 500) and reaches the app-wide handler."""
        service = MagicMock()
        service.get_user_notifications = AsyncMock(
            side_effect=ServiceUnavailable("dead port")
        )
        app.dependency_overrides[get_current_user_context] = _regular_user
        app.dependency_overrides[get_neo4j_service] = lambda: MagicMock()
        app.dependency_overrides[get_notification_service] = lambda: service

        _assert_clean_503(client.get("/api/v1/notifications/"))


class TestChatHistoryStatus:
    """AC: a non-existent conversation returns 404, not 500."""

    _HISTORY = "src.kene_api.routers.chat.agent_client.get_conversation_history"

    def test_missing_conversation_returns_404(self, client, monkeypatch):
        monkeypatch.setattr(self._HISTORY, AsyncMock(return_value=None))
        app.dependency_overrides[get_current_user_context] = _regular_user

        response = client.get("/api/v1/chat/conversations/sess_missing/history")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_real_error_still_returns_500(self, client, monkeypatch):
        """Guard: the new `except HTTPException: raise` must not swallow genuine
        failures — a real error still maps to 500."""
        monkeypatch.setattr(self._HISTORY, AsyncMock(side_effect=RuntimeError("boom")))
        app.dependency_overrides[get_current_user_context] = _regular_user

        response = client.get("/api/v1/chat/conversations/sess_x/history")

        assert response.status_code == 500
