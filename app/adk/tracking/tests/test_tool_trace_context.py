"""Tests for the off-state Weave tool-trace context stash (AgentTool fix).

Regression context: the per-tool ``weave.attributes(...)`` context manager is
generator-backed. It used to be parked in ADK session ``state``; when an
``AgentTool`` (agent-as-tool, e.g. ``agent.google_search``) ran, ADK deep-copied
the parent session state into the child session and ``copy.deepcopy`` of a
generator raised ``TypeError: cannot pickle 'generator' object`` — so every
agent-as-tool call failed. The fix holds the CM off-state in
``tool_trace_context`` so it never crosses the AgentTool state copy.
"""

from __future__ import annotations

import contextlib
import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adk.tracking.tool_trace_context import (
    pop_trace_context,
    stash_trace_context,
)


@contextlib.contextmanager
def _generator_cm():
    """A generator-backed context manager, exactly like ``weave.attributes``."""
    yield "attrs"


class MockState(dict):
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


# ---------------------------------------------------------------------------
# Module unit tests
# ---------------------------------------------------------------------------


class TestStashPop:
    def test_round_trip(self) -> None:
        ctx = MockToolContext()
        sentinel = object()
        stash_trace_context(ctx, sentinel)
        assert pop_trace_context(ctx) is sentinel

    def test_pop_is_one_shot(self) -> None:
        ctx = MockToolContext()
        stash_trace_context(ctx, object())
        pop_trace_context(ctx)
        assert pop_trace_context(ctx) is None

    def test_pop_missing_returns_none(self) -> None:
        assert pop_trace_context(MockToolContext()) is None

    def test_two_contexts_are_isolated(self) -> None:
        ctx_a, ctx_b = MockToolContext(), MockToolContext()
        a, b = object(), object()
        stash_trace_context(ctx_a, a)
        stash_trace_context(ctx_b, b)
        assert (pop_trace_context(ctx_a), pop_trace_context(ctx_b)) == (a, b)


# ---------------------------------------------------------------------------
# Regression: the original failure mode + the fix
# ---------------------------------------------------------------------------


class TestDeepCopyRegression:
    def test_generator_cm_in_state_is_the_original_failure(self) -> None:
        """Documents the bug: a generator-backed CM in state breaks deepcopy —
        which is exactly what AgentTool.run_async does to the parent state."""
        cm = _generator_cm()
        cm.__enter__()
        with pytest.raises(TypeError, match="cannot pickle 'generator' object"):
            copy.deepcopy({"_trace_attrs_ctx": cm})
        cm.__exit__(None, None, None)

    @pytest.mark.asyncio
    @patch("app.adk.security.hooks.before_tool_execution_hook")
    @patch("app.adk.security.hooks._refresh_ga_token_if_needed")
    @patch("app.adk.security.hooks.weave")
    async def test_before_tool_keeps_cm_out_of_state(
        self, mock_weave: MagicMock, mock_refresh: MagicMock, mock_hook: MagicMock
    ) -> None:
        """After before-tool runs, the CM is NOT in state (so the AgentTool
        state deep-copy succeeds) and IS retrievable off-state."""
        from app.adk.security.hooks import adk_before_tool_callback

        mock_refresh.return_value = None
        mock_hook.return_value = MagicMock(allowed=True)
        cm = _generator_cm()
        mock_weave.attributes.return_value = cm

        tool = MockBaseTool("query_google_analytics")
        ctx = MockToolContext({"account_id": "a1"})

        await adk_before_tool_callback(tool, {"q": "test"}, ctx)

        # The generator-backed CM must not have leaked into session state.
        assert "_trace_attrs_ctx" not in ctx.state
        # The exact operation AgentTool performs on the parent state must work.
        copy.deepcopy(dict(ctx.state))  # must not raise
        # And the CM is held off-state for the after-tool callback to close.
        assert pop_trace_context(ctx) is cm
        cm.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Lifecycle: after-tool exits and clears the stashed CM
# ---------------------------------------------------------------------------


class TestAfterToolLifecycle:
    @pytest.mark.asyncio
    async def test_after_tool_exits_and_clears_stashed_cm(self) -> None:
        from app.adk.tracking.callbacks import adk_after_tool_callback

        tool = MockBaseTool("query_google_analytics")
        ctx = MockToolContext({"user_id": "u1", "account_id": "a1"})
        cm = MagicMock()
        stash_trace_context(ctx, cm)

        with patch("app.adk.tracking.callbacks.get_usage_tracker") as mock_tracker_fn:
            mock_tracker_fn.return_value = AsyncMock()
            await adk_after_tool_callback(tool, {"q": "x"}, ctx, {"status": "ok"})

        cm.__exit__.assert_called_once_with(None, None, None)
        assert pop_trace_context(ctx) is None

    @pytest.mark.asyncio
    async def test_cross_context_exit_is_swallowed_and_bookkeeping_runs(self) -> None:
        """Guard: a ValueError from weave's ContextVar reset (cross-context exit)
        must be swallowed by the finally block without skipping _previous_tool_calls."""
        from app.adk.tracking.callbacks import adk_after_tool_callback

        cm = MagicMock()
        cm.__exit__.side_effect = ValueError("Token was created in a different Context")

        ctx = MockToolContext(
            {"user_id": "u1", "account_id": "a1", "_previous_tool_calls": ["search_company_news"]}
        )
        stash_trace_context(ctx, cm)

        with patch("app.adk.tracking.callbacks.get_usage_tracker") as mock_tracker_fn:
            mock_tracker_fn.return_value = AsyncMock()
            # Must not raise even though cm.__exit__ raises ValueError
            await adk_after_tool_callback(
                MockBaseTool("query_google_analytics"), {"q": "test"}, ctx, {"status": "ok"}
            )

        cm.__exit__.assert_called_once_with(None, None, None)
        assert ctx.state["_previous_tool_calls"] == ["search_company_news", "query_google_analytics"]
