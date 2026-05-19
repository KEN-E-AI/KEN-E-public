"""Tests for organization subscription change functionality."""

import json
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.database import Neo4jService, get_neo4j_service
from src.kene_api.firestore import FirestoreService, get_firestore_service
from src.kene_api.routers.organizations import router

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4jService."""
    service = Mock(spec=Neo4jService)
    service.health_check = AsyncMock(return_value=True)
    service.execute_query = AsyncMock()
    service.execute_write_query = AsyncMock()
    return service


class _AllAdminPermissions(dict):
    """Organization-permission map that grants ``admin`` for every org.

    The subscription-change permission check looks up the role for a single
    org id; granting admin universally keeps these tests focused on the
    subscription logic rather than permission setup.
    """

    def get(self, key, default=None):
        return "admin"


# Admin user document returned for the organization-permission check.
_ADMIN_USER_DOC = {"permissions": {"organizations": _AllAdminPermissions()}}


def _neo4j_query_router(org_data):
    """Build an ``execute_query`` side effect that returns the right row shape.

    The subscription-change flow issues two distinct read queries: one that
    returns the organization node (``RETURN org``) and one that returns just
    the team map (``RETURN o.team as team``).
    """

    async def _route(query, params=None):
        if "o.team as team" in query:
            return [{"team": org_data["team"]}]
        return [{"org": org_data}]

    return _route


@pytest.fixture
def mock_firestore_service():
    """Create a mock FirestoreService.

    ``get_document`` special-cases the ``users`` collection (the
    organization-permission check) so it always returns an admin user; for any
    other collection it returns whatever a test sets as ``plan_document``.
    """
    service = Mock(spec=FirestoreService)
    service.health_check = Mock(return_value=True)
    service.plan_document = None

    def _get_document(collection, document_id):
        if collection == "users":
            return _ADMIN_USER_DOC
        return service.plan_document

    service.get_document = Mock(side_effect=_get_document)
    return service


@pytest.fixture
def test_app(mock_neo4j_service, mock_firestore_service, monkeypatch):
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()

    # The endpoint resolves the Firestore service via a direct module call
    # (not Depends), so patch the symbol the router actually uses.
    monkeypatch.setattr(
        "src.kene_api.routers.organizations.get_firestore_service",
        lambda: mock_firestore_service,
    )

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_current_user_context] = lambda: UserContext(
        user_id="test-user",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )

    app.include_router(router, prefix="/api/v1/organizations")

    return TestClient(app)


@pytest.fixture
def sample_organization_data():
    """Sample organization data."""
    return {
        "organization_id": "org_test123",
        "organization_name": "Test Organization",
        "plan": "Free Plan",
        "website": "https://test-org.example.com",
        "agency": False,
        "subscription": {
            "plan_name": "Free Plan",
            "plan_description": "Basic features for getting started",
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-01",
            "features": ["Basic Reports", "1 User"],
            "usage": {"reports_generated": 5, "reports_limit": 10},
        },
        "team": {"members_used": 1, "members_limit": 1, "pending_invitations": 0},
        "billing": {
            "payment_method": {"last_four": "", "brand": "", "expires": ""},
            "address": "",
            "tax_id": "",
        },
    }


@pytest.fixture
def sample_plan_data():
    """Sample subscription plan data from Firestore."""
    return {
        "plan_id": "starter-plan",
        "plan_name": "Starter Plan",
        "plan_description": "Perfect for small teams",
        "price": 49.0,
        "currency": "USD",
        "billing_cycle": "monthly",
        "features": {
            "max_users": 5,
            "max_reports": 50,
            "features": [
                "Advanced Reports",
                "Up to 5 Users",
                "Priority Email Support",
                "API Access",
            ],
        },
        "is_default": False,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class TestChangeOrganizationSubscription:
    """Tests for changing organization subscription."""

    async def test_change_subscription_success(
        self,
        test_app,
        mock_neo4j_service,
        mock_firestore_service,
        sample_organization_data,
        sample_plan_data,
    ):
        """Test successfully changing a subscription plan."""
        # Mock get_organization to return existing org
        mock_neo4j_service.execute_query.side_effect = _neo4j_query_router(
            sample_organization_data
        )

        # Mock Firestore to return the new plan
        mock_firestore_service.plan_document = sample_plan_data

        # Make the request
        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "starter-plan"},
        )

        assert response.status_code == 200

        # Verify Neo4j was called to update the organization
        mock_neo4j_service.execute_write_query.assert_called_once()
        call_args = mock_neo4j_service.execute_write_query.call_args

        # Check the query contains expected updates
        query = call_args[0][0]
        assert "SET o.subscription = $subscription" in query
        assert "o.team = $team" in query
        assert "o.plan = $plan_name" in query

        # Check parameters
        params = call_args[1]["parameters"]
        assert params["organization_id"] == "org_test123"
        assert params["plan_name"] == "Starter Plan"

        # Team JSON carries the updated member limit from the new plan
        team = json.loads(params["team"])
        assert team["members_limit"] == 5

        # Check subscription JSON
        subscription = json.loads(params["subscription"])
        assert subscription["plan_name"] == "Starter Plan"
        assert subscription["price"] == 49.0
        assert subscription["usage"]["reports_limit"] == 50

    async def test_change_subscription_organization_not_found(
        self, test_app, mock_neo4j_service, mock_firestore_service
    ):
        """Test changing subscription for non-existent organization."""
        # Mock get_organization to return empty result
        mock_neo4j_service.execute_query.return_value = []

        response = test_app.put(
            "/api/v1/organizations/non_existent/subscription?account_id=user123",
            json={"plan_id": "starter-plan"},
        )

        assert response.status_code == 404
        assert "Organization not found" in response.json()["detail"]

    async def test_change_subscription_plan_not_found(
        self,
        test_app,
        mock_neo4j_service,
        mock_firestore_service,
        sample_organization_data,
    ):
        """Test changing to a non-existent plan."""
        # Mock get_organization to return existing org
        mock_neo4j_service.execute_query.side_effect = _neo4j_query_router(
            sample_organization_data
        )

        # Mock Firestore to return None (plan not found)
        mock_firestore_service.plan_document = None

        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "non-existent-plan"},
        )

        assert response.status_code == 404
        assert "Subscription plan not found" in response.json()["detail"]

    async def test_change_subscription_inactive_plan(
        self,
        test_app,
        mock_neo4j_service,
        mock_firestore_service,
        sample_organization_data,
        sample_plan_data,
    ):
        """Test changing to an inactive plan."""
        # Mock get_organization to return existing org
        mock_neo4j_service.execute_query.side_effect = _neo4j_query_router(
            sample_organization_data
        )

        # Mock Firestore to return inactive plan
        inactive_plan = sample_plan_data.copy()
        inactive_plan["is_active"] = False
        mock_firestore_service.plan_document = inactive_plan

        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "inactive-plan"},
        )

        assert response.status_code == 400
        assert "Subscription plan is not active" in response.json()["detail"]

    async def test_change_subscription_preserves_usage(
        self,
        test_app,
        mock_neo4j_service,
        mock_firestore_service,
        sample_organization_data,
        sample_plan_data,
    ):
        """Test that changing subscription preserves current usage data."""
        # Set some usage in the current subscription
        sample_organization_data["subscription"]["usage"]["reports_generated"] = 8

        # Mock get_organization to return existing org
        mock_neo4j_service.execute_query.side_effect = _neo4j_query_router(
            sample_organization_data
        )

        # Mock Firestore to return the new plan
        mock_firestore_service.plan_document = sample_plan_data

        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "starter-plan"},
        )

        assert response.status_code == 200

        # Check that usage was preserved in the update
        call_args = mock_neo4j_service.execute_write_query.call_args
        params = call_args[1]["parameters"]
        subscription = json.loads(params["subscription"])

        assert subscription["usage"]["reports_generated"] == 8  # Preserved
        assert subscription["usage"]["reports_limit"] == 50  # Updated from new plan

    async def test_change_subscription_database_error(
        self,
        test_app,
        mock_neo4j_service,
        mock_firestore_service,
        sample_organization_data,
        sample_plan_data,
    ):
        """Test handling database errors during subscription change."""
        # Mock get_organization to return existing org
        mock_neo4j_service.execute_query.side_effect = _neo4j_query_router(
            sample_organization_data
        )

        # Mock Firestore to return the new plan
        mock_firestore_service.plan_document = sample_plan_data

        # Mock write query to raise an error
        mock_neo4j_service.execute_write_query.side_effect = Exception(
            "Database connection error"
        )

        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "starter-plan"},
        )

        # The endpoint surfaces an unexpected write failure as a generic 500.
        assert response.status_code == 500
        assert "unexpected error" in response.json()["detail"].lower()
