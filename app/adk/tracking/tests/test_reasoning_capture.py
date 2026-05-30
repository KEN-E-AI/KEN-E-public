"""Tests for LLM reasoning capture via after_model_callback."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class MockState(dict):
    """Dict-like state that supports both get() and __setitem__."""

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class MockCallbackContext:
    def __init__(self, state: dict | None = None) -> None:
        self.state = MockState(state or {})


class MockLlmResponse:
    def __init__(self, parts: list | None = None) -> None:
        if parts is not None:
            self.content = MagicMock()
            self.content.parts = parts
        else:
            self.content = None


def _make_text_part(text: str, thought: bool = False) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.thought = thought
    part.function_call = None
    return part


def _make_function_call_part() -> MagicMock:
    part = MagicMock()
    part.text = None
    part.thought = False
    part.function_call = MagicMock(name="search_company_news")
    return part


class TestAfterModelCallback:
    """Test adk_after_model_callback extracts reasoning from LlmResponse.

    AH-89: the callback no longer strips thought=True parts from the response.
    It only captures reasoning into state["_last_reasoning"] for Weave tool
    spans and always returns None.
    """

    @pytest.mark.asyncio
    async def test_extracts_thought_reasoning(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        thought = _make_text_part(
            "I'll search for Apple news to answer your question.", thought=True
        )
        func_call = _make_function_call_part()
        response = MockLlmResponse([thought, func_call])

        result = await adk_after_model_callback(ctx, response)

        # AH-89: always returns None — never mutates the response
        assert result is None
        assert (
            ctx.state["_last_reasoning"]
            == "I'll search for Apple news to answer your question."
        )

    @pytest.mark.asyncio
    async def test_prefers_thought_parts_over_regular_text(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(
            [
                _make_text_part("Thinking about which tool to use...", thought=True),
                _make_text_part("Here's what I found:"),
                _make_function_call_part(),
            ]
        )

        result = await adk_after_model_callback(ctx, response)

        # AH-89: always returns None
        assert result is None
        assert ctx.state["_last_reasoning"] == "Thinking about which tool to use..."

    @pytest.mark.asyncio
    async def test_falls_back_to_regular_text_when_no_thoughts(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(
            [
                _make_text_part("I'll search for Apple news."),
                _make_function_call_part(),
            ]
        )

        result = await adk_after_model_callback(ctx, response)

        assert result is None
        assert ctx.state["_last_reasoning"] == "I'll search for Apple news."

    @pytest.mark.asyncio
    async def test_joins_multiple_thought_parts(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(
            [
                _make_text_part("Let me check the analytics data.", thought=True),
                _make_text_part("I'll use the GA report tool.", thought=True),
                _make_function_call_part(),
            ]
        )

        result = await adk_after_model_callback(ctx, response)

        # AH-89: always returns None
        assert result is None
        assert ctx.state["_last_reasoning"] == (
            "Let me check the analytics data.\nI'll use the GA report tool."
        )

    @pytest.mark.asyncio
    async def test_handles_no_content(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(parts=None)

        result = await adk_after_model_callback(ctx, response)

        assert result is None
        assert "_last_reasoning" not in ctx.state

    @pytest.mark.asyncio
    async def test_handles_no_text_parts(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse([_make_function_call_part()])

        result = await adk_after_model_callback(ctx, response)

        assert result is None
        assert "_last_reasoning" not in ctx.state

    @pytest.mark.asyncio
    async def test_handles_empty_parts_list(self) -> None:
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse([])

        result = await adk_after_model_callback(ctx, response)

        assert result is None
        assert "_last_reasoning" not in ctx.state

    @pytest.mark.asyncio
    async def test_truncates_long_reasoning(self) -> None:
        from app.adk.tracking.callbacks import (
            _MAX_REASONING_LENGTH,
            adk_after_model_callback,
        )

        ctx = MockCallbackContext()
        response = MockLlmResponse([_make_text_part("x" * 5000, thought=True)])

        await adk_after_model_callback(ctx, response)

        assert len(ctx.state["_last_reasoning"]) <= _MAX_REASONING_LENGTH

    @pytest.mark.asyncio
    async def test_thought_parts_survive_in_response(self) -> None:
        """AH-89: thought parts must NOT be stripped — the streaming router needs them."""
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        thought = _make_text_part("reasoning about tool choice", thought=True)
        func_call = _make_function_call_part()
        response = MockLlmResponse([thought, func_call])

        result = await adk_after_model_callback(ctx, response)

        # AH-89: callback returns None and leaves response untouched
        assert result is None
        assert thought in response.content.parts
        assert func_call in response.content.parts

    @pytest.mark.asyncio
    async def test_returns_none_always(self) -> None:
        """AH-89: callback never mutates the response — always returns None."""
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(
            [_make_text_part("regular text"), _make_function_call_part()]
        )

        result = await adk_after_model_callback(ctx, response)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_thought_parts_present(self) -> None:
        """AH-89: even with thought parts, callback returns None (no mutation)."""
        from app.adk.tracking.callbacks import adk_after_model_callback

        ctx = MockCallbackContext()
        response = MockLlmResponse(
            [
                _make_text_part("thinking...", thought=True),
                _make_function_call_part(),
            ]
        )

        result = await adk_after_model_callback(ctx, response)

        assert result is None


class TestReasoningInBeforeToolCallback:
    """Test that before_tool_callback reads _last_reasoning and sets context_reasoning."""

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_reads_reasoning_and_sets_attribute(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MagicMock()
        tool.name = "search_company_news"

        ctx = MagicMock()
        ctx.state = MockState(
            {
                "_last_reasoning": "I need to search for Apple news.",
            }
        )
        ctx.user_content = None

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert attrs_dict["context_reasoning"] == "I need to search for Apple news."

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_clears_reasoning_after_read(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MagicMock()
        tool.name = "search_company_news"

        ctx = MagicMock()
        ctx.state = MockState(
            {
                "_last_reasoning": "Some reasoning text.",
            }
        )
        ctx.user_content = None

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        assert ctx.state.get("_last_reasoning") is None

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_no_reasoning_key_when_not_present(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        mock_attrs_ctx = MagicMock()
        mock_weave.attributes.return_value = mock_attrs_ctx

        tool = MagicMock()
        tool.name = "search_company_news"

        ctx = MagicMock()
        ctx.state = MockState({})
        ctx.user_content = None

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        attrs_dict = mock_weave.attributes.call_args[0][0]
        assert "context_reasoning" not in attrs_dict
