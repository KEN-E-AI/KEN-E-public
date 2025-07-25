"""Tests for activity operations with Neo4j integration."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from src.kene_api.main import app


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_get_activities_with_name(mock_neo4j_service):
    """Test getting activities returns activity_name field."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[
            {
                "activity": {
                    "activity_id": "test-id",
                    "activity_name": "Test Activity Name",
                    "activity_description": "Test description",
                    "expected_impact": "Test impact",
                    "internal": True,
                    "known_activity": False,
                },
                "logs": [],
            }
        ]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/activities/?account_id=test123")

    assert response.status_code == 200
    data = response.json()
    assert len(data["activities"]) == 1
    activity = data["activities"][0]
    assert activity["activity_name"] == "Test Activity Name"
    assert activity["activity_description"] == "Test description"


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_create_activity_success(mock_neo4j_service):
    """Test successful activity creation with Neo4j."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[{"a": {"account_id": "test123"}}]
    )  # Account exists
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={
            "nodes_created": 1,
            "relationships_created": 1,
            "properties_set": 6,
        }
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/activities/",
            json={
                "account_id": "test123",
                "activity_name": "Test Activity",
                "activity_description": "Test activity description",
                "expected_impact": "Test impact",
                "internal": True,
                "known_activity": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Activity created successfully" in data["message"]
    assert "id" in data["data"]


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_create_activity_account_not_found(mock_neo4j_service):
    """Test activity creation when account doesn't exist."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[]
    )  # Account doesn't exist

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/activities/",
            json={
                "account_id": "nonexistent",
                "activity_description": "Test activity description",
            },
        )

    assert response.status_code == 404
    data = response.json()
    assert "Account with account_id 'nonexistent' not found" in data["detail"]


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_update_activity_success(mock_neo4j_service):
    """Test successful activity update."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[{"activity": {"id": "test-id"}}]
    )  # Activity exists
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={"properties_set": 2}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(
            "/api/v1/activities/",
            json={
                "account_id": "test123",
                "activity_id": "test-id",
                "activity_name": "Updated Activity Name",
                "activity_description": "Updated description",
                "expected_impact": "Updated impact",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Activity updated successfully" in data["message"]


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_delete_activity_success(mock_neo4j_service):
    """Test successful activity deletion."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[{"activity": {"id": "test-activity"}}]
    )  # Activity exists
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={"nodes_deleted": 1, "relationships_deleted": 1}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.request(
            "DELETE",
            "/api/v1/activities/",
            json={"account_id": "test123", "activity_id": "test-activity"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Activity and associated logs deleted successfully" in data["message"]


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_update_activity_name_only(mock_neo4j_service):
    """Test updating only the activity name field."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[{"activity": {"id": "test-id"}}]
    )  # Activity exists
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={"properties_set": 1}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.put(
            "/api/v1/activities/",
            json={
                "account_id": "test123",
                "activity_id": "test-id",
                "activity_name": "New Activity Name",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Activity updated successfully" in data["message"]


@pytest.mark.asyncio
@patch("src.kene_api.database.neo4j_service")
async def test_create_test_account_success(mock_neo4j_service):
    """Test creating a test account."""
    # Mock Neo4j service async methods
    mock_neo4j_service.health_check = AsyncMock(return_value=True)  # Neo4j is healthy
    mock_neo4j_service.execute_query = AsyncMock(
        return_value=[]
    )  # Account doesn't exist
    mock_neo4j_service.execute_write_query = AsyncMock(
        return_value={"nodes_created": 1, "properties_set": 3}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/activities/test/create-account?account_id=test123"
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "created successfully" in data["message"]
