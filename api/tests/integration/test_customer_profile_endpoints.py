"""Integration tests for customer profile endpoints.

Tests link/unlink product categories and cascade deletion.
Requires DATABASE_INTEGRATION_TESTS=true to run.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.kene_api.main import app
from src.kene_api.models.graph_models import (
    BrandAwarenessStrategyCreate,
    ConsiderationStrategyCreate,
    ConversionStrategyCreate,
    CustomerProfileCreate,
    LoyaltyStrategyCreate,
    ProblemAwarenessStrategyCreate,
    ProductCategoryCreate,
)

TEST_ACCOUNT_ID = "test_account_customer_profiles_123"
TEST_USER_ID = "test_user_profiles_456"

pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_INTEGRATION_TESTS") != "true",
    reason="Requires real databases - set DATABASE_INTEGRATION_TESTS=true",
)


@pytest_asyncio.fixture
async def authenticated_client():
    """Create authenticated test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.headers.update({"Authorization": "Bearer test_token"})
        yield client


@pytest_asyncio.fixture
async def test_customer_profile(authenticated_client):
    """Create a test customer profile."""
    base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

    profile_data = CustomerProfileCreate(
        display_name="Test Profile",
        description="Test customer profile description",
        references=[],
    )

    response = await authenticated_client.post(
        f"{base_url}/customer-profiles", json=profile_data.model_dump()
    )
    assert response.status_code == 200
    profile = response.json()

    yield profile

    # Cleanup
    await authenticated_client.delete(
        f"{base_url}/customer-profiles/{profile['node_id']}"
    )


@pytest_asyncio.fixture
async def test_product_category(authenticated_client):
    """Create a test product category."""
    base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

    category_data = ProductCategoryCreate(
        product_name="Test Product", description="Test product description"
    )

    response = await authenticated_client.post(
        f"{base_url}/product-categories", json=category_data.model_dump()
    )
    assert response.status_code == 200
    category = response.json()

    yield category

    # Cleanup
    await authenticated_client.delete(
        f"{base_url}/product-categories/{category['node_id']}"
    )


class TestCustomerProfileLinking:
    """Test customer profile linking to product categories."""

    @pytest.mark.asyncio
    async def test_link_product_category_success(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test successfully linking a product category to customer profile."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link product category
        response = await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Product category linked successfully"

        # Verify link exists by fetching linked categories
        get_response = await authenticated_client.get(
            f"{base_url}/customer-profiles/{profile_id}/product-categories"
        )
        assert get_response.status_code == 200
        linked_categories = get_response.json()["categories"]
        assert len(linked_categories) == 1
        assert linked_categories[0]["node_id"] == category_id

    @pytest.mark.asyncio
    async def test_link_duplicate_fails(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test that linking same category twice fails."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # First link succeeds
        response1 = await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )
        assert response1.status_code == 200

        # Second link fails
        response2 = await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_unlink_product_category_success(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test successfully unlinking a product category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link first
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Unlink
        response = await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}/unlink-product-category/{category_id}"
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Product category unlinked successfully"

        # Verify no linked categories
        get_response = await authenticated_client.get(
            f"{base_url}/customer-profiles/{profile_id}/product-categories"
        )
        assert get_response.status_code == 200
        assert len(get_response.json()["categories"]) == 0


class TestCascadeDeletion:
    """Test cascade deletion when unlinking."""

    @pytest.mark.asyncio
    async def test_unlink_deletes_strategies(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test that unlinking deletes ALL 5 associated marketing strategy types."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link product category
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Create all 5 strategy types for this profile/category pair
        strategy_types = [
            ("problem-awareness-strategies", ProblemAwarenessStrategyCreate),
            ("brand-awareness-strategies", BrandAwarenessStrategyCreate),
            ("consideration-strategies", ConsiderationStrategyCreate),
            ("conversion-strategies", ConversionStrategyCreate),
            ("loyalty-strategies", LoyaltyStrategyCreate),
        ]

        strategy_ids = {}
        for endpoint_name, strategy_class in strategy_types:
            strategy_data = strategy_class(
                display_name=f"Test {endpoint_name.replace('-', ' ').title()}",
                description=f"Test {endpoint_name} description",
            )

            strategy_response = await authenticated_client.post(
                f"{base_url}/product-categories/{category_id}/customer-profiles/{profile_id}/{endpoint_name}",
                json=strategy_data.model_dump(),
            )
            assert strategy_response.status_code == 200
            strategy_ids[endpoint_name] = strategy_response.json()["node_id"]

        # Unlink (should cascade delete ALL strategies)
        unlink_response = await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}/unlink-product-category/{category_id}"
        )
        assert unlink_response.status_code == 200

        # Verify ALL 5 strategies are deleted
        for endpoint_name, strategy_id in strategy_ids.items():
            strategy_get = await authenticated_client.get(
                f"{base_url}/{endpoint_name}/{strategy_id}"
            )
            assert (
                strategy_get.status_code == 404
            ), f"Strategy {endpoint_name} with ID {strategy_id} should be deleted"


