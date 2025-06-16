"""Tests for the intuitions router."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from src.kene_api.main import app


class TestIntuitionsRouter:
    """Test class for intuitions router endpoints."""

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_success(self, mock_neo4j_service):
        """Test successful intuition creation."""
        # Mock Neo4j service async methods
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[]  # No existing relationship
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 1,
                "nodes_created": 0,
                "properties_set": 1,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                    "direction": "positive",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Intuition created successfully"

        # Verify Neo4j query was called with correct parameters
        mock_neo4j_service.execute_write_query.assert_called_once()
        call_args = mock_neo4j_service.execute_write_query.call_args
        assert "activity_id" in call_args[0][1]
        assert "metric_id" in call_args[0][1]
        assert "direction" in call_args[0][1]
        assert call_args[0][1]["activity_id"] == "activity_001"
        assert call_args[0][1]["metric_id"] == "metric_001"
        assert call_args[0][1]["direction"] == "positive"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_missing_activity_id(self, mock_neo4j_service):
        """Test intuition creation with missing activity_id."""
        mock_neo4j_service.health_check = AsyncMock(return_value=True)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "metric_id": "metric_001",
                    "direction": "positive",
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert "Both activity_id and metric_id are required" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_missing_metric_id(self, mock_neo4j_service):
        """Test intuition creation with missing metric_id."""
        mock_neo4j_service.health_check = AsyncMock(return_value=True)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "direction": "positive",
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert "Both activity_id and metric_id are required" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_not_found(self, mock_neo4j_service):
        """Test intuition creation when activity or metric not found."""
        # Mock Neo4j service to return no relationships created
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[]  # No existing relationship
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 0,
                "nodes_created": 0,
                "properties_set": 0,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "nonexistent_activity",
                    "metric_id": "nonexistent_metric",
                    "direction": "positive",
                },
            )

        assert response.status_code == 404
        data = response.json()
        assert "Activity or Metric not found" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_update_intuition_success(self, mock_neo4j_service):
        """Test successful intuition update."""
        # Mock Neo4j service async methods
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 0,
                "nodes_created": 0,
                "properties_set": 1,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                    "direction": "negative",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Intuition updated successfully"

        # Verify Neo4j query was called with correct parameters
        mock_neo4j_service.execute_write_query.assert_called_once()
        call_args = mock_neo4j_service.execute_write_query.call_args
        assert call_args[0][1]["direction"] == "negative"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_update_intuition_not_found(self, mock_neo4j_service):
        """Test intuition update when relationship not found."""
        # Mock Neo4j service to return no properties set
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 0,
                "nodes_created": 0,
                "properties_set": 0,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "nonexistent_activity",
                    "metric_id": "nonexistent_metric",
                    "direction": "positive",
                },
            )

        assert response.status_code == 404
        data = response.json()
        assert "Intuition relationship not found" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_update_intuition_missing_ids(self, mock_neo4j_service):
        """Test intuition update with missing required IDs."""
        mock_neo4j_service.health_check = AsyncMock(return_value=True)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.put(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "direction": "positive",
                    # Missing metric_id
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert "Both activity_id and metric_id are required" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_delete_intuition_success(self, mock_neo4j_service):
        """Test successful intuition deletion."""
        # Mock Neo4j service async methods
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 0,
                "nodes_created": 0,
                "relationships_deleted": 1,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.request(
                "DELETE",
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Intuition deleted successfully"

        # Verify Neo4j query was called with correct parameters
        mock_neo4j_service.execute_write_query.assert_called_once()
        call_args = mock_neo4j_service.execute_write_query.call_args
        assert call_args[0][1]["activity_id"] == "activity_001"
        assert call_args[0][1]["metric_id"] == "metric_001"

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_delete_intuition_not_found(self, mock_neo4j_service):
        """Test intuition deletion when relationship not found."""
        # Mock Neo4j service to return no relationships deleted
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 0,
                "nodes_created": 0,
                "relationships_deleted": 0,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.request(
                "DELETE",
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "nonexistent_activity",
                    "metric_id": "nonexistent_metric",
                },
            )

        assert response.status_code == 404
        data = response.json()
        assert "Intuition relationship not found" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_delete_intuition_missing_ids(self, mock_neo4j_service):
        """Test intuition deletion with missing required IDs."""
        mock_neo4j_service.health_check = AsyncMock(return_value=True)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.request(
                "DELETE",
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "metric_id": "metric_001",
                    # Missing activity_id
                },
            )

        assert response.status_code == 400
        data = response.json()
        assert "Both activity_id and metric_id are required" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_database_error(self, mock_neo4j_service):
        """Test intuition creation with database error."""
        # Mock Neo4j service to raise an exception
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                    "direction": "positive",
                },
            )

        assert response.status_code == 500
        data = response.json()
        assert "Database error" in data["detail"]

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_without_direction(self, mock_neo4j_service):
        """Test intuition creation without direction (should default to None)."""
        # Mock Neo4j service async methods
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[]  # No existing relationship
        )
        mock_neo4j_service.execute_write_query = AsyncMock(
            return_value={
                "relationships_created": 1,
                "nodes_created": 0,
                "properties_set": 0,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                    # No direction provided
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Intuition created successfully"

        # Verify Neo4j query was called with direction as None
        mock_neo4j_service.execute_write_query.assert_called_once()
        call_args = mock_neo4j_service.execute_write_query.call_args
        assert call_args[0][1]["direction"] is None

    @pytest.mark.asyncio
    @patch("src.kene_api.database.neo4j_service")
    async def test_create_intuition_duplicate_relationship(self, mock_neo4j_service):
        """Test intuition creation when relationship already exists."""
        # Mock Neo4j service to return existing relationship on check
        mock_neo4j_service.health_check = AsyncMock(return_value=True)
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[{"r": {"direction": "positive"}}]  # Relationship exists
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/intuitions/",
                json={
                    "account_id": "test123",
                    "activity_id": "activity_001",
                    "metric_id": "metric_001",
                    "direction": "positive",
                },
            )

        assert response.status_code == 409
        data = response.json()
        assert "Intuition relationship already exists" in data["detail"]
        assert "activity_001" in data["detail"]
        assert "metric_001" in data["detail"]

        # Verify execute_write_query was not called since relationship already exists
        mock_neo4j_service.execute_write_query.assert_not_called()
