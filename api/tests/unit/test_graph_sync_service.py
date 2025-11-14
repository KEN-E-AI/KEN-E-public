"""Unit tests for GraphSyncService.

Tests generic CRUD operations for all node types using mocked dependencies.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from src.kene_api.exceptions import NodeNotFoundException
from src.kene_api.models.graph_models import (
    OpportunityCreate,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    StrengthCreate,
)
from src.kene_api.services.graph_sync_service import GraphSyncService
from src.kene_api.services.graph_validation_service import GraphValidationService


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service."""
    service = AsyncMock()
    service.execute_query = AsyncMock()
    service.execute_write_query = AsyncMock()
    service.execute_write_operation = AsyncMock()
    return service


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service."""
    service = Mock()
    service.get_document = Mock(return_value={})  # Return mutable dict by default
    service.update_document = Mock(return_value=True)
    return service


@pytest.fixture
def mock_validation_service():
    """Mock GraphValidationService."""
    service = AsyncMock()
    # Set up default return values for validation methods
    service.validate_account_exists = AsyncMock(return_value=True)
    service.validate_node_exists = AsyncMock(return_value=True)
    service.validate_non_empty_string = Mock(return_value=(True, ""))
    service.validate_url_format = Mock(return_value=True)
    service.validate_unique_product_category_name = AsyncMock(return_value=(True, ""))
    service.validate_unique_product_name = AsyncMock(return_value=(True, ""))
    service.validate_unique_display_name = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_product_category = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_product = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_strength = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_weakness = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_competitor = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_competitor_strength = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_competitor_weakness = AsyncMock(return_value=(True, ""))
    service.validate_can_delete_substitute_product = AsyncMock(return_value=(True, ""))
    service.get_or_create_swot_hub = AsyncMock(return_value="swot_test123_abc")
    return service


@pytest.fixture
def graph_sync_service(
    mock_neo4j_service, mock_firestore_service, mock_validation_service
):
    """Create GraphSyncService with mocked dependencies."""
    return GraphSyncService(
        mock_neo4j_service, mock_firestore_service, mock_validation_service
    )


# ==================== ProductCategory Tests ====================


class TestProductCategoryOperations:
    """Tests for ProductCategory CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_product_category_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful product category creation."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category", description="Test description"
        )

        # Mock Neo4j create
        expected_node_id = "productcat_test123_abc123"
        expected_node = {
            "node_id": expected_node_id,
            "product_name": "Test Category",
            "description": "Test description",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {
            "product_portfolio": [],
            "updated_at": datetime(2025, 1, 1),
        }

        # Act
        result = await graph_sync_service.create_product_category(
            account_id, category_create, user_id
        )

        # Assert
        assert result.product_name == "Test Category"
        assert result.description == "Test description"
        assert result.account_id == account_id
        assert result.node_id == expected_node_id

        # Verify validations were called
        mock_validation_service.validate_non_empty_string.assert_called()
        mock_validation_service.validate_unique_product_category_name.assert_called_once_with(
            account_id, "Test Category"
        )

        # Verify Neo4j was called
        assert mock_neo4j_service.execute_write_query.call_count >= 1

        # Verify Firestore was synced
        mock_firestore_service.update_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_category_account_not_found(
        self, graph_sync_service, mock_validation_service, mock_neo4j_service
    ):
        """Test creation fails when account doesn't exist."""
        # Arrange
        account_id = "acc_nonexistent"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category", description="Test description"
        )

        # Mock account validation to return False (account not found)
        mock_validation_service.validate_account_exists.return_value = False

        # Act & Assert
        with pytest.raises(NodeNotFoundException, match=r"Account.*not found"):
            await graph_sync_service.create_product_category(
                account_id, category_create, user_id
            )

    @pytest.mark.asyncio
    async def test_create_product_category_firestore_sync_fails_rolls_back(
        self, graph_sync_service, mock_neo4j_service, mock_firestore_service
    ):
        """Test rollback when Firestore sync fails."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category", description="Test description"
        )

        # Mock account validation
        mock_neo4j_service.execute_query.return_value = [
            {"acc": {"account_id": account_id}}
        ]

        # Mock Neo4j create succeeds
        expected_node = {
            "node_id": "productcat_test123_abc123",
            "product_name": "Test Category",
            "description": "Test description",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]

        # Mock Firestore sync fails
        mock_firestore_service.get_document.side_effect = Exception("Firestore error")

        # Act & Assert
        with pytest.raises(Exception, match="Graph sync failed during create"):
            await graph_sync_service.create_product_category(
                account_id, category_create, user_id
            )

        # Verify rollback was attempted (delete node)
        mock_neo4j_service.execute_write_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_product_category_success(
        self, graph_sync_service, mock_neo4j_service, mock_firestore_service
    ):
        """Test successful product category update."""
        # Arrange
        account_id = "acc_test123"
        node_id = "productcat_test123_abc123"
        user_id = "user_test456"

        updates = ProductCategoryUpdate(
            product_name="Updated Category", description="Updated description"
        )

        # Mock existing node
        existing_node = {
            "node_id": node_id,
            "product_name": "Old Category",
            "description": "Old description",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        # Mock Neo4j update
        updated_node = {
            **existing_node,
            "product_name": "Updated Category",
            "description": "Updated description",
            "last_modified": datetime(2025, 1, 2),
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {
            "product_portfolio": [
                {"node_id": node_id, "category_name": "Old Category", "products": []}
            ],
            "updated_at": datetime(2025, 1, 1),
        }

        # Act
        result = await graph_sync_service.update_product_category(
            account_id, node_id, updates, user_id
        )

        # Assert
        assert result.product_name == "Updated Category"
        assert result.description == "Updated description"

        # Verify both Neo4j and Firestore were updated
        assert mock_neo4j_service.execute_write_query.call_count >= 1
        mock_firestore_service.update_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_product_category_with_products_fails(
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
    ):
        """Test deletion fails when category has dependent products."""
        # Arrange
        from src.kene_api.exceptions import NodeHasDependenciesException

        account_id = "acc_test123"
        node_id = "productcat_test123_abc123"
        user_id = "user_test456"

        # Mock existing node
        existing_node = {
            "node_id": node_id,
            "product_name": "Test Category",
            "description": "Test description",
            "account_id": account_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        # Mock validation returns failure
        mock_validation_service.validate_can_delete_product_category.return_value = (
            False,
            "Cannot delete ProductCategory with 3 existing products",
        )

        # Act & Assert
        with pytest.raises(NodeHasDependenciesException) as exc_info:
            await graph_sync_service.delete_product_category(
                account_id, node_id, user_id
            )

        assert "3" in str(exc_info.value)
        assert "existing products" in str(exc_info.value)


# ==================== Product Tests ====================


class TestProductOperations:
    """Tests for Product CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_product_success(
        self, graph_sync_service, mock_neo4j_service, mock_firestore_service
    ):
        """Test successful product creation."""
        # Arrange
        account_id = "acc_test123"
        category_node_id = "productcat_test123_xyz789"
        user_id = "user_test456"
        product_create = ProductCreate(
            product_name="Test Product",
            description="Product description",
            references=["https://example.com"],
            product_detail_page="https://product.com",
            category_node_id=category_node_id,
        )

        # Mock validations (account + parent category exists)
        mock_neo4j_service.execute_query.side_effect = [
            [{"acc": {"account_id": account_id}}],  # Account exists
            [{"cat": {"node_id": category_node_id}}],  # Category exists
        ]

        # Mock Neo4j create
        expected_node_id = "prod_test123_def456"
        expected_node = {
            "node_id": expected_node_id,
            "product_name": "Test Product",
            "description": "Product description",
            "references": ["https://example.com"],
            "product_detail_page": "https://product.com",
            "category_node_id": category_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {
            "product_portfolio": [],
            "updated_at": datetime(2025, 1, 1),
        }

        # Act
        result = await graph_sync_service.create_product(
            account_id, product_create, user_id
        )

        # Assert
        assert result.product_name == "Test Product"
        assert result.category_node_id == category_node_id
        assert result.node_id == expected_node_id

    @pytest.mark.asyncio
    async def test_create_product_parent_category_not_found(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test creation fails when parent category doesn't exist."""
        # Arrange
        account_id = "acc_test123"
        category_node_id = "productcat_nonexistent"
        user_id = "user_test456"
        product_create = ProductCreate(
            product_name="Test Product",
            description="Product description",
            references=[],
            product_detail_page=None,
            category_node_id=category_node_id,
        )

        # Mock account exists but category doesn't
        mock_neo4j_service.execute_query.side_effect = [
            [{"acc": {"account_id": account_id}}],  # Account exists
            [],  # Category doesn't exist
        ]

        # Act & Assert
        with pytest.raises(ValueError, match=r"Parent ProductCategory .* not found"):
            await graph_sync_service.create_product(account_id, product_create, user_id)


# ==================== SWOT Tests ====================


class TestStrengthOperations:
    """Tests for Strength CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_strength_auto_creates_swot_hub(
        self, graph_sync_service, mock_neo4j_service, mock_firestore_service
    ):
        """Test that strength creation auto-creates SWOT hub if doesn't exist."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        strength_create = StrengthCreate(
            display_name="Strong Brand",
            description="Well-known brand",
            references=["https://example.com"],
        )

        # Mock SWOT hub doesn't exist, so it will be created
        swot_node_id = "swot_test123_hub123"
        mock_neo4j_service.execute_query.side_effect = [
            [],  # SWOT hub doesn't exist (first call in get_or_create_swot_hub)
            [{"acc": {"account_id": account_id}}],  # Account exists
            [
                {"swot": {"node_id": swot_node_id}}
            ],  # SWOT hub exists after creation (validate_node_exists)
        ]

        # Mock SWOT hub creation
        mock_neo4j_service.execute_write_query.side_effect = [
            [{"node": {"node_id": swot_node_id}}],  # SWOT hub created
            [
                {
                    "node": {
                        "node_id": "strength_test123_str123",
                        "display_name": "Strong Brand",
                        "description": "Well-known brand",
                        "references": ["https://example.com"],
                        "account_id": account_id,
                        "created_time": datetime(2025, 1, 1),
                        "last_modified": datetime(2025, 1, 1),
                        "created_by": user_id,
                        "last_modified_by": user_id,
                        "embedding": None,
                    }
                }
            ],  # Strength created
        ]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {
            "swot_analysis": {"strengths_and_opportunities": []},
            "updated_at": datetime(2025, 1, 1),
        }

        # Act
        result = await graph_sync_service.create_strength(
            account_id, strength_create, user_id
        )

        # Assert
        assert result.display_name == "Strong Brand"
        assert mock_neo4j_service.execute_write_query.call_count == 2  # Hub + Strength


class TestOpportunityOperations:
    """Tests for Opportunity CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_opportunity_requires_parent_strength(
        self, graph_sync_service, mock_neo4j_service, mock_firestore_service
    ):
        """Test that opportunity creation requires a parent strength."""
        # Arrange
        account_id = "acc_test123"
        strength_node_id = "strength_test123_str123"
        user_id = "user_test456"
        opportunity_create = OpportunityCreate(
            display_name="Market Expansion",
            description="Expand to new markets",
            references=[],
            strength_node_id=strength_node_id,
        )

        # Mock validations
        mock_neo4j_service.execute_query.side_effect = [
            [{"acc": {"account_id": account_id}}],  # Account exists
            [{"strength": {"node_id": strength_node_id}}],  # Strength exists
        ]

        # Mock Neo4j create
        expected_node = {
            "node_id": "opportunity_test123_opp123",
            "display_name": "Market Expansion",
            "description": "Expand to new markets",
            "references": [],
            "strength_node_id": strength_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {
            "swot_analysis": {"strengths_and_opportunities": []},
            "updated_at": datetime(2025, 1, 1),
        }

        # Act
        result = await graph_sync_service.create_opportunity(
            account_id, opportunity_create, user_id
        )

        # Assert
        assert result.display_name == "Market Expansion"
        assert result.strength_node_id == strength_node_id


# ==================== Helper Methods Tests ====================


class TestHelperMethods:
    """Tests for service helper methods."""

    def test_generate_node_id_creates_correct_prefixes(self, graph_sync_service):
        """Test that node IDs are generated with correct prefixes."""
        account_id = "acc_test123"

        # Test various node types
        product_id = graph_sync_service._generate_node_id("Product", account_id)
        assert product_id.startswith("prod_acc_test123_")

        category_id = graph_sync_service._generate_node_id(
            "ProductCategory", account_id
        )
        assert category_id.startswith("productcat_acc_test123_")

        strength_id = graph_sync_service._generate_node_id("Strength", account_id)
        assert strength_id.startswith("strength_acc_test123_")

        goal_id = graph_sync_service._generate_node_id("Goal", account_id)
        assert goal_id.startswith("goal_acc_test123_")

    def test_get_relationship_config_returns_correct_mappings(self, graph_sync_service):
        """Test that relationship configs are correct."""
        # Product -> ProductCategory
        config = graph_sync_service._get_relationship_config(
            "Product", "ProductCategory"
        )
        assert config is not None
        assert config["from_parent"] == "INCLUDES_PRODUCT"

        # Strength -> SWOTAnalysis
        config = graph_sync_service._get_relationship_config("Strength", "SWOTAnalysis")
        assert config is not None
        assert config["from_parent"] == "HAS_STRENGTH"

        # Opportunity -> Strength
        config = graph_sync_service._get_relationship_config("Opportunity", "Strength")
        assert config is not None
        assert config["from_parent"] == "CREATES"

        # Invalid combination
        config = graph_sync_service._get_relationship_config("Product", "Strength")
        assert config is None


# ==================== List and Get Tests ====================


class TestListAndGetOperations:
    """Tests for generic list and get operations."""

    @pytest.mark.asyncio
    async def test_list_nodes_without_parent_filter(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test listing all nodes of a type."""
        # Arrange
        account_id = "acc_test123"

        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {"node_id": "prod_1", "product_name": "Product 1"},
                "account_id": account_id,
            },
            {
                "node": {"node_id": "prod_2", "product_name": "Product 2"},
                "account_id": account_id,
            },
        ]

        # Act
        result = await graph_sync_service.list_nodes(account_id, "Product")

        # Assert
        assert len(result) == 2
        assert result[0]["node_id"] == "prod_1"
        assert result[1]["node_id"] == "prod_2"

    @pytest.mark.asyncio
    async def test_list_nodes_with_parent_filter(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test listing nodes filtered by parent."""
        # Arrange
        account_id = "acc_test123"
        parent_node_id = "productcat_123"

        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": "prod_1",
                    "product_name": "Product 1",
                    "category_node_id": parent_node_id,
                },
                "account_id": account_id,
            },
        ]

        # Act
        result = await graph_sync_service.list_nodes(
            account_id, "Product", parent_node_id=parent_node_id
        )

        # Assert
        assert len(result) == 1
        assert result[0]["category_node_id"] == parent_node_id

    @pytest.mark.asyncio
    async def test_get_node_returns_node_when_exists(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test getting a specific node."""
        # Arrange
        account_id = "acc_test123"
        node_id = "prod_123"

        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": node_id,
                    "product_name": "Test Product",
                    "account_id": account_id,
                },
                "account_id": account_id,
            }
        ]

        # Act
        result = await graph_sync_service.get_node(account_id, node_id, "Product")

        # Assert
        assert result is not None
        assert result["node_id"] == node_id
        assert result["product_name"] == "Test Product"

    @pytest.mark.asyncio
    async def test_get_node_returns_none_when_not_exists(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test getting a non-existent node."""
        # Arrange
        account_id = "acc_test123"
        node_id = "prod_nonexistent"

        mock_neo4j_service.execute_query.return_value = []

        # Act
        result = await graph_sync_service.get_node(account_id, node_id, "Product")

        # Assert
        assert result is None


# ==================== Competitive Strategy Tests ====================


class TestCompetitorOperations:
    """Tests for Competitor CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_competitor_auto_creates_hub(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating competitor auto-creates CompetitiveEnvironment hub if missing."""
        # Arrange
        from src.kene_api.models.graph_models import CompetitorCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        competitor_create = CompetitorCreate(
            display_name="Test Competitor",
            description="A test competitor company",
            references=["https://example.com/competitor"],
        )

        # Mock list_nodes check for existing CompetitiveEnvironment (returns empty = no hub exists)
        # Then mock hub creation, then competitor creation
        mock_neo4j_service.execute_query.return_value = []  # No existing hub

        # Mock CompetitiveEnvironment creation
        hub_node_id = "competitiveenv_test123_xyz"
        hub_node = {
            "node_id": hub_node_id,
            "description": "Competitive environment for tracking key competitors and market analysis.",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # Mock Competitor creation
        competitor_node_id = "competitor_test123_abc"
        competitor_node = {
            "node_id": competitor_node_id,
            "display_name": "Test Competitor",
            "description": "A test competitor company",
            "references": ["https://example.com/competitor"],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # First call creates hub, second creates competitor
        mock_neo4j_service.execute_write_query.side_effect = [
            [{"node": hub_node}],  # Hub creation
            [{"node": competitor_node}],  # Competitor creation
        ]

        # Mock Firestore sync
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.create_competitor(
            account_id, competitor_create, user_id
        )

        # Assert
        assert result.node_id == competitor_node_id
        assert result.display_name == "Test Competitor"
        assert result.references == ["https://example.com/competitor"]
        # Verify hub was created first
        assert mock_neo4j_service.execute_write_query.call_count == 2

    @pytest.mark.asyncio
    async def test_create_competitor_reuses_existing_hub(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating competitor reuses existing CompetitiveEnvironment hub."""
        # Arrange
        from src.kene_api.models.graph_models import CompetitorCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        competitor_create = CompetitorCreate(
            display_name="Test Competitor",
            description="A test competitor",
            references=[],
        )

        # Mock existing CompetitiveEnvironment
        hub_node_id = "competitiveenv_test123_xyz"
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": hub_node_id,
                    "description": "Existing hub",
                    "account_id": account_id,
                    "created_time": datetime(2025, 1, 1),
                    "last_modified": datetime(2025, 1, 1),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                "account_id": account_id,  # Required by list_nodes query
            }
        ]

        # Mock Competitor creation
        competitor_node = {
            "node_id": "competitor_test123_abc",
            "display_name": "Test Competitor",
            "description": "A test competitor",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [
            {"node": competitor_node}
        ]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.create_competitor(
            account_id, competitor_create, user_id
        )

        # Assert
        assert result.display_name == "Test Competitor"
        # Hub should NOT be created again (only 1 write query for competitor)
        assert mock_neo4j_service.execute_write_query.call_count == 1

    @pytest.mark.asyncio
    async def test_delete_competitor_validates_dependencies(
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
    ):
        """Test deleting competitor with dependencies fails validation."""
        # Arrange
        from src.kene_api.exceptions import NodeHasDependenciesException

        account_id = "acc_test123"
        node_id = "competitor_test123_abc"
        user_id = "user_test456"

        # Mock existing competitor
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": node_id,
                    "display_name": "Test Competitor",
                    "description": "Test",
                    "references": [],
                    "account_id": account_id,
                    "created_time": datetime(2025, 1, 1),
                    "last_modified": datetime(2025, 1, 1),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                "account_id": account_id,  # Required by get_node query
            }
        ]

        # Mock validation failure (has dependent tactics)
        mock_validation_service.validate_can_delete_competitor.return_value = (
            False,
            "Cannot delete Competitor with 3 dependent tactics",
        )

        # Act & Assert
        with pytest.raises(NodeHasDependenciesException) as exc_info:
            await graph_sync_service.delete_competitor(account_id, node_id, user_id)

        assert "3" in str(exc_info.value)
        assert "dependent tactics" in str(exc_info.value)


