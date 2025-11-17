"""Integration tests for knowledge graph endpoints.

Tests full CRUD flow with real Neo4j and Firestore instances.
"""

import pytest
from httpx import AsyncClient
from kene_api.main import app
from kene_api.models.graph_models import (
    CompetitorCreate,
    CompetitorStrengthCreate,
    CompetitorTacticCreate,
    CompetitorWeaknessCreate,
    GoalCreate,
    OpportunityCreate,
    ProductCategoryCreate,
    ProductCreate,
    RiskCreate,
    StrengthCreate,
    SubstituteProductCreate,
    ValuePropositionCreate,
)

# Test account and user fixtures
TEST_ACCOUNT_ID = "test_account_integration_123"
TEST_USER_ID = "test_user_integration_456"


@pytest.fixture
async def authenticated_client():
    """Create authenticated test client."""
    # Note: In real integration tests, you'd set up proper auth
    # For now, we assume auth is mocked or bypassed in test environment
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Add auth headers if needed
        client.headers.update({"Authorization": "Bearer test_token"})
        yield client


@pytest.fixture
async def setup_test_account(authenticated_client):
    """Set up test account in Neo4j before tests."""
    # Create test account node if it doesn't exist
    # This would be handled by your account setup logic
    yield TEST_ACCOUNT_ID

    # Cleanup after tests
    # Delete all test nodes created during testing


