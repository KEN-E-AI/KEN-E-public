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
    CustomerProfileCreate,
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
        """Test that unlinking deletes associated marketing strategies."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"
        profile_id = test_customer_profile["node_id"]
        category_id = test_product_category["node_id"]

        # Link product category
        await authenticated_client.post(
            f"{base_url}/customer-profiles/{profile_id}/link-product-category",
            json={"product_category_node_id": category_id},
        )

        # Create a ProblemAwarenessStrategy for this profile/category pair
        strategy_data = ProblemAwarenessStrategyCreate(
            display_name="Test Strategy", description="Test strategy description"
        )

        strategy_response = await authenticated_client.post(
            f"{base_url}/product-categories/{category_id}/customer-profiles/{profile_id}/problem-awareness-strategies",
            json=strategy_data.model_dump(),
        )
        assert strategy_response.status_code == 200
        strategy_id = strategy_response.json()["node_id"]

        # Unlink (should cascade delete strategy)
        unlink_response = await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}/unlink-product-category/{category_id}"
        )
        assert unlink_response.status_code == 200

        # Verify strategy is deleted
        strategy_get = await authenticated_client.get(
            f"{base_url}/problem-awareness-strategies/{strategy_id}"
        )
        assert strategy_get.status_code == 404
