"""Tests for move account endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app

# Create test client
client = TestClient(app)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(
        return_value=[
            {
                "acc": {"account_id": "test-account"},
                "old_org_name": "Old Organization",
                "new_org_name": "New Organization",
            }
        ]
    )
    return mock_service


def test_move_account_success(mock_neo4j_service):
    """Test successfully moving account between organizations."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Current organization exists
        [{"exists": True}],  # Target organization exists
        [{"account_exists": True}],  # Account exists in current organization
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "moved successfully" in data["message"]
    assert data["data"]["account_id"] == "test-account"
    assert data["data"]["old_organization_id"] == "current-org"
    assert data["data"]["new_organization_id"] == "target-org"

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_missing_new_org_id(mock_neo4j_service):
    """Test moving account with missing new_organization_id."""
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {}  # Missing new_organization_id

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 400
    assert "new_organization_id is required" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_same_organization(mock_neo4j_service):
    """Test moving account to the same organization."""
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "current-org"}  # Same as current

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 400
    assert "Cannot move account to the same organization" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_current_org_not_found(mock_neo4j_service):
    """Test moving account when current organization doesn't exist."""
    # Mock the checks - current org doesn't exist
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": False}],  # Current organization doesn't exist
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/nonexistent-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 404
    assert "Current organization nonexistent-org not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_target_org_not_found(mock_neo4j_service):
    """Test moving account when target organization doesn't exist."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Current organization exists
        [{"exists": False}],  # Target organization doesn't exist
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "nonexistent-target"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 404
    assert (
        "Target organization nonexistent-target not found" in response.json()["detail"]
    )

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_account_not_found(mock_neo4j_service):
    """Test moving account that doesn't exist in current organization."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Current organization exists
        [{"exists": True}],  # Target organization exists
        [{"account_exists": False}],  # Account doesn't exist in current organization
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/nonexistent-account",
        json=request_data,
    )

    assert response.status_code == 404
    assert (
        "Account nonexistent-account not found in organization current-org"
        in response.json()["detail"]
    )

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_database_unavailable(mock_neo4j_service):
    """Test moving account when database is unavailable."""
    # Mock database health check failure
    mock_neo4j_service.health_check.return_value = False

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 503
    assert "Database service unavailable" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_move_operation_fails(mock_neo4j_service):
    """Test moving account when the move operation fails."""
    # Mock the checks to pass
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Current organization exists
        [{"exists": True}],  # Target organization exists
        [{"account_exists": True}],  # Account exists in current organization
    ]

    # Mock write query to return empty result (failure)
    mock_neo4j_service.execute_write_query.return_value = []

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 500
    assert "Failed to move account" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_with_organization_names(mock_neo4j_service):
    """Test moving account and verify organization names are included in response."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Current organization exists
        [{"exists": True}],  # Target organization exists
        [{"account_exists": True}],  # Account exists in current organization
    ]

    # Mock write query with organization names
    mock_neo4j_service.execute_write_query.return_value = [
        {
            "acc": {"account_id": "test-account"},
            "old_org_name": "Current Organization Name",
            "new_org_name": "Target Organization Name",
        }
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["old_organization_name"] == "Current Organization Name"
    assert data["data"]["new_organization_name"] == "Target Organization Name"
    assert "Current Organization Name" in data["message"]
    assert "Target Organization Name" in data["message"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_invalid_request_format(mock_neo4j_service):
    """Test moving account with invalid request format."""
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    # Invalid request data - not a dict
    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json="invalid-format",
    )

    assert response.status_code == 422  # Pydantic validation error

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_empty_new_org_id(mock_neo4j_service):
    """Test moving account with empty new_organization_id."""
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": ""}  # Empty string

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 400
    assert "new_organization_id is required" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_move_account_neo4j_connection_error(mock_neo4j_service):
    """Test moving account when Neo4j connection fails."""
    # Mock Neo4j connection error
    mock_neo4j_service.execute_query.side_effect = Exception("Neo4j connection failed")

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    request_data = {"new_organization_id": "target-org"}

    response = client.put(
        "/api/v1/organizations/current-org/move-account/test-account",
        json=request_data,
    )

    assert response.status_code == 503
    assert "Database service unavailable" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()
