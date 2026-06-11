"""Integration tests for authenticated endpoints."""

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator",
)


@pytest.fixture(autouse=True)
def _mock_org_resolver():
    """IN-2: resolve account-scoped endpoints' owning org without Neo4j.

    Account-scoped gates (e.g. notification create) call
    ``require_account_access_for`` → ``resolve_owning_organization_id`` (Neo4j).
    Patch it to org_123 (the org ``authed_user`` is admin of). Org-scoped
    endpoints use ``require_organization_access`` and never hit this resolver.
    A user who is not an admin of org_123 (``user_no_org_admin``) is still
    denied, so the without-permission case correctly yields 404.
    """
    with mock.patch(
        "src.kene_api.auth.account_org.resolve_owning_organization_id",
        new=mock.AsyncMock(return_value="org_123"),
    ):
        yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def authed_user():
    """User with admin on org_123, view on org_456, admin on acc_123, viewer on acc_456."""
    user = UserContext(
        user_id="test-user-123",
        email="test@example.com",
        organization_permissions={"org_123": "admin", "org_456": "view"},
        account_permissions={"acc_123": "admin", "acc_456": "viewer"},
    )
    app.dependency_overrides[get_current_user_context] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user_context, None)


@pytest.fixture
def user_no_org_admin():
    """User with NO org-admin permission — only explicit account access on acc_123.

    UserContext.has_account_access returns True for ANY user with at least one
    org-admin permission (auth/models.py:87-91), so per-account denial tests
    require a user without org-admin scope. The fixture name encodes the
    invariant so a contributor swapping it for ``authed_user`` (which has
    org_123 admin) will notice the test stops being meaningful.
    """
    user = UserContext(
        user_id="test-user-no-org-admin",
        email="viewer@example.com",
        organization_permissions={},
        account_permissions={"acc_123": "viewer"},
    )
    app.dependency_overrides[get_current_user_context] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user_context, None)


@pytest.fixture
def mock_neo4j():
    service = mock.MagicMock()
    service.health_check = mock.AsyncMock(return_value=True)
    service.execute_query = mock.AsyncMock(return_value=[])
    app.dependency_overrides[get_neo4j_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_neo4j_service, None)


@pytest.fixture
def mock_firestore():
    service = mock.MagicMock()
    app.dependency_overrides[get_firestore_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_firestore_service, None)


