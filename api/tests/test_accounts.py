"""Tests for accounts endpoints."""

import json
import os
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.bigquery import get_bigquery_service
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import FirestoreService, get_firestore_service
from src.kene_api.main import app
from src.kene_api.services.skill_storage import get_skill_storage_service
from src.kene_api.services.storage_service import get_storage_service

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator",
)

# Create test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def _override_auth_dep():
    """Bypass FastAPI's Firebase auth dep with a super-admin test user.

    The router uses ``Depends(get_current_user_context)`` which would
    otherwise reject test requests at 401 (no Authorization header) or
    blow up trying to talk to real Firebase/Firestore. Super-admin role
    matches the router's ``user.is_super_admin`` branch that bypasses
    permission checks; tests that need to exercise non-admin permission
    branches should install their own override on top of this fixture.
    """
    test_user = UserContext(
        user_id="test-user-123",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )
    app.dependency_overrides[get_current_user_context] = lambda: test_user
    yield
    app.dependency_overrides.pop(get_current_user_context, None)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(
        return_value={
            "nodes_created": 1,
            "relationships_created": 1,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }
    )
    return mock_service


@pytest.fixture
def mock_firestore_service():
    """Create a mock Firestore service."""
    service = Mock(spec=FirestoreService)
    service.health_check = Mock(return_value=True)
    service.list_documents = Mock(return_value=[])
    return service


def test_get_accounts(mock_neo4j_service):
    """Test getting all accounts."""
    # Mock the database response
    mock_neo4j_service.execute_query.return_value = [
        {
            "acc": {
                "account_id": "test-account",
                "account_name": "Test Account",
                "organization_id": "test-org",
                "industry": "Technology",
                "status": "Active",
                "websites": ["https://test.com"],
                "timezone": "America/New_York",
            }
        }
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/accounts/")

    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert "total" in data
    assert data["total"] == 1
    assert len(data["accounts"]) == 1
    assert data["accounts"][0]["account_id"] == "test-account"

    # Clean up
    app.dependency_overrides.clear()


def test_get_accounts_by_organization(mock_neo4j_service):
    """Test getting accounts filtered by organization."""
    # Mock the database response
    mock_neo4j_service.execute_query.return_value = [
        {
            "acc": {
                "account_id": "test-account-1",
                "account_name": "Test Account 1",
                "organization_id": "test-org",
                "industry": "Technology",
                "status": "Active",
                "websites": ["https://test1.com"],
                "timezone": "America/New_York",
            }
        },
        {
            "acc": {
                "account_id": "test-account-2",
                "account_name": "Test Account 2",
                "organization_id": "test-org",
                "industry": "Finance",
                "status": "Active",
                "websites": ["https://test2.com"],
                "timezone": "America/Chicago",
            }
        },
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/accounts/?organization_id=test-org")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(acc["organization_id"] == "test-org" for acc in data["accounts"])

    # Clean up
    app.dependency_overrides.clear()


def test_get_account_by_id(mock_neo4j_service):
    """Test getting a specific account."""
    # Access is now gated by require_account_access_for. The super-admin test
    # user (see _override_auth_dep) short-circuits before the org resolver, so
    # the injected db sees a single execute_query call: the account fetch.
    mock_neo4j_service.execute_query.return_value = [
        {
            "acc": {
                "account_id": "test-account",
                "account_name": "Test Account",
                "organization_id": "test-org",
                "industry": "Technology",
                "status": "Active",
                "websites": ["https://test.com"],
                "timezone": "America/New_York",
            }
        }
    ]

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/accounts/test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "test-account"
    assert data["account_name"] == "Test Account"

    # Clean up
    app.dependency_overrides.clear()


def test_create_account(mock_neo4j_service, mock_firestore_service):
    """Test creating a new account via multipart/form-data."""

    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        if "org.agency" in query:
            return [{"agency": False}]
        if "Account" in query and "exists" in query:
            return [{"exists": False}]
        if "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                {
                    "acc": {
                        "account_id": parameters["account_id"],
                        "account_name": "New Account",
                        "organization_id": "test-org",
                        "industry": "Manufacturing",
                        "status": "Active",
                        "websites": ["https://new.com"],
                        "timezone": "America/New_York",
                        "data_region": "",
                        "region": [],
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    mock_bigquery = MagicMock()
    mock_bigquery.query_holiday_activities = Mock(return_value=[])
    mock_storage = MagicMock()
    mock_skill_storage = MagicMock()

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery
    app.dependency_overrides[get_storage_service] = lambda: mock_storage
    app.dependency_overrides[get_skill_storage_service] = lambda: mock_skill_storage

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "test-org",
        "industry": "Manufacturing",
        "status": "Active",
        "websites": json.dumps(["https://new.com"]),
        "timezone": "America/New_York",
    }

    try:
        with mock.patch(
            "src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"
        ):
            response = client.post("/api/v1/accounts/", data=new_account_data)

        assert response.status_code == 200
        data = response.json()
        assert data["account_id"].startswith("account_")
        assert data["account_name"] == "New Account"
        assert data["organization_id"] == "test-org"
    finally:
        app.dependency_overrides.clear()


def test_create_account_organization_not_found(mock_neo4j_service):
    """Test creating an account for non-existent organization."""

    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": False}]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "non-existent-org",
        "industry": "Manufacturing",
        "status": "Active",
        "websites": json.dumps(["https://new.com"]),
        "timezone": "America/New_York",
    }

    try:
        response = client.post("/api/v1/accounts/", data=new_account_data)

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "Organization" in detail
        assert "not found" in detail
    finally:
        app.dependency_overrides.clear()


def test_create_account_agency_organization_forbidden(mock_neo4j_service):
    """Test that agency organizations cannot create accounts."""

    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        if "org.agency" in query:
            return [{"agency": True}]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "agency-org",
        "industry": "Manufacturing",
        "status": "Active",
        "websites": json.dumps(["https://new.com"]),
        "timezone": "America/New_York",
    }

    try:
        response = client.post("/api/v1/accounts/", data=new_account_data)
        assert response.status_code == 403
        assert "agency" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_create_account_non_agency_organization_allowed(
    mock_neo4j_service, mock_firestore_service
):
    """Test that non-agency organizations can create accounts."""

    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        if "org.agency" in query:
            return [{"agency": False}]
        if "Account" in query and "exists" in query:
            return [{"exists": False}]
        if "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                {
                    "acc": {
                        "account_id": parameters["account_id"],
                        "account_name": "New Account",
                        "organization_id": "regular-org",
                        "industry": "Manufacturing",
                        "status": "Active",
                        "websites": ["https://new.com"],
                        "timezone": "America/New_York",
                        "data_region": "",
                        "region": [],
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    mock_bigquery = MagicMock()
    mock_bigquery.query_holiday_activities = Mock(return_value=[])

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery
    app.dependency_overrides[get_storage_service] = lambda: MagicMock()
    app.dependency_overrides[get_skill_storage_service] = lambda: MagicMock()

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "regular-org",
        "industry": "Manufacturing",
        "status": "Active",
        "websites": json.dumps(["https://new.com"]),
        "timezone": "America/New_York",
    }

    try:
        with mock.patch(
            "src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"
        ):
            response = client.post("/api/v1/accounts/", data=new_account_data)
        assert response.status_code == 200
        assert response.json()["account_name"] == "New Account"
    finally:
        app.dependency_overrides.clear()


