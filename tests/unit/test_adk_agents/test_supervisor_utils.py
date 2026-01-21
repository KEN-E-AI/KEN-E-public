"""Unit tests for supervisor_utils module.

Tests the new session state integration for credentials and organization context.
"""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app directory to the path to avoid full import chain
app_dir = Path(__file__).parents[3] / "app"
sys.path.insert(0, str(app_dir))

# Mock the neo4j dependency before importing supervisor_utils
neo4j_mock = MagicMock()
neo4j_mock.exceptions = MagicMock()
neo4j_mock.exceptions.ServiceUnavailable = Exception
neo4j_mock.exceptions.SessionExpired = Exception
sys.modules["neo4j"] = neo4j_mock
sys.modules["neo4j.exceptions"] = neo4j_mock.exceptions

# Import directly from the module file to avoid triggering full import chain
from adk.agents.utils.supervisor_utils import (
    dispatch_with_context,
    encode_ga_credentials,
    extract_tenant_context,
)


class TestEncodeGaCredentials:
    """Test the encode_ga_credentials helper function."""

    def test_encode_basic_credentials(self):
        """Should encode basic GA credentials to base64 JSON."""
        ga_creds = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "tenant_id": "acc_123",
        }

        result = encode_ga_credentials(ga_creds)

        # Decode and verify
        decoded = json.loads(base64.b64decode(result).decode())
        assert decoded["access_token"] == "test_access_token"
        assert decoded["refresh_token"] == "test_refresh_token"
        assert decoded["tenant_id"] == "acc_123"
        assert decoded["selected_property_ids"] == []
        assert decoded["selected_properties"] == []

    def test_encode_with_property_ids(self):
        """Should include property IDs when present."""
        ga_creds = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "tenant_id": "acc_123",
            "selected_property_ids": ["property_1", "property_2"],
            "selected_properties": [
                {"property_id": "property_1", "display_name": "Website 1"},
                {"property_id": "property_2", "display_name": "Website 2"},
            ],
        }

        result = encode_ga_credentials(ga_creds)

        decoded = json.loads(base64.b64decode(result).decode())
        assert decoded["selected_property_ids"] == ["property_1", "property_2"]
        assert len(decoded["selected_properties"]) == 2
        assert decoded["selected_properties"][0]["property_id"] == "property_1"

    def test_encode_returns_string(self):
        """Should return a string that's base64 encoded."""
        ga_creds = {
            "access_token": "token",
            "refresh_token": "refresh",
            "tenant_id": "acc_123",
        }

        result = encode_ga_credentials(ga_creds)

        assert isinstance(result, str)
        # Should be valid base64
        base64.b64decode(result)  # Will raise if invalid


class TestExtractTenantContext:
    """Test the extract_tenant_context function (existing function)."""

    def test_extract_from_string(self):
        """Should handle plain string input."""
        tenant_id, tenant_context, message = extract_tenant_context("Hello world")

        assert tenant_id is None
        assert tenant_context is None
        assert message == "Hello world"

    def test_extract_from_dict_with_credentials(self):
        """Should extract tenant context from dict."""
        input_data = {
            "message": "Get my analytics",
            "tenant_id": "acc_123",
            "tenant_credentials": "base64_encoded_creds",
            "selected_property_ids": ["prop_1"],
            "account_id": "acc_123",
        }

        tenant_id, tenant_context, message = extract_tenant_context(input_data)

        assert tenant_id == "acc_123"
        assert tenant_context["tenant_id"] == "acc_123"
        assert tenant_context["tenant_credentials"] == "base64_encoded_creds"
        assert tenant_context["account_id"] == "acc_123"
        assert tenant_context["selected_property_ids"] == ["prop_1"]
        assert message == "Get my analytics"


