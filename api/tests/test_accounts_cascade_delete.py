import pytest
from unittest.mock import Mock, patch
from src.kene_api.routers.accounts import delete_account
from src.kene_api.services.neo4j_service import Neo4jService
from src.kene_api.models.kene_models import SuccessResponse


@pytest.fixture
def mock_neo4j_service():
    """Fixture for mocked Neo4j service."""
    service = Mock(spec=Neo4jService)
    return service


class TestAccountsCascadeDelete:
    """Test cascade deletion functionality for accounts."""

    @pytest.mark.asyncio
    async def test_delete_account_with_activity_logs(self, mock_neo4j_service):
        """Test deleting account cascades to ActivityLog nodes."""
        # Arrange
        account_id = "acc_test123"
        mock_neo4j_service.execute_write.side_effect = [
            {"nodes_deleted": 5, "relationships_deleted": 5},  # ActivityLogs
            {"nodes_deleted": 10, "relationships_deleted": 15},  # Related entities
            {"nodes_deleted": 1, "relationships_deleted": 0},  # Account
        ]

        # Act
        result = await delete_account(account_id, mock_neo4j_service)

        # Assert
        assert result.success is True
        assert result.message == "Account deleted successfully"
        assert result.data == {"nodes_deleted": 16, "relationships_deleted": 20}
        assert mock_neo4j_service.execute_write.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_account_empty_collections(self, mock_neo4j_service):
        """Test deletion handles empty collections gracefully."""
        # Arrange
        account_id = "acc_empty"
        mock_neo4j_service.execute_write.side_effect = [
            {"nodes_deleted": 0, "relationships_deleted": 0},  # No ActivityLogs
            {"nodes_deleted": 0, "relationships_deleted": 0},  # No related entities
            {"nodes_deleted": 1, "relationships_deleted": 0},  # Account exists
        ]

        # Act
        result = await delete_account(account_id, mock_neo4j_service)

        # Assert
        assert result.success is True
        assert result.data["nodes_deleted"] == 1
        assert result.data["relationships_deleted"] == 0

    @pytest.mark.asyncio
    async def test_delete_account_not_found(self, mock_neo4j_service):
        """Test deleting non-existent account."""
        # Arrange
        account_id = "acc_nonexistent"
        mock_neo4j_service.execute_write.side_effect = [
            {"nodes_deleted": 0, "relationships_deleted": 0},  # No ActivityLogs
            {"nodes_deleted": 0, "relationships_deleted": 0},  # No related entities
            {"nodes_deleted": 0, "relationships_deleted": 0},  # Account doesn't exist
        ]

        # Act
        result = await delete_account(account_id, mock_neo4j_service)

        # Assert
        assert result.success is True
        assert result.message == "Account deleted successfully"
        assert result.data["nodes_deleted"] == 0

    @pytest.mark.asyncio
    async def test_delete_account_with_complex_relationships(self, mock_neo4j_service):
        """Test deleting account with multiple entity types."""
        # Arrange
        account_id = "acc_complex"
        mock_neo4j_service.execute_write.side_effect = [
            {"nodes_deleted": 25, "relationships_deleted": 30},  # Many ActivityLogs
            {"nodes_deleted": 50, "relationships_deleted": 75},  # Many related entities
            {"nodes_deleted": 1, "relationships_deleted": 5},  # Account with relationships
        ]

        # Act
        result = await delete_account(account_id, mock_neo4j_service)

        # Assert
        assert result.success is True
        assert result.data["nodes_deleted"] == 76
        assert result.data["relationships_deleted"] == 110

    @pytest.mark.asyncio
    async def test_delete_account_query_structure(self, mock_neo4j_service):
        """Test that correct queries are executed in correct order."""
        # Arrange
        account_id = "acc_verify_queries"
        mock_neo4j_service.execute_write.return_value = {
            "nodes_deleted": 1,
            "relationships_deleted": 1,
        }

        # Act
        await delete_account(account_id, mock_neo4j_service)

        # Assert
        calls = mock_neo4j_service.execute_write.call_args_list
        assert len(calls) == 3

        # Verify first query deletes ActivityLogs
        first_query = calls[0][0][0]
        assert "ActivityLog" in first_query
        assert "LOGGED" in first_query

        # Verify second query deletes entities with BELONGS_TO
        second_query = calls[1][0][0]
        assert "BELONGS_TO" in second_query

        # Verify third query deletes the account
        third_query = calls[2][0][0]
        assert "Account {account_id: $account_id}" in third_query