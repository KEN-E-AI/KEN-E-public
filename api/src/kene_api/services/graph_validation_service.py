"""Validation service for knowledge graph operations.

Provides shared validation logic for graph node operations.
"""

import logging
import re

from ..constants import VALID_NODE_TYPES
from ..database import Neo4jService
from ..exceptions import ValidationException

logger = logging.getLogger(__name__)

# URL validation pattern: allows http/https/relative URLs
URL_PATTERN = re.compile(
    r"^(https?://[^\s]+|/[^\s]*|[a-zA-Z0-9][a-zA-Z0-9\-]*(\.[a-zA-Z0-9][a-zA-Z0-9\-]*)*(/[^\s]*)?)$"
)


def validate_node_type(node_type: str) -> None:
    """Validate node type against whitelist to prevent Cypher injection.

    This function protects against Cypher injection attacks by ensuring that only
    valid node types are used in dynamic Cypher query construction.

    Args:
        node_type: Node type to validate

    Raises:
        ValidationException: If node type is not in the whitelist
    """
    if node_type not in VALID_NODE_TYPES:
        valid_types = ", ".join(sorted(VALID_NODE_TYPES))
        raise ValidationException(
            f"Invalid node type '{node_type}'. Must be one of: {valid_types}",
            field_name="node_type",
        )


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
            node_type: Type of node (e.g., "Product", "ProductCategory", "Account")

        Returns:
            True if node exists, False otherwise

        Raises:
            ValidationException: If node_type is not valid
        """
        # Validate node_type to prevent Cypher injection
        validate_node_type(node_type)

        # Special handling for Account nodes which use account_id instead of node_id
        if node_type == "Account":
            query = f"MATCH (n:{node_type} {{account_id: $node_id}}) RETURN n LIMIT 1"
        else:
            query = f"MATCH (n:{node_type} {{node_id: $node_id}}) RETURN n LIMIT 1"

        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        return len(result) > 0

    async def validate_can_delete_product_category(
        self, node_id: str
    ) -> tuple[bool, str]:
        """Validate that a product category can be deleted.

        ProductCategory deletion will cascade delete all products and their value propositions.
        This is always allowed.

        Args:
            node_id: ProductCategory node_id

        Returns:
            (can_delete, reason) tuple
        """
        # No validation needed - cascade delete handles cleanup
        return True, ""

    async def validate_can_delete_product(self, node_id: str) -> tuple[bool, str]:
        """Validate that a product can be deleted.

        Product deletion will cascade delete all its value propositions.
        This is always allowed.

        Args:
            node_id: Product node_id

        Returns:
            (can_delete, reason) tuple
        """
        # No validation needed - cascade delete handles cleanup
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
            return (
                False,
                f"Cannot delete Strength with {opp_count} linked opportunities",
            )

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

        logger.info(
            f"Created SWOT Analysis hub {swot_node_id} for account {account_id}"
        )
        return result[0]["node_id"]

    def validate_url_format(self, url: str) -> bool:
        """Validate URL format.

        Accepts:
        - Full URLs: https://example.com/path
        - Protocol-relative: //example.com/path
        - Absolute paths: /path/to/resource
        - Relative paths: path/to/resource

        Args:
            url: URL string to validate

        Returns:
            True if valid URL format, False otherwise
        """
        if not url or not url.strip():
            return False

        # Allow common URL patterns
        return bool(URL_PATTERN.match(url.strip()))

    def validate_non_empty_string(
        self, value: str, field_name: str
    ) -> tuple[bool, str]:
        """Validate that string is not empty after trimming whitespace.

        Args:
            value: String value to validate
            field_name: Name of field being validated (for error message)

        Returns:
            (is_valid, error_message) tuple
        """
        if not value or not value.strip():
            return False, f"{field_name} cannot be empty or contain only whitespace"

        return True, ""

    async def validate_unique_product_category_name(
        self, account_id: str, product_name: str, exclude_node_id: str | None = None
    ) -> tuple[bool, str]:
        """Check if product category name is unique within account.

        Args:
            account_id: Account identifier
            product_name: Product category name to check
            exclude_node_id: Optional node_id to exclude (for updates)

        Returns:
            (is_unique, error_message) tuple
        """
        query = """
        MATCH (cat:ProductCategory {account_id: $account_id, product_name: $product_name})
        WHERE $exclude_node_id IS NULL OR cat.node_id <> $exclude_node_id
        RETURN count(cat) as count
        """
        result = await self.neo4j.execute_query(
            query,
            {
                "account_id": account_id,
                "product_name": product_name,
                "exclude_node_id": exclude_node_id,
            },
        )

        count = result[0]["count"] if result else 0
        if count > 0:
            return (
                False,
                f"Product category with name '{product_name}' already exists in this account",
            )

        return True, ""

    async def validate_unique_product_name(
        self,
        account_id: str,
        product_name: str,
        category_node_id: str,
        exclude_node_id: str | None = None,
    ) -> tuple[bool, str]:
        """Check if product name is unique within category.

        Args:
            account_id: Account identifier
            product_name: Product name to check
            category_node_id: Category node_id to check within
            exclude_node_id: Optional node_id to exclude (for updates)

        Returns:
            (is_unique, error_message) tuple
        """
        query = """
        MATCH (cat:ProductCategory {node_id: $category_node_id})-[:INCLUDES_PRODUCT]->(p:Product {product_name: $product_name})
        WHERE p.account_id = $account_id
        AND ($exclude_node_id IS NULL OR p.node_id <> $exclude_node_id)
        RETURN count(p) as count
        """
        result = await self.neo4j.execute_query(
            query,
            {
                "account_id": account_id,
                "product_name": product_name,
                "category_node_id": category_node_id,
                "exclude_node_id": exclude_node_id,
            },
        )

        count = result[0]["count"] if result else 0
        if count > 0:
            return (
                False,
                f"Product with name '{product_name}' already exists in this category",
            )

        return True, ""

    async def validate_unique_display_name(
        self,
        account_id: str,
        node_type: str,
        display_name: str,
        exclude_node_id: str | None = None,
    ) -> tuple[bool, str]:
        """Check if display_name is unique for node type within account.

        Used for Strength, Weakness, Opportunity, Risk, Goal, ValueProposition.

        Args:
            account_id: Account identifier
            node_type: Type of node (e.g., "Strength", "Goal")
            display_name: Display name to check
            exclude_node_id: Optional node_id to exclude (for updates)

        Returns:
            (is_unique, error_message) tuple

        Raises:
            ValidationException: If node_type is not valid
        """
        # Validate node_type to prevent Cypher injection
        validate_node_type(node_type)

        query = f"""
        MATCH (n:{node_type} {{account_id: $account_id, display_name: $display_name}})
        WHERE $exclude_node_id IS NULL OR n.node_id <> $exclude_node_id
        RETURN count(n) as count
        """
        result = await self.neo4j.execute_query(
            query,
            {
                "account_id": account_id,
                "display_name": display_name,
                "exclude_node_id": exclude_node_id,
            },
        )

        count = result[0]["count"] if result else 0
        if count > 0:
            return (
                False,
                f"{node_type} with display name '{display_name}' already exists in this account",
            )

        return True, ""

    # ==================== COMPETITIVE STRATEGY VALIDATION ====================

    async def validate_can_delete_competitor(self, node_id: str) -> tuple[bool, str]:
        """Validate a competitor can be safely deleted.

        Args:
            node_id: Competitor node_id

        Returns:
            (can_delete, error_message) tuple
        """
        # Check for dependent tactics
        query = """
        MATCH (c:Competitor {node_id: $node_id})-[:USES_TACTIC]->(ct:CompetitorTactic)
        RETURN count(ct) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        tactic_count = result[0]["count"] if result else 0

        if tactic_count > 0:
            return (
                False,
                f"Cannot delete Competitor with {tactic_count} dependent tactics",
            )

        # Check for dependent strengths
        query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_STRENGTH]->(cs:CompetitorStrength)
        RETURN count(cs) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        strength_count = result[0]["count"] if result else 0

        if strength_count > 0:
            return (
                False,
                f"Cannot delete Competitor with {strength_count} dependent strengths",
            )

        # Check for dependent weaknesses
        query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_WEAKNESS]->(cw:CompetitorWeakness)
        RETURN count(cw) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        weakness_count = result[0]["count"] if result else 0

        if weakness_count > 0:
            return (
                False,
                f"Cannot delete Competitor with {weakness_count} dependent weaknesses",
            )

        # Check for dependent substitute products
        query = """
        MATCH (c:Competitor {node_id: $node_id})-[:OFFERS_PRODUCT]->(sp:SubstituteProduct)
        RETURN count(sp) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        product_count = result[0]["count"] if result else 0

        if product_count > 0:
            return (
                False,
                f"Cannot delete Competitor with {product_count} dependent substitute products",
            )

        # Check for dependent value propositions
        query = """
        MATCH (c:Competitor {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN count(vp) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        vp_count = result[0]["count"] if result else 0

        if vp_count > 0:
            return (
                False,
                f"Cannot delete Competitor with {vp_count} dependent value propositions",
            )

        return True, ""

    async def validate_can_delete_competitor_strength(
        self, node_id: str
    ) -> tuple[bool, str]:
        """Validate a competitor strength can be safely deleted.

        Args:
            node_id: CompetitorStrength node_id

        Returns:
            (can_delete, error_message) tuple
        """
        query = """
        MATCH (cs:CompetitorStrength {node_id: $node_id})-[:CREATES]->(r:Risk)
        RETURN count(r) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        count = result[0]["count"] if result else 0

        if count > 0:
            return (
                False,
                f"Cannot delete CompetitorStrength with {count} dependent risks",
            )

        return True, ""

    async def validate_can_delete_competitor_weakness(
        self, node_id: str
    ) -> tuple[bool, str]:
        """Validate a competitor weakness can be safely deleted.

        Args:
            node_id: CompetitorWeakness node_id

        Returns:
            (can_delete, error_message) tuple
        """
        query = """
        MATCH (cw:CompetitorWeakness {node_id: $node_id})-[:CREATES]->(o:Opportunity)
        RETURN count(o) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        count = result[0]["count"] if result else 0

        if count > 0:
            return (
                False,
                f"Cannot delete CompetitorWeakness with {count} dependent opportunities",
            )

        return True, ""

    async def validate_can_delete_substitute_product(
        self, node_id: str
    ) -> tuple[bool, str]:
        """Validate a substitute product can be safely deleted.

        Args:
            node_id: SubstituteProduct node_id

        Returns:
            (can_delete, error_message) tuple
        """
        query = """
        MATCH (sp:SubstituteProduct {node_id: $node_id})-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        RETURN count(vp) as count
        """
        result = await self.neo4j.execute_query(query, {"node_id": node_id})
        count = result[0]["count"] if result else 0

        if count > 0:
            return (
                False,
                f"Cannot delete SubstituteProduct with {count} dependent value propositions",
            )

        return True, ""


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
