"""
Graph builder for marketing strategy and customer intelligence knowledge graph.
Creates CustomerProfile nodes and marketing strategy nodes in Neo4j.
"""

import logging
import uuid
from datetime import datetime

from .marketing_models import (
    IdealCustomerProfile,
    MarketingResearchReport,
)
from .neo4j_tools import Neo4jOperations

logger = logging.getLogger(__name__)


class MarketingGraphBuilder:
    """Builds marketing strategy knowledge graph in Neo4j."""

    def __init__(self, neo4j_ops: Neo4jOperations):
        """
        Initialize graph builder.

        Args:
            neo4j_ops: Neo4j operations instance
        """
        self.neo4j_ops = neo4j_ops

    def build_marketing_graph(
        self, research_report: MarketingResearchReport, account_id: str, user_id: str
    ) -> dict:
        """
        Build complete marketing strategy graph in Neo4j.

        Updated approach: Creates master CustomerProfile nodes WITHOUT strategies,
        then for each product category creates strategy nodes scoped to both the
        category and the profile.

        Structure:
        1. Create master CustomerProfile nodes (2-5 total, no strategies)
        2. For each ProductCategory:
           - For each customer_strategy in the mapping:
             - Create 5 strategy nodes (ProblemAwarenessStrategy, etc.)
             - Link each strategy to BOTH ProductCategory AND CustomerProfile
             - Create IS_MARKETED_TO relationship

        Args:
            research_report: Marketing research with master profiles and product mappings
            account_id: Account identifier
            user_id: User identifier

        Returns:
            Dictionary with created node counts
        """
        try:
            created_nodes = {
                "customer_profiles": [],
                "problem_awareness_strategies": [],
                "brand_awareness_strategies": [],
                "consideration_strategies": [],
                "conversion_strategies": [],
                "loyalty_strategies": [],
                "is_marketed_to_relationships": [],
            }

            # Phase 1: Create master CustomerProfile nodes (2-5 total, NO strategies)
            profile_node_map = {}  # lowercase display_name -> node_id

            logger.info(
                f"Phase 1: Creating {len(research_report.ideal_customer_profiles)} master customer profiles (without strategies)"
            )

            for icp in research_report.ideal_customer_profiles:
                logger.info(f"Creating master profile: {icp.display_name}")

                # Create CustomerProfile node (no strategies attached yet)
                customer_profile_node = self._create_customer_profile(icp, account_id)
                created_nodes["customer_profiles"].append(customer_profile_node)
                # Store with lowercase key and strip whitespace for case-insensitive lookup
                profile_key = icp.display_name.lower().strip()
                profile_node_map[profile_key] = customer_profile_node["node_id"]
                logger.info(f"Stored profile in map with key: '{profile_key}' (length: {len(profile_key)})")

            # Phase 2: For each ProductCategory, create strategies scoped to category+profile
            # Calculate expected strategy count for validation
            expected_strategy_count = sum(
                len(mapping.customer_strategies) * 5  # 5 strategies per customer_strategy
                for mapping in research_report.product_category_mappings
            )
            logger.info(
                f"Phase 2: Creating product-scoped marketing strategies for {len(research_report.product_category_mappings)} product categories"
            )
            logger.info(f"Expected to create {expected_strategy_count} total strategies (5 per customer strategy)")
            logger.info(f"Product mappings data: {[(m.category_name, len(m.customer_strategies)) for m in research_report.product_category_mappings]}")
            logger.info(f"Available profile keys in map: {list(profile_node_map.keys())}")

            skipped_profiles = []  # Track skipped profiles for detailed error reporting

            # Batch fetch all product category IDs to avoid N+1 query pattern
            category_names = [m.category_name for m in research_report.product_category_mappings]
            logger.info(f"Attempting to fetch product categories: {category_names}")
            category_id_map = self._get_product_category_node_ids(category_names, account_id)
            logger.info(f"Fetched {len(category_id_map)} product category IDs from Neo4j: {category_id_map}")
            logger.info(f"Categories requested but not found: {[name for name in category_names if name not in category_id_map]}")

            for mapping in research_report.product_category_mappings:
                logger.info(
                    f"Processing product category '{mapping.category_name}' with {len(mapping.customer_strategies)} customer strategies"
                )

                # Get the ProductCategory node ID from pre-fetched map
                product_category_id = category_id_map.get(mapping.category_name)

                if not product_category_id:
                    logger.warning(
                        f"ProductCategory '{mapping.category_name}' not found in graph, skipping strategies"
                    )
                    continue

                # For each customer strategy in this product category
                for customer_strategy in mapping.customer_strategies:
                    profile_name = customer_strategy.customer_profile_name
                    profile_name_lower = profile_name.lower().strip()  # Normalize for lookup
                    strategy = customer_strategy.strategy

                    logger.info(f"Looking up profile with key: '{profile_name_lower}' (length: {len(profile_name_lower)}) for category '{mapping.category_name}'")

                    # Validate profile reference exists (case-insensitive)
                    if profile_name_lower not in profile_node_map:
                        skipped_profiles.append({
                            "profile_name": profile_name,
                            "category": mapping.category_name
                        })
                        logger.warning(
                            f"Profile '{profile_name}' (normalized: '{profile_name_lower}', length: {len(profile_name_lower)}) referenced in category '{mapping.category_name}' not found in master profile list. Available keys: {list(profile_node_map.keys())}"
                        )
                        continue

                    profile_node_id = profile_node_map[profile_name_lower]

                    logger.info(
                        f"Creating strategies for '{profile_name}' in category '{mapping.category_name}'"
                    )

                    # Create 5 strategy nodes scoped to ProductCategory + CustomerProfile
                    problem_node = self._create_problem_awareness_strategy(
                        strategy.problem_awareness_strategy,
                        customer_profile_id=profile_node_id,
                        product_category_id=product_category_id,
                        account_id=account_id,
                        references=strategy.references,
                    )
                    created_nodes["problem_awareness_strategies"].append(problem_node)

                    brand_node = self._create_brand_awareness_strategy(
                        strategy.brand_awareness_strategy,
                        customer_profile_id=profile_node_id,
                        product_category_id=product_category_id,
                        account_id=account_id,
                        references=strategy.references,
                    )
                    created_nodes["brand_awareness_strategies"].append(brand_node)

                    consideration_node = self._create_consideration_strategy(
                        strategy.consideration_strategy,
                        customer_profile_id=profile_node_id,
                        product_category_id=product_category_id,
                        account_id=account_id,
                        references=strategy.references,
                    )
                    created_nodes["consideration_strategies"].append(
                        consideration_node
                    )

                    conversion_node = self._create_conversion_strategy(
                        strategy.conversion_strategy,
                        customer_profile_id=profile_node_id,
                        product_category_id=product_category_id,
                        account_id=account_id,
                        references=strategy.references,
                    )
                    created_nodes["conversion_strategies"].append(conversion_node)

                    loyalty_node = self._create_loyalty_strategy(
                        strategy.loyalty_strategy,
                        customer_profile_id=profile_node_id,
                        product_category_id=product_category_id,
                        account_id=account_id,
                        references=strategy.references,
                    )
                    created_nodes["loyalty_strategies"].append(loyalty_node)

                    # Create IS_MARKETED_TO relationship (ProductCategory -> CustomerProfile)
                    relationship = self._link_product_category_to_customer_profile(
                        product_category_id,
                        profile_node_id,
                        account_id,
                    )
                    if relationship:
                        created_nodes["is_marketed_to_relationships"].append(
                            relationship
                        )

            # Validate strategy count - we create 5 strategy types per profile
            # Count all created strategies across all 5 types
            actual_strategy_count = (
                len(created_nodes["problem_awareness_strategies"])
                + len(created_nodes["brand_awareness_strategies"])
                + len(created_nodes["consideration_strategies"])
                + len(created_nodes["conversion_strategies"])
                + len(created_nodes["loyalty_strategies"])
            )
            if actual_strategy_count != expected_strategy_count:
                error_msg = (
                    f"Strategy count mismatch: expected {expected_strategy_count}, "
                    f"but created {actual_strategy_count}. "
                )
                if skipped_profiles:
                    error_msg += f"Skipped {len(skipped_profiles)} profile references: "
                    error_msg += ", ".join(
                        f"'{s['profile_name']}' in category '{s['category']}'"
                        for s in skipped_profiles
                    )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info(
                f"Successfully created marketing graph: {len(created_nodes['customer_profiles'])} profiles, "
                f"{len(created_nodes['problem_awareness_strategies'])} strategy sets"
            )
            return created_nodes

        except Exception as e:
            logger.error(f"Failed to build marketing graph: {e}", exc_info=True)
            logger.error(f"Exception type: {type(e).__name__}, Exception args: {e.args}")
            raise

    def _get_product_category_node_ids(
        self, category_names: list[str], account_id: str
    ) -> dict[str, str]:
        """
        Get node_ids for multiple ProductCategories by name in a single query.

        This method batches multiple category lookups to avoid N+1 query pattern.

        Args:
            category_names: List of product category names
            account_id: Account identifier

        Returns:
            Dictionary mapping category_name -> node_id for found categories
        """
        if not category_names:
            return {}

        query = """
        MATCH (pc:ProductCategory)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        WHERE toLower(pc.product_name) IN [name IN $category_names | toLower(name)]
        RETURN pc.product_name as category_name, pc.node_id as node_id
        """
        logger.info(f"Querying Neo4j for product categories with account_id: {account_id}, category_names: {category_names}")
        result = self.neo4j_ops.connection.execute_query(
            query,
            {"account_id": account_id, "category_names": category_names},
        )

        # Build mapping of category_name -> node_id (case-insensitive match)
        category_map = {}
        logger.info(f"Neo4j query returned {len(result)} rows")
        for record in result:
            category_name = record["category_name"]
            node_id = record["node_id"]
            logger.info(f"Found ProductCategory in Neo4j: '{category_name}' -> {node_id}")
            # Store with original case from database
            category_map[category_name] = node_id

        return category_map

    def _get_product_category_node_id(
        self, category_name: str, account_id: str
    ) -> str | None:
        """
        Get the node_id of a ProductCategory by name.

        Args:
            category_name: Name of the product category
            account_id: Account identifier

        Returns:
            node_id of the ProductCategory, or None if not found
        """
        query = """
        MATCH (pc:ProductCategory)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        WHERE toLower(pc.product_name) = toLower($category_name)
        RETURN pc.node_id as node_id
        """
        result = self.neo4j_ops.connection.execute_query(
            query,
            {"account_id": account_id, "category_name": category_name},
        )

        if result and len(result) > 0:
            return result[0]["node_id"]
        return None

    def _create_customer_profile(
        self, icp: IdealCustomerProfile, account_id: str
    ) -> dict:
        """
        Create CustomerProfile node with identifying information only.

        Note: Strategies are NOT created here. They are created per product category.
        Note: created_time, last_modified, created_by, last_modified_by are set by create_strategy_node
        """
        # Generate unique ID
        node_id = f"icp_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "display_name": icp.display_name.lower(),
            "description": icp.narrative,
            "references": icp.references,
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        # Use create_strategy_node which handles MERGE and sets timestamps/audit fields
        self.neo4j_ops.create_strategy_node("CustomerProfile", node_data, account_id)
        return node_data

    def _create_problem_awareness_strategy(
        self,
        description: str,
        customer_profile_id: str,
        product_category_id: str,
        account_id: str,
        references: list[str] | None = None,
    ) -> dict:
        """
        Create ProblemAwarenessStrategy node scoped to ProductCategory + CustomerProfile.

        Creates relationships to BOTH ProductCategory and CustomerProfile to ensure
        the strategy is properly scoped.
        """
        # Generate unique ID that includes both category and profile for uniqueness
        node_id = f"problemaware_{product_category_id}_{customer_profile_id}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": references or [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        self.neo4j_ops.create_strategy_node(
            "ProblemAwarenessStrategy", node_data, account_id
        )

        # Link to BOTH ProductCategory and CustomerProfile
        query = """
        MATCH (pas:ProblemAwarenessStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MATCH (pc:ProductCategory {node_id: $category_id})
        MERGE (cp)-[:DISCOVERS_THE_PROBLEM_BY]->(pas)
        MERGE (pc)-[:HAS_PROBLEM_AWARENESS_STRATEGY]->(pas)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "strategy_id": node_id,
                "profile_id": customer_profile_id,
                "category_id": product_category_id,
            },
        )

        return node_data

    def _create_brand_awareness_strategy(
        self,
        description: str,
        customer_profile_id: str,
        product_category_id: str,
        account_id: str,
        references: list[str] | None = None,
    ) -> dict:
        """
        Create BrandAwarenessStrategy node scoped to ProductCategory + CustomerProfile.

        Creates relationships to BOTH ProductCategory and CustomerProfile.
        """
        node_id = f"brandaware_{product_category_id}_{customer_profile_id}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": references or [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        self.neo4j_ops.create_strategy_node(
            "BrandAwarenessStrategy", node_data, account_id
        )

        # Link to BOTH ProductCategory and CustomerProfile
        query = """
        MATCH (bas:BrandAwarenessStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MATCH (pc:ProductCategory {node_id: $category_id})
        MERGE (cp)-[:DISCOVERS_OUR_BRAND_BY]->(bas)
        MERGE (pc)-[:HAS_BRAND_AWARENESS_STRATEGY]->(bas)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "strategy_id": node_id,
                "profile_id": customer_profile_id,
                "category_id": product_category_id,
            },
        )

        return node_data

    def _create_consideration_strategy(
        self,
        description: str,
        customer_profile_id: str,
        product_category_id: str,
        account_id: str,
        references: list[str] | None = None,
    ) -> dict:
        """
        Create ConsiderationStrategy node scoped to ProductCategory + CustomerProfile.

        Creates relationships to BOTH ProductCategory and CustomerProfile.
        """
        node_id = f"consideration_{product_category_id}_{customer_profile_id}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": references or [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        self.neo4j_ops.create_strategy_node(
            "ConsiderationStrategy", node_data, account_id
        )

        # Link to BOTH ProductCategory and CustomerProfile
        query = """
        MATCH (cs:ConsiderationStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MATCH (pc:ProductCategory {node_id: $category_id})
        MERGE (cp)-[:CONSIDERS_OUR_BRAND_BECAUSE]->(cs)
        MERGE (pc)-[:HAS_CONSIDERATION_STRATEGY]->(cs)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "strategy_id": node_id,
                "profile_id": customer_profile_id,
                "category_id": product_category_id,
            },
        )

        return node_data

    def _create_conversion_strategy(
        self,
        description: str,
        customer_profile_id: str,
        product_category_id: str,
        account_id: str,
        references: list[str] | None = None,
    ) -> dict:
        """
        Create ConversionStrategy node scoped to ProductCategory + CustomerProfile.

        Creates relationships to BOTH ProductCategory and CustomerProfile.
        """
        node_id = f"conversion_{product_category_id}_{customer_profile_id}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": references or [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        self.neo4j_ops.create_strategy_node(
            "ConversionStrategy", node_data, account_id
        )

        # Link to BOTH ProductCategory and CustomerProfile
        query = """
        MATCH (cvs:ConversionStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MATCH (pc:ProductCategory {node_id: $category_id})
        MERGE (cp)-[:PURCHASES_OUR_BRAND_BECAUSE]->(cvs)
        MERGE (pc)-[:HAS_CONVERSION_STRATEGY]->(cvs)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "strategy_id": node_id,
                "profile_id": customer_profile_id,
                "category_id": product_category_id,
            },
        )

        return node_data

    def _create_loyalty_strategy(
        self,
        description: str,
        customer_profile_id: str,
        product_category_id: str,
        account_id: str,
        references: list[str] | None = None,
    ) -> dict:
        """
        Create LoyaltyStrategy node scoped to ProductCategory + CustomerProfile.

        Creates relationships to BOTH ProductCategory and CustomerProfile.
        """
        node_id = f"loyalty_{product_category_id}_{customer_profile_id}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": references or [],
            "created_time": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        self.neo4j_ops.create_strategy_node("LoyaltyStrategy", node_data, account_id)

        # Link to BOTH ProductCategory and CustomerProfile
        query = """
        MATCH (ls:LoyaltyStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MATCH (pc:ProductCategory {node_id: $category_id})
        MERGE (cp)-[:BECOMES_AN_ADVOCATE_BECAUSE]->(ls)
        MERGE (pc)-[:HAS_LOYALTY_STRATEGY]->(ls)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "strategy_id": node_id,
                "profile_id": customer_profile_id,
                "category_id": product_category_id,
            },
        )

        return node_data

    def _link_product_category_to_customer_profile(
        self, product_category_id: str, customer_profile_id: str, account_id: str
    ) -> dict | None:
        """
        Link existing ProductCategory node to CustomerProfile via IS_MARKETED_TO relationship.

        This relationship indicates that a particular customer profile is targeted for
        a specific product category.

        Args:
            product_category_id: Node ID of the ProductCategory
            customer_profile_id: Node ID of the CustomerProfile
            account_id: Account identifier

        Returns:
            Relationship info dict or None if linking failed
        """
        query = """
        MATCH (pc:ProductCategory {node_id: $category_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (pc)-[:IS_MARKETED_TO]->(cp)
        RETURN pc.product_name as category, cp.node_id as profile
        """
        result = self.neo4j_ops.connection.execute_query(
            query,
            {
                "category_id": product_category_id,
                "profile_id": customer_profile_id,
            },
        )

        if result and len(result) > 0:
            logger.info(
                f"Linked ProductCategory (ID: {product_category_id}) to CustomerProfile (ID: {customer_profile_id})"
            )
            return result[0]
        else:
            logger.warning(
                f"Failed to link ProductCategory {product_category_id} to CustomerProfile {customer_profile_id}"
            )
            return None
