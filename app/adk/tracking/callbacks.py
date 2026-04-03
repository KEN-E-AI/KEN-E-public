"""ADK callbacks for usage tracking and Weave trace hierarchy.

Provides:
- adk_after_tool_callback: Records tool execution events via UsageTracker.
- weave_before_agent_callback / weave_after_agent_callback: Creates a parent
  Weave span wrapping the entire agent invocation so that auto-instrumented
  LLM calls and tool dispatches nest under one root trace.

Usage:
    from google.adk.agents import Agent
    from app.adk.tracking.callbacks import (
        adk_after_tool_callback,
        weave_before_agent_callback,
        weave_after_agent_callback,
    )

    agent = Agent(
        ...,
        before_agent_callback=weave_before_agent_callback,
        after_tool_callback=adk_after_tool_callback,
        after_agent_callback=weave_after_agent_callback,
    )
"""

from __future__ import annotations

import contextvars
import json
import time
from typing import TYPE_CHECKING, Any

from app.utils.weave_observability import init_weave_if_needed

try:
    from weave.trace.api import get_client as _weave_get_client
    from weave.trace.context import call_context as _weave_call_context

    _WEAVE_TRACE_AVAILABLE = True
except ImportError:
    _WEAVE_TRACE_AVAILABLE = False
    _weave_get_client = None  # type: ignore[assignment]
    _weave_call_context = None  # type: ignore[assignment]
from shared.structured_logging import get_structured_logger

from .usage import ExecutionStatus, get_usage_tracker

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types

logger = get_structured_logger(__name__)

# ---------------------------------------------------------------------------
# Weave agent-level span callbacks
# ---------------------------------------------------------------------------

_current_agent_call: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "_current_agent_call", default=None
)


def weave_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Create a parent Weave span for the entire agent invocation.

    Pushes a call onto the Weave call stack so that subsequent
    auto-instrumented LLM calls and @weave.op() tool dispatches
    become children of this span.

    Returns None so the agent proceeds normally.
    """
    if not _WEAVE_TRACE_AVAILABLE:
        return None
    try:
        # On Agent Engine, module-level weave.init() from ken_e_agent.py
        # doesn't re-execute after deserialization. This is the earliest
        # runtime hook — initialize Weave here so the parent span wraps
        # the LLM routing call and all tool dispatches.
        init_weave_if_needed()

        client = _weave_get_client()
        if not client:
            return None
        call = client.create_call(
            op="ken_e_agent",
            inputs={"agent": "ken_e"},
            use_stack=True,
        )
        _current_agent_call.set(call)
    except Exception:
        logger.warning("Failed to create Weave parent span", exc_info=True)
    return None


def weave_after_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Finish the parent Weave span created by weave_before_agent_callback.

    Finalises the call, pops it from the Weave call stack, and clears
    the ContextVar.

    Returns None so the agent proceeds normally.
    """
    call = _current_agent_call.get(None)
    if not call or not _WEAVE_TRACE_AVAILABLE:
        return None
    try:
        client = _weave_get_client()
        if client:
            client.finish_call(call, output={"status": "completed"})
        _weave_call_context.pop_call(call.id)
    except Exception:
        logger.warning("Failed to finish Weave parent span", exc_info=True)
        try:
            _weave_call_context.pop_call(call.id)
        except Exception:
            pass
    finally:
        _current_agent_call.set(None)
    return None


_MAX_OUTPUT_BYTES = 100 * 1024  # 100KB


def truncate_large_output(
    output: Any, max_bytes: int = _MAX_OUTPUT_BYTES
) -> Any:
    """Truncate tool output if it exceeds max_bytes.

    Returns the original output if within limits, or a truncation marker dict
    if the serialized output exceeds max_bytes.

    Args:
        output: Tool response to check
        max_bytes: Maximum size in bytes before truncation

    Returns:
        Original output or {_truncated: True, size_bytes: N, preview: "..."}
    """
    try:
        serialized = json.dumps(output) if isinstance(output, dict) else str(output)
        size = len(serialized.encode("utf-8"))
        if size <= max_bytes:
            return output
        return {
            "_truncated": True,
            "size_bytes": size,
            "preview": serialized[:500],
        }
    except Exception:
        return output


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

        # Truncate large outputs for trace storage (preserves signal, protects Weave)
        traced_output = truncate_large_output(tool_response)

        tracker = get_usage_tracker()
        await tracker.track_execution(
            tool_name=tool.name,
            user_id=user_id,
            account_id=account_id,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            metadata={
                "args_keys": list(args.keys()),
                "output": traced_output,
            },
        )
        # Flush immediately so events persist even in short-lived processes
        await tracker.flush()
    except Exception as e:
        logger.warning(f"Usage tracking failed (non-blocking): {e}")

    return None