class TestProductCategoryEndpoints:
    """Integration tests for ProductCategory CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_list_get_update_delete_category(self, authenticated_client):
        """Test complete CRUD flow for product category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # 1. CREATE - Create a new product category
        category_data = ProductCategoryCreate(
            product_name="Cloud Services",
            description="Enterprise cloud computing solutions",
        )

        create_response = await authenticated_client.post(
            f"{base_url}/product-categories", json=category_data.model_dump()
        )
        assert create_response.status_code == 200
        created_category = create_response.json()
        assert created_category["product_name"] == "Cloud Services"
        assert created_category["account_id"] == TEST_ACCOUNT_ID
        assert "node_id" in created_category

        category_node_id = created_category["node_id"]

        # 2. LIST - Verify category appears in list
        list_response = await authenticated_client.get(f"{base_url}/product-categories")
        assert list_response.status_code == 200
        categories = list_response.json()
        assert categories["total_count"] >= 1
        assert any(
            cat["node_id"] == category_node_id for cat in categories["categories"]
        )

        # 3. GET - Retrieve specific category
        get_response = await authenticated_client.get(
            f"{base_url}/product-categories/{category_node_id}"
        )
        assert get_response.status_code == 200
        retrieved_category = get_response.json()
        assert retrieved_category["node_id"] == category_node_id
        assert retrieved_category["product_name"] == "Cloud Services"

        # 4. UPDATE - Update category
        update_response = await authenticated_client.patch(
            f"{base_url}/product-categories/{category_node_id}",
            json={"product_name": "Cloud & AI Services"},
        )
        assert update_response.status_code == 200
        updated_category = update_response.json()
        assert updated_category["product_name"] == "Cloud & AI Services"
        assert (
            updated_category["description"] == "Enterprise cloud computing solutions"
        )  # Unchanged

        # 5. DELETE - Delete category
        delete_response = await authenticated_client.delete(
            f"{base_url}/product-categories/{category_node_id}"
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["success"] is True

        # 6. VERIFY DELETION - Confirm category no longer exists
        get_deleted_response = await authenticated_client.get(
            f"{base_url}/product-categories/{category_node_id}"
        )
        assert get_deleted_response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_delete_category_with_products(self, authenticated_client):
        """Test that category with products cannot be deleted."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create category
        category_data = ProductCategoryCreate(
            product_name="SaaS Products", description="Software as a Service offerings"
        )
        create_cat_response = await authenticated_client.post(
            f"{base_url}/product-categories", json=category_data.model_dump()
        )
        category_node_id = create_cat_response.json()["node_id"]

        # Create product under category
        product_data = ProductCreate(
            product_name="Analytics Platform",
            description="Real-time analytics",
            category_node_id=category_node_id,
        )
        create_prod_response = await authenticated_client.post(
            f"{base_url}/products", json=product_data.model_dump()
        )
        product_node_id = create_prod_response.json()["node_id"]

        # Try to delete category (should fail)
        delete_response = await authenticated_client.delete(
            f"{base_url}/product-categories/{category_node_id}"
        )
        assert delete_response.status_code == 400
        assert "Cannot delete ProductCategory" in delete_response.json()["detail"]

        # Cleanup: Delete product first, then category
        await authenticated_client.delete(f"{base_url}/products/{product_node_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_node_id}"
        )


class TestProductEndpoints:
    """Integration tests for Product CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_product_with_category(self, authenticated_client):
        """Test creating product linked to category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parent category
        category_data = ProductCategoryCreate(
            product_name="Mobile Apps", description="Mobile application suite"
        )
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories", json=category_data.model_dump()
        )
        category_node_id = cat_response.json()["node_id"]

        # Create product
        product_data = ProductCreate(
            product_name="iOS App",
            description="Native iOS application",
            references=["https://apps.apple.com/app"],
            product_detail_page="https://example.com/ios",
            category_node_id=category_node_id,
        )
        prod_response = await authenticated_client.post(
            f"{base_url}/products", json=product_data.model_dump()
        )
        assert prod_response.status_code == 200
        product = prod_response.json()
        assert product["product_name"] == "iOS App"
        assert product["category_node_id"] == category_node_id
        assert len(product["references"]) == 1

        # Cleanup
        await authenticated_client.delete(f"{base_url}/products/{product['node_id']}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_node_id}"
        )

    @pytest.mark.asyncio
    async def test_list_products_filtered_by_category(self, authenticated_client):
        """Test filtering products by parent category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create two categories
        cat1_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Hardware", "description": "Physical products"},
        )
        cat1_id = cat1_response.json()["node_id"]

        cat2_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Software", "description": "Digital products"},
        )
        cat2_id = cat2_response.json()["node_id"]

        # Create products in each category
        prod1_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "Server Rack",
                "description": "Data center hardware",
                "category_node_id": cat1_id,
            },
        )
        prod1_id = prod1_response.json()["node_id"]

        prod2_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "Database Software",
                "description": "SQL database",
                "category_node_id": cat2_id,
            },
        )
        prod2_id = prod2_response.json()["node_id"]

        # List products filtered by cat1
        list_response = await authenticated_client.get(
            f"{base_url}/products?category_node_id={cat1_id}"
        )
        assert list_response.status_code == 200
        products = list_response.json()
        assert products["total_count"] == 1
        assert products["products"][0]["product_name"] == "Server Rack"

        # Cleanup
        await authenticated_client.delete(f"{base_url}/products/{prod1_id}")
        await authenticated_client.delete(f"{base_url}/products/{prod2_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat1_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat2_id}")

    @pytest.mark.asyncio
    async def test_list_all_products_includes_category_info(self, authenticated_client):
        """Test listing all products includes category_node_id (N+1 query fix).

        Verifies that when listing products without category filter, the endpoint
        returns category information without making N+1 queries.
        """
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create a category
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={
                "product_name": "Test Category",
                "description": "Test category for N+1 fix",
            },
        )
        assert cat_response.status_code == 200
        cat_id = cat_response.json()["node_id"]

        # Create multiple products in the category
        product_ids = []
        for i in range(3):
            prod_response = await authenticated_client.post(
                f"{base_url}/products",
                json={
                    "product_name": f"Test Product {i}",
                    "description": f"Product {i} description",
                    "category_node_id": cat_id,
                },
            )
            assert prod_response.status_code == 200
            product_ids.append(prod_response.json()["node_id"])

        # List ALL products (no category filter) - this tests the N+1 fix
        list_response = await authenticated_client.get(f"{base_url}/products")
        assert list_response.status_code == 200
        products = list_response.json()

        # Verify all products have category_node_id populated
        test_products = [p for p in products["products"] if p["node_id"] in product_ids]
        assert len(test_products) == 3
        for product in test_products:
            assert "category_node_id" in product
            assert product["category_node_id"] == cat_id

        # Cleanup
        for prod_id in product_ids:
            await authenticated_client.delete(f"{base_url}/products/{prod_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestSWOTEndpoints:
    """Integration tests for SWOT Analysis endpoints."""

    @pytest.mark.asyncio
    async def test_swot_hub_auto_creation(self, authenticated_client):
        """Test SWOT Analysis hub is auto-created when first strength is added."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create first strength (should auto-create SWOT hub)
        strength_data = StrengthCreate(
            display_name="Market Leader",
            description="Leading position in the market",
            references=["https://example.com/report"],
        )
        strength_response = await authenticated_client.post(
            f"{base_url}/strengths", json=strength_data.model_dump()
        )
        assert strength_response.status_code == 200
        strength = strength_response.json()
        strength_id = strength["node_id"]

        # Verify strength exists
        assert strength["display_name"] == "Market Leader"

        # Cleanup
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")

    @pytest.mark.asyncio
    async def test_opportunity_linked_to_strength(self, authenticated_client):
        """Test creating opportunity linked to parent strength."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create strength
        strength_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Strong Brand",
                "description": "Well-recognized brand",
                "references": [],
            },
        )
        strength_id = strength_response.json()["node_id"]

        # Create opportunity linked to strength
        opportunity_data = OpportunityCreate(
            display_name="Market Expansion",
            description="Expand to new markets leveraging brand",
            references=["https://example.com/market-research"],
            strength_node_id=strength_id,
        )
        opp_response = await authenticated_client.post(
            f"{base_url}/opportunities", json=opportunity_data.model_dump()
        )
        assert opp_response.status_code == 200
        opportunity = opp_response.json()
        assert opportunity["strength_node_id"] == strength_id
        opp_id = opportunity["node_id"]

        # List opportunities filtered by strength
        list_response = await authenticated_client.get(
            f"{base_url}/opportunities?strength_node_id={strength_id}"
        )
        opportunities = list_response.json()
        assert opportunities["total_count"] == 1
        assert opportunities["opportunities"][0]["node_id"] == opp_id

        # Cleanup
        await authenticated_client.delete(f"{base_url}/opportunities/{opp_id}")
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")

    @pytest.mark.asyncio
    async def test_risk_linked_to_weakness(self, authenticated_client):
        """Test creating risk linked to parent weakness."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create weakness
        weakness_response = await authenticated_client.post(
            f"{base_url}/weaknesses",
            json={
                "display_name": "Limited Resources",
                "description": "Small team size",
                "references": [],
            },
        )
        weakness_id = weakness_response.json()["node_id"]

        # Create risk linked to weakness
        risk_data = RiskCreate(
            display_name="Scaling Challenges",
            description="Difficulty scaling operations",
            references=[],
            weakness_node_id=weakness_id,
        )
        risk_response = await authenticated_client.post(
            f"{base_url}/risks", json=risk_data.model_dump()
        )
        assert risk_response.status_code == 200
        risk = risk_response.json()
        assert risk["weakness_node_id"] == weakness_id
        risk_id = risk["node_id"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/risks/{risk_id}")
        await authenticated_client.delete(f"{base_url}/weaknesses/{weakness_id}")

    @pytest.mark.asyncio
    async def test_cannot_delete_strength_with_opportunities(
        self, authenticated_client
    ):
        """Test that strength with opportunities cannot be deleted."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create strength
        strength_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Innovation",
                "description": "Culture of innovation",
                "references": [],
            },
        )
        strength_id = strength_response.json()["node_id"]

        # Create opportunity
        opp_response = await authenticated_client.post(
            f"{base_url}/opportunities",
            json={
                "display_name": "New Products",
                "description": "Launch innovative products",
                "references": [],
                "strength_node_id": strength_id,
            },
        )
        opp_id = opp_response.json()["node_id"]

        # Try to delete strength (should fail)
        delete_response = await authenticated_client.delete(
            f"{base_url}/strengths/{strength_id}"
        )
        assert delete_response.status_code == 400
        assert "Cannot delete Strength" in delete_response.json()["detail"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/opportunities/{opp_id}")
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")


class TestGoalEndpoints:
    """Integration tests for Goal endpoints."""

    @pytest.mark.asyncio
    async def test_goal_crud(self, authenticated_client):
        """Test complete CRUD flow for strategic goals."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create goal
        goal_data = GoalCreate(
            display_name="Increase Revenue",
            description="Achieve 50% revenue growth in 2025",
            references=["https://example.com/strategy"],
        )
        create_response = await authenticated_client.post(
            f"{base_url}/goals", json=goal_data.model_dump()
        )
        assert create_response.status_code == 200
        goal = create_response.json()
        goal_id = goal["node_id"]

        # Update goal
        update_response = await authenticated_client.patch(
            f"{base_url}/goals/{goal_id}",
            json={"display_name": "Accelerate Revenue Growth"},
        )
        assert update_response.status_code == 200
        updated_goal = update_response.json()
        assert updated_goal["display_name"] == "Accelerate Revenue Growth"

        # Cleanup
        await authenticated_client.delete(f"{base_url}/goals/{goal_id}")


class TestValuePropositionEndpoints:
    """Integration tests for ValueProposition endpoints."""

    @pytest.mark.asyncio
    async def test_value_prop_linked_to_product(self, authenticated_client):
        """Test value proposition linked to product."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create category and product
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={
                "product_name": "Enterprise Software",
                "description": "B2B solutions",
            },
        )
        cat_id = cat_response.json()["node_id"]

        prod_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "CRM System",
                "description": "Customer relationship management",
                "category_node_id": cat_id,
            },
        )
        prod_id = prod_response.json()["node_id"]

        # Create value proposition for product
        vp_data = ValuePropositionCreate(
            display_name="Boost Sales Efficiency",
            description="Increase sales team productivity by 30%",
            references=["https://example.com/case-study"],
            parent_node_id=prod_id,
            parent_node_type="Product",
        )
        vp_response = await authenticated_client.post(
            f"{base_url}/value-propositions", json=vp_data.model_dump()
        )
        assert vp_response.status_code == 200
        value_prop = vp_response.json()
        assert value_prop["parent_node_id"] == prod_id
        vp_id = value_prop["node_id"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/value-propositions/{vp_id}")
        await authenticated_client.delete(f"{base_url}/products/{prod_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestBusinessStrategyAggregatedView:
    """Integration tests for aggregated business strategy endpoint."""

    @pytest.mark.asyncio
    async def test_get_complete_business_strategy(self, authenticated_client):
        """Test retrieving complete business strategy graph."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create a minimal business strategy
        # 1. Category
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Services", "description": "Professional services"},
        )
        cat_id = cat_response.json()["node_id"]

        # 2. Product
        prod_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "Consulting",
                "description": "Strategic consulting",
                "category_node_id": cat_id,
            },
        )
        prod_id = prod_response.json()["node_id"]

        # 3. Strength
        strength_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Expertise",
                "description": "Deep domain expertise",
                "references": [],
            },
        )
        strength_id = strength_response.json()["node_id"]

        # 4. Goal
        goal_response = await authenticated_client.post(
            f"{base_url}/goals",
            json={
                "display_name": "Market Leadership",
                "description": "Become market leader",
                "references": [],
            },
        )
        goal_id = goal_response.json()["node_id"]

        # Get aggregated view
        strategy_response = await authenticated_client.get(
            f"{base_url}/business-strategy"
        )
        assert strategy_response.status_code == 200
        strategy = strategy_response.json()

        # Verify structure
        assert strategy["account_id"] == TEST_ACCOUNT_ID
        assert "product_categories" in strategy
        assert "products" in strategy
        assert "strengths" in strategy
        assert "goals" in strategy
        assert len(strategy["product_categories"]) >= 1
        assert len(strategy["products"]) >= 1
        assert len(strategy["strengths"]) >= 1
        assert len(strategy["goals"]) >= 1

        # Cleanup
        await authenticated_client.delete(f"{base_url}/goals/{goal_id}")
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")
        await authenticated_client.delete(f"{base_url}/products/{prod_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestFirestoreSync:
    """Integration tests for Neo4j + Firestore bidirectional sync."""

    @pytest.mark.asyncio
    async def test_create_syncs_to_firestore(self, authenticated_client):
        """Test that creating node in Neo4j syncs to Firestore."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create category (should sync to Firestore)
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Test Sync", "description": "Testing Firestore sync"},
        )
        assert cat_response.status_code == 200
        cat_id = cat_response.json()["node_id"]

        # TODO: Add Firestore verification
        # firestore_doc = await firestore_service.get_document(...)
        # assert cat_id in firestore_doc["product_portfolio"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")

    @pytest.mark.asyncio
    async def test_update_syncs_to_firestore(self, authenticated_client):
        """Test that updating node syncs changes to Firestore."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create and update
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={
                "product_name": "Original Name",
                "description": "Original description",
            },
        )
        cat_id = cat_response.json()["node_id"]

        update_response = await authenticated_client.patch(
            f"{base_url}/product-categories/{cat_id}",
            json={"product_name": "Updated Name"},
        )
        assert update_response.status_code == 200

        # TODO: Verify Firestore has updated data

        # Cleanup
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")

    @pytest.mark.asyncio
    async def test_delete_syncs_to_firestore(self, authenticated_client):
        """Test that deleting node syncs to Firestore."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create and delete
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "To Delete", "description": "Will be deleted"},
        )
        cat_id = cat_response.json()["node_id"]

        delete_response = await authenticated_client.delete(
            f"{base_url}/product-categories/{cat_id}"
        )
        assert delete_response.status_code == 200

        # TODO: Verify Firestore no longer has this node


