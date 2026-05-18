"""Tests for the insights router."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.database import Neo4jService, get_neo4j_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service for testing."""
    mock_service = MagicMock(spec=Neo4jService)
    mock_service.health_check = AsyncMock(return_value=True)
    mock_service.execute_query = AsyncMock()
    mock_service.execute_write_query = AsyncMock()
    return mock_service


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


class TestInsightsRouter:
    """Test suite for insights router."""

    def test_get_insights_empty_response(self, client, mock_neo4j_service):
        """Test getting insights with no data."""
        # Mock empty responses
        mock_neo4j_service.execute_query.side_effect = [[], []]  # insights, intuitions

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        response = client.get("/api/v1/insights/?account_id=test_account")

        assert response.status_code == 200
        data = response.json()
        assert data["insights"] == []
        assert data["intuitions"] == []
        assert data["total"] == 0

        app.dependency_overrides.clear()

    def test_get_insights_with_data(self, client, mock_neo4j_service):
        """Test getting insights with sample data."""
        # Mock insight data
        insight_record = {
            "activity": {
                "activity_id": "activity_001",
                "activity_description": "Test activity",
            },
            "metric": {"metric_id": "metric_001", "metric_name": "Test Metric"},
            "activity_log": {"activity_log_id": "log_001"},
            "dataset": {"product": "HubSpot,Salesforce"},
            "relationship": {},
        }

        # Mock intuition data
        intuition_record = {
            "activity": {
                "activity_id": "activity_002",
                "activity_description": "Test activity 2",
            },
            "metric": {"metric_id": "metric_002", "metric_name": "Test Metric 2"},
            "relationship": {"direction": "positive"},
        }

        mock_neo4j_service.execute_query.side_effect = [
            [insight_record],  # insights query
            [intuition_record],  # intuitions query
        ]

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        response = client.get("/api/v1/insights/?account_id=test_account")

        assert response.status_code == 200
        data = response.json()
        assert len(data["insights"]) == 1
        assert len(data["intuitions"]) == 1
        assert data["total"] == 2

        # Verify insight structure
        insight = data["insights"][0]
        assert insight["activity_id"] == "activity_001"
        assert insight["metric_id"] == "metric_001"
        assert insight["activity_log_id"] == "log_001"
        assert insight["metric_verbose_name"] == "Test Metric"
        assert "HubSpot" in insight["related_dataset_products"]
        assert "Salesforce" in insight["related_dataset_products"]

        # Verify intuition structure
        intuition = data["intuitions"][0]
        assert intuition["activity_id"] == "activity_002"
        assert intuition["metric_id"] == "metric_002"
        assert intuition["direction"] == "positive"

        app.dependency_overrides.clear()

    def test_get_insights_with_relationship_types(self, client, mock_neo4j_service):
        """Test getting insights with different relationship types."""
        # Mock insight with INFLUENCE_CONFIRMED
        influence_confirmed_record = {
            "activity": {
                "activity_id": "activity_001",
                "activity_description": "Test activity",
            },
            "metric": {"metric_id": "metric_001", "metric_name": "Test Metric"},
            "activity_log": {"activity_log_id": "log_001"},
            "dataset": {"product": "HubSpot,Salesforce"},
            "relationship": {"direction": "positive"},
            "relationship_type": "INFLUENCE_CONFIRMED",
        }

        # Mock insight with NO_INFLUENCE_CONFIRMED
        no_influence_record = {
            "activity": {
                "activity_id": "activity_002",
                "activity_description": "Test activity 2",
            },
            "metric": {"metric_id": "metric_002", "metric_name": "Test Metric 2"},
            "activity_log": {"activity_log_id": "log_002"},
            "dataset": {"product": "Analytics"},
            "relationship": {},
            "relationship_type": "NO_INFLUENCE_CONFIRMED",
        }

        mock_neo4j_service.execute_query.side_effect = [
            [influence_confirmed_record, no_influence_record],  # insights query
            [],  # intuitions query
        ]

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        response = client.get("/api/v1/insights/?account_id=test_account")

        assert response.status_code == 200
        data = response.json()
        assert len(data["insights"]) == 2
        assert data["total"] == 2

        # Verify first insight has INFLUENCE_CONFIRMED
        insight1 = data["insights"][0]
        assert insight1["relationship_type"] == "INFLUENCE_CONFIRMED"
        assert insight1["direction"] == "positive"

        # Verify second insight has NO_INFLUENCE_CONFIRMED
        insight2 = data["insights"][1]
        assert insight2["relationship_type"] == "NO_INFLUENCE_CONFIRMED"
        assert insight2["direction"] is None  # Should be None for no influence

        app.dependency_overrides.clear()

    def test_create_insight(self, client, mock_neo4j_service):
        """Test creating a new insight."""
        mock_neo4j_service.execute_write_query.return_value = {
            "relationships_created": 1,
            "nodes_created": 0,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        create_request = {
            "account_id": "a000001",
            "activity_log_id": "log_001",
            "metric_id": "metric_001",
        }

        response = client.post("/api/v1/insights/", json=create_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "created successfully" in data["message"]

        app.dependency_overrides.clear()

    def test_create_insight_with_evidence(self, client, mock_neo4j_service):
        """Test creating insight with evidence data."""
        mock_neo4j_service.execute_write_query.return_value = {
            "relationships_created": 1,
            "nodes_created": 0,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "properties_set": 0,
        }

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        create_request = {
            "account_id": "a000001",
            "activity_log_id": "log_001",
            "metric_id": "metric_001",
            "evidence": {
                "active_evidence": {
                    "active_confidence": "HIGH",
                    "evidence": ["correlation_analysis"],
                    "data": None,
                },
                "influence_evidence": {
                    "influence_direction_aligned": True,
                    "influence_likely": True,
                    "other_conflicting_insights": [],
                    "other_supporting_insights": [],
                    "overlapping_conflicting_insights": [],
                    "overlapping_supporting_insights": [],
                },
            },
        }

        response = client.post("/api/v1/insights/", json=create_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        app.dependency_overrides.clear()

    def test_update_insight(self, client, mock_neo4j_service):
        """Test updating an existing insight."""
        mock_neo4j_service.execute_write_query.return_value = {
            "relationships_created": 0,
            "nodes_created": 0,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "properties_set": 2,
        }

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        update_request = {
            "account_id": "a000001",
            "activity_log_id": "log_001",
            "metric_id": "metric_001",
        }

        response = client.put("/api/v1/insights/", json=update_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "updated successfully" in data["message"]

        app.dependency_overrides.clear()

    def test_delete_insight(self, client, mock_neo4j_service):
        """Test deleting an insight."""
        mock_neo4j_service.execute_write_query.return_value = {
            "relationships_created": 0,
            "nodes_created": 0,
            "nodes_deleted": 0,
            "relationships_deleted": 1,
            "properties_set": 0,
        }

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        delete_request = {
            "account_id": "a000001",
            "activity_log_id": "log_001",
            "metric_id": "metric_001",
        }

        response = client.request("DELETE", "/api/v1/insights/", json=delete_request)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

        app.dependency_overrides.clear()

    def test_error_handling_missing_ids(self, client, mock_neo4j_service):
        """Test error handling for missing required IDs."""
        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        create_request = {
            "account_id": "a000001",
            "metric_id": "metric_001",
            # Missing activity_log_id
        }

        response = client.post("/api/v1/insights/", json=create_request)

        assert response.status_code == 400
        # This will be a business logic validation error for missing required field

        app.dependency_overrides.clear()

    def test_error_handling_database_unavailable(self, client, mock_neo4j_service):
        """Test error handling when database is unavailable."""
        mock_neo4j_service.health_check = AsyncMock(return_value=False)

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        response = client.get("/api/v1/insights/?account_id=test_account")

        assert response.status_code == 503
        assert "Database service unavailable" in response.json()["detail"]

        app.dependency_overrides.clear()
