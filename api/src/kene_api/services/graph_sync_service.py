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
from .graph_validation_service import GraphValidationService

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
            ValueError: If validation fails
            Exception: If sync fails (with rollback)
        """
        try:
            # 1. Validate account exists
            if not await self.validation.validate_account_exists(account_id):
                raise ValueError(f"Account {account_id} not found")

            # 2. Validate parent exists (if required)
            if parent_node_id:
                if not await self.validation.validate_node_exists(parent_node_id, parent_node_type):
                    raise ValueError(f"Parent {parent_node_type} {parent_node_id} not found")

            # 3. Generate node_id with appropriate prefix
            node_id = self._generate_node_id(node_type, account_id)

            # 4. Create in Neo4j with bidirectional relationships
            neo4j_result = await self._create_node_neo4j(
                node_id=node_id,
                node_type=node_type,
                node_data=node_data,
                account_id=account_id,
                parent_node_id=parent_node_id,
                parent_node_type=parent_node_type,
                user_id=user_id,
            )

            # 5. Sync to Firestore
            try:
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=neo4j_result,
                    firestore_doc_type=firestore_doc_type,
                    operation="create",
                )
            except Exception as firestore_error:
                # Rollback Neo4j on Firestore failure
                logger.error(f"Firestore sync failed, rolling back Neo4j: {firestore_error}")
                await self._delete_node_neo4j(node_id)
                raise Exception(f"Firestore sync failed, rolled back Neo4j: {firestore_error}") from firestore_error

            return neo4j_result

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
            ValueError: If node not found
            Exception: If sync fails (with rollback)
        """
        try:
            # 1. Verify node exists and get current state
            existing_node = await self.get_node(account_id, node_id, node_type)
            if not existing_node:
                raise ValueError(f"{node_type} {node_id} not found")

            # 2. Update in Neo4j
            neo4j_result = await self._update_node_neo4j(
                node_id=node_id,
                node_type=node_type,
                updates=updates,
                user_id=user_id,
            )

            # 3. Sync to Firestore
            try:
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=neo4j_result,
                    firestore_doc_type=firestore_doc_type,
                    operation="update",
                )
            except Exception as firestore_error:
                # Rollback Neo4j on Firestore failure
                logger.error(f"Firestore sync failed, rolling back Neo4j: {firestore_error}")
                # Restore previous state
                await self._update_node_neo4j(
                    node_id=node_id,
                    node_type=node_type,
                    updates={k: v for k, v in existing_node.items() if k in updates},
                    user_id=user_id,
                )
                raise Exception(f"Firestore sync failed, rolled back Neo4j: {firestore_error}") from firestore_error

            return neo4j_result

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
            ValueError: If validation fails
            Exception: If sync fails (with rollback)
        """
        try:
            # 1. Verify node exists
            existing_node = await self.get_node(account_id, node_id, node_type)
            if not existing_node:
                raise ValueError(f"{node_type} {node_id} not found")

            # 2. Check dependencies if required
            if check_dependencies:
                can_delete, reason = await self._validate_can_delete(node_id, node_type)
                if not can_delete:
                    raise ValueError(reason)

            # 3. Delete from Neo4j
            await self._delete_node_neo4j(node_id)

            # 4. Sync to Firestore
            try:
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=existing_node,
                    firestore_doc_type=firestore_doc_type,
                    operation="delete",
                )
            except Exception as firestore_error:
                # Rollback Neo4j on Firestore failure
                logger.error(f"Firestore sync failed, restoring Neo4j node: {firestore_error}")
                # Restore node
                await self._create_node_neo4j(
                    node_id=node_id,
                    node_type=node_type,
                    node_data=existing_node,
                    account_id=account_id,
                    parent_node_id=existing_node.get("parent_node_id"),
                    parent_node_type=existing_node.get("parent_node_type"),
                    user_id=user_id,
                )
                raise Exception(f"Firestore sync failed, rolled back Neo4j: {firestore_error}") from firestore_error

        except Exception as e:
            logger.error(f"Failed to delete {node_type} {node_id}: {e}")
            raise

    async def list_nodes(
        self,
        account_id: str,
        node_type: str,
        parent_node_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generic list operation for any node type.

        Args:
            account_id: Account identifier
            node_type: Node type label
            parent_node_id: Optional filter by parent relationship

        Returns:
            List of nodes as dictionaries
        """
        if parent_node_id:
            # Query with parent filter - match relationship in both directions
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (parent {{node_id: $parent_node_id}})-[r]-(node:{node_type})
            WHERE (node)-[:BELONGS_TO]->(acc)
            RETURN node
            ORDER BY node.display_name, node.product_name, node.name
            """
        else:
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})
            MATCH (node:{node_type})-[:BELONGS_TO]->(acc)
            RETURN node
            ORDER BY node.display_name, node.product_name, node.name
            """

        result = await self.neo4j.execute_query(
            query, {"account_id": account_id, "parent_node_id": parent_node_id}
        )

        return [self._neo4j_node_to_dict(record["node"]) for record in result]

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
        """
        query = f"""
        MATCH (node:{node_type} {{node_id: $node_id}})
        WHERE node.account_id = $account_id OR (node)-[:BELONGS_TO]->(:Account {{account_id: $account_id}})
        RETURN node
        """

        result = await self.neo4j.execute_query(query, {"node_id": node_id, "account_id": account_id})

        if not result:
            return None

        return self._neo4j_node_to_dict(result[0]["node"])

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
        """
        node_data = {"product_name": category.product_name, "description": category.description}

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
        """Delete a product category.

        Args:
            account_id: Account identifier
            node_id: Category node_id
            user_id: User performing deletion

        Raises:
            ValueError: If category has dependent products
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="ProductCategory",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=True,
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
        """
        node_data = {
            "product_name": product.product_name,
            "description": product.description,
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

        return ProductResponse(**result)

    async def delete_product(
        self,
        account_id: str,
        node_id: str,
        user_id: str,
    ) -> None:
        """Delete a product.

        Args:
            account_id: Account identifier
            node_id: Product node_id
            user_id: User performing deletion

        Raises:
            ValueError: If product has dependent value propositions
        """
        await self.delete_node(
            account_id=account_id,
            node_id=node_id,
            node_type="Product",
            user_id=user_id,
            firestore_doc_type="business_strategy",
            check_dependencies=True,
        )

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
        """
        node_data = {
            "display_name": value_prop.display_name,
            "description": value_prop.description,
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
        """
        # Ensure SWOT Analysis hub exists
        swot_node_id = await self.validation.get_or_create_swot_hub(account_id, user_id)

        node_data = {
            "display_name": strength.display_name,
            "description": strength.description,
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
        """
        # Ensure SWOT Analysis hub exists
        swot_node_id = await self.validation.get_or_create_swot_hub(account_id, user_id)

        node_data = {
            "display_name": weakness.display_name,
            "description": weakness.description,
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
        """
        node_data = {
            "display_name": opportunity.display_name,
            "description": opportunity.description,
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
        """
        node_data = {
            "display_name": risk.display_name,
            "description": risk.description,
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
        """
        node_data = {
            "display_name": goal.display_name,
            "description": goal.description,
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
            query += f"""
            WITH node, acc
            MATCH (parent:{parent_node_type} {{node_id: $parent_node_id}})
            MERGE (parent)-[:{relationship_config['from_parent']}]->(node)
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

        return self._neo4j_node_to_dict(result[0]["node"])

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
            ("ValueProposition", "ProductCategory"): {"from_parent": "HAS_VALUE_PROPOSITION"},
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

    async def _validate_can_delete(self, node_id: str, node_type: str) -> tuple[bool, str]:
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
            self._sync_business_node_to_doc(doc, node_id, node_type, node_data, operation)
        else:
            raise ValueError(f"Unsupported node type for Firestore sync: {node_type}")

        # Update document timestamp
        doc["updated_at"] = datetime.now()

        # Write back to Firestore
        self.firestore.update_document(doc_path, collection_name, doc)

    def _create_initial_firestore_doc(self, doc_type: str, account_id: str) -> dict[str, Any]:
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
                "swot_analysis": {"strengths_and_opportunities": [], "weaknesses_and_risks": []},
                "strategic_goals": [],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        else:
            return {"account_id": account_id, "created_at": datetime.now(), "updated_at": datetime.now()}

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

    def _neo4j_node_to_dict(self, node: Any) -> dict[str, Any]:
        """Convert Neo4j node to dictionary.

        Args:
            node: Neo4j node object

        Returns:
            Node as dictionary
        """
        if hasattr(node, "_properties"):
            return dict(node._properties)
        elif hasattr(node, "items"):
            return dict(node.items())
        else:
            return dict(node)


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
