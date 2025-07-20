"""Tests for accounts endpoints."""

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
        return_value={
            "nodes_created": 1,
            "relationships_created": 1,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }
    )
    return mock_service


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

    response = client.get("/api/v1/accounts/test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "test-account"
    assert data["account_name"] == "Test Account"

    # Clean up
    app.dependency_overrides.clear()


def test_create_account(mock_neo4j_service):
    """Test creating a new account."""

    # Mock the checks and creation
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]  # Organization exists
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]  # Account doesn't exist (UUID collision check)
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            # Handle get_account query
            return [
                {
                    "acc": {
                        "account_id": parameters[
                            "account_id"
                        ],  # Use the generated UUID
                        "account_name": "New Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "Active",
                        "websites": ["https://new.com"],
                        "timezone": "America/New_York",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

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
    data = response.json()
    # The actual UUID will be different from the mock, but we can test the format
    assert data["account_id"].startswith("acc_")
    assert len(data["account_id"]) == 36  # 'acc_' + 32 character UUID
    assert data["account_name"] == "New Account"
    assert data["organization_id"] == "test-org"

    # Clean up
    app.dependency_overrides.clear()


def test_create_account_organization_not_found(mock_neo4j_service):
    """Test creating an account for non-existent organization."""
    # Mock organization doesn't exist
    mock_neo4j_service.execute_query.return_value = [{"exists": False}]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    new_account_data = {
        "account_name": "New Account",
        "organization_id": "non-existent-org",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://new.com"],
        "timezone": "America/New_York",
    }

    response = client.post("/api/v1/accounts/", json=new_account_data)

    assert response.status_code == 404
    assert "Organization" in response.json()["detail"]
    assert "not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_update_account(mock_neo4j_service):
    """Test updating an account."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Account exists
        [
            {  # Return updated account
                "acc": {
                    "account_id": "test-account",
                    "account_name": "Test Account",
                    "organization_id": "test-org",
                    "industry": "Technology",
                    "status": "Inactive",
                    "websites": ["https://updated.com"],
                    "timezone": "America/New_York",
                }
            }
        ],
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    update_data = {"status": "Inactive", "websites": ["https://updated.com"]}

    response = client.put("/api/v1/accounts/test-account", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Inactive"
    assert data["websites"] == ["https://updated.com"]

    # Clean up
    app.dependency_overrides.clear()


def test_delete_account(mock_neo4j_service):
    """Test deleting an account."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Account exists
        [{"related_count": 0}],  # No related entities
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.delete("/api/v1/accounts/test-account")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]

    # Clean up
    app.dependency_overrides.clear()


def test_delete_account_with_related_entities(mock_neo4j_service):
    """Test deleting an account that has related entities."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Account exists
        [{"related_count": 5}],  # Has 5 related entities
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.delete("/api/v1/accounts/test-account")

    assert response.status_code == 400
    assert "Cannot delete account with" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


# Edge case tests
def test_create_account_missing_required_fields(mock_neo4j_service):
    """Test creating account with missing required fields."""
    # Missing account_name and organization_id
    account_data = {"industry": "Technology", "status": "Active"}

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/accounts/", json=account_data)

    assert response.status_code == 400  # Application validation error

    # Clean up
    app.dependency_overrides.clear()


def test_create_account_invalid_status(mock_neo4j_service):
    """Test creating account with invalid status value."""
    account_data = {
        "account_name": "Test Account",
        "organization_id": "test-org",
        "industry": "Technology",
        "status": "InvalidStatus",  # Should be Active/Inactive/Suspended
        "websites": ["https://example.com"],
        "timezone": "America/New_York",
    }

    # Mock organization exists and account creation flows
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]  # Organization exists
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]  # Account doesn't exist (UUID collision check)
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            # Handle get_account query
            return [
                {
                    "acc": {
                        "account_id": parameters[
                            "account_id"
                        ],  # Use the generated UUID
                        "account_name": "Test Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "InvalidStatus",
                        "websites": ["https://example.com"],
                        "timezone": "America/New_York",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/accounts/", json=account_data)

    # Should succeed - status field has no validation constraints
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"].startswith("acc_")
    assert data["status"] == "InvalidStatus"  # Status value is preserved

    # Clean up
    app.dependency_overrides.clear()


def test_create_account_invalid_timezone(mock_neo4j_service):
    """Test creating account with invalid timezone."""
    account_data = {
        "account_name": "Test Account",
        "organization_id": "test-org",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://example.com"],
        "timezone": "Invalid/Timezone",  # Invalid timezone
    }

    # Mock organization exists and account creation
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]  # Organization exists
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]  # Account doesn't exist (UUID collision check)
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            # Handle get_account query
            return [
                {
                    "acc": {
                        "account_id": parameters[
                            "account_id"
                        ],  # Use the generated UUID
                        "account_name": "Test Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "Active",
                        "websites": ["https://example.com"],
                        "timezone": "Invalid/Timezone",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/accounts/", json=account_data)

    # Should still create (timezone validation is lenient)
    assert response.status_code == 200

    # Clean up
    app.dependency_overrides.clear()


def test_create_account_empty_websites_array(mock_neo4j_service):
    """Test creating account with empty websites array."""
    account_data = {
        "account_name": "Test Account",
        "organization_id": "test-org",
        "industry": "Technology",
        "status": "Active",
        "websites": [],  # Empty array
        "timezone": "America/New_York",
    }

    # Mock organization exists and account creation
    def mock_execute_query(query, parameters=None):
        if "Organization" in query and "exists" in query:
            return [{"exists": True}]  # Organization exists
        elif "Account" in query and "exists" in query:
            return [{"exists": False}]  # Account doesn't exist (UUID collision check)
        elif "MATCH (acc:Account" in query and "RETURN acc" in query:
            # Handle get_account query
            return [
                {
                    "acc": {
                        "account_id": parameters[
                            "account_id"
                        ],  # Use the generated UUID
                        "account_name": "Test Account",
                        "organization_id": "test-org",
                        "industry": "Technology",
                        "status": "Active",
                        "websites": [],
                        "timezone": "America/New_York",
                    }
                }
            ]
        else:
            return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/accounts/", json=account_data)

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"].startswith("acc_")
    assert data["websites"] == []  # Empty array is valid

    # Clean up
    app.dependency_overrides.clear()


def test_update_account_invalid_field_types(mock_neo4j_service):
    """Test updating account with invalid field types."""
    # Mock account exists
    mock_neo4j_service.execute_query.return_value = [{"exists": True}]

    update_data = {
        "account_name": ["should", "be", "string"],  # Should be string
        "status": 123,  # Should be string
        "websites": "should-be-array",  # Should be array
    }

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.put("/api/v1/accounts/test-account", json=update_data)

    assert response.status_code == 422  # Pydantic validation error

    # Clean up
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


def test_create_account_uuid_collision_detection(mock_neo4j_service):
    """Test account creation UUID collision detection (extremely rare scenario)."""
    account_data = {
        "account_name": "Test Account",
        "organization_id": "test-org",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://example.com"],
        "timezone": "America/New_York",
    }

    # Mock organization exists check passes, but first UUID collides, second succeeds
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{"exists": True}],  # First UUID collision (extremely rare)
        [{"exists": False}],  # Second UUID is unique
        [
            {  # Return created account
                "acc": {
                    "account_id": "acc_seconduuidgenerated123456789abc",
                    "account_name": "Test Account",
                    "organization_id": "test-org",
                    "industry": "Technology",
                    "status": "Active",
                    "websites": ["https://example.com"],
                    "timezone": "America/New_York",
                }
            }
        ],
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/accounts/", json=account_data)

    # Should succeed after collision detection and retry
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"].startswith("acc_")
    assert data["account_name"] == "Test Account"

    # Clean up
    app.dependency_overrides.clear()
