"""Unit tests for supervisor_utils module.

Tests the new session state integration for credentials and organization context.
"""

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
    extract_tenant_context,
    invoke_agent_sync,
)


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
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="GA analytics result")
        wrapped = dispatch_with_context(mock_dispatch)

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

        with patch(
            "adk.agents.utils.supervisor_utils.HierarchicalContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.load_executive_summary.return_value = "# Company Context\nTest Company"
            mock_manager.inject_context.return_value = "[ORGANIZATION CONTEXT]\n# Company Context\nTest Company\n[END CONTEXT]\n\nGet my analytics"
            mock_manager.get_total_tokens.return_value = 100

            result = wrapped("Get my analytics", tool_context=mock_tool_context)

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args

            query_arg = call_args[0][0]
            assert "[ORGANIZATION CONTEXT]" in query_arg
            assert "Get my analytics" in query_arg

            # Credentials flow via McpToolset header_provider now, not encoded in tenant_context
            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg is not None
            assert tenant_context_arg["tenant_id"] == "acc_123"
            assert tenant_context_arg["account_id"] == "acc_123"
            assert tenant_context_arg["selected_property_ids"] == ["prop_1"]
            # tenant_credentials key no longer present (credentials flow via headers)
            assert "tenant_credentials" not in tenant_context_arg

            mock_manager_class.assert_called_once_with("acc_123")
            mock_manager.load_executive_summary.assert_called_once()
            mock_manager.inject_context.assert_called_once_with("Get my analytics")

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

        # Mock HierarchicalContextManager
        with patch(
            "adk.agents.utils.supervisor_utils.HierarchicalContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.load_executive_summary.return_value = "# Company Context\nTest Company"
            mock_manager.inject_context.return_value = "[ORGANIZATION CONTEXT]\n# Company Context\n[END CONTEXT]\n\nGet latest news"
            mock_manager.get_total_tokens.return_value = 100

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

        # Mock HierarchicalContextManager
        with patch(
            "adk.agents.utils.supervisor_utils.HierarchicalContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.load_executive_summary.return_value = None  # No org context

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

        # Mock HierarchicalContextManager to raise an error
        with patch(
            "adk.agents.utils.supervisor_utils.HierarchicalContextManager"
        ) as mock_manager_class:
            mock_manager_class.side_effect = Exception("Neo4j connection error")

            # Should not raise, should continue without org context
            result = wrapped("Query", tool_context=mock_tool_context)

            assert result == "Result"
            # Dispatch should still be called
            assert mock_dispatch.called


class TestInvokeAgentSyncState:
    """Test that invoke_agent_sync passes initial state to child session."""

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_create_session_called_with_state(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Should pass state dict to create_session when provided."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async.return_value = iter([])

        mock_agent = MagicMock()
        mock_agent.name = "test_agent"

        ga_state = {"ga_credentials": {"access_token": "tok_123"}}

        invoke_agent_sync(
            mock_agent, "test query", state=ga_state
        )

        mock_session_service.create_session.assert_called_once()
        call_kwargs = mock_session_service.create_session.call_args[1]
        assert call_kwargs["state"] == ga_state

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_create_session_called_without_state(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Should pass state=None to create_session when not provided."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async.return_value = iter([])

        mock_agent = MagicMock()
        mock_agent.name = "test_agent"

        invoke_agent_sync(mock_agent, "test query")

        mock_session_service.create_session.assert_called_once()
        call_kwargs = mock_session_service.create_session.call_args[1]
        assert call_kwargs["state"] is None
