"""
Tests for dispatch handlers with retry logic.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from .agent_retry import DEFAULT_RETRY_CONFIG, FAST_RETRY_CONFIG
from .dispatch_handlers import (
    dispatch_to_company_news,
    dispatch_to_google_analytics,
    dispatch_to_strategy,
)


@pytest.fixture(autouse=True)
def _isolate_dispatch_handlers():
    """Isolate dispatch tests from unmocked network dependencies.

    Three leaks would otherwise hang or badly slow CI on real GCP calls:

    1. dispatch_to_company_news / dispatch_to_google_analytics resolve their
       specialist via get_registry().get(...), which importlib-imports the
       agent package — and those modules load config from Firestore at import
       time. Specialist invocation is mocked per-test, so a stub agent object
       is sufficient.
    2. dispatch_to_strategy builds a StrategyAgentLogger, which writes to
       Google Cloud Logging. Forcing HAS_CLOUD_LOGGING off selects the
       logger's intended local-only fallback path.
    3. dispatch_to_strategy imports strategy_agent.orchestrator, whose
       module-level reasoning_engines.AdkApp(...) resolves the GCP project via
       a Resource Manager RPC that retries for ~60s without credentials.
       Seeding vertexai.init() with a project short-circuits that lookup.
    """
    import vertexai

    vertexai.init(project="test-project", location="us-central1")

    stub_registry = MagicMock()
    stub_registry.get.return_value = MagicMock(name="stub_specialist_agent")
    with (
        patch("agents.registry.get_registry", return_value=stub_registry),
        patch("agents.strategy_agent.logging_config.HAS_CLOUD_LOGGING", False),
    ):
        yield


class TestDispatchToCompanyNews:
    """Test the dispatch_to_company_news function."""

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_successful_dispatch(self, mock_invoke):
        """Test successful dispatch to company news agent."""
        mock_invoke.return_value = "News about the company"

        result = dispatch_to_company_news("Get news about Acme Corp")

        assert result["status"] == "success"
        assert result["query"] == "Get news about Acme Corp"
        assert result["result"] == "News about the company"
        assert result["source"] == "company_news_specialist"
        assert result["agent"] == "news"
        mock_invoke.assert_called_once()

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_dispatch_with_error(self, mock_invoke):
        """Test dispatch handling errors."""
        mock_invoke.side_effect = ConnectionError("Failed to connect")

        result = dispatch_to_company_news("Get news")

        assert result["status"] == "error"
        assert result["query"] == "Get news"
        assert "Failed to connect" in result["error"]
        assert result["source"] == "company_news_specialist"
        assert result["agent"] == "news"

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_dispatch_with_tenant_context(self, mock_invoke):
        """Test that tenant context is passed but not used for news."""
        mock_invoke.return_value = "News response"

        tenant_context = {
            "tenant_id": "test-org",
            "user_id": "test-user",
        }

        result = dispatch_to_company_news("Get news", tenant_context)

        assert result["status"] == "success"
        # News agent doesn't use tenant context
        assert "tenant_id" not in result


class TestDispatchToGoogleAnalytics:
    """Test the dispatch_to_google_analytics function."""

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_successful_dispatch(self, mock_invoke):
        """Test successful dispatch to Google Analytics agent."""
        mock_invoke.return_value = "Analytics data"

        tenant_context = {"tenant_id": "test-org"}

        result = dispatch_to_google_analytics(
            "Get analytics", tenant_context=tenant_context
        )

        assert result["status"] == "success"
        assert result["query"] == "Get analytics"
        assert result["result"] == "Analytics data"
        assert result["source"] == "google_analytics_specialist"
        assert result["agent"] == "analytics"
        assert result["tenant_id"] == "test-org"

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_dispatch_without_credentials(self, mock_invoke):
        """Test dispatch without any credentials."""
        mock_invoke.return_value = "Limited response"

        with patch.dict(os.environ, {}, clear=True):
            result = dispatch_to_google_analytics("Get data")

        assert result["status"] == "success"
        assert result["tenant_id"] is None

        # Query should not have credential injection
        args = mock_invoke.call_args[0]
        enhanced_query = args[1]
        assert "TENANT_ID:" not in enhanced_query
        assert "TENANT_CREDS:" not in enhanced_query

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_dispatch_with_error(self, mock_invoke):
        """Test error handling in analytics dispatch."""
        mock_invoke.side_effect = TimeoutError("Request timed out")

        result = dispatch_to_google_analytics("Get analytics")

        assert result["status"] == "error"
        assert "Request timed out" in result["error"]
        assert result["source"] == "google_analytics_specialist"


class TestDispatchToStrategy:
    """Test the dispatch_to_strategy function."""

    @patch("agents.strategy_agent.orchestrator.execute_strategy_generation")
    def test_successful_dispatch(self, mock_execute):
        """Test successful dispatch to strategy agent."""
        mock_execute.return_value = {"strategy": "Generated strategy"}

        query = """
        Generate strategy for:
        - company_name: TestCorp
        - industry: Technology
        - account_id: acc_123
        - user_id: usr_456
        - annual_ad_budget: $50,000
        """

        result = dispatch_to_strategy(query)

        assert result["status"] == "success"
        assert result["query"] == query
        assert result["result"] == {"strategy": "Generated strategy"}
        assert result["source"] == "strategy_specialist"
        assert result["agent"] == "strategy"
        assert result["account_id"] == "acc_123"

        # Verify the strategy agent was called with parsed parameters
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["company_name"] == "TestCorp"
        assert call_kwargs["industry"] == "Technology"
        assert call_kwargs["account_id"] == "acc_123"
        assert call_kwargs["user_id"] == "usr_456"
        # The Pydantic model parses the budget string to a float
        assert call_kwargs["annual_ad_budget"] == 50000.0

    @patch("agents.strategy_agent.orchestrator.execute_strategy_generation")
    def test_dispatch_with_tenant_context(self, mock_execute):
        """Test dispatch with tenant context filling missing values."""
        mock_execute.return_value = {"strategy": "Strategy result"}

        query = """
        - company_name: ContextCorp
        - industry: Finance
        """

        tenant_context = {
            "tenant_id": "org_789",
            "account_id": "acc_from_context",
            "user_id": "usr_from_context",
            "project_id": "context-project",
        }

        result = dispatch_to_strategy(query, tenant_context)

        assert result["status"] == "success"
        assert result["account_id"] == "acc_from_context"

        # Verify context values were used
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["account_id"] == "acc_from_context"
        assert call_kwargs["user_id"] == "usr_from_context"
        assert call_kwargs["project_id"] == "context-project"

    @patch("agents.strategy_agent.orchestrator.execute_strategy_generation")
    def test_dispatch_with_validation_error(self, mock_execute):
        """Test handling of Pydantic validation errors."""
        mock_execute.return_value = {"strategy": "Strategy"}

        # Query missing required fields
        query = """
        - industry: Tech
        """

        result = dispatch_to_strategy(query)

        # Should still succeed with defaults applied
        assert result["status"] == "success"

        # Check that defaults were applied for missing fields
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["company_name"] == "Unknown Company"
        assert call_kwargs["account_id"] == "unknown"
        assert call_kwargs["user_id"] == "unknown"

    @patch("agents.strategy_agent.orchestrator.execute_strategy_generation")
    def test_dispatch_with_execution_error(self, mock_execute):
        """Test error handling during strategy execution."""
        mock_execute.side_effect = RuntimeError("Strategy generation failed")

        query = """
        - company_name: ErrorCorp
        - industry: Tech
        - account_id: acc_err
        - user_id: usr_err
        """

        result = dispatch_to_strategy(query)

        assert result["status"] == "error"
        assert "Strategy generation failed" in result["error"]
        assert result["source"] == "strategy_specialist"

    @patch("agents.strategy_agent.orchestrator.execute_strategy_generation")
    def test_dispatch_with_uploaded_documents(self, mock_execute):
        """Test dispatch with uploaded documents."""
        mock_execute.return_value = {"strategy": "Strategy with docs"}

        query = """
        - company_name: DocCorp
        - industry: Healthcare
        - account_id: acc_doc
        - user_id: usr_doc
        - uploaded_documents: gs://bucket/doc1.pdf,gs://bucket/doc2.pdf
        """

        result = dispatch_to_strategy(query)

        assert result["status"] == "success"

        # Verify documents were passed
        call_kwargs = mock_execute.call_args[1]
        # The uploaded_documents are parsed into a list by Pydantic
        assert call_kwargs["uploaded_documents"] == [
            "gs://bucket/doc1.pdf",
            "gs://bucket/doc2.pdf",
        ]

    def test_parameter_extraction_logging(self, caplog):
        """Test that parameter extraction is properly logged."""
        with patch(
            "agents.strategy_agent.orchestrator.execute_strategy_generation"
        ) as mock_execute:
            mock_execute.return_value = {"strategy": "Result"}

            query = """
            - company_name: LogCorp
            - industry: Retail
            - account_id: acc_log
            - user_id: usr_log
            """

            with caplog.at_level(logging.INFO):
                dispatch_to_strategy(query)

            # Check that key steps were logged
            assert "Routing strategy query to specialized agent" in caplog.text
            assert "Successfully validated strategy parameters" in caplog.text
            assert "Strategy agent completed successfully" in caplog.text


class TestRetryIntegration:
    """Test that retry logic is properly integrated."""

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_news_uses_fast_retry_config(self, mock_invoke):
        """News dispatch wires the fast retry config into invoke_agent_with_retry."""
        mock_invoke.return_value = "News"

        dispatch_to_company_news("Query")

        mock_invoke.assert_called_once()
        assert mock_invoke.call_args.kwargs["retry_config"] is FAST_RETRY_CONFIG

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_analytics_uses_default_retry_config(self, mock_invoke):
        """Analytics dispatch wires the default retry config into invoke_agent_with_retry."""
        mock_invoke.return_value = "Analytics"

        dispatch_to_google_analytics("Query")

        mock_invoke.assert_called_once()
        assert mock_invoke.call_args.kwargs["retry_config"] is DEFAULT_RETRY_CONFIG


class TestDispatchToGoogleAnalyticsState:
    """Test that dispatch_to_google_analytics passes session state to child agent."""

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_passes_ga_credentials_as_initial_state(self, mock_invoke):
        """Should pass ga_credentials as initial state when present in tool_context."""
        mock_invoke.return_value = "Analytics data"

        ga_creds = {
            "access_token": "tok_abc",
            "refresh_token": "ref_xyz",
            "tenant_id": "acc_123",
            "selected_property_ids": ["prop_1"],
            "selected_properties": [],
        }

        mock_tool_context = MagicMock()
        mock_tool_context.state = {
            "account_id": "acc_123",
            "ga_credentials": ga_creds,
        }

        dispatch_to_google_analytics("Get sessions", tool_context=mock_tool_context)

        kwargs = mock_invoke.call_args[1]
        assert kwargs["state"] == {"ga_credentials": ga_creds}

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_passes_none_state_when_no_credentials(self, mock_invoke):
        """Should pass state=None when no ga_credentials in tool_context."""
        mock_invoke.return_value = "Limited response"

        mock_tool_context = MagicMock()
        mock_tool_context.state = {"account_id": "acc_123"}

        dispatch_to_google_analytics("Get sessions", tool_context=mock_tool_context)

        kwargs = mock_invoke.call_args[1]
        assert kwargs["state"] is None

    @patch("agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_passes_none_state_when_no_tool_context(self, mock_invoke):
        """Should pass state=None when no tool_context at all."""
        mock_invoke.return_value = "Response"

        dispatch_to_google_analytics("Get sessions")

        kwargs = mock_invoke.call_args[1]
        assert kwargs["state"] is None