class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.asyncio
    async def test_create_product_with_nonexistent_category(self, authenticated_client):
        """Test that creating product with invalid category fails."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "Orphan Product",
                "description": "Product without valid parent",
                "category_node_id": "nonexistent_category_id",
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_nonexistent_node(self, authenticated_client):
        """Test that getting nonexistent node returns 404."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        response = await authenticated_client.get(
            f"{base_url}/product-categories/nonexistent_node_id"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent_node(self, authenticated_client):
        """Test that updating nonexistent node fails."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        response = await authenticated_client.patch(
            f"{base_url}/product-categories/nonexistent_node_id",
            json={"product_name": "New Name"},
        )
        assert response.status_code == 400 or response.status_code == 404


# ==================== Competitive Strategy Integration Tests ====================


class TestCompetitorEndpoints:
    """Integration tests for Competitor CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_list_get_update_delete_competitor(self, authenticated_client):
        """Test complete CRUD flow for competitor."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # 1. CREATE - Create a new competitor
        competitor_data = CompetitorCreate(
            display_name="Molekule, Inc",
            description="Premium air purifier manufacturer with PECO technology",
            references=["https://molekule.com/about"],
        )

        create_response = await authenticated_client.post(
            f"{base_url}/competitors", json=competitor_data.model_dump()
        )
        assert create_response.status_code == 200
        created_competitor = create_response.json()
        assert created_competitor["display_name"] == "Molekule, Inc"
        assert created_competitor["account_id"] == TEST_ACCOUNT_ID
        assert "node_id" in created_competitor
        assert created_competitor["references"] == ["https://molekule.com/about"]

        competitor_node_id = created_competitor["node_id"]

        # 2. LIST - Verify competitor appears in list
        list_response = await authenticated_client.get(f"{base_url}/competitors")
        assert list_response.status_code == 200
        competitors = list_response.json()
        assert competitors["total_count"] >= 1
        assert any(
            c["node_id"] == competitor_node_id for c in competitors["competitors"]
        )

        # 3. GET - Retrieve specific competitor
        get_response = await authenticated_client.get(
            f"{base_url}/competitors/{competitor_node_id}"
        )
        assert get_response.status_code == 200
        retrieved_competitor = get_response.json()
        assert retrieved_competitor["node_id"] == competitor_node_id
        assert retrieved_competitor["display_name"] == "Molekule, Inc"

        # 4. UPDATE - Update competitor
        update_response = await authenticated_client.patch(
            f"{base_url}/competitors/{competitor_node_id}",
            json={
                "description": "Premium air purifier manufacturer with patented PECO technology"
            },
        )
        assert update_response.status_code == 200
        updated_competitor = update_response.json()
        assert "patented PECO" in updated_competitor["description"]
        assert updated_competitor["display_name"] == "Molekule, Inc"  # Unchanged

        # 5. DELETE - Delete competitor (should succeed if no dependencies)
        delete_response = await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_node_id}"
        )
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["success"] is True

        # Verify deletion
        get_after_delete = await authenticated_client.get(
            f"{base_url}/competitors/{competitor_node_id}"
        )
        assert get_after_delete.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_competitor_with_tactics_fails(self, authenticated_client):
        """Test that deleting competitor with tactics fails."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create competitor
        competitor_data = CompetitorCreate(
            display_name="Test Competitor with Tactics",
            description="Test competitor",
            references=[],
        )
        create_comp_response = await authenticated_client.post(
            f"{base_url}/competitors", json=competitor_data.model_dump()
        )
        assert create_comp_response.status_code == 200
        competitor_node_id = create_comp_response.json()["node_id"]

        # Create tactic linked to competitor
        tactic_data = CompetitorTacticCreate(
            display_name="Social Media Campaign",
            description="Active on LinkedIn and Twitter",
            references=[],
            competitor_node_id=competitor_node_id,
        )
        create_tactic_response = await authenticated_client.post(
            f"{base_url}/competitor-tactics", json=tactic_data.model_dump()
        )
        assert create_tactic_response.status_code == 200
        tactic_node_id = create_tactic_response.json()["node_id"]

        # Try to delete competitor (should fail due to tactic dependency)
        delete_response = await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_node_id}"
        )
        assert delete_response.status_code == 400
        error_data = delete_response.json()
        assert "dependent" in error_data["detail"].lower()

        # Cleanup: Delete tactic first, then competitor
        await authenticated_client.delete(
            f"{base_url}/competitor-tactics/{tactic_node_id}"
        )
        delete_comp_response = await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_node_id}"
        )
        assert delete_comp_response.status_code == 200


