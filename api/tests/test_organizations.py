"""Tests for organizations endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from src.kene_api.main import app
from src.kene_api.database import get_neo4j_service

# Create test client
client = TestClient(app)


@pytest.fixture
def mock_neo4j_service():
    """Create a mock Neo4j service."""
    mock_service = MagicMock()
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock(return_value=[])
    mock_service.execute_write_query = AsyncMock(return_value={
        "nodes_created": 1,
        "relationships_created": 0,
        "nodes_deleted": 0,
        "relationships_deleted": 0,
        "properties_set": 0
    })
    return mock_service


def test_get_organizations(mock_neo4j_service):
    """Test getting all organizations."""
    # Mock the database response
    mock_neo4j_service.execute_query.return_value = [
        {
            "org": {
                "organization_id": "test-org",
                "organization_name": "Test Organization",
                "plan": "Professional",
                "website": "https://test.com",
                "company_size": "medium",
                "agency": False,
                "child_organizations": [],
                "subscription": {
                    "plan_name": "Professional Plan",
                    "plan_description": "Test plan",
                    "price": 99.0,
                    "currency": "USD",
                    "billing_cycle": "monthly",
                    "next_billing_date": "2024-02-15",
                    "features": ["Feature 1"],
                    "usage": {"reports_generated": 10, "reports_limit": 100}
                },
                "billing": {
                    "payment_method": {
                        "last_four": "4242",
                        "brand": "Visa",
                        "expires": "12/25"
                    },
                    "address": "123 Test St",
                    "tax_id": "123456789"
                },
                "team": {
                    "members_used": 5,
                    "members_limit": 10,
                    "pending_invitations": 0
                }
            }
        }
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.get("/api/v1/organizations/")
    
    assert response.status_code == 200
    data = response.json()
    assert "organizations" in data
    assert "total" in data
    assert data["total"] == 1
    assert len(data["organizations"]) == 1
    assert data["organizations"][0]["organization_id"] == "test-org"
    
    # Clean up
    app.dependency_overrides.clear()


def test_get_organization_by_id(mock_neo4j_service):
    """Test getting a specific organization."""
    # Mock the database response
    mock_neo4j_service.execute_query.return_value = [
        {
            "org": {
                "organization_id": "test-org",
                "organization_name": "Test Organization",
                "plan": "Professional",
                "website": "https://test.com",
                "company_size": "medium",
                "agency": False,
                "child_organizations": [],
                "subscription": {
                    "plan_name": "Professional Plan",
                    "plan_description": "Test plan",
                    "price": 99.0,
                    "currency": "USD",
                    "billing_cycle": "monthly",
                    "next_billing_date": "2024-02-15",
                    "features": ["Feature 1"],
                    "usage": {"reports_generated": 10, "reports_limit": 100}
                },
                "billing": {
                    "payment_method": {
                        "last_four": "4242",
                        "brand": "Visa",
                        "expires": "12/25"
                    },
                    "address": "123 Test St",
                    "tax_id": "123456789"
                },
                "team": {
                    "members_used": 5,
                    "members_limit": 10,
                    "pending_invitations": 0
                }
            }
        }
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.get("/api/v1/organizations/test-org")
    
    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == "test-org"
    assert data["organization_name"] == "Test Organization"
    
    # Clean up
    app.dependency_overrides.clear()


def test_get_organization_not_found(mock_neo4j_service):
    """Test getting a non-existent organization."""
    # Mock empty response
    mock_neo4j_service.execute_query.return_value = []
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.get("/api/v1/organizations/non-existent")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    
    # Clean up
    app.dependency_overrides.clear()


def test_create_organization(mock_neo4j_service):
    """Test creating a new organization."""
    # Mock the check for existing org (returns False)
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": False}],  # Organization doesn't exist
        [{  # Return created organization
            "org": {
                "organization_id": "new-company",
                "organization_name": "New Company",
                "plan": "Professional",
                "website": "https://newcompany.com",
                "company_size": "medium",
                "agency": False,
                "child_organizations": [],
                "subscription": {
                    "plan_name": "Professional Plan",
                    "plan_description": "Advanced analytics",
                    "price": 99.0,
                    "currency": "USD",
                    "billing_cycle": "monthly",
                    "next_billing_date": "2024-03-01",
                    "features": ["Feature 1"],
                    "usage": {"reports_generated": 0, "reports_limit": 1000}
                },
                "billing": {
                    "payment_method": {
                        "last_four": "1234",
                        "brand": "Visa",
                        "expires": "12/26"
                    },
                    "address": "456 New St",
                    "tax_id": "987654321"
                },
                "team": {
                    "members_used": 1,
                    "members_limit": 10,
                    "pending_invitations": 0
                }
            }
        }]
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    new_org_data = {
        "organization_name": "New Company",
        "plan": "Professional",
        "website": "https://newcompany.com",
        "company_size": "medium",
        "agency": False,
        "subscription": {
            "plan_name": "Professional Plan",
            "plan_description": "Advanced analytics",
            "price": 99.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-03-01",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 0, "reports_limit": 1000}
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "Visa",
                "expires": "12/26"
            },
            "address": "456 New St",
            "tax_id": "987654321"
        },
        "team": {
            "members_used": 1,
            "members_limit": 10,
            "pending_invitations": 0
        }
    }
    
    response = client.post("/api/v1/organizations/", json=new_org_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == "new-company"
    assert data["organization_name"] == "New Company"
    
    # Clean up
    app.dependency_overrides.clear()


def test_delete_organization(mock_neo4j_service):
    """Test deleting an organization."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{"account_count": 0}]  # No accounts
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.delete("/api/v1/organizations/test-org")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "deleted successfully" in data["message"]
    
    # Clean up
    app.dependency_overrides.clear()


