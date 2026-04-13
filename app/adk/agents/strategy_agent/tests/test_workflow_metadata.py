"""Tests for workflow metadata on strategy generation root span."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestWorkflowMetadataOnRootSpan:
    """Test workflow_id and workflow_type on the strategy root span.

    The execute_strategy_generation wrapper enters a weave.attributes() context
    with workflow_id (execution_id) and workflow_type before calling
    _execute_strategy_generation_impl. This causes the @weave.op span for
    _execute_strategy_generation_impl to be created with these attributes.
    """

    @patch("app.adk.agents.strategy_agent.orchestrator._execute_strategy_generation_impl")
    @patch("app.adk.agents.strategy_agent.orchestrator.weave")
    def test_wrapper_enters_weave_attributes_with_workflow_metadata(
        self,
        mock_weave: MagicMock,
        mock_impl: MagicMock,
    ) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            execute_strategy_generation,
        )

        mock_impl.return_value = "ok"
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        execute_strategy_generation(
            company_name="TestCo",
            industry="Tech",
            websites="https://test.co",
            customer_regions="US",
            account_id="acc_test",
            user_id="user_1",
            dry_run=True,
        )

        # Verify weave.attributes was called with the workflow metadata
        mock_weave.attributes.assert_called_once()
        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert attrs_dict["workflow_type"] == "strategy_generation"
        assert "workflow_id" in attrs_dict
        assert len(attrs_dict["workflow_id"]) == 12  # 12-char hex

        # Verify the impl was called inside the context
        mock_attrs_ctx.__enter__.assert_called_once()
        mock_impl.assert_called_once()

    @patch("app.adk.agents.strategy_agent.orchestrator._execute_strategy_generation_impl")
    @patch("app.adk.agents.strategy_agent.orchestrator.weave")
    def test_wrapper_passes_execution_id_to_impl(
        self,
        mock_weave: MagicMock,
        mock_impl: MagicMock,
    ) -> None:
        """workflow_id and execution_id passed to impl must match."""
        from app.adk.agents.strategy_agent.orchestrator import (
            execute_strategy_generation,
        )

        mock_impl.return_value = "ok"
        mock_weave.attributes.return_value = MagicMock()

        execute_strategy_generation(
            company_name="TestCo",
            industry="Tech",
            websites="https://test.co",
            customer_regions="US",
            account_id="acc_test",
            user_id="user_1",
            dry_run=True,
        )

        attrs_dict = mock_weave.attributes.call_args[0][0]
        impl_kwargs = mock_impl.call_args[1]
        assert attrs_dict["workflow_id"] == impl_kwargs["execution_id"]

    @patch("app.adk.agents.strategy_agent.orchestrator._execute_strategy_generation_body")
    @patch("app.adk.agents.strategy_agent.config_loader.get_current_config_metadata")
    @patch("app.adk.agents.strategy_agent.orchestrator.weave")
    def test_direct_uses_passed_execution_id_in_session_id(
        self,
        mock_weave: MagicMock,
        mock_get_meta: MagicMock,
        mock_body: MagicMock,
    ) -> None:
        """When execution_id is passed to _direct, it's used in session_id."""
        from app.adk.agents.strategy_agent.models import StrategyContext
        from app.adk.agents.strategy_agent.orchestrator import (
            execute_strategy_generation_direct,
        )

        mock_get_meta.return_value = {}
        mock_body.return_value = {}
        mock_weave.attributes.return_value = MagicMock()

        context = StrategyContext(
            account_id="acc_test",
            company_name="TestCo",
            industry="Tech",
            user_id="user_1",
        )

        execute_strategy_generation_direct(
            context=context,
            firestore_client=MagicMock(),
            analytics_service=None,
            performance_profiler=None,
            alert_manager=None,
            enabled_strategies=[],
            override_product_categories=None,
            dry_run=True,
            execution_id="abc123def456",
        )

        # Find the root_attrs call (has account_id)
        root_call = None
        for call in mock_weave.attributes.call_args_list:
            attrs = call[0][0] if call[0] else {}
            if isinstance(attrs, dict) and "account_id" in attrs:
                root_call = attrs
                break

        assert root_call is not None
        assert root_call["session_id"] == "strategy_acc_test_abc123def456"
