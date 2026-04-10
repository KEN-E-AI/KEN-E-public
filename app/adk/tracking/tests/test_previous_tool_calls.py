"""Tests for previous_tool_calls tracking on tool call spans."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adk.tracking.callbacks import adk_after_tool_callback


class MockState(dict):
    """Dict-like state that supports both get() and __setitem__."""

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class MockBaseTool:
    def __init__(self, name: str = "test_tool") -> None:
        self.name = name


class MockToolContext:
    def __init__(self, state: dict | None = None) -> None:
        self.state = MockState(state or {})
        part = MagicMock()
        part.text = "test query"
        content = MagicMock()
        content.parts = [part]
        self.user_content = content


class TestPreviousToolCallsTracking:
    """Test that previous_tool_calls accumulates in state across tool calls."""

    @pytest.mark.asyncio
    async def test_first_tool_call_appends_to_empty_list(self) -> None:
        tool = MockBaseTool("search_company_news")
        ctx = MockToolContext({"user_id": "u1", "account_id": "a1"})

        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker"
        ) as mock_tracker_fn:
            mock_tracker = AsyncMock()
            mock_tracker_fn.return_value = mock_tracker

            await adk_after_tool_callback(tool, {"q": "test"}, ctx, {"status": "ok"})

        assert ctx.state["_previous_tool_calls"] == ["search_company_news"]

    @pytest.mark.asyncio
    async def test_second_tool_call_appends_to_existing_list(self) -> None:
        tool = MockBaseTool("query_google_analytics")
        ctx = MockToolContext({
            "user_id": "u1",
            "account_id": "a1",
            "_previous_tool_calls": ["search_company_news"],
        })

        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker"
        ) as mock_tracker_fn:
            mock_tracker = AsyncMock()
            mock_tracker_fn.return_value = mock_tracker

            await adk_after_tool_callback(tool, {"q": "test"}, ctx, {"status": "ok"})

        assert ctx.state["_previous_tool_calls"] == [
            "search_company_news",
            "query_google_analytics",
        ]

    @pytest.mark.asyncio
    async def test_third_tool_call_preserves_full_history(self) -> None:
        tool = MockBaseTool("dispatch_to_strategy")
        ctx = MockToolContext({
            "user_id": "u1",
            "account_id": "a1",
            "_previous_tool_calls": ["search_company_news", "query_google_analytics"],
        })

        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker"
        ) as mock_tracker_fn:
            mock_tracker = AsyncMock()
            mock_tracker_fn.return_value = mock_tracker

            await adk_after_tool_callback(tool, {"q": "test"}, ctx, {"status": "ok"})

        assert ctx.state["_previous_tool_calls"] == [
            "search_company_news",
            "query_google_analytics",
            "dispatch_to_strategy",
        ]


class TestPreviousToolCallsWeaveAttribute:
    """Test that before_tool_callback sets context_previous_tool_calls as weave attribute."""

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_before_tool_sets_previous_calls_attribute(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MockBaseTool("query_google_analytics")
        ctx = MockToolContext({
            "_previous_tool_calls": ["search_company_news"],
        })

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        mock_weave.attributes.assert_called_once()
        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert attrs_dict["context_previous_tool_calls"] == ["search_company_news"]

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_first_tool_call_gets_empty_list(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MockBaseTool("search_company_news")
        ctx = MockToolContext({})

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        mock_weave.attributes.assert_called_once()
        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert attrs_dict["context_previous_tool_calls"] == []
