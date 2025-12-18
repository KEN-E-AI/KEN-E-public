"""Graph sync service for bidirectional Neo4j + Firestore operations.

Provides unified CRUD operations for ALL strategy node types (Business, Competitive,
Marketing, Brand). Uses generic operations to eliminate code duplication (DRY principle).
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import Depends

from ..constants import ROLLUP_NODE_ID_PREFIX, VALID_MARKETING_STRATEGY_TYPES
from ..database import Neo4jService, get_neo4j_service
from ..exceptions import (
    DuplicateNodeException,
    GraphSyncException,
    NodeHasDependenciesException,
    NodeNotFoundException,
    ValidationException,
)
from ..firestore import FirestoreService, get_firestore_service
from ..models.graph_models import (
    BrandAwarenessStrategyCreate,
    BrandAwarenessStrategyResponse,
    BrandAwarenessStrategyUpdate,
    CompetitiveEnvironmentCreate,
    CompetitiveEnvironmentResponse,
    CompetitiveEnvironmentUpdate,
    CompetitorCreate,
    CompetitorResponse,
    CompetitorStrengthCreate,
    CompetitorStrengthResponse,
    CompetitorStrengthUpdate,
    CompetitorTacticCreate,
    CompetitorTacticResponse,
    CompetitorTacticUpdate,
    CompetitorUpdate,
    CompetitorWeaknessCreate,
    CompetitorWeaknessResponse,
    CompetitorWeaknessUpdate,
    ConsiderationStrategyCreate,
    ConsiderationStrategyResponse,
    ConsiderationStrategyUpdate,
    ConversionStrategyCreate,
    ConversionStrategyResponse,
    ConversionStrategyUpdate,
    CustomerProfileCreate,
    CustomerProfileResponse,
    CustomerProfileUpdate,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    LoyaltyStrategyCreate,
    LoyaltyStrategyResponse,
    LoyaltyStrategyUpdate,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
    ProblemAwarenessStrategyCreate,
    ProblemAwarenessStrategyResponse,
    ProblemAwarenessStrategyUpdate,
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    RiskCreate,
    RiskResponse,
    RiskUpdate,
    StrengthCreate,
    StrengthResponse,
    StrengthUpdate,
    SubstituteProductCreate,
    SubstituteProductResponse,
    SubstituteProductUpdate,
    ValuePropositionCreate,
    ValuePropositionResponse,
    ValuePropositionUpdate,
    WeaknessCreate,
    WeaknessResponse,
    WeaknessUpdate,
)
from .graph_validation_service import GraphValidationService, validate_node_type

logger = logging.getLogger(__name__)


class GraphSyncService:
    """Unified service for syncing ALL strategy nodes between Neo4j and Firestore.

    Handles: Business, Competitive, Marketing, and Brand strategy nodes.
    Uses generic CRUD operations to avoid code duplication.
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        firestore_service: FirestoreService,
        validation_service: GraphValidationService,
    ):
        """Initialize graph sync service.

        Args:
            neo4j_service: Neo4j database service
            firestore_service: Firestore database service
            validation_service: Graph validation service
        """
        self.neo4j = neo4j_service
        self.firestore = firestore_service
        self.validation = validation_service

    # ==================== GENERIC CRUD OPERATIONS ====================

    async def create_node(
        self,
        account_id: str,
        node_type: str,
        node_data: dict[str, Any],
        parent_node_id: str | None,
        parent_node_type: str | None,
        user_id: str,
        firestore_doc_type: str,
    ) -> dict[str, Any]:
        """Generic node creation with Neo4j + Firestore sync.

        Works for ALL node types: Product, Competitor, CustomerProfile, etc.

        Args:
            account_id: Account identifier
            node_type: Node type label (e.g., "Product", "Competitor")
            node_data: Node properties (pre-validated by Pydantic)
            parent_node_id: Optional parent for relationship
            parent_node_type: Type of parent node
            user_id: User creating the node
            firestore_doc_type: "business_strategy", "competitive_strategy", etc.

        Returns:
            Created node as dictionary

        Raises:
            ValidationException: If node_type is invalid
            NodeNotFoundException: If account or parent not found
            GraphSyncException: If sync fails (with rollback)
        """
        try:
            # 0. Validate node_type to prevent Cypher injection
            validate_node_type(node_type)

            # 1. Validate account exists
            if not await self.validation.validate_account_exists(account_id):
                raise NodeNotFoundException("Account", account_id)

            # 2. Validate parent exists (if required)
            if parent_node_id:
                validate_node_type(parent_node_type)
                if not await self.validation.validate_node_exists(
                    parent_node_id, parent_node_type
                ):
                    raise NodeNotFoundException(parent_node_type, parent_node_id)

            # 3. Generate node_id with appropriate prefix
            node_id = self._generate_node_id(node_type, account_id)

            # 4. Use transactional approach: Create in Neo4j within transaction,
            #    then sync to Firestore BEFORE committing
            neo4j_result = None
            try:
                # Step 4a: Create in Neo4j (transaction not committed yet if using session.execute_write)
                neo4j_result = await self._create_node_neo4j(
                    node_id=node_id,
                    node_type=node_type,
                    node_data=node_data,
                    account_id=account_id,
                    parent_node_id=parent_node_id,
                    parent_node_type=parent_node_type,
                    user_id=user_id,
                )

                # Step 4b: Sync to Firestore
                # If this fails, Neo4j transaction will rollback when exception propagates
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=neo4j_result,
                    firestore_doc_type=firestore_doc_type,
                    operation="create",
                )

                # Step 4c: Both succeeded - return result
                logger.info(f"Successfully created and synced {node_type} {node_id}")
                return {**neo4j_result, "account_id": account_id}

            except Exception as sync_error:
                # If Firestore sync failed, explicitly rollback Neo4j
                # Note: execute_write_query should auto-rollback on exception,
                # but we explicitly delete to ensure cleanup
                if neo4j_result:
                    logger.error(
                        f"Sync failed after Neo4j create, attempting rollback: {sync_error}"
                    )
                    try:
                        await self._delete_node_neo4j(node_id)
                        logger.info(f"Successfully rolled back Neo4j node {node_id}")
                    except Exception as rollback_error:
                        logger.error(
                            f"CRITICAL: Rollback failed for {node_id}: {rollback_error}"
                        )
                        # This is a critical failure - database may be inconsistent
                        raise GraphSyncException(
                            f"Database sync failed AND rollback failed: {sync_error}. "
                            f"Manual cleanup may be required for node_id={node_id}",
                            operation="create",
                            node_type=node_type,
                            node_id=node_id,
                        ) from rollback_error

                # Raise appropriate exception
                raise GraphSyncException(
                    str(sync_error),
                    operation="create",
                    node_type=node_type,
                    node_id=node_id,
                ) from sync_error

        except Exception as e:
            logger.error(f"Failed to create {node_type}: {e}")
            raise

    async def update_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        updates: dict[str, Any],
        user_id: str,
        firestore_doc_type: str,
    ) -> dict[str, Any]:
        """Generic node update with atomic rollback on failure.

        Args:
            account_id: Account identifier
            node_id: Node identifier to update
            node_type: Node type label
            updates: Dictionary of fields to update
            user_id: User performing update
            firestore_doc_type: Firestore document type

        Returns:
            Updated node as dictionary

        Raises:
            ValidationException: If node_type is invalid
            NodeNotFoundException: If node not found
            GraphSyncException: If sync fails (with rollback)
        """
        try:
            # 0. Validate node_type to prevent Cypher injection
            validate_node_type(node_type)

            # 1. Verify node exists and get current state (for potential rollback)
            existing_node = await self.get_node(account_id, node_id, node_type)
            if not existing_node:
                raise NodeNotFoundException(node_type, node_id)

            # 2. Use transactional approach: Update in Neo4j, then sync to Firestore
            neo4j_result = None
            try:
                # Step 2a: Update in Neo4j
                neo4j_result = await self._update_node_neo4j(
                    node_id=node_id,
                    node_type=node_type,
                    updates=updates,
                    user_id=user_id,
                )

                # Step 2b: Sync to Firestore
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=neo4j_result,
                    firestore_doc_type=firestore_doc_type,
                    operation="update",
                )

                # Step 2c: Both succeeded
                logger.info(f"Successfully updated and synced {node_type} {node_id}")
                return {**neo4j_result, "account_id": account_id}

            except Exception as sync_error:
                # If Firestore sync failed, rollback Neo4j to previous state
                if neo4j_result:
                    logger.error(
                        f"Sync failed after Neo4j update, attempting rollback: {sync_error}"
                    )
                    try:
                        # Restore only the fields that were updated
                        rollback_updates = {
                            k: v for k, v in existing_node.items() if k in updates
                        }
                        await self._update_node_neo4j(
                            node_id=node_id,
                            node_type=node_type,
                            updates=rollback_updates,
                            user_id=user_id,
                        )
                        logger.info(
                            f"Successfully rolled back Neo4j node {node_id} to previous state"
                        )
                    except Exception as rollback_error:
                        logger.error(
                            f"CRITICAL: Rollback failed for {node_id}: {rollback_error}"
                        )
                        raise GraphSyncException(
                            f"Database sync failed AND rollback failed: {sync_error}. "
                            f"Node {node_id} may be in inconsistent state",
                            operation="update",
                            node_type=node_type,
                            node_id=node_id,
                        ) from rollback_error

                # Raise appropriate exception
                raise GraphSyncException(
                    str(sync_error),
                    operation="update",
                    node_type=node_type,
                    node_id=node_id,
                ) from sync_error

        except Exception as e:
            logger.error(f"Failed to update {node_type} {node_id}: {e}")
            raise

    async def delete_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        user_id: str,
        firestore_doc_type: str,
        check_dependencies: bool = True,
    ) -> None:
        """Generic node deletion with dependency validation.

        Args:
            account_id: Account identifier
            node_id: Node identifier to delete
            node_type: Node type label
            user_id: User performing deletion
            firestore_doc_type: Firestore document type
            check_dependencies: Whether to validate no dependent nodes

        Raises:
            ValidationException: If node_type is invalid
            NodeNotFoundException: If node not found
            NodeHasDependenciesException: If node has dependencies
            GraphSyncException: If sync fails (with rollback)
        """
        try:
            # 0. Validate node_type to prevent Cypher injection
            validate_node_type(node_type)

            # 1. Verify node exists
            existing_node = await self.get_node(account_id, node_id, node_type)
            if not existing_node:
                raise NodeNotFoundException(node_type, node_id)

            # 2. Check dependencies if required
            if check_dependencies:
                can_delete, reason = await self._validate_can_delete(node_id, node_type)
                if not can_delete:
                    # Parse reason to extract dependency info for proper exception
                    # Reason format: "Cannot delete NodeType with N existing dependencies"
                    import re

                    match = re.search(
                        r"with (\d+) (?:existing )?(.+?)(?:\(s\))?$", reason
                    )
                    if match:
                        count = int(match.group(1))
                        dependency_type = match.group(2).strip()
                        raise NodeHasDependenciesException(
                            node_type, node_id, dependency_type, count
                        )
                    else:
                        # Fallback if parsing fails
                        raise NodeHasDependenciesException(
                            node_type, node_id, "dependent nodes", 0
                        )

            # 3. Use transactional approach: Delete from Neo4j, then sync to Firestore
            deleted = False
            try:
                # Step 3a: Delete from Neo4j
                await self._delete_node_neo4j(node_id)
                deleted = True

                # Step 3b: Sync to Firestore
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=existing_node,
                    firestore_doc_type=firestore_doc_type,
                    operation="delete",
                )

                # Step 3c: Both succeeded
                logger.info(f"Successfully deleted and synced {node_type} {node_id}")

            except Exception as sync_error:
                # If Firestore sync failed after Neo4j deletion, restore the node
                if deleted:
                    logger.error(
                        f"Sync failed after Neo4j delete, attempting to restore: {sync_error}"
                    )
                    try:
                        # Restore the deleted node
                        await self._create_node_neo4j(
                            node_id=node_id,
                            node_type=node_type,
                            node_data=existing_node,
                            account_id=account_id,
                            parent_node_id=existing_node.get("parent_node_id"),
                            parent_node_type=existing_node.get("parent_node_type"),
                            user_id=user_id,
                        )
                        logger.info(f"Successfully restored Neo4j node {node_id}")
                    except Exception as rollback_error:
                        logger.error(
                            f"CRITICAL: Failed to restore deleted node {node_id}: {rollback_error}"
                        )
                        raise GraphSyncException(
                            f"Database sync failed AND node restoration failed: {sync_error}. "
                            f"Node {node_id} was deleted from Neo4j but not Firestore",
                            operation="delete",
                            node_type=node_type,
                            node_id=node_id,
                        ) from rollback_error

                # Raise appropriate exception
                raise GraphSyncException(
                    str(sync_error),
                    operation="delete",
                    node_type=node_type,
                    node_id=node_id,
                ) from sync_error

        except Exception as e:
            logger.error(f"Failed to delete {node_type} {node_id}: {e}")
            raise

    async def list_nodes(
        self,
        account_id: str,
        node_type: str,
        parent_node_id: str | None = None,
        parent_node_type: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Generic list operation for any node type with optional pagination.

        Args:
            account_id: Account identifier
            node_type: Node type label
            parent_node_id: Optional filter by parent relationship
            parent_node_type: Optional parent node type (required if parent_node_id is provided)
            skip: Number of nodes to skip (default: 0)
            limit: Maximum number of nodes to return (default: None = all)

        Returns:
            List of nodes as dictionaries

        Raises:
            ValidationException: If node_type is invalid
        """
        # Validate node_type to prevent Cypher injection
        validate_node_type(node_type)

        # Build base query
        if parent_node_id:
            # Get relationship configuration for this node type and parent type
            # If parent_node_type is not provided, match any relationship type (for backwards compatibility)
            if parent_node_type:
                relationship_config = self._get_relationship_config(
                    node_type, parent_node_type
                )
                relationship_type = (
                    relationship_config["from_parent"]
                    if relationship_config
                    else "HAS_VALUE_PROPOSITION"
                )
                relationship_pattern = f"-[:{relationship_type}]->"
            else:
                # Match any relationship type (for ValuePropositions with unknown parent type)
                relationship_pattern = "-->"

            # Query with parent filter - match relationship based on node types
            # Include parent information for nodes that need it
            # Special handling for Account parent nodes which use account_id instead of node_id
            base_query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (parent){relationship_pattern}(node:{node_type})
            WHERE (parent.node_id = $parent_node_id OR parent.account_id = $parent_node_id)
              AND (node)-[:BELONGS_TO]->(acc)
            RETURN DISTINCT node, acc.account_id as account_id,
                   COALESCE(parent.node_id, parent.account_id) as parent_node_id,
                   labels(parent)[0] as parent_node_type
            ORDER BY node.display_name, node.product_name, node.name
            """
        else:
            base_query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (node:{node_type})-[:BELONGS_TO]->(acc)
            RETURN node, acc.account_id as account_id
            ORDER BY node.display_name, node.product_name, node.name
            """

        # Add pagination if limit is specified
        if limit is not None:
            query = f"{base_query} SKIP $skip LIMIT $limit"
            params = {
                "account_id": account_id,
                "parent_node_id": parent_node_id,
                "skip": skip,
                "limit": limit,
            }
        else:
            query = base_query
            params = {"account_id": account_id, "parent_node_id": parent_node_id}

        result = await self.neo4j.execute_query(query, params)

        # Build result with parent information if available
        nodes = []
        for record in result:
            node_dict = {
                **self._neo4j_node_to_dict(record["node"]),
                "account_id": record["account_id"],
            }
            # Add parent information if it exists in the query result
            if record.get("parent_node_id"):
                node_dict["parent_node_id"] = record["parent_node_id"]
            if record.get("parent_node_type"):
                node_dict["parent_node_type"] = record["parent_node_type"]
            nodes.append(node_dict)

        return nodes

    async def get_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
    ) -> dict[str, Any] | None:
        """Generic get operation for any node type.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type label

        Returns:
            Node as dictionary, or None if not found

        Raises:
            ValidationException: If node_type is invalid
        """
        # Validate node_type to prevent Cypher injection
        validate_node_type(node_type)

        # Handle legacy field names for nodes that might use type-specific IDs
        # TODO: Remove this compatibility layer after Neo4j data migration
        legacy_field_map = {
            "Risk": "risk_id",
            "Opportunity": "opportunity_id",
        }
        legacy_field = legacy_field_map.get(node_type)

        # Try node_id first, then fall back to legacy field if applicable
        if legacy_field:
            query = f"""
            MATCH (node:{node_type})
            WHERE (node.node_id = $node_id OR node.{legacy_field} = $node_id)
              AND (node.account_id = $account_id OR (node)-[:BELONGS_TO]->(:Account {{account_id: $account_id}}))
            RETURN node, $account_id as account_id
            LIMIT 1
            """
        else:
            query = f"""
            MATCH (node:{node_type} {{node_id: $node_id}})
            WHERE node.account_id = $account_id OR (node)-[:BELONGS_TO]->(:Account {{account_id: $account_id}})
            RETURN node, $account_id as account_id
            """

        result = await self.neo4j.execute_query(
            query, {"node_id": node_id, "account_id": account_id}
        )

        if not result:
            return None

        node_dict = self._neo4j_node_to_dict(result[0]["node"])

        # Normalize legacy field to node_id if needed
        if legacy_field and "node_id" not in node_dict and legacy_field in node_dict:
            node_dict["node_id"] = node_dict[legacy_field]

        return {
            **node_dict,
            "account_id": result[0]["account_id"],
        }

    async def count_nodes(
        self,
        account_id: str,
        node_type: str,
        parent_node_id: str | None = None,
        parent_node_type: str | None = None,
    ) -> int:
        """Get total count of nodes for accurate pagination.

        This method returns the actual count from the database, not just the count
        of returned results. Essential for proper pagination UI (e.g., "Page 1 of 5").

        Args:
            account_id: Account identifier
            node_type: Node type label
            parent_node_id: Optional filter by parent relationship
            parent_node_type: Optional parent node type (required if parent_node_id is provided)

        Returns:
            Total count of matching nodes in database

        Raises:
            ValidationException: If node_type is invalid
        """
        # Validate node_type to prevent Cypher injection
        validate_node_type(node_type)

        # Build count query based on whether parent filter is used
        if parent_node_id:
            # Get relationship configuration for this node type and parent type
            # If parent_node_type is not provided, match any relationship type (for backwards compatibility)
            if parent_node_type:
                relationship_config = self._get_relationship_config(
                    node_type, parent_node_type
                )
                relationship_type = (
                    relationship_config["from_parent"]
                    if relationship_config
                    else "HAS_VALUE_PROPOSITION"
                )
                relationship_pattern = f"-[:{relationship_type}]->"
            else:
                # Match any relationship type (for ValuePropositions with unknown parent type)
                relationship_pattern = "-->"

            # Special handling for Account parent nodes which use account_id instead of node_id
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (parent){relationship_pattern}(node:{node_type})
            WHERE (parent.node_id = $parent_node_id OR parent.account_id = $parent_node_id)
              AND (node)-[:BELONGS_TO]->(acc)
            RETURN count(DISTINCT node) as total
            """
            params = {"account_id": account_id, "parent_node_id": parent_node_id}
        else:
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (node:{node_type})-[:BELONGS_TO]->(acc)
            RETURN count(node) as total
            """
            params = {"account_id": account_id}

        result = await self.neo4j.execute_query(query, params)
        return result[0]["total"] if result else 0

    # ==================== CONVENIENCE WRAPPERS FOR BUSINESS STRATEGY ====================

    async def create_product_category(
        self,
        account_id: str,
        category: ProductCategoryCreate,
        user_id: str,
    ) -> ProductCategoryResponse:
        """Create a product category.

        Args:
            account_id: Account identifier
            category: Category creation data
            user_id: User creating the category

        Returns:
            Created product category

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If category name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            category.product_name, "product_name"
        )
        if not is_valid:
            raise ValidationException(error, "product_name")

        is_valid, error = self.validation.validate_non_empty_string(
            category.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Check for duplicate name
        is_unique, error = await self.validation.validate_unique_product_category_name(
            account_id, category.product_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "ProductCategory", "product_name", category.product_name, account_id
            )

        node_data = {
            "product_name": category.product_name.strip(),
            "description": category.description.strip(),
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="ProductCategory",
            node_data=node_data,
            parent_node_id=None,  # ProductCategory links directly to Account
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return ProductCategoryResponse(**result)

    async def update_product_category(
        self,
        account_id: str,
        node_id: str,
        updates: ProductCategoryUpdate,
        user_id: str,
    ) -> ProductCategoryResponse:
        """Update a product category.

        Args:
            account_id: Account identifier
            node_id: Category node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated product category
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ProductCategory",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return ProductCategoryResponse(**result)

    async def delete_product_category(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a product category and cascade delete its products and value propositions.

        Args:
            account_id: Account identifier
            node_id: Category node_id
            user_id: User performing deletion
        """
        # First, get all products in this category
        prod_query = """
        MATCH (cat:ProductCategory {node_id: $node_id})-[:INCLUDES_PRODUCT]->(prod:Product)
        RETURN prod.node_id as prod_node_id
        """
        prod_results = await self.neo4j.execute_query(prod_query, {"node_id": node_id})

        # Cascade delete each product (which will in turn delete their VPs)
        for record in prod_results:
            prod_node_id = record["prod_node_id"]
            logger.info(
                f"Cascade deleting product {prod_node_id} from category {node_id}"
            )
            await self.delete_product(account_id, prod_node_id, user_id)

        # Delete value propositions directly linked to the category
        cat_vp_query = """
        MATCH (cat:ProductCategory {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN vp.node_id as vp_node_id
        """
        cat_vp_results = await self.neo4j.execute_query(
            cat_vp_query, {"node_id": node_id}
        )

        # Delete each category-level value proposition
        for record in cat_vp_results:
            vp_node_id = record["vp_node_id"]
            logger.info(
                f"Cascade deleting value proposition {vp_node_id} from category {node_id}"
            )
            await self.delete_value_proposition(account_id, vp_node_id, user_id)

        # Now delete the category itself (no dependency check needed since we cleaned up)
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ProductCategory",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,
        )

    async def create_product(
        self,
        account_id: str,
        product: ProductCreate,
        user_id: str,
    ) -> ProductResponse:
        """Create a product.

        Args:
            account_id: Account identifier
            product: Product creation data
            user_id: User creating the product

        Returns:
            Created product

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If product name already exists in category
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            product.product_name, "product_name"
        )
        if not is_valid:
            raise ValidationException(error, "product_name")

        is_valid, error = self.validation.validate_non_empty_string(
            product.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        if product.product_detail_page and not self.validation.validate_url_format(
            product.product_detail_page
        ):
            raise ValidationException(
                f"Invalid URL format: {product.product_detail_page}",
                "product_detail_page",
            )

        for ref in product.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate name within category
        is_unique, error = await self.validation.validate_unique_product_name(
            account_id, product.product_name.strip(), product.category_node_id
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Product",
                "product_name",
                product.product_name,
                product.category_node_id,
            )

        node_data = {
            "product_name": product.product_name.strip(),
            "description": product.description.strip(),
            "references": product.references,
            "product_detail_page": product.product_detail_page,
            "category_node_id": product.category_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Product",
            node_data=node_data,
            parent_node_id=product.category_node_id,
            parent_node_type="ProductCategory",
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return ProductResponse(**result)

    async def update_product(
        self,
        account_id: str,
        node_id: str,
        updates: ProductUpdate,
        user_id: str,
    ) -> ProductResponse:
        """Update a product.

        Args:
            account_id: Account identifier
            node_id: Product node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated product
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Product",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        # Fetch category_node_id from relationship
        query = """
        MATCH (cat:ProductCategory)-[:INCLUDES_PRODUCT]->(p:Product {node_id: $node_id})
        RETURN cat.node_id as category_node_id
        """

        category_result = await self.neo4j.execute_query(query, {"node_id": node_id})

        if category_result and len(category_result) > 0:
            result["category_node_id"] = category_result[0]["category_node_id"]

        return ProductResponse(**result)

    async def delete_product(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a product and cascade delete its value propositions.

        Args:
            account_id: Account identifier
            node_id: Product node_id
            user_id: User performing deletion
        """
        # First, cascade delete all value propositions linked to this product
        vp_query = """
        MATCH (prod:Product {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN vp.node_id as vp_node_id
        """
        vp_results = await self.neo4j.execute_query(vp_query, {"node_id": node_id})

        # Delete each value proposition
        for record in vp_results:
            vp_node_id = record["vp_node_id"]
            logger.info(
                f"Cascade deleting value proposition {vp_node_id} from product {node_id}"
            )
            await self.delete_value_proposition(account_id, vp_node_id, user_id)

        # Now delete the product itself (no dependency check needed since we cleaned up VPs)
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Product",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,
        )

    async def list_products_with_categories(
        self,
        account_id: str,
        category_node_id: str | None = None,
        substitute_product_node_id: str | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List products with their category information in a single query.

        Optimized to avoid N+1 query problem by using OPTIONAL MATCH to fetch
        category_node_id for all products in one database round-trip.

        Args:
            account_id: Account identifier
            category_node_id: Optional filter by specific category
            substitute_product_node_id: Optional filter by substitute product (MAY_BE_SUBSTITUTED_FOR)
            skip: Number of products to skip (default: 0)
            limit: Maximum number of products to return (default: None = all)

        Returns:
            Tuple of (products_list, total_count)
            Each product dict includes category_node_id from relationship

        Raises:
            ValidationException: If validation fails
        """
        if substitute_product_node_id:
            # Query products that MAY_BE_SUBSTITUTED_FOR this substitute product
            query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (sub:SubstituteProduct {node_id: $substitute_product_node_id})
                  <-[:MAY_BE_SUBSTITUTED_FOR]-(p:Product)-[:BELONGS_TO]->(acc)
            OPTIONAL MATCH (cat:ProductCategory)-[:INCLUDES_PRODUCT]->(p)
            RETURN p as node, acc.account_id as account_id, cat.node_id as category_node_id
            ORDER BY p.product_name
            """
            count_query = """
            MATCH (sub:SubstituteProduct {node_id: $substitute_product_node_id})
                  <-[:MAY_BE_SUBSTITUTED_FOR]-(p:Product)-[:BELONGS_TO]->(:Account {account_id: $account_id})
            RETURN count(p) as total
            """
            count_params = {
                "account_id": account_id,
                "substitute_product_node_id": substitute_product_node_id,
            }
        elif category_node_id:
            # Query products filtered by specific category
            query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (cat:ProductCategory {node_id: $category_node_id})-[:INCLUDES_PRODUCT]->(p:Product)
            WHERE (p)-[:BELONGS_TO]->(acc)
            RETURN p as node, acc.account_id as account_id, cat.node_id as category_node_id
            ORDER BY p.product_name
            """
            count_query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (cat:ProductCategory {node_id: $category_node_id})-[:INCLUDES_PRODUCT]->(p:Product)
            WHERE (p)-[:BELONGS_TO]->(acc)
            RETURN count(p) as total
            """
            count_params = {
                "account_id": account_id,
                "category_node_id": category_node_id,
            }
        else:
            # Query ALL products with OPTIONAL MATCH for category (avoids N+1)
            query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (p:Product)-[:BELONGS_TO]->(acc)
            OPTIONAL MATCH (cat:ProductCategory)-[:INCLUDES_PRODUCT]->(p)
            RETURN p as node, acc.account_id as account_id, cat.node_id as category_node_id
            ORDER BY p.product_name
            """
            count_query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (p:Product)-[:BELONGS_TO]->(acc)
            RETURN count(p) as total
            """
            count_params = {"account_id": account_id}

        # Add pagination if limit is specified
        if limit is not None:
            query += " SKIP $skip LIMIT $limit"
            params = {**count_params, "skip": skip, "limit": limit}
        else:
            params = count_params

        # Execute count query
        count_result = await self.neo4j.execute_query(count_query, count_params)
        total_count = count_result[0]["total"] if count_result else 0

        # Execute main query
        result = await self.neo4j.execute_query(query, params)

        # Build products list with category information
        products = []
        for record in result:
            product_dict = {
                **self._neo4j_node_to_dict(record["node"]),
                "account_id": record["account_id"],
                "category_node_id": record.get("category_node_id", ""),
            }
            products.append(product_dict)

        return products, total_count

    async def create_value_proposition(
        self,
        account_id: str,
        value_prop: ValuePropositionCreate,
        user_id: str,
    ) -> ValuePropositionResponse:
        """Create a value proposition.

        Args:
            account_id: Account identifier
            value_prop: Value proposition creation data
            user_id: User creating the value proposition

        Returns:
            Created value proposition

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            value_prop.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            value_prop.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in value_prop.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "ValueProposition", value_prop.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "ValueProposition", "display_name", value_prop.display_name, account_id
            )

        node_data = {
            "display_name": value_prop.display_name.strip(),
            "description": value_prop.description.strip(),
            "references": value_prop.references,
            "parent_node_id": value_prop.parent_node_id,
            "parent_node_type": value_prop.parent_node_type,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="ValueProposition",
            node_data=node_data,
            parent_node_id=value_prop.parent_node_id,
            parent_node_type=value_prop.parent_node_type,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return ValuePropositionResponse(**result)

    async def update_value_proposition(
        self,
        account_id: str,
        node_id: str,
        updates: ValuePropositionUpdate,
        user_id: str,
    ) -> ValuePropositionResponse:
        """Update a value proposition.

        Args:
            account_id: Account identifier
            node_id: ValueProposition node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated value proposition
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ValueProposition",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return ValuePropositionResponse(**result)

    async def delete_value_proposition(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a value proposition.

        Args:
            account_id: Account identifier
            node_id: ValueProposition node_id
            user_id: User performing deletion
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ValueProposition",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,  # No dependencies
        )

    async def create_strength(
        self,
        account_id: str,
        strength: StrengthCreate,
        user_id: str,
    ) -> StrengthResponse:
        """Create a strength.

        Args:
            account_id: Account identifier
            strength: Strength creation data
            user_id: User creating the strength

        Returns:
            Created strength

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            strength.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            strength.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in strength.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "Strength", strength.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Strength", "display_name", strength.display_name, account_id
            )

        # Ensure SWOT Analysis hub exists
        swot_node_id = await self.validation.get_or_create_swot_hub(account_id, user_id)

        node_data = {
            "display_name": strength.display_name.strip(),
            "description": strength.description.strip(),
            "references": strength.references,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Strength",
            node_data=node_data,
            parent_node_id=swot_node_id,
            parent_node_type="SWOTAnalysis",
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return StrengthResponse(**result)

    async def update_strength(
        self,
        account_id: str,
        node_id: str,
        updates: StrengthUpdate,
        user_id: str,
    ) -> StrengthResponse:
        """Update a strength.

        Args:
            account_id: Account identifier
            node_id: Strength node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated strength
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Strength",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return StrengthResponse(**result)

    async def delete_strength(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a strength.

        Args:
            account_id: Account identifier
            node_id: Strength node_id
            user_id: User performing deletion

        Raises:
            ValueError: If strength has linked opportunities
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Strength",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=True,
        )

    async def create_weakness(
        self,
        account_id: str,
        weakness: WeaknessCreate,
        user_id: str,
    ) -> WeaknessResponse:
        """Create a weakness.

        Args:
            account_id: Account identifier
            weakness: Weakness creation data
            user_id: User creating the weakness

        Returns:
            Created weakness

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            weakness.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            weakness.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in weakness.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "Weakness", weakness.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Weakness", "display_name", weakness.display_name, account_id
            )

        # Ensure SWOT Analysis hub exists
        swot_node_id = await self.validation.get_or_create_swot_hub(account_id, user_id)

        node_data = {
            "display_name": weakness.display_name.strip(),
            "description": weakness.description.strip(),
            "references": weakness.references,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Weakness",
            node_data=node_data,
            parent_node_id=swot_node_id,
            parent_node_type="SWOTAnalysis",
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return WeaknessResponse(**result)

    async def update_weakness(
        self,
        account_id: str,
        node_id: str,
        updates: WeaknessUpdate,
        user_id: str,
    ) -> WeaknessResponse:
        """Update a weakness.

        Args:
            account_id: Account identifier
            node_id: Weakness node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated weakness
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Weakness",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return WeaknessResponse(**result)

    async def delete_weakness(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a weakness.

        Args:
            account_id: Account identifier
            node_id: Weakness node_id
            user_id: User performing deletion

        Raises:
            ValueError: If weakness has linked risks
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Weakness",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=True,
        )

    async def create_opportunity(
        self,
        account_id: str,
        opportunity: OpportunityCreate,
        user_id: str,
    ) -> OpportunityResponse:
        """Create an opportunity.

        Args:
            account_id: Account identifier
            opportunity: Opportunity creation data
            user_id: User creating the opportunity

        Returns:
            Created opportunity

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
            NodeNotFoundException: If parent strength doesn't exist
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            opportunity.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            opportunity.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in opportunity.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "Opportunity", opportunity.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Opportunity", "display_name", opportunity.display_name, account_id
            )

        # Determine parent node and type (Strength or CompetitorWeakness)
        if opportunity.strength_node_id:
            parent_node_id = opportunity.strength_node_id
            parent_node_type = "Strength"
            parent_field_name = "strength_node_id"
        else:
            parent_node_id = opportunity.weakness_node_id
            parent_node_type = "CompetitorWeakness"
            parent_field_name = "weakness_node_id"

        node_data = {
            "display_name": opportunity.display_name.strip(),
            "description": opportunity.description.strip(),
            "references": opportunity.references,
            parent_field_name: parent_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Opportunity",
            node_data=node_data,
            parent_node_id=parent_node_id,
            parent_node_type=parent_node_type,
            user_id=user_id,
            firestore_doc_type="business_strategy"
            if opportunity.strength_node_id
            else "competitive_strategy",
        )

        return OpportunityResponse(**result)

    async def update_opportunity(
        self,
        account_id: str,
        node_id: str,
        updates: OpportunityUpdate,
        user_id: str,
    ) -> OpportunityResponse:
        """Update an opportunity.

        Args:
            account_id: Account identifier
            node_id: Opportunity node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated opportunity
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Opportunity",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        # Handle legacy data: map opportunity_id to node_id if needed
        if "node_id" not in result and "opportunity_id" in result:
            result["node_id"] = result["opportunity_id"]

        # Fetch the parent relationship (could be Strength or CompetitorWeakness)
        # Handle both node_id and legacy opportunity_id field
        parent_query = """
        MATCH (parent)-[:CREATES]->(o:Opportunity)
        WHERE (o.node_id = $node_id OR o.opportunity_id = $node_id)
          AND (parent:Strength OR parent:CompetitorWeakness)
        RETURN parent.node_id as parent_node_id, labels(parent) as parent_labels
        LIMIT 1
        """
        parent_result = await self.neo4j.execute_query(
            parent_query, {"node_id": node_id}
        )
        if parent_result and parent_result[0]:
            parent_labels = parent_result[0]["parent_labels"]
            if "Strength" in parent_labels:
                result["strength_node_id"] = parent_result[0]["parent_node_id"]
                result["weakness_node_id"] = None
            elif "CompetitorWeakness" in parent_labels:
                result["weakness_node_id"] = parent_result[0]["parent_node_id"]
                result["strength_node_id"] = None

        return OpportunityResponse(**result)

    async def delete_opportunity(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete an opportunity.

        Args:
            account_id: Account identifier
            node_id: Opportunity node_id
            user_id: User performing deletion
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Opportunity",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,
        )

    async def create_risk(
        self,
        account_id: str,
        risk: RiskCreate,
        user_id: str,
    ) -> RiskResponse:
        """Create a risk.

        Args:
            account_id: Account identifier
            risk: Risk creation data
            user_id: User creating the risk

        Returns:
            Created risk

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
            NodeNotFoundException: If parent weakness doesn't exist
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            risk.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            risk.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in risk.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "Risk", risk.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Risk", "display_name", risk.display_name, account_id
            )

        # Determine parent node and type (Weakness or CompetitorStrength)
        if risk.weakness_node_id:
            parent_node_id = risk.weakness_node_id
            parent_node_type = "Weakness"
            parent_field_name = "weakness_node_id"
        else:
            parent_node_id = risk.strength_node_id
            parent_node_type = "CompetitorStrength"
            parent_field_name = "strength_node_id"

        node_data = {
            "display_name": risk.display_name.strip(),
            "description": risk.description.strip(),
            "references": risk.references,
            parent_field_name: parent_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Risk",
            node_data=node_data,
            parent_node_id=parent_node_id,
            parent_node_type=parent_node_type,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return RiskResponse(**result)

    async def update_risk(
        self,
        account_id: str,
        node_id: str,
        updates: RiskUpdate,
        user_id: str,
    ) -> RiskResponse:
        """Update a risk.

        Args:
            account_id: Account identifier
            node_id: Risk node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated risk
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Risk",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        # Handle legacy data: map risk_id to node_id if needed
        if "node_id" not in result and "risk_id" in result:
            result["node_id"] = result["risk_id"]

        # Fetch the parent relationship (either Weakness or CompetitorStrength)
        # Risks can be created by:
        # - Weakness nodes (business SWOT)
        # - CompetitorStrength nodes (competitive analysis)
        # Handle both node_id and legacy risk_id field
        parent_query = """
        MATCH (parent)-[:CREATES]->(r:Risk)
        WHERE (r.node_id = $node_id OR r.risk_id = $node_id)
          AND (parent:Weakness OR parent:CompetitorStrength)
        RETURN parent.node_id as parent_node_id, labels(parent) as parent_labels
        LIMIT 1
        """
        parent_result = await self.neo4j.execute_query(
            parent_query, {"node_id": node_id}
        )
        if parent_result and parent_result[0]:
            parent_labels = parent_result[0]["parent_labels"]
            if "Weakness" in parent_labels:
                result["weakness_node_id"] = parent_result[0]["parent_node_id"]
                result["strength_node_id"] = None
            elif "CompetitorStrength" in parent_labels:
                result["strength_node_id"] = parent_result[0]["parent_node_id"]
                result["weakness_node_id"] = None

        return RiskResponse(**result)

    async def delete_risk(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a risk.

        Args:
            account_id: Account identifier
            node_id: Risk node_id
            user_id: User performing deletion
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Risk",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,
        )

    async def create_goal(
        self,
        account_id: str,
        goal: GoalCreate,
        user_id: str,
    ) -> GoalResponse:
        """Create a strategic goal.

        Args:
            account_id: Account identifier
            goal: Goal creation data
            user_id: User creating the goal

        Returns:
            Created goal

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            goal.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            goal.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate URLs
        for ref in goal.references:
            if not self.validation.validate_url_format(ref):
                raise ValidationException(
                    f"Invalid URL format in references: {ref}", "references"
                )

        # Check for duplicate display_name
        is_unique, error = await self.validation.validate_unique_display_name(
            account_id, "Goal", goal.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "Goal", "display_name", goal.display_name, account_id
            )

        node_data = {
            "display_name": goal.display_name.strip(),
            "description": goal.description.strip(),
            "references": goal.references,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Goal",
            node_data=node_data,
            parent_node_id=None,  # Goals link directly to Account
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return GoalResponse(**result)

    async def update_goal(
        self,
        account_id: str,
        node_id: str,
        updates: GoalUpdate,
        user_id: str,
    ) -> GoalResponse:
        """Update a goal.

        Args:
            account_id: Account identifier
            node_id: Goal node_id
            updates: Updates to apply
            user_id: User performing update

        Returns:
            Updated goal
        """
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Goal",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="business_strategy",
        )

        return GoalResponse(**result)

    async def delete_goal(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a goal.

        Args:
            account_id: Account identifier
            node_id: Goal node_id
            user_id: User performing deletion
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Goal",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=False,
        )

    # ==================== CONVENIENCE WRAPPERS FOR COMPETITIVE STRATEGY ====================
    # Steps 2 & 3 Implementation

    async def create_competitive_environment(
        self,
        account_id: str,
        env: CompetitiveEnvironmentCreate,
        user_id: str,
    ) -> CompetitiveEnvironmentResponse:
        """Create or update competitive environment hub node.

        CompetitiveEnvironment is a hub node - only one per account is allowed.
        If one exists, it will be updated; otherwise, a new one is created.

        Args:
            account_id: Account identifier
            env: Environment creation data
            user_id: User creating the environment

        Returns:
            Created or updated competitive environment
        """
        # Check if competitive environment already exists
        existing = await self.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )

        if existing:
            # Update existing
            existing_node_id = existing[0]["node_id"]
            return await self.update_competitive_environment(
                account_id=account_id,
                node_id=existing_node_id,
                updates=CompetitiveEnvironmentUpdate(**env.model_dump()),
                user_id=user_id,
            )

        # Create new
        node_data = {"description": env.description.strip()}

        result = await self.create_node(
            account_id=account_id,
            node_type="CompetitiveEnvironment",
            node_data=node_data,
            parent_node_id=None,  # Links to Account
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitiveEnvironmentResponse(**result)

    async def update_competitive_environment(
        self,
        account_id: str,
        node_id: str,
        updates: CompetitiveEnvironmentUpdate,
        user_id: str,
    ) -> CompetitiveEnvironmentResponse:
        """Update competitive environment."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitiveEnvironment",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitiveEnvironmentResponse(**result)

    async def create_competitor(
        self,
        account_id: str,
        competitor: CompetitorCreate,
        user_id: str,
    ) -> CompetitorResponse:
        """Create a competitor node.

        Args:
            account_id: Account identifier
            competitor: Competitor creation data
            user_id: User creating the competitor

        Returns:
            Created competitor

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If competitor name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            competitor.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            competitor.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate competitor limit
        from ..constants import MAX_COMPETITORS_PER_ACCOUNT

        current_count = await self.count_nodes(account_id, "Competitor")
        if current_count >= MAX_COMPETITORS_PER_ACCOUNT:
            raise ValidationException(
                f"Maximum of {MAX_COMPETITORS_PER_ACCOUNT} competitors allowed per account. "
                "Please delete an existing competitor before adding a new one.",
                "account_id",
            )

        # Ensure CompetitiveEnvironment hub exists
        comp_envs = await self.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        if not comp_envs:
            # Auto-create hub if it doesn't exist
            await self.create_competitive_environment(
                account_id=account_id,
                env=CompetitiveEnvironmentCreate(
                    description="Competitive environment for tracking key competitors and market analysis."
                ),
                user_id=user_id,
            )

        node_data = {
            "display_name": competitor.display_name.strip(),
            "description": competitor.description.strip(),
            "references": competitor.references,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Competitor",
            node_data=node_data,
            parent_node_id=None,  # Competitor links to CompetitiveEnvironment via IS_KEY_PLAYER in _create_node_neo4j
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorResponse(**result)

    async def update_competitor(
        self,
        account_id: str,
        node_id: str,
        updates: CompetitorUpdate,
        user_id: str,
    ) -> CompetitorResponse:
        """Update a competitor."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Competitor",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorResponse(**result)

    async def delete_competitor(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
        cascade: bool = False,
    ) -> None:
        """Delete a competitor.

        Args:
            account_id: Account identifier
            node_id: Competitor node_id
            user_id: User performing deletion
            cascade: If True, cascade delete all dependent entities
        """
        if cascade:
            await self.delete_competitor_cascade(account_id, node_id, user_id)
        else:
            # Existing behavior - fail if dependencies exist
            await self.delete_node(
                account_id=account_id,
                node_id=node_id,
                node_type="Competitor",
                user_id=user_id,
                firestore_doc_type="competitive_strategy",
                check_dependencies=True,
            )

    async def delete_competitor_cascade(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a competitor and cascade delete all dependent entities.

        Deletes in this order:
        1. Risks (from CompetitorStrengths)
        2. CompetitorStrengths
        3. Opportunities (from CompetitorWeaknesses)
        4. CompetitorWeaknesses
        5. ValuePropositions (from SubstituteProducts)
        6. SubstituteProducts (unlinks Products)
        7. CompetitorTactics
        8. ValuePropositions directly linked to Competitor
        9. Competitor node itself
        """
        # 1. Delete all risks (from strengths) first
        risk_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_STRENGTH]->(cs:CompetitorStrength)-[:CREATES]->(r:Risk)
        RETURN r.node_id as risk_node_id
        """
        risk_results = await self.neo4j.execute_query(risk_query, {"node_id": node_id})

        for record in risk_results:
            risk_node_id = record["risk_node_id"]
            if risk_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting risk {risk_node_id} from competitor {node_id}"
                )
                await self.delete_risk(account_id, risk_node_id, user_id)

        # 2. Delete all strengths (now that risks are gone)
        strength_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_STRENGTH]->(cs:CompetitorStrength)
        RETURN cs.node_id as strength_node_id
        """
        strength_results = await self.neo4j.execute_query(
            strength_query, {"node_id": node_id}
        )

        for record in strength_results:
            strength_node_id = record["strength_node_id"]
            if strength_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting strength {strength_node_id} from competitor {node_id}"
                )
                # Use delete_node directly with check_dependencies=False since we already deleted risks
                await self.delete_node(
                    account_id=account_id,
                    node_id=strength_node_id,
                    node_type="CompetitorStrength",
                    user_id=user_id,
                    firestore_doc_type="competitive_strategy",
                    check_dependencies=False,
                )

        # 3. Delete all opportunities (from weaknesses) first
        opportunity_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_WEAKNESS]->(cw:CompetitorWeakness)-[:CREATES]->(o:Opportunity)
        RETURN o.node_id as opportunity_node_id
        """
        opportunity_results = await self.neo4j.execute_query(
            opportunity_query, {"node_id": node_id}
        )

        for record in opportunity_results:
            opportunity_node_id = record["opportunity_node_id"]
            if opportunity_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting opportunity {opportunity_node_id} from competitor {node_id}"
                )
                await self.delete_opportunity(account_id, opportunity_node_id, user_id)

        # 4. Delete all weaknesses (now that opportunities are gone)
        weakness_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_WEAKNESS]->(cw:CompetitorWeakness)
        RETURN cw.node_id as weakness_node_id
        """
        weakness_results = await self.neo4j.execute_query(
            weakness_query, {"node_id": node_id}
        )

        for record in weakness_results:
            weakness_node_id = record["weakness_node_id"]
            if weakness_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting weakness {weakness_node_id} from competitor {node_id}"
                )
                # Use delete_node directly with check_dependencies=False since we already deleted opportunities
                await self.delete_node(
                    account_id=account_id,
                    node_id=weakness_node_id,
                    node_type="CompetitorWeakness",
                    user_id=user_id,
                    firestore_doc_type="competitive_strategy",
                    check_dependencies=False,
                )

        # 5. Delete all value propositions from substitute products first
        sub_vp_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:OFFERS_PRODUCT]->(sp:SubstituteProduct)-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN vp.node_id as vp_node_id
        """
        sub_vp_results = await self.neo4j.execute_query(
            sub_vp_query, {"node_id": node_id}
        )

        for record in sub_vp_results:
            vp_node_id = record["vp_node_id"]
            if vp_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting value proposition {vp_node_id} from substitute product"
                )
                await self.delete_value_proposition(account_id, vp_node_id, user_id)

        # 6. Delete all substitute products (now that their VPs are gone, unlink products)
        substitute_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:OFFERS_PRODUCT]->(sp:SubstituteProduct)
        RETURN sp.node_id as substitute_node_id
        """
        substitute_results = await self.neo4j.execute_query(
            substitute_query, {"node_id": node_id}
        )

        for record in substitute_results:
            substitute_node_id = record["substitute_node_id"]
            if substitute_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting substitute product {substitute_node_id} from competitor {node_id}"
                )
                # Use delete_node directly with check_dependencies=False since we already deleted VPs
                await self.delete_node(
                    account_id=account_id,
                    node_id=substitute_node_id,
                    node_type="SubstituteProduct",
                    user_id=user_id,
                    firestore_doc_type="competitive_strategy",
                    check_dependencies=False,
                )

        # 7. Delete all tactics
        tactic_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:USES_TACTIC]->(ct:CompetitorTactic)
        RETURN ct.node_id as tactic_node_id
        """
        tactic_results = await self.neo4j.execute_query(
            tactic_query, {"node_id": node_id}
        )

        for record in tactic_results:
            tactic_node_id = record["tactic_node_id"]
            if tactic_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting tactic {tactic_node_id} from competitor {node_id}"
                )
                await self.delete_competitor_tactic(account_id, tactic_node_id, user_id)

        # 8. Delete value propositions directly linked to competitor
        vp_query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN vp.node_id as vp_node_id
        """
        vp_results = await self.neo4j.execute_query(vp_query, {"node_id": node_id})

        for record in vp_results:
            vp_node_id = record["vp_node_id"]
            if vp_node_id:  # Skip None values
                logger.info(
                    f"Cascade deleting value proposition {vp_node_id} from competitor {node_id}"
                )
                await self.delete_value_proposition(account_id, vp_node_id, user_id)

        # 9. Finally, delete the competitor itself (no dependency check needed)
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Competitor",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
            check_dependencies=False,  # We already cascaded the dependencies
        )

        # 10. Delete associated monitoring keywords from Firestore
        try:
            # Get monitoring topics document
            doc = self.firestore.get_document(
                collection="monitoring_topics", document_id=account_id
            )

            if doc and "competitor_entries" in doc:
                competitors = doc["competitor_entries"]

                # Find and remove the entry matching this competitor's node_id
                updated_competitors = [
                    entry for entry in competitors if entry.get("node_id") != node_id
                ]

                # Only update if we actually removed something
                if len(updated_competitors) < len(competitors):
                    from datetime import datetime

                    self.firestore.update_document(
                        collection="monitoring_topics",
                        document_id=account_id,
                        data={
                            "competitor_entries": updated_competitors,
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    )
        except Exception as e:
            # Log but don't fail the deletion if monitoring keywords cleanup fails
            logger.warning(
                f"Failed to delete monitoring keywords for competitor {node_id}: {e}"
            )

    async def create_competitor_tactic(
        self,
        account_id: str,
        tactic: CompetitorTacticCreate,
        user_id: str,
    ) -> CompetitorTacticResponse:
        """Create a competitor tactic node."""
        is_valid, error = self.validation.validate_non_empty_string(
            tactic.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        # Validate tactics limit per competitor
        from ..constants import MAX_TACTICS_PER_COMPETITOR

        current_count = await self.count_nodes(
            account_id, "CompetitorTactic", parent_node_id=tactic.competitor_node_id
        )
        if current_count >= MAX_TACTICS_PER_COMPETITOR:
            raise ValidationException(
                f"Maximum of {MAX_TACTICS_PER_COMPETITOR} tactics allowed per competitor. "
                "Please delete an existing tactic before adding a new one.",
                "competitor_node_id",
            )

        node_data = {
            "display_name": tactic.display_name.strip(),
            "description": tactic.description.strip(),
            "references": tactic.references,
            "competitor_node_id": tactic.competitor_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="CompetitorTactic",
            node_data=node_data,
            parent_node_id=tactic.competitor_node_id,
            parent_node_type="Competitor",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorTacticResponse(**result)

    async def update_competitor_tactic(
        self,
        account_id: str,
        node_id: str,
        updates: CompetitorTacticUpdate,
        user_id: str,
    ) -> CompetitorTacticResponse:
        """Update a competitor tactic."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorTactic",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorTacticResponse(**result)

    async def delete_competitor_tactic(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a competitor tactic."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorTactic",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
            check_dependencies=False,
        )

    async def create_competitor_strength(
        self,
        account_id: str,
        strength: CompetitorStrengthCreate,
        user_id: str,
    ) -> CompetitorStrengthResponse:
        """Create a competitor strength node."""
        is_valid, error = self.validation.validate_non_empty_string(
            strength.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        # Validate strengths limit per competitor
        from ..constants import MAX_STRENGTHS_PER_COMPETITOR

        current_count = await self.count_nodes(
            account_id, "CompetitorStrength", parent_node_id=strength.competitor_node_id
        )
        if current_count >= MAX_STRENGTHS_PER_COMPETITOR:
            raise ValidationException(
                f"Maximum of {MAX_STRENGTHS_PER_COMPETITOR} strengths allowed per competitor. "
                "Please delete an existing strength before adding a new one.",
                "competitor_node_id",
            )

        node_data = {
            "display_name": strength.display_name.strip(),
            "description": strength.description.strip(),
            "references": strength.references,
            "competitor_node_id": strength.competitor_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="CompetitorStrength",
            node_data=node_data,
            parent_node_id=strength.competitor_node_id,
            parent_node_type="Competitor",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorStrengthResponse(**result)

    async def update_competitor_strength(
        self,
        account_id: str,
        node_id: str,
        updates: CompetitorStrengthUpdate,
        user_id: str,
    ) -> CompetitorStrengthResponse:
        """Update a competitor strength."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorStrength",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorStrengthResponse(**result)

    async def delete_competitor_strength(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a competitor strength (validates no dependent risks exist)."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorStrength",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
            check_dependencies=True,
        )

    async def create_competitor_weakness(
        self,
        account_id: str,
        weakness: CompetitorWeaknessCreate,
        user_id: str,
    ) -> CompetitorWeaknessResponse:
        """Create a competitor weakness node."""
        is_valid, error = self.validation.validate_non_empty_string(
            weakness.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        # Validate weaknesses limit per competitor
        from ..constants import MAX_WEAKNESSES_PER_COMPETITOR

        current_count = await self.count_nodes(
            account_id, "CompetitorWeakness", parent_node_id=weakness.competitor_node_id
        )
        if current_count >= MAX_WEAKNESSES_PER_COMPETITOR:
            raise ValidationException(
                f"Maximum of {MAX_WEAKNESSES_PER_COMPETITOR} weaknesses allowed per competitor. "
                "Please delete an existing weakness before adding a new one.",
                "competitor_node_id",
            )

        node_data = {
            "display_name": weakness.display_name.strip(),
            "description": weakness.description.strip(),
            "references": weakness.references,
            "competitor_node_id": weakness.competitor_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="CompetitorWeakness",
            node_data=node_data,
            parent_node_id=weakness.competitor_node_id,
            parent_node_type="Competitor",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorWeaknessResponse(**result)

    async def update_competitor_weakness(
        self,
        account_id: str,
        node_id: str,
        updates: CompetitorWeaknessUpdate,
        user_id: str,
    ) -> CompetitorWeaknessResponse:
        """Update a competitor weakness."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorWeakness",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return CompetitorWeaknessResponse(**result)

    async def delete_competitor_weakness(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a competitor weakness (validates no dependent opportunities exist)."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CompetitorWeakness",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
            check_dependencies=True,
        )

    async def create_substitute_product(
        self,
        account_id: str,
        product: SubstituteProductCreate,
        user_id: str,
    ) -> SubstituteProductResponse:
        """Create a substitute product node."""
        is_valid, error = self.validation.validate_non_empty_string(
            product.product_name, "product_name"
        )
        if not is_valid:
            raise ValidationException(error, "product_name")

        # Validate substitute products limit per competitor
        from ..constants import MAX_SUBSTITUTE_PRODUCTS_PER_COMPETITOR

        current_count = await self.count_nodes(
            account_id, "SubstituteProduct", parent_node_id=product.competitor_node_id
        )
        if current_count >= MAX_SUBSTITUTE_PRODUCTS_PER_COMPETITOR:
            raise ValidationException(
                f"Maximum of {MAX_SUBSTITUTE_PRODUCTS_PER_COMPETITOR} substitute products allowed per competitor. "
                "Please delete an existing product before adding a new one.",
                "competitor_node_id",
            )

        node_data = {
            "product_name": product.product_name.strip(),
            "description": product.description.strip(),
            "references": product.references,
            "product_detail_page": product.product_detail_page,
            "competitor_node_id": product.competitor_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="SubstituteProduct",
            node_data=node_data,
            parent_node_id=product.competitor_node_id,
            parent_node_type="Competitor",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return SubstituteProductResponse(**result)

    async def update_substitute_product(
        self,
        account_id: str,
        node_id: str,
        updates: SubstituteProductUpdate,
        user_id: str,
    ) -> SubstituteProductResponse:
        """Update a substitute product."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="SubstituteProduct",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
        )

        return SubstituteProductResponse(**result)

    async def delete_substitute_product(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a substitute product (validates no dependent value propositions exist)."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="SubstituteProduct",
            user_id=user_id,
            firestore_doc_type="competitive_strategy",
            check_dependencies=True,
        )

    async def link_product_to_substitute(
        self,
        account_id: str,
        product_node_id: str,
        substitute_product_node_id: str,
    ) -> None:
        """Create MAY_BE_SUBSTITUTED_FOR relationship between Product and SubstituteProduct.

        Args:
            account_id: Account identifier
            product_node_id: Node ID of the Product
            substitute_product_node_id: Node ID of the SubstituteProduct

        Raises:
            ValidationException: If validation fails
        """
        query = """
        MATCH (p:Product {node_id: $product_node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
        MATCH (s:SubstituteProduct {node_id: $substitute_product_node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
        MERGE (p)-[:MAY_BE_SUBSTITUTED_FOR]->(s)
        RETURN p, s
        """
        params = {
            "account_id": account_id,
            "product_node_id": product_node_id,
            "substitute_product_node_id": substitute_product_node_id,
        }

        result = await self.neo4j.execute_write_query(query, params)
        if not result:
            raise ValidationException(
                "Product or SubstituteProduct not found",
                "product_node_id or substitute_product_node_id",
            )

    async def unlink_product_from_substitute(
        self,
        account_id: str,
        product_node_id: str,
        substitute_product_node_id: str,
    ) -> None:
        """Remove MAY_BE_SUBSTITUTED_FOR relationship between Product and SubstituteProduct.

        Args:
            account_id: Account identifier
            product_node_id: Node ID of the Product
            substitute_product_node_id: Node ID of the SubstituteProduct

        Raises:
            ValidationException: If validation fails
        """
        query = """
        MATCH (p:Product {node_id: $product_node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
        MATCH (s:SubstituteProduct {node_id: $substitute_product_node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
        MATCH (p)-[r:MAY_BE_SUBSTITUTED_FOR]->(s)
        DELETE r
        RETURN p, s
        """
        params = {
            "account_id": account_id,
            "product_node_id": product_node_id,
            "substitute_product_node_id": substitute_product_node_id,
        }

        result = await self.neo4j.execute_write_query(query, params)
        if not result:
            raise ValidationException(
                "Relationship not found or nodes do not exist",
                "product_node_id or substitute_product_node_id",
            )

    # ==================== CONVENIENCE WRAPPERS FOR MARKETING STRATEGY ====================
    # Steps 4 & 5 Implementation

    async def create_customer_profile(
        self,
        account_id: str,
        profile: CustomerProfileCreate,
        user_id: str,
    ) -> CustomerProfileResponse:
        """Create a customer profile node.

        Note: Strategy nodes are NOT auto-created. They must be created separately
        when linking the profile to a ProductCategory.

        Args:
            account_id: Account identifier
            profile: Profile creation data
            user_id: User creating the profile

        Returns:
            Created customer profile

        Raises:
            ValidationException: If validation fails
            DuplicateNodeException: If display_name already exists
        """
        # Validate non-empty strings
        is_valid, error = self.validation.validate_non_empty_string(
            profile.display_name, "display_name"
        )
        if not is_valid:
            raise ValidationException(error, "display_name")

        is_valid, error = self.validation.validate_non_empty_string(
            profile.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Check for duplicate display_name (case-insensitive)
        is_unique, error = await self.validation.validate_unique_customer_profile_name(
            account_id, profile.display_name.strip()
        )
        if not is_unique:
            raise DuplicateNodeException(
                "CustomerProfile", "display_name", profile.display_name, account_id
            )

        node_data = {
            "display_name": profile.display_name.strip().lower(),  # Store lowercase for case-insensitive matching
            "description": profile.description.strip(),
            "references": profile.references,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="CustomerProfile",
            node_data=node_data,
            parent_node_id=None,  # Links directly to Account
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return CustomerProfileResponse(**result)

    async def update_customer_profile(
        self,
        account_id: str,
        node_id: str,
        updates: CustomerProfileUpdate,
        user_id: str,
    ) -> CustomerProfileResponse:
        """Update a customer profile."""
        update_dict = updates.model_dump(exclude_unset=True)

        # If updating display_name, convert to lowercase
        if "display_name" in update_dict:
            update_dict["display_name"] = update_dict["display_name"].strip().lower()

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CustomerProfile",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return CustomerProfileResponse(**result)

    async def delete_customer_profile(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a customer profile with cascade deletion of linked strategy nodes.

        This will:
        1. Delete all marketing strategy nodes linked to this profile (across all ProductCategories)
        2. Delete all IS_MARKETED_TO relationships
        3. Delete the CustomerProfile node
        4. Delete associated monitoring keywords from Firestore

        Args:
            account_id: Account identifier
            node_id: CustomerProfile node_id
            user_id: User performing deletion
        """
        # Delete all linked strategy nodes
        strategy_types = [
            "ProblemAwarenessStrategy",
            "BrandAwarenessStrategy",
            "ConsiderationStrategy",
            "ConversionStrategy",
            "LoyaltyStrategy",
        ]

        for strategy_type in strategy_types:
            # Find all strategies linked to this profile
            query = f"""
            MATCH (cp:CustomerProfile {{node_id: $profile_id}})-[]->(s:{strategy_type})
            WHERE (s)-[:BELONGS_TO]->(:Account {{account_id: $account_id}})
            RETURN s.node_id as node_id
            """
            strategies = await self.neo4j.execute_query(
                query, {"profile_id": node_id, "account_id": account_id}
            )

            # Delete each strategy
            for strategy in strategies:
                strategy_node_id = strategy["node_id"]
                await self.delete_node(
                    account_id=account_id,
                    node_id=strategy_node_id,
                    node_type=strategy_type,
                    user_id=user_id,
                    firestore_doc_type="marketing_strategy",
                    check_dependencies=False,  # No dependencies to check for strategy nodes
                )

        # Then delete the profile (IS_MARKETED_TO relationships will be auto-deleted by DETACH DELETE)
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="CustomerProfile",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,  # We already cascaded the dependencies
        )

        # Finally, delete associated monitoring keywords from Firestore
        try:
            # Get monitoring topics document
            doc = self.firestore.get_document(
                collection="monitoring_topics", document_id=account_id
            )

            if doc and "customer_profile_entries" in doc:
                customer_profiles = doc["customer_profile_entries"]

                # Find and remove the entry matching this profile's node_id
                updated_profiles = [
                    entry
                    for entry in customer_profiles
                    if entry.get("node_id") != node_id
                ]

                # Only update if we actually removed something
                if len(updated_profiles) < len(customer_profiles):
                    from datetime import datetime

                    self.firestore.update_document(
                        collection="monitoring_topics",
                        document_id=account_id,
                        data={
                            "customer_profile_entries": updated_profiles,
                            "updated_at": datetime.utcnow().isoformat(),
                        },
                    )
        except Exception as e:
            # Log but don't fail the deletion if monitoring keywords cleanup fails
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to delete monitoring keywords for customer profile {node_id}: {e}"
            )

    async def link_product_category_to_customer_profile(
        self,
        account_id: str,
        customer_profile_id: str,
        product_category_id: str,
        user_id: str,
    ) -> None:
        """Link a product category to a customer profile via IS_MARKETED_TO relationship.

        Args:
            account_id: Account identifier
            customer_profile_id: CustomerProfile node_id
            product_category_id: ProductCategory node_id
            user_id: User performing the operation
        """
        # Validate both nodes exist
        if not await self.validation.validate_node_exists(
            customer_profile_id, "CustomerProfile"
        ):
            raise ValidationException(
                f"CustomerProfile {customer_profile_id} not found",
                "customer_profile_id",
            )

        if not await self.validation.validate_node_exists(
            product_category_id, "ProductCategory"
        ):
            raise ValidationException(
                f"ProductCategory {product_category_id} not found",
                "product_category_id",
            )

        # Create IS_MARKETED_TO relationship
        query = """
        MATCH (pc:ProductCategory {node_id: $product_category_id})
        MATCH (cp:CustomerProfile {node_id: $customer_profile_id})
        WHERE (pc)-[:BELONGS_TO]->(:Account {account_id: $account_id})
          AND (cp)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        MERGE (pc)-[:IS_MARKETED_TO]->(cp)
        RETURN pc, cp
        """

        result = await self.neo4j.execute_write_query(
            query,
            {
                "product_category_id": product_category_id,
                "customer_profile_id": customer_profile_id,
                "account_id": account_id,
            },
        )

        if not result:
            raise ValidationException(
                "Failed to create IS_MARKETED_TO relationship. Nodes may not belong to this account.",
                "relationship",
            )

        # Auto-create all 5 marketing strategy nodes with placeholder descriptions
        strategy_configs = [
            (
                "ProblemAwarenessStrategy",
                "problemaware_",
                "DISCOVERS_THE_PROBLEM_BY",
                "HAS_PROBLEM_AWARENESS_STRATEGY",
            ),
            (
                "BrandAwarenessStrategy",
                "brandaware_",
                "DISCOVERS_OUR_BRAND_BY",
                "HAS_BRAND_AWARENESS_STRATEGY",
            ),
            (
                "ConsiderationStrategy",
                "consideration_",
                "CONSIDERS_OUR_BRAND_BECAUSE",
                "HAS_CONSIDERATION_STRATEGY",
            ),
            (
                "ConversionStrategy",
                "conversion_",
                "PURCHASES_OUR_BRAND_BECAUSE",
                "HAS_CONVERSION_STRATEGY",
            ),
            (
                "LoyaltyStrategy",
                "loyalty_",
                "BECOMES_AN_ADVOCATE_BECAUSE",
                "HAS_LOYALTY_STRATEGY",
            ),
        ]

        for node_type, prefix, profile_rel, category_rel in strategy_configs:
            node_id = f"{prefix}{product_category_id}_{customer_profile_id}"

            node_data = {
                "description": "No description provided yet. Click edit to add your strategy.",
                "references": [],
                "customer_profile_node_id": customer_profile_id,
                "product_category_node_id": product_category_id,
            }

            await self._create_marketing_strategy_node(
                node_id=node_id,
                node_type=node_type,
                node_data=node_data,
                account_id=account_id,
                customer_profile_id=customer_profile_id,
                product_category_id=product_category_id,
                user_id=user_id,
                profile_relationship=profile_rel,
                category_relationship=category_rel,
            )

    async def unlink_product_category_from_customer_profile(
        self,
        account_id: str,
        customer_profile_id: str,
        product_category_id: str,
        user_id: str,
    ) -> None:
        """Unlink a product category from a customer profile with cascade deletion of strategies.

        This will:
        1. Delete all 5 strategy nodes for this (CustomerProfile, ProductCategory) pair
        2. Delete the IS_MARKETED_TO relationship

        Args:
            account_id: Account identifier
            customer_profile_id: CustomerProfile node_id
            product_category_id: ProductCategory node_id
            user_id: User performing deletion
        """
        # Find all strategy nodes for this pair using a single atomic query
        find_strategies_query = """
        MATCH (s)
        WHERE s.customer_profile_node_id = $customer_profile_id
          AND s.product_category_node_id = $product_category_id
          AND (s)-[:BELONGS_TO]->(:Account {account_id: $account_id})
          AND (s:ProblemAwarenessStrategy OR s:BrandAwarenessStrategy
               OR s:ConsiderationStrategy OR s:ConversionStrategy OR s:LoyaltyStrategy)
        RETURN s.node_id as node_id, labels(s)[0] as strategy_type
        """
        strategies = await self.neo4j.execute_query(
            find_strategies_query,
            {
                "customer_profile_id": customer_profile_id,
                "product_category_id": product_category_id,
                "account_id": account_id,
            },
        )

        # Delete all strategies found
        # Note: delete_node handles both Neo4j and Firestore with rollback on failure
        for strategy in strategies:
            strategy_node_id = strategy["node_id"]
            strategy_type = strategy["strategy_type"]
            await self.delete_node(
                account_id=account_id,
                node_id=strategy_node_id,
                node_type=strategy_type,
                user_id=user_id,
                firestore_doc_type="marketing_strategy",
                check_dependencies=False,
            )

        # Delete the IS_MARKETED_TO relationship
        delete_query = """
        MATCH (pc:ProductCategory {node_id: $product_category_id})-[r:IS_MARKETED_TO]->(cp:CustomerProfile {node_id: $customer_profile_id})
        WHERE (pc)-[:BELONGS_TO]->(:Account {account_id: $account_id})
          AND (cp)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        DELETE r
        """

        await self.neo4j.execute_write_query(
            delete_query,
            {
                "product_category_id": product_category_id,
                "customer_profile_id": customer_profile_id,
                "account_id": account_id,
            },
        )

    async def list_linked_product_categories(
        self,
        account_id: str,
        customer_profile_id: str,
    ) -> list[dict]:
        """List all product categories linked to a customer profile.

        Args:
            account_id: Account identifier
            customer_profile_id: CustomerProfile node_id

        Returns:
            List of ProductCategory nodes with strategy counts
        """
        query = """
        MATCH (pc:ProductCategory)-[:IS_MARKETED_TO]->(cp:CustomerProfile {node_id: $customer_profile_id})
        WHERE (pc)-[:BELONGS_TO]->(:Account {account_id: $account_id})
          AND (cp)-[:BELONGS_TO]->(:Account {account_id: $account_id})

        OPTIONAL MATCH (pc)-[:HAS_PROBLEM_AWARENESS_STRATEGY]->(pas)
        WHERE pas.customer_profile_node_id = $customer_profile_id

        OPTIONAL MATCH (pc)-[:HAS_BRAND_AWARENESS_STRATEGY]->(bas)
        WHERE bas.customer_profile_node_id = $customer_profile_id

        OPTIONAL MATCH (pc)-[:HAS_CONSIDERATION_STRATEGY]->(cs)
        WHERE cs.customer_profile_node_id = $customer_profile_id

        OPTIONAL MATCH (pc)-[:HAS_CONVERSION_STRATEGY]->(cos)
        WHERE cos.customer_profile_node_id = $customer_profile_id

        OPTIONAL MATCH (pc)-[:HAS_LOYALTY_STRATEGY]->(ls)
        WHERE ls.customer_profile_node_id = $customer_profile_id

        WITH pc,
             count(DISTINCT pas) + count(DISTINCT bas) + count(DISTINCT cs) + count(DISTINCT cos) + count(DISTINCT ls) as strategy_count

        RETURN pc.node_id as node_id,
               $account_id as account_id,
               pc.product_name as product_name,
               pc.description as description,
               pc.references as references,
               pc.created_time as created_time,
               pc.last_modified as last_modified,
               pc.created_by as created_by,
               pc.last_modified_by as last_modified_by,
               strategy_count
        ORDER BY pc.product_name
        """

        results = await self.neo4j.execute_query(
            query,
            {
                "customer_profile_id": customer_profile_id,
                "account_id": account_id,
            },
        )

        # Convert Neo4j DateTime objects to ISO strings and ensure all fields are present
        categories = []
        for record in results:
            category_dict = dict(record)
            # Convert DateTime objects to ISO strings
            if category_dict.get("created_time"):
                category_dict["created_time"] = category_dict["created_time"].isoformat()
            if category_dict.get("last_modified"):
                category_dict["last_modified"] = category_dict["last_modified"].isoformat()
            # Ensure account_id is set
            if not category_dict.get("account_id"):
                category_dict["account_id"] = account_id
            categories.append(category_dict)

        return categories

    async def list_linked_customer_profiles(
        self,
        account_id: str,
        product_category_id: str,
    ) -> list[dict]:
        """List all customer profiles linked to a product category via IS_MARKETED_TO.

        Args:
            account_id: Account identifier
            product_category_id: ProductCategory node_id

        Returns:
            List of CustomerProfile nodes
        """
        query = """
        MATCH (pc:ProductCategory {node_id: $product_category_id})-[:IS_MARKETED_TO]->(cp:CustomerProfile)
        WHERE (pc)-[:BELONGS_TO]->(:Account {account_id: $account_id})
          AND (cp)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        RETURN cp.node_id as node_id,
               $account_id as account_id,
               cp.display_name as display_name,
               cp.description as description,
               cp.references as references,
               cp.created_time as created_time,
               cp.last_modified as last_modified,
               cp.created_by as created_by,
               cp.last_modified_by as last_modified_by
        ORDER BY cp.display_name
        """

        results = await self.neo4j.execute_query(
            query,
            {
                "product_category_id": product_category_id,
                "account_id": account_id,
            },
        )

        profiles = []
        for record in results:
            profile_dict = dict(record)
            # Convert DateTime objects to ISO strings if needed
            if profile_dict.get("created_time") and hasattr(
                profile_dict["created_time"], "isoformat"
            ):
                profile_dict["created_time"] = profile_dict["created_time"].isoformat()
            if profile_dict.get("last_modified") and hasattr(
                profile_dict["last_modified"], "isoformat"
            ):
                profile_dict["last_modified"] = profile_dict["last_modified"].isoformat()
            if not profile_dict.get("account_id"):
                profile_dict["account_id"] = account_id
            profiles.append(profile_dict)

        return profiles

    async def create_problem_awareness_strategy(
        self,
        account_id: str,
        strategy: ProblemAwarenessStrategyCreate,
        user_id: str,
    ) -> ProblemAwarenessStrategyResponse:
        """Create a problem awareness strategy with dual-parent relationships."""
        is_valid, error = self.validation.validate_non_empty_string(
            strategy.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        # Validate both parents exist
        if not await self.validation.validate_node_exists(
            strategy.customer_profile_node_id, "CustomerProfile"
        ):
            raise NodeNotFoundException(
                "CustomerProfile", strategy.customer_profile_node_id
            )

        if not await self.validation.validate_node_exists(
            strategy.product_category_node_id, "ProductCategory"
        ):
            raise NodeNotFoundException(
                "ProductCategory", strategy.product_category_node_id
            )

        # Generate composite node_id from both parents
        node_id = f"problemaware_{strategy.product_category_node_id}_{strategy.customer_profile_node_id}"

        node_data = {
            "description": strategy.description.strip(),
            "references": strategy.references,
            "customer_profile_node_id": strategy.customer_profile_node_id,
            "product_category_node_id": strategy.product_category_node_id,
        }

        # Create with dual-parent relationships
        result = await self._create_marketing_strategy_node(
            node_id=node_id,
            node_type="ProblemAwarenessStrategy",
            node_data=node_data,
            account_id=account_id,
            customer_profile_id=strategy.customer_profile_node_id,
            product_category_id=strategy.product_category_node_id,
            user_id=user_id,
            profile_relationship="DISCOVERS_THE_PROBLEM_BY",
            category_relationship="HAS_PROBLEM_AWARENESS_STRATEGY",
        )

        return ProblemAwarenessStrategyResponse(**result)

    async def update_problem_awareness_strategy(
        self,
        account_id: str,
        node_id: str,
        updates: ProblemAwarenessStrategyUpdate,
        user_id: str,
    ) -> ProblemAwarenessStrategyResponse:
        """Update a problem awareness strategy."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ProblemAwarenessStrategy",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return ProblemAwarenessStrategyResponse(**result)

    async def delete_problem_awareness_strategy(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a problem awareness strategy."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ProblemAwarenessStrategy",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,
        )

    async def create_brand_awareness_strategy(
        self,
        account_id: str,
        strategy: BrandAwarenessStrategyCreate,
        user_id: str,
    ) -> BrandAwarenessStrategyResponse:
        """Create a brand awareness strategy with dual-parent relationships."""
        is_valid, error = self.validation.validate_non_empty_string(
            strategy.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        if not await self.validation.validate_node_exists(
            strategy.customer_profile_node_id, "CustomerProfile"
        ):
            raise NodeNotFoundException(
                "CustomerProfile", strategy.customer_profile_node_id
            )

        if not await self.validation.validate_node_exists(
            strategy.product_category_node_id, "ProductCategory"
        ):
            raise NodeNotFoundException(
                "ProductCategory", strategy.product_category_node_id
            )

        node_id = f"brandaware_{strategy.product_category_node_id}_{strategy.customer_profile_node_id}"

        node_data = {
            "description": strategy.description.strip(),
            "references": strategy.references,
            "customer_profile_node_id": strategy.customer_profile_node_id,
            "product_category_node_id": strategy.product_category_node_id,
        }

        result = await self._create_marketing_strategy_node(
            node_id=node_id,
            node_type="BrandAwarenessStrategy",
            node_data=node_data,
            account_id=account_id,
            customer_profile_id=strategy.customer_profile_node_id,
            product_category_id=strategy.product_category_node_id,
            user_id=user_id,
            profile_relationship="DISCOVERS_OUR_BRAND_BY",
            category_relationship="HAS_BRAND_AWARENESS_STRATEGY",
        )

        return BrandAwarenessStrategyResponse(**result)

    async def update_brand_awareness_strategy(
        self,
        account_id: str,
        node_id: str,
        updates: BrandAwarenessStrategyUpdate,
        user_id: str,
    ) -> BrandAwarenessStrategyResponse:
        """Update a brand awareness strategy."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="BrandAwarenessStrategy",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return BrandAwarenessStrategyResponse(**result)

    async def delete_brand_awareness_strategy(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a brand awareness strategy."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="BrandAwarenessStrategy",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,
        )

    async def create_consideration_strategy(
        self,
        account_id: str,
        strategy: ConsiderationStrategyCreate,
        user_id: str,
    ) -> ConsiderationStrategyResponse:
        """Create a consideration strategy with dual-parent relationships."""
        is_valid, error = self.validation.validate_non_empty_string(
            strategy.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        if not await self.validation.validate_node_exists(
            strategy.customer_profile_node_id, "CustomerProfile"
        ):
            raise NodeNotFoundException(
                "CustomerProfile", strategy.customer_profile_node_id
            )

        if not await self.validation.validate_node_exists(
            strategy.product_category_node_id, "ProductCategory"
        ):
            raise NodeNotFoundException(
                "ProductCategory", strategy.product_category_node_id
            )

        node_id = f"consideration_{strategy.product_category_node_id}_{strategy.customer_profile_node_id}"

        node_data = {
            "description": strategy.description.strip(),
            "references": strategy.references,
            "customer_profile_node_id": strategy.customer_profile_node_id,
            "product_category_node_id": strategy.product_category_node_id,
        }

        result = await self._create_marketing_strategy_node(
            node_id=node_id,
            node_type="ConsiderationStrategy",
            node_data=node_data,
            account_id=account_id,
            customer_profile_id=strategy.customer_profile_node_id,
            product_category_id=strategy.product_category_node_id,
            user_id=user_id,
            profile_relationship="CONSIDERS_OUR_BRAND_BECAUSE",
            category_relationship="HAS_CONSIDERATION_STRATEGY",
        )

        return ConsiderationStrategyResponse(**result)

    async def update_consideration_strategy(
        self,
        account_id: str,
        node_id: str,
        updates: ConsiderationStrategyUpdate,
        user_id: str,
    ) -> ConsiderationStrategyResponse:
        """Update a consideration strategy."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ConsiderationStrategy",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return ConsiderationStrategyResponse(**result)

    async def delete_consideration_strategy(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a consideration strategy."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ConsiderationStrategy",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,
        )

    async def create_conversion_strategy(
        self,
        account_id: str,
        strategy: ConversionStrategyCreate,
        user_id: str,
    ) -> ConversionStrategyResponse:
        """Create a conversion strategy with dual-parent relationships."""
        is_valid, error = self.validation.validate_non_empty_string(
            strategy.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        if not await self.validation.validate_node_exists(
            strategy.customer_profile_node_id, "CustomerProfile"
        ):
            raise NodeNotFoundException(
                "CustomerProfile", strategy.customer_profile_node_id
            )

        if not await self.validation.validate_node_exists(
            strategy.product_category_node_id, "ProductCategory"
        ):
            raise NodeNotFoundException(
                "ProductCategory", strategy.product_category_node_id
            )

        node_id = f"conversion_{strategy.product_category_node_id}_{strategy.customer_profile_node_id}"

        node_data = {
            "description": strategy.description.strip(),
            "references": strategy.references,
            "customer_profile_node_id": strategy.customer_profile_node_id,
            "product_category_node_id": strategy.product_category_node_id,
        }

        result = await self._create_marketing_strategy_node(
            node_id=node_id,
            node_type="ConversionStrategy",
            node_data=node_data,
            account_id=account_id,
            customer_profile_id=strategy.customer_profile_node_id,
            product_category_id=strategy.product_category_node_id,
            user_id=user_id,
            profile_relationship="PURCHASES_OUR_BRAND_BECAUSE",
            category_relationship="HAS_CONVERSION_STRATEGY",
        )

        return ConversionStrategyResponse(**result)

    async def update_conversion_strategy(
        self,
        account_id: str,
        node_id: str,
        updates: ConversionStrategyUpdate,
        user_id: str,
    ) -> ConversionStrategyResponse:
        """Update a conversion strategy."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ConversionStrategy",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return ConversionStrategyResponse(**result)

    async def delete_conversion_strategy(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a conversion strategy."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ConversionStrategy",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,
        )

    async def create_loyalty_strategy(
        self,
        account_id: str,
        strategy: LoyaltyStrategyCreate,
        user_id: str,
    ) -> LoyaltyStrategyResponse:
        """Create a loyalty strategy with dual-parent relationships."""
        is_valid, error = self.validation.validate_non_empty_string(
            strategy.description, "description"
        )
        if not is_valid:
            raise ValidationException(error, "description")

        if not await self.validation.validate_node_exists(
            strategy.customer_profile_node_id, "CustomerProfile"
        ):
            raise NodeNotFoundException(
                "CustomerProfile", strategy.customer_profile_node_id
            )

        if not await self.validation.validate_node_exists(
            strategy.product_category_node_id, "ProductCategory"
        ):
            raise NodeNotFoundException(
                "ProductCategory", strategy.product_category_node_id
            )

        node_id = f"loyalty_{strategy.product_category_node_id}_{strategy.customer_profile_node_id}"

        node_data = {
            "description": strategy.description.strip(),
            "references": strategy.references,
            "customer_profile_node_id": strategy.customer_profile_node_id,
            "product_category_node_id": strategy.product_category_node_id,
        }

        result = await self._create_marketing_strategy_node(
            node_id=node_id,
            node_type="LoyaltyStrategy",
            node_data=node_data,
            account_id=account_id,
            customer_profile_id=strategy.customer_profile_node_id,
            product_category_id=strategy.product_category_node_id,
            user_id=user_id,
            profile_relationship="BECOMES_AN_ADVOCATE_BECAUSE",
            category_relationship="HAS_LOYALTY_STRATEGY",
        )

        return LoyaltyStrategyResponse(**result)

    async def update_loyalty_strategy(
        self,
        account_id: str,
        node_id: str,
        updates: LoyaltyStrategyUpdate,
        user_id: str,
    ) -> LoyaltyStrategyResponse:
        """Update a loyalty strategy."""
        update_dict = updates.model_dump(exclude_unset=True)

        result = await self.update_node(
            account_id=account_id,
            node_id=node_id,
            node_type="LoyaltyStrategy",
            updates=update_dict,
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
        )

        return LoyaltyStrategyResponse(**result)

    async def delete_loyalty_strategy(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a loyalty strategy."""
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="LoyaltyStrategy",
            user_id=user_id,
            firestore_doc_type="marketing_strategy",
            check_dependencies=False,
        )

    # ==================== GENERIC HELPER METHODS ====================

    def _generate_node_id(self, node_type: str, account_id: str) -> str:
        """Generate node_id with appropriate prefix based on node type.

        Matches naming conventions from graph builders.

        Args:
            node_type: Type of node
            account_id: Account identifier

        Returns:
            Generated node_id
        """
        prefix_map = {
            # Business Strategy
            "Product": "prod",
            "ProductCategory": "productcat",
            "ValueProposition": "value",
            "Strength": "strength",
            "Weakness": "weakness",
            "Opportunity": "opportunity",
            "Risk": "risk",
            "Goal": "goal",
            "SWOTAnalysis": "swot",
            # Competitive Strategy (for future phases)
            "Competitor": "competitor",
            "CompetitorTactic": "tactic",
            "SubstituteProduct": "substitute",
            "CompetitorStrength": "compstrength",
            "CompetitorWeakness": "compweakness",
            "CompetitiveEnvironment": "competitiveenv",
            # Marketing Strategy (for future phases)
            "CustomerProfile": "icp",
            "ProblemAwarenessStrategy": "probaware",
            "BrandAwarenessStrategy": "brandaware",
            "ConsiderationStrategy": "consider",
            "ConversionStrategy": "convert",
            "LoyaltyStrategy": "loyalty",
            # Brand Guidelines (for future phases)
            "BrandIdentity": "brand",
            "BrandPersonality": "personality",
            "VoiceAndTone": "voicetone",
            "ColorPalette": "colors",
            "Typography": "typography",
            "ImageStyle": "imagestyle",
            "MissionAndValues": "mission",
        }

        prefix = prefix_map.get(node_type, "node")
        return f"{prefix}_{account_id}_{uuid.uuid4().hex[:8]}"

    async def _create_node_neo4j(
        self,
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        account_id: str,
        parent_node_id: str | None,
        parent_node_type: str | None,
        user_id: str,
    ) -> dict[str, Any]:
        """Generic Neo4j node creation with bidirectional relationships.

        Handles ALL node types through parameterization.
        Applies Strategy label and standard audit fields automatically.

        Args:
            node_id: Generated node identifier
            node_type: Node type label
            node_data: Node properties
            account_id: Account identifier
            parent_node_id: Optional parent node
            parent_node_type: Optional parent type
            user_id: User creating node

        Returns:
            Created node as dictionary
        """
        # Get relationship configuration for this node type
        relationship_config = self._get_relationship_config(node_type, parent_node_type)

        # Build base query with Strategy label and standard fields
        query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        MERGE (node:{node_type}:Strategy {{node_id: $node_id}})
        SET node += $node_data,
            node.account_id = $account_id,
            node.created_time = COALESCE(node.created_time, datetime()),
            node.last_modified = datetime(),
            node.created_by = COALESCE(node.created_by, $user_id),
            node.last_modified_by = $user_id,
            node.embedding = null
        MERGE (node)-[:BELONGS_TO]->(acc)
        """

        # Add parent relationship if specified
        if parent_node_id and relationship_config:
            # Special handling for Account parent nodes which use account_id instead of node_id
            if parent_node_type == "Account":
                query += f"""
                WITH node, acc
                MATCH (parent:{parent_node_type} {{account_id: $parent_node_id}})
                MERGE (parent)-[:{relationship_config["from_parent"]}]->(node)
                """
            else:
                query += f"""
                WITH node, acc
                MATCH (parent:{parent_node_type} {{node_id: $parent_node_id}})
                MERGE (parent)-[:{relationship_config["from_parent"]}]->(node)
                """

        # Add bidirectional relationship to Account for certain node types
        if node_type in ["ProductCategory", "Goal"]:
            account_rel_map = {"ProductCategory": "OFFERS_PRODUCTS", "Goal": "HAS_GOAL"}
            query += f"""
            WITH node, acc
            MERGE (acc)-[:{account_rel_map[node_type]}]->(node)
            """

        query += " RETURN node"

        params = {
            "node_id": node_id,
            "account_id": account_id,
            "node_data": node_data,
            "user_id": user_id,
            "parent_node_id": parent_node_id,
        }

        result = await self.neo4j.execute_write_query(query, params)

        if not result:
            raise Exception(f"Failed to create {node_type} in Neo4j")

        return {**self._neo4j_node_to_dict(result[0]["node"]), "account_id": account_id}

    async def _create_marketing_strategy_node(
        self,
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        account_id: str,
        customer_profile_id: str,
        product_category_id: str,
        user_id: str,
        profile_relationship: str,
        category_relationship: str,
    ) -> dict[str, Any]:
        """Create marketing strategy node with dual-parent relationships.

        Marketing strategies are unique because they link to BOTH CustomerProfile AND
        ProductCategory through separate relationships.

        Args:
            node_id: Pre-generated node ID (format: {type}_{category_id}_{profile_id})
            node_type: Strategy node type
            node_data: Node properties (includes parent IDs)
            account_id: Account identifier
            customer_profile_id: CustomerProfile parent
            product_category_id: ProductCategory parent
            user_id: User creating the node
            profile_relationship: Relationship from CustomerProfile to strategy
            category_relationship: Relationship from ProductCategory to strategy

        Returns:
            Created node as dictionary
        """
        validate_node_type(node_type)

        # Create strategy node with BELONGS_TO + dual parent relationships
        query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        MATCH (cp:CustomerProfile {{node_id: $customer_profile_id}})
        MATCH (pc:ProductCategory {{node_id: $product_category_id}})

        CREATE (node:{node_type}:Strategy)
        SET node += $node_data,
            node.node_id = $node_id,
            node.account_id = $account_id,
            node.created_time = datetime(),
            node.last_modified = datetime(),
            node.created_by = $user_id,
            node.last_modified_by = $user_id,
            node.embedding = null

        MERGE (node)-[:BELONGS_TO]->(acc)
        MERGE (cp)-[:{profile_relationship}]->(node)
        MERGE (pc)-[:{category_relationship}]->(node)
        MERGE (pc)-[:IS_MARKETED_TO]->(cp)

        RETURN node
        """

        params = {
            "node_id": node_id,
            "account_id": account_id,
            "customer_profile_id": customer_profile_id,
            "product_category_id": product_category_id,
            "node_data": node_data,
            "user_id": user_id,
        }

        result = await self.neo4j.execute_write_query(query, params)

        if not result:
            raise Exception(f"Failed to create {node_type} in Neo4j")

        created_node = {
            **self._neo4j_node_to_dict(result[0]["node"]),
            "account_id": account_id,
        }

        # Sync to Firestore
        await self._sync_node_to_firestore(
            account_id=account_id,
            node_id=node_id,
            node_type=node_type,
            node_data=created_node,
            firestore_doc_type="marketing_strategy",
            operation="create",
        )

        return created_node

    def _get_relationship_config(
        self, node_type: str, parent_node_type: str | None
    ) -> dict[str, str] | None:
        """Get bidirectional relationship configuration for node type and parent.

        Returns dict with 'from_parent' relationship type.

        Args:
            node_type: Child node type
            parent_node_type: Parent node type

        Returns:
            Relationship configuration or None
        """
        relationship_map = {
            # Business Strategy
            ("Product", "ProductCategory"): {"from_parent": "INCLUDES_PRODUCT"},
            ("ValueProposition", "Product"): {"from_parent": "HAS_VALUE_PROPOSITION"},
            ("ValueProposition", "ProductCategory"): {
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("ValueProposition", "Account"): {"from_parent": "HAS_VALUE_PROPOSITION"},
            ("Strength", "SWOTAnalysis"): {"from_parent": "HAS_STRENGTH"},
            ("Weakness", "SWOTAnalysis"): {"from_parent": "HAS_WEAKNESS"},
            ("Opportunity", "Strength"): {"from_parent": "CREATES"},
            ("Risk", "Weakness"): {"from_parent": "CREATES"},
            # Competitive Strategy
            ("CompetitorTactic", "Competitor"): {"from_parent": "USES_TACTIC"},
            ("CompetitorStrength", "Competitor"): {"from_parent": "HAS_STRENGTH"},
            ("CompetitorWeakness", "Competitor"): {"from_parent": "HAS_WEAKNESS"},
            ("SubstituteProduct", "Competitor"): {"from_parent": "OFFERS_PRODUCT"},
            ("ValueProposition", "Competitor"): {
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("ValueProposition", "SubstituteProduct"): {
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("Risk", "CompetitorStrength"): {"from_parent": "CREATES"},
            ("Opportunity", "CompetitorWeakness"): {"from_parent": "CREATES"},
        }

        return relationship_map.get((node_type, parent_node_type))

    async def _update_node_neo4j(
        self,
        node_id: str,
        node_type: str,
        updates: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Update node in Neo4j.

        Args:
            node_id: Node identifier
            node_type: Node type label
            updates: Fields to update
            user_id: User performing update

        Returns:
            Updated node as dictionary
        """
        # Handle legacy field names for nodes that might use type-specific IDs
        # TODO: Remove this compatibility layer after Neo4j data migration
        legacy_field_map = {
            "Risk": "risk_id",
            "Opportunity": "opportunity_id",
        }
        legacy_field = legacy_field_map.get(node_type)

        # Match on either node_id or legacy field
        if legacy_field:
            query = f"""
            MATCH (node:{node_type})
            WHERE node.node_id = $node_id OR node.{legacy_field} = $node_id
            SET node += $updates,
                node.last_modified = datetime(),
                node.last_modified_by = $user_id
            RETURN node
            """
        else:
            query = f"""
            MATCH (node:{node_type} {{node_id: $node_id}})
            SET node += $updates,
                node.last_modified = datetime(),
                node.last_modified_by = $user_id
            RETURN node
            """

        result = await self.neo4j.execute_write_query(
            query, {"node_id": node_id, "updates": updates, "user_id": user_id}
        )

        if not result:
            raise Exception(f"Failed to update {node_type} {node_id} in Neo4j")

        node_dict = self._neo4j_node_to_dict(result[0]["node"])

        # Normalize legacy field to node_id if needed
        if legacy_field and "node_id" not in node_dict and legacy_field in node_dict:
            node_dict["node_id"] = node_dict[legacy_field]

        return node_dict

    async def _delete_node_neo4j(self, node_id: str) -> None:
        """Delete a node and its relationships from Neo4j.

        Args:
            node_id: Node identifier to delete
        """
        query = """
        MATCH (n {node_id: $node_id})
        DETACH DELETE n
        """
        await self.neo4j.execute_write_operation(query, {"node_id": node_id})

    async def _validate_can_delete(
        self, node_id: str, node_type: str
    ) -> tuple[bool, str]:
        """Validate that a node can be safely deleted.

        Args:
            node_id: Node identifier
            node_type: Node type

        Returns:
            (can_delete, reason) tuple
        """
        # Business Strategy
        if node_type == "ProductCategory":
            return await self.validation.validate_can_delete_product_category(node_id)
        elif node_type == "Product":
            return await self.validation.validate_can_delete_product(node_id)
        elif node_type == "Strength":
            return await self.validation.validate_can_delete_strength(node_id)
        elif node_type == "Weakness":
            return await self.validation.validate_can_delete_weakness(node_id)
        # Competitive Strategy
        elif node_type == "Competitor":
            return await self.validation.validate_can_delete_competitor(node_id)
        elif node_type == "CompetitorStrength":
            return await self.validation.validate_can_delete_competitor_strength(
                node_id
            )
        elif node_type == "CompetitorWeakness":
            return await self.validation.validate_can_delete_competitor_weakness(
                node_id
            )
        elif node_type == "SubstituteProduct":
            return await self.validation.validate_can_delete_substitute_product(node_id)
        else:
            # No dependencies to check
            return True, ""

    async def _sync_node_to_firestore(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        firestore_doc_type: str,
        operation: str,
    ) -> None:
        """Generic Firestore sync for any node type.

        Routes node updates to appropriate location in Firestore document structure.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type
            node_data: Node data to sync
            firestore_doc_type: "business_strategy", "competitive_strategy", etc.
            operation: "create", "update", or "delete"
        """
        # Store directly in account-specific collection
        doc_path = f"strategy_docs_{account_id}"
        collection_name = firestore_doc_type

        # Get current document
        doc = self.firestore.get_document(doc_path, collection_name)
        if not doc:
            # Create initial document structure if doesn't exist
            doc = self._create_initial_firestore_doc(firestore_doc_type, account_id)

        # Route to appropriate sync method based on node type
        if node_type in [
            "Product",
            "ProductCategory",
            "ValueProposition",
            "Strength",
            "Weakness",
            "Opportunity",
            "Risk",
            "Goal",
        ]:
            self._sync_business_node_to_doc(
                doc, node_id, node_type, node_data, operation
            )
        elif node_type in [
            "CompetitiveEnvironment",
            "Competitor",
            "CompetitorTactic",
            "CompetitorStrength",
            "CompetitorWeakness",
            "SubstituteProduct",
        ]:
            self._sync_competitive_node_to_doc(
                doc, node_id, node_type, node_data, operation
            )
        elif node_type in [
            "CustomerProfile",
            "ProblemAwarenessStrategy",
            "BrandAwarenessStrategy",
            "ConsiderationStrategy",
            "ConversionStrategy",
            "LoyaltyStrategy",
        ]:
            self._sync_marketing_node_to_doc(
                doc, node_id, node_type, node_data, operation
            )
        elif node_type in [
            "BrandIdentity",
            "BrandPersonality",
            "VoiceAndTone",
            "ColorPalette",
            "Typography",
            "ImageStyle",
            "MissionAndValues",
        ]:
            self._sync_brand_node_to_doc(doc, node_id, node_type, node_data, operation)
        else:
            raise ValueError(f"Unsupported node type for Firestore sync: {node_type}")

        # Update document timestamp
        doc["updated_at"] = datetime.now()

        # Write back to Firestore
        self.firestore.update_document(doc_path, collection_name, doc)

    def _create_initial_firestore_doc(
        self, doc_type: str, account_id: str
    ) -> dict[str, Any]:
        """Create initial Firestore document structure.

        Args:
            doc_type: Document type
            account_id: Account identifier

        Returns:
            Initial document structure
        """
        if doc_type == "business_strategy":
            return {
                "account_id": account_id,
                "product_portfolio": [],
                "swot_analysis": {
                    "strengths_and_opportunities": [],
                    "weaknesses_and_risks": [],
                },
                "strategic_goals": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        elif doc_type == "competitive_strategy":
            return {
                "account_id": account_id,
                "competitive_environment": None,
                "competitors": [],
                "competitor_tactics": [],
                "competitor_strengths": [],
                "competitor_weaknesses": [],
                "substitute_products": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        elif doc_type == "marketing_strategy":
            return {
                "account_id": account_id,
                "customer_profiles": [],
                "problem_awareness_strategies": [],
                "brand_awareness_strategies": [],
                "consideration_strategies": [],
                "conversion_strategies": [],
                "loyalty_strategies": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        elif doc_type == "brand_guidelines":
            return {
                "account_id": account_id,
                "brand_identity": None,
                "brand_personality": None,
                "voice_and_tone": None,
                "color_palette": None,
                "typography": None,
                "image_style": None,
                "mission_and_values": None,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        else:
            return {
                "account_id": account_id,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }

    def _sync_business_node_to_doc(
        self,
        doc: dict[str, Any],
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        operation: str,
    ) -> None:
        """Sync business strategy node to Firestore document structure.

        Args:
            doc: Firestore document
            node_id: Node identifier
            node_type: Node type
            node_data: Node data
            operation: "create", "update", or "delete"
        """
        # Stub implementation - detailed sync logic would go here
        # For Phase 1, we accept eventual consistency and focus on Neo4j as primary
        logger.info(f"Firestore sync stub: {operation} {node_type} {node_id}")

    def _sync_competitive_node_to_doc(
        self,
        doc: dict[str, Any],
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        operation: str,
    ) -> None:
        """Sync competitive strategy node to Firestore document structure.

        Maintains denormalized view of Neo4j competitive nodes in Firestore.

        Structure:
        {
            "competitive_environment": {...} or None,
            "competitors": [...],
            "competitor_tactics": [...],
            "competitor_strengths": [...],
            "competitor_weaknesses": [...],
            "substitute_products": [...],
        }

        Args:
            doc: Firestore document
            node_id: Node identifier
            node_type: Node type
            node_data: Node data
            operation: "create", "update", or "delete"
        """
        # Handle CompetitiveEnvironment separately (it's a singleton, not an array)
        if node_type == "CompetitiveEnvironment":
            if operation == "create" or operation == "update":
                doc["competitive_environment"] = node_data
                logger.info(
                    f"Synced CompetitiveEnvironment {node_id} to Firestore ({operation})"
                )
            elif operation == "delete":
                doc["competitive_environment"] = None
                logger.info(
                    f"Synced CompetitiveEnvironment {node_id} to Firestore (delete)"
                )
            return

        # Map node types to document arrays
        node_type_to_array = {
            "Competitor": "competitors",
            "CompetitorTactic": "competitor_tactics",
            "CompetitorStrength": "competitor_strengths",
            "CompetitorWeakness": "competitor_weaknesses",
            "SubstituteProduct": "substitute_products",
        }

        array_name = node_type_to_array.get(node_type)
        if not array_name:
            logger.warning(f"Unknown competitive node type for sync: {node_type}")
            return

        # Ensure array exists in document
        if array_name not in doc:
            doc[array_name] = []

        # Find existing node in array
        existing_index = next(
            (i for i, n in enumerate(doc[array_name]) if n.get("node_id") == node_id),
            None,
        )

        if operation == "create":
            if existing_index is not None:
                logger.warning(
                    f"Node {node_id} already exists in Firestore, updating instead"
                )
                doc[array_name][existing_index] = node_data
            else:
                doc[array_name].append(node_data)
            logger.info(f"Synced {node_type} {node_id} to Firestore (create)")

        elif operation == "update":
            if existing_index is not None:
                doc[array_name][existing_index] = node_data
                logger.info(f"Synced {node_type} {node_id} to Firestore (update)")
            else:
                logger.warning(
                    f"Node {node_id} not found in Firestore for update, creating"
                )
                doc[array_name].append(node_data)

        elif operation == "delete":
            if existing_index is not None:
                doc[array_name].pop(existing_index)
                logger.info(f"Synced {node_type} {node_id} to Firestore (delete)")
            else:
                logger.warning(f"Node {node_id} not found in Firestore for deletion")

    def _sync_marketing_node_to_doc(
        self,
        doc: dict[str, Any],
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        operation: str,
    ) -> None:
        """Sync marketing strategy node to Firestore document structure.

        Maintains denormalized view of Neo4j nodes in Firestore for query performance.

        Structure:
        {
            "customer_profiles": [...],  # Array of profile objects
            "problem_awareness_strategies": [...],  # Flat array
            "brand_awareness_strategies": [...],
            "consideration_strategies": [...],
            "conversion_strategies": [...],
            "loyalty_strategies": [...],
        }

        Args:
            doc: Firestore document
            node_id: Node identifier
            node_type: Node type
            node_data: Node data
            operation: "create", "update", or "delete"
        """
        # Map node types to document arrays
        node_type_to_array = {
            "CustomerProfile": "customer_profiles",
            "ProblemAwarenessStrategy": "problem_awareness_strategies",
            "BrandAwarenessStrategy": "brand_awareness_strategies",
            "ConsiderationStrategy": "consideration_strategies",
            "ConversionStrategy": "conversion_strategies",
            "LoyaltyStrategy": "loyalty_strategies",
        }

        array_name = node_type_to_array.get(node_type)
        if not array_name:
            logger.warning(f"Unknown marketing node type for sync: {node_type}")
            return

        # Ensure array exists in document
        if array_name not in doc:
            doc[array_name] = []

        # Find existing node in array
        existing_index = next(
            (i for i, n in enumerate(doc[array_name]) if n.get("node_id") == node_id),
            None,
        )

        if operation == "create":
            # Add new node to array
            if existing_index is not None:
                logger.warning(
                    f"Node {node_id} already exists in Firestore, updating instead"
                )
                doc[array_name][existing_index] = node_data
            else:
                doc[array_name].append(node_data)
            logger.info(f"Synced {node_type} {node_id} to Firestore (create)")

        elif operation == "update":
            # Update existing node
            if existing_index is not None:
                doc[array_name][existing_index] = node_data
                logger.info(f"Synced {node_type} {node_id} to Firestore (update)")
            else:
                logger.warning(
                    f"Node {node_id} not found in Firestore for update, creating"
                )
                doc[array_name].append(node_data)

        elif operation == "delete":
            # Remove node from array
            if existing_index is not None:
                doc[array_name].pop(existing_index)
                logger.info(f"Synced {node_type} {node_id} to Firestore (delete)")
            else:
                logger.warning(f"Node {node_id} not found in Firestore for deletion")

    def _sync_brand_node_to_doc(
        self,
        doc: dict[str, Any],
        node_id: str,
        node_type: str,
        node_data: dict[str, Any],
        operation: str,
    ) -> None:
        """Sync brand guidelines node to Firestore document structure.

        Brand nodes are singletons (one per account), not arrays. Similar to
        CompetitiveEnvironment hub pattern.

        Structure:
        {
            "brand_identity": {...} or None,
            "brand_personality": {...} or None,
            "voice_and_tone": {...} or None,
            "color_palette": {...} or None,
            "typography": {...} or None,
            "image_style": {...} or None,
            "mission_and_values": {...} or None,
        }

        Args:
            doc: Firestore document
            node_id: Node identifier
            node_type: Node type
            node_data: Node data
            operation: "create", "update", or "delete"
        """
        # Map node types to document fields (all are singletons)
        node_type_to_field = {
            "BrandIdentity": "brand_identity",
            "BrandPersonality": "brand_personality",
            "VoiceAndTone": "voice_and_tone",
            "ColorPalette": "color_palette",
            "Typography": "typography",
            "ImageStyle": "image_style",
            "MissionAndValues": "mission_and_values",
        }

        field_name = node_type_to_field.get(node_type)
        if not field_name:
            logger.warning(f"Unknown brand node type for sync: {node_type}")
            return

        if operation == "create" or operation == "update":
            doc[field_name] = node_data
            logger.info(f"Synced {node_type} {node_id} to Firestore ({operation})")
        elif operation == "delete":
            doc[field_name] = None
            logger.info(f"Synced {node_type} {node_id} to Firestore (delete)")

    def _convert_neo4j_value(self, value: Any) -> Any:
        """Convert Neo4j-specific types to Python-native types.

        Args:
            value: Value to convert (may be Neo4j DateTime, native Python, etc.)

        Returns:
            Python-native value suitable for JSON serialization
        """
        try:
            from neo4j.time import DateTime as Neo4jDateTime

            if isinstance(value, Neo4jDateTime):
                return value.to_native().isoformat()
        except ImportError:
            pass

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, list):
            return [self._convert_neo4j_value(item) for item in value]

        if isinstance(value, dict):
            return {k: self._convert_neo4j_value(v) for k, v in value.items()}

        return value

    # ==================== ROLLUP MARKETING STRATEGY METHODS ====================

    def _validate_marketing_strategy_type(self, strategy_type: str) -> None:
        """Validate strategy type to prevent Cypher injection.

        Args:
            strategy_type: Strategy type to validate

        Raises:
            ValidationException: If strategy type is not in whitelist
        """
        if strategy_type not in VALID_MARKETING_STRATEGY_TYPES:
            valid_types = ", ".join(sorted(VALID_MARKETING_STRATEGY_TYPES))
            raise ValidationException(
                f"Invalid strategy type '{strategy_type}'. Must be one of: {valid_types}",
                field_name="strategy_type",
            )

    async def get_rollup_marketing_hub(
        self,
        account_id: str,
    ) -> dict | None:
        """
        Get the RollupMarketingStrategy hub node for an account.

        Args:
            account_id: Account identifier

        Returns:
            Hub node with linked rollup strategy node_ids, or None if not found
        """
        query = """
        MATCH (hub:RollupMarketingStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        OPTIONAL MATCH (hub)-[r]->(rollup:Strategy)
        WHERE type(r) STARTS WITH 'INCREASES_'
        RETURN hub, collect({type: type(r), node_id: rollup.node_id}) as linked_strategies
        """

        result = await self.neo4j.execute_query(query, {"account_id": account_id})

        if not result:
            return None

        hub_data = self._neo4j_node_to_dict(result[0]["hub"])
        linked = result[0]["linked_strategies"]

        # Build rollup_strategies map
        rollup_strategies = {}
        for link in linked:
            if link.get("node_id"):  # Only include if node_id exists
                if link["type"] == "INCREASES_PROBLEM_AWARENESS_BY":
                    rollup_strategies["problem_awareness"] = link["node_id"]
                elif link["type"] == "INCREASES_BRAND_AWARENESS_BY":
                    rollup_strategies["brand_awareness"] = link["node_id"]
                elif link["type"] == "INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY":
                    rollup_strategies["consideration"] = link["node_id"]
                elif link["type"] == "INCREASES_PAYING_CUSTOMERS_BY":
                    rollup_strategies["conversion"] = link["node_id"]
                elif link["type"] == "INCREASES_LOYAL_CUSTOMERS_BY":
                    rollup_strategies["loyalty"] = link["node_id"]

        hub_data["rollup_strategies"] = rollup_strategies
        hub_data["account_id"] = account_id
        return hub_data

    async def create_rollup_marketing_hub(
        self,
        account_id: str,
        data: dict,
        user_id: str,
    ) -> dict:
        """Create a new RollupMarketingStrategy hub node."""
        # Check if hub already exists to prevent duplicates
        existing_hub = await self.get_rollup_marketing_hub(account_id)
        if existing_hub:
            raise DuplicateNodeException(
                node_type="RollupMarketingStrategy",
                field_name="account_id",
                field_value=account_id,
                account_id=account_id,
            )

        node_id = f"rollup_marketing_hub_{account_id}"

        query = """
        MATCH (acc:Account {account_id: $account_id})
        CREATE (hub:RollupMarketingStrategy:Strategy)
        SET hub.node_id = $node_id,
            hub.description = $description,
            hub.account_id = $account_id,
            hub.created_time = datetime(),
            hub.last_modified = datetime(),
            hub.created_by = $user_id,
            hub.last_modified_by = $user_id,
            hub.embedding = null
        MERGE (hub)-[:BELONGS_TO]->(acc)
        MERGE (hub)-[:INCREASES_CUSTOMERS_BY]->(acc)
        RETURN hub
        """

        params = {
            "node_id": node_id,
            "account_id": account_id,
            "description": data["description"],
            "user_id": user_id,
        }

        result = await self.neo4j.execute_write_query(query, params)

        if not result:
            from ..exceptions import NodeCreationException

            raise NodeCreationException(
                node_type="RollupMarketingStrategy",
                account_id=account_id,
                reason="Account may not exist or hub may already exist",
            )

        return {**self._neo4j_node_to_dict(result[0]["hub"]), "account_id": account_id}

    async def update_rollup_marketing_hub(
        self,
        account_id: str,
        node_id: str,
        updates: dict,
        user_id: str,
    ) -> dict:
        """Update an existing RollupMarketingStrategy hub node."""
        # Build SET clause dynamically
        set_clauses = [
            "node.last_modified = datetime()",
            "node.last_modified_by = $user_id",
        ]

        if "description" in updates and updates["description"] is not None:
            set_clauses.append("node.description = $description")

        query = f"""
        MATCH (node:RollupMarketingStrategy {{node_id: $node_id}})
        MATCH (node)-[:BELONGS_TO]->(acc:Account {{account_id: $account_id}})
        SET {", ".join(set_clauses)}
        RETURN node
        """

        params = {
            "node_id": node_id,
            "account_id": account_id,
            "user_id": user_id,
            **{k: v for k, v in updates.items() if v is not None},
        }

        result = await self.neo4j.execute_write_query(query, params)

        if not result:
            raise NodeNotFoundException(
                f"RollupMarketingStrategy hub {node_id} not found in account {account_id}"
            )

        return {**self._neo4j_node_to_dict(result[0]["node"]), "account_id": account_id}

    async def delete_rollup_marketing_hub(
        self,
        account_id: str,
        node_id: str,
    ) -> bool:
        """
        Delete RollupMarketingStrategy hub node.

        Note: This will NOT cascade delete rollup strategies.
        Only deletes the hub and its relationships.
        """
        query = """
        MATCH (hub:RollupMarketingStrategy {node_id: $node_id})
        MATCH (hub)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        DETACH DELETE hub
        RETURN count(hub) as deleted
        """

        result = await self.neo4j.execute_write_query(
            query, {"node_id": node_id, "account_id": account_id}
        )

        return result[0]["deleted"] > 0 if result else False

    async def list_rollup_strategies_by_type(
        self,
        account_id: str,
        strategy_type: str,
        skip: int = 0,
        limit: int | None = None,
    ) -> dict:
        """
        List rollup strategies of a specific type for an account.

        Only returns rollup strategies (node_id starts with ROLLUP_NODE_ID_PREFIX).
        """
        # Validate strategy type to prevent Cypher injection
        self._validate_marketing_strategy_type(strategy_type)

        # Combined query: get strategies and total count in single database round trip
        # Use COLLECT to gather all strategies first, then slice for pagination
        # Use WHERE $strategy_label IN labels() for safe parameterization instead of f-string
        query = """
        MATCH (strategy:Strategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        WHERE $strategy_label IN labels(strategy) AND strategy.node_id STARTS WITH $rollup_prefix
        OPTIONAL MATCH (strategy)-[:CAN_BE_CUSTOMIZED_BY]->(individual)
        WITH strategy, count(individual) as individual_count
        ORDER BY strategy.created_time DESC
        WITH collect({strategy: strategy, individual_count: individual_count}) as all_strategies
        RETURN
            CASE
                WHEN $limit IS NULL THEN all_strategies[$skip..]
                ELSE all_strategies[$skip..($skip + $limit)]
            END as paginated_strategies,
            size(all_strategies) as total
        """

        result = await self.neo4j.execute_query(
            query,
            {
                "account_id": account_id,
                "strategy_label": strategy_type,
                "skip": skip,
                "limit": limit,
                "rollup_prefix": ROLLUP_NODE_ID_PREFIX,
            },
        )

        items = []
        total = 0

        if result and result[0]:
            paginated_strategies = result[0].get("paginated_strategies", [])
            total = result[0].get("total", 0)

            for item in paginated_strategies:
                strategy_data = self._neo4j_node_to_dict(item["strategy"])
                strategy_data["account_id"] = account_id
                strategy_data["individual_strategy_count"] = item["individual_count"]
                items.append(strategy_data)

        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    async def get_rollup_strategy_with_individuals(
        self,
        account_id: str,
        node_id: str,
        strategy_type: str,
    ) -> dict | None:
        """
        Get a rollup strategy node with its linked individual strategies.

        Args:
            account_id: Account identifier
            node_id: Rollup strategy node_id
            strategy_type: Strategy node type (e.g., "ProblemAwarenessStrategy")

        Returns:
            Rollup strategy with list of individual strategy node_ids
        """
        # Validate strategy type to prevent Cypher injection
        self._validate_marketing_strategy_type(strategy_type)

        # Use WHERE $strategy_label IN labels() for safe parameterization instead of f-string
        query = """
        MATCH (rollup:Strategy {node_id: $node_id})
        WHERE $strategy_label IN labels(rollup)
        MATCH (rollup)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        OPTIONAL MATCH (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual:Strategy)
        WHERE $strategy_label IN labels(individual)
        RETURN rollup, collect(individual.node_id) as individual_ids
        """

        result = await self.neo4j.execute_query(
            query,
            {
                "node_id": node_id,
                "account_id": account_id,
                "strategy_label": strategy_type,
            },
        )

        if not result:
            return None

        rollup_data = self._neo4j_node_to_dict(result[0]["rollup"])
        rollup_data["account_id"] = account_id
        rollup_data["linked_individual_strategies"] = result[0]["individual_ids"]
        return rollup_data

    def _neo4j_node_to_dict(self, node: Any) -> dict[str, Any]:
        """Convert Neo4j node to dictionary with proper type conversion.

        Args:
            node: Neo4j node object

        Returns:
            Node as dictionary with Neo4j types converted to Python types
        """
        if hasattr(node, "_properties"):
            props = dict(node._properties)
        elif hasattr(node, "items"):
            props = dict(node.items())
        else:
            props = dict(node)

        return {key: self._convert_neo4j_value(value) for key, value in props.items()}


def get_graph_sync_service(
    neo4j: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> GraphSyncService:
    """Dependency injection for GraphSyncService.

    Args:
        neo4j: Neo4j service instance
        firestore: Firestore service instance

    Returns:
        GraphSyncService instance
    """
    validation = GraphValidationService(neo4j)
    return GraphSyncService(neo4j, firestore, validation)
