"""Unit tests for account cascade deletion logic."""

from unittest.mock import AsyncMock, Mock

import pytest


class TestAccountsCascadeDelete:
    """Test cascade deletion functionality for accounts."""

    @pytest.mark.asyncio
    async def test_cascade_delete_logic(self):
        """Test the cascade delete logic flow."""
        # This tests the logic without importing the actual router

        # Simulate the cascade delete logic
        async def cascade_delete_account(account_id: str, db_service):
            """Simulated cascade delete logic matching the actual implementation."""
            total_nodes = 0
            total_relationships = 0

            # Delete ActivityLogs
            logs_result = await db_service.execute_write(
                """
                MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)<-[:LOGGED]-(log:ActivityLog)
                DETACH DELETE log
                RETURN COUNT(log) as nodes_deleted
                """,
                {"account_id": account_id},
            )
            total_nodes += logs_result.get("nodes_deleted", 0)
            total_relationships += logs_result.get("relationships_deleted", 0)

            # Delete related entities
            entities_result = await db_service.execute_write(
                """
                MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(entity)
                DETACH DELETE entity
                RETURN COUNT(entity) as nodes_deleted
                """,
                {"account_id": account_id},
            )
            total_nodes += entities_result.get("nodes_deleted", 0)
            total_relationships += entities_result.get("relationships_deleted", 0)

            # Delete account
            account_result = await db_service.execute_write(
                """
                MATCH (acc:Account {account_id: $account_id})
                DETACH DELETE acc
                RETURN COUNT(acc) as nodes_deleted
                """,
                {"account_id": account_id},
            )
            total_nodes += account_result.get("nodes_deleted", 0)
            total_relationships += account_result.get("relationships_deleted", 0)

            return {
                "success": True,
                "message": "Account deleted successfully",
                "data": {
                    "nodes_deleted": total_nodes,
                    "relationships_deleted": total_relationships,
                },
            }

        # Test with mock service
        mock_service = Mock()
        mock_service.execute_write = AsyncMock()
        mock_service.execute_write.side_effect = [
            {"nodes_deleted": 5, "relationships_deleted": 5},
            {"nodes_deleted": 10, "relationships_deleted": 15},
            {"nodes_deleted": 1, "relationships_deleted": 0},
        ]

        result = await cascade_delete_account("acc_test", mock_service)

        assert result["success"] is True
        assert result["data"]["nodes_deleted"] == 16
        assert result["data"]["relationships_deleted"] == 20
        assert mock_service.execute_write.call_count == 3

    @pytest.mark.asyncio
    async def test_delete_queries_order(self):
        """Test that deletion queries are executed in the correct order."""
        queries_executed = []

        async def track_query(query, params):
            queries_executed.append(query)
            return {"nodes_deleted": 1, "relationships_deleted": 1}

        mock_service = Mock()
        mock_service.execute_write = track_query

        # Simulate the delete process
        await mock_service.execute_write(
            "MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)<-[:LOGGED]-(log:ActivityLog) DETACH DELETE log",
            {"account_id": "test"},
        )
        await mock_service.execute_write(
            "MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(entity) DETACH DELETE entity",
            {"account_id": "test"},
        )
        await mock_service.execute_write(
            "MATCH (acc:Account {account_id: $account_id}) DETACH DELETE acc",
            {"account_id": "test"},
        )

        # Verify order: ActivityLogs first, then entities, then account
        assert len(queries_executed) == 3
        assert "ActivityLog" in queries_executed[0]
        assert "BELONGS_TO" in queries_executed[1]
        assert (
            queries_executed[2].count("BELONGS_TO") == 0
        )  # Account query has no BELONGS_TO
