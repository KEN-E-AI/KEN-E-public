"""Unit tests for supervisor_utils module.

Tests the new session state integration for credentials and organization context.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    invoke_pipeline,
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

    def test_dispatch_with_tool_context_and_org_context_in_state(self):
        """Should use org context from session state and skip Neo4j."""
        mock_dispatch = MagicMock(
            __name__="mock_dispatch", return_value="GA analytics result"
        )
        wrapped = dispatch_with_context(mock_dispatch)

        mock_tool_context = MagicMock()
        mock_tool_context.state = {
            "account_id": "acc_123",
            "organization_context": "# Company Context\nTest Company",
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
            result = wrapped("Get my analytics", tool_context=mock_tool_context)

            assert mock_dispatch.called
            call_args = mock_dispatch.call_args

            query_arg = call_args[0][0]
            assert "[ORGANIZATION CONTEXT]" in query_arg
            assert "Get my analytics" in query_arg

            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg is not None
            assert tenant_context_arg["tenant_id"] == "acc_123"
            assert tenant_context_arg["account_id"] == "acc_123"
            assert tenant_context_arg["selected_property_ids"] == ["prop_1"]
            assert "tenant_credentials" not in tenant_context_arg

            # Neo4j should NOT be called when org context is in session state
            mock_manager_class.assert_not_called()

            assert result == "GA analytics result"

    def test_dispatch_falls_back_to_neo4j_when_no_org_context_in_state(self):
        """Should fall back to Neo4j when org context is not in session state."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="News result")
        wrapped = dispatch_with_context(mock_dispatch)

        mock_tool_context = MagicMock()
        mock_tool_context.state = {
            "account_id": "acc_123",
        }

        with patch(
            "adk.agents.utils.supervisor_utils.HierarchicalContextManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.load_executive_summary.return_value = (
                "# Company Context\nTest Company"
            )
            mock_manager.inject_context.return_value = "[ORGANIZATION CONTEXT]\n# Company Context\n[END CONTEXT]\n\nGet latest news"

            result = wrapped("Get latest news", tool_context=mock_tool_context)

            # Neo4j SHOULD be called as fallback
            mock_manager_class.assert_called_once_with("acc_123")
            mock_manager.load_executive_summary.assert_called_once()

            call_args = mock_dispatch.call_args
            tenant_context_arg = call_args[0][1]
            assert tenant_context_arg == {"account_id": "acc_123"}

    def test_dispatch_without_tool_context_json_fallback(self):
        """Should fall back to JSON parsing when no tool_context."""
        mock_dispatch = MagicMock(__name__="mock_dispatch", return_value="Result")
        wrapped = dispatch_with_context(mock_dispatch)

        # JSON input (legacy format)
        json_input = json.dumps(
            {
                "message": "Get analytics",
                "tenant_id": "acc_123",
                "tenant_credentials": "base64_creds",
                "account_id": "acc_123",
            }
        )

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
        mock_dispatch = MagicMock(
            __name__="mock_dispatch", return_value={"result": "Extracted result"}
        )
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
        mock_session_service.create_session = AsyncMock()

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield  # makes it an async generator

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_agent"

        ga_state = {"ga_credentials": {"access_token": "tok_123"}}

        invoke_agent_sync(mock_agent, "test query", state=ga_state)

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
        mock_session_service.create_session = AsyncMock()

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield  # makes it an async generator

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_agent"

        invoke_agent_sync(mock_agent, "test query")

        mock_session_service.create_session.assert_called_once()
        call_kwargs = mock_session_service.create_session.call_args[1]
        assert call_kwargs["state"] is None


