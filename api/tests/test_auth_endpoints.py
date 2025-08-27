"""Integration tests for authenticated endpoints."""

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.kene_api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_firebase_token():
    """Mock Firebase ID token verification."""
    decoded_token = {
        "uid": "test-user-123",
        "email": "test@example.com",
        "email_verified": True,
    }
    
    with mock.patch("src.kene_api.auth.user_context.verify_id_token", return_value=decoded_token):
        yield decoded_token


@pytest.fixture
def mock_user_permissions():
    """Mock user permissions in Firestore."""
    user_data = {
        "uid": "test-user-123",
        "email": "test@example.com",
        "permissions": {
            "accounts": {
                "acc_123": "admin",
                "acc_456": "viewer",
            },
            "organizations": {
                "org_123": "admin",
                "org_456": "view",
            },
        },
    }
    
    mock_doc = mock.Mock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = user_data
    
    return mock_doc


class TestAuthenticationMiddleware:
    """Test authentication middleware behavior."""
    
    def test_unauthenticated_request_returns_401(self, client):
        """Test that requests without auth token return 401."""
        # Test various protected endpoints
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
        with mock.patch("src.kene_api.auth.user_context.verify_id_token", side_effect=Exception("Invalid token")):
            response = client.get(
                "/api/v1/organizations/",
                headers={"Authorization": "Bearer invalid-token"}
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "Invalid authentication token"


class TestOrganizationEndpoints:
    """Test organization endpoints with authentication."""
    
    def test_get_organizations_authenticated(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting organizations with valid authentication."""
        # Mock Firestore
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            # Mock Neo4j
            with mock.patch("src.kene_api.database.get_neo4j_service") as mock_neo4j:
                mock_db = mock.Mock()
                mock_db.health_check.return_value = True
                mock_db.execute_query.return_value = [
                    {"org": {"organization_id": "org_123", "organization_name": "Test Org 1"}},
                    {"org": {"organization_id": "org_456", "organization_name": "Test Org 2"}},
                ]
                mock_neo4j.return_value = mock_db
                
                response = client.get(
                    "/api/v1/organizations/",
                    headers={"Authorization": "Bearer valid-token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                assert len(data["organizations"]) == 2
                
                # Verify query was filtered by user's accessible organizations
                called_query = mock_db.execute_query.call_args[0][0]
                assert "WHERE org.organization_id IN $org_ids" in called_query
                called_params = mock_db.execute_query.call_args[0][1]
                assert set(called_params["org_ids"]) == {"org_123", "org_456"}
    
    def test_get_organization_by_id_with_access(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting specific organization when user has access."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            with mock.patch("src.kene_api.database.get_neo4j_service") as mock_neo4j:
                mock_db = mock.Mock()
                mock_db.health_check.return_value = True
                mock_db.execute_query.return_value = [
                    {"org": {"organization_id": "org_123", "organization_name": "Test Org"}}
                ]
                mock_neo4j.return_value = mock_db
                
                response = client.get(
                    "/api/v1/organizations/org_123",
                    headers={"Authorization": "Bearer valid-token"}
                )
                
                assert response.status_code == 200
                assert response.json()["organization_id"] == "org_123"
    
    def test_get_organization_by_id_without_access(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting organization when user lacks access."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            response = client.get(
                "/api/v1/organizations/org_999",
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == 403
            assert "Access denied to organization org_999" in response.json()["detail"]


class TestAccountEndpoints:
    """Test account endpoints with authentication."""
    
    def test_get_accounts_authenticated(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting accounts with valid authentication."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            with mock.patch("src.kene_api.database.get_neo4j_service") as mock_neo4j:
                mock_db = mock.Mock()
                mock_db.health_check.return_value = True
                mock_db.execute_query.return_value = [
                    {"acc": {"account_id": "acc_123", "account_name": "Account 1"}},
                    {"acc": {"account_id": "acc_456", "account_name": "Account 2"}},
                ]
                mock_neo4j.return_value = mock_db
                
                response = client.get(
                    "/api/v1/accounts/",
                    headers={"Authorization": "Bearer valid-token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                
                # Verify query was filtered by user's accessible accounts
                called_query = mock_db.execute_query.call_args[0][0]
                assert "WHERE acc.account_id IN $account_ids" in called_query
    
    def test_get_accounts_filtered_by_organization(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting accounts filtered by organization."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            with mock.patch("src.kene_api.database.get_neo4j_service") as mock_neo4j:
                mock_db = mock.Mock()
                mock_db.health_check.return_value = True
                mock_db.execute_query.return_value = []
                mock_neo4j.return_value = mock_db
                
                # Should succeed - user has access to org_123
                response = client.get(
                    "/api/v1/accounts/?organization_id=org_123",
                    headers={"Authorization": "Bearer valid-token"}
                )
                assert response.status_code == 200
                
                # Should fail - user doesn't have access to org_999
                response = client.get(
                    "/api/v1/accounts/?organization_id=org_999",
                    headers={"Authorization": "Bearer valid-token"}
                )
                assert response.status_code == 403
                assert "Access denied to organization org_999" in response.json()["detail"]


class TestNotificationEndpoints:
    """Test notification endpoints with authentication."""
    
    def test_get_notification_preferences(self, client, mock_firebase_token, mock_user_permissions):
        """Test getting notification preferences."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            
            # Mock user document
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            
            # Mock preferences document
            mock_prefs_doc = mock.Mock()
            mock_prefs_doc.exists = True
            mock_prefs_doc.to_dict.return_value = {
                "categories": ["KPI Performance", "New Features"],
                "channels": ["ui", "email"],
            }
            
            with mock.patch("src.kene_api.services.notification_service_v2.NotificationService.get_user_preferences") as mock_get_prefs:
                mock_get_prefs.return_value = {
                    "categories": ["KPI Performance", "New Features"],
                    "channels": ["ui", "email"],
                }
                
                mock_firestore.return_value = mock_service
                
                response = client.get(
                    "/api/v1/notifications/preferences",
                    headers={"Authorization": "Bearer valid-token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "categories" in data
                assert "channels" in data
    
    def test_create_notification_with_permission(self, client, mock_firebase_token, mock_user_permissions):
        """Test creating notification when user has write permission."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            with mock.patch("src.kene_api.services.notification_service_v2.NotificationService.create_notification") as mock_create:
                mock_create.return_value = "notif_123"
                
                notification_data = {
                    "account_id": "acc_123",  # User has admin access
                    "category": "KPI Performance",
                    "description": "Test notification",
                }
                
                response = client.post(
                    "/api/v1/notifications/",
                    json=notification_data,
                    headers={"Authorization": "Bearer valid-token"}
                )
                
                assert response.status_code == 200
                assert response.json()["notification_id"] == "notif_123"
    
    def test_create_notification_without_permission(self, client, mock_firebase_token, mock_user_permissions):
        """Test creating notification when user lacks write permission."""
        with mock.patch("src.kene_api.firestore.get_firestore_service") as mock_firestore:
            mock_service = mock.Mock()
            mock_client = mock.Mock()
            mock_service.get_client.return_value = mock_client
            mock_client.collection.return_value.document.return_value.get.return_value = mock_user_permissions
            mock_firestore.return_value = mock_service
            
            notification_data = {
                "account_id": "acc_999",  # User doesn't have access
                "category": "KPI Performance",
                "description": "Test notification",
            }
            
            response = client.post(
                "/api/v1/notifications/",
                json=notification_data,
                headers={"Authorization": "Bearer valid-token"}
            )
            
            assert response.status_code == 403
            error_detail = response.json()["detail"]
            # Stronger assertion: check exact error message format
            assert error_detail == "Access denied to account acc_999", \
                f"Expected specific error message, got: {error_detail}"