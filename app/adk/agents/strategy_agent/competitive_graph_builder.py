"""
Graph builder for competitive analysis knowledge graph.
Creates CompetitiveEnvironment, Competitor, and related nodes in Neo4j.
Updated to match new competitive strategy requirements.
"""

import logging
import uuid
from datetime import datetime

from .competitive_models import (
    CompetitiveAnalysis,
    Competitor,
    NamedDetail,
    StrengthWithRisks,
    SubstituteProduct,
    WeaknessWithOpportunities,
)
from .neo4j_tools import Neo4jOperations

logger = logging.getLogger(__name__)


class CompetitiveGraphBuilder:
    """Builds competitive analysis knowledge graph in Neo4j."""

    def __init__(self, neo4j_ops: Neo4jOperations):
        """
        Initialize graph builder.

        Args:
            neo4j_ops: Neo4j operations instance
        """
        self.neo4j_ops = neo4j_ops

    def build_competitive_graph(
        self, analysis: CompetitiveAnalysis, account_id: str, user_id: str
    ) -> dict:
        """
        Build complete competitive analysis graph in Neo4j.

        Args:
            analysis: Competitive analysis with all competitor data
            account_id: Account identifier
            user_id: User identifier

        Returns:
            Dictionary with created node counts
        """
        try:
            created_nodes = {
                "competitive_environment": None,
                "competitors": [],
                "competitor_tactics": [],
                "competitor_value_propositions": [],
                "substitute_products": [],
                "substitute_value_propositions": [],
                "competitor_strengths": [],
                "competitor_weaknesses": [],
                "risks": [],
                "opportunities": [],
                "may_be_substituted_for_relationships": [],
            }

            # Step 1: Create CompetitiveEnvironment node
            logger.info(
                f"Creating CompetitiveEnvironment node for account {account_id}"
            )
            comp_env = self._create_competitive_environment(analysis, account_id)
            created_nodes["competitive_environment"] = comp_env

            # Step 2: Create Competitor nodes and their children
            for competitor in analysis.competitors:
                logger.info(f"Creating competitor: {competitor.name}")

                # Create Competitor node
                competitor_node = self._create_competitor_node(
                    competitor, comp_env["node_id"], account_id
                )
                created_nodes["competitors"].append(competitor_node)

                # Create CompetitorTactic nodes
                for tactic in competitor.marketing_tactics:
                    tactic_node = self._create_competitor_tactic(
                        tactic, competitor_node["node_id"], account_id
                    )
                    created_nodes["competitor_tactics"].append(tactic_node)

                # Create Competitor-level ValueProposition nodes
                for vp in competitor.value_propositions:
                    vp_node = self._create_competitor_value_proposition(
                        vp, competitor_node["node_id"], account_id
                    )
                    created_nodes["competitor_value_propositions"].append(vp_node)

                # Create CompetitorStrength nodes with linked Risk nodes
                for strength in competitor.strengths:
                    strength_node = self._create_competitor_strength(
                        strength, competitor_node["node_id"], account_id, created_nodes
                    )
                    created_nodes["competitor_strengths"].append(strength_node)

                # Create CompetitorWeakness nodes with linked Opportunity nodes
                for weakness in competitor.weaknesses:
                    weakness_node = self._create_competitor_weakness(
                        weakness, competitor_node["node_id"], account_id, created_nodes
                    )
                    created_nodes["competitor_weaknesses"].append(weakness_node)

                # Create SubstituteProduct nodes with single ValueProposition
                for product in competitor.substitute_products:
                    product_node = self._create_substitute_product(
                        product, competitor_node["node_id"], account_id, created_nodes
                    )
                    created_nodes["substitute_products"].append(product_node)

            # Step 3: Create MAY_BE_SUBSTITUTED_FOR relationships
            # Link company Products to SubstituteProducts
            substitution_relationships = self._create_substitution_relationships(
                account_id, created_nodes["substitute_products"]
            )
            created_nodes["may_be_substituted_for_relationships"] = (
                substitution_relationships
            )

            logger.info(
                f"Successfully created competitive graph with {len(created_nodes['competitors'])} competitors"
            )
            return created_nodes

        except Exception as e:
            logger.error(f"Failed to build competitive graph: {e}")
            raise

    def _create_competitive_environment(
        self, analysis: CompetitiveAnalysis, account_id: str
    ) -> dict:
        """Create CompetitiveEnvironment node."""
        node_id = f"competitiveenv_{account_id}_{uuid.uuid4().hex[:8]}"

        query = """
        MERGE (acc:Account {account_id: $account_id})
        ON CREATE SET acc.account_name = $account_id,
                      acc.created_time = datetime(),
                      acc.last_modified = datetime()
        MERGE (ce:CompetitiveEnvironment:Strategy {node_id: $node_id})
        SET ce.account_id = $account_id,
            ce.description = $description,
            ce.created_time = COALESCE(ce.created_time, datetime()),
            ce.last_modified = datetime(),
            ce.created_by = COALESCE(ce.created_by, 'System'),
            ce.last_modified_by = 'System',
            ce.embedding = null
        MERGE (acc)-[:OPERATES_WITHIN]->(ce)
        MERGE (ce)-[:BELONGS_TO]->(acc)
        RETURN ce.node_id as node_id, ce
        """

        result = self.neo4j_ops.connection.execute_query(
            query,
            {
                "node_id": node_id,
                "account_id": account_id,
                "description": analysis.competitive_environment_description,
            },
        )

        return result[0] if result else None

    def _create_competitor_node(
        self, competitor: Competitor, comp_env_id: str, account_id: str
    ) -> dict:
        """Create Competitor node with all fields."""
        node_data = {
            "node_id": f"competitor_{account_id}_{uuid.uuid4().hex[:8]}",
            "display_name": competitor.name,
            "description": competitor.description,
            "references": competitor.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        # Create Competitor node
        node = self.neo4j_ops.create_strategy_node("Competitor", node_data, account_id)

        # Link to CompetitiveEnvironment with IS_KEY_PLAYER relationship
        query = """
        MATCH (c:Competitor {node_id: $competitor_id})
        MATCH (ce:CompetitiveEnvironment {node_id: $comp_env_id})
        MERGE (ce)-[:IS_KEY_PLAYER]->(c)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"competitor_id": node_data["node_id"], "comp_env_id": comp_env_id}
        )

        return node_data

    def _create_competitor_tactic(
        self, tactic: NamedDetail, competitor_id: str, account_id: str
    ) -> dict:
        """Create CompetitorTactic node."""
        node_data = {
            "node_id": f"tactic_{tactic.name.lower().replace(' ', '_')}_{competitor_id[:16]}",
            "display_name": tactic.name,
            "description": tactic.description,
            "references": tactic.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "CompetitorTactic", node_data, account_id
        )

        # Link to Competitor
        query = """
        MATCH (ct:CompetitorTactic {node_id: $tactic_id})
        MATCH (c:Competitor {node_id: $competitor_id})
        MERGE (c)-[:USES_TACTIC]->(ct)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"tactic_id": node_data["node_id"], "competitor_id": competitor_id}
        )

        return node_data

    def _create_competitor_value_proposition(
        self, vp: NamedDetail, competitor_id: str, account_id: str
    ) -> dict:
        """Create ValueProposition node for competitor."""
        node_data = {
            "node_id": f"value_{account_id}_{uuid.uuid4().hex[:8]}",
            "display_name": vp.name,
            "description": vp.description,
            "references": vp.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "ValueProposition", node_data, account_id
        )

        # Link to Competitor
        query = """
        MATCH (vp:ValueProposition {node_id: $vp_id})
        MATCH (c:Competitor {node_id: $competitor_id})
        MERGE (c)-[:HAS_VALUE_PROPOSITION]->(vp)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"vp_id": node_data["node_id"], "competitor_id": competitor_id}
        )

        return node_data

    def _create_competitor_strength(
        self,
        strength: StrengthWithRisks,
        competitor_id: str,
        account_id: str,
        created_nodes: dict,
    ) -> dict:
        """Create CompetitorStrength node with linked Risk nodes."""
        node_data = {
            "node_id": f"strength_{strength.name.lower().replace(' ', '_')}_{competitor_id[:16]}",
            "display_name": strength.name,
            "description": strength.description,
            "references": strength.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "CompetitorStrength", node_data, account_id
        )

        # Link to Competitor
        query = """
        MATCH (cs:CompetitorStrength {node_id: $strength_id})
        MATCH (c:Competitor {node_id: $competitor_id})
        MERGE (c)-[:HAS_STRENGTH]->(cs)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"strength_id": node_data["node_id"], "competitor_id": competitor_id}
        )

        # Create linked Risk nodes and CREATES relationships
        for risk_item in strength.risks:
            risk_node = self.neo4j_ops.create_strategy_node(
                "Risk",
                {
                    "risk_id": f"risk_{risk_item.name.lower().replace(' ', '_')}_{node_data['node_id'][:16]}",
                    "display_name": risk_item.name,
                    "description": risk_item.description,
                    "references": risk_item.references,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            created_nodes["risks"].append(risk_node)

            # Create CREATES relationship: CompetitorStrength -> Risk
            creates_query = """
            MATCH (cs:CompetitorStrength {node_id: $strength_id})
            MATCH (r:Risk {risk_id: $risk_id})
            MERGE (cs)-[:CREATES]->(r)
            """
            self.neo4j_ops.connection.execute_query(
                creates_query,
                {"strength_id": node_data["node_id"], "risk_id": risk_node["risk_id"]},
            )

        return node_data

    def _create_competitor_weakness(
        self,
        weakness: WeaknessWithOpportunities,
        competitor_id: str,
        account_id: str,
        created_nodes: dict,
    ) -> dict:
        """Create CompetitorWeakness node with linked Opportunity nodes."""
        node_data = {
            "node_id": f"weakness_{weakness.name.lower().replace(' ', '_')}_{competitor_id[:16]}",
            "display_name": weakness.name,
            "description": weakness.description,
            "references": weakness.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "CompetitorWeakness", node_data, account_id
        )

        # Link to Competitor
        query = """
        MATCH (cw:CompetitorWeakness {node_id: $weakness_id})
        MATCH (c:Competitor {node_id: $competitor_id})
        MERGE (c)-[:HAS_WEAKNESS]->(cw)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"weakness_id": node_data["node_id"], "competitor_id": competitor_id}
        )

        # Create linked Opportunity nodes and CREATES relationships
        for opp_item in weakness.opportunities:
            opp_node = self.neo4j_ops.create_strategy_node(
                "Opportunity",
                {
                    "opportunity_id": f"opp_{opp_item.name.lower().replace(' ', '_')}_{node_data['node_id'][:16]}",
                    "display_name": opp_item.name,
                    "description": opp_item.description,
                    "references": opp_item.references,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            created_nodes["opportunities"].append(opp_node)

            # Create CREATES relationship: CompetitorWeakness -> Opportunity
            creates_query = """
            MATCH (cw:CompetitorWeakness {node_id: $weakness_id})
            MATCH (o:Opportunity {opportunity_id: $opportunity_id})
            MERGE (cw)-[:CREATES]->(o)
            """
            self.neo4j_ops.connection.execute_query(
                creates_query,
                {
                    "weakness_id": node_data["node_id"],
                    "opportunity_id": opp_node["opportunity_id"],
                },
            )

        return node_data

    def _create_substitute_product(
        self,
        product: SubstituteProduct,
        competitor_id: str,
        account_id: str,
        created_nodes: dict,
    ) -> dict:
        """Create SubstituteProduct node with single ValueProposition."""
        node_data = {
            "node_id": f"substitute_{product.name.lower().replace(' ', '_')}_{competitor_id[:16]}",
            "product_name": product.name,
            "description": product.description,
            "references": product.references,
            "product_detail_page": "",  # Optional field, would be populated if available
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "SubstituteProduct", node_data, account_id
        )

        # Link to Competitor
        query = """
        MATCH (sp:SubstituteProduct {node_id: $product_id})
        MATCH (c:Competitor {node_id: $competitor_id})
        MERGE (c)-[:OFFERS_PRODUCT]->(sp)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"product_id": node_data["node_id"], "competitor_id": competitor_id}
        )

        # Create single ValueProposition for this substitute product
        vp = product.value_proposition
        vp_node = self.neo4j_ops.create_strategy_node(
            "ValueProposition",
            {
                "node_id": f"value_{account_id}_{uuid.uuid4().hex[:8]}",
                "display_name": vp.name,
                "description": vp.description,
                "references": vp.references,
                "created_time": datetime.now(),
                "last_modified": datetime.now(),
                "created_by": "System",
                "last_modified_by": "System",
                "embedding": None,
            },
            account_id,
        )
        created_nodes["substitute_value_propositions"].append(vp_node)

        # Link VP to SubstituteProduct
        vp_query = """
        MATCH (vp:ValueProposition {node_id: $vp_id})
        MATCH (sp:SubstituteProduct {node_id: $product_id})
        MERGE (sp)-[:HAS_VALUE_PROPOSITION]->(vp)
        """
        self.neo4j_ops.connection.execute_query(
            vp_query, {"vp_id": vp_node["node_id"], "product_id": node_data["node_id"]}
        )

        return node_data

    def _create_substitution_relationships(
        self, account_id: str, substitute_products: list[dict]
    ) -> list[dict]:
        """
        Create MAY_BE_SUBSTITUTED_FOR relationships between company Products and SubstituteProducts.
        This links the company's products to competing substitute products.
        """
        relationships = []

        # Get all company products
        query = """
        MATCH (p:Product)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        RETURN p.product_id as product_id, p.product_name as product_name
        """
        company_products = self.neo4j_ops.connection.execute_query(
            query, {"account_id": account_id}
        )

        # Create MAY_BE_SUBSTITUTED_FOR relationship from each company product to all substitute products
        for company_product in company_products:
            for substitute_product in substitute_products:
                rel_query = """
                MATCH (p:Product {product_id: $product_id})
                MATCH (sp:SubstituteProduct {node_id: $substitute_id})
                MERGE (p)-[:MAY_BE_SUBSTITUTED_FOR]->(sp)
                RETURN p.product_id as from_product, sp.node_id as to_substitute
                """
                result = self.neo4j_ops.connection.execute_query(
                    rel_query,
                    {
                        "product_id": company_product["product_id"],
                        "substitute_id": substitute_product["node_id"],
                    },
                )
                if result:
                    relationships.append(result[0])

        logger.info(
            f"Created {len(relationships)} MAY_BE_SUBSTITUTED_FOR relationships"
        )
        return relationships
