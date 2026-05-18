"""Integration tests for organization deletion constraints."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.database import get_neo4j_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


class TestOrganizationDeletionConstraints:
    """Test organization deletion with account constraints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_neo4j_service(self):
        """Create mock Neo4j service."""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(return_value=True)
        mock_service.execute_query = AsyncMock()
        mock_service.execute_write_query = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_db_dependency(self, mock_neo4j_service):
        """Override database dependency."""
        app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j_service
        yield mock_neo4j_service
        app.dependency_overrides.clear()

    def test_delete_organization_with_accounts_should_fail(
        self, client, mock_db_dependency
    ):
        """Test that deleting an organization with accounts returns 400 error."""
        organization_id = "org_test123"

        # Mock organization exists
        mock_db_dependency.execute_query.side_effect = [
            # First call: check if organization exists
            [{"exists": True}],
            # Second call: check account count
            [{"account_count": 3}],
        ]

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 400
        assert (
            "Cannot delete organization with 3 associated accounts"
            in response.json()["detail"]
        )
        assert "Delete accounts first" in response.json()["detail"]

        # Verify the correct queries were called
        assert mock_db_dependency.execute_query.call_count == 2

        # Check organization exists query
        first_call = mock_db_dependency.execute_query.call_args_list[0]
        assert (
            "MATCH (org:Organization {organization_id: $organization_id})"
            in first_call[0][0]
        )
        assert first_call[0][1] == {"organization_id": organization_id}

        # Check account count query
        second_call = mock_db_dependency.execute_query.call_args_list[1]
        assert (
            "MATCH (org:Organization {organization_id: $organization_id})<-[:BELONGS_TO]-(acc:Account)"
            in second_call[0][0]
        )
        assert "count(acc) as account_count" in second_call[0][0]
        assert second_call[0][1] == {"organization_id": organization_id}

        # Verify delete was NOT called
        mock_db_dependency.execute_write_query.assert_not_called()

    def test_delete_organization_without_accounts_should_succeed(
        self, client, mock_db_dependency
    ):
        """Test that deleting an organization without accounts succeeds."""
        organization_id = "org_test123"

        # Mock organization exists and has no accounts
        mock_db_dependency.execute_query.side_effect = [
            # First call: check if organization exists
            [{"exists": True}],
            # Second call: check account count
            [{"account_count": 0}],
        ]

        # Mock successful deletion
        mock_db_dependency.execute_write_query.return_value = {
            "nodes_deleted": 1,
            "relationships_deleted": 0,
        }

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 200
        assert (
            response.json()["message"]
            == f"Organization {organization_id} deleted successfully"
        )
        assert response.json()["data"]["organization_id"] == organization_id
        assert response.json()["data"]["nodes_deleted"] == 1

        # Verify delete was called
        mock_db_dependency.execute_write_query.assert_called_once()
        delete_call = mock_db_dependency.execute_write_query.call_args
        assert "DETACH DELETE org" in delete_call[0][0]
        assert delete_call[0][1] == {"organization_id": organization_id}

    def test_delete_nonexistent_organization_should_fail(
        self, client, mock_db_dependency
    ):
        """Test that deleting a non-existent organization returns 404."""
        organization_id = "org_nonexistent"

        # Mock organization does not exist
        mock_db_dependency.execute_query.return_value = [{"exists": False}]

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Organization not found"

        # Verify only existence check was called
        assert mock_db_dependency.execute_query.call_count == 1
        mock_db_dependency.execute_write_query.assert_not_called()

    def test_delete_organization_with_one_account_shows_correct_count(
        self, client, mock_db_dependency
    ):
        """Test error message shows correct account count."""
        organization_id = "org_test123"

        # Mock organization exists with 1 account
        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 1}],
        ]

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 400
        assert (
            "Cannot delete organization with 1 associated accounts"
            in response.json()["detail"]
        )

    def test_delete_organization_with_many_accounts_shows_correct_count(
        self, client, mock_db_dependency
    ):
        """Test error message shows correct account count for multiple accounts."""
        organization_id = "org_test123"

        # Mock organization exists with 15 accounts
        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 15}],
        ]

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 400
        assert (
            "Cannot delete organization with 15 associated accounts"
            in response.json()["detail"]
        )

    def test_database_error_during_account_check_returns_503(
        self, client, mock_db_dependency
    ):
        """Test that database errors during account check are handled properly."""
        organization_id = "org_test123"

        # Mock organization exists
        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            Exception("Database connection failed"),
        ]

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        # Neo4j connection errors are handled as 503 Service Unavailable
        assert response.status_code == 503
        assert "Database service unavailable" in response.json()["detail"]

    def test_database_error_during_deletion_returns_500(
        self, client, mock_db_dependency
    ):
        """Test that database errors during deletion are handled properly."""
        organization_id = "org_test123"

        # Mock organization exists with no accounts
        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 0}],
        ]

        # Mock deletion failure
        mock_db_dependency.execute_write_query.side_effect = Exception(
            "Deletion failed"
        )

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 500
        assert "Error deleting organization" in response.json()["detail"]

    def test_neo4j_health_check_failure_returns_503(self, client, mock_db_dependency):
        """Test that Neo4j health check failure returns 503."""
        organization_id = "org_test123"

        # Mock health check failure
        mock_db_dependency.health_check.return_value = False

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 503
        assert (
            response.json()["detail"]
            == "Database service unavailable. Please try again later."
        )

    def test_account_count_query_format(self, client, mock_db_dependency):
        """Test that the account count query uses the correct Neo4j pattern."""
        organization_id = "org_test123"

        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 2}],
        ]

        client.delete(f"/api/v1/organizations/{organization_id}")

        # Verify the account count query format
        account_count_call = mock_db_dependency.execute_query.call_args_list[1]
        query = account_count_call[0][0]

        # Check for correct Cypher query pattern
        assert "MATCH (org:Organization {organization_id: $organization_id})" in query
        assert "<-[:BELONGS_TO]-(acc:Account)" in query
        assert "RETURN count(acc) as account_count" in query

    def test_deletion_query_uses_detach_delete(self, client, mock_db_dependency):
        """Test that deletion query uses DETACH DELETE to remove relationships."""
        organization_id = "org_test123"

        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 0}],
        ]

        mock_db_dependency.execute_write_query.return_value = {
            "nodes_deleted": 1,
            "relationships_deleted": 2,
        }

        client.delete(f"/api/v1/organizations/{organization_id}")

        # Verify deletion query uses DETACH DELETE
        delete_call = mock_db_dependency.execute_write_query.call_args
        query = delete_call[0][0]

        assert "DETACH DELETE org" in query
        assert "MATCH (org:Organization {organization_id: $organization_id})" in query

    def test_successful_deletion_returns_summary_data(self, client, mock_db_dependency):
        """Test that successful deletion returns summary information."""
        organization_id = "org_test123"

        mock_db_dependency.execute_query.side_effect = [
            [{"exists": True}],
            [{"account_count": 0}],
        ]

        mock_db_dependency.execute_write_query.return_value = {
            "nodes_deleted": 1,
            "relationships_deleted": 3,
        }

        response = client.delete(f"/api/v1/organizations/{organization_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["message"] == f"Organization {organization_id} deleted successfully"
        assert data["data"]["organization_id"] == organization_id
        assert data["data"]["nodes_deleted"] == 1
        assert data["data"]["relationships_deleted"] == 3
