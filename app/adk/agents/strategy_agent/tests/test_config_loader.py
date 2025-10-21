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
            "model": "gemini-2.0-flash",
            "description": "Test agent",
            "instruction": "Test instruction",
            "generate_content_config": {"temperature": 0.3, "max_output_tokens": 2500},
            "metadata": {
                "version": "v1.0",
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
        config, metadata = load_config_from_firestore("test_agent", "test-project")

        # Verify
        assert config.name == "test_agent"
        assert config.model == "gemini-2.0-flash"
        assert metadata["version"] == "v1.0"
        assert metadata["variant_name"] == "test"

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
                "version": "v2.0",
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
        assert metadata["version"] == "v2.0"
        assert metadata["variant_name"] == "advanced"
        assert metadata["experiment_id"] == "exp_123"
        assert metadata["model"] == "gemini-2.5-pro"

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