def _account_record(status="Active", websites=None, region=None):
    return {
        "acc": {
            "account_id": "test-account",
            "account_name": "Test Account",
            "organization_id": "test-org",
            "industry": "Manufacturing",
            "status": status,
            "websites": websites or ["https://test.com"],
            "timezone": "America/New_York",
            "region": region or [],
            "data_region": "",
        }
    }


def _update_query_mock(
    initial_region=None, return_status="Active", return_websites=None
):
    """Build a query-matcher for the update_account 5-query chain.

    Chain: _check_account_exists (1) → get_account [org+acc] (2) for current
    → execute_write_query (the update itself, separate mock) → get_account
    [org+acc] (2) for return.
    """

    def _mock(query, parameters=None):
        if "count(acc) > 0 as exists" in query:
            return [{"exists": True}]
        if (
            "BELONGS_TO]->(org:Organization)" in query
            and "organization_id as organization_id" in query
        ):
            return [{"organization_id": "test-org"}]
        if "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                _account_record(
                    status=return_status,
                    websites=return_websites,
                    region=initial_region,
                )
            ]
        return []

    return _mock


def test_update_account(mock_neo4j_service):
    """Test updating an account name + status via PUT."""
    mock_neo4j_service.execute_query.side_effect = _update_query_mock(
        return_status="Inactive",
        return_websites=["https://updated.com"],
    )

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    update_data = {"status": "Inactive", "websites": ["https://updated.com"]}

    try:
        response = client.put("/api/v1/accounts/test-account", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Inactive"
        assert data["websites"] == ["https://updated.com"]
    finally:
        app.dependency_overrides.clear()


def test_update_account_regions_triggers_sync(
    mock_neo4j_service, mock_firestore_service
):
    """Updating account regions triggers the holiday-activity-logs sync (BigQuery call)."""
    mock_bigquery_service = MagicMock()
    mock_bigquery_service.query_holiday_activities = Mock(
        return_value=[
            {
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            }
        ]
    )

    mock_neo4j_service.execute_query.side_effect = _update_query_mock(
        initial_region=[], return_websites=["https://test.com"]
    )
    mock_neo4j_service.execute_write_query.return_value = {"nodes_created": 1}

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    update_data = {"region": ["AU", "US"]}

    try:
        with mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
            response = client.put("/api/v1/accounts/test-account", json=update_data)

        assert response.status_code == 200
        # The router builds the regions arg from a set, so list order is not
        # deterministic — assert on contents, not order.
        assert mock_bigquery_service.query_holiday_activities.call_count == 1
        call_args = mock_bigquery_service.query_holiday_activities.call_args
        assert call_args[0][0] == "test-project"
        assert set(call_args[0][1]) == {"AU", "US"}
    finally:
        app.dependency_overrides.clear()


def test_update_account_no_region_change_no_sync(mock_neo4j_service):
    """PUT without a region change does not call BigQuery for holiday sync."""
    mock_bigquery_service = MagicMock()
    mock_bigquery_service.query_holiday_activities = Mock()

    mock_neo4j_service.execute_query.side_effect = _update_query_mock(
        initial_region=["AU", "US"]
    )

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    update_data = {"account_name": "Updated Account"}

    try:
        response = client.put("/api/v1/accounts/test-account", json=update_data)
        assert response.status_code == 200
        mock_bigquery_service.query_holiday_activities.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def _delete_account_deps(account_exists=True):
    """Wire mock storage / skill_storage / firestore for delete_account."""
    mock_storage = MagicMock()
    mock_storage.delete_account_documents = AsyncMock(return_value=True)
    mock_skill_storage = MagicMock()
    mock_skill_storage.delete_account_prefix = Mock(return_value=0)
    mock_firestore = MagicMock()
    mock_firestore.get_client.return_value = MagicMock()
    return mock_storage, mock_skill_storage, mock_firestore


def test_delete_account(mock_neo4j_service):
    """Super-admin DELETE removes the account and returns success."""

    def mock_execute_query(query, parameters=None):
        if "data_region" in query:
            return [{"data_region": "US"}]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query
    mock_neo4j_service.execute_write_operation = AsyncMock(
        return_value={"nodes_deleted": 1}
    )
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={"nodes_deleted": 1}
    )

    mock_storage, mock_skill_storage, mock_firestore = _delete_account_deps()

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore
    app.dependency_overrides[get_storage_service] = lambda: mock_storage
    app.dependency_overrides[get_skill_storage_service] = lambda: mock_skill_storage

    try:
        response = client.delete("/api/v1/accounts/test-account")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]
        # Cascade has multiple swallowed-exception branches in the router; a
        # silent failure in any one would still produce 200. Assert the
        # cleanup_errors stayed empty so a regression in the cascade actually
        # fails the test.
        cleanup = data["data"]
        assert cleanup["cleanup_errors"] == []
        assert cleanup["firestore_account_deleted"] is True
        assert cleanup["gcs_documents_deleted"] == 1
    finally:
        app.dependency_overrides.clear()


