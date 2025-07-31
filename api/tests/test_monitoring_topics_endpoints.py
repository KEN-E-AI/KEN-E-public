"""Tests for monitoring topics API endpoints with comprehensive error scenarios."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

from src.kene_api.auth.models import UserContext
from src.kene_api.main import app


class TestMonitoringTopicsEndpoints:
    """Test monitoring topics API endpoints."""
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user context with access."""
        return UserContext(
            user_id="test_user",
            email="test@example.com",
            accessible_accounts=["acc_test"],
            permissions={},
            organization_permissions={"org_test": "admin"},
            account_permissions={"acc_test": "edit"}
        )
    
    @pytest.fixture
    def mock_user_no_access(self):
        """Create a mock user context without access."""
        return UserContext(
            user_id="test_user_no_access",
            email="notest@example.com",
            accessible_accounts=[],
            permissions={},
            organization_permissions={},
            account_permissions={}
        )
    
    @pytest.fixture
    def mock_user_view_only(self):
        """Create a mock user context with view-only access."""
        return UserContext(
            user_id="test_user_view",
            email="view@example.com",
            accessible_accounts=["acc_test"],
            permissions={},
            organization_permissions={"org_test": "view"},
            account_permissions={"acc_test": "view"}
        )
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    # GET endpoint tests
    def test_get_monitoring_topics_success(self, client, mock_user):
        """Test successful retrieval of monitoring topics."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "organization_id": "org_test",
                    "industry_keywords": ["keyword1", "keyword2"],
                    "company_keywords": ["company1"],
                    "customer_keywords": [],
                    "competitor_entries": [],
                    "created_at": "2025-01-01T00:00:00",
                    "updated_at": "2025-01-01T00:00:00",
                }
                
                response = client.get(
                    "/api/v1/monitoring-topics/acc_test",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["data"]["account_id"] == "acc_test"
    
    def test_get_monitoring_topics_no_document_creates_new(self, client, mock_user):
        """Test that a new document is created when none exists."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                with patch("src.kene_api.routers.monitoring_topics.get_neo4j_service") as mock_neo4j:
                    # Mock Firestore returning no document
                    mock_firestore.return_value.get_document.side_effect = [
                        None,  # First call for monitoring topics
                        {"keywords": ["tech", "software"]}  # Second call for industry keywords
                    ]
                    
                    # Mock Neo4j session and query
                    mock_session = AsyncMock()
                    mock_result = AsyncMock()
                    mock_result.single.return_value = {
                        "industry": "Technology",
                        "organization_id": "org_test"
                    }
                    mock_session.run.return_value = mock_result
                    mock_neo4j.return_value = AsyncMock()
                    mock_neo4j.return_value.get_session.return_value.__aenter__.return_value = mock_session
                    
                    response = client.get(
                        "/api/v1/monitoring-topics/acc_test",
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    assert response.status_code == 200
    
    def test_get_monitoring_topics_access_denied(self, client, mock_user_no_access):
        """Test access denied for user without permissions."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user_no_access):
            response = client.get(
                "/api/v1/monitoring-topics/acc_test",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
    
    def test_get_monitoring_topics_no_auth(self, client):
        """Test request without authentication."""
        response = client.get("/api/v1/monitoring-topics/acc_test")
        assert response.status_code == 401
    
    def test_get_monitoring_topics_account_not_in_neo4j(self, client, mock_user):
        """Test when account doesn't exist in Neo4j."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                with patch("src.kene_api.routers.monitoring_topics.get_neo4j_service") as mock_neo4j:
                    mock_firestore.return_value.get_document.return_value = None
                    
                    # Mock Neo4j returning no record
                    mock_session = AsyncMock()
                    mock_result = AsyncMock()
                    mock_result.single.return_value = None
                    mock_session.run.return_value = mock_result
                    mock_neo4j.return_value = AsyncMock()
                    mock_neo4j.return_value.get_session.return_value.__aenter__.return_value = mock_session
                    
                    response = client.get(
                        "/api/v1/monitoring-topics/acc_test",
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    assert response.status_code == 200
                    assert response.json()["data"] is None
    
    def test_get_monitoring_topics_neo4j_connection_error(self, client, mock_user):
        """Test handling of Neo4j connection error."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                with patch("src.kene_api.routers.monitoring_topics.get_neo4j_service") as mock_neo4j:
                    mock_firestore.return_value.get_document.return_value = None
                    
                    # Mock Neo4j connection error
                    mock_neo4j.side_effect = Exception("Neo4j connection failed")
                    
                    response = client.get(
                        "/api/v1/monitoring-topics/acc_test",
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    assert response.status_code == 500
                    assert "Neo4j connection failed" in response.json()["detail"]
    
    def test_get_monitoring_topics_firestore_error(self, client, mock_user):
        """Test handling of Firestore error."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                # Mock Firestore error
                mock_firestore.return_value.get_document.side_effect = Exception("Firestore quota exceeded")
                
                response = client.get(
                    "/api/v1/monitoring-topics/acc_test",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 500
                assert "Firestore quota exceeded" in response.json()["detail"]
    
    # PUT company keywords tests
    def test_update_company_keywords_success(self, client, mock_user):
        """Test successful update of company keywords."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "company_keywords": ["old_keyword"]
                }
                
                response = client.put(
                    "/api/v1/monitoring-topics/acc_test/company",
                    json={
                        "account_id": "acc_test",
                        "company_keywords": ["new_keyword1", "new_keyword2"]
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                assert response.json()["data"]["company_keywords"] == ["new_keyword1", "new_keyword2"]
    
    def test_update_company_keywords_validation_error(self, client, mock_user):
        """Test validation error for mismatched account ID."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            response = client.put(
                "/api/v1/monitoring-topics/acc_test/company",
                json={
                    "account_id": "acc_different",
                    "company_keywords": ["valid"]
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 400
            assert "Account ID in path does not match" in response.json()["detail"]
    
    def test_update_company_keywords_view_only_access(self, client, mock_user_view_only):
        """Test that view-only users cannot update keywords."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user_view_only):
            response = client.put(
                "/api/v1/monitoring-topics/acc_test/company",
                json={
                    "account_id": "acc_test",
                    "company_keywords": ["keyword"]
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 403
            assert "Write access denied" in response.json()["detail"]
    
    def test_update_company_keywords_empty_list(self, client, mock_user):
        """Test updating with empty keyword list."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "company_keywords": ["old_keyword"]
                }
                
                response = client.put(
                    "/api/v1/monitoring-topics/acc_test/company",
                    json={
                        "account_id": "acc_test",
                        "company_keywords": []
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                assert response.json()["data"]["company_keywords"] == []
    
    def test_update_company_keywords_large_list(self, client, mock_user):
        """Test updating with large keyword list."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {"account_id": "acc_test"}
                
                # Create 100 keywords
                large_keyword_list = [f"keyword_{i}" for i in range(100)]
                
                response = client.put(
                    "/api/v1/monitoring-topics/acc_test/company",
                    json={
                        "account_id": "acc_test",
                        "company_keywords": large_keyword_list
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                assert len(response.json()["data"]["company_keywords"]) == 100
    
    # POST competitor tests
    def test_add_competitor_success(self, client, mock_user):
        """Test successful addition of competitor."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "competitor_entries": []
                }
                
                response = client.post(
                    "/api/v1/monitoring-topics/acc_test/competitors",
                    json={
                        "account_id": "acc_test",
                        "name": "New Competitor",
                        "keywords": ["comp_keyword"]
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                assert "competitor_id" in response.json()["data"]
    
    def test_add_competitor_duplicate(self, client, mock_user):
        """Test adding duplicate competitor."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "competitor_entries": [
                        {
                            "competitor_id": "comp_123",
                            "name": "Existing Competitor",
                            "keywords": ["keyword1"]
                        }
                    ]
                }
                
                response = client.post(
                    "/api/v1/monitoring-topics/acc_test/competitors",
                    json={
                        "account_id": "acc_test",
                        "name": "Existing Competitor",
                        "keywords": ["keyword2"]
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 400
                assert "already exists" in response.json()["detail"]
    
    def test_add_competitor_with_website(self, client, mock_user):
        """Test adding competitor with website."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "competitor_entries": []
                }
                
                response = client.post(
                    "/api/v1/monitoring-topics/acc_test/competitors",
                    json={
                        "account_id": "acc_test",
                        "name": "Competitor with Site",
                        "website": "https://competitor.com",
                        "keywords": ["comp"]
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                data = response.json()["data"]
                assert data["name"] == "Competitor with Site"
                assert data["website"] == "https://competitor.com"
    
    # DELETE competitor tests
    def test_delete_competitor_success(self, client, mock_user):
        """Test successful deletion of competitor."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "competitor_entries": [
                        {
                            "competitor_id": "comp_123",
                            "name": "To Delete",
                            "keywords": ["keyword"]
                        }
                    ]
                }
                
                response = client.delete(
                    "/api/v1/monitoring-topics/acc_test/competitors/comp_123",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
                assert response.json()["message"] == "Competitor removed successfully"
    
    def test_delete_competitor_not_found(self, client, mock_user):
        """Test deleting non-existent competitor."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                mock_firestore.return_value.get_document.return_value = {
                    "account_id": "acc_test",
                    "competitor_entries": []
                }
                
                response = client.delete(
                    "/api/v1/monitoring-topics/acc_test/competitors/comp_nonexistent",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 404
                assert "Competitor not found" in response.json()["detail"]
    
    # Network timeout tests
    def test_network_timeout_handling(self, client, mock_user):
        """Test handling of network timeout."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                import asyncio
                # Simulate timeout
                mock_firestore.return_value.get_document.side_effect = asyncio.TimeoutError("Request timed out")
                
                response = client.get(
                    "/api/v1/monitoring-topics/acc_test",
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 500
    
    # Industry keywords tests
    def test_update_industry_keywords_super_admin(self, client):
        """Test that super admin can update industry keywords."""
        super_admin = UserContext(
            user_id="admin_user",
            email="admin@ken-e.ai",
            accessible_accounts=["acc_test"],
            permissions={},
            organization_permissions={"org_test": "admin"},
            account_permissions={}
        )
        
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=super_admin):
            with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock_firestore:
                response = client.put(
                    "/api/v1/monitoring-topics/industries/technology",
                    json={
                        "industry": "Technology",
                        "keywords": ["tech", "software", "AI"]
                    },
                    headers={"Authorization": "Bearer test_token"}
                )
                
                assert response.status_code == 200
    
    def test_update_industry_keywords_regular_user_denied(self, client, mock_user):
        """Test that regular users cannot update industry keywords."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context", return_value=mock_user):
            response = client.put(
                "/api/v1/monitoring-topics/industries/technology",
                json={
                    "industry": "Technology",
                    "keywords": ["tech", "software"]
                },
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 403
            assert "Only super admins" in response.json()["detail"]