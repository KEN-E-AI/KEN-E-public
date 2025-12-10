"""Integration tests for rollup marketing strategy API endpoints.

Tests CRUD operations for RollupMarketingStrategy hub and rollup strategy nodes.
These tests require real Neo4j and Firestore instances.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.kene_api.main import app
from src.kene_api.models.graph_models import RollupMarketingStrategyCreate

# Test account and user fixtures
TEST_ACCOUNT_ID = "test_rollup_acc_123"
TEST_USER_ID = "test_rollup_user_456"

# Skip all tests in this module in CI unless DATABASE_INTEGRATION_TESTS is enabled
pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_INTEGRATION_TESTS") != "true",
    reason="Requires real Neo4j and Firestore databases - set DATABASE_INTEGRATION_TESTS=true to run",
)


@pytest_asyncio.fixture
async def authenticated_client():
    """Create authenticated test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Add auth headers if needed
        client.headers.update({"Authorization": "Bearer test_token"})
        yield client


@pytest_asyncio.fixture
async def setup_test_account(authenticated_client):
    """Set up test account in Neo4j before tests."""
    # Assume account exists or is created by account setup logic
    yield TEST_ACCOUNT_ID
    # Cleanup after tests would happen here


class TestRollupMarketingHub:
    """Tests for RollupMarketingStrategy hub endpoints."""

    @pytest.mark.asyncio
    async def test_get_rollup_hub_success(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test GET rollup marketing hub returns hub with linked strategies."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        response = await authenticated_client.get(
            f"{base_url}/rollup-marketing-strategy"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["node_id"] == f"rollup_marketing_hub_{account_id}"
        assert "rollup_strategies" in data
        assert isinstance(data["rollup_strategies"], dict)

    @pytest.mark.asyncio
    async def test_get_rollup_hub_not_found(
        self,
        authenticated_client,
    ):
        """Test GET rollup hub returns 404 if not created yet."""
        nonexistent_account = "nonexistent_account_999"
        base_url = f"/api/v1/knowledge-graph/marketing/{nonexistent_account}"

        response = await authenticated_client.get(
            f"{base_url}/rollup-marketing-strategy"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_rollup_hub(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test POST creates rollup marketing hub."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        hub_data = RollupMarketingStrategyCreate(
            description="Test rollup marketing strategy"
        )

        response = await authenticated_client.post(
            f"{base_url}/rollup-marketing-strategy",
            json=hub_data.model_dump(),
        )

        assert response.status_code == 201
        data = response.json()

        assert data["node_id"].startswith("rollup_marketing_hub_")
        assert data["description"] == "Test rollup marketing strategy"

    @pytest.mark.asyncio
    async def test_update_rollup_hub(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test PATCH updates rollup hub description."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # First, get the existing hub
        get_response = await authenticated_client.get(
            f"{base_url}/rollup-marketing-strategy"
        )
        assert get_response.status_code == 200
        existing_hub = get_response.json()
        node_id = existing_hub["node_id"]

        # Update the hub
        response = await authenticated_client.patch(
            f"{base_url}/rollup-marketing-strategy/{node_id}",
            json={"description": "Updated rollup description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated rollup description"

    @pytest.mark.asyncio
    async def test_delete_rollup_hub(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test DELETE removes rollup hub."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # First create a hub to delete
        hub_data = RollupMarketingStrategyCreate(description="Hub to delete")
        create_response = await authenticated_client.post(
            f"{base_url}/rollup-marketing-strategy",
            json=hub_data.model_dump(),
        )
        assert create_response.status_code == 201
        node_id = create_response.json()["node_id"]

        # Delete it
        delete_response = await authenticated_client.delete(
            f"{base_url}/rollup-marketing-strategy/{node_id}"
        )

        assert delete_response.status_code == 200

        # Verify it's deleted
        get_response = await authenticated_client.get(
            f"{base_url}/rollup-marketing-strategy"
        )
        assert get_response.status_code == 404


class TestRollupStrategies:
    """Tests for rollup strategy endpoints."""

    @pytest.mark.asyncio
    async def test_list_rollup_problem_awareness_strategies(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test listing rollup problem awareness strategies."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        response = await authenticated_client.get(
            f"{base_url}/rollup-problem-awareness-strategies"
        )

        assert response.status_code == 200
        data = response.json()

        assert "strategies" in data
        assert data["total_count"] >= 0

        # If rollup exists, verify it has correct structure
        if data["total_count"] > 0:
            rollup = data["strategies"][0]
            assert rollup["node_id"].startswith("rollup_problemawareness_")
            assert "individual_strategy_count" in rollup

    @pytest.mark.asyncio
    async def test_get_rollup_strategy_with_individuals(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test getting rollup strategy includes linked individual strategies."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # First list to get a rollup strategy node_id
        list_response = await authenticated_client.get(
            f"{base_url}/rollup-problem-awareness-strategies"
        )
        assert list_response.status_code == 200
        list_data = list_response.json()

        if list_data["total_count"] == 0:
            pytest.skip("No rollup strategies exist to test")

        node_id = list_data["strategies"][0]["node_id"]

        # Get the specific rollup strategy
        response = await authenticated_client.get(
            f"{base_url}/rollup-problem-awareness-strategies/{node_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert "linked_individual_strategies" in data
        assert isinstance(data["linked_individual_strategies"], list)

    @pytest.mark.asyncio
    async def test_list_all_rollup_strategy_types(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test that all 5 rollup strategy type endpoints are accessible."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        endpoints = [
            "/rollup-problem-awareness-strategies",
            "/rollup-brand-awareness-strategies",
            "/rollup-consideration-strategies",
            "/rollup-conversion-strategies",
            "/rollup-loyalty-strategies",
        ]

        for endpoint in endpoints:
            response = await authenticated_client.get(f"{base_url}{endpoint}")
            assert response.status_code == 200
            data = response.json()
            assert "strategies" in data
            assert "total_count" in data
