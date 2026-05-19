import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)

client = TestClient(app)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service for testing."""
    mock_service = MagicMock()

    # Use AsyncMock for async methods
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(
        return_value={
            "nodes_created": 1,
            "nodes_deleted": 0,
            "relationships_created": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }
    )

    return mock_service


# Test organization endpoints
def test_get_organizations(mock_neo4j_service):
    """Test getting all organizations."""
    # Mock data
    mock_orgs = [
        {
            "org": {
                "organization_id": "org-1",
                "organization_name": "Company A",
                "plan": "Professional",
                "website": "https://companya.com",
                "company_size": "medium",
                "agency": False,
                "child_organizations": [],
                "subscription": json.dumps(
                    {
                        "plan_name": "Pro",
                        "plan_description": "Professional features",
                        "price": 99.0,
                        "currency": "USD",
                        "billing_cycle": "monthly",
                        "next_billing_date": "2024-03-01",
                        "features": ["Feature 1", "Feature 2"],
                        "usage": {"reports_generated": 50, "reports_limit": 100},
                    }
                ),
                "billing": json.dumps(
                    {
                        "payment_method": {
                            "last_four": "1234",
                            "brand": "Visa",
                            "expires": "12/25",
                        },
                        "address": "123 Main St",
                        "tax_id": "123456789",
                    }
                ),
                "team": json.dumps(
                    {"members_used": 5, "members_limit": 10, "pending_invitations": 2}
                ),
            }
        },
        {
            "org": {
                "organization_id": "org-2",
                "organization_name": "Company B",
                "plan": "Enterprise",
                "website": "https://companyb.com",
                "company_size": "large",
                "agency": True,
                "child_organizations": ["org-3", "org-4"],
                "subscription": json.dumps(
                    {
                        "plan_name": "Enterprise",
                        "plan_description": "Full features",
                        "price": 299.0,
                        "currency": "USD",
                        "billing_cycle": "monthly",
                        "next_billing_date": "2024-03-01",
                        "features": ["All Features"],
                        "usage": {"reports_generated": 200, "reports_limit": 1000},
                    }
                ),
                "billing": json.dumps(
                    {
                        "payment_method": {
                            "last_four": "5678",
                            "brand": "Mastercard",
                            "expires": "06/26",
                        },
                        "address": "456 Corporate Blvd",
                        "tax_id": "987654321",
                    }
                ),
                "team": json.dumps(
                    {"members_used": 25, "members_limit": 50, "pending_invitations": 5}
                ),
            }
        },
    ]

    mock_neo4j_service.execute_query.return_value = mock_orgs

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/organizations/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["organizations"]) == 2
    assert data["organizations"][0]["organization_name"] == "Company A"
    assert data["organizations"][1]["organization_name"] == "Company B"

    # Verify subscription data is properly deserialized
    assert data["organizations"][0]["subscription"]["plan_name"] == "Pro"
    assert data["organizations"][1]["subscription"]["plan_name"] == "Enterprise"

    # Verify agency and child organizations
    assert data["organizations"][0]["agency"] is False
    assert data["organizations"][1]["agency"] is True
    assert data["organizations"][1]["child_organizations"] == ["org-3", "org-4"]

    # Clean up
    app.dependency_overrides.clear()


def test_get_organization_by_id(mock_neo4j_service):
    """Test getting a specific organization by ID."""
    # Mock data
    mock_org = [
        {
            "org": {
                "organization_id": "org-1",
                "organization_name": "Company A",
                "plan": "Professional",
                "website": "https://companya.com",
                "company_size": "medium",
                "agency": False,
                "child_organizations": [],
                "subscription": json.dumps(
                    {
                        "plan_name": "Pro",
                        "plan_description": "Professional features",
                        "price": 99.0,
                        "currency": "USD",
                        "billing_cycle": "monthly",
                        "next_billing_date": "2024-03-01",
                        "features": ["Feature 1", "Feature 2"],
                        "usage": {"reports_generated": 50, "reports_limit": 100},
                    }
                ),
                "billing": json.dumps(
                    {
                        "payment_method": {
                            "last_four": "1234",
                            "brand": "Visa",
                            "expires": "12/25",
                        },
                        "address": "123 Main St",
                        "tax_id": "123456789",
                    }
                ),
                "team": json.dumps(
                    {"members_used": 5, "members_limit": 10, "pending_invitations": 2}
                ),
            }
        }
    ]

    mock_neo4j_service.execute_query.return_value = mock_org

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/organizations/org-1")

    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == "org-1"
    assert data["organization_name"] == "Company A"
    assert data["subscription"]["plan_name"] == "Pro"

    # Clean up
    app.dependency_overrides.clear()


def test_create_organization(mock_neo4j_service):
    """Test creating a new organization."""
    org_data = {
        "organization_name": "New Company",
        "plan": "Professional",
        "website": "https://newcompany.com",
        "company_size": "medium",
        "agency": False,
        "subscription": {
            "plan_name": "Professional Plan",
            "plan_description": "Advanced analytics and team features",
            "price": 99.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-03-01",
            "features": ["Advanced Analytics", "Team Collaboration", "API Access"],
            "usage": {"reports_generated": 0, "reports_limit": 1000},
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "Visa",
                "expires": "12/26",
            },
            "address": "456 New St, Suite 100, New York, NY 10001",
            "tax_id": "987654321",
        },
        "team": {"members_used": 1, "members_limit": 10, "pending_invitations": 0},
    }

    # Set up side_effect for execute_query to handle different queries
    call_count = 0

    async def mock_execute_query(query, params=None):
        nonlocal call_count
        call_count += 1

        # First two calls: check if organization exists (should return False)
        if "count(org) > 0 as exists" in query:
            return [{"exists": False}]

        # Final call: return created organization
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "test-org-id-123",
                        "organization_name": "New Company",
                        "plan": "Professional",
                        "website": "https://newcompany.com",
                        "company_size": "medium",
                        "agency": False,
                        "child_organizations": [],
                        "subscription": json.dumps(
                            {
                                "plan_name": "Professional Plan",
                                "plan_description": "Advanced analytics and team features",
                                "price": 99.0,
                                "currency": "USD",
                                "billing_cycle": "monthly",
                                "next_billing_date": "2024-03-01",
                                "features": [
                                    "Advanced Analytics",
                                    "Team Collaboration",
                                    "API Access",
                                ],
                                "usage": {
                                    "reports_generated": 0,
                                    "reports_limit": 1000,
                                },
                            }
                        ),
                        "billing": json.dumps(
                            {
                                "payment_method": {
                                    "last_four": "1234",
                                    "brand": "Visa",
                                    "expires": "12/26",
                                },
                                "address": "456 New St, Suite 100, New York, NY 10001",
                                "tax_id": "987654321",
                            }
                        ),
                        "team": json.dumps(
                            {
                                "members_used": 1,
                                "members_limit": 10,
                                "pending_invitations": 0,
                            }
                        ),
                    }
                }
            ]

        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    # Mock UUID generation
    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "test-org-id-123"

        response = client.post("/api/v1/organizations/", json=org_data)

    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == "test-org-id-123"
    assert data["organization_name"] == "New Company"
    assert data["company_size"] == "medium"

    # Clean up
    app.dependency_overrides.clear()


def test_update_organization(mock_neo4j_service):
    """Test updating an existing organization."""
    update_data = {
        "organization_name": "Updated Company Name",
        "website": "https://updated.com",
    }

    # Mock the queries
    async def mock_execute_query(query, params=None):
        # Check if organization exists
        if "count(org) > 0 as exists" in query:
            return [{"exists": True}]

        # Return updated organization
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "test-org",
                        "organization_name": "Updated Company Name",
                        "plan": "Professional",
                        "website": "https://updated.com",
                        "company_size": "medium",
                        "agency": False,
                        "child_organizations": [],
                        "subscription": json.dumps(
                            {
                                "plan_name": "Pro",
                                "plan_description": "Professional features",
                                "price": 99.0,
                                "currency": "USD",
                                "billing_cycle": "monthly",
                                "next_billing_date": "2024-03-01",
                                "features": ["Feature 1"],
                                "usage": {
                                    "reports_generated": 50,
                                    "reports_limit": 100,
                                },
                            }
                        ),
                        "billing": json.dumps(
                            {
                                "payment_method": {
                                    "last_four": "1234",
                                    "brand": "Visa",
                                    "expires": "12/25",
                                },
                                "address": "123 Main St",
                                "tax_id": "123456789",
                            }
                        ),
                        "team": json.dumps(
                            {
                                "members_used": 5,
                                "members_limit": 10,
                                "pending_invitations": 2,
                            }
                        ),
                    }
                }
            ]

        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.put("/api/v1/organizations/test-org", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == "Updated Company Name"
    assert data["website"] == "https://updated.com"

    # Clean up
    app.dependency_overrides.clear()


def test_delete_organization(mock_neo4j_service):
    """Test deleting an organization."""

    # Mock the checks and deletion
    async def mock_execute_query(query, params=None):
        if "count(org) > 0 as exists" in query:
            return [{"exists": True}]
        if "count(acc) as account_count" in query:
            return [{"account_count": 0}]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Mock the write query to return proper summary
    mock_neo4j_service.execute_write_query.return_value = {
        "nodes_deleted": 1,
        "relationships_deleted": 0,
        "nodes_created": 0,
        "relationships_created": 0,
        "properties_set": 0,
    }

    # Mock Firestore service
    mock_firestore_service = MagicMock()
    mock_firestore_client = MagicMock()
    mock_firestore_service.get_client.return_value = mock_firestore_client

    # Mock user documents with organization permissions
    mock_user1 = MagicMock()
    mock_user1.id = "user1"
    mock_user1.to_dict.return_value = {
        "permissions": {"organizations": {"test-org": "admin", "other-org": "member"}}
    }
    mock_user1_ref = MagicMock()
    mock_user1.reference = mock_user1_ref

    mock_user2 = MagicMock()
    mock_user2.id = "user2"
    mock_user2.to_dict.return_value = {
        "permissions": {"organizations": {"test-org": "member"}}
    }
    mock_user2_ref = MagicMock()
    mock_user2.reference = mock_user2_ref

    # Mock collection stream
    mock_users_collection = MagicMock()
    mock_users_collection.stream.return_value = [mock_user1, mock_user2]
    mock_firestore_client.collection.return_value = mock_users_collection

    # Override dependencies
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    from src.kene_api.firestore import get_firestore_service

    app.dependency_overrides[get_firestore_service] = lambda: mock_firestore_service

    response = client.delete("/api/v1/organizations/test-org")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]
    assert data["data"]["organization_id"] == "test-org"
    assert data["data"]["nodes_deleted"] == 1

    # Verify Firestore cleanup was called
    assert mock_user1_ref.update.called
    assert mock_user2_ref.update.called

    # Verify the correct updates were made
    mock_user1_ref.update.assert_called_with(
        {
            "permissions.organizations": {"other-org": "member"}  # test-org removed
        }
    )
    mock_user2_ref.update.assert_called_with(
        {
            "permissions.organizations": {}  # test-org was the only org
        }
    )

    # Clean up
    app.dependency_overrides.clear()


def test_delete_organization_with_accounts(mock_neo4j_service):
    """Test deleting an organization that has accounts."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{"account_count": 2}],  # Has 2 accounts
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.delete("/api/v1/organizations/test-org")

    assert response.status_code == 400
    assert "Cannot delete organization with" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


