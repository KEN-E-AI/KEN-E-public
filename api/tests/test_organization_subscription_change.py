"""Tests for organization subscription change functionality."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.kene_api.routers.organizations import router
from src.kene_api.models.kene_models import (
    Organization,
    ChangeSubscriptionRequest,
    Subscription,
    Team,
    Billing,
)
from src.kene_api.database import Neo4jService, get_neo4j_service
from src.kene_api.firestore import FirestoreService, get_firestore_service


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4jService."""
    service = Mock(spec=Neo4jService)
    service.health_check = Mock(return_value=True)
    service.execute_query = AsyncMock()
    service.execute_write_query = AsyncMock()
    return service


@pytest.fixture
def mock_firestore_service():
    """Create a mock FirestoreService."""
    service = Mock(spec=FirestoreService)
    service.health_check = Mock(return_value=True)
    service.get_document = Mock()
    return service


@pytest.fixture
def test_app(mock_neo4j_service, mock_firestore_service):
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

    app.include_router(router, prefix="/api/v1/organizations")

    return TestClient(app)


@pytest.fixture
def sample_organization_data():
    """Sample organization data."""
    return {
        "organization_id": "org_test123",
        "organization_name": "Test Organization",
        "plan": "Free Plan",
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
        mock_neo4j_service.execute_query.return_value = [[sample_organization_data]]

        # Mock Firestore to return the new plan
        mock_firestore_service.get_document.return_value = sample_plan_data

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
        assert "o.team.members_limit = $members_limit" in query
        assert "o.plan = $plan_name" in query

        # Check parameters
        params = call_args[1]["parameters"]
        assert params["organization_id"] == "org_test123"
        assert params["plan_name"] == "Starter Plan"
        assert params["members_limit"] == 5

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
        mock_neo4j_service.execute_query.return_value = [[]]

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
        mock_neo4j_service.execute_query.return_value = [[sample_organization_data]]

        # Mock Firestore to return None (plan not found)
        mock_firestore_service.get_document.return_value = None

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
        mock_neo4j_service.execute_query.return_value = [[sample_organization_data]]

        # Mock Firestore to return inactive plan
        inactive_plan = sample_plan_data.copy()
        inactive_plan["is_active"] = False
        mock_firestore_service.get_document.return_value = inactive_plan

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
        mock_neo4j_service.execute_query.return_value = [[sample_organization_data]]

        # Mock Firestore to return the new plan
        mock_firestore_service.get_document.return_value = sample_plan_data

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
        mock_neo4j_service.execute_query.return_value = [[sample_organization_data]]

        # Mock Firestore to return the new plan
        mock_firestore_service.get_document.return_value = sample_plan_data

        # Mock write query to raise an error
        mock_neo4j_service.execute_write_query.side_effect = Exception(
            "Database connection error"
        )

        response = test_app.put(
            "/api/v1/organizations/org_test123/subscription?account_id=user123",
            json={"plan_id": "starter-plan"},
        )

        assert response.status_code == 503
        assert "Database service unavailable" in response.json()["detail"]