class TestAuthenticationMiddleware:
    """Test authentication middleware behavior."""

    def test_unauthenticated_request_returns_401(self, client):
        """Test that requests without auth token return 401."""
        endpoints = [
            "/api/v1/organizations/",
            "/api/v1/accounts/",
            "/api/v1/notifications/preferences",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
            assert response.json()["detail"] == "Missing authentication credentials"

    def test_invalid_token_returns_401(self, client):
        """Test that invalid tokens return 401."""
        with mock.patch(
            "src.kene_api.auth.user_context.verify_id_token",
            side_effect=Exception("Invalid token"),
        ):
            response = client.get(
                "/api/v1/organizations/",
                headers={"Authorization": "Bearer invalid-token"},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid authentication token"


class TestOrganizationEndpoints:
    """Test organization endpoints with authentication."""

    def test_get_organizations_authenticated(self, client, authed_user, mock_neo4j):
        """Authenticated user sees organizations they have access to."""
        mock_neo4j.execute_query.return_value = [
            {"org": {"organization_id": "org_123", "organization_name": "Test Org 1"}},
            {"org": {"organization_id": "org_456", "organization_name": "Test Org 2"}},
        ]

        # The router calls _create_organization_from_record which builds a
        # full Organization Pydantic model (plan/billing/subscription/team).
        # The test is exercising the org-list query filter, not the record
        # serializer, so short-circuit the helper.
        def _fake_create(org_data):
            from src.kene_api.models.kene_models import Organization

            return Organization.model_construct(
                organization_id=org_data["organization_id"],
                organization_name=org_data["organization_name"],
            )

        with mock.patch(
            "src.kene_api.routers.organizations._create_organization_from_record",
            side_effect=_fake_create,
        ):
            response = client.get("/api/v1/organizations/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["organizations"]) == 2

        called_query = mock_neo4j.execute_query.call_args[0][0]
        assert "WHERE org.organization_id IN $org_ids" in called_query
        called_params = mock_neo4j.execute_query.call_args[0][1]
        assert set(called_params["org_ids"]) == {"org_123", "org_456"}

    def test_get_organization_by_id_with_access(self, client, authed_user, mock_neo4j):
        """User with admin on org_123 can fetch it."""
        from src.kene_api.models.kene_models import Organization

        org = Organization.model_construct(
            organization_id="org_123", organization_name="Test Org"
        )

        with mock.patch(
            "src.kene_api.routers.organizations._get_organization_by_id",
            return_value=org,
        ):
            response = client.get("/api/v1/organizations/org_123")

        assert response.status_code == 200
        assert response.json()["organization_id"] == "org_123"

    def test_get_organization_by_id_without_access(self, client, authed_user):
        """User without permission on org_999 gets 403."""
        response = client.get("/api/v1/organizations/org_999")

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestAccountEndpoints:
    """Test account endpoints with authentication."""

    def test_get_accounts_authenticated(self, client, authed_user, mock_neo4j):
        """Authenticated user sees only accounts they have access to."""

        def _query_router(query, params=None):
            # Org-admin enumeration query — returns [{account_id: ...}].
            if "MATCH (org:Organization {organization_id: $org_id})" in query:
                return [{"account_id": "acc_org_admin"}]
            # Final account-list query — returns [{acc: {...}}].
            if "account_id IN $account_ids" in query:
                return [
                    {"acc": {"account_id": "acc_123", "account_name": "Account 1"}},
                    {"acc": {"account_id": "acc_456", "account_name": "Account 2"}},
                ]
            # Fail loudly on drift — if the router gains a new query shape, the
            # test should not silently pick up the wrong response.
            raise AssertionError(f"Unexpected query in test mock: {query!r}")

        mock_neo4j.execute_query.side_effect = _query_router

        def _fake_create(acc_data):
            from src.kene_api.models.kene_models import Account

            return Account.model_construct(
                account_id=acc_data["account_id"],
                account_name=acc_data["account_name"],
            )

        with mock.patch(
            "src.kene_api.routers.accounts._create_account_from_record",
            side_effect=_fake_create,
        ):
            response = client.get("/api/v1/accounts/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # The final query enumerates accessible_account_ids via WHERE IN.
        final_call_query = mock_neo4j.execute_query.call_args[0][0]
        assert "account_id IN $account_ids" in final_call_query

    def test_get_accounts_filtered_by_organization(
        self, client, authed_user, mock_neo4j
    ):
        """User with access to org_123 can filter accounts by it; org_999 returns 403."""
        mock_neo4j.execute_query.return_value = []

        response = client.get("/api/v1/accounts/?organization_id=org_123")
        assert response.status_code == 200

        response = client.get("/api/v1/accounts/?organization_id=org_999")
        assert response.status_code == 403
        assert "Access denied to organization org_999" in response.json()["detail"]


class TestNotificationEndpoints:
    """Test notification endpoints with authentication."""

    def test_get_notification_preferences(self, client, authed_user, mock_firestore):
        """Authenticated user can fetch their preferences."""
        with mock.patch(
            "src.kene_api.services.notification_service_v2.NotificationService.get_user_preferences",
            return_value={
                "categories": ["KPI Performance", "New Features"],
                "channels": ["ui", "email"],
            },
        ):
            response = client.get("/api/v1/notifications/preferences")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "channels" in data

    def test_create_notification_with_permission(
        self, client, authed_user, mock_firestore
    ):
        """User with admin on acc_123 can create a notification on it."""
        with mock.patch(
            "src.kene_api.services.notification_service_v2.NotificationService.create_notification",
            return_value="notif_123",
        ):
            response = client.post(
                "/api/v1/notifications/",
                json={
                    "account_id": "acc_123",
                    "category": "KPI Performance",
                    "description": "Test notification",
                },
            )

        assert response.status_code == 200
        assert response.json()["notification_id"] == "notif_123"

    def test_create_notification_without_permission(
        self, client, user_no_org_admin, mock_firestore
    ):
        """User without access to acc_999 gets 404.

        IN-2: denial returns 404 'Account not found' (anti-enumeration), not a
        403 that would confirm the account exists.
        """
        response = client.post(
            "/api/v1/notifications/",
            json={
                "account_id": "acc_999",
                "category": "KPI Performance",
                "description": "Test notification",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Account not found"
