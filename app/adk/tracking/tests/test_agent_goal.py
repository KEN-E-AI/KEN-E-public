"""Tests for context_agent_goal propagation to Weave spans."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

_MOCK_CONFIG_METADATA = {
    "version": "v1.0.0",
    "experiment_id": "baseline",
    "variant_name": "baseline",
    "model": "gemini-2.5-pro",
}

_CONFIG_METADATA_PATH = "app.adk.tracking.callbacks._get_chatbot_config_metadata"


class TestWeaveBeforeAgentCallbackGoal:
    """Test that weave_before_agent_callback sets context_agent_goal."""

    def _make_callback_context(
        self, user_text: str = "What is Apple's stock price?"
    ) -> MagicMock:
        ctx = MagicMock()
        part = MagicMock()
        part.text = user_text
        content = MagicMock()
        content.parts = [part]
        ctx.user_content = content
        return ctx

    @pytest.mark.asyncio
    @patch(_CONFIG_METADATA_PATH, return_value=_MOCK_CONFIG_METADATA)
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    async def test_agent_goal_set_from_user_content(
        self,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_cfg: MagicMock,
    ) -> None:
        from app.adk.tracking.callbacks import weave_before_agent_callback

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_client.create_call.return_value = mock_call
        mock_get_client.return_value = mock_client

        ctx = self._make_callback_context("Tell me about Tesla earnings")
        result = await weave_before_agent_callback(ctx)

        assert result is None
        call_kwargs = mock_client.create_call.call_args
        inputs = (
            call_kwargs[1]["inputs"]
            if "inputs" in call_kwargs[1]
            else call_kwargs[0][1]
        )
        assert inputs.get("context_agent_goal") == "Tell me about Tesla earnings"

    @pytest.mark.asyncio
    @patch(_CONFIG_METADATA_PATH, return_value=_MOCK_CONFIG_METADATA)
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    async def test_agent_goal_none_when_no_user_content(
        self,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_cfg: MagicMock,
    ) -> None:
        from app.adk.tracking.callbacks import weave_before_agent_callback

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_client.create_call.return_value = mock_call
        mock_get_client.return_value = mock_client

        ctx = MagicMock()
        ctx.user_content = None
        result = await weave_before_agent_callback(ctx)

        assert result is None
        call_kwargs = mock_client.create_call.call_args
        inputs = (
            call_kwargs[1]["inputs"]
            if "inputs" in call_kwargs[1]
            else call_kwargs[0][1]
        )
        assert inputs.get("context_agent_goal") is None

    @pytest.mark.asyncio
    @patch(_CONFIG_METADATA_PATH, return_value=_MOCK_CONFIG_METADATA)
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    async def test_agent_goal_truncated_for_long_queries(
        self,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_cfg: MagicMock,
    ) -> None:
        from app.adk.tracking.callbacks import weave_before_agent_callback

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_client.create_call.return_value = mock_call
        mock_get_client.return_value = mock_client

        long_query = "x" * 1000
        ctx = self._make_callback_context(long_query)
        result = await weave_before_agent_callback(ctx)

        assert result is None
        call_kwargs = mock_client.create_call.call_args
        inputs = (
            call_kwargs[1]["inputs"]
            if "inputs" in call_kwargs[1]
            else call_kwargs[0][1]
        )
        goal = inputs.get("context_agent_goal")
        assert goal is not None
        assert len(goal) <= 500


class TestAgentGoalContextPropagation:
    """Test that agent-level weave.attributes context propagates to tool spans."""

    @pytest.mark.asyncio
    @patch(_CONFIG_METADATA_PATH, return_value=_MOCK_CONFIG_METADATA)
    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    @patch("app.adk.tracking.callbacks.init_weave_if_needed")
    @patch("app.adk.tracking.callbacks.weave")
    async def test_before_callback_enters_attributes_context(
        self,
        mock_weave: MagicMock,
        mock_init: MagicMock,
        mock_get_client: MagicMock,
        mock_call_ctx: MagicMock,
        mock_cfg: MagicMock,
    ) -> None:
        from app.adk.tracking.callbacks import weave_before_agent_callback

        mock_client = MagicMock()
        mock_call = MagicMock()
        mock_client.create_call.return_value = mock_call
        mock_get_client.return_value = mock_client

        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        ctx = MagicMock()
        part = MagicMock()
        part.text = "Show me site traffic"
        content = MagicMock()
        content.parts = [part]
        ctx.user_content = content

        await weave_before_agent_callback(ctx)

        # The before-callback now enters weave.attributes() with the full L1
        # root metadata block plus context_agent_goal. Assert the goal is
        # present along with the required L1 spec fields.
        mock_weave.attributes.assert_called_once()
        attrs_passed = mock_weave.attributes.call_args[0][0]
        assert attrs_passed["context_agent_goal"] == "Show me site traffic"
        assert attrs_passed["agent_id"] == "ken_e_chatbot"
        assert "agent_version" in attrs_passed
        assert "experiment_id" in attrs_passed
        assert "variant_name" in attrs_passed
        assert "environment" in attrs_passed
        assert "rollout_percentage" in attrs_passed
        mock_attrs_ctx.__enter__.assert_called_once()

    @patch("app.adk.tracking.callbacks._weave_call_context")
    @patch("app.adk.tracking.callbacks._weave_get_client")
    def test_after_callback_exits_attributes_context(
        self, mock_get_client: MagicMock, mock_call_ctx: MagicMock
    ) -> None:
        from app.adk.tracking.callbacks import (
            _weave_agent_span_stack,
            weave_after_agent_callback,
        )

        mock_call = MagicMock(id="call-goal-test")
        mock_goal_ctx = MagicMock()
        # The attrs context manager is carried on the agent's stack frame and
        # exited when the matching after callback pops it.
        _weave_agent_span_stack.set([(mock_call, mock_goal_ctx)])
        mock_get_client.return_value = MagicMock()

        ctx = MagicMock()
        try:
            weave_after_agent_callback(ctx)

            mock_goal_ctx.__exit__.assert_called_once_with(None, None, None)
            assert (_weave_agent_span_stack.get() or []) == []
        finally:
            _weave_agent_span_stack.set(None)
