"""Tests for industry templates API endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from src.kene_api.main import app
from src.kene_api.models.kene_models import (
    IndustryTemplate,
    IndustryTemplateSettings,
    IndustryTemplateDefaults,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service."""
    mock = Mock()
    mock.health_check.return_value = True
    return mock


@pytest.fixture
def sample_template_data():
    """Sample template data for testing."""
    return {
        "id": "retail_trade_b2c",
        "industry": "Retail Trade [B2C]",
        "name": "Retail Trade [B2C] Template",
        "description": "Selling goods directly to consumers",
        "default_objectives": ["Increase sales", "Improve customer satisfaction"],
        "default_channels": ["Email", "Social Media"],
        "default_kpis": ["Revenue", "Customer Count"],
        "marketing_channels": ["Email", "Social Media", "SEO"],
        "product_integrations": ["Shopify", "WooCommerce"],
        "recommended_settings": {
            "timezone": "America/New_York",
            "data_region": "United States",
            "industry": "Retail Trade [B2C]"
        },
        "default_settings": {
            "data_retention": 90
        },
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user context."""
    mock_user = Mock()
    mock_user.user_id = "test_user_123"
    mock_user.email = "test@example.com"
    mock_user.is_super_admin = False
    mock_user.selected_organization_id = "org_123"
    return mock_user


@pytest.fixture
def mock_super_admin():
    """Mock super admin user context."""
    mock_user = Mock()
    mock_user.user_id = "admin_user_123"
    mock_user.email = "admin@example.com"
    mock_user.is_super_admin = True
    mock_user.selected_organization_id = "org_123"
    return mock_user


class TestListIndustryTemplates:
    """Tests for listing industry templates."""
    
    @patch("src.kene_api.routers.industry_templates._fetch_all_templates")
    def test_list_all_templates_success(self, mock_fetch, client, sample_template_data):
        """Test successful listing of all templates."""
        # Setup mock to return parsed template
        template = IndustryTemplate(**sample_template_data)
        mock_fetch.return_value = [template]
        
        # Make request
        response = client.get("/api/v1/industry-templates")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert "total" in data
        assert len(data["templates"]) == 1
        assert data["templates"][0]["industry"] == "Retail Trade [B2C]"
        assert data["total"] == 1
    
    @patch("src.kene_api.routers.industry_templates._fetch_all_templates")
    def test_list_active_only_filters_inactive(self, mock_fetch, client, sample_template_data):
        """Test that active_only parameter filters inactive templates."""
        # Setup mock with active and inactive templates
        inactive_template_data = sample_template_data.copy()
        inactive_template_data["id"] = "inactive_template"
        inactive_template_data["industry"] = "Inactive Industry"
        inactive_template_data["is_active"] = False
        
        active_template = IndustryTemplate(**sample_template_data)
        inactive_template = IndustryTemplate(**inactive_template_data)
        mock_fetch.return_value = [active_template, inactive_template]
        
        # Make request with active_only=true
        response = client.get("/api/v1/industry-templates?active_only=true")
        
        # Assert only active template returned
        assert response.status_code == 200
        data = response.json()
        assert len(data["templates"]) == 1
        assert data["templates"][0]["is_active"] is True
    
    @patch("src.kene_api.routers.industry_templates._fetch_all_templates")
    def test_list_templates_firestore_unavailable(self, mock_fetch, client):
        """Test handling when Firestore is unavailable."""
        # Setup mock to raise HTTPException
        from fastapi import HTTPException
        mock_fetch.side_effect = HTTPException(status_code=503, detail="Firestore service unavailable")
        
        # Make request
        response = client.get("/api/v1/industry-templates")
        
        # Assert service unavailable
        assert response.status_code == 503
        assert "Firestore service unavailable" in response.json()["detail"]


class TestGetIndustryTemplate:
    """Tests for getting template by industry."""
    
    @patch("src.kene_api.routers.industry_templates._fetch_template_by_industry")
    def test_get_template_by_industry_success(self, mock_fetch, client, sample_template_data):
        """Test successful retrieval of template by industry name."""
        # Setup mock to return template
        template = IndustryTemplate(**sample_template_data)
        mock_fetch.return_value = template
        
        # Make request
        response = client.get("/api/v1/industry-templates/industry/Retail%20Trade%20%5BB2C%5D")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["industry"] == "Retail Trade [B2C]"
        assert data["description"] == "Selling goods directly to consumers"
    
    @patch("src.kene_api.routers.industry_templates._fetch_template_by_industry")
    def test_get_template_by_industry_not_found(self, mock_fetch, client):
        """Test 404 when template not found."""
        # Setup mock to return None
        mock_fetch.return_value = None
        
        # Make request
        response = client.get("/api/v1/industry-templates/industry/NonExistent%20Industry")
        
        # Assert
        assert response.status_code == 404
        assert "Template not found for industry" in response.json()["detail"]
    
    def test_get_template_invalid_industry_name(self, client):
        """Test validation of industry parameter."""
        # Empty industry name should fail
        response = client.get("/api/v1/industry-templates/industry/")
        assert response.status_code == 404  # FastAPI returns 404 for missing path param
        
        # Very long industry name should fail validation
        long_name = "x" * 201
        response = client.get(f"/api/v1/industry-templates/industry/{long_name}")
        assert response.status_code == 422  # Validation error


class TestGetTemplateById:
    """Tests for getting template by ID."""
    
    @patch("src.kene_api.routers.industry_templates._fetch_all_templates")
    def test_get_template_by_id_success(self, mock_fetch, client, sample_template_data):
        """Test successful retrieval of template by ID."""
        # Setup mock to return template
        template = IndustryTemplate(**sample_template_data)
        mock_fetch.return_value = [template]
        
        # Make request
        response = client.get("/api/v1/industry-templates/retail_trade_b2c")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "retail_trade_b2c"
        assert data["industry"] == "Retail Trade [B2C]"
    
    @patch("src.kene_api.routers.industry_templates.get_firestore_service")
    @patch("src.kene_api.routers.industry_templates._fetch_all_templates")
    def test_get_template_by_id_not_found(self, mock_fetch, mock_get_firestore, client, mock_firestore_service):
        """Test 404 when template ID not found."""
        # Setup mocks
        mock_fetch.return_value = []  # Empty list
        mock_firestore_service.get_document.return_value = None
        mock_get_firestore.return_value = mock_firestore_service
        
        # Make request
        response = client.get("/api/v1/industry-templates/nonexistent_id")
        
        # Assert
        assert response.status_code == 404
        assert "Template not found" in response.json()["detail"]


class TestUpdateIndustryTemplate:
    """Tests for updating industry templates."""
    
    @patch("src.kene_api.auth.get_current_user_context")
    @patch("src.kene_api.routers.industry_templates.get_firestore_service")
    def test_update_template_as_super_admin(self, mock_get_firestore, mock_get_user, 
                                           client, sample_template_data, mock_super_admin, 
                                           mock_firestore_service):
        """Test successful template update by super admin."""
        # Setup mocks
        mock_get_user.return_value = mock_super_admin
        mock_firestore_service.set_document.return_value = True
        mock_get_firestore.return_value = mock_firestore_service
        
        # Prepare update data
        update_data = sample_template_data.copy()
        update_data["description"] = "Updated description"
        
        # Make request
        response = client.put("/api/v1/industry-templates/retail_trade_b2c", json=update_data)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        mock_firestore_service.set_document.assert_called_once()
    
    @patch("src.kene_api.auth.get_current_user_context")
    @patch("src.kene_api.routers.industry_templates.get_firestore_service")
    def test_update_template_as_regular_user_forbidden(self, mock_get_firestore, mock_get_user,
                                                      client, sample_template_data, mock_auth_user):
        """Test that regular users cannot update templates."""
        # Setup mocks
        mock_get_user.return_value = mock_auth_user
        
        # Make request
        response = client.put("/api/v1/industry-templates/retail_trade_b2c", json=sample_template_data)
        
        # Assert forbidden
        assert response.status_code == 403
        assert "Only super admins can update" in response.json()["detail"]
    
    @patch("src.kene_api.auth.get_current_user_context")
    @patch("src.kene_api.routers.industry_templates.get_firestore_service")
    def test_update_template_firestore_failure(self, mock_get_firestore, mock_get_user,
                                              client, sample_template_data, mock_super_admin,
                                              mock_firestore_service):
        """Test handling of Firestore update failure."""
        # Setup mocks
        mock_get_user.return_value = mock_super_admin
        mock_firestore_service.set_document.return_value = False
        mock_get_firestore.return_value = mock_firestore_service
        
        # Make request
        response = client.put("/api/v1/industry-templates/retail_trade_b2c", json=sample_template_data)
        
        # Assert error
        assert response.status_code == 500
        assert "Failed to update template" in response.json()["detail"]


class TestCacheBehavior:
    """Tests for caching behavior."""
    
    @patch("src.kene_api.routers.industry_templates.get_firestore_service")
    def test_cache_hit_avoids_firestore_call(self, mock_get_firestore, client, sample_template_data, mock_firestore_service):
        """Test that cached data avoids additional Firestore calls."""
        # Setup mock
        mock_firestore_service.list_documents.return_value = [sample_template_data]
        mock_get_firestore.return_value = mock_firestore_service
        
        # Import and clear cache
        from src.kene_api.routers.industry_templates import _template_cache
        _template_cache.invalidate()
        
        # First request - should call Firestore
        response1 = client.get("/api/v1/industry-templates")
        assert response1.status_code == 200
        assert mock_firestore_service.list_documents.call_count == 1
        
        # Second request - should use cache (if caching is enabled)
        response2 = client.get("/api/v1/industry-templates")
        assert response2.status_code == 200
        
        # In development, cache is disabled so it will call again
        # In production, it would use cache
        from src.kene_api.routers.industry_templates import IS_DEVELOPMENT
        if not IS_DEVELOPMENT:
            assert mock_firestore_service.list_documents.call_count == 1
        else:
            assert mock_firestore_service.list_documents.call_count == 2
    
    def test_no_caching_in_development(self, client):
        """Test that caching is disabled in development mode."""
        from src.kene_api.routers.industry_templates import _template_cache, IS_DEVELOPMENT
        
        if IS_DEVELOPMENT:
            # Cache should not store in development
            _template_cache.set("test_key", "test_value")
            assert _template_cache.get("test_key") is None


class TestInputValidation:
    """Tests for input validation."""
    
    def test_industry_parameter_validation(self, client):
        """Test validation of industry parameter constraints."""
        # Test minimum length validation
        response = client.get("/api/v1/industry-templates/industry/")
        assert response.status_code == 404  # Empty path
        
        # Test maximum length validation (201 characters)
        long_industry = "A" * 201
        response = client.get(f"/api/v1/industry-templates/industry/{long_industry}")
        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "at most 200" in error["msg"]
    
    def test_template_id_parameter_validation(self, client):
        """Test validation of template_id parameter constraints."""
        # Test maximum length validation (201 characters)
        long_id = "a" * 201
        response = client.get(f"/api/v1/industry-templates/{long_id}")
        assert response.status_code == 422
        error = response.json()["detail"][0]
        assert "at most 200" in error["msg"]