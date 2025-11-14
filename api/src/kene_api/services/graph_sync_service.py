"""Graph sync service for bidirectional Neo4j + Firestore operations.

Provides unified CRUD operations for ALL strategy node types (Business, Competitive,
Marketing, Brand). Uses generic operations to eliminate code duplication (DRY principle).
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import Depends

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
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    OpportunityCreate,
    OpportunityResponse,
    OpportunityUpdate,
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
            if "parent_node_id" in record and record["parent_node_id"]:
                node_dict["parent_node_id"] = record["parent_node_id"]
            if "parent_node_type" in record and record["parent_node_type"]:
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

        return {
            **self._neo4j_node_to_dict(result[0]["node"]),
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
        skip: int = 0,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List products with their category information in a single query.

        Optimized to avoid N+1 query problem by using OPTIONAL MATCH to fetch
        category_node_id for all products in one database round-trip.

        Args:
            account_id: Account identifier
            category_node_id: Optional filter by specific category
            skip: Number of products to skip (default: 0)
            limit: Maximum number of products to return (default: None = all)

        Returns:
            Tuple of (products_list, total_count)
            Each product dict includes category_node_id from relationship

        Raises:
            ValidationException: If validation fails
        """
        if category_node_id:
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

        node_data = {
            "display_name": opportunity.display_name.strip(),
            "description": opportunity.description.strip(),
            "references": opportunity.references,
            "strength_node_id": opportunity.strength_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Opportunity",
            node_data=node_data,
            parent_node_id=opportunity.strength_node_id,
            parent_node_type="Strength",
            user_id=user_id,
            firestore_doc_type="business_strategy",
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

        # Fetch the parent strength relationship
        strength_query = """
        MATCH (s:Strength)-[:CREATES]->(o:Opportunity {node_id: $node_id})
        RETURN s.node_id as strength_node_id
        LIMIT 1
        """
        strength_result = await self.neo4j.execute_query(
            strength_query, {"node_id": node_id}
        )
        if strength_result and strength_result[0]:
            result["strength_node_id"] = strength_result[0]["strength_node_id"]

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

        node_data = {
            "display_name": risk.display_name.strip(),
            "description": risk.description.strip(),
            "references": risk.references,
            "weakness_node_id": risk.weakness_node_id,
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Risk",
            node_data=node_data,
            parent_node_id=risk.weakness_node_id,
            parent_node_type="Weakness",
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

        # Fetch the parent weakness relationship
        weakness_query = """
        MATCH (w:Weakness)-[:CREATES]->(r:Risk {node_id: $node_id})
        RETURN w.node_id as weakness_node_id
        LIMIT 1
        """
        weakness_result = await self.neo4j.execute_query(
            weakness_query, {"node_id": node_id}
        )
        if weakness_result and weakness_result[0]:
            result["weakness_node_id"] = weakness_result[0]["weakness_node_id"]

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

        return self._neo4j_node_to_dict(result[0]["node"])

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
        if node_type == "ProductCategory":
            return await self.validation.validate_can_delete_product_category(node_id)
        elif node_type == "Product":
            return await self.validation.validate_can_delete_product(node_id)
        elif node_type == "Strength":
            return await self.validation.validate_can_delete_strength(node_id)
        elif node_type == "Weakness":
            return await self.validation.validate_can_delete_weakness(node_id)
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
