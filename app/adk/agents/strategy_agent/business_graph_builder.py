"""
Graph builder module for transforming structured business strategies into Neo4j knowledge graph.
Creates nodes and relationships following the knowledge graph design document.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from .neo4j_tools import Neo4jOperations, get_neo4j_operations
from .structured_models import (
    PESTELAnalysis,
    StrategyDelta,
    StrategyVersion,
    StructuredBusinessStrategy,
    SWOTAnalysis,
)

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and maintains the Neo4j knowledge graph for business strategies."""

    def __init__(self, neo4j_ops: Neo4jOperations = None):
        """
        Initialize the graph builder.

        Args:
            neo4j_ops: Neo4j operations instance (creates new if None)
        """
        self.neo4j_ops = neo4j_ops or get_neo4j_operations()

    def build_strategy_graph(
        self,
        strategy: StructuredBusinessStrategy,
        account_id: str,
        user_id: str = "System",
        version: int = 1,
    ) -> dict[str, Any]:
        """
        Build complete knowledge graph from structured business strategy.

        Args:
            strategy: Structured business strategy
            account_id: Account identifier
            user_id: User creating the strategy
            version: Version number

        Returns:
            Dictionary with created nodes and relationships
        """
        logger.info(f"Building strategy graph for account {account_id}")

        # Track all created nodes
        created_nodes = {
            "account": None,
            "business_value_propositions": [],
            "products": [],
            "value_propositions": [],
            "swot": {},
            "goals": [],
        }

        try:
            # 1. Create or update Account node
            account_node = self._create_account_node(strategy, account_id)
            created_nodes["account"] = account_node

            # 2. Create business-level ValueProposition nodes
            self._create_business_value_propositions(
                strategy.business_value_propositions, account_id, created_nodes
            )

            # 3. Create Product and ValueProposition nodes
            self._create_product_nodes(strategy, account_id, created_nodes)

            # 4. Create SWOT nodes with hub and CREATES relationships
            self._create_swot_nodes(strategy.swot_analysis, account_id, created_nodes)

            # 5. Create Goal nodes
            self._create_goal_nodes(strategy.strategic_goals, account_id, created_nodes)

            logger.info(
                f"Successfully created strategy graph for {strategy.company_name}"
            )
            return created_nodes

        except Exception as e:
            logger.error(f"Failed to build strategy graph: {e}")
            raise

    def _create_account_node(
        self, strategy: StructuredBusinessStrategy, account_id: str
    ) -> dict:
        """
        Update the Account node with agent-derived fields only.

        User-provided fields (account_name, websites, industry, budget, etc.) are
        already set during account creation and should NEVER be overwritten.

        Agent-derived fields that can be updated:
        - company_name: Refined company name (e.g., "HDFC Bank" -> "HDFC Bank Limited")
        - company_overview: Generated company description
        """
        account_data = {
            "account_id": account_id,
            "company_name": strategy.company_name,  # Agents can refine company name
            "company_overview": strategy.company_overview_summary,  # Agents generate overview
        }
        return self.neo4j_ops.merge_account(account_data)

    def _create_business_value_propositions(
        self, value_props: list, account_id: str, created_nodes: dict
    ):
        """Create business-level ValueProposition nodes linked to Account."""
        for vp in value_props:
            node_id = f"value_{account_id}_{uuid.uuid4().hex[:8]}"
            vp_node = self.neo4j_ops.create_strategy_node(
                "ValueProposition",
                {
                    "node_id": node_id,
                    "display_name": vp.display_name,
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
            created_nodes["business_value_propositions"].append(vp_node)

            # Link to Account
            query = """
            MATCH (acc:Account {account_id: $account_id})
            MATCH (vp:ValueProposition {node_id: $node_id})
            MERGE (acc)-[:HAS_VALUE_PROPOSITION]->(vp)
            """
            self.neo4j_ops.connection.execute_query(
                query, {"account_id": account_id, "node_id": node_id}
            )

    def _create_product_nodes(
        self, strategy: StructuredBusinessStrategy, account_id: str, created_nodes: dict
    ):
        """Create Product and ValueProposition nodes."""
        for category in strategy.product_portfolio:
            # Generate unique node_id for ProductCategory
            category_node_id = f"productcat_{account_id}_{uuid.uuid4().hex[:8]}"

            # Generate description for category from its value propositions
            category_desc = (
                f"Product category containing {len(category.products)} products. "
            )
            if category.value_propositions:
                category_desc += "Key value propositions: " + ", ".join(
                    [vp.display_name for vp in category.value_propositions[:3]]
                )

            # Create category
            query = """
            MATCH (acc:Account {account_id: $account_id})
            MERGE (cat:ProductCategory:Strategy {node_id: $node_id})
            SET cat.product_name = $category_name,
                cat.created_time = COALESCE(cat.created_time, datetime()),
                cat.last_modified = datetime(),
                cat.created_by = COALESCE(cat.created_by, 'System'),
                cat.last_modified_by = 'System',
                cat.description = $description,
                cat.embedding = null
            MERGE (cat)-[:BELONGS_TO]->(acc)
            MERGE (acc)-[:OFFERS_PRODUCTS]->(cat)
            """
            self.neo4j_ops.connection.execute_query(
                query,
                {
                    "account_id": account_id,
                    "node_id": category_node_id,
                    "category_name": category.category_name,
                    "description": category_desc,
                },
            )

            # Create category-level value propositions
            for vp in category.value_propositions:
                vp_node_id = f"value_{account_id}_{uuid.uuid4().hex[:8]}"
                vp_node = self.neo4j_ops.create_strategy_node(
                    "ValueProposition",
                    {
                        "node_id": vp_node_id,
                        "display_name": vp.display_name,
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

                # Link to ProductCategory
                vp_link_query = """
                MATCH (cat:ProductCategory {node_id: $category_node_id})
                MATCH (vp:ValueProposition {node_id: $vp_node_id})
                MERGE (cat)-[:HAS_VALUE_PROPOSITION]->(vp)
                """
                self.neo4j_ops.connection.execute_query(
                    vp_link_query,
                    {"category_node_id": category_node_id, "vp_node_id": vp_node_id},
                )

                created_nodes["value_propositions"].append(vp_node)

            # Create products in category with ALL fields
            for product in category.products:
                product_node_id = f"prod_{account_id}_{uuid.uuid4().hex[:8]}"
                prod_node = self.neo4j_ops.create_strategy_node(
                    "Product",
                    {
                        "node_id": product_node_id,
                        "product_name": product.display_name,
                        "description": product.description,
                        "references": product.references,
                        "product_detail_page": "",  # Not in current model, would need to be added
                        "created_time": datetime.now(),
                        "last_modified": datetime.now(),
                        "created_by": "System",
                        "last_modified_by": "System",
                        "embedding": None,
                    },
                    account_id,
                )
                created_nodes["products"].append(prod_node)

                # Link product to category
                link_query = """
                MATCH (cat:ProductCategory {node_id: $category_node_id})
                MATCH (prod:Product {node_id: $product_node_id})
                MERGE (cat)-[:INCLUDES_PRODUCT]->(prod)
                """
                self.neo4j_ops.connection.execute_query(
                    link_query,
                    {
                        "category_node_id": category_node_id,
                        "product_node_id": product_node_id,
                    },
                )

                # Create value propositions for product
                for vp in product.value_propositions:
                    vp_node = self._create_value_proposition(
                        vp, product_node_id, account_id
                    )
                    created_nodes["value_propositions"].append(vp_node)

    def _create_value_proposition(
        self, vp, product_node_id: str, account_id: str
    ) -> dict:
        """Create a ValueProposition node and link to product."""
        vp_node_id = f"value_{account_id}_{uuid.uuid4().hex[:8]}"
        vp_node = self.neo4j_ops.create_strategy_node(
            "ValueProposition",
            {
                "node_id": vp_node_id,
                "display_name": vp.display_name,
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

        # Link to product
        link_query = """
        MATCH (prod:Product {node_id: $product_node_id})
        MATCH (vp:ValueProposition {node_id: $vp_node_id})
        MERGE (prod)-[:HAS_VALUE_PROPOSITION]->(vp)
        """
        self.neo4j_ops.connection.execute_query(
            link_query, {"product_node_id": product_node_id, "vp_node_id": vp_node_id}
        )

        return vp_node

    def _create_swot_nodes(
        self, swot: SWOTAnalysis, account_id: str, created_nodes: dict
    ):
        """Create SWOT analysis nodes with hub node and CREATES relationships."""
        # Step 1: Create SWOTAnalysis hub node
        swot_node_id = f"swot_{account_id}_{uuid.uuid4().hex[:8]}"
        swot_hub_query = """
        MATCH (acc:Account {account_id: $account_id})
        MERGE (swot:SWOTAnalysis {node_id: $node_id})
        SET swot.display_name = $display_name,
            swot.created_time = COALESCE(swot.created_time, datetime()),
            swot.last_modified = datetime(),
            swot.created_by = COALESCE(swot.created_by, 'System'),
            swot.last_modified_by = 'System'
        MERGE (acc)-[:AFFECTED_BY_ANALYSIS]->(swot)
        MERGE (swot)-[:BELONGS_TO]->(acc)
        RETURN swot
        """
        swot_hub = self.neo4j_ops.connection.execute_query(
            swot_hub_query,
            {
                "account_id": account_id,
                "node_id": swot_node_id,
                "display_name": f"SWOT Analysis for {account_id}",
            },
        )

        # Step 2: Process strengths_and_opportunities
        for link in swot.strengths_and_opportunities:
            # Create strength node
            strength_node_id = f"strength_{account_id}_{uuid.uuid4().hex[:8]}"
            strength_node = self.neo4j_ops.create_strategy_node(
                "Strength",
                {
                    "node_id": strength_node_id,
                    "display_name": link.strength.id.replace("-", " ").title(),
                    "description": link.strength.description,
                    "references": link.strength.references,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            created_nodes["swot"]["strengths"] = created_nodes["swot"].get(
                "strengths", []
            )
            created_nodes["swot"]["strengths"].append(strength_node)

            # Link strength to SWOT hub
            self._link_to_swot_hub(strength_node, swot_node_id, "HAS_STRENGTH")

            # Create linked opportunities and CREATES relationships
            for opp_item in link.linked_opportunities:
                opp_node_id = f"opportunity_{account_id}_{uuid.uuid4().hex[:8]}"
                opp_node = self.neo4j_ops.create_strategy_node(
                    "Opportunity",
                    {
                        "node_id": opp_node_id,
                        "display_name": opp_item.id.replace("-", " ").title(),
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
                created_nodes["swot"]["opportunities"] = created_nodes["swot"].get(
                    "opportunities", []
                )
                created_nodes["swot"]["opportunities"].append(opp_node)

                # Create CREATES relationship: Strength -> Opportunity
                creates_query = """
                MATCH (s:Strength {node_id: $strength_node_id})
                MATCH (o:Opportunity {node_id: $opp_node_id})
                MERGE (s)-[:CREATES]->(o)
                """
                self.neo4j_ops.connection.execute_query(
                    creates_query,
                    {"strength_node_id": strength_node_id, "opp_node_id": opp_node_id},
                )

        # Step 3: Process weaknesses_and_risks
        for link in swot.weaknesses_and_risks:
            # Create weakness node
            weakness_node_id = f"weakness_{account_id}_{uuid.uuid4().hex[:8]}"
            weakness_node = self.neo4j_ops.create_strategy_node(
                "Weakness",
                {
                    "node_id": weakness_node_id,
                    "display_name": link.weakness.id.replace("-", " ").title(),
                    "description": link.weakness.description,
                    "references": link.weakness.references,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            created_nodes["swot"]["weaknesses"] = created_nodes["swot"].get(
                "weaknesses", []
            )
            created_nodes["swot"]["weaknesses"].append(weakness_node)

            # Link weakness to SWOT hub
            self._link_to_swot_hub(weakness_node, swot_node_id, "HAS_WEAKNESS")

            # Create linked risks and CREATES relationships
            for risk_item in link.linked_risks:
                risk_node_id = f"risk_{account_id}_{uuid.uuid4().hex[:8]}"
                risk_node = self.neo4j_ops.create_strategy_node(
                    "Risk",
                    {
                        "node_id": risk_node_id,
                        "display_name": risk_item.id.replace("-", " ").title(),
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
                created_nodes["swot"]["risks"] = created_nodes["swot"].get("risks", [])
                created_nodes["swot"]["risks"].append(risk_node)

                # Create CREATES relationship: Weakness -> Risk
                creates_query = """
                MATCH (w:Weakness {node_id: $weakness_node_id})
                MATCH (r:Risk {node_id: $risk_node_id})
                MERGE (w)-[:CREATES]->(r)
                """
                self.neo4j_ops.connection.execute_query(
                    creates_query,
                    {
                        "weakness_node_id": weakness_node_id,
                        "risk_node_id": risk_node_id,
                    },
                )

    def _link_to_swot_hub(self, node: dict, swot_node_id: str, relationship_type: str):
        """Link a SWOT item to the SWOTAnalysis hub node."""
        # Determine node label based on relationship type
        if relationship_type == "HAS_STRENGTH":
            node_label = "Strength"
        elif relationship_type == "HAS_WEAKNESS":
            node_label = "Weakness"
        else:
            return

        if "node_id" in node:
            query = f"""
            MATCH (swot:SWOTAnalysis {{node_id: $swot_node_id}})
            MATCH (n:{node_label} {{node_id: $node_id}})
            MERGE (swot)-[:{relationship_type}]->(n)
            """
            self.neo4j_ops.connection.execute_query(
                query, {"swot_node_id": swot_node_id, "node_id": node["node_id"]}
            )

    def _create_pestel_nodes(
        self, pestel: PESTELAnalysis, account_id: str, created_nodes: dict
    ):
        """
        [DEPRECATED] Create PESTEL analysis nodes.
        PESTEL is now at industry level, not account level.
        Kept for reference - will be used in industry_graph_builder.py
        """
        # First create the PESTELAnalysis anchor node
        pestel_query = """
        MATCH (acc:Account {account_id: $account_id})
        MERGE (p:PESTELAnalysis {display_name: $display_name})
        SET p.created_time = COALESCE(p.created_time, datetime()),
            p.last_modified = datetime()
        MERGE (acc)-[:AFFECTED_BY_ANALYSIS]->(p)
        MERGE (p)-[:BELONGS_TO]->(acc)
        RETURN p
        """
        pestel_node = self.neo4j_ops.connection.execute_query(
            pestel_query,
            {
                "account_id": account_id,
                "display_name": f"PESTEL Analysis for {account_id}",
            },
        )

        # Create factor nodes for each category
        factor_types = [
            ("political", "PoliticalFactor", pestel.political),
            ("economic", "EconomicFactor", pestel.economic),
            ("social", "SocialFactor", pestel.social),
            ("technological", "TechnologicalFactor", pestel.technological),
            ("environmental", "EnvironmentalFactor", pestel.environmental),
            ("legal", "LegalFactor", pestel.legal),
        ]

        for category_name, factor_type, factors in factor_types:
            created_nodes["pestel"][category_name] = []
            for factor in factors:
                node = self.neo4j_ops.create_strategy_node(
                    factor_type,
                    {
                        f"{category_name}factor_id": factor.id,
                        "display_name": factor.id.replace("-", " ").title(),
                        "description": factor.description,
                        "trend": factor.trend,
                        "created_time": datetime.now(),
                        "last_modified": datetime.now(),
                        "created_by": "System",
                        "last_modified_by": "System",
                        "embedding": None,
                    },
                    account_id,
                )
                created_nodes["pestel"][category_name].append(node)

                # Link to PESTEL analysis node
                link_query = f"""
                MATCH (p:PESTELAnalysis {{display_name: $display_name}})
                MATCH (f:{factor_type})
                WHERE elementId(f) = $node_id
                MERGE (p)-[:INCLUDES_FACTOR]->(f)
                """
                self.neo4j_ops.connection.execute_query(
                    link_query,
                    {
                        "display_name": f"PESTEL Analysis for {account_id}",
                        "node_id": node.get("elementId", node.get("id")),
                    },
                )

    def _create_goal_nodes(self, goals: list, account_id: str, created_nodes: dict):
        """Create strategic goal nodes."""
        for goal in goals:
            goal_node_id = f"goal_{account_id}_{uuid.uuid4().hex[:8]}"
            node = self.neo4j_ops.create_strategy_node(
                "Goal",
                {
                    "node_id": goal_node_id,
                    "display_name": goal.display_name,
                    "description": goal.description,
                    "references": goal.references,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            created_nodes["goals"].append(node)
            self._link_to_account(node, account_id, "HAS_GOAL")

    def _create_business_model_nodes(
        self, business_model, account_id: str, created_nodes: dict
    ):
        """Create business model, revenue streams, and cost structure nodes."""
        # Create BusinessModel node with ALL fields
        bm_query = """
        MATCH (acc:Account {account_id: $account_id})
        MERGE (bm:BusinessModel {display_name: $display_name})
        SET bm.created_time = COALESCE(bm.created_time, datetime()),
            bm.last_modified = datetime(),
            bm.created_by = COALESCE(bm.created_by, 'System'),
            bm.last_modified_by = 'System'
        MERGE (acc)-[:OPERATES_ON]->(bm)
        MERGE (bm)-[:BELONGS_TO]->(acc)
        RETURN bm
        """
        bm_node = self.neo4j_ops.connection.execute_query(
            bm_query,
            {
                "account_id": account_id,
                "display_name": business_model.business_model_name,
            },
        )
        created_nodes["business_model"] = bm_node

        # Create RevenueStream nodes with ALL fields
        for revenue_stream in business_model.revenue_streams:
            node = self.neo4j_ops.create_strategy_node(
                "RevenueStream",
                {
                    "revenuestream_id": revenue_stream.id,
                    "display_name": revenue_stream.display_name,
                    "references": [],
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                },
                account_id,
            )
            created_nodes["revenue_streams"].append(node)

            # Link to business model
            link_query = """
            MATCH (bm:BusinessModel {display_name: $bm_name})
            MATCH (rs:RevenueStream {revenuestream_id: $rs_id})
            MERGE (bm)-[:HAS_REVENUE_STREAM]->(rs)
            """
            self.neo4j_ops.connection.execute_query(
                link_query,
                {
                    "bm_name": business_model.business_model_name,
                    "rs_id": revenue_stream.id,
                },
            )

        # Create CostStructure nodes with ALL fields
        for cost_item in business_model.cost_structure:
            node = self.neo4j_ops.create_strategy_node(
                "CostStructure",
                {
                    "coststructure_id": cost_item.id,
                    "display_name": cost_item.display_name,
                    "references": [],
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                },
                account_id,
            )
            created_nodes["cost_structure"].append(node)

            # Link to business model
            link_query = """
            MATCH (bm:BusinessModel {display_name: $bm_name})
            MATCH (cs:CostStructure {coststructure_id: $cs_id})
            MERGE (bm)-[:HAS_COST_STRUCTURE]->(cs)
            """
            self.neo4j_ops.connection.execute_query(
                link_query,
                {"bm_name": business_model.business_model_name, "cs_id": cost_item.id},
            )

    def _create_market_analysis_nodes(
        self, market_analysis, account_id: str, created_nodes: dict
    ):
        """Create market analysis related nodes."""
        # Create IndustryTrend nodes with ALL fields
        for trend in market_analysis.industry_trends:
            node = self.neo4j_ops.create_strategy_node(
                "IndustryTrend",
                {
                    "trend_id": trend.id,
                    "display_name": trend.display_name,
                    "description": trend.description,
                    "created_time": datetime.now(),
                    "last_modified": datetime.now(),
                    "created_by": "System",
                    "last_modified_by": "System",
                    "embedding": None,
                },
                account_id,
            )
            # Could link to opportunities if AI determines correlation

    def _link_to_account(self, node: dict, account_id: str, relationship_type: str):
        """Create a specific relationship from Account to a node."""
        query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        MATCH (n)
        WHERE elementId(n) = $node_id
        MERGE (acc)-[:{relationship_type}]->(n)
        """
        self.neo4j_ops.connection.execute_query(
            query,
            {
                "account_id": account_id,
                "node_id": node.get("elementId", node.get("id")),
            },
        )

    def update_strategy_graph(
        self, account_id: str, deltas: list[StrategyDelta], version: StrategyVersion
    ) -> dict[str, Any]:
        """
        Update existing strategy graph with changes.

        Args:
            account_id: Account identifier
            deltas: List of changes to apply
            version: Version information

        Returns:
            Dictionary with updated nodes
        """
        logger.info(
            f"Updating strategy graph for account {account_id}, version {version.version_number}"
        )

        updated_nodes = []

        for delta in deltas:
            if delta.operation == "create":
                # Create new node
                node = self.neo4j_ops.create_strategy_node(
                    delta.node_type, delta.new_values, account_id
                )
                updated_nodes.append(node)

            elif delta.operation == "update":
                # Update existing node with versioning
                node = self.neo4j_ops.update_strategy_node(
                    delta.node_id, delta.new_values, delta.changed_by
                )
                updated_nodes.append(node)

            elif delta.operation == "delete":
                # Mark node as deleted (soft delete)
                delete_query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                SET n.deleted = true,
                    n.deleted_at = datetime(),
                    n.deleted_by = $user
                """
                self.neo4j_ops.connection.execute_query(
                    delete_query, {"node_id": delta.node_id, "user": delta.changed_by}
                )

        logger.info(
            f"Updated {len(updated_nodes)} nodes for version {version.version_number}"
        )
        return {"updated_nodes": updated_nodes, "version": version.version_number}
