"""Validation service for knowledge graph operations.

Provides shared validation logic for graph node operations.
"""

import logging

from ..database import Neo4jService

logger = logging.getLogger(__name__)


class GraphValidationService:
    """Validation service for knowledge graph CRUD operations."""

    def __init__(self, neo4j_service: Neo4jService):
        """Initialize validation service.

        Args:
            neo4j_service: Neo4j service for database queries
        """
        self.neo4j = neo4j_service

    async def validate_account_exists(self, account_id: str) -> bool:
        """Check if account exists in Neo4j.

        Args:
            account_id: Account identifier to validate

        Returns:
            True if account exists, False otherwise
        """
        query = "MATCH (acc:Account {account_id: $account_id}) RETURN acc LIMIT 1"
        result = await self.neo4j.execute_query(query, {"account_id": account_id})
        return len(result) > 0

    async def validate_node_exists(self, node_id: str, node_type: str) -> bool:
        """Check if a specific node exists.

        Args:
            node_id: Node identifier
            node_type: Type of node (e.g., "Product", "ProductCategory")

        Returns:
            True if node exists, False otherwise
        """
        query = f"MATCH (n:{node_type} {{node_id: $node_id}}) RETURN n LIMIT 1"
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        return len(result) > 0

    async def validate_can_delete_product_category(self, node_id: str) -> tuple[bool, str]:
        """Validate that a product category can be deleted.

        ProductCategory can only be deleted if it has no products.

        Args:
            node_id: ProductCategory node_id

        Returns:
            (can_delete, reason) tuple
        """
        query = """
        MATCH (cat:ProductCategory {node_id: $node_id})-[:INCLUDES_PRODUCT]->(prod:Product)
        RETURN count(prod) as product_count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})

        if not result:
            return False, "ProductCategory not found"

        product_count = result[0]["product_count"]
        if product_count > 0:
            return False, f"Cannot delete ProductCategory with {product_count} existing products"

        return True, ""

    async def validate_can_delete_product(self, node_id: str) -> tuple[bool, str]:
        """Validate that a product can be deleted.

        Product can only be deleted if it has no value propositions.

        Args:
            node_id: Product node_id

        Returns:
            (can_delete, reason) tuple
        """
        query = """
        MATCH (prod:Product {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN count(vp) as vp_count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})

        if not result:
            return False, "Product not found"

        vp_count = result[0]["vp_count"]
        if vp_count > 0:
            return False, f"Cannot delete Product with {vp_count} existing value propositions"

        return True, ""

    async def validate_can_delete_strength(self, node_id: str) -> tuple[bool, str]:
        """Validate that a strength can be deleted.

        Strength can only be deleted if it has no linked opportunities.

        Args:
            node_id: Strength node_id

        Returns:
            (can_delete, reason) tuple
        """
        query = """
        MATCH (s:Strength {node_id: $node_id})-[:CREATES]->(opp:Opportunity)
        RETURN count(opp) as opp_count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})

        if not result:
            return False, "Strength not found"

        opp_count = result[0]["opp_count"]
        if opp_count > 0:
            return False, f"Cannot delete Strength with {opp_count} linked opportunities"

        return True, ""

    async def validate_can_delete_weakness(self, node_id: str) -> tuple[bool, str]:
        """Validate that a weakness can be deleted.

        Weakness can only be deleted if it has no linked risks.

        Args:
            node_id: Weakness node_id

        Returns:
            (can_delete, reason) tuple
        """
        query = """
        MATCH (w:Weakness {node_id: $node_id})-[:CREATES]->(risk:Risk)
        RETURN count(risk) as risk_count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})

        if not result:
            return False, "Weakness not found"

        risk_count = result[0]["risk_count"]
        if risk_count > 0:
            return False, f"Cannot delete Weakness with {risk_count} linked risks"

        return True, ""

    async def get_or_create_swot_hub(self, account_id: str, user_id: str) -> str:
        """Get existing SWOT Analysis hub or create if doesn't exist.

        Args:
            account_id: Account identifier
            user_id: User creating the hub

        Returns:
            node_id of SWOT Analysis hub
        """
        # Check if hub exists
        query = """
        MATCH (acc:Account {account_id: $account_id})-[:AFFECTED_BY_ANALYSIS]->(swot:SWOTAnalysis)
        RETURN swot.node_id as node_id
        LIMIT 1
        """
        result = await self.neo4j.execute_query(query, {"account_id": account_id})

        if result:
            return result[0]["node_id"]

        # Create hub if doesn't exist
        import uuid

        swot_node_id = f"swot_{account_id}_{uuid.uuid4().hex[:8]}"

        create_query = """
        MATCH (acc:Account {account_id: $account_id})
        MERGE (swot:SWOTAnalysis {node_id: $node_id})
        SET swot.display_name = $display_name,
            swot.account_id = $account_id,
            swot.created_time = COALESCE(swot.created_time, datetime()),
            swot.last_modified = datetime(),
            swot.created_by = COALESCE(swot.created_by, $user_id),
            swot.last_modified_by = $user_id
        MERGE (acc)-[:AFFECTED_BY_ANALYSIS]->(swot)
        MERGE (swot)-[:BELONGS_TO]->(acc)
        RETURN swot.node_id as node_id
        """

        result = await self.neo4j.execute_write_query(
            create_query,
            {
                "account_id": account_id,
                "node_id": swot_node_id,
                "display_name": f"SWOT Analysis for {account_id}",
                "user_id": user_id,
            },
        )

        if not result:
            raise Exception("Failed to create SWOT Analysis hub")

        logger.info(f"Created SWOT Analysis hub {swot_node_id} for account {account_id}")
        return result[0]["node_id"]


async def get_graph_validation_service(
    neo4j: Neo4jService,
) -> GraphValidationService:
    """Dependency injection for GraphValidationService.

    Args:
        neo4j: Neo4j service instance

    Returns:
        GraphValidationService instance
    """
    return GraphValidationService(neo4j)
