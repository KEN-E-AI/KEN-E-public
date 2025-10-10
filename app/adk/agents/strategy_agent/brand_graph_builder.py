"""
Graph builder for brand guidelines knowledge graph.
Creates BrandIdentity hub and related brand guideline nodes in Neo4j.
"""

import logging
import uuid
from datetime import datetime

from .brand_models import BrandGuidelines
from .neo4j_tools import Neo4jOperations

logger = logging.getLogger(__name__)


class BrandGraphBuilder:
    """Builds brand guidelines knowledge graph in Neo4j."""

    def __init__(self, neo4j_ops: Neo4jOperations):
        """
        Initialize graph builder.

        Args:
            neo4j_ops: Neo4j operations instance
        """
        self.neo4j_ops = neo4j_ops

    def build_brand_graph(
        self, guidelines: BrandGuidelines, account_id: str, user_id: str
    ) -> dict:
        """
        Build complete brand guidelines graph in Neo4j.

        Args:
            guidelines: Brand guidelines with all brand data
            account_id: Account identifier
            user_id: User identifier

        Returns:
            Dictionary with created node counts
        """
        try:
            created_nodes = {
                "brand_identity": None,
                "brand_personality": None,
                "voice_and_tone": None,
                "color_palette": None,
                "typography": None,
                "image_style": None,
                "mission_and_values": None,
            }

            # Step 1: Create BrandIdentity hub node
            logger.info(f"Creating BrandIdentity node for account {account_id}")
            brand_identity = self._create_brand_identity(guidelines, account_id)
            created_nodes["brand_identity"] = brand_identity

            # Step 2: Create all 6 child nodes linked to BrandIdentity
            brand_personality = self._create_brand_personality(
                guidelines.brand_personality, brand_identity["node_id"], account_id
            )
            created_nodes["brand_personality"] = brand_personality

            voice_and_tone = self._create_voice_and_tone(
                guidelines.voice_and_tone, brand_identity["node_id"], account_id
            )
            created_nodes["voice_and_tone"] = voice_and_tone

            color_palette = self._create_color_palette(
                guidelines.color_palette, brand_identity["node_id"], account_id
            )
            created_nodes["color_palette"] = color_palette

            typography = self._create_typography(
                guidelines.typography, brand_identity["node_id"], account_id
            )
            created_nodes["typography"] = typography

            image_style = self._create_image_style(
                guidelines.image_style, brand_identity["node_id"], account_id
            )
            created_nodes["image_style"] = image_style

            mission_and_values = self._create_mission_and_values(
                guidelines.mission_and_values, brand_identity["node_id"], account_id
            )
            created_nodes["mission_and_values"] = mission_and_values

            logger.info("Successfully created brand guidelines graph")
            return created_nodes

        except Exception as e:
            logger.error(f"Failed to build brand graph: {e}")
            raise

    def _create_brand_identity(
        self, guidelines: BrandGuidelines, account_id: str
    ) -> dict:
        """Create BrandIdentity hub node."""
        node_id = f"brand_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": guidelines.brand_identity,
            "references": guidelines.references,
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        # Create BrandIdentity node
        node = self.neo4j_ops.create_strategy_node(
            "BrandIdentity", node_data, account_id
        )

        # Link to Account
        query = """
        MATCH (acc:Account {account_id: $account_id})
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MERGE (acc)-[:FOLLOWS_THESE_BRAND_GUIDELINES]->(bi)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"account_id": account_id, "brand_id": node_id}
        )

        return node_data

    def _create_brand_personality(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create BrandPersonality node."""
        node_id = f"personality_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
        }

        node = self.neo4j_ops.create_strategy_node(
            "BrandPersonality", node_data, account_id
        )

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (bp:BrandPersonality {node_id: $personality_id})
        MERGE (bi)-[:HAS_TRAITS_AND_CHARACTERISTICS]->(bp)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "personality_id": node_id}
        )

        return node_data

    def _create_voice_and_tone(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create VoiceAndTone node."""
        node_id = f"voice_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
        }

        node = self.neo4j_ops.create_strategy_node(
            "VoiceAndTone", node_data, account_id
        )

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (vt:VoiceAndTone {node_id: $voice_id})
        MERGE (bi)-[:USES_COMMUNICATION_STYLE]->(vt)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "voice_id": node_id}
        )

        return node_data

    def _create_color_palette(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create ColorPalette node."""
        node_id = f"color_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
        }

        node = self.neo4j_ops.create_strategy_node(
            "ColorPalette", node_data, account_id
        )

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (cp:ColorPalette {node_id: $color_id})
        MERGE (bi)-[:USES_COLORS]->(cp)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "color_id": node_id}
        )

        return node_data

    def _create_typography(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create Typography node."""
        node_id = f"typo_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
        }

        node = self.neo4j_ops.create_strategy_node("Typography", node_data, account_id)

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (t:Typography {node_id: $typo_id})
        MERGE (bi)-[:USES_FONTS_AND_TYPEFACES]->(t)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "typo_id": node_id}
        )

        return node_data

    def _create_image_style(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create ImageStyle node."""
        node_id = f"image_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
        }

        node = self.neo4j_ops.create_strategy_node("ImageStyle", node_data, account_id)

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (is:ImageStyle {node_id: $image_id})
        MERGE (bi)-[:USES_IMAGE_STYLE]->(is)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "image_id": node_id}
        )

        return node_data

    def _create_mission_and_values(
        self, description: str, brand_identity_id: str, account_id: str
    ) -> dict:
        """Create MissionAndValues node."""
        node_id = f"mission_{uuid.uuid4().hex}"

        node_data = {
            "node_id": node_id,
            "description": description,
            "references": [],
            "created_time": datetime.now(),
            "last_modified": datetime.now(),
            "created_by": "System",
            "last_modified_by": "System",
            "embedding": None,
        }

        node = self.neo4j_ops.create_strategy_node(
            "MissionAndValues", node_data, account_id
        )

        # Link to BrandIdentity
        query = """
        MATCH (bi:BrandIdentity {node_id: $brand_id})
        MATCH (mv:MissionAndValues {node_id: $mission_id})
        MERGE (bi)-[:HAS_MISSION]->(mv)
        """
        self.neo4j_ops.connection.execute_query(
            query, {"brand_id": brand_identity_id, "mission_id": node_id}
        )

        return node_data
