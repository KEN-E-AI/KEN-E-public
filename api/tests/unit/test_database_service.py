"""Unit tests for Neo4j database service methods."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest
from src.kene_api.database import Neo4jService


class TestNeo4jService:
    """Test Neo4j database service functionality."""

    @pytest.fixture
    def db_service(self):
        """Create a database service instance for testing."""
        with patch("src.kene_api.database.AsyncGraphDatabase"):
            return Neo4jService()

    @pytest.mark.asyncio
    async def test_connect_passes_configured_max_transaction_retry_time(self):
        """The driver is created with max_transaction_retry_time from settings.

        Without an explicit value the Neo4j driver defaults to 30s, so a
        transaction against an unreachable Neo4j (e.g. CI, which has no Neo4j)
        retries with escalating backoffs for ~30s and stalls the request. Making
        it configurable lets the e2e stack bound it to a couple of seconds.
        """
        with (
            patch("src.kene_api.database.AsyncGraphDatabase") as mock_gdb,
            patch("src.kene_api.database.settings") as mock_settings,
        ):
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "pw"
            mock_settings.neo4j_max_transaction_retry_time = 2.0
            mock_gdb.driver.return_value.verify_connectivity = AsyncMock()

            await Neo4jService().connect()

            assert mock_gdb.driver.call_args.kwargs["max_transaction_retry_time"] == 2.0

    @pytest.mark.asyncio
    async def test_execute_write_query_returns_data(self, db_service):
        """Test execute_write_query returns data for CREATE queries with RETURN."""
        # Mock session and transaction
        mock_session = AsyncMock()
        mock_tx = AsyncMock()
        mock_result = AsyncMock()

        # Mock the data that would be returned
        expected_data = [{"account_id": "acc_123", "name": "Test Account"}]
        mock_result.data = AsyncMock(return_value=expected_data)
        mock_tx.run = AsyncMock(return_value=mock_result)
        mock_session.execute_write = AsyncMock(return_value=expected_data)

        # Mock the session context manager
        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        db_service.get_session = mock_get_session

        # Test CREATE query with RETURN
        create_query = "CREATE (acc:Account {account_id: $account_id}) RETURN acc"
        result = await db_service.execute_write_query(
            create_query, {"account_id": "acc_123"}
        )

        # Verify the result
        assert result == expected_data
        mock_session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_write_operation_returns_summary(self, db_service):
        """Test execute_write_operation returns summary for DELETE queries."""
        # Mock session and transaction
        mock_session = AsyncMock()
        mock_tx = AsyncMock()
        mock_result = AsyncMock()
        mock_summary = Mock()

        # Mock counters
        mock_counters = Mock()
        mock_counters.nodes_created = 0
        mock_counters.nodes_deleted = 1
        mock_counters.relationships_created = 0
        mock_counters.relationships_deleted = 2
        mock_counters.properties_set = 0
        mock_summary.counters = mock_counters

        mock_result.consume = AsyncMock(return_value=mock_summary)
        mock_tx.run = AsyncMock(return_value=mock_result)

        expected_summary = {
            "nodes_created": 0,
            "nodes_deleted": 1,
            "relationships_created": 0,
            "relationships_deleted": 2,
            "properties_set": 0,
        }
        mock_session.execute_write = AsyncMock(return_value=expected_summary)

        # Mock the session context manager
        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        db_service.get_session = mock_get_session

        # Test DELETE query without RETURN
        delete_query = "MATCH (acc:Account {account_id: $account_id}) DETACH DELETE acc"
        result = await db_service.execute_write_operation(
            delete_query, {"account_id": "acc_123"}
        )

        # Verify the result
        assert result == expected_summary
        mock_session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_handles_parameters(self, db_service):
        """Test execute_query properly handles parameters."""
        # Mock session and transaction
        mock_session = AsyncMock()
        mock_tx = AsyncMock()
        mock_result = AsyncMock()

        expected_data = [{"count": 5}]
        mock_result.data = AsyncMock(return_value=expected_data)
        mock_tx.run = AsyncMock(return_value=mock_result)
        mock_session.execute_read = AsyncMock(return_value=expected_data)

        # Mock the session context manager
        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        db_service.get_session = mock_get_session

        # Test query with parameters
        query = (
            "MATCH (acc:Account) WHERE acc.status = $status RETURN count(acc) as count"
        )
        params = {"status": "Active"}
        result = await db_service.execute_query(query, params)

        # Verify the result and parameters were passed correctly
        assert result == expected_data
        mock_session.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_defaults_empty_parameters(self, db_service):
        """Test execute_query uses empty dict when parameters is None."""
        mock_session = AsyncMock()
        mock_session.execute_read = AsyncMock(return_value=[])

        # Mock the session context manager
        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        db_service.get_session = mock_get_session

        # Test query without parameters
        query = "MATCH (acc:Account) RETURN count(acc)"
        await db_service.execute_query(query, None)

        # Verify empty parameters were used
        mock_session.execute_read.assert_called_once()