class TestDispatchWithContext:
    """Test the dispatch_with_context wrapper with session state."""

    def test_dispatch_with_tool_context_and_credentials(self):
        """Should read credentials from tool_context.state and build tenant_context."""
        # Mock dispatch function
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="GA analytics result")
        wrapped = dispatch_with_context(mock_dispatch)

        # Mock ToolContext with session state
        mock_tool_context = MagicMock()
        mock_tool_context.state = {
            "account_id": "acc_123",
            "ga_credentials": {
                "access_token": "test_token",
                "refresh_token": "test_refresh",
                "tenant_id": "acc_123",
                "selected_property_ids": ["prop_1"],
                "selected_properties": [],
            },
        }

        # Mock organization context loading
        with patch(
            "adk.agents.utils.supervisor_utils.load_organization_context"
        ) as mock_load:
            mock_load.return_value = "# Company Context\nTest Company"

            # Call wrapper
            result = wrapped("Get my analytics", tool_context=mock_tool_context)

            # Verify dispatch was called with injected context
            assert mock_dispatch.called
            call_args = mock_dispatch.call_args

            # First arg should be the query (with org context injected)
            query_arg = call_args[0][0]
            assert "[ORGANIZATION CONTEXT]" in query_arg
            assert "Get my analytics" in query_arg

            # Second arg should be tenant_context with encoded credentials
            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg is not None
            assert tenant_context_arg["tenant_id"] == "acc_123"
            assert "tenant_credentials" in tenant_context_arg
            assert tenant_context_arg["account_id"] == "acc_123"

            # Verify organization context was loaded
            mock_load.assert_called_once_with(account_id="acc_123")

            # Result should be the dispatch function's return value
            assert result == "GA analytics result"

    def test_dispatch_with_tool_context_no_credentials(self):
        """Should handle account_id without GA credentials."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="News result")
        wrapped = dispatch_with_context(mock_dispatch)

        # Tool context with only account_id (no GA creds)
        mock_tool_context = MagicMock()
        mock_tool_context.state = {
            "account_id": "acc_123",
        }

        with patch(
            "adk.agents.utils.supervisor_utils.load_organization_context"
        ) as mock_load:
            mock_load.return_value = "# Company Context\nTest Company"

            result = wrapped("Get latest news", tool_context=mock_tool_context)

            # Should call dispatch with minimal tenant_context
            call_args = mock_dispatch.call_args
            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg == {"account_id": "acc_123"}

    def test_dispatch_without_tool_context_json_fallback(self):
        """Should fall back to JSON parsing when no tool_context."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="Result")
        wrapped = dispatch_with_context(mock_dispatch)

        # JSON input (legacy format)
        json_input = json.dumps({
            "message": "Get analytics",
            "tenant_id": "acc_123",
            "tenant_credentials": "base64_creds",
            "account_id": "acc_123",
        })

        with patch(
            "adk.agents.utils.supervisor_utils.load_organization_context"
        ) as mock_load:
            mock_load.return_value = None  # No org context

            result = wrapped(json_input, tool_context=None)

            # Should parse JSON and extract message
            call_args = mock_dispatch.call_args
            query_arg = call_args[0][0]
            assert query_arg == "Get analytics"  # Extracted message, not JSON

            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg["tenant_id"] == "acc_123"

    def test_dispatch_without_tool_context_plain_string(self):
        """Should handle plain string when no tool_context and not JSON."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="Result")
        wrapped = dispatch_with_context(mock_dispatch)

        result = wrapped("Simple query", tool_context=None)

        # Should pass through plain string
        call_args = mock_dispatch.call_args
        query_arg = call_args[0][0]
        assert query_arg == "Simple query"

        tenant_context_arg = call_args[0][1]
        assert tenant_context_arg is None

    def test_dispatch_handles_dict_result(self):
        """Should extract 'result' key from dict return values."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value={"result": "Extracted result"})
        wrapped = dispatch_with_context(mock_dispatch)

        result = wrapped("Query", tool_context=None)

        assert result == "Extracted result"

    def test_dispatch_organization_context_loading_failure(self):
        """Should gracefully handle org context loading errors."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="Result")
        wrapped = dispatch_with_context(mock_dispatch)

        mock_tool_context = MagicMock()
        mock_tool_context.state = {"account_id": "acc_123"}

        with patch(
            "adk.agents.utils.supervisor_utils.load_organization_context"
        ) as mock_load:
            mock_load.side_effect = Exception("Neo4j connection error")

            # Should not raise, should continue without org context
            result = wrapped("Query", tool_context=mock_tool_context)

            assert result == "Result"
            # Dispatch should still be called
            assert mock_dispatch.called
