"""Tests for accounts activity logs functionality."""

import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.bigquery import get_bigquery_service
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.routers.accounts import _create_initial_activity_logs

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)

# Create test client
client = TestClient(app)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(return_value=[{"created_count": 0}])
    return mock_service


@pytest.fixture
def mock_firestore_service():
    """Create a mock Firestore service."""
    service = Mock()
    service.health_check = Mock(return_value=True)
    service.list_documents = Mock(
        return_value=[
            {
                "activity_id": "act_00",
                "activity_name": "Holidays",
                "activity_description": "Public holidays and observances",
                "expected_impact": "Low",
                "internal": True,
                "known_activity": True,
            }
        ]
    )
    return service


@pytest.fixture
def mock_bigquery_service():
    """Create a mock BigQuery service."""
    service = Mock()
    service.health_check = Mock(return_value=True)
    service.query_holiday_activities = Mock(return_value=[])
    return service


@pytest.mark.asyncio
async def test_create_initial_activity_logs_success():
    """Test successful creation of initial activity logs."""
    # Mock services
    mock_neo4j = MagicMock()
    mock_bigquery = MagicMock()

    # Mock act_00 exists
    mock_neo4j.execute_query = AsyncMock(
        return_value=[{"a": {"activity_id": "act_00"}}]
    )

    # Mock holiday data from BigQuery
    mock_bigquery.query_holiday_activities = Mock(
        return_value=[
            {
                "description": "New Year's Day",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
            {
                "description": "Christmas Day",
                "start_date": "2024-12-25",
                "end_date": "2024-12-25",
            },
        ]
    )

    # Mock successful creation
    mock_neo4j.execute_write_query = AsyncMock(return_value=[{"created_count": 2}])

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _create_initial_activity_logs(
            mock_neo4j, mock_bigquery, "test-account-id", "test-org-id", ["AU", "CA"]
        )

    assert result == 2
    mock_bigquery.query_holiday_activities.assert_called_once_with(
        "test-project", ["AU", "CA"]
    )
    mock_neo4j.execute_write_query.assert_called_once()


@pytest.mark.asyncio
async def test_create_initial_activity_logs_no_project_id():
    """Test activity logs creation when project ID is not set."""
    mock_neo4j = MagicMock()
    mock_bigquery = MagicMock()

    with patch.dict(os.environ, {}, clear=True):
        result = await _create_initial_activity_logs(
            mock_neo4j, mock_bigquery, "test-account-id", "test-org-id", ["AU"]
        )

    assert result == 0
    mock_bigquery.query_holiday_activities.assert_not_called()


@pytest.mark.asyncio
async def test_create_initial_activity_logs_act_00_not_found():
    """Test activity logs creation when act_00 doesn't exist."""
    mock_neo4j = MagicMock()
    mock_bigquery = MagicMock()

    # Mock act_00 doesn't exist
    mock_neo4j.execute_query = AsyncMock(return_value=[])

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _create_initial_activity_logs(
            mock_neo4j, mock_bigquery, "test-account-id", "test-org-id", ["AU"]
        )

    assert result == 0
    mock_bigquery.query_holiday_activities.assert_not_called()


@pytest.mark.asyncio
async def test_create_initial_activity_logs_no_holidays():
    """Test activity logs creation when no holidays are found."""
    mock_neo4j = MagicMock()
    mock_bigquery = MagicMock()

    # Mock act_00 exists
    mock_neo4j.execute_query = AsyncMock(
        return_value=[{"a": {"activity_id": "act_00"}}]
    )

    # Mock no holiday data
    mock_bigquery.query_holiday_activities = Mock(return_value=[])

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _create_initial_activity_logs(
            mock_neo4j,
            mock_bigquery,
            "test-account-id",
            "test-org-id",
            ["XX"],  # Region with no holidays
        )

    assert result == 0
    mock_neo4j.execute_write_query.assert_not_called()


@pytest.mark.asyncio
async def test_create_initial_activity_logs_exception_handling():
    """Test activity logs creation handles exceptions gracefully."""
    mock_neo4j = MagicMock()
    mock_bigquery = MagicMock()

    # Mock act_00 exists
    mock_neo4j.execute_query = AsyncMock(
        return_value=[{"a": {"activity_id": "act_00"}}]
    )

    # Mock BigQuery throws exception
    mock_bigquery.query_holiday_activities = Mock(
        side_effect=Exception("BigQuery error")
    )

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        result = await _create_initial_activity_logs(
            mock_neo4j, mock_bigquery, "test-account-id", "test-org-id", ["AU"]
        )

    # Should return 0 and not raise exception
    assert result == 0


@patch("src.kene_api.bigquery._bigquery_service", None)
def test_create_account_with_regions(
    mock_neo4j_service, mock_firestore_service, mock_bigquery_service
):
    """Test creating account with regions triggers holiday activity logs creation."""
    # Mock BigQuery service to avoid real initialization
    mock_bigquery_service._initialized = True
    mock_bigquery_service._client = Mock()

    # Mock organization exists and is not agency
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        elif "org.agency" in query:
            return [{"agency": False}]
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]
        elif 'activity_id: "act_00"' in query:
            # Match the exact query for act_00
            return [{"a": {"activity_id": "act_00"}}]
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                {
                    "acc": {
                        "account_id": parameters["account_id"],
                        "account_name": "New Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "Active",
                        "websites": ["https://new.com"],
                        "timezone": "America/New_York",
                        "region": ["AU", "CA"],
                        "data_region": "",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Mock write queries - first for account creation, then for initial activities, then for activity logs
    mock_neo4j_service.execute_write_query.side_effect = [
        {"nodes_created": 1, "relationships_created": 1},  # Account creation
        [{"created_count": 1}],  # Initial activities creation (including act_00)
        [{"created_count": 1}],  # Activity logs creation
    ]

    # Mock BigQuery returns holidays
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        }
    ]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        new_account_data = {
            "account_name": "New Account",
            "organization_id": "test-org",
            "industry": "Technology",
            "status": "Active",
            "websites": ["https://new.com"],
            "timezone": "America/New_York",
            "region": ["AU", "CA"],
        }

        response = client.post("/api/v1/accounts/", json=new_account_data)

    assert response.status_code == 200
    data = response.json()
    assert data["account_name"] == "New Account"
    assert data["region"] == ["AU", "CA"]

    # Verify BigQuery was called
    mock_bigquery_service.query_holiday_activities.assert_called_once()

    # Clean up
    app.dependency_overrides.clear()


def test_create_account_without_regions(
    mock_neo4j_service, mock_firestore_service, mock_bigquery_service
):
    """Test creating account without regions doesn't trigger holiday activity logs."""

    # Mock organization exists and is not agency
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]
        elif "org.agency" in query:
            return [{"agency": False}]
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            return [
                {
                    "acc": {
                        "account_id": parameters["account_id"],
                        "account_name": "New Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "Active",
                        "websites": ["https://new.com"],
                        "timezone": "America/New_York",
                        "region": [],
                        "data_region": "",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "test-org",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://new.com"],
        "timezone": "America/New_York",
    }

    response = client.post("/api/v1/accounts/", json=new_account_data)

    assert response.status_code == 200

    # Verify BigQuery was NOT called
    mock_bigquery_service.query_holiday_activities.assert_not_called()

    # Clean up
    app.dependency_overrides.clear()
