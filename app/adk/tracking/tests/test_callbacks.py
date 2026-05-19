"""Tests for ADK after_tool_callback usage tracking."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adk.tracking.callbacks import _determine_status, adk_after_tool_callback
from app.adk.tracking.usage import ExecutionStatus


@dataclass
class MockBaseTool:
    """Minimal mock of ADK BaseTool."""

    name: str


@dataclass
class MockState:
    """Mock ADK state with dict-like access."""

    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value


@dataclass
class MockToolContext:
    """Minimal mock of ADK ToolContext."""

    state: MockState = field(default_factory=MockState)


def _make_context(
    user_id: str = "user1",
    account_id: str = "acct1",
    start_time: float | None = None,
) -> MockToolContext:
    ctx = MockToolContext()
    ctx.state["user_id"] = user_id
    ctx.state["account_id"] = account_id
    if start_time is not None:
        ctx.state["_tool_start_time"] = start_time
    return ctx


class TestDetermineStatus:
    """Tests for _determine_status helper."""

    def test_success_on_empty_response(self):
        assert _determine_status({}) == ExecutionStatus.SUCCESS

    def test_success_on_data_response(self):
        assert _determine_status({"data": [1, 2]}) == ExecutionStatus.SUCCESS

    def test_permission_denied(self):
        assert (
            _determine_status({"error": "permission_denied"})
            == ExecutionStatus.PERMISSION_DENIED
        )

    def test_authentication_required(self):
        assert (
            _determine_status({"error": "authentication_required"})
            == ExecutionStatus.PERMISSION_DENIED
        )

    def test_rate_limited(self):
        assert (
            _determine_status({"error": "rate_limited"}) == ExecutionStatus.RATE_LIMITED
        )

    def test_timeout(self):
        assert _determine_status({"error": "timeout"}) == ExecutionStatus.TIMEOUT

    def test_generic_error(self):
        assert (
            _determine_status({"error": "something_went_wrong"})
            == ExecutionStatus.FAILURE
        )

    def test_string_response_treated_as_success(self):
        assert _determine_status("some text response") == ExecutionStatus.SUCCESS

    def test_none_response_treated_as_success(self):
        assert _determine_status(None) == ExecutionStatus.SUCCESS


class TestAdkAfterToolCallback:
    """Tests for adk_after_tool_callback."""

    @pytest.mark.asyncio
    async def test_tracks_successful_execution(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context(start_time=time.monotonic() - 0.1)
        response = {"data": "analytics report"}

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            result = await adk_after_tool_callback(
                tool, {"query": "traffic"}, ctx, response
            )

        assert result is None
        mock_tracker.track_execution.assert_awaited_once()
        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["tool_name"] == "get_ga4_report"
        assert call_kwargs["user_id"] == "user1"
        assert call_kwargs["account_id"] == "acct1"
        assert call_kwargs["status"] == ExecutionStatus.SUCCESS
        assert call_kwargs["duration_ms"] is not None
        assert call_kwargs["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_tracks_permission_denied(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        response = {"error": "permission_denied", "message": "No token"}

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            await adk_after_tool_callback(tool, {}, ctx, response)

        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["status"] == ExecutionStatus.PERMISSION_DENIED
        assert call_kwargs["error_message"] == "No token"

    @pytest.mark.asyncio
    async def test_tracks_failure(self):
        tool = MockBaseTool(name="search_news")
        ctx = _make_context()
        response = {"error": "api_unavailable", "message": "Service down"}

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            await adk_after_tool_callback(tool, {}, ctx, response)

        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["status"] == ExecutionStatus.FAILURE
        assert call_kwargs["error_message"] == "Service down"

    @pytest.mark.asyncio
    async def test_returns_none_always(self):
        tool = MockBaseTool(name="some_tool")
        ctx = _make_context()

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            result = await adk_after_tool_callback(tool, {}, ctx, {"data": "ok"})

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_tracking_error_gracefully(self):
        tool = MockBaseTool(name="some_tool")
        ctx = _make_context()

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        mock_tracker.track_execution.side_effect = RuntimeError("Firestore down")
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            result = await adk_after_tool_callback(tool, {}, ctx, {"data": "ok"})

        assert result is None

    @pytest.mark.asyncio
    async def test_calculates_duration(self):
        tool = MockBaseTool(name="slow_tool")
        start = time.monotonic() - 0.5  # 500ms ago
        ctx = _make_context(start_time=start)

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            await adk_after_tool_callback(tool, {}, ctx, {})

        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["duration_ms"] is not None
        assert call_kwargs["duration_ms"] >= 400  # At least 400ms

    @pytest.mark.asyncio
    async def test_handles_string_tool_response(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        response = "Here is the analytics report data..."

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            result = await adk_after_tool_callback(
                tool, {"query": "traffic"}, ctx, response
            )

        assert result is None
        mock_tracker.track_execution.assert_awaited_once()
        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["status"] == ExecutionStatus.SUCCESS
        assert call_kwargs["error_message"] is None

    @pytest.mark.asyncio
    async def test_handles_missing_state(self):
        tool = MockBaseTool(name="some_tool")
        ctx = MockToolContext()  # Empty state

        mock_tracker = AsyncMock()
        mock_tracker.flush = AsyncMock()
        with patch(
            "app.adk.tracking.callbacks.get_usage_tracker",
            return_value=mock_tracker,
        ):
            result = await adk_after_tool_callback(tool, {}, ctx, {})

        assert result is None
        call_kwargs = mock_tracker.track_execution.call_args[1]
        assert call_kwargs["user_id"] == "unknown"
        assert call_kwargs["account_id"] == "unknown"
        assert call_kwargs["duration_ms"] is None


class TestTruncateLargeOutput:
    """Tests for output truncation utility."""

    def test_small_output_unchanged(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = {"result": "small data"}
        assert truncate_large_output(output) == output

    def test_large_output_truncated(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = {"data": "x" * 200_000}
        result = truncate_large_output(output)
        assert result["_truncated"] is True
        assert result["size_bytes"] > 100_000
        assert len(result["preview"]) == 500

    def test_exactly_100kb_not_truncated(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        # Create output that serializes to exactly 100KB
        output = {"d": "a" * (100 * 1024 - 10)}
        # Guard: verify our test data is actually at/under the limit
        serialized = json.dumps(output)
        assert len(serialized.encode("utf-8")) <= 100 * 1024
        result = truncate_large_output(output)
        # Should not be truncated (at or under limit)
        assert not isinstance(result, dict) or "_truncated" not in result

    def test_string_output_truncated(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = "x" * 200_000
        result = truncate_large_output(output)
        assert result["_truncated"] is True
        assert result["size_bytes"] > 100_000

    def test_list_output_truncated(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = [{"item": "x" * 200_000}]
        result = truncate_large_output(output)
        assert result["_truncated"] is True
        assert result["size_bytes"] > 100_000

    def test_small_list_output_unchanged(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = [{"a": 1}, {"b": 2}]
        assert truncate_large_output(output) == output

    def test_none_output_unchanged(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        assert truncate_large_output(None) is None

    def test_custom_max_bytes(self) -> None:
        from app.adk.tracking.callbacks import truncate_large_output

        output = {"data": "x" * 1000}
        result = truncate_large_output(output, max_bytes=100)
        assert result["_truncated"] is True
