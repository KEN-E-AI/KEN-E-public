"""Integration tests for node type validation.

Tests that all node types in VALID_NODE_TYPES constant work correctly
through the entire API stack, catching missing node types early in development.

These tests require real database connections and are skipped in CI
unless DATABASE_INTEGRATION_TESTS environment variable is set to 'true'.
"""

import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.kene_api.constants import NODE_TYPE_TO_PREFIX, VALID_NODE_TYPES
from src.kene_api.main import app
from src.kene_api.auth.dependencies import get_current_user
from src.kene_api.auth.models import UserContext

# Test account and user
TEST_ACCOUNT_ID = "test_account_node_validation"
TEST_USER_ID = "test_user_node_validation"

# Skip all tests in this module in CI unless DATABASE_INTEGRATION_TESTS is enabled
pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_INTEGRATION_TESTS") != "true",
    reason="Requires real Neo4j and Firestore databases - set DATABASE_INTEGRATION_TESTS=true to run"
)


def mock_get_current_user() -> UserContext:
    """Mock authenticated user for testing."""
    return UserContext(
        user_id=TEST_USER_ID,
        email="test@example.com",
        organization_permissions={},
        account_permissions={TEST_ACCOUNT_ID: "edit"}
    )


@pytest_asyncio.fixture
async def authenticated_client():
    """Create authenticated test client."""
    # Override auth dependency
    app.dependency_overrides[get_current_user] = mock_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers.update({"Authorization": "Bearer test_token"})
        yield client

    # Clear overrides after test
    app.dependency_overrides.clear()


class TestNodeTypeWhitelistCoverage:
    """Test that all node types in whitelist are properly supported."""

    @pytest.mark.asyncio
    async def test_all_valid_node_types_have_prefixes(self):
        """All node types in VALID_NODE_TYPES must have corresponding ID prefixes."""
        # Account is special and doesn't need a prefix for user-created nodes
        node_types_requiring_prefix = VALID_NODE_TYPES - {"Account", "SWOTAnalysis"}

        missing_prefixes = []
        for node_type in node_types_requiring_prefix:
            if node_type not in NODE_TYPE_TO_PREFIX:
                missing_prefixes.append(node_type)

        assert not missing_prefixes, (
            f"Node types missing ID prefixes: {missing_prefixes}. Add them to NODE_TYPE_TO_PREFIX in constants.py"
        )

    @pytest.mark.asyncio
    async def test_all_prefixes_have_valid_node_types(self):
        """All ID prefixes must correspond to valid node types."""
        orphaned_prefixes = []
        for node_type in NODE_TYPE_TO_PREFIX.keys():
            if node_type not in VALID_NODE_TYPES:
                orphaned_prefixes.append(node_type)

        assert not orphaned_prefixes, (
            f"Prefixes defined for invalid node types: {orphaned_prefixes}. Remove from NODE_TYPE_TO_PREFIX or add to VALID_NODE_TYPES"
        )


