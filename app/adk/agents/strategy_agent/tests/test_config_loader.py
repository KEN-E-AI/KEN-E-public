"""
Unit tests for config_loader module.

Tests Firestore config loading and agent creation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestConfigLoader:
    """Test config loading from Firestore."""

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_load_config_from_firestore_success(self, mock_firestore_client):
        """Test successful config loading from Firestore."""
        from app.adk.agents.strategy_agent.config_loader import (
            load_config_from_firestore,
        )

        # Mock Firestore response
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "test_agent",
            "model": "gemini-2.5-pro",
            "description": "Test agent",
            "instruction": "Test instruction",
            "generate_content_config": {"temperature": 0.3, "max_output_tokens": 2500},
            "metadata": {
                "version": "v1.0.0",
                "variant_name": "test",
                "experiment_id": "test_exp",
            },
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        # Test
        config, metadata, extensions = load_config_from_firestore(
            "test_agent", "test-project"
        )

        # Verify
        assert config.name == "test_agent"
        assert config.model == "gemini-2.5-pro"
        assert metadata["version"] == "v1.0.0"
        assert metadata["variant_name"] == "test"
        assert extensions == {}

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_load_config_strips_unknown_fields_into_extensions(
        self, mock_firestore_client
    ):
        """KEN-E-specific top-level fields (e.g. ``deployment_status``) must
        be stripped before validation against ``LlmAgentConfig`` (which has
        ``extra='forbid'``) and surfaced via the third return value.

        Regression for the staging incident where adding ``deployment_status``
        to ``agent_configs/ken_e_chatbot`` caused the loader to crash and the
        agent to fall back to a retired model.
        """
        from app.adk.agents.strategy_agent.config_loader import (
            load_config_from_firestore,
        )

        deployment_status = {
            "smoke_test_status": "pending",
            "rollout_percentage": 100,
            "environment": "staging",
        }
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "test_agent",
            "model": "gemini-2.5-pro",
            "description": "Test agent",
            "instruction": "Test instruction",
            "generate_content_config": {"temperature": 0.3, "max_output_tokens": 2500},
            "metadata": {"version": "v1.0.0", "variant_name": "test"},
            "deployment_status": deployment_status,
            "future_extension_field": "anything",
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        config, metadata, extensions = load_config_from_firestore(
            "test_agent", "test-project"
        )

        # Validation passed despite unknown top-level fields.
        assert config.name == "test_agent"
        assert config.model == "gemini-2.5-pro"
        # metadata sub-dict is still surfaced.
        assert metadata["version"] == "v1.0.0"
        # Unknown top-level fields land in extensions.
        assert extensions["deployment_status"] == deployment_status
        assert extensions["future_extension_field"] == "anything"
        # ``metadata`` itself is not duplicated into extensions.
        assert "metadata" not in extensions

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_load_config_not_found(self, mock_firestore_client):
        """Test config not found error."""
        from app.adk.agents.strategy_agent.config_loader import (
            load_config_from_firestore,
            ConfigNotFoundError,
        )

        # Mock Firestore response - document doesn't exist
        mock_doc = Mock()
        mock_doc.exists = False

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        # Test - should raise ConfigNotFoundError
        with pytest.raises(ConfigNotFoundError):
            load_config_from_firestore("nonexistent_agent", "test-project")

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_get_current_config_metadata(self, mock_firestore_client):
        """Test getting config metadata without full config."""
        from app.adk.agents.strategy_agent.config_loader import (
            get_current_config_metadata,
        )

        # Mock Firestore response
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "test_agent",
            "model": "gemini-2.5-pro",
            "metadata": {
                "version": "v2.0.0",
                "variant_name": "advanced",
                "experiment_id": "exp_123",
                "updated_at": "2025-10-15T00:00:00Z",
            },
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        # Test
        metadata = get_current_config_metadata("test_agent", "test-project")

        # Verify
        assert metadata["doc_id"] == "test_agent"
        assert metadata["version"] == "v2.0.0"
        assert metadata["variant_name"] == "advanced"
        assert metadata["experiment_id"] == "exp_123"
        assert metadata["model"] == "gemini-2.5-pro"

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_load_config_flat_shape_temperature_flows_into_sdk(
        self, mock_firestore_client
    ):
        """AH-40 AC-10: flat-stored temperature must reach the SDK boundary.

        Storage is flat post-AH-40. The loader reconstructs the nested
        ``generate_content_config`` block before ``LlmAgentConfig.model_validate``
        so downstream readers (Weave summary, agent construction) see the
        SDK shape they expect.
        """
        from app.adk.agents.strategy_agent.config_loader import (
            load_config_from_firestore,
        )

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "ken_e_chatbot",
            "model": "gemini-2.5-pro",
            "description": "Frontend-facing chat agent",
            "instruction": "You are KEN-E...",
            "temperature": 0.7,
            "max_output_tokens": 4096,
            "metadata": {"version": "v1.0.0", "variant_name": "baseline"},
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        config, _metadata, _extensions = load_config_from_firestore(
            "ken_e_chatbot", "test-project"
        )

        assert config.generate_content_config is not None
        assert config.generate_content_config.temperature == 0.7
        assert config.generate_content_config.max_output_tokens == 4096

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_load_config_flat_wins_over_legacy_nested(
        self, mock_firestore_client
    ):
        """Mid-backfill safety: if a doc carries both flat and nested fields,
        flat values win (new contract) and we keep loading without crashing."""
        from app.adk.agents.strategy_agent.config_loader import (
            load_config_from_firestore,
        )

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "ken_e_chatbot",
            "model": "gemini-2.5-pro",
            "description": "Hybrid-shape transitional doc",
            "instruction": "You are KEN-E...",
            "temperature": 0.7,
            "max_output_tokens": 4096,
            # Legacy nested block still present (backfill-in-progress).
            "generate_content_config": {"temperature": 0.1, "max_output_tokens": 500},
            "metadata": {"version": "v1.0.0", "variant_name": "baseline"},
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        config, _metadata, _extensions = load_config_from_firestore(
            "ken_e_chatbot", "test-project"
        )

        assert config.generate_content_config.temperature == 0.7
        assert config.generate_content_config.max_output_tokens == 4096

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_get_current_config_metadata_reads_flat(self, mock_firestore_client):
        """AH-40: ``get_current_config_metadata`` surfaces flat-stored
        temperature and max_output_tokens."""
        from app.adk.agents.strategy_agent.config_loader import (
            get_current_config_metadata,
        )

        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "name": "ken_e_chatbot",
            "model": "gemini-2.5-pro",
            "temperature": 0.7,
            "max_output_tokens": 4096,
            "metadata": {
                "version": "v1.0.0",
                "variant_name": "baseline",
                "experiment_id": "baseline",
                "updated_at": "2026-04-20T12:00:00Z",
            },
        }

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        metadata = get_current_config_metadata("ken_e_chatbot", "test-project")

        assert metadata["temperature"] == 0.7
        assert metadata["max_output_tokens"] == 4096

    @patch("app.adk.agents.strategy_agent.config_loader.firestore.Client")
    def test_get_config_metadata_not_found(self, mock_firestore_client):
        """Test metadata retrieval when config doesn't exist."""
        from app.adk.agents.strategy_agent.config_loader import (
            get_current_config_metadata,
        )

        # Mock Firestore response - document doesn't exist
        mock_doc = Mock()
        mock_doc.exists = False

        mock_collection = Mock()
        mock_collection.document.return_value.get.return_value = mock_doc

        mock_db = Mock()
        mock_db.collection.return_value = mock_collection

        mock_firestore_client.return_value = mock_db

        # Test - should return error dict
        metadata = get_current_config_metadata("nonexistent", "test-project")

        # Verify
        assert "error" in metadata
        assert metadata["error"] == "config_not_found"
        assert metadata["doc_id"] == "nonexistent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
