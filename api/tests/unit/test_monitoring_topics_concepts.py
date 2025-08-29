"""Unit tests for monitoring topics concept endpoints."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.kene_api.main import app
from src.kene_api.models.monitoring_models import (
    ConceptOption,
    ConceptReference,
    ConceptType,
    CustomerKeywordConcept,
)


client = TestClient(app)


class TestMonitoringTopicsConcepts:
    """Test monitoring topics concept-related endpoints."""
    
    @pytest.fixture
    def mock_user_context(self):
        """Mock user context for authentication."""
        with patch("src.kene_api.routers.monitoring_topics.get_current_user_context") as mock:
            user = MagicMock()
            user.email = "test@example.com"
            user.user_id = "user123"
            user.is_super_admin = False
            user.has_account_access.return_value = True
            mock.return_value = user
            yield user
    
    @pytest.fixture
    def mock_firestore(self):
        """Mock Firestore service."""
        with patch("src.kene_api.routers.monitoring_topics.get_firestore_service") as mock:
            firestore = MagicMock()
            mock.return_value = firestore
            yield firestore
    
    @pytest.fixture
    def mock_concept_service(self):
        """Mock concept disambiguation service."""
        with patch("src.kene_api.routers.monitoring_topics.ConceptDisambiguationService") as mock:
            yield mock
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        with patch("src.kene_api.routers.monitoring_topics._cache_service") as mock:
            mock.get = AsyncMock(return_value=None)
            mock.set = AsyncMock()
            yield mock
    
    @pytest.mark.asyncio
    async def test_search_customer_concepts_success(
        self, mock_user_context, mock_concept_service, mock_cache_service
    ):
        """Test successful concept search."""
        # Mock concept service
        mock_service_instance = MagicMock()
        mock_concept_service.return_value = mock_service_instance
        
        mock_concepts = [
            ConceptOption(
                id="concept1",
                label="Apple Inc.",
                type=ConceptType.COMPANY,
                description="Technology company",
                reference=ConceptReference(
                    url="https://apple.com",
                    title="Apple Inc.",
                    description="Technology company",
                    source_type="official_website"
                ),
                confidence_score=0.95
            )
        ]
        mock_service_instance.search_concepts = AsyncMock(return_value=mock_concepts)
        
        # Test
        response = client.get(
            "/api/v1/monitoring-topics/account123/customers/search-concepts",
            params={"term": "Apple"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "Apple Inc."
        assert data[0]["type"] == "company"
        assert data[0]["confidence_score"] == 0.95
    
    @pytest.mark.asyncio
    async def test_search_customer_concepts_cached(
        self, mock_user_context, mock_concept_service, mock_cache_service
    ):
        """Test concept search with cached results."""
        # Mock cached results
        cached_concepts = [
            {
                "id": "cached1",
                "label": "Cached Result",
                "type": "topic",
                "description": "From cache",
                "reference": {
                    "url": "https://example.com",
                    "title": "Cached",
                    "description": "Cached description",
                    "source_type": "wikipedia"
                },
                "confidence_score": 0.8
            }
        ]
        mock_cache_service.get.return_value = cached_concepts
        
        # Test
        response = client.get(
            "/api/v1/monitoring-topics/account123/customers/search-concepts",
            params={"term": "test"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["label"] == "Cached Result"
        
        # Should not have called concept service
        mock_concept_service.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_search_customer_concepts_access_denied(self, mock_user_context):
        """Test access denied for unauthorized user."""
        mock_user_context.has_account_access.return_value = False
        mock_user_context.is_super_admin = False
        
        response = client.get(
            "/api/v1/monitoring-topics/account123/customers/search-concepts",
            params={"term": "test"}
        )
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_add_customer_concept_success(
        self, mock_user_context, mock_firestore
    ):
        """Test successfully adding a customer concept."""
        # Mock Firestore document
        mock_firestore.get_document.return_value = {
            "customer_keywords": ["existing"],
            "customer_concepts": []
        }
        
        # Request body
        request_data = {
            "account_id": "account123",
            "keyword": "Apple",
            "concept_id": "concept123",
            "concept_type": "company",
            "reference": {
                "url": "https://apple.com",
                "title": "Apple Inc.",
                "description": "Technology company",
                "source_type": "official_website"
            }
        }
        
        # Test
        response = client.post(
            "/api/v1/monitoring-topics/account123/customers/add-concept",
            json=request_data
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["keyword"] == "Apple"
        assert data["concept_id"] == "concept123"
        assert data["concept_type"] == "company"
        assert data["added_by"] == "user123"
        
        # Verify Firestore update was called
        mock_firestore.update_document.assert_called_once()
        update_call = mock_firestore.update_document.call_args
        assert update_call.kwargs["collection"] == "monitoring_topics"
        assert update_call.kwargs["document_id"] == "account123"
        assert len(update_call.kwargs["data"]["customer_concepts"]) == 1
        assert "Apple" in update_call.kwargs["data"]["customer_keywords"]
    
    @pytest.mark.asyncio
    async def test_add_customer_concept_new_document(
        self, mock_user_context, mock_firestore
    ):
        """Test adding concept when monitoring topics document doesn't exist."""
        # Mock missing document
        mock_firestore.get_document.return_value = None
        
        # Mock Neo4j query for account info
        with patch("src.kene_api.routers.monitoring_topics.get_neo4j_service") as mock_neo4j:
            neo4j_service = AsyncMock()
            mock_neo4j.return_value = neo4j_service
            
            mock_session = AsyncMock()
            neo4j_service.get_session.return_value.__aenter__.return_value = mock_session
            
            mock_result = AsyncMock()
            mock_record = {"industry": "Technology", "organization_id": "org123"}
            mock_result.single.return_value = mock_record
            mock_session.run.return_value = mock_result
            
            # Mock get_or_create_monitoring_topics
            with patch("src.kene_api.routers.monitoring_topics.get_or_create_monitoring_topics") as mock_create:
                mock_monitoring_topics = MagicMock()
                mock_monitoring_topics.model_dump.return_value = {
                    "customer_keywords": [],
                    "customer_concepts": []
                }
                mock_create.return_value = mock_monitoring_topics
                
                # Request body
                request_data = {
                    "account_id": "account123",
                    "keyword": "Apple",
                    "concept_id": "concept123",
                    "concept_type": "company",
                    "reference": {
                        "url": "https://apple.com",
                        "title": "Apple Inc.",
                        "description": "Technology company",
                        "source_type": "official_website"
                    }
                }
                
                # Test
                response = client.post(
                    "/api/v1/monitoring-topics/account123/customers/add-concept",
                    json=request_data
                )
                
                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["keyword"] == "Apple"
    
    @pytest.mark.asyncio
    async def test_add_customer_concept_invalid_url(self, mock_user_context):
        """Test adding concept with invalid URL."""
        request_data = {
            "account_id": "account123",
            "keyword": "Test",
            "concept_id": "concept123",
            "concept_type": "topic",
            "reference": {
                "url": "not-a-valid-url",
                "title": "Test",
                "description": "Test description",
                "source_type": "other"
            }
        }
        
        response = client.post(
            "/api/v1/monitoring-topics/account123/customers/add-concept",
            json=request_data
        )
        
        assert response.status_code == 422
        assert "validation error" in response.json()["detail"][0]["msg"]
    
    @pytest.mark.asyncio
    async def test_remove_customer_concept_success(
        self, mock_user_context, mock_firestore
    ):
        """Test successfully removing a customer concept."""
        # Mock existing document with concepts
        mock_firestore.get_document.return_value = {
            "customer_keywords": ["Apple", "Google"],
            "customer_concepts": [
                {
                    "concept_id": "concept123",
                    "keyword": "Apple",
                    "concept_type": "company",
                    "reference": {
                        "url": "https://apple.com",
                        "title": "Apple Inc.",
                        "description": "Technology company",
                        "source_type": "official_website"
                    },
                    "added_by": "user123",
                    "added_at": "2024-01-01T00:00:00"
                },
                {
                    "concept_id": "concept456",
                    "keyword": "Google",
                    "concept_type": "company",
                    "reference": {
                        "url": "https://google.com",
                        "title": "Google",
                        "description": "Search company",
                        "source_type": "official_website"
                    },
                    "added_by": "user123",
                    "added_at": "2024-01-01T00:00:00"
                }
            ]
        }
        
        # Test
        response = client.delete(
            "/api/v1/monitoring-topics/account123/customers/concepts/concept123"
        )
        
        # Assertions
        assert response.status_code == 200
        assert "removed successfully" in response.json()["message"]
        
        # Verify Firestore update was called
        mock_firestore.update_document.assert_called_once()
        update_call = mock_firestore.update_document.call_args
        assert len(update_call.kwargs["data"]["customer_concepts"]) == 1
        assert update_call.kwargs["data"]["customer_concepts"][0]["concept_id"] == "concept456"
        assert "Apple" not in update_call.kwargs["data"]["customer_keywords"]
        assert "Google" in update_call.kwargs["data"]["customer_keywords"]
    
    @pytest.mark.asyncio
    async def test_remove_customer_concept_not_found(
        self, mock_user_context, mock_firestore
    ):
        """Test removing a non-existent concept."""
        mock_firestore.get_document.return_value = {
            "customer_keywords": [],
            "customer_concepts": []
        }
        
        response = client.delete(
            "/api/v1/monitoring-topics/account123/customers/concepts/nonexistent"
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_remove_customer_concept_no_document(
        self, mock_user_context, mock_firestore
    ):
        """Test removing concept when document doesn't exist."""
        mock_firestore.get_document.return_value = None
        
        response = client.delete(
            "/api/v1/monitoring-topics/account123/customers/concepts/concept123"
        )
        
        assert response.status_code == 404
        assert "Monitoring topics not found" in response.json()["detail"]