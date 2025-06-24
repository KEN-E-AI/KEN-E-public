"""Tests for metrics router."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from src.kene_api.main import app


class TestMetricsRouter:
    """Test class for metrics router endpoints."""

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_get_metrics_success(self, mock_neo4j_service):
        """Test successful retrieval of metrics."""
        # Mock Neo4j service async methods
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[
                {
                    "metric": {
                        "id": "metric_001",
                        "d3_format": ".2f",
                        "verbose_name": "Total Revenue",
                        "expression": "SUM(revenue)",
                        "metric_name": "total_revenue",
                        "account_components": ["financial", "sales"],
                        "description": "Total revenue metric",
                    },
                    "dataset": {
                        "dataset_id": 1,
                        "dataset_name": "revenue_dataset",
                        "products": ["salesforce", "hubspot"],
                    },
                }
            ]
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/metrics/?account_id=test_account")

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "total" in data
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["metric_name"] == "total_revenue"
        assert data["metrics"][0]["related_dataset_name"] == "revenue_dataset"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_get_metrics_neo4j_unavailable(self, mock_neo4j_service):
        """Test metrics retrieval when Neo4j is unavailable."""
        # Mock health check failure
        mock_neo4j_service.health_check = AsyncMock(return_value=False)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/api/v1/metrics/?account_id=test_account")

        assert response.status_code == 503
        assert "Database service unavailable" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.superset.superset_client")
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_metric_success(self, mock_neo4j_service, mock_superset_client):
        """Test successful metric creation."""
        # Mock successful account and dataset checks
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            side_effect=[
                [{"account": {"account_id": "test_account"}}],  # Account exists
                [{"dataset": {"dataset_id": 1}}],  # Dataset exists
            ]
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            side_effect=[
                [{"metric": {"id": "test_metric"}}],  # Metric created
                [],  # Relationship created
            ]
        )

        # Mock Superset client
        mock_superset_client.create_metric = AsyncMock(return_value={"id": 123})

        request_data = {
            "account_id": "test_account",
            "id": "test_metric",
            "d3_format": ".2f",
            "verbose_name": "Test Metric",
            "expression": "COUNT(*)",
            "metric_name": "test_metric",
            "account_components": ["marketing"],
            "related_dataset_id": 1,
            "description": "Test metric description",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/metrics/", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Metric created successfully"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_metric_account_not_found(self, mock_neo4j_service):
        """Test metric creation when account doesn't exist."""
        # Mock account not found
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(return_value=[])

        request_data = {
            "account_id": "nonexistent_account",
            "id": "test_metric",
            "d3_format": ".2f",
            "verbose_name": "Test Metric",
            "expression": "COUNT(*)",
            "metric_name": "test_metric",
            "account_components": ["marketing"],
            "description": "Test metric description",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/metrics/", json=request_data)

        assert response.status_code == 404
        assert "Account nonexistent_account not found" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.superset.superset_client")
    @patch("src.kene_api.database.neo4j_service")
    async def test_update_metric_success(self, mock_neo4j_service, mock_superset_client):
        """Test successful metric update."""
        # Mock metric exists and update successful
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            side_effect=[
                [{"metric": {"id": "test_metric"}, "dataset": {"dataset_id": 1}, "superset_metric_id": 123}],  # Metric exists with superset info
            ]
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            side_effect=[
                [{"metric": {"id": "test_metric"}}],  # Update successful
            ]
        )

        # Mock Superset client
        mock_superset_client.update_metric = AsyncMock(return_value={"success": True})

        request_data = {
            "account_id": "test_account",
            "id": "test_metric",
            "d3_format": ".3f",
            "description": "Updated description",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put("/api/v1/metrics/", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Metric updated successfully (synced with Superset)"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_update_metric_not_found(self, mock_neo4j_service):
        """Test metric update when metric doesn't exist."""
        # Mock metric not found
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(return_value=[])

        request_data = {
            "account_id": "test_account",
            "id": "nonexistent_metric",
            "d3_format": ".3f",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put("/api/v1/metrics/", json=request_data)

        assert response.status_code == 404
        assert "Metric nonexistent_metric not found" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.superset.superset_client")
    @patch("src.kene_api.database.neo4j_service")
    async def test_delete_metric_success(self, mock_neo4j_service, mock_superset_client):
        """Test successful metric deletion."""
        # Mock metric exists and deletion successful
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            side_effect=[
                [{"metric": {"id": "test_metric"}, "dataset": {"dataset_id": 1}, "superset_metric_id": 123}],  # Metric exists with superset info
            ]
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            side_effect=[
                [],  # Deletion successful
            ]
        )

        # Mock Superset client
        mock_superset_client.delete_metric = AsyncMock(return_value=True)

        request_data = {
            "account_id": "test_account",
            "id": "test_metric",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.request("DELETE", "/api/v1/metrics/", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Metric deleted successfully (removed from Superset)"