class TestCompetitiveStrategyAggregatedView:
    """Integration tests for aggregated competitive strategy endpoint."""

    @pytest.mark.asyncio
    async def test_get_competitive_strategy_returns_all_nodes(
        self, authenticated_client
    ):
        """Test that aggregated view returns complete competitive graph."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create test data
        # 1. Create competitor
        competitor_data = CompetitorCreate(
            display_name="Aggregation Test Competitor",
            description="Test competitor for aggregation",
            references=[],
        )
        comp_response = await authenticated_client.post(
            f"{base_url}/competitors", json=competitor_data.model_dump()
        )
        assert comp_response.status_code == 200
        competitor_node_id = comp_response.json()["node_id"]

        # 2. Create tactic
        tactic_data = CompetitorTacticCreate(
            display_name="Test Tactic",
            description="Test tactic",
            references=[],
            competitor_node_id=competitor_node_id,
        )
        tactic_response = await authenticated_client.post(
            f"{base_url}/competitor-tactics", json=tactic_data.model_dump()
        )
        assert tactic_response.status_code == 200
        tactic_node_id = tactic_response.json()["node_id"]

        # 3. Get aggregated view
        agg_response = await authenticated_client.get(
            f"{base_url}/competitive-strategy"
        )
        assert agg_response.status_code == 200
        strategy = agg_response.json()

        # Verify structure
        assert "account_id" in strategy
        assert strategy["account_id"] == TEST_ACCOUNT_ID
        assert "competitive_environment" in strategy
        assert "competitors" in strategy
        assert "competitor_tactics" in strategy
        assert "competitor_strengths" in strategy
        assert "competitor_weaknesses" in strategy
        assert "substitute_products" in strategy

        # Verify created nodes appear
        assert any(c["node_id"] == competitor_node_id for c in strategy["competitors"])
        assert any(
            t["node_id"] == tactic_node_id for t in strategy["competitor_tactics"]
        )

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/competitor-tactics/{tactic_node_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_node_id}"
        )


class TestCompetitiveEnvironmentHubBehavior:
    """Integration tests for CompetitiveEnvironment hub node behavior."""

    @pytest.mark.asyncio
    async def test_competitive_environment_auto_created_with_first_competitor(
        self, authenticated_client
    ):
        """Test that CompetitiveEnvironment is auto-created when first competitor is added."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Check if environment exists before
        env_before = await authenticated_client.get(
            f"{base_url}/competitive-environment"
        )
        # May or may not exist depending on previous tests

        # Create first competitor
        competitor_data = CompetitorCreate(
            display_name="Hub Test Competitor",
            description="Test for hub creation",
            references=[],
        )
        comp_response = await authenticated_client.post(
            f"{base_url}/competitors", json=competitor_data.model_dump()
        )
        assert comp_response.status_code == 200
        competitor_node_id = comp_response.json()["node_id"]

        # Verify environment now exists
        env_after = await authenticated_client.get(
            f"{base_url}/competitive-environment"
        )
        assert env_after.status_code == 200
        environment = env_after.json()
        assert "node_id" in environment
        assert "description" in environment

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_node_id}"
        )


