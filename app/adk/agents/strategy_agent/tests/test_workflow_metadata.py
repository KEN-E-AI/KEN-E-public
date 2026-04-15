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

        mock_weave.attributes.assert_called_once()
        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert attrs_dict["workflow_type"] == "strategy_generation"
        assert "workflow_id" in attrs_dict
        assert len(attrs_dict["workflow_id"]) == 12  # 12-char hex

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

    @patch("app.adk.agents.strategy_agent.orchestrator._execute_strategy_generation_impl")
    @patch("app.adk.agents.strategy_agent.orchestrator.weave")
    def test_wrapper_builds_session_id_from_same_execution_id_as_workflow_id(
        self,
        mock_weave: MagicMock,
        mock_impl: MagicMock,
    ) -> None:
        """session_id and workflow_id must share the same execution_id suffix.

        Rationale: the strategy trace has both a workflow_id (for MER-E
        workflow evaluation) and a session_id (for root span identity). Both
        are derived from the same `execution_id` generated in the wrapper,
        so any correlation across trace stores works. This test guards
        against a regression where the wrapper accidentally generates two
        different execution_ids (e.g., one for workflow, one passed through
        to impl) and the session_id would then lose its link to workflow_id.

        After the Feature 1.1.2 rebase on top of Feature 1.13, ALL root
        metadata (including account_id/session_id/agent_id/etc.) lives in
        the wrapper's weave.attributes() dict — _direct no longer builds
        session_id. The wrapper's single execution_id threads through both
        the workflow_id field AND the session_id f-string.
        """
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
        # Required: both fields present
        assert "workflow_id" in attrs_dict
        assert "session_id" in attrs_dict
        # Invariant: session_id must contain the same execution_id as workflow_id
        workflow_id = attrs_dict["workflow_id"]
        assert attrs_dict["session_id"] == f"strategy_acc_test_{workflow_id}"

    @patch("app.adk.agents.strategy_agent.orchestrator._execute_strategy_generation_impl")
    @patch("app.adk.agents.strategy_agent.orchestrator.weave")
    def test_wrapper_populates_full_root_metadata_block(
        self,
        mock_weave: MagicMock,
        mock_impl: MagicMock,
    ) -> None:
        """Per docs/trace-structure-spec.md §4.1, the strategy root span must
        carry the full metadata block (not just workflow fields).

        Feature 1.1.2 Decision A1 hardcodes the strategy_orchestrator identity
        since the orchestrator is not a tunable LLM agent.
        """
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

        attrs = mock_weave.attributes.call_args[0][0]
        # Workflow (Feature 1.13)
        assert attrs["workflow_type"] == "strategy_generation"
        assert "workflow_id" in attrs
        # Root session identity (Feature 1.1.2 Story 1.1.2-2)
        assert attrs["account_id"] == "acc_test"
        assert attrs["user_id"] == "user_1"
        assert "session_id" in attrs
        assert "environment" in attrs
        assert "rollout_percentage" in attrs
        # Strategy orchestrator identity (Decision A1)
        assert attrs["agent_id"] == "strategy_orchestrator"
        assert attrs["agent_version"] == "v1.0.0"
        assert attrs["experiment_id"] == "baseline"
        assert attrs["variant_name"] == "baseline"


class TestStepMetadataHelper:
    """Test the _get_strategy_step_metadata helper that returns step_type,
    step_index, and depends_on_steps for each strategy name.

    This helper is used at _execute_single_strategy call sites to build the
    weave.attributes() wrapper around each strategy execution. MER-E reads
    these attributes from each execute_single_strategy span to perform
    workflow step-level evaluation.
    """

    def test_business_strategy_is_research_step_zero(self) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        meta = _get_strategy_step_metadata("business_strategy")
        assert meta == {
            "step_type": "research",
            "step_index": 0,
            "depends_on_steps": [],
        }

    def test_competitive_strategy_is_analysis_step_one_no_deps(self) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        meta = _get_strategy_step_metadata("competitive_strategy")
        assert meta == {
            "step_type": "analysis",
            "step_index": 1,
            "depends_on_steps": [],
        }

    def test_marketing_strategy_is_generation_step_one_depends_on_business(
        self,
    ) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        meta = _get_strategy_step_metadata("marketing_strategy")
        assert meta == {
            "step_type": "generation",
            "step_index": 1,
            "depends_on_steps": ["business_strategy"],
        }

    def test_brand_guidelines_is_generation_step_one_no_deps(self) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        meta = _get_strategy_step_metadata("brand_guidelines")
        assert meta == {
            "step_type": "generation",
            "step_index": 1,
            "depends_on_steps": [],
        }

    def test_unknown_strategy_raises(self) -> None:
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        import pytest

        with pytest.raises(KeyError):
            _get_strategy_step_metadata("nonexistent_strategy")

    def test_parallel_strategies_share_step_index(self) -> None:
        """AC-4: parallel sub-agents share step_index."""
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        competitive = _get_strategy_step_metadata("competitive_strategy")
        marketing = _get_strategy_step_metadata("marketing_strategy")
        brand = _get_strategy_step_metadata("brand_guidelines")

        assert competitive["step_index"] == 1
        assert marketing["step_index"] == 1
        assert brand["step_index"] == 1

    def test_parallel_strategies_have_varied_step_types(self) -> None:
        """AC-4: parallel sub-agents can have different step_types."""
        from app.adk.agents.strategy_agent.orchestrator import (
            _get_strategy_step_metadata,
        )

        step_types = {
            _get_strategy_step_metadata(name)["step_type"]
            for name in ["competitive_strategy", "marketing_strategy", "brand_guidelines"]
        }
        # Parallel strategies have at least 2 distinct step_types (analysis + generation)
        assert len(step_types) >= 2
        assert "analysis" in step_types
        assert "generation" in step_types