def test_delete_account_not_found(mock_neo4j_service):
    """DELETE returns 404 when the account does not exist in Neo4j."""

    mock_neo4j_service.execute_query.side_effect = lambda *_a, **_k: []

    mock_storage, mock_skill_storage, mock_firestore = _delete_account_deps()
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore
    app.dependency_overrides[get_storage_service] = lambda: mock_storage
    app.dependency_overrides[get_skill_storage_service] = lambda: mock_skill_storage

    try:
        response = client.delete("/api/v1/accounts/nonexistent-account")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_account_empty_websites_array(
    mock_neo4j_service, mock_firestore_service
):
    """Empty websites array is accepted by the multipart endpoint."""
    account_data = {
        "account_name": "Test Account",
        "organization_id": "test-org",
        "industry": "Manufacturing",
        "status": "Active",
        "websites": json.dumps([]),
        "timezone": "America/New_York",
    }

    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        if "org.agency" in query:
            return [{"agency": False}]
        if "Account" in query and "exists" in query:
            return [{"exists": False}]
        if "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                {
                    "acc": {
                        "account_id": parameters["account_id"],
                        "account_name": "Test Account",
                        "organization_id": "test-org",
                        "industry": "Manufacturing",
                        "status": "Active",
                        "websites": [],
                        "timezone": "America/New_York",
                        "data_region": "",
                        "region": [],
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    mock_bigquery = MagicMock()
    mock_bigquery.query_holiday_activities = Mock(return_value=[])

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery
    app.dependency_overrides[get_storage_service] = lambda: MagicMock()
    app.dependency_overrides[get_skill_storage_service] = lambda: MagicMock()

    try:
        with mock.patch(
            "src.kene_api.tasks.strategy_tasks.trigger_strategy_generation"
        ):
            response = client.post("/api/v1/accounts/", data=account_data)

        assert response.status_code == 200
        data = response.json()
        assert data["account_id"].startswith("account_")
        assert data["websites"] == []
    finally:
        app.dependency_overrides.clear()


def test_update_account_invalid_field_types(mock_neo4j_service):
    """Updating with wrong field types is rejected by Pydantic at the request layer."""
    update_data = {
        "account_name": ["should", "be", "string"],
        "status": 123,
        "websites": "should-be-array",
    }

    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    try:
        response = client.put("/api/v1/accounts/test-account", json=update_data)
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_get_accounts_with_special_characters_in_org_id(mock_neo4j_service):
    """Test getting accounts with special characters in organization_id."""
    # Mock response
    mock_neo4j_service.execute_query.return_value = [{"accounts": [], "total": 0}]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    # Test with special characters that should be URL encoded
    org_id = "test-org-with-@#$%"
    response = client.get(f"/api/v1/accounts/?organization_id={org_id}")

    assert response.status_code == 200
    # Query should have handled special characters

    # Clean up
    app.dependency_overrides.clear()