class TestCompetitorTacticOperations:
    """Tests for CompetitorTactic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_competitor_tactic_validates_parent_exists(
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
    ):
        """Test creating tactic validates competitor exists."""
        # Arrange
        from src.kene_api.models.graph_models import CompetitorTacticCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        competitor_node_id = "competitor_test123_abc"

        tactic_create = CompetitorTacticCreate(
            display_name="Social Media Campaign",
            description="Active social media presence",
            references=[],
            competitor_node_id=competitor_node_id,
        )

        # Mock parent validation (competitor doesn't exist)
        mock_validation_service.validate_node_exists.return_value = False

        # Act & Assert
        with pytest.raises(NodeNotFoundException) as exc_info:
            await graph_sync_service.create_competitor_tactic(
                account_id, tactic_create, user_id
            )

        assert "Competitor" in str(exc_info.value)
        assert competitor_node_id in str(exc_info.value)


class TestCompetitorStrengthOperations:
    """Tests for CompetitorStrength CRUD operations."""

    @pytest.mark.asyncio
    async def test_delete_competitor_strength_blocks_when_risks_exist(
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
    ):
        """Test deleting strength with dependent risks fails."""
        # Arrange
        from src.kene_api.exceptions import NodeHasDependenciesException

        account_id = "acc_test123"
        node_id = "compstrength_test123_abc"
        user_id = "user_test456"

        # Mock existing strength
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": node_id,
                    "display_name": "Strong Brand",
                    "description": "Test",
                    "references": [],
                    "competitor_node_id": "competitor_test123",
                    "account_id": account_id,
                    "created_time": datetime(2025, 1, 1),
                    "last_modified": datetime(2025, 1, 1),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                "account_id": account_id,  # Required by get_node query
            }
        ]

        # Mock validation failure (has dependent risks)
        mock_validation_service.validate_can_delete_competitor_strength.return_value = (
            False,
            "Cannot delete CompetitorStrength with 2 dependent risks",
        )

        # Act & Assert
        with pytest.raises(NodeHasDependenciesException) as exc_info:
            await graph_sync_service.delete_competitor_strength(
                account_id, node_id, user_id
            )

        assert "2" in str(exc_info.value)
        assert "dependent risks" in str(exc_info.value)


class TestCompetitorWeaknessOperations:
    """Tests for CompetitorWeakness CRUD operations."""

    @pytest.mark.asyncio
    async def test_delete_competitor_weakness_blocks_when_opportunities_exist(
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
    ):
        """Test deleting weakness with dependent opportunities fails."""
        # Arrange
        from src.kene_api.exceptions import NodeHasDependenciesException

        account_id = "acc_test123"
        node_id = "compweakness_test123_abc"
        user_id = "user_test456"

        # Mock existing weakness
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": node_id,
                    "display_name": "High Price Point",
                    "description": "Test",
                    "references": [],
                    "competitor_node_id": "competitor_test123",
                    "account_id": account_id,
                    "created_time": datetime(2025, 1, 1),
                    "last_modified": datetime(2025, 1, 1),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                "account_id": account_id,  # Required by get_node query
            }
        ]

        # Mock validation failure (has dependent opportunities)
        mock_validation_service.validate_can_delete_competitor_weakness.return_value = (
            False,
            "Cannot delete CompetitorWeakness with 1 dependent opportunities",
        )

        # Act & Assert
        with pytest.raises(NodeHasDependenciesException) as exc_info:
            await graph_sync_service.delete_competitor_weakness(
                account_id, node_id, user_id
            )

        assert "1" in str(exc_info.value)
        assert "dependent opportunities" in str(exc_info.value)


class TestSubstituteProductOperations:
    """Tests for SubstituteProduct CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_substitute_product_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful substitute product creation."""
        # Arrange
        from src.kene_api.models.graph_models import SubstituteProductCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        competitor_node_id = "competitor_test123_abc"

        product_create = SubstituteProductCreate(
            product_name="Molekule Air Pro",
            description="Commercial air purifier",
            references=["https://molekule.com/air-pro"],
            product_detail_page="https://molekule.com/air-pro",
            competitor_node_id=competitor_node_id,
        )

        # Mock parent exists
        mock_validation_service.validate_node_exists.return_value = True

        # Mock product creation
        expected_node_id = "substitute_test123_abc"
        expected_node = {
            "node_id": expected_node_id,
            "product_name": "Molekule Air Pro",
            "description": "Commercial air purifier",
            "references": ["https://molekule.com/air-pro"],
            "product_detail_page": "https://molekule.com/air-pro",
            "competitor_node_id": competitor_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.create_substitute_product(
            account_id, product_create, user_id
        )

        # Assert
        assert result.node_id == expected_node_id
        assert result.product_name == "Molekule Air Pro"
        assert result.product_detail_page == "https://molekule.com/air-pro"
        assert result.competitor_node_id == competitor_node_id
