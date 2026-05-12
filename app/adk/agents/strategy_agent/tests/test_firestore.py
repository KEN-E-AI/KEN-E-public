"""Tests for firestore.py - testing the FirestoreClient class and related functions."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
from datetime import datetime

from app.adk.agents.strategy_agent.firestore import (
    FirestoreClient,
    get_default_client,
    parse_json_response,
    extract_field_requirements_from_best_practices,
    extract_validation_criteria_from_guidelines,
    format_new_information,
    ContextManager,
)
from app.adk.agents.strategy_agent.models import StrategyContext


class TestFirestoreClient:
    """Test the FirestoreClient class."""

    def test_initialization_with_project_id(self):
        """Test client initialization with a project ID."""
        with patch("google.cloud.firestore.Client") as MockClient:
            mock_client_instance = Mock()
            MockClient.return_value = mock_client_instance

            client = FirestoreClient(project_id="test-project")

            MockClient.assert_called_once_with(project="test-project")
            assert client.db == mock_client_instance
            assert client.is_initialized() is True

    def test_initialization_with_injected_client(self):
        """Test client initialization with an injected client."""
        mock_client = Mock()
        client = FirestoreClient(client=mock_client)

        assert client.db == mock_client
        assert client.is_initialized() is True

    def test_initialization_failure(self):
        """Test client initialization handles failures gracefully."""
        with patch("google.cloud.firestore.Client") as MockClient:
            MockClient.side_effect = Exception("Connection failed")

            client = FirestoreClient(project_id="test-project")

            assert client.db is None
            assert client.is_initialized() is False

    def test_get_best_practices_sync(self):
        """Test synchronous retrieval of best practices."""
        # Setup mock Firestore client
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "field1": "description1",
            "field2": "description2",
        }
        mock_db.collection().document().get.return_value = mock_doc

        client = FirestoreClient(client=mock_db)
        result = client.get_best_practices_sync("business_strategy")

        assert result is not None
        assert "field1" in result
        assert "field2" in result
        parsed = json.loads(result)
        assert parsed["field1"] == "description1"

    def test_get_best_practices_sync_not_found(self):
        """Test handling when best practices document doesn't exist."""
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.exists = False
        mock_db.collection().document().get.return_value = mock_doc

        client = FirestoreClient(client=mock_db)
        result = client.get_best_practices_sync("business_strategy")

        assert result is None

    def test_save_strategy_document_sync_success(self):
        """Test successful document saving."""
        mock_db = Mock()
        mock_doc_ref = Mock()
        mock_db.collection().document.return_value = mock_doc_ref

        client = FirestoreClient(client=mock_db)
        content = {"test": "data"}

        result = client.save_strategy_document_sync(
            account_id="test_account",
            doc_type="business_strategy",
            content=content,
            user_id="test_user",
        )

        assert result is True
        mock_doc_ref.set.assert_called_once()

        # Verify the document data structure
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["content"] == content
        assert call_args["doc_type"] == "business_strategy"
        assert call_args["account_id"] == "test_account"
        assert call_args["created_by"] == "test_user"
        assert call_args["version"] == 1

    def test_save_strategy_document_sync_no_client(self):
        """Test saving fails gracefully when no client is available."""
        client = FirestoreClient(client=None)
        client.db = None  # Ensure no client

        result = client.save_strategy_document_sync(
            account_id="test_account",
            doc_type="business_strategy",
            content={"test": "data"},
        )

        assert result is False

    def test_save_strategy_document_sync_exception(self):
        """Test saving handles exceptions gracefully."""
        mock_db = Mock()
        mock_db.collection().document().set.side_effect = Exception("Save failed")

        client = FirestoreClient(client=mock_db)

        result = client.save_strategy_document_sync(
            account_id="test_account",
            doc_type="business_strategy",
            content={"test": "data"},
        )

        assert result is False