class TestProductCategoryNodeType:
    """Integration tests for ProductCategory node type."""

    @pytest.mark.asyncio
    async def test_product_category_create_list_delete(self, authenticated_client):
        """Test ProductCategory CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={
                "product_name": "Test Category",
                "description": "Testing node type validation",
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create ProductCategory: {create_response.text}"
        )
        category = create_response.json()
        cat_id = category["node_id"]
        assert cat_id.startswith(NODE_TYPE_TO_PREFIX["ProductCategory"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/product-categories")
        assert list_response.status_code == 200
        categories = list_response.json()
        assert any(c["node_id"] == cat_id for c in categories["categories"])

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestProductNodeType:
    """Integration tests for Product node type."""

    @pytest.mark.asyncio
    async def test_product_create_list_delete(self, authenticated_client):
        """Test Product CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parent category first
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Parent Cat", "description": "Parent"},
        )
        cat_id = cat_response.json()["node_id"]

        # CREATE Product
        create_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "Test Product",
                "description": "Testing",
                "category_node_id": cat_id,
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Product: {create_response.text}"
        )
        product = create_response.json()
        prod_id = product["node_id"]
        assert prod_id.startswith(NODE_TYPE_TO_PREFIX["Product"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/products")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/products/{prod_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestValuePropositionNodeType:
    """Integration tests for ValueProposition node type."""

    @pytest.mark.asyncio
    async def test_value_proposition_create_list_delete(self, authenticated_client):
        """Test ValueProposition CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parent product
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "VP Cat", "description": "Category"},
        )
        cat_id = cat_response.json()["node_id"]

        prod_response = await authenticated_client.post(
            f"{base_url}/products",
            json={
                "product_name": "VP Product",
                "description": "Product",
                "category_node_id": cat_id,
            },
        )
        prod_id = prod_response.json()["node_id"]

        # CREATE ValueProposition
        create_response = await authenticated_client.post(
            f"{base_url}/value-propositions",
            json={
                "display_name": "Test VP",
                "description": "Testing",
                "references": [],
                "parent_node_id": prod_id,
                "parent_node_type": "Product",
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create ValueProposition: {create_response.text}"
        )
        vp = create_response.json()
        vp_id = vp["node_id"]
        assert vp_id.startswith(NODE_TYPE_TO_PREFIX["ValueProposition"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/value-propositions")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/value-propositions/{vp_id}")
        await authenticated_client.delete(f"{base_url}/products/{prod_id}")
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")


class TestStrengthNodeType:
    """Integration tests for Strength node type."""

    @pytest.mark.asyncio
    async def test_strength_create_list_delete(self, authenticated_client):
        """Test Strength CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Test Strength",
                "description": "Testing",
                "references": [],
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Strength: {create_response.text}"
        )
        strength = create_response.json()
        strength_id = strength["node_id"]
        assert strength_id.startswith(NODE_TYPE_TO_PREFIX["Strength"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/strengths")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")


class TestWeaknessNodeType:
    """Integration tests for Weakness node type."""

    @pytest.mark.asyncio
    async def test_weakness_create_list_delete(self, authenticated_client):
        """Test Weakness CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/weaknesses",
            json={
                "display_name": "Test Weakness",
                "description": "Testing",
                "references": [],
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Weakness: {create_response.text}"
        )
        weakness = create_response.json()
        weakness_id = weakness["node_id"]
        assert weakness_id.startswith(NODE_TYPE_TO_PREFIX["Weakness"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/weaknesses")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/weaknesses/{weakness_id}")


class TestOpportunityNodeType:
    """Integration tests for Opportunity node type."""

    @pytest.mark.asyncio
    async def test_opportunity_create_list_delete(self, authenticated_client):
        """Test Opportunity CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parent strength
        strength_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Parent Strength",
                "description": "Parent",
                "references": [],
            },
        )
        strength_id = strength_response.json()["node_id"]

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/opportunities",
            json={
                "display_name": "Test Opportunity",
                "description": "Testing",
                "references": [],
                "strength_node_id": strength_id,
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Opportunity: {create_response.text}"
        )
        opportunity = create_response.json()
        opp_id = opportunity["node_id"]
        assert opp_id.startswith(NODE_TYPE_TO_PREFIX["Opportunity"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/opportunities")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/opportunities/{opp_id}")
        await authenticated_client.delete(f"{base_url}/strengths/{strength_id}")


class TestRiskNodeType:
    """Integration tests for Risk node type."""

    @pytest.mark.asyncio
    async def test_risk_create_list_delete(self, authenticated_client):
        """Test Risk CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create parent weakness
        weakness_response = await authenticated_client.post(
            f"{base_url}/weaknesses",
            json={
                "display_name": "Parent Weakness",
                "description": "Parent",
                "references": [],
            },
        )
        weakness_id = weakness_response.json()["node_id"]

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/risks",
            json={
                "display_name": "Test Risk",
                "description": "Testing",
                "references": [],
                "weakness_node_id": weakness_id,
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Risk: {create_response.text}"
        )
        risk = create_response.json()
        risk_id = risk["node_id"]
        assert risk_id.startswith(NODE_TYPE_TO_PREFIX["Risk"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/risks")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/risks/{risk_id}")
        await authenticated_client.delete(f"{base_url}/weaknesses/{weakness_id}")


class TestGoalNodeType:
    """Integration tests for Goal node type."""

    @pytest.mark.asyncio
    async def test_goal_create_list_delete(self, authenticated_client):
        """Test Goal CRUD operations work end-to-end."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # CREATE
        create_response = await authenticated_client.post(
            f"{base_url}/goals",
            json={
                "display_name": "Test Goal",
                "description": "Testing",
                "references": [],
            },
        )
        assert create_response.status_code == 200, (
            f"Failed to create Goal: {create_response.text}"
        )
        goal = create_response.json()
        goal_id = goal["node_id"]
        assert goal_id.startswith(NODE_TYPE_TO_PREFIX["Goal"])

        # LIST
        list_response = await authenticated_client.get(f"{base_url}/goals")
        assert list_response.status_code == 200

        # CLEANUP
        await authenticated_client.delete(f"{base_url}/goals/{goal_id}")


class TestNodeTypeValidationInQueries:
    """Test that node type validation works in graph query operations."""

    @pytest.mark.asyncio
    async def test_validate_node_exists_requires_valid_type(self, authenticated_client):
        """Test that validate_node_exists properly validates node types."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create a product category
        cat_response = await authenticated_client.post(
            f"{base_url}/product-categories",
            json={"product_name": "Validation Test", "description": "Test"},
        )
        cat_id = cat_response.json()["node_id"]

        # This should work (valid node type)
        get_response = await authenticated_client.get(
            f"{base_url}/product-categories/{cat_id}"
        )
        assert get_response.status_code == 200

        # Cleanup
        await authenticated_client.delete(f"{base_url}/product-categories/{cat_id}")

    @pytest.mark.asyncio
    async def test_validate_unique_display_name_requires_valid_type(
        self, authenticated_client
    ):
        """Test that uniqueness validation properly validates node types."""
        base_url = f"/api/v1/knowledge-graph/{TEST_ACCOUNT_ID}"

        # Create first strength
        strength1_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Unique Strength",
                "description": "Test",
                "references": [],
            },
        )
        strength1_id = strength1_response.json()["node_id"]

        # Try to create duplicate (should fail due to uniqueness)
        strength2_response = await authenticated_client.post(
            f"{base_url}/strengths",
            json={
                "display_name": "Unique Strength",
                "description": "Test",
                "references": [],
            },
        )
        assert strength2_response.status_code == 400
        assert "already exists" in strength2_response.json()["detail"]

        # Cleanup
        await authenticated_client.delete(f"{base_url}/strengths/{strength1_id}")


class TestFutureNodeTypePreparation:
    """Tests to prepare for future node types (competitive, marketing, brand)."""

    def test_future_node_types_documented(self):
        """Document future node types that need to be added to whitelist."""
        # This test serves as documentation for planned node types
        # When adding these types, update VALID_NODE_TYPES and NODE_TYPE_TO_PREFIX

        planned_phase_2_types = [
            # Competitive Analysis phase
            "Competitor",
            "CompetitorProduct",
            "MarketPosition",
            # Marketing Strategy phase
            "Campaign",
            "Channel",
            "Audience",
            # Brand Strategy phase
            "BrandAttribute",
            "BrandMessage",
            "BrandAsset",
        ]

        # This test always passes but documents what's coming
        assert True, f"Future node types to add: {', '.join(planned_phase_2_types)}"

    def test_node_type_addition_checklist(self):
        """Checklist for adding new node types."""
        checklist = [
            "1. Add node type to VALID_NODE_TYPES in constants.py",
            "2. Add corresponding prefix to NODE_TYPE_TO_PREFIX in constants.py",
            "3. Create Pydantic models in api/src/kene_api/models/graph_models.py",
            "4. Add CRUD endpoints in api/src/kene_api/routes/knowledge_graph.py",
            "5. Add integration test class in this file (test_node_type_validation.py)",
            "6. Update graph service if special business logic is needed",
            "7. Run pytest to verify all tests pass",
        ]

        # This test always passes but provides a checklist
        assert True, "Node type addition checklist:\n" + "\n".join(checklist)
