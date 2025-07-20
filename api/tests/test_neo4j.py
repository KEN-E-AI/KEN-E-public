from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from src.kene_api.database import Neo4jService


@pytest.mark.asyncio
async def test_neo4j_service_initialization():
    """Test Neo4j service can be initialized."""
    service = Neo4jService()
    assert service.driver is None


@pytest.mark.asyncio
async def test_neo4j_health_check_no_driver():
    """Test health check returns False when no driver is connected."""
    service = Neo4jService()
    is_healthy = await service.health_check()
    assert is_healthy is False


@pytest.mark.asyncio
@patch("src.kene_api.database.AsyncGraphDatabase.driver")
async def test_neo4j_connect_success(mock_driver_factory):
    """Test successful Neo4j connection."""
    # Create mock driver and session
    mock_driver = AsyncMock()
    mock_driver.verify_connectivity = AsyncMock()
    mock_driver_factory.return_value = mock_driver

    service = Neo4jService()
    await service.connect()

    assert service.driver is not None
    mock_driver.verify_connectivity.assert_called_once()


@pytest.mark.asyncio
@patch("src.kene_api.database.Neo4jService.get_session")
async def test_neo4j_execute_query_success(mock_get_session):
    """Test successful query execution."""
    # Mock session with proper async context manager
    mock_session = AsyncMock()
    mock_session.execute_read = AsyncMock(return_value=[{"test": "data"}])

    # Create async context manager mock
    @asynccontextmanager
    async def mock_session_context():
        yield mock_session

    mock_get_session.return_value = mock_session_context()

    # Create service and set up driver
    service = Neo4jService()
    mock_driver = AsyncMock()
    service.driver = mock_driver

    # Execute query
    result = await service.execute_query("MATCH (n) RETURN n LIMIT 1")

    # Verify results
    assert result == [{"test": "data"}]
    mock_session.execute_read.assert_called_once()


@pytest.mark.asyncio
@patch("src.kene_api.database.Neo4jService.get_session")
async def test_neo4j_execute_write_query_success(mock_get_session):
    """Test successful write query execution."""
    # Mock session with proper async context manager
    mock_session = AsyncMock()

    # Configure the mock return value for write operations
    expected_summary = {
        "nodes_created": 1,
        "nodes_deleted": 0,
        "relationships_created": 1,
        "relationships_deleted": 0,
        "properties_set": 2,
    }

    mock_session.execute_write = AsyncMock(return_value=expected_summary)

    # Create async context manager mock
    @asynccontextmanager
    async def mock_session_context():
        yield mock_session

    mock_get_session.return_value = mock_session_context()

    # Create service and set up driver
    service = Neo4jService()
    mock_driver = AsyncMock()
    service.driver = mock_driver

    # Execute write query
    result = await service.execute_write_query(
        "CREATE (n:Test {name: $name}) RETURN n", {"name": "test"}
    )

    # Verify results
    assert result == expected_summary
    mock_session.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_neo4j_close():
    """Test closing Neo4j connection."""
    service = Neo4jService()
    mock_driver = AsyncMock()
    service.driver = mock_driver

    await service.close()

    mock_driver.close.assert_called_once()