# Edge case tests
def test_create_organization_missing_required_fields(mock_neo4j_service):
    """Test creating organization with missing required fields."""
    # Missing organization_name
    org_data = {
        "company_size": "50-100",
        "plan": "free",
        "website": "https://example.com",
    }

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/organizations/", json=org_data)

    # The API returns 400 for validation errors, not 422
    assert response.status_code == 400
    assert "organization_name is required" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_create_organization_invalid_data_types(mock_neo4j_service):
    """Test creating organization with invalid data types."""
    org_data = {
        "organization_name": 123,  # Should be string
        "company_size": "50-100",
        "plan": "free",
        "website": "not-a-valid-url",
        "agency": "yes",  # Should be boolean
        "subscription": {
            "plan_name": "Test Plan",
            "plan_description": "Test",
            "price": "not-a-number",  # Should be float
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "invalid-date",
            "features": "should-be-list",  # Should be list
            "usage": {"reports_generated": 10, "reports_limit": 100},
        },
    }

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.post("/api/v1/organizations/", json=org_data)

    assert response.status_code == 422  # Validation error

    # Clean up
    app.dependency_overrides.clear()


def test_create_organization_extremely_long_name(mock_neo4j_service):
    """Test creating organization with extremely long name."""
    org_data = {
        "organization_name": "A" * 1000,  # 1000 character name
        "company_size": "50-100",
        "plan": "free",
        "website": "https://example.com",
        "agency": False,
        "subscription": {
            "plan_name": "Test Plan",
            "plan_description": "Test",
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 10, "reports_limit": 100},
        },
        "billing": {},
        "team": {},
    }

    # Mock successful creation with generated ID
    mock_neo4j_service.execute_query.return_value = [
        {
            "org": {
                "organization_id": "a" * 100,  # Truncated ID
                "organization_name": "A" * 1000,
                "company_size": "50-100",
                "plan": "free",
                "website": "https://example.com",
                "agency": False,
            }
        }
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    # The API should handle this gracefully
    # Whether it truncates or allows long names is implementation specific
    response = client.post("/api/v1/organizations/", json=org_data)

    # Should either succeed or return a specific error
    assert response.status_code in [200, 400, 422]

    # Clean up
    app.dependency_overrides.clear()


def test_update_organization_non_existent(mock_neo4j_service):
    """Test updating a non-existent organization."""
    update_data = {
        "organization_name": "Updated Name",
    }

    # Mock that organization doesn't exist
    mock_neo4j_service.execute_query.return_value = [{"exists": False}]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.put("/api/v1/organizations/non-existent-org", json=update_data)

    assert response.status_code == 404
    assert "Organization not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_delete_organization_non_existent(mock_neo4j_service):
    """Test deleting a non-existent organization."""
    # Mock that organization doesn't exist
    mock_neo4j_service.execute_query.return_value = [{"exists": False}]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.delete("/api/v1/organizations/non-existent-org")

    assert response.status_code == 404
    assert "Organization not found" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_neo4j_connection_failure(mock_neo4j_service):
    """Test handling Neo4j connection failure."""
    # Mock health check failure
    mock_neo4j_service.health_check = AsyncMock(return_value=False)

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/organizations/")

    assert response.status_code == 503
    assert "Database service unavailable" in response.json()["detail"]

    # Clean up
    app.dependency_overrides.clear()


def test_organization_with_agency_and_children(mock_neo4j_service):
    """Test creating and retrieving an agency organization with child organizations."""
    org_data = {
        "organization_name": "Agency Corp",
        "plan": "enterprise",
        "website": "https://agency.com",
        "company_size": "100-500",
        "agency": True,
        "child_organizations": ["child-org-1", "child-org-2", "child-org-3"],
        "subscription": {
            "plan_name": "Enterprise",
            "plan_description": "Full agency features",
            "price": 499.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-03-01",
            "features": ["Multi-org management", "Advanced reporting"],
            "usage": {"reports_generated": 0, "reports_limit": 5000},
        },
        "billing": {
            "payment_method": {
                "last_four": "9999",
                "brand": "Amex",
                "expires": "12/27",
            },
            "address": "789 Agency Ave",
            "tax_id": "555555555",
        },
        "team": {"members_used": 20, "members_limit": 100, "pending_invitations": 5},
    }

    # Mock the write query execution
    mock_neo4j_service.execute_write_query.return_value = None

    # Mock the return query
    def mock_execute_query(query, parameters=None):
        if "CREATE" in query:
            return [
                {
                    "org": {
                        "organization_id": parameters["organization_id"],
                        "organization_name": parameters["organization_name"],
                        "plan": parameters["plan"],
                        "website": parameters["website"],
                        "company_size": parameters["company_size"],
                        "agency": parameters["agency"],
                        "child_organizations": parameters["child_organizations"],
                        "subscription": parameters["subscription"],
                        "billing": parameters["billing"],
                        "team": parameters["team"],
                    }
                }
            ]
        elif "MATCH" in query and "RETURN org" in query:
            return [
                {
                    "org": {
                        "organization_id": "agency-org-id",
                        "organization_name": "Agency Corp",
                        "plan": "enterprise",
                        "website": "https://agency.com",
                        "company_size": "100-500",
                        "agency": True,
                        "child_organizations": [
                            "child-org-1",
                            "child-org-2",
                            "child-org-3",
                        ],
                        "subscription": json.dumps(org_data["subscription"]),
                        "billing": json.dumps(org_data["billing"]),
                        "team": json.dumps(org_data["team"]),
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    # Mock UUID generation
    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "agency-org-id"

        response = client.post("/api/v1/organizations/", json=org_data)

    assert response.status_code == 200
    data = response.json()
    assert data["agency"] is True
    assert len(data["child_organizations"]) == 3
    assert data["child_organizations"] == ["child-org-1", "child-org-2", "child-org-3"]

    # Clean up
    app.dependency_overrides.clear()


def test_organization_special_characters_in_name(mock_neo4j_service):
    """Test creating organization with special characters in name."""
    org_data = {
        "organization_name": "Company & Co. (Test) #1 - Special €£¥",
        "company_size": "50-100",
        "plan": "professional",
        "website": "https://special-chars.com",
        "agency": False,
        "subscription": {
            "plan_name": "Test Plan",
            "plan_description": "Test",
            "price": 99.0,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 0, "reports_limit": 100},
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "Visa",
                "expires": "12/26",
            },
            "address": "123 Special St",
            "tax_id": "123456789",
        },
        "team": {"members_used": 1, "members_limit": 5, "pending_invitations": 0},
    }

    # Mock successful creation with query handling
    async def mock_execute_query(query, params=None):
        if "count(org) > 0 as exists" in query:
            return [{"exists": False}]
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "special-org-id",
                        "organization_name": "Company & Co. (Test) #1 - Special €£¥",
                        "company_size": "50-100",
                        "plan": "professional",
                        "website": "https://special-chars.com",
                        "agency": False,
                        "child_organizations": [],
                        "subscription": json.dumps(org_data["subscription"]),
                        "billing": json.dumps(org_data["billing"]),
                        "team": json.dumps(org_data["team"]),
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "special-org-id"

        response = client.post("/api/v1/organizations/", json=org_data)

    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == "Company & Co. (Test) #1 - Special €£¥"

    # Clean up
    app.dependency_overrides.clear()


def test_organization_empty_strings_and_nulls(mock_neo4j_service):
    """Test creating organization with empty strings and null values."""
    org_data = {
        "organization_name": "Minimal Org",
        "company_size": "",  # Empty string
        "plan": "free",
        "website": "",  # Empty string
        "agency": False,
        "child_organizations": [],  # Empty list
        "subscription": {
            "plan_name": "Free",
            "plan_description": "",  # Empty string
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": [],  # Empty list
            "usage": {"reports_generated": 0, "reports_limit": 10},
        },
        "billing": {
            "payment_method": {"last_four": "", "brand": "", "expires": ""},
            "address": "",
            "tax_id": "",
        },
        "team": {"members_used": 1, "members_limit": 1, "pending_invitations": 0},
    }

    # Mock query handling
    async def mock_execute_query(query, params=None):
        if "count(org) > 0 as exists" in query:
            return [{"exists": False}]
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "minimal-org-id",
                        "organization_name": "Minimal Org",
                        "company_size": "",
                        "plan": "free",
                        "website": "",
                        "agency": False,
                        "child_organizations": [],
                        "subscription": json.dumps(org_data["subscription"]),
                        "billing": json.dumps(org_data["billing"]),
                        "team": json.dumps(org_data["team"]),
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "minimal-org-id"

        response = client.post("/api/v1/organizations/", json=org_data)

    assert response.status_code == 200
    data = response.json()
    assert data["website"] == ""
    assert data["company_size"] == ""

    # Clean up
    app.dependency_overrides.clear()


def test_organization_circular_parent_child_relationship(mock_neo4j_service):
    """Test handling circular parent-child relationships."""
    # Create an organization that lists itself as a child
    org_data = {
        "organization_name": "Self-referencing Org",
        "company_size": "50-100",
        "plan": "professional",
        "website": "https://circular.com",
        "agency": True,
        "child_organizations": ["self-org-id"],  # References itself
        "subscription": {
            "plan_name": "Test Plan",
            "plan_description": "Test",
            "price": 99.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 0, "reports_limit": 100},
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "Visa",
                "expires": "12/26",
            },
            "address": "123 Test St",
            "tax_id": "123456789",
        },
        "team": {
            "members_used": 1,
            "members_limit": 5,
            "pending_invitations": 0,
        },
    }

    # Mock query handling
    async def mock_execute_query(query, params=None):
        if "count(org) > 0 as exists" in query:
            return [{"exists": False}]
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "self-org-id",
                        "organization_name": "Self-referencing Org",
                        "company_size": "50-100",
                        "plan": "professional",
                        "website": "https://circular.com",
                        "agency": True,
                        "child_organizations": ["self-org-id"],
                        "subscription": json.dumps(org_data["subscription"]),
                        "billing": json.dumps(org_data["billing"]),
                        "team": json.dumps(org_data["team"]),
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "self-org-id"

        response = client.post("/api/v1/organizations/", json=org_data)

    # The API should handle this gracefully
    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == "self-org-id"
    assert "self-org-id" in data["child_organizations"]

    # Clean up
    app.dependency_overrides.clear()