class TestContextManager:
    """Test the ContextManager class."""

    @pytest.mark.asyncio
    async def test_save_context(self):
        """Test saving context to Firestore."""
        mock_client = Mock(spec=FirestoreClient)
        mock_client.is_initialized.return_value = True
        mock_db = Mock()
        mock_doc_ref = Mock()
        mock_db.collection.return_value.document.return_value = mock_doc_ref
        mock_client.db = mock_db

        manager = ContextManager(firestore_client=mock_client)
        context = StrategyContext(
            account_id="test_account",
            company_name="Test Corp",
            websites=["https://test.com"],
            industry="Technology",
            customer_regions=["USA"],
            user_id="test_user",
        )

        result = await manager.save_context(context)

        assert result is True
        mock_db.collection.assert_called_once_with("accounts/test_account/strategy_processing_state")
        mock_db.collection.return_value.document.assert_called_once_with("current_state")
        mock_doc_ref.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context(self):
        """Test retrieving context from Firestore."""
        mock_client = Mock(spec=FirestoreClient)
        mock_client.is_initialized.return_value = True
        mock_db = Mock()
        mock_doc = Mock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "account_id": "test_account",
            "company_name": "Test Corp",
            "websites": ["https://test.com"],
            "industry": "Technology",
            "customer_regions": ["USA"],
        }
        mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_client.db = mock_db

        manager = ContextManager(firestore_client=mock_client)
        result = await manager.get_context("test_account")

        assert result is not None
        assert result.account_id == "test_account"
        assert result.company_name == "Test Corp"
        mock_db.collection.assert_called_once_with("accounts/test_account/strategy_processing_state")
        mock_db.collection.return_value.document.assert_called_once_with("current_state")


class TestUtilityFunctions:
    """Test utility functions."""

    def test_parse_json_response_direct_json(self):
        """Test parsing direct JSON string."""
        json_str = '{"key": "value", "number": 42}'
        result = parse_json_response(json_str)

        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_parse_json_response_with_text(self):
        """Test parsing JSON embedded in text."""
        text = 'Here is the result: {"key": "value", "number": 42} Done.'
        result = parse_json_response(text)

        assert result is not None
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_parse_json_response_invalid(self):
        """Test handling invalid JSON."""
        text = "This is not JSON"
        result = parse_json_response(text)

        assert result is None

    def test_extract_field_requirements_from_best_practices(self):
        """Test extracting field requirements from best practices."""
        best_practices = json.dumps(
            {
                "field1": "Description of field 1",
                "field2": "Description of field 2",
                "field3": "Description of field 3",
            }
        )

        result = extract_field_requirements_from_best_practices(best_practices)

        assert "# OUTPUT REQUIREMENTS" in result
        assert "- field1" in result
        assert "- field2" in result
        assert "- field3" in result
        assert "DO NOT skip any fields" in result

    def test_extract_validation_criteria_from_guidelines(self):
        """Test extracting validation criteria."""
        guidelines = json.dumps({"guidelines": "Specific review guidelines"})
        best_practices = json.dumps({"field1": "desc1", "field2": "desc2"})

        result = extract_validation_criteria_from_guidelines(guidelines, best_practices)

        assert "# VALIDATION PROCESS" in result
        assert "Check that ALL 2 required fields are present" in result
        assert "- field1" in result
        assert "- field2" in result
        assert "Specific review guidelines" in result

    def test_format_new_information(self):
        """Test formatting new information for prompts."""
        result = format_new_information(
            company_name="Test Corp",
            websites=["https://test.com", "https://blog.test.com"],
            industry="Technology",
            customer_regions=["USA", "Europe"],
            annual_ad_budget=100000.0,
        )

        assert "Test Corp" in result
        assert "https://test.com" in result
        assert "Technology" in result
        assert "USA, Europe" in result
        assert "$100,000.00" in result


class TestLegacyWrappers:
    """Test the legacy wrapper functions."""

    @patch("app.adk.agents.strategy_agent.firestore.get_default_client")
    def test_legacy_save_strategy_document_sync(self, mock_get_client):
        """Test legacy wrapper for save_strategy_document_sync."""
        mock_client = Mock(spec=FirestoreClient)
        mock_client.save_strategy_document_sync.return_value = True
        mock_get_client.return_value = mock_client

        from app.adk.agents.strategy_agent.firestore import save_strategy_document_sync

        result = save_strategy_document_sync(
            account_id="test", doc_type="business_strategy", content={"test": "data"}
        )

        assert result is True
        mock_client.save_strategy_document_sync.assert_called_once()
