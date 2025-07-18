"""Tests for the Funnel Reports router."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service for testing."""
    mock_service = MagicMock()

    # Make health_check async
    async def mock_health_check():
        return True

    mock_service.health_check = mock_health_check
    mock_service.execute_query.return_value = []
    mock_service.execute_write_query.return_value = {
        "relationships_created": 1,
        "nodes_created": 0,
        "nodes_deleted": 0,
        "relationships_deleted": 0,
        "properties_set": 0,
    }
    return mock_service


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


class TestFunnelReportsRouter:
    """Test class for funnel reports router endpoints."""

    @patch("src.kene_api.routers.funnel_reports.search_main")
    def test_analysis_search(self, mock_search_main, client, mock_neo4j_service):
        """Test the analysis endpoint (moved from insights search)."""
        # Mock the search_main function to return test data
        mock_search_main.return_value = {"activity_001": {"test": "data"}}

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        search_request = {
            "account_id": "test_account",
            "metric_id": "metric_001",
            "evaluation_date_start": "2024-01-01",
            "evaluation_date_end": "2024-01-31",
            "comparison_date_start": "2023-12-01",
            "comparison_date_end": "2023-12-31",
            "direction": "positive",
        }

        response = client.post("/api/v1/funnel-reports/analysis", json=search_request)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # Length of the mock result
        assert "insights" in data

        # Verify search_main was called with correct parameters (including activity_id=None)
        mock_search_main.assert_called_once()
        call_args = mock_search_main.call_args
        assert call_args.kwargs["account_id"] == "test_account"
        assert call_args.kwargs["activity_id"] is None  # This is the key change
        assert call_args.kwargs["input_metric_id"] == "metric_001"
        assert call_args.kwargs["input_direction"] == "positive"

        app.dependency_overrides.clear()

    @patch("src.kene_api.routers.funnel_reports.search_main")
    def test_analysis_search_invalid_date_format(
        self, mock_search_main, client, mock_neo4j_service
    ):
        """Test analysis endpoint with invalid date format."""
        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        search_request = {
            "account_id": "test_account",
            "metric_id": "metric_001",
            "evaluation_date_start": "invalid-date",
            "evaluation_date_end": "2024-01-31",
            "comparison_date_start": "2023-12-01",
            "comparison_date_end": "2023-12-31",
            "direction": "positive",
        }

        response = client.post("/api/v1/funnel-reports/analysis", json=search_request)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid date format" in data["detail"]

        # Verify search_main was not called due to date validation error
        mock_search_main.assert_not_called()

        app.dependency_overrides.clear()

    @patch("src.kene_api.routers.funnel_reports.search_main")
    def test_analysis_search_database_unavailable(
        self, mock_search_main, client, mock_neo4j_service
    ):
        """Test analysis endpoint when database is unavailable."""

        # Override the health_check to return False
        async def mock_health_check_unavailable():
            return False

        mock_neo4j_service.health_check = mock_health_check_unavailable

        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service

        search_request = {
            "account_id": "test_account",
            "metric_id": "metric_001",
            "evaluation_date_start": "2024-01-01",
            "evaluation_date_end": "2024-01-31",
            "comparison_date_start": "2023-12-01",
            "comparison_date_end": "2023-12-31",
            "direction": "positive",
        }

        response = client.post("/api/v1/funnel-reports/analysis", json=search_request)

        assert response.status_code == 503
        data = response.json()
        assert "Database service unavailable" in data["detail"]

        # Verify search_main was not called due to database unavailability
        mock_search_main.assert_not_called()

        app.dependency_overrides.clear()