def test_delete_organization_with_accounts(mock_neo4j_service):
    """Test deleting an organization that has accounts."""
    # Mock the checks
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{"account_count": 2}]  # Has 2 accounts
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
        "website": "https://example.com"
    }
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.post("/api/v1/organizations/", json=org_data)
    
    assert response.status_code == 422  # Validation error
    
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
            "usage": {"reports_generated": 10, "reports_limit": 100}
        }
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
            "usage": {"reports_generated": 10, "reports_limit": 100}
        },
        "billing": {},
        "team": {}
    }
    
    # Mock successful creation with generated ID
    mock_neo4j_service.execute_query.return_value = [{
        "org": {
            "organization_id": "a" * 100,  # Truncated ID
            "organization_name": "A" * 1000,
            "company_size": "50-100",
            "plan": "free",
            "website": "https://example.com",
            "agency": False
        }
    }]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.post("/api/v1/organizations/", json=org_data)
    
    # Should succeed but with truncated organization_id
    assert response.status_code == 200
    data = response.json()
    assert len(data["organization_id"]) <= 100  # ID should be truncated
    
    # Clean up
    app.dependency_overrides.clear()


def test_update_organization_special_characters(mock_neo4j_service):
    """Test updating organization with special characters in fields."""
    update_data = {
        "organization_name": "Test & Co. <script>alert('xss')</script>",
        "website": "https://test-site.com?param=value&other=123"
    }
    
    # Mock the checks and update
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{
            "org": {
                "organization_id": "test-org",
                "organization_name": "Test & Co. <script>alert('xss')</script>",
                "website": "https://test-site.com?param=value&other=123"
            }
        }]
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.put("/api/v1/organizations/test-org", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    # Special characters should be preserved (escaping handled by frontend/DB)
    assert data["organization_name"] == "Test & Co. <script>alert('xss')</script>"
    
    # Clean up
    app.dependency_overrides.clear()


def test_get_organizations_pagination_edge_cases(mock_neo4j_service):
    """Test getting organizations with edge case pagination parameters."""
    # Mock response
    mock_neo4j_service.execute_query.return_value = [{
        "orgs": [],
        "total": 0
    }]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    # Test with negative skip
    response = client.get("/api/v1/organizations/?skip=-10&limit=10")
    assert response.status_code == 422  # Should validate
    
    # Test with zero limit
    response = client.get("/api/v1/organizations/?skip=0&limit=0")
    assert response.status_code == 422  # Should validate
    
    # Test with extremely large values
    response = client.get("/api/v1/organizations/?skip=999999&limit=999999")
    assert response.status_code == 200  # Should work but return empty
    
    # Clean up
    app.dependency_overrides.clear()


# PARENT_OF relationship tests
def test_create_agency_organization_with_children(mock_neo4j_service):
    """Test creating an agency organization with child organizations."""
    org_data = {
        "organization_name": "Parent Agency",
        "company_size": "100-500",
        "plan": "agency",
        "website": "https://agency.com",
        "agency": True,
        "child_organizations": ["child-org-1", "child-org-2"],
        "subscription": {
            "plan_name": "Agency Plan",
            "plan_description": "For agencies",
            "price": 500.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Multi-org management"],
            "usage": {"reports_generated": 0, "reports_limit": 1000}
        },
        "billing": {},
        "team": {}
    }
    
    # Mock successful creation
    mock_neo4j_service.execute_query.return_value = [{
        "org": {
            "organization_id": "parent-agency",
            "organization_name": "Parent Agency",
            "agency": True,
            "child_organizations": ["child-org-1", "child-org-2"]
        }
    }]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.post("/api/v1/organizations/", json=org_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["agency"] is True
    assert data["child_organizations"] == ["child-org-1", "child-org-2"]
    
    # Verify relationship queries were made
    calls = mock_neo4j_service.execute_query.call_args_list
    # Should have created org and then 2 PARENT_OF relationships
    assert len(calls) >= 3
    
    # Clean up
    app.dependency_overrides.clear()


def test_update_organization_add_child_relationships(mock_neo4j_service):
    """Test updating organization to add child organizations."""
    update_data = {
        "agency": True,
        "child_organizations": ["new-child-1", "new-child-2"]
    }
    
    # Mock the checks and update
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{  # Current state - no children
            "org": {
                "organization_id": "test-org",
                "agency": False,
                "child_organizations": []
            }
        }],
        [{  # After update
            "org": {
                "organization_id": "test-org",
                "agency": True,
                "child_organizations": ["new-child-1", "new-child-2"]
            }
        }]
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.put("/api/v1/organizations/test-org", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["agency"] is True
    assert data["child_organizations"] == ["new-child-1", "new-child-2"]
    
    # Clean up
    app.dependency_overrides.clear()


def test_update_organization_remove_child_relationships(mock_neo4j_service):
    """Test updating organization to remove child organizations."""
    update_data = {
        "agency": False,  # No longer an agency
        "child_organizations": []
    }
    
    # Mock the checks and update
    mock_neo4j_service.execute_query.side_effect = [
        [{"exists": True}],  # Organization exists
        [{  # Current state - has children
            "org": {
                "organization_id": "test-org",
                "agency": True,
                "child_organizations": ["child-1", "child-2"]
            }
        }],
        [{  # After update - no children
            "org": {
                "organization_id": "test-org",
                "agency": False,
                "child_organizations": []
            }
        }]
    ]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.put("/api/v1/organizations/test-org", json=update_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["agency"] is False
    assert data["child_organizations"] == []
    
    # Clean up
    app.dependency_overrides.clear()


def test_create_organization_circular_parent_child_relationship(mock_neo4j_service):
    """Test creating organization where it's its own child (circular reference)."""
    org_data = {
        "organization_id": "self-parent",  # Explicitly set ID
        "organization_name": "Self Parent Org",
        "company_size": "50-100",
        "plan": "agency",
        "website": "https://example.com",
        "agency": True,
        "child_organizations": ["self-parent"],  # References itself
        "subscription": {
            "plan_name": "Agency Plan",
            "plan_description": "Test",
            "price": 99.0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-02-15",
            "features": ["Feature 1"],
            "usage": {"reports_generated": 0, "reports_limit": 100}
        },
        "billing": {},
        "team": {}
    }
    
    # Mock successful creation but relationship creation might fail
    mock_neo4j_service.execute_query.return_value = [{
        "org": {
            "organization_id": "self-parent",
            "organization_name": "Self Parent Org",
            "agency": True,
            "child_organizations": ["self-parent"]
        }
    }]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.post("/api/v1/organizations/", json=org_data)
    
    # Should still succeed - circular reference prevention is DB concern
    assert response.status_code == 200
    
    # Clean up
    app.dependency_overrides.clear()


def test_get_organization_with_parent_child_relationships(mock_neo4j_service):
    """Test getting organization includes parent/child relationship data."""
    # Mock organization with both parent and children
    mock_neo4j_service.execute_query.return_value = [{
        "org": {
            "organization_id": "middle-org",
            "organization_name": "Middle Organization",
            "agency": True,
            "child_organizations": ["child-1", "child-2"],
            "parent_organization": "parent-agency"  # If we track parent
        }
    }]
    
    # Override dependency
    app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
    
    response = client.get("/api/v1/organizations/middle-org")
    
    assert response.status_code == 200
    data = response.json()
    assert data["child_organizations"] == ["child-1", "child-2"]
    # Parent relationship might be tracked differently
    
    # Clean up
    app.dependency_overrides.clear()