def test_organization_complex_hierarchy(mock_neo4j_service):
    """Test organization with complex parent-child hierarchy."""
    # Mock a query that returns an organization with both parent and child relationships
    mock_neo4j_service.execute_query.return_value = [
        {
            "org": {
                "organization_id": "middle-org",
                "organization_name": "Middle Organization",
                "plan": "professional",
                "website": "https://middle.com",
                "company_size": "100-500",
                "agency": True,
                "child_organizations": ["child-1", "child-2"],
                "subscription": json.dumps(
                    {
                        "plan_name": "Pro",
                        "plan_description": "Professional",
                        "price": 199.0,
                        "currency": "USD",
                        "billing_cycle": "monthly",
                        "next_billing_date": "2024-03-01",
                        "features": ["All features"],
                        "usage": {"reports_generated": 100, "reports_limit": 1000},
                    }
                ),
                "billing": json.dumps(
                    {
                        "payment_method": {
                            "last_four": "7890",
                            "brand": "Visa",
                            "expires": "06/26",
                        },
                        "address": "789 Middle Rd",
                        "tax_id": "999999999",
                    }
                ),
                "team": json.dumps(
                    {"members_used": 15, "members_limit": 25, "pending_invitations": 3}
                ),
            }
        }
    ]

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    response = client.get("/api/v1/organizations/middle-org")

    assert response.status_code == 200
    data = response.json()
    assert data["child_organizations"] == ["child-1", "child-2"]
    # Parent relationship might be tracked differently

    # Clean up
    app.dependency_overrides.clear()


