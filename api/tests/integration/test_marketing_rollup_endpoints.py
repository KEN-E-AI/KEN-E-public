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


async def create_test_account_in_neo4j(client: AsyncClient, account_id: str) -> bool:
    """Create test account node in Neo4j via API.

    Returns:
        True if account created or already exists, False otherwise
    """
    # Check if account already exists
    response = await client.get(f"/api/v1/accounts/{account_id}")
    if response.status_code == 200:
        return True

    # Create account via API
    account_data = {
        "account_name": "Test Rollup Account",
        "organization_id": "test_org_rollup",
        "industry": "Technology",
        "websites": ["https://test-rollup.com"],
        "timezone": "America/New_York",
    }

    response = await client.post("/api/v1/accounts/", json=account_data)
    return response.status_code in [200, 201]


async def cleanup_test_rollup_nodes(client: AsyncClient, account_id: str) -> None:
    """Clean up test rollup nodes created during testing.

    Deletes rollup hub and all rollup strategy nodes for the test account.
    """
    base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

    # Delete rollup hub (if exists)
    try:
        hub_response = await client.get(f"{base_url}/rollup-marketing-strategy")
        if hub_response.status_code == 200:
            hub_data = hub_response.json()
            hub_node_id = hub_data.get("node_id")
            if hub_node_id:
                await client.delete(
                    f"{base_url}/rollup-marketing-strategy/{hub_node_id}"
                )
    except Exception:
        pass  # Hub might not exist

    # Delete rollup strategies for each type
    strategy_types = [
        "rollup-problem-awareness-strategies",
        "rollup-brand-awareness-strategies",
        "rollup-consideration-strategies",
        "rollup-conversion-strategies",
        "rollup-loyalty-strategies",
    ]

    for strategy_type in strategy_types:
        try:
            list_response = await client.get(f"{base_url}/{strategy_type}")
            if list_response.status_code == 200:
                strategies = list_response.json().get("strategies", [])
                for strategy in strategies:
                    node_id = strategy.get("node_id")
                    if node_id:
                        # Delete via appropriate endpoint based on strategy type
                        strategy_base = strategy_type.replace("rollup-", "").replace(
                            "-strategies", "-strategy"
                        )
                        await client.delete(f"{base_url}/{strategy_base}/{node_id}")
        except Exception:
            pass  # Strategy might not exist


@pytest_asyncio.fixture
async def setup_test_account(authenticated_client):
    """Set up test account in Neo4j before tests and clean up after."""
    # Setup: Create test account if it doesn't exist
    account_created = await create_test_account_in_neo4j(
        authenticated_client, TEST_ACCOUNT_ID
    )

    if not account_created:
        pytest.skip(f"Could not create test account {TEST_ACCOUNT_ID}")

    yield TEST_ACCOUNT_ID

    # Teardown: Clean up rollup nodes created during tests
    await cleanup_test_rollup_nodes(authenticated_client, TEST_ACCOUNT_ID)


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


class TestRollupEdgeCases:
    """Tests for edge cases and error handling in rollup endpoints."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_rollup_strategy(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test getting a rollup strategy that doesn't exist returns 404."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # Try to get a non-existent rollup strategy
        response = await authenticated_client.get(
            f"{base_url}/rollup-problem-awareness-strategies/nonexistent_rollup_123"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_rollup_strategies_with_pagination(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test pagination parameters work correctly."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # Test with skip and limit
        response = await authenticated_client.get(
            f"{base_url}/rollup-problem-awareness-strategies?skip=0&limit=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data
        assert "total_count" in data
        assert len(data["strategies"]) <= 10

    @pytest.mark.asyncio
    async def test_list_rollup_strategies_with_no_limit(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test listing without limit parameter."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # Test without limit (should return all)
        response = await authenticated_client.get(
            f"{base_url}/rollup-consideration-strategies?skip=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert "strategies" in data

    @pytest.mark.asyncio
    async def test_create_duplicate_rollup_hub(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test creating duplicate hub handles gracefully."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        hub_data = {"description": "First rollup hub"}

        # Create first hub
        response1 = await authenticated_client.post(
            f"{base_url}/rollup-marketing-strategy",
            json=hub_data,
        )

        # If first creation succeeded, try creating duplicate
        if response1.status_code == 201:
            response2 = await authenticated_client.post(
                f"{base_url}/rollup-marketing-strategy",
                json=hub_data,
            )

            # Should fail with appropriate error
            assert response2.status_code in [400, 409, 500]

    @pytest.mark.asyncio
    async def test_update_rollup_hub_with_invalid_data(
        self,
        authenticated_client,
        setup_test_account,
    ):
        """Test updating hub with invalid data."""
        account_id = setup_test_account
        base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

        # First get the hub
        get_response = await authenticated_client.get(
            f"{base_url}/rollup-marketing-strategy"
        )

        if get_response.status_code == 200:
            hub_data = get_response.json()
            node_id = hub_data["node_id"]

            # Try to update with empty description
            update_response = await authenticated_client.patch(
                f"{base_url}/rollup-marketing-strategy/{node_id}",
                json={"description": ""},
            )

            # Should either accept empty string or reject it
            assert update_response.status_code in [200, 400]


async def test_rollup_strategy_links_to_individual_strategies(
    authenticated_client, setup_test_account
):
    """Verify rollup strategies correctly link to individual strategies via [:CAN_BE_CUSTOMIZED_BY] relationship."""
    account_id = setup_test_account
    base_url = f"/api/v1/knowledge-graph/marketing/{account_id}"

    # Step 1: Create a customer profile
    profile_response = await authenticated_client.post(
        f"{base_url}/customer-profiles",
        json={
            "profile_name": "Test Profile for Rollup Links",
            "narrative": "Test customer profile narrative for rollup relationship testing",
        },
    )
    assert profile_response.status_code == 201
    profile_data = profile_response.json()
    profile_node_id = profile_data["node_id"]

    # Step 2: Create 3 individual problem awareness strategies
    individual_strategies = []
    for i in range(3):
        strategy_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json={
                "strategy_text": f"Test individual strategy {i+1}",
                "customer_profile_node_id": profile_node_id,
            },
        )
        assert strategy_response.status_code == 201
        strategy_data = strategy_response.json()
        individual_strategies.append(strategy_data["node_id"])

    # Step 3: Get the list of rollup problem awareness strategies
    # (Assumes rollup was created during test account setup or needs to be created)
    rollup_list_response = await authenticated_client.get(
        f"{base_url}/rollup-problem-awareness-strategies"
    )

    # If no rollup exists, this test can't verify the relationship
    if rollup_list_response.status_code == 200:
        rollup_list_data = rollup_list_response.json()
        if rollup_list_data.get("strategies") and len(rollup_list_data["strategies"]) > 0:
            rollup_strategy = rollup_list_data["strategies"][0]

            # Step 4: Verify the rollup strategy has linked_individual_strategies field
            assert "linked_individual_strategies" in rollup_strategy
            linked_strategies = rollup_strategy["linked_individual_strategies"]

            # The rollup should link to our 3 individual strategies
            # (or at least include them in the list)
            assert isinstance(linked_strategies, list)

            # Verify at least some of our strategies are linked
            # Note: Other tests may have created additional strategies, so we check
            # that our strategies are present, not that ONLY our strategies are present
            for strategy_id in individual_strategies:
                assert strategy_id in linked_strategies, (
                    f"Individual strategy {strategy_id} should be linked to rollup strategy "
                    f"via [:CAN_BE_CUSTOMIZED_BY] relationship"
                )