class TestInvokePipelineState:
    """Test that invoke_pipeline passes state and returns (text, state) tuple."""

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_returns_tuple_with_state(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Should return (response_text, final_state) tuple."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_session = MagicMock()
        mock_session.state = {
            "ga_review_draft": "traffic up 12%",
            "ga_review_feedback": "",
        }
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield  # makes it an async generator

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_pipeline"

        result = invoke_pipeline(mock_agent, "show traffic trends")

        assert isinstance(result, tuple)
        assert len(result) == 3
        text, state, events = result
        assert isinstance(text, str)
        assert isinstance(state, dict)
        assert isinstance(events, list)

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_create_session_called_with_initial_state(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Should pass initial state dict to create_session."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_pipeline"

        initial_state = {"ga_credentials": {"access_token": "tok_abc"}}
        invoke_pipeline(mock_agent, "test query", state=initial_state)

        mock_session_service.create_session.assert_called_once()
        call_kwargs = mock_session_service.create_session.call_args[1]
        assert call_kwargs["state"] == initial_state

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_get_session_called_after_run(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Should call get_session to retrieve final state after runner completes."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_session = MagicMock()
        mock_session.state = {"ga_review_draft": "draft text", "ga_review_feedback": ""}
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_pipeline"

        invoke_pipeline(mock_agent, "test query")

        mock_session_service.get_session.assert_called_once()

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_timeout_returns_error_tuple(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """On TimeoutError, should return (error_text, {}) tuple."""
        import concurrent.futures

        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            # Simulate no running event loop (Python 3.12+ pattern).
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = concurrent.futures.TimeoutError()

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"
            text, state, events = invoke_pipeline(mock_agent, "test query")

        assert "timed out" in text.lower() or "error" in text.lower()
        assert state == {}
        assert events == []

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_exception_returns_error_tuple(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """On a general exception, should return (error_text, {}) tuple."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            # Simulate no running event loop, then a runtime error from asyncio.run().
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = RuntimeError("ADK error")

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"
            text, state, events = invoke_pipeline(mock_agent, "test query")

        assert "error" in text.lower()
        assert state == {}
        assert events == []


class TestLocalEventBufferContract:
    """AC #1: events.append at line ~148 is a local-list buffer, not session.events mutation.

    These tests pin the contract so a future refactor cannot accidentally write
    directly to session.events (which would bypass the framework yield in ADK 2.0).
    """

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_events_returned_match_runner_yield_order(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """Events list returned by invoke_pipeline matches exactly what runner.run_async yielded."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service

        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        # Create three distinct mock events to verify order preservation.
        event_a = MagicMock(name="event_a")
        event_a.content = None
        event_b = MagicMock(name="event_b")
        event_b.content = None
        event_c = MagicMock(name="event_c")
        event_c.content = None

        async def _three_events(*a, **kw):
            for ev in [event_a, event_b, event_c]:
                yield ev

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _three_events

        mock_agent = MagicMock()
        mock_agent.name = "test_pipeline"

        _text, _state, events = invoke_pipeline(mock_agent, "test query")

        assert events == [event_a, event_b, event_c]

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_empty_run_yields_empty_events_list(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """An agent that emits no events produces an empty events list (not None or session.events)."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_session = MagicMock()
        mock_session.state = {}
        mock_session_service.create_session = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=mock_session)

        async def _no_events(*a, **kw):
            return
            yield  # makes it an async generator

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_runner.run_async = _no_events

        mock_agent = MagicMock()
        mock_agent.name = "test_pipeline"

        _text, _state, events = invoke_pipeline(mock_agent, "test query")

        assert events == []
        assert isinstance(events, list)


class TestFrameworkExceptionReraisePropagation:
    """AC #2 (supervisor_utils): only ADK *framework* exceptions escape invoke_pipeline.

    The handler catches ``Exception`` and re-raises anything whose defining module
    is under ``google.adk`` (ADK 2.0 node control-flow signals such as
    NodeTimeoutError / DynamicNodeFailError) so the framework's retry machinery
    sees them. Every non-framework exception — RuntimeError, a GoogleAPICallError
    from ``google.api_core`` — is still converted to the legacy error-tuple.
    NodeInterruptedError (BaseException) propagates regardless.
    """

    class _SimulatedNodeTimeoutError(Exception):
        """Stand-in for ADK's NodeTimeoutError (an Exception defined under google.adk)."""

    # Make the stand-in's defining module match the real ADK framework so the
    # module-origin predicate (is_adk_framework_exception) re-raises it.
    _SimulatedNodeTimeoutError.__module__ = "google.adk.agents._control_flow"

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_base_exception_subclass_propagates(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """A BaseException subclass raised from asyncio.run() propagates out of invoke_pipeline."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        class _SimulatedNodeInterruptedError(BaseException):
            """Stand-in for ADK's NodeInterruptedError."""

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = _SimulatedNodeInterruptedError("interrupted")

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"

            try:
                invoke_pipeline(mock_agent, "test query")
                raised = False
            except _SimulatedNodeInterruptedError:
                raised = True

        assert raised, "BaseException subclass must propagate; invoke_pipeline must not swallow it"

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_adk_framework_exception_propagates(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """An Exception defined under google.adk propagates (simulating NodeTimeoutError)."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = self._SimulatedNodeTimeoutError("node timed out")

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"

            try:
                invoke_pipeline(mock_agent, "test query")
                raised = False
            except self._SimulatedNodeTimeoutError:
                raised = True

        assert raised, "ADK framework exception must propagate; invoke_pipeline must not swallow it"

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_runtime_error_returns_error_tuple(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """RuntimeError (concrete recoverable type) still produces the legacy error-tuple return."""
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = RuntimeError("transient error")

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"
            text, state, events = invoke_pipeline(mock_agent, "test query")

        assert "error" in text.lower()
        assert state == {}
        assert events == []

    @patch("adk.agents.utils.supervisor_utils.Runner")
    @patch("adk.agents.utils.supervisor_utils.InMemoryArtifactService")
    @patch("adk.agents.utils.supervisor_utils.InMemorySessionService")
    def test_non_framework_google_exception_returns_error_tuple(
        self, mock_session_cls, mock_artifact_cls, mock_runner_cls
    ):
        """A non-ADK exception (e.g. GoogleAPICallError from google.api_core) is
        converted to the error-tuple, NOT leaked raw.

        Regression guard for the over-broad-propagation bug: the earlier
        `except (RuntimeError, ValueError, OSError)` let any other exception
        (GoogleAPICallError, httpx errors, KeyError) escape invoke_pipeline.
        Only exceptions defined under ``google.adk`` may propagate now.
        """
        mock_session_service = MagicMock()
        mock_session_cls.return_value = mock_session_service
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        class _SimulatedGoogleAPIError(Exception):
            """Stand-in for google.api_core.exceptions.GoogleAPICallError."""

        _SimulatedGoogleAPIError.__module__ = "google.api_core.exceptions"

        with patch("adk.agents.utils.supervisor_utils.asyncio") as mock_asyncio:
            mock_asyncio.get_running_loop.side_effect = RuntimeError("no running loop")
            mock_asyncio.run.side_effect = _SimulatedGoogleAPIError("backend 503")

            mock_agent = MagicMock()
            mock_agent.name = "test_pipeline"
            text, state, events = invoke_pipeline(mock_agent, "test query")

        assert "error" in text.lower()
        assert state == {}
        assert events == []
