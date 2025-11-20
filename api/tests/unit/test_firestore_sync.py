"""Unit tests for Firestore bidirectional sync functionality.

Tests that Neo4j CRUD operations correctly sync to Firestore documents.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest
from src.kene_api.services.graph_sync_service import GraphSyncService


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service for sync tests."""
    service = Mock()
    service.get_document = Mock(return_value={})
    service.update_document = Mock(return_value=True)
    return service


@pytest.fixture
def graph_sync_service(mock_firestore_service):
    """Create GraphSyncService with mocked Firestore only."""
    # We only need to test Firestore sync methods, so mock Neo4j
    mock_neo4j = Mock()
    mock_validation = Mock()
    return GraphSyncService(mock_neo4j, mock_firestore_service, mock_validation)


# ==================== Marketing Node Sync Tests ====================


class TestMarketingNodeSync:
    """Tests for _sync_marketing_node_to_doc method."""

    def test_create_customer_profile_syncs_to_firestore(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test Neo4j create syncs CustomerProfile to Firestore."""
        doc = {
            "account_id": "acc_test123",
            "customer_profiles": [],
            "problem_awareness_strategies": [],
        }
        node_id = "customerprofile_test123_abc"
        node_data = {
            "node_id": node_id,
            "display_name": "marketing mary",
            "narrative": "Test narrative",
            "references": [],
            "account_id": "acc_test123",
            "created_time": datetime(2025, 1, 1),
            "last_modified": datetime(2025, 1, 1),
        }

        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "CustomerProfile", node_data, "create"
        )

        assert len(doc["customer_profiles"]) == 1
        assert doc["customer_profiles"][0]["node_id"] == node_id
        assert doc["customer_profiles"][0]["display_name"] == "marketing mary"

    def test_update_strategy_syncs_changes_to_firestore(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test Neo4j update syncs strategy changes to Firestore."""
        node_id = "problemaware_cat123_prof456"
        doc = {
            "account_id": "acc_test123",
            "problem_awareness_strategies": [
                {
                    "node_id": node_id,
                    "description": "Original description",
                    "references": [],
                }
            ],
        }

        updated_node_data = {
            "node_id": node_id,
            "description": "Updated description",
            "references": ["https://example.com/updated"],
            "product_category_node_id": "productcat_test123",
            "customer_profile_node_id": "customerprofile_test123",
        }

        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "ProblemAwarenessStrategy", updated_node_data, "update"
        )

        assert len(doc["problem_awareness_strategies"]) == 1
        assert (
            doc["problem_awareness_strategies"][0]["description"]
            == "Updated description"
        )
        assert len(doc["problem_awareness_strategies"][0]["references"]) == 1

    def test_delete_removes_from_firestore(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test Neo4j delete removes node from Firestore."""
        node_id = "brandaware_cat123_prof456"
        doc = {
            "account_id": "acc_test123",
            "brand_awareness_strategies": [
                {"node_id": node_id, "description": "Test"},
                {"node_id": "brandaware_other", "description": "Other"},
            ],
        }

        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "BrandAwarenessStrategy", {}, "delete"
        )

        assert len(doc["brand_awareness_strategies"]) == 1
        assert doc["brand_awareness_strategies"][0]["node_id"] == "brandaware_other"

    def test_sync_all_5_strategy_types(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test sync works for all 5 marketing strategy types."""
        doc = {
            "account_id": "acc_test123",
            "problem_awareness_strategies": [],
            "brand_awareness_strategies": [],
            "consideration_strategies": [],
            "conversion_strategies": [],
            "loyalty_strategies": [],
        }

        strategy_types = [
            ("ProblemAwarenessStrategy", "problemaware_test"),
            ("BrandAwarenessStrategy", "brandaware_test"),
            ("ConsiderationStrategy", "consideration_test"),
            ("ConversionStrategy", "conversion_test"),
            ("LoyaltyStrategy", "loyalty_test"),
        ]

        for node_type, node_id in strategy_types:
            node_data = {"node_id": node_id, "description": f"Test {node_type}"}
            graph_sync_service._sync_marketing_node_to_doc(
                doc, node_id, node_type, node_data, "create"
            )

        # Verify all were added
        assert len(doc["problem_awareness_strategies"]) == 1
        assert len(doc["brand_awareness_strategies"]) == 1
        assert len(doc["consideration_strategies"]) == 1
        assert len(doc["conversion_strategies"]) == 1
        assert len(doc["loyalty_strategies"]) == 1


# ==================== Competitive Node Sync Tests ====================


class TestCompetitiveNodeSync:
    """Tests for _sync_competitive_node_to_doc method."""

    def test_create_competitor_syncs_to_firestore(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test creating competitor syncs to Firestore array."""
        doc = {
            "account_id": "acc_test123",
            "competitive_environment": None,
            "competitors": [],
        }
        node_id = "competitor_test123_abc"
        node_data = {
            "node_id": node_id,
            "display_name": "Test Competitor",
            "description": "Test description",
            "references": [],
        }

        graph_sync_service._sync_competitive_node_to_doc(
            doc, node_id, "Competitor", node_data, "create"
        )

        assert len(doc["competitors"]) == 1
        assert doc["competitors"][0]["node_id"] == node_id

    def test_update_competitive_environment_hub(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test CompetitiveEnvironment hub syncs as singleton (not array)."""
        doc = {
            "account_id": "acc_test123",
            "competitive_environment": None,
            "competitors": [],
        }
        node_id = "competitiveenv_test123_xyz"
        node_data = {
            "node_id": node_id,
            "description": "Competitive environment description",
        }

        graph_sync_service._sync_competitive_node_to_doc(
            doc, node_id, "CompetitiveEnvironment", node_data, "create"
        )

        assert doc["competitive_environment"] is not None
        assert doc["competitive_environment"]["node_id"] == node_id

    def test_delete_competitor_tactic(self, graph_sync_service, mock_firestore_service):
        """Test deleting competitor tactic removes from Firestore."""
        node_id = "tactic_test123_abc"
        doc = {
            "account_id": "acc_test123",
            "competitor_tactics": [
                {"node_id": node_id, "display_name": "To Delete"},
                {"node_id": "tactic_other", "display_name": "Keep"},
            ],
        }

        graph_sync_service._sync_competitive_node_to_doc(
            doc, node_id, "CompetitorTactic", {}, "delete"
        )

        assert len(doc["competitor_tactics"]) == 1
        assert doc["competitor_tactics"][0]["node_id"] == "tactic_other"

    def test_sync_all_competitive_node_types(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test sync for all competitive node types."""
        doc = {
            "account_id": "acc_test123",
            "competitors": [],
            "competitor_tactics": [],
            "competitor_strengths": [],
            "competitor_weaknesses": [],
            "substitute_products": [],
        }

        node_types = [
            ("Competitor", "competitor_test"),
            ("CompetitorTactic", "tactic_test"),
            ("CompetitorStrength", "compstrength_test"),
            ("CompetitorWeakness", "compweakness_test"),
            ("SubstituteProduct", "substitute_test"),
        ]

        for node_type, node_id in node_types:
            node_data = {"node_id": node_id, "display_name": f"Test {node_type}"}
            graph_sync_service._sync_competitive_node_to_doc(
                doc, node_id, node_type, node_data, "create"
            )

        # Verify all were added
        assert len(doc["competitors"]) == 1
        assert len(doc["competitor_tactics"]) == 1
        assert len(doc["competitor_strengths"]) == 1
        assert len(doc["competitor_weaknesses"]) == 1
        assert len(doc["substitute_products"]) == 1


# ==================== Brand Node Sync Tests ====================


class TestBrandNodeSync:
    """Tests for _sync_brand_node_to_doc method."""

    def test_create_brand_identity_hub(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test BrandIdentity hub syncs as singleton."""
        doc = {
            "account_id": "acc_test123",
            "brand_identity": None,
            "brand_personality": None,
        }
        node_id = "brand_test123_xyz"
        node_data = {
            "node_id": node_id,
            "description": "Our brand represents innovation",
        }

        graph_sync_service._sync_brand_node_to_doc(
            doc, node_id, "BrandIdentity", node_data, "create"
        )

        assert doc["brand_identity"] is not None
        assert doc["brand_identity"]["node_id"] == node_id

    def test_update_brand_personality(self, graph_sync_service, mock_firestore_service):
        """Test updating brand personality node."""
        node_id = "personality_test123_abc"
        doc = {
            "account_id": "acc_test123",
            "brand_personality": {
                "node_id": node_id,
                "description": "Original personality",
            },
        }

        updated_data = {"node_id": node_id, "description": "Updated personality traits"}

        graph_sync_service._sync_brand_node_to_doc(
            doc, node_id, "BrandPersonality", updated_data, "update"
        )

        assert doc["brand_personality"]["description"] == "Updated personality traits"

    def test_delete_voice_and_tone(self, graph_sync_service, mock_firestore_service):
        """Test deleting voice_and_tone sets field to None."""
        node_id = "voice_test123_abc"
        doc = {
            "account_id": "acc_test123",
            "voice_and_tone": {"node_id": node_id, "description": "Authoritative"},
        }

        graph_sync_service._sync_brand_node_to_doc(
            doc, node_id, "VoiceAndTone", {}, "delete"
        )

        assert doc["voice_and_tone"] is None

    def test_sync_all_brand_node_types(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test sync for all 7 brand node types."""
        doc = {
            "account_id": "acc_test123",
            "brand_identity": None,
            "brand_personality": None,
            "voice_and_tone": None,
            "color_palette": None,
            "typography": None,
            "image_style": None,
            "mission_and_values": None,
        }

        brand_node_types = [
            ("BrandIdentity", "brand_test"),
            ("BrandPersonality", "personality_test"),
            ("VoiceAndTone", "voice_test"),
            ("ColorPalette", "color_test"),
            ("Typography", "typo_test"),
            ("ImageStyle", "image_test"),
            ("MissionAndValues", "mission_test"),
        ]

        for node_type, node_id in brand_node_types:
            node_data = {"node_id": node_id, "description": f"Test {node_type}"}
            graph_sync_service._sync_brand_node_to_doc(
                doc, node_id, node_type, node_data, "create"
            )

        # Verify all were set (singletons, not arrays)
        assert doc["brand_identity"] is not None
        assert doc["brand_personality"] is not None
        assert doc["voice_and_tone"] is not None
        assert doc["color_palette"] is not None
        assert doc["typography"] is not None
        assert doc["image_style"] is not None
        assert doc["mission_and_values"] is not None


# ==================== Bidirectional Consistency Tests ====================


class TestBidirectionalConsistency:
    """Tests for bidirectional sync consistency."""

    def test_create_then_update_maintains_consistency(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test that create followed by update maintains consistency."""
        doc = {"account_id": "acc_test123", "consideration_strategies": []}
        node_id = "consideration_cat123_prof456"

        # Create
        create_data = {
            "node_id": node_id,
            "description": "Original",
            "references": [],
        }
        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "ConsiderationStrategy", create_data, "create"
        )

        # Update
        update_data = {
            "node_id": node_id,
            "description": "Updated",
            "references": ["https://example.com"],
        }
        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "ConsiderationStrategy", update_data, "update"
        )

        # Verify only one entry exists with updated data
        assert len(doc["consideration_strategies"]) == 1
        assert doc["consideration_strategies"][0]["description"] == "Updated"

    def test_sync_with_missing_firestore_document_creates_structure(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test sync auto-creates arrays if missing from Firestore document."""
        doc = {"account_id": "acc_test123"}  # No arrays yet

        node_data = {"node_id": "conversion_test", "description": "Test"}

        graph_sync_service._sync_marketing_node_to_doc(
            doc, "conversion_test", "ConversionStrategy", node_data, "create"
        )

        # Verify array was created
        assert "conversion_strategies" in doc
        assert len(doc["conversion_strategies"]) == 1

    def test_sync_preserves_other_firestore_fields(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test that sync preserves other fields in Firestore document."""
        doc = {
            "account_id": "acc_test123",
            "customer_profiles": [],
            "custom_field": "should be preserved",
            "metadata": {"version": 1},
        }

        node_data = {
            "node_id": "customerprofile_test",
            "display_name": "test",
            "narrative": "test",
        }

        graph_sync_service._sync_marketing_node_to_doc(
            doc, "customerprofile_test", "CustomerProfile", node_data, "create"
        )

        # Verify other fields preserved
        assert doc["custom_field"] == "should be preserved"
        assert doc["metadata"]["version"] == 1

    def test_multiple_creates_build_array(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test multiple creates build up the array."""
        doc = {"account_id": "acc_test123", "competitors": []}

        for i in range(3):
            node_id = f"competitor_test_{i}"
            node_data = {"node_id": node_id, "display_name": f"Competitor {i}"}
            graph_sync_service._sync_competitive_node_to_doc(
                doc, node_id, "Competitor", node_data, "create"
            )

        assert len(doc["competitors"]) == 3

    def test_delete_non_existent_node_logs_warning(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test deleting non-existent node logs warning but doesn't fail."""
        doc = {"account_id": "acc_test123", "loyalty_strategies": []}

        # Try to delete node that doesn't exist (should not raise exception)
        graph_sync_service._sync_marketing_node_to_doc(
            doc, "nonexistent_node", "LoyaltyStrategy", {}, "delete"
        )

        # Document should be unchanged
        assert len(doc["loyalty_strategies"]) == 0

    def test_update_non_existent_node_creates_it(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test updating non-existent node creates it (eventual consistency)."""
        doc = {"account_id": "acc_test123", "substitute_products": []}

        node_data = {"node_id": "substitute_new", "product_name": "New Product"}

        graph_sync_service._sync_competitive_node_to_doc(
            doc, "substitute_new", "SubstituteProduct", node_data, "update"
        )

        # Should create the node
        assert len(doc["substitute_products"]) == 1

    def test_create_duplicate_updates_instead(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test creating duplicate node updates existing (idempotent)."""
        node_id = "loyalty_test123"
        doc = {
            "account_id": "acc_test123",
            "loyalty_strategies": [{"node_id": node_id, "description": "Original"}],
        }

        new_data = {"node_id": node_id, "description": "Duplicate attempt"}

        graph_sync_service._sync_marketing_node_to_doc(
            doc, node_id, "LoyaltyStrategy", new_data, "create"
        )

        # Should update, not duplicate
        assert len(doc["loyalty_strategies"]) == 1
        assert doc["loyalty_strategies"][0]["description"] == "Duplicate attempt"

    def test_competitive_environment_singleton_behavior(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test CompetitiveEnvironment is singleton, not array."""
        doc = {"account_id": "acc_test123", "competitive_environment": None}

        node1_data = {"node_id": "env_1", "description": "First"}
        graph_sync_service._sync_competitive_node_to_doc(
            doc, "env_1", "CompetitiveEnvironment", node1_data, "create"
        )

        assert doc["competitive_environment"]["node_id"] == "env_1"

        # Second create should replace, not append
        node2_data = {"node_id": "env_2", "description": "Second"}
        graph_sync_service._sync_competitive_node_to_doc(
            doc, "env_2", "CompetitiveEnvironment", node2_data, "create"
        )

        assert doc["competitive_environment"]["node_id"] == "env_2"

    def test_brand_identity_singleton_behavior(
        self, graph_sync_service, mock_firestore_service
    ):
        """Test BrandIdentity is singleton, not array."""
        doc = {"account_id": "acc_test123", "brand_identity": None}

        node_data = {"node_id": "brand_123", "description": "Our brand"}

        graph_sync_service._sync_brand_node_to_doc(
            doc, "brand_123", "BrandIdentity", node_data, "create"
        )

        assert doc["brand_identity"] is not None
        assert doc["brand_identity"]["node_id"] == "brand_123"