def test_create_organization_without_company_size(mock_neo4j_service):
    """Test creating organization without company_size (should work as it's optional)."""
    org_data = {
        "organization_name": "Company Without Size",
        "plan": "free",
        "website": "https://example.com",
        "agency": False,
        "subscription": {
            "plan_name": "Test Plan",
            "plan_description": "Test",
            "price": 0.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 10, "reports_limit": 100},
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "Visa",
                "expires": "12/26",
            },
            "address": "123 Test St",
            "tax_id": "123456789",
        },
        "team": {
            "members_used": 1,
            "members_limit": 5,
            "pending_invitations": 0,
        },
    }

    # Mock query handling
    async def mock_execute_query(query, params=None):
        if "count(org) > 0 as exists" in query:
            return [{"exists": False}]
        if "MATCH (org:Organization {organization_id:" in query:
            return [
                {
                    "org": {
                        "organization_id": "test-org-id",
                        "organization_name": "Company Without Size",
                        "plan": "free",
                        "website": "https://example.com",
                        "company_size": "",  # Empty string when not provided
                        "agency": False,
                        "child_organizations": [],
                        "subscription": json.dumps(org_data["subscription"]),
                        "billing": json.dumps(org_data["billing"]),
                        "team": json.dumps(org_data["team"]),
                    }
                }
            ]
        return []

    mock_neo4j_service.execute_query.side_effect = mock_execute_query

    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

    with patch(
        "src.kene_api.routers.organizations.generate_unique_organization_id"
    ) as mock_uuid:
        mock_uuid.return_value = "test-org-id"

        response = client.post("/api/v1/organizations/", json=org_data)

    # Debug: print response if it fails
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")

    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == "Company Without Size"
    # When empty string is stored in Neo4j, it's returned as empty string
    assert data["company_size"] == ""

    # Clean up
    app.dependency_overrides.clear()
