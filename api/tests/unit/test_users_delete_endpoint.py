"""Unit tests for DELETE /api/v1/users/{user_id} super-admin-gated endpoint.

All external I/O (Firestore, GCS) is mocked.  The orchestrator
``delete_user_data`` is replaced with ``AsyncMock`` so these tests stay
hermetic and fast — full deletion semantics are covered by DM-54's
integration test (test_user_deletion_no_orphans.py).

Pattern mirrors ``api/tests/integration/test_agent_configs_api.py`` —
``app.dependency_overrides`` on ``get_current_user_context`` + an autouse
fixture that clears overrides before and after each test.

Spec: docs/design/components/data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md §4.3, §6 AC-8
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.main import app
from src.kene_api.models.user_deletion import UserDeletionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_overrides() -> None:
    """Guarantee dependency_overrides is clean before and after every test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_user(email: str) -> UserContext:
    return UserContext(
        user_id="u_test",
        email=email,
        organization_permissions={},
        account_permissions={},
    )


SUPER_ADMIN_USER = _make_user("admin@ken-e.ai")
REGULAR_USER = _make_user("user@example.com")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _zero_result(user_id: str = "u_target") -> UserDeletionResult:
    return UserDeletionResult(user_id=user_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteUserEndpoint:
    """DELETE /api/v1/users/{user_id} — auth gate and delegation contract."""

    def test_super_admin_returns_200_with_deletion_result(
        self, client: TestClient
    ) -> None:
        """AC-8: super-admin caller receives 200 with UserDeletionResult body."""
        expected_result = UserDeletionResult(
            user_id="u_target",
            member_rows_deleted=5,
            integrations_hook_fired=3,
            user_doc_deleted=True,
            gcs_prefixes_purged=0,
            errors=[],
        )
        app.dependency_overrides[get_current_user_context] = lambda: SUPER_ADMIN_USER

        with patch(
            "src.kene_api.routers.users.delete_user_data",
            new=AsyncMock(return_value=expected_result),
        ) as mock_delete:
            resp = client.delete("/api/v1/users/u_target")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "u_target"
        assert body["member_rows_deleted"] == 5
        assert body["integrations_hook_fired"] == 3
        assert body["user_doc_deleted"] is True
        assert body["errors"] == []
        mock_delete.assert_awaited_once()
        call_args = mock_delete.call_args
        assert call_args.args[0] == "u_target"
        assert call_args.kwargs["actor"] is SUPER_ADMIN_USER

    def test_super_admin_invokes_orchestrator_with_correct_user_id(
        self, client: TestClient
    ) -> None:
        """Orchestrator is called with the path param user_id, not the actor's user_id."""
        app.dependency_overrides[get_current_user_context] = lambda: SUPER_ADMIN_USER

        with patch(
            "src.kene_api.routers.users.delete_user_data",
            new=AsyncMock(return_value=_zero_result("u_carol")),
        ) as mock_delete:
            resp = client.delete("/api/v1/users/u_carol")

        assert resp.status_code == 200
        mock_delete.assert_awaited_once()
        assert mock_delete.call_args.args[0] == "u_carol"

    def test_non_super_admin_returns_403_with_exact_body(
        self, client: TestClient
    ) -> None:
        """AC-8: non-super-admin caller receives 403 with body {\"error\": \"super_admin_required\"}.

        The body must be exactly this flat shape — NOT {\"detail\": {\"error\": ...}}.
        """
        app.dependency_overrides[get_current_user_context] = lambda: REGULAR_USER

        with patch(
            "src.kene_api.routers.users.delete_user_data",
            new=AsyncMock(return_value=_zero_result()),
        ) as mock_delete:
            resp = client.delete("/api/v1/users/u_target")

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}
        # Orchestrator must NOT be called for unauthorized requests.
        mock_delete.assert_not_awaited()

    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        """Callers with no auth token receive 401 before the super-admin check."""
        # No dependency override — real get_current_user_context raises 401 when
        # no Bearer token is present.
        resp = client.delete("/api/v1/users/u_target")

        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate") == "Bearer"

    def test_idempotent_rerun_returns_200_with_zero_counts(
        self, client: TestClient
    ) -> None:
        """Re-running DELETE on an already-purged user returns 200 with zero-count result.

        The orchestrator's idempotency contract (PRD AC-10) guarantees this;
        the route must not special-case zero-count responses.
        """
        zero = _zero_result("u_already_gone")
        # Simulate the idempotent no-op — user_doc_deleted stays False when
        # the user doc was already absent (recursive_delete on a missing doc
        # is a no-op that does NOT raise).
        app.dependency_overrides[get_current_user_context] = lambda: SUPER_ADMIN_USER

        with patch(
            "src.kene_api.routers.users.delete_user_data",
            new=AsyncMock(return_value=zero),
        ):
            resp = client.delete("/api/v1/users/u_already_gone")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "u_already_gone"
        assert body["member_rows_deleted"] == 0
        assert body["user_doc_deleted"] is False
        assert body["errors"] == []
