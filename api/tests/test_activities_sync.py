"""Tests for activity logs sync endpoint."""

import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.bigquery import get_bigquery_service
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app

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
def mock_bigquery_service():
    """Create a mock BigQuery service."""
    service = Mock()
    service.query_holiday_activities = Mock(return_value=[])
    return service


def test_sync_holiday_activity_logs_success(mock_neo4j_service, mock_bigquery_service):
    """Test successful sync of holiday activity logs."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU", "CA"]}],  # Account query
        [{"a": {"activity_id": "act_00"}}],  # Activity exists
        [  # Existing logs with IDs and no metric relationships
            {
                "log_id": "log_001",
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            }
        ],
    ]

    # Mock BigQuery returns more holidays than existing
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        },
        {
            "description": "Christmas",
            "start_date": "2024-12-25",
            "end_date": "2024-12-25",
        },
        {"description": "Easter", "start_date": "2024-03-31", "end_date": "2024-03-31"},
    ]

    # Mock successful creation
    mock_neo4j_service.execute_write_query.return_value = {"nodes_created": 2}

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Created 2 new logs, deleted 0 outdated logs" in data["message"]
    assert data["data"]["account_id"] == "test-account"
    assert data["data"]["regions"] == ["AU", "CA"]
    assert data["data"]["total_holidays_in_bigquery"] == 3
    assert data["data"]["existing_logs_before_sync"] == 1
    assert data["data"]["new_logs_created"] == 2
    assert data["data"]["logs_deleted"] == 0
    assert data["data"]["logs_protected_from_deletion"] == 0

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_no_project_id(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync fails when GCP project ID is not configured."""
    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {}, clear=True):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 503
    assert "BigQuery configuration missing" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_account_not_found(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync fails when account doesn't exist."""
    # Mock account doesn't exist
    mock_neo4j_service.execute_query.return_value = []

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=non-existent")

    assert response.status_code == 404
    assert "Account non-existent not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_no_regions(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync returns early when account has no regions."""
    # Mock account exists but has no regions
    mock_neo4j_service.execute_query.return_value = [{"regions": []}]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "No regions configured for account"
    assert data["data"]["new_logs_created"] == 0
    assert data["data"]["logs_deleted"] == 0

    # Verify BigQuery was not called
    mock_bigquery_service.query_holiday_activities.assert_not_called()

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_act_00_not_found(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync fails when act_00 doesn't exist for account."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        [],  # Activity doesn't exist
    ]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 404
    assert "Activity act_00 not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_all_exist(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync when all holidays already exist as activity logs."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        [{"a": {"activity_id": "act_00"}}],  # Activity exists
        [  # Existing logs match BigQuery results
            {
                "log_id": "log_001",
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_002",
                "description": "Christmas",
                "start_date": "2024-12-25",
                "end_date": "2024-12-25",
                "has_metric_relationship": False,
            },
        ],
    ]

    # Mock BigQuery returns same holidays
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        },
        {
            "description": "Christmas",
            "start_date": "2024-12-25",
            "end_date": "2024-12-25",
        },
    ]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Created 0 new logs, deleted 0 outdated logs" in data["message"]
    assert data["data"]["total_holidays_in_bigquery"] == 2
    assert data["data"]["existing_logs_before_sync"] == 2
    assert data["data"]["new_logs_created"] == 0
    assert data["data"]["logs_deleted"] == 0
    assert data["data"]["logs_protected_from_deletion"] == 0

    # Verify no write query was executed
    mock_neo4j_service.execute_write_query.assert_not_called()

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_error_handling(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync handles errors gracefully."""
    # Mock account exists
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        Exception("Database error"),  # Error checking activity
    ]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 500
    assert "Error syncing holiday activity logs" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_missing_account_id():
    """Test sync fails when account_id is not provided."""
    response = client.post("/api/v1/activities/logs/sync")

    assert (
        response.status_code == 422
    )  # Validation error for missing required parameter


def test_sync_holiday_activity_logs_with_deletion(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync deletes activity logs that are no longer in BigQuery."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        [{"a": {"activity_id": "act_00"}}],  # Activity exists
        [  # Existing logs - some will be deleted
            {
                "log_id": "log_001",
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_002",
                "description": "Christmas",
                "start_date": "2024-12-25",
                "end_date": "2024-12-25",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_003",
                "description": "Old Holiday",
                "start_date": "2023-07-04",
                "end_date": "2023-07-04",
                "has_metric_relationship": False,
            },
        ],
        [{"to_delete_count": 1}],  # Count query for deletion
    ]

    # Mock BigQuery returns only some holidays (Old Holiday is missing)
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        },
        {
            "description": "Christmas",
            "start_date": "2024-12-25",
            "end_date": "2024-12-25",
        },
    ]

    # Mock successful deletion
    mock_neo4j_service.execute_write_query.return_value = {"nodes_deleted": 1}

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Created 0 new logs, deleted 1 outdated logs" in data["message"]
    assert data["data"]["total_holidays_in_bigquery"] == 2
    assert data["data"]["existing_logs_before_sync"] == 3
    assert data["data"]["new_logs_created"] == 0
    assert data["data"]["logs_deleted"] == 1
    assert data["data"]["logs_protected_from_deletion"] == 0

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_protect_metric_relationships(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync protects activity logs that have metric relationships."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        [{"a": {"activity_id": "act_00"}}],  # Activity exists
        [  # Existing logs - one has metric relationship
            {
                "log_id": "log_001",
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_002",
                "description": "Christmas",
                "start_date": "2024-12-25",
                "end_date": "2024-12-25",
                "has_metric_relationship": True,
            },  # Protected
            {
                "log_id": "log_003",
                "description": "Old Holiday",
                "start_date": "2023-07-04",
                "end_date": "2023-07-04",
                "has_metric_relationship": False,
            },
        ],
        [{"to_delete_count": 1}],  # Count query for deletion
    ]

    # Mock BigQuery returns only New Year (Christmas and Old Holiday missing)
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        },
    ]

    # Mock successful deletion (only Old Holiday deleted, Christmas protected)
    mock_neo4j_service.execute_write_query.return_value = {"nodes_deleted": 1}

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Created 0 new logs, deleted 1 outdated logs" in data["message"]
    assert data["data"]["total_holidays_in_bigquery"] == 1
    assert data["data"]["existing_logs_before_sync"] == 3
    assert data["data"]["new_logs_created"] == 0
    assert data["data"]["logs_deleted"] == 1
    assert data["data"]["logs_protected_from_deletion"] == 1  # Christmas was protected

    # Clean up
    app.dependency_overrides.clear()


def test_sync_holiday_activity_logs_create_and_delete(
    mock_neo4j_service, mock_bigquery_service
):
    """Test sync creates new logs and deletes outdated ones in same operation."""
    # Mock account exists with regions
    mock_neo4j_service.execute_query.side_effect = [
        [{"regions": ["AU"]}],  # Account query
        [{"a": {"activity_id": "act_00"}}],  # Activity exists
        [  # Existing logs
            {
                "log_id": "log_001",
                "description": "New Year",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_002",
                "description": "Old Holiday 1",
                "start_date": "2023-07-04",
                "end_date": "2023-07-04",
                "has_metric_relationship": False,
            },
            {
                "log_id": "log_003",
                "description": "Old Holiday 2",
                "start_date": "2023-05-01",
                "end_date": "2023-05-01",
                "has_metric_relationship": True,
            },  # Protected
        ],
        [{"to_delete_count": 1}],  # Count query for deletion
    ]

    # Mock BigQuery returns different holidays
    mock_bigquery_service.query_holiday_activities.return_value = [
        {
            "description": "New Year",
            "start_date": "2024-01-01",
            "end_date": "2024-01-01",
        },
        {
            "description": "Christmas",
            "start_date": "2024-12-25",
            "end_date": "2024-12-25",
        },  # New
        {
            "description": "Easter",
            "start_date": "2024-03-31",
            "end_date": "2024-03-31",
        },  # New
    ]

    # Mock successful operations
    mock_neo4j_service.execute_write_query.side_effect = [
        {"nodes_created": 2},  # Create new logs
        {"nodes_deleted": 1},  # Delete query returns nodes deleted
    ]

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    app.dependency_overrides[get_bigquery_service] = lambda: mock_bigquery_service

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT_ID": "test-project"}):
        response = client.post("/api/v1/activities/logs/sync?account_id=test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Created 2 new logs, deleted 1 outdated logs" in data["message"]
    assert data["data"]["total_holidays_in_bigquery"] == 3
    assert data["data"]["existing_logs_before_sync"] == 3
    assert data["data"]["new_logs_created"] == 2
    assert data["data"]["logs_deleted"] == 1
    assert (
        data["data"]["logs_protected_from_deletion"] == 1
    )  # Old Holiday 2 was protected

    # Clean up
    app.dependency_overrides.clear()