class TestCompetitorLimits:
    """Integration tests for competitor resource limits."""

    @pytest.mark.asyncio
    async def test_create_competitor_enforces_account_limit(self, authenticated_client):
        """Test that creating 6th competitor fails with clear error."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 5 competitors (the maximum)
        competitor_ids = []
        for i in range(5):
            response = await authenticated_client.post(
                f"{base_url}/competitors",
                json={
                    "display_name": f"Test Competitor {i + 1}",
                    "description": f"Competitor description {i + 1}",
                    "references": [],
                },
            )
            assert response.status_code == 200
            competitor_ids.append(response.json()["node_id"])

        # Attempt to create 6th competitor should fail
        response = await authenticated_client.post(
            f"{base_url}/competitors",
            json={
                "display_name": "Test Competitor 6",
                "description": "This should fail due to limit",
                "references": [],
            },
        )
        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert "Maximum of 5 competitors" in error_detail
        assert "delete an existing competitor" in error_detail.lower()

        # Verify count is still 5
        list_response = await authenticated_client.get(f"{base_url}/competitors")
        assert list_response.status_code == 200
        assert list_response.json()["total_count"] == 5

        # Cleanup
        for competitor_id in competitor_ids:
            await authenticated_client.delete(f"{base_url}/competitors/{competitor_id}")

    @pytest.mark.asyncio
    async def test_create_competitor_tactic_enforces_per_competitor_limit(
        self, authenticated_client
    ):
        """Test that creating 6th tactic for same competitor fails."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create competitor
        comp_response = await authenticated_client.post(
            f"{base_url}/competitors",
            json={
                "display_name": "Tactic Limit Test Competitor",
                "description": "Testing tactic limits",
                "references": [],
            },
        )
        assert comp_response.status_code == 200
        competitor_id = comp_response.json()["node_id"]

        # Create 5 tactics (the maximum)
        tactic_ids = []
        for i in range(5):
            response = await authenticated_client.post(
                f"{base_url}/competitor-tactics",
                json={
                    "display_name": f"Tactic {i + 1}",
                    "description": f"Tactic description {i + 1}",
                    "references": [],
                    "competitor_node_id": competitor_id,
                },
            )
            assert response.status_code == 200
            tactic_ids.append(response.json()["node_id"])

        # Attempt to create 6th tactic should fail
        response = await authenticated_client.post(
            f"{base_url}/competitor-tactics",
            json={
                "display_name": "Tactic 6",
                "description": "This should fail due to limit",
                "references": [],
                "competitor_node_id": competitor_id,
            },
        )
        assert response.status_code == 400
        assert "Maximum of 5 tactics" in response.json()["detail"]

        # Cleanup
        for tactic_id in tactic_ids:
            await authenticated_client.delete(
                f"{base_url}/competitor-tactics/{tactic_id}"
            )
        await authenticated_client.delete(f"{base_url}/competitors/{competitor_id}")

    @pytest.mark.asyncio
    async def test_delete_competitor_frees_up_account_limit(self, authenticated_client):
        """Test that deleting a competitor allows creating a new one."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 5 competitors (the maximum)
        competitor_ids = []
        for i in range(5):
            response = await authenticated_client.post(
                f"{base_url}/competitors",
                json={
                    "display_name": f"Delete Test Competitor {i + 1}",
                    "description": f"Competitor description {i + 1}",
                    "references": [],
                },
            )
            assert response.status_code == 200
            competitor_ids.append(response.json()["node_id"])

        # Delete one competitor
        delete_response = await authenticated_client.delete(
            f"{base_url}/competitors/{competitor_ids[0]}"
        )
        assert delete_response.status_code == 200

        # Now should be able to create a new competitor
        response = await authenticated_client.post(
            f"{base_url}/competitors",
            json={
                "display_name": "New Competitor After Delete",
                "description": "This should succeed",
                "references": [],
            },
        )
        assert response.status_code == 200
        new_competitor_id = response.json()["node_id"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/competitors/{new_competitor_id}")
        for competitor_id in competitor_ids[1:]:  # Skip the already deleted one
            await authenticated_client.delete(f"{base_url}/competitors/{competitor_id}")


# ==================== Marketing Strategy Integration Tests ====================


class TestMarketingStrategyDualParentArchitecture:
    """Integration tests for dual-parent architecture of marketing strategies."""

    @pytest.mark.asyncio
    async def test_create_customer_profile_and_all_5_strategy_types(
        self, authenticated_client
    ):
        """Test creating CustomerProfile + ProductCategory + all 5 strategy types."""
        from src.kene_api.models.graph_models import (
            BrandAwarenessStrategyCreate,
            ConsiderationStrategyCreate,
            ConversionStrategyCreate,
            CustomerProfileCreate,
            LoyaltyStrategyCreate,
            ProblemAwarenessStrategyCreate,
            ProductCategoryCreate,
        )

        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create ProductCategory
        category_data = ProductCategoryCreate(
            product_name="Marketing Automation Platform",
            description="All-in-one marketing automation solution",
        )
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories", json=category_data.model_dump()
        )
        assert cat_response.status_code == 200
        category_id = cat_response.json()["node_id"]

        # Create CustomerProfile
        profile_data = CustomerProfileCreate(
            display_name="Marketing Manager Mary",
            narrative="Mid-level marketing manager at B2B SaaS company, focused on demand generation",
            references=["https://example.com/persona-research"],
        )
        profile_response = await authenticated_client.post(
            f"{base_url}/customer-profiles", json=profile_data.model_dump()
        )
        assert profile_response.status_code == 200
        profile_id = profile_response.json()["node_id"]

        # Create ProblemAwarenessStrategy
        problem_strategy = ProblemAwarenessStrategyCreate(
            description="Educate on challenges of manual marketing processes and lack of attribution",
            references=["https://example.com/problem-research"],
            product_category_node_id=category_id,
            customer_profile_node_id=profile_id,
        )
        prob_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json=problem_strategy.model_dump(),
        )
        assert prob_response.status_code == 200
        prob_id = prob_response.json()["node_id"]

        # Create BrandAwarenessStrategy
        brand_strategy = BrandAwarenessStrategyCreate(
            description="Showcase thought leadership through webinars and case studies",
            references=["https://example.com/brand-research"],
            product_category_node_id=category_id,
            customer_profile_node_id=profile_id,
        )
        brand_response = await authenticated_client.post(
            f"{base_url}/brand-awareness-strategies", json=brand_strategy.model_dump()
        )
        assert brand_response.status_code == 200
        brand_id = brand_response.json()["node_id"]

        # Create ConsiderationStrategy
        consideration_strategy = ConsiderationStrategyCreate(
            description="Provide ROI calculator and competitor comparison guides",
            references=[],
            product_category_node_id=category_id,
            customer_profile_node_id=profile_id,
        )
        cons_response = await authenticated_client.post(
            f"{base_url}/consideration-strategies",
            json=consideration_strategy.model_dump(),
        )
        assert cons_response.status_code == 200
        cons_id = cons_response.json()["node_id"]

        # Create ConversionStrategy
        conversion_strategy = ConversionStrategyCreate(
            description="Offer 14-day free trial with onboarding specialist",
            references=[],
            product_category_node_id=category_id,
            customer_profile_node_id=profile_id,
        )
        conv_response = await authenticated_client.post(
            f"{base_url}/conversion-strategies", json=conversion_strategy.model_dump()
        )
        assert conv_response.status_code == 200
        conv_id = conv_response.json()["node_id"]

        # Create LoyaltyStrategy
        loyalty_strategy = LoyaltyStrategyCreate(
            description="VIP community access and quarterly product roadmap previews",
            references=[],
            product_category_node_id=category_id,
            customer_profile_node_id=profile_id,
        )
        loy_response = await authenticated_client.post(
            f"{base_url}/loyalty-strategies", json=loyalty_strategy.model_dump()
        )
        assert loy_response.status_code == 200
        loy_id = loy_response.json()["node_id"]

        # Verify all strategies were created successfully
        assert prob_id.startswith("problemaware_")
        assert brand_id.startswith("brandaware_")
        assert cons_id.startswith("consideration_")
        assert conv_id.startswith("conversion_")
        assert loy_id.startswith("loyalty_")

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/problem-awareness-strategies/{prob_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/brand-awareness-strategies/{brand_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/consideration-strategies/{cons_id}"
        )
        await authenticated_client.delete(f"{base_url}/conversion-strategies/{conv_id}")
        await authenticated_client.delete(f"{base_url}/loyalty-strategies/{loy_id}")
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )

    @pytest.mark.asyncio
    async def test_verify_dual_relationships_in_neo4j(self, authenticated_client):
        """Test that strategies have correct dual relationships to both parents."""
        from src.kene_api.models.graph_models import (
            CustomerProfileCreate,
            ProblemAwarenessStrategyCreate,
            ProductCategoryCreate,
        )

        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parents
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Test Category", "description": "Test"},
        )
        category_id = cat_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Test Profile",
                "narrative": "Test narrative",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create strategy
        strategy_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json={
                "description": "Test strategy",
                "references": [],
                "product_category_node_id": category_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy_id = strategy_response.json()["node_id"]

        # Retrieve strategy and verify parent IDs are stored
        get_response = await authenticated_client.get(
            f"{base_url}/problem-awareness-strategies/{strategy_id}"
        )
        assert get_response.status_code == 200
        strategy = get_response.json()
        assert strategy["product_category_node_id"] == category_id
        assert strategy["customer_profile_node_id"] == profile_id

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/problem-awareness-strategies/{strategy_id}"
        )
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )

    @pytest.mark.asyncio
    async def test_list_strategies_filtered_by_customer_profile(
        self, authenticated_client
    ):
        """Test filtering strategies by CustomerProfile."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 2 profiles, 1 category, and strategies for each profile
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "SaaS Platform", "description": "Test"},
        )
        category_id = cat_response.json()["node_id"]

        prof1_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Profile One",
                "narrative": "First profile",
                "references": [],
            },
        )
        profile1_id = prof1_response.json()["node_id"]

        prof2_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Profile Two",
                "narrative": "Second profile",
                "references": [],
            },
        )
        profile2_id = prof2_response.json()["node_id"]

        # Create strategies for both profiles
        strat1_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json={
                "description": "Strategy for profile 1",
                "references": [],
                "product_category_node_id": category_id,
                "customer_profile_node_id": profile1_id,
            },
        )
        strategy1_id = strat1_response.json()["node_id"]

        strat2_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json={
                "description": "Strategy for profile 2",
                "references": [],
                "product_category_node_id": category_id,
                "customer_profile_node_id": profile2_id,
            },
        )
        strategy2_id = strat2_response.json()["node_id"]

        # List strategies filtered by profile1
        list_response = await authenticated_client.get(
            f"{base_url}/problem-awareness-strategies?customer_profile_node_id={profile1_id}"
        )
        assert list_response.status_code == 200
        strategies = list_response.json()

        # Verify only strategy1 is returned
        assert strategies["total_count"] == 1
        assert strategies["strategies"][0]["node_id"] == strategy1_id

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/problem-awareness-strategies/{strategy1_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/problem-awareness-strategies/{strategy2_id}"
        )
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile1_id}")
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile2_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )

    @pytest.mark.asyncio
    async def test_list_strategies_filtered_by_product_category(
        self, authenticated_client
    ):
        """Test filtering strategies by ProductCategory."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 2 categories, 1 profile, strategies for each category
        cat1_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Category A", "description": "Test"},
        )
        category1_id = cat1_response.json()["node_id"]

        cat2_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Category B", "description": "Test"},
        )
        category2_id = cat2_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Shared Profile",
                "narrative": "Used by both categories",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create strategies for both categories
        strat1_response = await authenticated_client.post(
            f"{base_url}/brand-awareness-strategies",
            json={
                "description": "Strategy for category A",
                "references": [],
                "product_category_node_id": category1_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy1_id = strat1_response.json()["node_id"]

        strat2_response = await authenticated_client.post(
            f"{base_url}/brand-awareness-strategies",
            json={
                "description": "Strategy for category B",
                "references": [],
                "product_category_node_id": category2_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy2_id = strat2_response.json()["node_id"]

        # List strategies filtered by category1
        list_response = await authenticated_client.get(
            f"{base_url}/brand-awareness-strategies?product_category_node_id={category1_id}"
        )
        assert list_response.status_code == 200
        strategies = list_response.json()

        # Verify only strategy1 is returned
        assert strategies["total_count"] == 1
        assert strategies["strategies"][0]["node_id"] == strategy1_id

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/brand-awareness-strategies/{strategy1_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/brand-awareness-strategies/{strategy2_id}"
        )
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category1_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category2_id}"
        )


class TestCascadeDeletionCustomerProfile:
    """Integration tests for cascade deletion when CustomerProfile is deleted."""

    @pytest.mark.asyncio
    async def test_delete_customer_profile_cascades_all_strategies(
        self, authenticated_client
    ):
        """Test deleting CustomerProfile cascades to all 5 strategy types across multiple categories."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 2 categories
        cat1_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Category 1", "description": "First category"},
        )
        category1_id = cat1_response.json()["node_id"]

        cat2_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Category 2", "description": "Second category"},
        )
        category2_id = cat2_response.json()["node_id"]

        # Create 1 profile
        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Cascade Test Profile",
                "narrative": "Profile to be deleted",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create strategies for category1 + profile
        strategy_ids = []
        for strategy_type, endpoint in [
            ("problem-awareness", "problem-awareness-strategies"),
            ("brand-awareness", "brand-awareness-strategies"),
            ("consideration", "consideration-strategies"),
            ("conversion", "conversion-strategies"),
            ("loyalty", "loyalty-strategies"),
        ]:
            response = await authenticated_client.post(
                f"{base_url}/{endpoint}",
                json={
                    "description": f"{strategy_type} for cat1",
                    "references": [],
                    "product_category_node_id": category1_id,
                    "customer_profile_node_id": profile_id,
                },
            )
            assert response.status_code == 200
            strategy_ids.append((endpoint, response.json()["node_id"]))

        # Create strategies for category2 + profile
        for strategy_type, endpoint in [
            ("problem-awareness", "problem-awareness-strategies"),
            ("brand-awareness", "brand-awareness-strategies"),
        ]:
            response = await authenticated_client.post(
                f"{base_url}/{endpoint}",
                json={
                    "description": f"{strategy_type} for cat2",
                    "references": [],
                    "product_category_node_id": category2_id,
                    "customer_profile_node_id": profile_id,
                },
            )
            assert response.status_code == 200
            strategy_ids.append((endpoint, response.json()["node_id"]))

        # Delete the CustomerProfile
        delete_response = await authenticated_client.delete(
            f"{base_url}/customer-profiles/{profile_id}"
        )
        assert delete_response.status_code == 200

        # Verify all strategies are deleted (cascade)
        for endpoint, strategy_id in strategy_ids:
            get_response = await authenticated_client.get(
                f"{base_url}/{endpoint}/{strategy_id}"
            )
            assert get_response.status_code == 404

        # Cleanup categories
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category1_id}"
        )
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category2_id}"
        )

    @pytest.mark.asyncio
    async def test_verify_neo4j_nodes_deleted_after_cascade(self, authenticated_client):
        """Test that Neo4j nodes are actually deleted (query returns empty)."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create minimal setup
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Neo4j Test Cat", "description": "Test"},
        )
        category_id = cat_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Neo4j Test Profile",
                "narrative": "Test",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create one strategy
        strat_response = await authenticated_client.post(
            f"{base_url}/loyalty-strategies",
            json={
                "description": "Test loyalty",
                "references": [],
                "product_category_node_id": category_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy_id = strat_response.json()["node_id"]

        # Delete profile (should cascade)
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")

        # Query Neo4j - strategy should be gone
        get_strategy_response = await authenticated_client.get(
            f"{base_url}/loyalty-strategies/{strategy_id}"
        )
        assert get_strategy_response.status_code == 404

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )


class TestCascadeDeletionProductCategory:
    """Integration tests for cascade deletion when ProductCategory is deleted."""

    @pytest.mark.asyncio
    async def test_delete_product_category_cascades_linked_strategies(
        self, authenticated_client
    ):
        """Test deleting ProductCategory cascades to all linked strategies."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create category and profile
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Category to Delete", "description": "Test"},
        )
        category_id = cat_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Profile for Cat Delete Test",
                "narrative": "Test",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create 3 strategies
        strategy_ids = []
        for endpoint in [
            "problem-awareness-strategies",
            "consideration-strategies",
            "conversion-strategies",
        ]:
            response = await authenticated_client.post(
                f"{base_url}/{endpoint}",
                json={
                    "description": "Test strategy",
                    "references": [],
                    "product_category_node_id": category_id,
                    "customer_profile_node_id": profile_id,
                },
            )
            strategy_ids.append((endpoint, response.json()["node_id"]))

        # Delete the ProductCategory
        delete_response = await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )
        assert delete_response.status_code == 200

        # Verify strategies are deleted
        for endpoint, strategy_id in strategy_ids:
            get_response = await authenticated_client.get(
                f"{base_url}/{endpoint}/{strategy_id}"
            )
            assert get_response.status_code == 404

        # Cleanup profile
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")

    @pytest.mark.asyncio
    async def test_verify_is_marketed_to_relationships_removed(
        self, authenticated_client
    ):
        """Test that IS_MARKETED_TO relationships are removed after category deletion."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create category and profile
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Relationship Test Cat", "description": "Test"},
        )
        category_id = cat_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Relationship Test Profile",
                "narrative": "Test",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create strategy (which creates IS_MARKETED_TO relationship)
        strat_response = await authenticated_client.post(
            f"{base_url}/problem-awareness-strategies",
            json={
                "description": "Test",
                "references": [],
                "product_category_node_id": category_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy_id = strat_response.json()["node_id"]

        # Delete category
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category_id}"
        )

        # Strategy should be gone
        get_response = await authenticated_client.get(
            f"{base_url}/problem-awareness-strategies/{strategy_id}"
        )
        assert get_response.status_code == 404

        # Cleanup
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")

    @pytest.mark.asyncio
    async def test_strategies_for_other_categories_remain_intact(
        self, authenticated_client
    ):
        """Test that strategies for other categories remain after deleting one category."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create 2 categories and 1 profile
        cat1_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Keep Category", "description": "Should remain"},
        )
        category1_id = cat1_response.json()["node_id"]

        cat2_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Delete Category", "description": "Will be deleted"},
        )
        category2_id = cat2_response.json()["node_id"]

        prof_response = await authenticated_client.post(
            f"{base_url}/customer-profiles",
            json={
                "display_name": "Multi-Category Profile",
                "narrative": "Used by both",
                "references": [],
            },
        )
        profile_id = prof_response.json()["node_id"]

        # Create strategy for category1
        strat1_response = await authenticated_client.post(
            f"{base_url}/loyalty-strategies",
            json={
                "description": "Keep this strategy",
                "references": [],
                "product_category_node_id": category1_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy1_id = strat1_response.json()["node_id"]

        # Create strategy for category2
        strat2_response = await authenticated_client.post(
            f"{base_url}/loyalty-strategies",
            json={
                "description": "Delete this strategy",
                "references": [],
                "product_category_node_id": category2_id,
                "customer_profile_node_id": profile_id,
            },
        )
        strategy2_id = strat2_response.json()["node_id"]

        # Delete category2
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category2_id}"
        )

        # Strategy1 should still exist
        get_strat1_response = await authenticated_client.get(
            f"{base_url}/loyalty-strategies/{strategy1_id}"
        )
        assert get_strat1_response.status_code == 200

        # Strategy2 should be deleted
        get_strat2_response = await authenticated_client.get(
            f"{base_url}/loyalty-strategies/{strategy2_id}"
        )
        assert get_strat2_response.status_code == 404

        # Cleanup
        await authenticated_client.delete(
            f"{base_url}/loyalty-strategies/{strategy1_id}"
        )
        await authenticated_client.delete(f"{base_url}/customer-profiles/{profile_id}")
        await authenticated_client.delete(
            f"{base_url}/product-categories/{category1_id}"
        )
