"""
Graph builder for marketing strategy and customer intelligence knowledge graph.
Creates CustomerProfile nodes and marketing strategy nodes in Neo4j.
"""

import logging
from typing import Dict, List
from datetime import datetime
import uuid
from .marketing_models import (
    MarketingResearchReport,
    ProductCategory,
    IdealCustomerProfile
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
        self,
        research_report: MarketingResearchReport,
        account_id: str,
        user_id: str
    ) -> Dict:
        """
        Build complete marketing strategy graph in Neo4j.

        Args:
            research_report: Marketing research with customer profiles
            account_id: Account identifier
            user_id: User identifier

        Returns:
            Dictionary with created node counts
        """
        try:
            created_nodes = {
                'customer_profiles': [],
                'problem_awareness_strategies': [],
                'brand_awareness_strategies': [],
                'consideration_strategies': [],
                'conversion_strategies': [],
                'loyalty_strategies': [],
                'are_sold_to_relationships': []
            }

            # Iterate through each product category
            for product_category in research_report.product_categories:
                logger.info(f"Processing product category: {product_category.category_name}")

                # For each ideal customer profile in this category
                for icp in product_category.ideal_customer_profiles:
                    logger.info(f"Creating customer profile for category: {product_category.category_name}")

                    # Step 1: Create CustomerProfile node
                    customer_profile_node = self._create_customer_profile(
                        icp,
                        account_id
                    )
                    created_nodes['customer_profiles'].append(customer_profile_node)

                    # Step 2: Create 5 strategy nodes linked to this customer profile
                    problem_node = self._create_problem_awareness_strategy(
                        icp.problem_awareness_strategy,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    created_nodes['problem_awareness_strategies'].append(problem_node)

                    brand_node = self._create_brand_awareness_strategy(
                        icp.brand_awareness_strategy,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    created_nodes['brand_awareness_strategies'].append(brand_node)

                    consideration_node = self._create_consideration_strategy(
                        icp.consideration_strategy,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    created_nodes['consideration_strategies'].append(consideration_node)

                    conversion_node = self._create_conversion_strategy(
                        icp.conversion_strategy,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    created_nodes['conversion_strategies'].append(conversion_node)

                    loyalty_node = self._create_loyalty_strategy(
                        icp.loyalty_strategy,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    created_nodes['loyalty_strategies'].append(loyalty_node)

                    # Step 3: Link ProductCategory to CustomerProfile
                    # Find existing ProductCategory node by category_name and create IS_MARKETED_TO relationship
                    relationship = self._link_product_category_to_customer_profile(
                        product_category.category_name,
                        customer_profile_node['node_id'],
                        account_id
                    )
                    if relationship:
                        created_nodes['are_sold_to_relationships'].append(relationship)

            logger.info(f"Successfully created marketing graph with {len(created_nodes['customer_profiles'])} customer profiles")
            return created_nodes

        except Exception as e:
            logger.error(f"Failed to build marketing graph: {e}")
            raise

    def _create_customer_profile(self, icp: IdealCustomerProfile, account_id: str) -> Dict:
        """Create CustomerProfile node with all fields."""
        # Generate unique ID
        node_id = f"icp_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': icp.narrative,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        # Use create_strategy_node which handles MERGE
        node = self.neo4j_ops.create_strategy_node('CustomerProfile', node_data, account_id)
        return node_data

    def _create_problem_awareness_strategy(
        self,
        description: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """Create ProblemAwarenessStrategy node."""
        node_id = f"problemaware_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': description,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        node = self.neo4j_ops.create_strategy_node('ProblemAwarenessStrategy', node_data, account_id)

        # Link to CustomerProfile
        query = """
        MATCH (pas:ProblemAwarenessStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:DISCOVERS_THE_PROBLEM_BY]->(pas)
        """
        self.neo4j_ops.connection.execute_query(query, {
            'strategy_id': node_id,
            'profile_id': customer_profile_id
        })

        return node_data

    def _create_brand_awareness_strategy(
        self,
        description: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """Create BrandAwarenessStrategy node."""
        node_id = f"brandaware_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': description,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        node = self.neo4j_ops.create_strategy_node('BrandAwarenessStrategy', node_data, account_id)

        # Link to CustomerProfile
        query = """
        MATCH (bas:BrandAwarenessStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:DISCOVERS_OUR_BRAND_BY]->(bas)
        """
        self.neo4j_ops.connection.execute_query(query, {
            'strategy_id': node_id,
            'profile_id': customer_profile_id
        })

        return node_data

    def _create_consideration_strategy(
        self,
        description: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """Create ConsiderationStrategy node."""
        node_id = f"consideration_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': description,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        node = self.neo4j_ops.create_strategy_node('ConsiderationStrategy', node_data, account_id)

        # Link to CustomerProfile
        query = """
        MATCH (cs:ConsiderationStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:CONSIDERS_OUR_BRAND_BECAUSE]->(cs)
        """
        self.neo4j_ops.connection.execute_query(query, {
            'strategy_id': node_id,
            'profile_id': customer_profile_id
        })

        return node_data

    def _create_conversion_strategy(
        self,
        description: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """Create ConversionStrategy node."""
        node_id = f"conversion_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': description,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        node = self.neo4j_ops.create_strategy_node('ConversionStrategy', node_data, account_id)

        # Link to CustomerProfile
        query = """
        MATCH (cvs:ConversionStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:PURCHASES_OUR_BRAND_BECAUSE]->(cvs)
        """
        self.neo4j_ops.connection.execute_query(query, {
            'strategy_id': node_id,
            'profile_id': customer_profile_id
        })

        return node_data

    def _create_loyalty_strategy(
        self,
        description: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """Create LoyaltyStrategy node."""
        node_id = f"loyalty_{uuid.uuid4().hex}"

        node_data = {
            'node_id': node_id,
            'description': description,
            'created_time': datetime.now(),
            'last_modified': datetime.now(),
            'created_by': 'System',
            'last_modified_by': 'System',
            'embedding': None
        }

        node = self.neo4j_ops.create_strategy_node('LoyaltyStrategy', node_data, account_id)

        # Link to CustomerProfile
        query = """
        MATCH (ls:LoyaltyStrategy {node_id: $strategy_id})
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:BECOMES_AN_ADVOCATE_BECAUSE]->(ls)
        """
        self.neo4j_ops.connection.execute_query(query, {
            'strategy_id': node_id,
            'profile_id': customer_profile_id
        })

        return node_data

    def _link_product_category_to_customer_profile(
        self,
        category_name: str,
        customer_profile_id: str,
        account_id: str
    ) -> Dict:
        """
        Link existing ProductCategory node to CustomerProfile.
        This creates the IS_MARKETED_TO relationship.
        """
        query = """
        MATCH (pc:ProductCategory)-[:BELONGS_TO]->(:Account {account_id: $account_id})
        WHERE pc.category_name = $category_name
        MATCH (cp:CustomerProfile {node_id: $profile_id})
        MERGE (cp)-[:IS_MARKETED_TO]->(pc)
        RETURN pc.category_name as category, cp.node_id as profile
        """
        result = self.neo4j_ops.connection.execute_query(query, {
            'account_id': account_id,
            'category_name': category_name,
            'profile_id': customer_profile_id
        })

        if result:
            logger.info(f"Linked ProductCategory '{category_name}' to CustomerProfile")
            return result[0]
        else:
            logger.warning(f"ProductCategory '{category_name}' not found for account {account_id}")
            return None
