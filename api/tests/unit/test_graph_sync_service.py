"""Unit tests for GraphSyncService.

Tests generic CRUD operations for all node types using mocked dependencies.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from src.kene_api.exceptions import NodeNotFoundException, ValidationException
from src.kene_api.models.graph_models import (
    CompetitorCreate,
    CompetitorTacticCreate,
    OpportunityCreate,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    StrengthCreate,
)
from src.kene_api.services.graph_sync_service import GraphSyncService


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
    service.validate_unique_customer_profile_name = AsyncMock(return_value=(True, ""))
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
    @pytest.mark.skip(
        reason="GraphSyncService API changed: delete_product_category now cascades directly instead of blocking via validate_can_delete_product_category"
    )
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
        self, graph_sync_service, mock_neo4j_service, mock_validation_service
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

        # Mock parent category not found
        mock_validation_service.validate_node_exists = AsyncMock(return_value=False)

        # Act & Assert
        with pytest.raises(NodeNotFoundException):
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

        # Mock Strength creation (SWOT hub creation is mocked on validation service)
        mock_neo4j_service.execute_write_query.return_value = [
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
        assert (
            mock_neo4j_service.execute_write_query.call_count == 1
        )  # Strength only (hub via mocked validation)


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
        hub_record = {
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
            "account_id": account_id,
        }
        mock_neo4j_service.execute_query.side_effect = [
            [{"total": 0}],  # count_nodes: below limit
            [hub_record],  # list_nodes: existing hub found
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

    @pytest.mark.asyncio
    async def test_delete_competitor_cascade_removes_monitoring_topic_entry(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that cascade-deleting a competitor removes its entry from monitoring_topics
        Shape B path (accounts/{account_id}/monitoring_topics, document_id='default')."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "competitor_test123_abc"
        other_node_id = "competitor_test123_xyz"

        competitor_node = {
            "node_id": node_id,
            "display_name": "Test Competitor",
            "description": "Test",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # delete_competitor_cascade makes 8 execute_query calls for cascade sub-queries
        # (risks, strengths, opportunities, weaknesses, sub_vps, substitutes, tactics, vps)
        # followed by 1 execute_query call from get_node inside delete_node for the Competitor itself
        mock_neo4j_service.execute_query.side_effect = [
            [],  # 1. risks (from strengths)
            [],  # 2. strengths
            [],  # 3. opportunities (from weaknesses)
            [],  # 4. weaknesses
            [],  # 5. value propositions from substitute products
            [],  # 6. substitute products
            [],  # 7. tactics
            [],  # 8. value propositions directly linked to competitor
            [{"node": competitor_node, "account_id": account_id}],  # 9. get_node check
        ]

        mock_neo4j_service.execute_write_operation.return_value = None

        monitoring_doc = {
            "competitor_entries": [
                {"node_id": node_id, "name": "Test Competitor", "keywords": ["kw1"]},
                {
                    "node_id": other_node_id,
                    "name": "Other Competitor",
                    "keywords": ["kw2"],
                },
            ]
        }
        monitoring_collection = f"accounts/{account_id}/monitoring_topics"

        # Route get_document responses by collection so the test is resilient to
        # refactors that change the number or order of other Firestore reads.
        def get_document_side_effect(collection, document_id):
            if collection == monitoring_collection:
                return monitoring_doc
            return {}

        mock_firestore_service.get_document.side_effect = get_document_side_effect

        # Act
        await graph_sync_service.delete_competitor(
            account_id, node_id, user_id, cascade=True
        )

        # Assert — get_document was called for the monitoring_topics Shape B path
        mock_firestore_service.get_document.assert_any_call(
            collection=monitoring_collection,
            document_id="default",
        )

        # Assert — update_document was called for the monitoring_topics Shape B path
        monitoring_update_calls = [
            call
            for call in mock_firestore_service.update_document.call_args_list
            if call.kwargs.get("collection") == monitoring_collection
        ]
        assert len(monitoring_update_calls) == 1, (
            "Expected exactly one update_document call for monitoring_topics"
        )

        # Assert — the deleted competitor's entry was removed; the other entry remains
        update_call = monitoring_update_calls[0]
        remaining_entries = update_call.kwargs["data"]["competitor_entries"]
        assert len(remaining_entries) == 1
        assert remaining_entries[0]["node_id"] == other_node_id


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

        # Mock count_nodes to return 0 (below limit) then parent validation fails
        mock_neo4j_service.execute_query = AsyncMock(return_value=[{"total": 0}])
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

        # Mock count_nodes to return 0 (below limit), then parent exists
        mock_neo4j_service.execute_query = AsyncMock(return_value=[{"total": 0}])
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


class TestCompetitorLimits:
    """Unit tests for competitor limit validation."""

    @pytest.mark.asyncio
    async def test_competitor_limit_validation_at_limit(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that ValidationException is raised when at competitor limit."""
        # Arrange
        account_id = "acc_test"
        user_id = "user_test"
        competitor_data = CompetitorCreate(
            display_name="Test Competitor",
            description="Test description",
            references=[],
        )

        # Mock count_nodes to return 5 (at limit)
        mock_neo4j_service.execute_query = AsyncMock(return_value=[{"total": 5}])

        # Mock validation services
        mock_validation_service.validate_non_empty_string = Mock(
            return_value=(True, None)
        )
        mock_validation_service.validate_account_exists = AsyncMock(return_value=True)

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            await graph_sync_service.create_competitor(
                account_id=account_id, competitor=competitor_data, user_id=user_id
            )

        assert "Maximum of 5 competitors" in str(exc_info.value)
        assert exc_info.value.field_name == "account_id"

    @pytest.mark.asyncio
    async def test_competitor_tactic_limit_validation_at_limit(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that ValidationException is raised when at tactic limit per competitor."""
        # Arrange
        account_id = "acc_test"
        user_id = "user_test"
        competitor_node_id = "competitor_acc_test_abc123"
        tactic_data = CompetitorTacticCreate(
            display_name="Test Tactic",
            description="Test description",
            references=[],
            competitor_node_id=competitor_node_id,
        )

        # Mock count_nodes to return 5 (at limit)
        mock_neo4j_service.execute_query = AsyncMock(return_value=[{"total": 5}])

        # Mock validation services
        mock_validation_service.validate_non_empty_string = Mock(
            return_value=(True, None)
        )

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            await graph_sync_service.create_competitor_tactic(
                account_id=account_id, tactic=tactic_data, user_id=user_id
            )

        assert "Maximum of 5 tactics" in str(exc_info.value)
        assert exc_info.value.field_name == "competitor_node_id"

    @pytest.mark.asyncio
    async def test_competitor_limit_allows_creation_below_limit(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that competitor can be created when below limit."""
        # Arrange
        account_id = "acc_test"
        user_id = "user_test"
        competitor_data = CompetitorCreate(
            display_name="Test Competitor",
            description="Test description",
            references=[],
        )

        # Mock count_nodes to return 4 (below limit), list_nodes returns [] (no hub)
        mock_neo4j_service.execute_query = AsyncMock(
            side_effect=[
                [{"total": 4}],  # count_nodes: below limit
                [],  # list_nodes in create_competitor: no CompetitiveEnvironment hub
                [],  # list_nodes in create_competitive_environment: no hub exists
            ]
        )

        # Mock hub creation + competitor creation
        env_node = {
            "node_id": "competitiveenv_acc_test_hub",
            "description": "Competitive environment for tracking key competitors and market analysis.",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        competitor_node = {
            "node_id": "competitor_acc_test_xyz789",
            "display_name": "Test Competitor",
            "description": "Test description",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query = AsyncMock(
            side_effect=[
                [{"node": env_node}],  # create_competitive_environment
                [{"node": competitor_node}],  # create_competitor
            ]
        )

        # Mock validation services
        mock_validation_service.validate_non_empty_string = Mock(
            return_value=(True, None)
        )
        mock_validation_service.validate_account_exists = AsyncMock(return_value=True)
        mock_firestore_service.get_document = Mock(return_value={})

        # Act
        result = await graph_sync_service.create_competitor(
            account_id=account_id, competitor=competitor_data, user_id=user_id
        )

        # Assert
        assert result.display_name == "Test Competitor"
        assert result.description == "Test description"


# ==================== Marketing Strategy Tests ====================


class TestCustomerProfileOperations:
    """Tests for CustomerProfile CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_customer_profile_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful customer profile creation."""
        # Arrange
        from src.kene_api.models.graph_models import CustomerProfileCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        profile_create = CustomerProfileCreate(
            display_name="Marketing Mary",
            description="Chief Marketing Officer at mid-size B2B SaaS company",
            references=["https://example.com/research"],
        )

        # Mock unique customer profile name validation
        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            True,
            "",
        )

        # Mock profile creation
        expected_node_id = "customerprofile_test123_abc"
        expected_node = {
            "node_id": expected_node_id,
            "display_name": "Marketing Mary",
            "description": "Chief Marketing Officer at mid-size B2B SaaS company",
            "references": ["https://example.com/research"],
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
        result = await graph_sync_service.create_customer_profile(
            account_id, profile_create, user_id
        )

        # Assert
        assert result.node_id == expected_node_id
        assert result.display_name == "Marketing Mary"
        assert (
            result.description == "Chief Marketing Officer at mid-size B2B SaaS company"
        )
        mock_validation_service.validate_unique_customer_profile_name.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_customer_profile_duplicate_name(
        self, graph_sync_service, mock_validation_service
    ):
        """Test creating profile with duplicate display_name fails."""
        # Arrange
        from src.kene_api.exceptions import DuplicateNodeException
        from src.kene_api.models.graph_models import CustomerProfileCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        profile_create = CustomerProfileCreate(
            display_name="Existing Profile",
            description="Test profile",
            references=[],
        )

        # Mock duplicate name validation failure
        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            False,
            "Customer profile with display_name 'Existing Profile' already exists",
        )

        # Act & Assert
        with pytest.raises(DuplicateNodeException, match="already exists"):
            await graph_sync_service.create_customer_profile(
                account_id, profile_create, user_id
            )

    @pytest.mark.asyncio
    async def test_delete_customer_profile_cascades_strategies(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test deleting profile cascades to all related strategies."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        profile_node_id = "customerprofile_test123_abc"

        # Mock profile exists
        profile_node = {
            "node_id": profile_node_id,
            "display_name": "Test Profile",
            "narrative": "Test narrative",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # Mock finding strategies for each type (return empty - no strategies exist)
        # First query checks for strategies, subsequent queries are for get_node (profile exists)
        mock_neo4j_service.execute_query.side_effect = [
            [],  # No ProblemAwarenessStrategy
            [],  # No BrandAwarenessStrategy
            [],  # No ConsiderationStrategy
            [],  # No ConversionStrategy
            [],  # No LoyaltyStrategy
            [{"node": profile_node, "account_id": account_id}],  # Profile exists
        ]

        # Mock profile deletion
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        # Act
        await graph_sync_service.delete_customer_profile(
            account_id, profile_node_id, user_id
        )

        # Assert
        assert mock_neo4j_service.execute_write_operation.called
        # Verify firestore was synced
        assert mock_firestore_service.update_document.called

    @pytest.mark.asyncio
    async def test_delete_customer_profile_removes_monitoring_topic_entry(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that deleting a customer profile removes its entry from monitoring_topics
        Shape B path (accounts/{account_id}/monitoring_topics, document_id='default')."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        profile_node_id = "customerprofile_test123_abc"
        other_profile_node_id = "customerprofile_test123_xyz"

        profile_node = {
            "node_id": profile_node_id,
            "display_name": "Test Profile",
            "narrative": "Test narrative",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # delete_customer_profile loops over 5 strategy types (each one execute_query for
        # finding strategies — all return empty here) then calls delete_node for the profile
        # itself which calls get_node (one more execute_query)
        mock_neo4j_service.execute_query.side_effect = [
            [],  # No ProblemAwarenessStrategy
            [],  # No BrandAwarenessStrategy
            [],  # No ConsiderationStrategy
            [],  # No ConversionStrategy
            [],  # No LoyaltyStrategy
            [{"node": profile_node, "account_id": account_id}],  # get_node check
        ]

        mock_neo4j_service.execute_write_operation.return_value = None

        monitoring_doc = {
            "customer_profile_entries": [
                {
                    "node_id": profile_node_id,
                    "name": "Test Profile",
                    "keywords": ["kw1"],
                },
                {
                    "node_id": other_profile_node_id,
                    "name": "Other Profile",
                    "keywords": ["kw2"],
                },
            ]
        }
        monitoring_collection = f"accounts/{account_id}/monitoring_topics"

        # Route get_document responses by collection so the test is resilient to
        # refactors that change the number or order of other Firestore reads.
        def get_document_side_effect(collection, document_id):
            if collection == monitoring_collection:
                return monitoring_doc
            return {}

        mock_firestore_service.get_document.side_effect = get_document_side_effect

        # Act
        await graph_sync_service.delete_customer_profile(
            account_id, profile_node_id, user_id
        )

        # Assert — get_document was called for the monitoring_topics Shape B path
        mock_firestore_service.get_document.assert_any_call(
            collection=monitoring_collection,
            document_id="default",
        )

        # Assert — update_document was called for the monitoring_topics Shape B path
        monitoring_update_calls = [
            call
            for call in mock_firestore_service.update_document.call_args_list
            if call.kwargs.get("collection") == monitoring_collection
        ]
        assert len(monitoring_update_calls) == 1, (
            "Expected exactly one update_document call for monitoring_topics"
        )

        # Assert — the deleted profile's entry was removed; the other entry remains
        update_call = monitoring_update_calls[0]
        remaining_entries = update_call.kwargs["data"]["customer_profile_entries"]
        assert len(remaining_entries) == 1
        assert remaining_entries[0]["node_id"] == other_profile_node_id


class TestProblemAwarenessStrategyOperations:
    """Tests for ProblemAwarenessStrategy CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_problem_awareness_strategy_dual_parents(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating strategy validates both parent nodes exist."""
        # Arrange
        from src.kene_api.models.graph_models import ProblemAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = ProblemAwarenessStrategyCreate(
            description="Educate on benefits of AI-powered marketing automation",
            references=["https://example.com/strategy"],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        # Mock parent validation
        mock_validation_service.validate_node_exists.return_value = True

        # Mock strategy creation with dual parents
        expected_node_id = f"problemaware_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Educate on benefits of AI-powered marketing automation",
            "references": ["https://example.com/strategy"],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
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
        result = await graph_sync_service.create_problem_awareness_strategy(
            account_id, strategy_create, user_id
        )

        # Assert
        assert result.node_id == expected_node_id
        assert result.product_category_node_id == product_category_id
        assert result.customer_profile_node_id == profile_id
        # Verify both parents were validated
        assert mock_validation_service.validate_node_exists.call_count == 2

    @pytest.mark.asyncio
    async def test_create_problem_awareness_strategy_invalid_parent(
        self, graph_sync_service, mock_validation_service
    ):
        """Test creating strategy with non-existent parent fails."""
        # Arrange
        from src.kene_api.exceptions import NodeNotFoundException
        from src.kene_api.models.graph_models import ProblemAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        strategy_create = ProblemAwarenessStrategyCreate(
            description="Test strategy",
            references=[],
            product_category_node_id="nonexistent_category",
            customer_profile_node_id="customerprofile_test123_def",
        )

        # Mock parent validation failure
        mock_validation_service.validate_node_exists.side_effect = (
            NodeNotFoundException("ProductCategory", "nonexistent_category")
        )

        # Act & Assert
        with pytest.raises(NodeNotFoundException):
            await graph_sync_service.create_problem_awareness_strategy(
                account_id, strategy_create, user_id
            )


class TestProblemAwarenessStrategyEdgeCases:
    """Additional edge case tests for ProblemAwarenessStrategy."""

    @pytest.mark.asyncio
    async def test_create_problem_awareness_with_invalid_customer_profile(
        self, graph_sync_service, mock_validation_service
    ):
        """Test creating strategy with invalid CustomerProfile parent fails."""
        from src.kene_api.exceptions import NodeNotFoundException
        from src.kene_api.models.graph_models import ProblemAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        strategy_create = ProblemAwarenessStrategyCreate(
            description="Test strategy",
            references=[],
            product_category_node_id="productcat_test123_abc",
            customer_profile_node_id="nonexistent_profile",
        )

        mock_validation_service.validate_node_exists.side_effect = [
            True,  # ProductCategory exists
            False,  # CustomerProfile does not exist
        ]

        with pytest.raises(NodeNotFoundException):
            await graph_sync_service.create_problem_awareness_strategy(
                account_id, strategy_create, user_id
            )

    @pytest.mark.asyncio
    async def test_update_problem_awareness_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful problem awareness strategy update."""
        from src.kene_api.models.graph_models import ProblemAwarenessStrategyUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "problemaware_cat123_prof456"

        updates = ProblemAwarenessStrategyUpdate(
            description="Updated: Focus on pain points in manual processes",
            references=["https://example.com/updated-research"],
        )

        existing_node = {
            "node_id": node_id,
            "description": "Original description",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        updated_node = existing_node.copy()
        updated_node["description"] = (
            "Updated: Focus on pain points in manual processes"
        )
        updated_node["references"] = ["https://example.com/updated-research"]
        updated_node["last_modified"] = datetime(2025, 1, 2)
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.update_problem_awareness_strategy(
            account_id, node_id, updates, user_id
        )

        assert result.description == "Updated: Focus on pain points in manual processes"
        assert result.references == ["https://example.com/updated-research"]

    @pytest.mark.asyncio
    async def test_delete_problem_awareness_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful problem awareness strategy deletion."""
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "problemaware_cat123_prof456"

        existing_node = {
            "node_id": node_id,
            "description": "Test strategy",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        await graph_sync_service.delete_problem_awareness_strategy(
            account_id, node_id, user_id
        )

        assert mock_neo4j_service.execute_write_operation.called
        assert mock_firestore_service.update_document.called

    @pytest.mark.asyncio
    async def test_verify_node_id_format_matches_pattern(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that node_id follows problemaware_{category}_{profile} pattern."""
        from src.kene_api.models.graph_models import ProblemAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_acc_test123_xyz"
        profile_id = "customerprofile_acc_test123_abc"

        strategy_create = ProblemAwarenessStrategyCreate(
            description="Test",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node_id = f"problemaware_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Test",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_problem_awareness_strategy(
            account_id, strategy_create, user_id
        )

        assert result.node_id == expected_node_id
        assert result.node_id.startswith("problemaware_")


class TestBrandAwarenessStrategyOperations:
    """Tests for BrandAwarenessStrategy CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_brand_awareness_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful brand awareness strategy creation."""
        # Arrange
        from src.kene_api.models.graph_models import BrandAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = BrandAwarenessStrategyCreate(
            description="Showcase thought leadership through industry reports",
            references=["https://example.com/brand-strategy"],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        # Mock parent validation
        mock_validation_service.validate_node_exists.return_value = True

        # Mock strategy creation
        expected_node_id = f"brandaware_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Showcase thought leadership through industry reports",
            "references": ["https://example.com/brand-strategy"],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
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
        result = await graph_sync_service.create_brand_awareness_strategy(
            account_id, strategy_create, user_id
        )

        # Assert
        assert result.node_id == expected_node_id
        assert (
            result.description == "Showcase thought leadership through industry reports"
        )
        assert result.product_category_node_id == product_category_id
        assert result.customer_profile_node_id == profile_id

    @pytest.mark.asyncio
    async def test_update_brand_awareness_references_field(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test updating only references field."""
        from src.kene_api.models.graph_models import BrandAwarenessStrategyUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "brandaware_cat123_prof456"

        updates = BrandAwarenessStrategyUpdate(
            references=["https://example.com/new-ref1", "https://example.com/new-ref2"]
        )

        existing_node = {
            "node_id": node_id,
            "description": "Original description",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        updated_node = existing_node.copy()
        updated_node["references"] = [
            "https://example.com/new-ref1",
            "https://example.com/new-ref2",
        ]
        updated_node["last_modified"] = datetime(2025, 1, 2)
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.update_brand_awareness_strategy(
            account_id, node_id, updates, user_id
        )

        assert len(result.references) == 2
        assert "https://example.com/new-ref1" in result.references

    @pytest.mark.asyncio
    async def test_delete_brand_awareness_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful brand awareness strategy deletion."""
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "brandaware_cat123_prof456"

        existing_node = {
            "node_id": node_id,
            "description": "Test strategy",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        await graph_sync_service.delete_brand_awareness_strategy(
            account_id, node_id, user_id
        )

        assert mock_neo4j_service.execute_write_operation.called
        assert mock_firestore_service.update_document.called

    @pytest.mark.asyncio
    async def test_verify_dual_parent_ids_stored_as_properties(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that parent node_ids are stored as properties for query performance."""
        from src.kene_api.models.graph_models import BrandAwarenessStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = BrandAwarenessStrategyCreate(
            description="Test",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node = {
            "node_id": f"brandaware_{product_category_id}_{profile_id}",
            "description": "Test",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_brand_awareness_strategy(
            account_id, strategy_create, user_id
        )

        assert result.product_category_node_id == product_category_id
        assert result.customer_profile_node_id == profile_id


class TestConsiderationStrategyOperations:
    """Tests for ConsiderationStrategy CRUD operations."""

    @pytest.mark.asyncio
    async def test_update_consideration_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful consideration strategy update."""
        # Arrange
        from src.kene_api.models.graph_models import ConsiderationStrategyUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "consideration_cat123_prof456"

        updates = ConsiderationStrategyUpdate(
            description="Updated: Provide ROI calculator and case studies",
            references=["https://example.com/updated"],
        )

        # Mock node exists
        existing_node = {
            "node_id": node_id,
            "description": "Original description",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        # Mock update
        updated_node = existing_node.copy()
        updated_node["description"] = "Updated: Provide ROI calculator and case studies"
        updated_node["references"] = ["https://example.com/updated"]
        updated_node["last_modified"] = datetime(2025, 1, 2)
        updated_node["last_modified_by"] = user_id
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.update_consideration_strategy(
            account_id, node_id, updates, user_id
        )

        # Assert
        assert result.description == "Updated: Provide ROI calculator and case studies"
        assert result.references == ["https://example.com/updated"]


class TestMarketingStrategyIntegration:
    """Integration tests for complete marketing strategy workflows."""

    @pytest.mark.asyncio
    async def test_create_profile_and_multiple_strategies(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating profile and multiple strategy types for same customer-product pair."""
        # Arrange
        from src.kene_api.models.graph_models import (
            ConversionStrategyCreate,
            CustomerProfileCreate,
            LoyaltyStrategyCreate,
        )

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"

        profile_create = CustomerProfileCreate(
            display_name="Enterprise Eva",
            description="VP of Operations at Fortune 500 company",
            references=[],
        )

        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            True,
            "",
        )
        mock_validation_service.validate_node_exists.return_value = True

        # Mock profile creation
        profile_node_id = "customerprofile_test123_xyz"
        profile_node = {
            "node_id": profile_node_id,
            "display_name": "Enterprise Eva",
            "description": "VP of Operations at Fortune 500 company",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # Mock conversion strategy
        conversion_node_id = f"conversion_{product_category_id}_{profile_node_id}"
        conversion_node = {
            "node_id": conversion_node_id,
            "description": "Offer white-glove onboarding and dedicated CSM",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        # Mock loyalty strategy
        loyalty_node_id = f"loyalty_{product_category_id}_{profile_node_id}"
        loyalty_node = {
            "node_id": loyalty_node_id,
            "description": "Executive forums and early access to new features",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        mock_neo4j_service.execute_write_query.side_effect = [
            [{"node": profile_node}],
            [{"node": conversion_node}],
            [{"node": loyalty_node}],
        ]
        mock_firestore_service.get_document.return_value = {}

        # Act - Create profile
        profile_result = await graph_sync_service.create_customer_profile(
            account_id, profile_create, user_id
        )

        # Act - Create conversion strategy
        conversion_create = ConversionStrategyCreate(
            description="Offer white-glove onboarding and dedicated CSM",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_node_id,
        )
        conversion_result = await graph_sync_service.create_conversion_strategy(
            account_id, conversion_create, user_id
        )

        # Act - Create loyalty strategy
        loyalty_create = LoyaltyStrategyCreate(
            description="Executive forums and early access to new features",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_node_id,
        )
        loyalty_result = await graph_sync_service.create_loyalty_strategy(
            account_id, loyalty_create, user_id
        )

        # Assert
        assert profile_result.display_name == "Enterprise Eva"
        assert conversion_result.product_category_node_id == product_category_id
        assert conversion_result.customer_profile_node_id == profile_node_id
        assert loyalty_result.product_category_node_id == product_category_id
        assert loyalty_result.customer_profile_node_id == profile_node_id
        # Verify all three nodes were created
        assert mock_neo4j_service.execute_write_query.call_count == 3


# ==================== Additional Marketing Strategy Tests ====================


class TestConsiderationStrategyEdgeCases:
    """Additional edge case tests for ConsiderationStrategy."""

    @pytest.mark.asyncio
    async def test_create_consideration_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful consideration strategy creation."""
        from src.kene_api.models.graph_models import ConsiderationStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = ConsiderationStrategyCreate(
            description="Provide ROI calculator and detailed case studies",
            references=["https://example.com/consideration"],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node_id = f"consideration_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Provide ROI calculator and detailed case studies",
            "references": ["https://example.com/consideration"],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_consideration_strategy(
            account_id, strategy_create, user_id
        )

        assert result.node_id == expected_node_id
        assert result.product_category_node_id == product_category_id
        assert result.customer_profile_node_id == profile_id

    @pytest.mark.asyncio
    async def test_delete_consideration_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful consideration strategy deletion."""
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "consideration_cat123_prof456"

        existing_node = {
            "node_id": node_id,
            "description": "Test strategy",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        await graph_sync_service.delete_consideration_strategy(
            account_id, node_id, user_id
        )

        assert mock_neo4j_service.execute_write_operation.called
        assert mock_firestore_service.update_document.called

    @pytest.mark.asyncio
    async def test_create_consideration_with_missing_parent_fails(
        self, graph_sync_service, mock_validation_service
    ):
        """Test creating strategy with missing parent fails."""
        from src.kene_api.exceptions import NodeNotFoundException
        from src.kene_api.models.graph_models import ConsiderationStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        strategy_create = ConsiderationStrategyCreate(
            description="Test",
            references=[],
            product_category_node_id="nonexistent_cat",
            customer_profile_node_id="customerprofile_test123_def",
        )

        mock_validation_service.validate_node_exists.return_value = False

        with pytest.raises(NodeNotFoundException):
            await graph_sync_service.create_consideration_strategy(
                account_id, strategy_create, user_id
            )

    @pytest.mark.asyncio
    async def test_verify_consideration_node_id_format(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that node_id follows consideration_{category}_{profile} pattern."""
        from src.kene_api.models.graph_models import ConsiderationStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_xyz"
        profile_id = "customerprofile_abc"

        strategy_create = ConsiderationStrategyCreate(
            description="Test",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node_id = f"consideration_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Test",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_consideration_strategy(
            account_id, strategy_create, user_id
        )

        assert result.node_id == expected_node_id
        assert result.node_id.startswith("consideration_")


class TestConversionStrategyEdgeCases:
    """Edge case tests for ConversionStrategy."""

    @pytest.mark.asyncio
    async def test_create_conversion_strategy_with_dual_parents(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating conversion strategy validates both parents."""
        from src.kene_api.models.graph_models import ConversionStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = ConversionStrategyCreate(
            description="Offer free trial and dedicated onboarding specialist",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node_id = f"conversion_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "Offer free trial and dedicated onboarding specialist",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_conversion_strategy(
            account_id, strategy_create, user_id
        )

        assert result.node_id == expected_node_id
        assert mock_validation_service.validate_node_exists.call_count == 2

    @pytest.mark.asyncio
    async def test_update_conversion_description_field(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test updating conversion strategy description."""
        from src.kene_api.models.graph_models import ConversionStrategyUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "conversion_cat123_prof456"

        updates = ConversionStrategyUpdate(
            description="Updated: Add money-back guarantee and expedited setup"
        )

        existing_node = {
            "node_id": node_id,
            "description": "Original description",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        updated_node = existing_node.copy()
        updated_node["description"] = (
            "Updated: Add money-back guarantee and expedited setup"
        )
        updated_node["last_modified"] = datetime(2025, 1, 2)
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.update_conversion_strategy(
            account_id, node_id, updates, user_id
        )

        assert "money-back guarantee" in result.description

    @pytest.mark.asyncio
    async def test_delete_conversion_and_verify_firestore_sync_called(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test deletion calls Firestore sync."""
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "conversion_cat123_prof456"

        existing_node = {
            "node_id": node_id,
            "description": "Test",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        await graph_sync_service.delete_conversion_strategy(
            account_id, node_id, user_id
        )

        mock_firestore_service.update_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_required_description_field(
        self, graph_sync_service, mock_validation_service
    ):
        """Test that description cannot be empty."""
        from src.kene_api.exceptions import ValidationException
        from src.kene_api.models.graph_models import ConversionStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"

        strategy_create = ConversionStrategyCreate(
            description="",  # Empty description should fail service validation
            references=[],
            product_category_node_id="productcat_test123_abc",
            customer_profile_node_id="customerprofile_test123_def",
        )

        # Mock validation to return invalid for empty string
        mock_validation_service.validate_non_empty_string.return_value = (
            False,
            "description cannot be empty or contain only whitespace",
        )

        # Service-level validation should catch empty description
        with pytest.raises(ValidationException):
            await graph_sync_service.create_conversion_strategy(
                account_id, strategy_create, user_id
            )


class TestLoyaltyStrategyEdgeCases:
    """Edge case tests for LoyaltyStrategy."""

    @pytest.mark.asyncio
    async def test_create_loyalty_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful loyalty strategy creation."""
        from src.kene_api.models.graph_models import LoyaltyStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = LoyaltyStrategyCreate(
            description="VIP community access and early feature previews",
            references=["https://example.com/loyalty-program"],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        expected_node_id = f"loyalty_{product_category_id}_{profile_id}"
        expected_node = {
            "node_id": expected_node_id,
            "description": "VIP community access and early feature previews",
            "references": ["https://example.com/loyalty-program"],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_loyalty_strategy(
            account_id, strategy_create, user_id
        )

        assert result.node_id == expected_node_id
        assert result.description == "VIP community access and early feature previews"

    @pytest.mark.asyncio
    async def test_update_loyalty_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful loyalty strategy update."""
        from src.kene_api.models.graph_models import LoyaltyStrategyUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "loyalty_cat123_prof456"

        updates = LoyaltyStrategyUpdate(
            description="Updated: Quarterly executive briefings and product roadmap access"
        )

        existing_node = {
            "node_id": node_id,
            "description": "Original loyalty program",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        updated_node = existing_node.copy()
        updated_node["description"] = (
            "Updated: Quarterly executive briefings and product roadmap access"
        )
        updated_node["last_modified"] = datetime(2025, 1, 2)
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.update_loyalty_strategy(
            account_id, node_id, updates, user_id
        )

        assert "executive briefings" in result.description

    @pytest.mark.asyncio
    async def test_delete_loyalty_strategy_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
    ):
        """Test successful loyalty strategy deletion."""
        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "loyalty_cat123_prof456"

        existing_node = {
            "node_id": node_id,
            "description": "Test",
            "references": [],
            "product_category_node_id": "productcat_test123_abc",
            "customer_profile_node_id": "customerprofile_test123_def",
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]
        mock_neo4j_service.execute_write_operation.return_value = None
        mock_firestore_service.get_document.return_value = {}

        await graph_sync_service.delete_loyalty_strategy(account_id, node_id, user_id)

        assert mock_neo4j_service.execute_write_operation.called

    @pytest.mark.asyncio
    async def test_verify_strategy_label_applied(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that Strategy label is applied for embedding search."""
        from src.kene_api.models.graph_models import LoyaltyStrategyCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        product_category_id = "productcat_test123_abc"
        profile_id = "customerprofile_test123_def"

        strategy_create = LoyaltyStrategyCreate(
            description="Test",
            references=[],
            product_category_node_id=product_category_id,
            customer_profile_node_id=profile_id,
        )

        mock_validation_service.validate_node_exists.return_value = True

        # Verify the Cypher query includes both labels (implicit in implementation)
        expected_node = {
            "node_id": f"loyalty_{product_category_id}_{profile_id}",
            "description": "Test",
            "references": [],
            "product_category_node_id": product_category_id,
            "customer_profile_node_id": profile_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_loyalty_strategy(
            account_id, strategy_create, user_id
        )

        # Verify node was created successfully (label verification happens in integration tests)
        assert result.node_id is not None
        assert result.embedding is None  # Initially null


class TestCustomerProfileEdgeCases:
    """Additional edge case tests for CustomerProfile operations."""

    @pytest.mark.asyncio
    async def test_create_with_case_insensitive_duplicate_name_fails(
        self, graph_sync_service, mock_validation_service
    ):
        """Test that case-insensitive duplicate display_name fails."""
        from src.kene_api.exceptions import DuplicateNodeException
        from src.kene_api.models.graph_models import CustomerProfileCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        profile_create = CustomerProfileCreate(
            display_name="Marketing Mary",  # Will be stored as "marketing mary"
            description="Test profile",
            references=[],
        )

        # Mock validation to indicate name already exists (case-insensitive)
        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            False,
            "Customer profile with display_name 'marketing mary' already exists",
        )

        with pytest.raises(DuplicateNodeException):
            await graph_sync_service.create_customer_profile(
                account_id, profile_create, user_id
            )

    @pytest.mark.asyncio
    async def test_create_with_empty_references_array(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating profile with empty references array."""
        from src.kene_api.models.graph_models import CustomerProfileCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        profile_create = CustomerProfileCreate(
            display_name="Tech Tom",
            description="Technical buyer persona",
            references=[],  # Empty array
        )

        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            True,
            "",
        )

        expected_node_id = "customerprofile_test123_xyz"
        expected_node = {
            "node_id": expected_node_id,
            "display_name": "tech tom",  # Lowercase
            "description": "Technical buyer persona",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_customer_profile(
            account_id, profile_create, user_id
        )

        assert result.references == []

    @pytest.mark.asyncio
    async def test_update_display_name_successfully(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successfully updating display_name."""
        from src.kene_api.models.graph_models import CustomerProfileUpdate

        account_id = "acc_test123"
        user_id = "user_test456"
        node_id = "customerprofile_test123_abc"

        updates = CustomerProfileUpdate(display_name="Enterprise Emily")

        existing_node = {
            "node_id": node_id,
            "display_name": "enterprise eva",
            "narrative": "Original narrative",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
        }
        mock_neo4j_service.execute_query.return_value = [
            {"node": existing_node, "account_id": account_id}
        ]

        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            True,
            "",
        )

        updated_node = existing_node.copy()
        updated_node["display_name"] = "enterprise emily"  # Stored lowercase
        updated_node["last_modified"] = datetime(2025, 1, 2)
        mock_neo4j_service.execute_write_query.return_value = [{"node": updated_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.update_customer_profile(
            account_id, node_id, updates, user_id
        )

        assert result.display_name == "enterprise emily"

    @pytest.mark.asyncio
    async def test_verify_lowercase_storage_of_display_name(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test that display_name is stored in lowercase for case-insensitive matching."""
        from src.kene_api.models.graph_models import CustomerProfileCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        profile_create = CustomerProfileCreate(
            display_name="Marketing MARY",  # Mixed case
            description="Test",
            references=[],
        )

        mock_validation_service.validate_unique_customer_profile_name.return_value = (
            True,
            "",
        )

        expected_node = {
            "node_id": "customerprofile_test123_xyz",
            "display_name": "marketing mary",  # Stored as lowercase
            "description": "Test",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]
        mock_firestore_service.get_document.return_value = {}

        result = await graph_sync_service.create_customer_profile(
            account_id, profile_create, user_id
        )

        assert result.display_name == "marketing mary"
        assert result.display_name == result.display_name.lower()


# ==================== Brand Strategy Tests ====================


class TestBrandIdentityOperations:
    """Tests for BrandIdentity hub operations."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="GraphSyncService API changed: get_or_create_brand_identity method no longer exists"
    )
    async def test_get_or_create_brand_identity_creates_new(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test get_or_create creates BrandIdentity hub when none exists."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"

        # Mock no existing hub
        mock_neo4j_service.execute_query.return_value = []

        # Mock hub creation
        hub_node_id = "brand_test123_abc"
        hub_node = {
            "node_id": hub_node_id,
            "description": "Brand identity and guidelines hub",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": hub_node}]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result_node_id = await graph_sync_service.get_or_create_brand_identity(
            account_id, user_id
        )

        # Assert
        assert result_node_id == hub_node_id
        assert mock_neo4j_service.execute_write_query.called

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="GraphSyncService API changed: get_or_create_brand_identity method no longer exists"
    )
    async def test_get_or_create_brand_identity_reuses_existing(
        self, graph_sync_service, mock_neo4j_service
    ):
        """Test get_or_create reuses existing BrandIdentity hub."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        existing_hub_id = "brand_test123_xyz"

        # Mock existing hub
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {
                    "node_id": existing_hub_id,
                    "description": "Existing hub",
                    "references": [],
                    "account_id": account_id,
                },
                "account_id": account_id,
            }
        ]

        # Act
        result_node_id = await graph_sync_service.get_or_create_brand_identity(
            account_id, user_id
        )

        # Assert
        assert result_node_id == existing_hub_id
        # Should NOT create new hub
        assert not mock_neo4j_service.execute_write_query.called


class TestBrandPersonalityOperations:
    """Tests for BrandPersonality CRUD operations."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="GraphSyncService API changed: create_brand_personality method no longer exists"
    )
    async def test_create_brand_personality_auto_creates_hub(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating brand personality auto-creates BrandIdentity hub if missing."""
        # Arrange
        from src.kene_api.models.graph_models import BrandPersonalityCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        personality_create = BrandPersonalityCreate(
            description="Innovative, friendly, and approachable",
            references=["https://example.com/brand-guide"],
        )

        # Mock no existing hub
        mock_neo4j_service.execute_query.return_value = []

        # Mock hub creation then personality creation
        hub_node_id = "brand_test123_xyz"
        hub_node = {
            "node_id": hub_node_id,
            "description": "Brand identity and guidelines hub",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        personality_node_id = "personality_test123_abc"
        personality_node = {
            "node_id": personality_node_id,
            "description": "Innovative, friendly, and approachable",
            "references": ["https://example.com/brand-guide"],
            "brand_identity_node_id": hub_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        mock_neo4j_service.execute_write_query.side_effect = [
            [{"node": hub_node}],  # Hub creation
            [{"node": personality_node}],  # Personality creation
        ]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.create_brand_personality(
            account_id, personality_create, user_id
        )

        # Assert
        assert result.node_id == personality_node_id
        assert result.description == "Innovative, friendly, and approachable"
        assert result.brand_identity_node_id == hub_node_id
        # Verify hub was created first
        assert mock_neo4j_service.execute_write_query.call_count == 2


class TestColorPaletteOperations:
    """Tests for ColorPalette CRUD operations."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="GraphSyncService API changed: create_color_palette method no longer exists"
    )
    async def test_create_color_palette_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test successful color palette creation."""
        # Arrange
        from src.kene_api.models.graph_models import ColorPaletteCreate

        account_id = "acc_test123"
        user_id = "user_test456"
        hub_node_id = "brand_test123_xyz"

        palette_create = ColorPaletteCreate(
            description="Primary: Navy Blue (#1A2B3C). Secondary: Sky Blue (#4A90E2)",
            references=["https://example.com/colors"],
        )

        # Mock existing hub
        mock_neo4j_service.execute_query.return_value = [
            {
                "node": {"node_id": hub_node_id},
                "account_id": account_id,
            }
        ]

        # Mock palette creation
        palette_node_id = "colors_test123_abc"
        palette_node = {
            "node_id": palette_node_id,
            "description": "Primary: Navy Blue (#1A2B3C). Secondary: Sky Blue (#4A90E2)",
            "references": ["https://example.com/colors"],
            "brand_identity_node_id": hub_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": palette_node}]
        mock_firestore_service.get_document.return_value = {}

        # Act
        result = await graph_sync_service.create_color_palette(
            account_id, palette_create, user_id
        )

        # Assert
        assert result.node_id == palette_node_id
        assert result.brand_identity_node_id == hub_node_id
        assert "Navy Blue" in result.description


class TestBrandStrategyIntegration:
    """Integration tests for complete brand strategy workflows."""

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="GraphSyncService API changed: create_brand_personality and create_voice_and_tone methods no longer exist"
    )
    async def test_create_multiple_brand_children_share_hub(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service,
        mock_validation_service,
    ):
        """Test creating multiple brand children all link to same hub."""
        # Arrange
        from src.kene_api.models.graph_models import (
            BrandPersonalityCreate,
            VoiceAndToneCreate,
        )

        account_id = "acc_test123"
        user_id = "user_test456"
        hub_node_id = "brand_test123_xyz"

        # First creation: no hub exists, then hub exists for subsequent
        mock_neo4j_service.execute_query.side_effect = [
            [],  # No hub for first child
            [
                {"node": {"node_id": hub_node_id}, "account_id": account_id}
            ],  # Hub exists
        ]

        hub_node = {
            "node_id": hub_node_id,
            "description": "Brand identity and guidelines hub",
            "references": [],
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        personality_node = {
            "node_id": "personality_test123_abc",
            "description": "Friendly",
            "references": [],
            "brand_identity_node_id": hub_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        voice_node = {
            "node_id": "voicetone_test123_def",
            "description": "Conversational",
            "references": [],
            "brand_identity_node_id": hub_node_id,
            "account_id": account_id,
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None,
        }

        mock_neo4j_service.execute_write_query.side_effect = [
            [{"node": hub_node}],  # Create hub
            [{"node": personality_node}],  # Create personality
            [{"node": voice_node}],  # Create voice
        ]
        mock_firestore_service.get_document.return_value = {}

        # Act
        personality_create = BrandPersonalityCreate(
            description="Friendly", references=[]
        )
        personality_result = await graph_sync_service.create_brand_personality(
            account_id, personality_create, user_id
        )

        voice_create = VoiceAndToneCreate(description="Conversational", references=[])
        voice_result = await graph_sync_service.create_voice_and_tone(
            account_id, voice_create, user_id
        )

        # Assert
        assert personality_result.brand_identity_node_id == hub_node_id
        assert voice_result.brand_identity_node_id == hub_node_id
        # Hub created once + two children
        assert mock_neo4j_service.execute_write_query.call_count == 3


# ==================== Rollup Strategy Validation Tests ====================


class TestRollupStrategyValidation:
    """Tests for rollup marketing strategy type validation."""

    def test_validate_marketing_strategy_type_valid(self, graph_sync_service):
        """Test validation passes for valid strategy types."""
        valid_types = [
            "ProblemAwarenessStrategy",
            "BrandAwarenessStrategy",
            "ConsiderationStrategy",
            "ConversionStrategy",
            "LoyaltyStrategy",
        ]

        for strategy_type in valid_types:
            # Should not raise exception
            graph_sync_service._validate_marketing_strategy_type(strategy_type)

    def test_validate_marketing_strategy_type_invalid(self, graph_sync_service):
        """Test validation raises exception for invalid strategy types."""
        from src.kene_api.exceptions import ValidationException

        invalid_types = [
            "InvalidStrategy",
            "ProductCategory",
            "'; DROP TABLE strategies; --",  # SQL injection attempt
            "Strategy<script>alert('xss')</script>",  # XSS attempt
        ]

        for strategy_type in invalid_types:
            with pytest.raises(ValidationException) as exc_info:
                graph_sync_service._validate_marketing_strategy_type(strategy_type)
            assert "Invalid strategy type" in str(exc_info.value)
            assert strategy_type in str(exc_info.value)


class TestRollupHubCreation:
    """Tests for rollup marketing hub creation exception handling."""

    @pytest.mark.asyncio
    async def test_create_rollup_hub_failure_raises_proper_exception(
        self,
        graph_sync_service,
        mock_neo4j_service,
    ):
        """Test that hub creation failure raises NodeCreationException."""
        from src.kene_api.exceptions import NodeCreationException
        from src.kene_api.models.graph_models import RollupMarketingStrategyCreate

        # Arrange - mock duplicate check to return empty (no existing hub)
        # Then mock Neo4j creation to return empty result (failure)
        mock_neo4j_service.execute_query = AsyncMock(return_value=[])
        mock_neo4j_service.execute_write_query.return_value = None

        account_id = "acc_test123"
        user_id = "user_test456"
        hub_data = RollupMarketingStrategyCreate(description="Test rollup strategy")

        # Act & Assert
        with pytest.raises(NodeCreationException) as exc_info:
            await graph_sync_service.create_rollup_marketing_hub(
                account_id, hub_data.model_dump(), user_id
            )

        assert exc_info.value.node_type == "RollupMarketingStrategy"
        assert exc_info.value.account_id == account_id
        assert "Account may not exist" in str(exc_info.value)


class TestRollupStrategyListOptimization:
    """Tests for optimized rollup strategy list query."""

    @pytest.mark.asyncio
    async def test_list_rollup_strategies_single_query(
        self,
        graph_sync_service,
        mock_neo4j_service,
    ):
        """Test that list operation uses single database query to prevent N+1 problem."""
        # Arrange
        account_id = "acc_test123"
        strategy_type = "ProblemAwarenessStrategy"

        # Mock single combined query result
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[
                {
                    "paginated_strategies": [
                        {
                            "strategy": {
                                "node_id": "rollup_problemawareness_acc_test123_abc",
                                "description": "Test strategy 1",
                                "created_time": datetime.now(),
                            },
                            "individual_count": 3,
                        },
                        {
                            "strategy": {
                                "node_id": "rollup_problemawareness_acc_test123_def",
                                "description": "Test strategy 2",
                                "created_time": datetime.now(),
                            },
                            "individual_count": 5,
                        },
                    ],
                    "total": 10,
                }
            ]
        )

        # Act
        result = await graph_sync_service.list_rollup_strategies_by_type(
            account_id=account_id,
            strategy_type=strategy_type,
            skip=0,
            limit=2,
        )

        # Assert - verify single query was made
        assert mock_neo4j_service.execute_query.call_count == 1
        assert len(result["items"]) == 2
        assert result["total"] == 10
        assert result["items"][0]["individual_strategy_count"] == 3
        assert result["items"][1]["individual_strategy_count"] == 5

    @pytest.mark.asyncio
    async def test_list_rollup_strategies_with_no_limit(
        self,
        graph_sync_service,
        mock_neo4j_service,
    ):
        """Test pagination with limit=None returns all items after skip."""
        # Arrange
        account_id = "acc_test123"
        strategy_type = "ConsiderationStrategy"

        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[
                {
                    "paginated_strategies": [
                        {
                            "strategy": {
                                "node_id": f"rollup_consideration_acc_test123_{i}",
                                "description": f"Strategy {i}",
                                "created_time": datetime.now(),
                            },
                            "individual_count": i,
                        }
                        for i in range(5, 10)  # Simulating skip=5
                    ],
                    "total": 10,
                }
            ]
        )

        # Act
        result = await graph_sync_service.list_rollup_strategies_by_type(
            account_id=account_id,
            strategy_type=strategy_type,
            skip=5,
            limit=None,
        )

        # Assert
        assert len(result["items"]) == 5
        assert result["total"] == 10
        assert result["skip"] == 5
        assert result["limit"] is None

    @pytest.mark.asyncio
    async def test_list_rollup_strategies_empty_result(
        self,
        graph_sync_service,
        mock_neo4j_service,
    ):
        """Test handling of empty result set."""
        # Arrange
        mock_neo4j_service.execute_query = AsyncMock(
            return_value=[{"paginated_strategies": [], "total": 0}]
        )

        # Act
        result = await graph_sync_service.list_rollup_strategies_by_type(
            account_id="acc_test123",
            strategy_type="ConversionStrategy",
            skip=0,
            limit=10,
        )

        # Assert
        assert result["items"] == []
        assert result["total"] == 0