class TestNewEndpoints:
    """Test new endpoints added in marketing strategy PR."""

    @pytest.mark.asyncio
    async def test_list_linked_customer_profiles(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test listing customer profiles linked to a product category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Initially no profiles linked
        get_response = await authenticated_client.get(
            f"{base_url}/product-categories/{category_id}/customer-profiles"
        )
        assert get_response.status_code == 200
        assert len(get_response.json()["customer_profiles"]) == 0

        # Link profile to category
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Verify profile appears in list
        get_response = await authenticated_client.get(
            f"{base_url}/product-categories/{category_id}/customer-profiles"
        )
        assert get_response.status_code == 200
        profiles = get_response.json()["customer_profiles"]
        assert len(profiles) == 1
        assert profiles[0]["node_id"] == profile_id

        # Unlink and verify empty again
        await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}/unlink-product-category/{category_id}"
        )

        get_response = await authenticated_client.get(
            f"{base_url}/product-categories/{category_id}/customer-profiles"
        )
        assert get_response.status_code == 200
        assert len(get_response.json()["customer_profiles"]) == 0

    @pytest.mark.asyncio
    async def test_auto_created_strategies_have_node_ids(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test that auto-created strategies have customer_profile_node_id and product_category_node_id."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link product category (triggers auto-creation)
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Verify all 5 auto-created strategies have the required IDs
        strategy_endpoints = [
            "problem-awareness-strategies",
            "brand-awareness-strategies",
            "consideration-strategies",
            "conversion-strategies",
            "loyalty-strategies",
        ]

        for endpoint in strategy_endpoints:
            # List strategies for this profile
            list_response = await authenticated_client.get(
                f"{base_url}/{endpoint}?customer_profile_node_id={profile_id}"
            )
            assert list_response.status_code == 200

            strategies_data = list_response.json()
            # The response field name varies by strategy type
            strategies_key = [k for k in strategies_data.keys() if k.endswith("_strategies")][0]
            strategies = strategies_data[strategies_key]

            # Should have exactly 1 auto-created strategy
            assert len(strategies) >= 1, f"Expected at least 1 strategy for {endpoint}"

            # Find the strategy for this category
            strategy = next(
                (s for s in strategies if s.get("product_category_node_id") == category_id),
                None
            )
            assert strategy is not None, f"No strategy found for category {category_id}"

            # Verify required fields are present and not None
            assert strategy["customer_profile_node_id"] == profile_id
            assert strategy["product_category_node_id"] == category_id

    @pytest.mark.asyncio
    async def test_strategy_cascade_uses_case_statement(
        self, authenticated_client, test_customer_profile, test_product_category
    ):
        """Test that cascade deletion properly identifies strategy types using CASE statement."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link product category (auto-creates 5 strategies)
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Get list of auto-created strategy IDs
        strategy_ids = []
        strategy_endpoints = [
            "problem-awareness-strategies",
            "brand-awareness-strategies",
            "consideration-strategies",
            "conversion-strategies",
            "loyalty-strategies",
        ]

        for endpoint in strategy_endpoints:
            list_response = await authenticated_client.get(
                f"{base_url}/{endpoint}?customer_profile_node_id={profile_id}"
            )
            assert list_response.status_code == 200

            strategies_data = list_response.json()
            strategies_key = [k for k in strategies_data.keys() if k.endswith("_strategies")][0]
            strategies = strategies_data[strategies_key]

            for strategy in strategies:
                if strategy.get("product_category_node_id") == category_id:
                    strategy_ids.append((endpoint, strategy["node_id"]))

        # Should have found all 5 auto-created strategies
        assert len(strategy_ids) == 5, f"Expected 5 strategies, found {len(strategy_ids)}"

        # Unlink (triggers cascade deletion with CASE statement)
        unlink_response = await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}/unlink-product-category/{category_id}"
        )
        assert unlink_response.status_code == 200

        # Verify ALL strategies are properly deleted
        for endpoint, strategy_id in strategy_ids:
            get_response = await authenticated_client.get(
                f"{base_url}/{endpoint}/{strategy_id}"
            )
            assert get_response.status_code == 404, (
                f"Strategy {strategy_id} from {endpoint} should be deleted. "
                f"If found, CASE statement may be returning generic 'Strategy' label."
            )
