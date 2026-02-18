"""ADK after_tool_callback for usage tracking.

Records tool execution events after tool completion using the UsageTracker.
Integrates with ADK's callback system to capture execution metrics.

Usage:
    from google.adk.agents import Agent
    from app.adk.tracking.callbacks import adk_after_tool_callback

    agent = Agent(
        ...,
        after_tool_callback=adk_after_tool_callback,
    )
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from shared.structured_logging import get_structured_logger

from .usage import ExecutionStatus, get_usage_tracker

if TYPE_CHECKING:
    from google.adk.tools import BaseTool, ToolContext

logger = get_structured_logger(__name__)


def _determine_status(tool_response: dict[str, Any] | str | Any) -> ExecutionStatus:
    """Determine execution status from the tool response.

    Args:
        tool_response: The response from the tool (dict, string, or other)

    Returns:
        Appropriate ExecutionStatus based on response content
    """
    if not isinstance(tool_response, dict):
        return ExecutionStatus.SUCCESS
    error = tool_response.get("error", "")
    if error == "permission_denied":
        return ExecutionStatus.PERMISSION_DENIED
    if error == "authentication_required":
        return ExecutionStatus.PERMISSION_DENIED
    if error == "rate_limited":
        return ExecutionStatus.RATE_LIMITED
    if error == "timeout":
        return ExecutionStatus.TIMEOUT
    if error:
        return ExecutionStatus.FAILURE
    return ExecutionStatus.SUCCESS


async def adk_after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
    """ADK-compatible after_tool_callback for usage tracking.

    Records tool execution events after completion. Never blocks or
    modifies the tool response — always returns None.

    Args:
        tool: ADK BaseTool that was executed
        args: Tool arguments that were passed
        tool_context: ADK ToolContext with session state
        tool_response: Response dict from the tool execution

    Returns:
        None (never overrides the tool response)
    """
    try:
        state: dict[str, Any] = {}
        if hasattr(tool_context, "state") and hasattr(tool_context.state, "get"):
            state = tool_context.state  # type: ignore[assignment]

        user_id = state.get("user_id", "unknown")
        account_id = state.get("account_id", "unknown")

        status = _determine_status(tool_response)

        duration_ms: int | None = None
        start_time = state.get("_tool_start_time")
        if start_time is not None:
            duration_ms = int((time.monotonic() - start_time) * 1000)

        error_message: str | None = None
        if status != ExecutionStatus.SUCCESS and isinstance(tool_response, dict):
            error_message = tool_response.get("message") or tool_response.get("error")

        tracker = get_usage_tracker()
        await tracker.track_execution(
            tool_name=tool.name,
            user_id=user_id,
            account_id=account_id,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            metadata={"args_keys": list(args.keys())},
        )
        # Flush immediately so events persist even in short-lived processes
        await tracker.flush()
    except Exception as e:
        logger.warning(f"Usage tracking failed (non-blocking): {e}")

    return None
