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
import os
import time
from typing import TYPE_CHECKING, Any

import weave
from weave.trace.api import get_client as _weave_get_client
from weave.trace.context import call_context as _weave_call_context

from app.utils.weave_observability import init_weave_if_needed
from shared.structured_logging import get_structured_logger
from shared.trace_metadata import DEFAULT_VERSION

from .usage import ExecutionStatus, get_usage_tracker

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_response import LlmResponse
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types

logger = get_structured_logger(__name__)

# ---------------------------------------------------------------------------
# Weave agent-level span callbacks
# ---------------------------------------------------------------------------

_current_agent_call: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "_current_agent_call", default=None
)
_current_agent_goal_ctx: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "_current_agent_goal_ctx", default=None
)


_MAX_GOAL_LENGTH = 500


def _get_chatbot_config_metadata() -> dict[str, Any]:
    """Return span-attribute metadata for the ken_e_chatbot config doc.

    Delegates to ``get_cached_config("ken_e_chatbot")`` — the shared TTL
    cache in ``app/adk/agents/utils/config_cache.py`` (Sprint 6 Decision B).
    That helper provides:

    * 60-second TTL with a single Firestore read per window (single-flight
      under concurrent first-turn load via 32-stripe locking).
    * Serve-stale-on-error: a Firestore hiccup with a prior cache hit returns
      the last-good value rather than blocking the agent turn.
    * On first-call failure (no cached value) the helper raises; we catch and
      return ``{}`` so the callback's outer ``try/except`` degrades gracefully.

    The returned dict carries the six keys ``_build_chatbot_root_attrs``
    reads: ``version``, ``experiment_id``, ``variant_name``, ``model``,
    ``temperature``, ``max_output_tokens``.

    Note: config changes propagate to trace metadata on the next TTL boundary
    (~60 s). This matches the existing InstructionProvider contract (Sprint 6
    Decision B) — we are aligning trace metadata with it, not introducing a
    new staleness window.

    Import path handles both deployment layouts:
      - Local dev: ``app.adk.agents.utils.config_cache``
      - Agent Engine runtime (extra_packages flatten to root):
        ``agents.utils.config_cache``
    """
    try:
        try:
            from agents.utils.config_cache import get_cached_config
        except ImportError:
            from app.adk.agents.utils.config_cache import get_cached_config

        config, metadata, _extensions = get_cached_config("ken_e_chatbot")
        gcc = getattr(config, "generate_content_config", None)
        return {
            "version": metadata.get("version"),
            "experiment_id": metadata.get("experiment_id", "baseline"),
            "variant_name": metadata.get("variant_name", "baseline"),
            "model": getattr(config, "model", "unknown"),
            "temperature": getattr(gcc, "temperature", None),
            "max_output_tokens": getattr(gcc, "max_output_tokens", None),
        }
    except Exception as e:
        logger.warning(f"Failed to load ken_e_chatbot config metadata: {e}")
        return {}


def _build_chatbot_root_attrs(callback_context: CallbackContext) -> dict[str, Any]:
    """Build the L1 chatbot agent span attributes from session state + config.

    Per docs/trace-structure-spec.md §4.1-4.2, the root and L1 spans for a
    chatbot trace must carry account_id, session_id, user_id, environment,
    rollout_percentage, agent_id, agent_version, experiment_id, variant_name.

    Sources:
    - session_id, user_id: pulled from callback_context._invocation_context
      (the canonical ADK location). The API doesn't push these into state
      because ADK already owns them at the framework level.
    - account_id: pulled from session state, set by the API in
      routers/chat.py when creating the conversation.
    - agent identity / experiment: from cached Firestore config snapshot.
    """
    state: dict[str, Any] = {}
    try:
        if hasattr(callback_context, "state") and hasattr(
            callback_context.state, "get"
        ):
            state = callback_context.state  # type: ignore[assignment]
    except Exception:
        state = {}

    # Pull session_id/user_id from the ADK invocation context — they live there,
    # not in session state. Fall back to "unknown" if the private attribute
    # ever moves (private API, but trace-only usage so non-critical).
    session_id = "unknown"
    user_id = "unknown"
    try:
        invocation_context = getattr(callback_context, "_invocation_context", None)
        if invocation_context is not None:
            session = getattr(invocation_context, "session", None)
            if session is not None and getattr(session, "id", None):
                session_id = session.id
            inv_user_id = getattr(invocation_context, "user_id", None)
            if inv_user_id:
                user_id = inv_user_id
    except Exception as e:
        logger.debug(f"Could not read session/user from invocation_context: {e}")

    cfg = _get_chatbot_config_metadata()
    attrs: dict[str, Any] = {
        "account_id": state.get("account_id", "unknown"),
        "session_id": session_id,
        "user_id": user_id,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "rollout_percentage": int(os.getenv("ROLLOUT_PERCENTAGE", "100")),
        "agent_id": "ken_e_chatbot",
        "agent_version": cfg.get("version", DEFAULT_VERSION),
        "experiment_id": cfg.get("experiment_id", "baseline"),
        "variant_name": cfg.get("variant_name", "baseline"),
        "model_used": cfg.get("model", "unknown"),
    }
    # Optional generation-config fields — included when the Firestore doc
    # surfaces them, omitted otherwise (the trace-spec marks them
    # ``Required: No`` for L2 sub-agent spans).
    if cfg.get("temperature") is not None:
        attrs["temperature"] = cfg["temperature"]
    if cfg.get("max_output_tokens") is not None:
        attrs["max_output_tokens"] = cfg["max_output_tokens"]
    return attrs


def _extract_user_goal(callback_context: CallbackContext) -> str | None:
    """Extract the user's query text from CallbackContext for agent_goal."""
    try:
        content = callback_context.user_content
        if content and hasattr(content, "parts") and content.parts:
            text = getattr(content.parts[0], "text", None)
            if text:
                return text[:_MAX_GOAL_LENGTH]
    except Exception:
        pass
    return None


async def weave_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Create a parent Weave span for the entire agent invocation.

    Pushes a call onto the Weave call stack so that subsequent
    auto-instrumented LLM calls and @weave.op() tool dispatches
    become children of this span.

    Resolves the agent's system instruction text via
    ``agent.canonical_instruction(callback_context)`` and includes it in the
    span inputs so MER-E can inspect the active prompt at trace time. The
    resolution is wrapped in a defensive try/except so any ADK-internal API
    change degrades gracefully without breaking the agent turn.

    Returns None so the agent proceeds normally.
    """
    try:
        # On Agent Engine, module-level weave.init() from ken_e_agent.py
        # doesn't re-execute after deserialization. This is the earliest
        # runtime hook — initialize Weave here so the parent span wraps
        # the LLM routing call and all tool dispatches.
        init_weave_if_needed()

        client = _weave_get_client()
        if not client:
            return None

        agent_goal = _extract_user_goal(callback_context)

        # Resolve the instruction text for the root span inputs.
        # ``canonical_instruction`` handles both plain-string and
        # InstructionProvider callable variants. Wrapped in try/except so any
        # ADK-internal API change doesn't break the agent turn.
        instruction_text: str | None = None
        try:
            invocation_ctx = getattr(callback_context, "_invocation_context", None)
            if invocation_ctx is not None:
                agent = getattr(invocation_ctx, "agent", None)
                if agent is not None and hasattr(agent, "canonical_instruction"):
                    instr, _ = await agent.canonical_instruction(callback_context)
                    instruction_text = instr
        except Exception:
            pass

        # Build L1 root metadata + agent_goal in a single weave.attributes()
        # context. Entering BEFORE create_call ensures the parent span itself
        # carries the attributes (Weave reads contextvars at call creation
        # time). Exited in weave_after_agent_callback.
        root_attrs = _build_chatbot_root_attrs(callback_context)
        if agent_goal:
            root_attrs["context_agent_goal"] = agent_goal

        attrs_ctx = weave.attributes(root_attrs)
        attrs_ctx.__enter__()
        _current_agent_goal_ctx.set(attrs_ctx)

        # ``weave.attributes(...)`` propagates to ``@weave.op()`` child spans
        # via contextvar, but ``client.create_call(...)`` does not snapshot
        # that contextvar onto the call it creates — we have to pass
        # ``attributes=`` explicitly or the parent root span ships without
        # ``account_id``, ``session_id``, ``agent_id``, ``agent_version``
        # set, which fails ``validate_trace_compliance``.
        inputs: dict[str, Any] = {
            "agent": "ken_e",
            "context_agent_goal": agent_goal,
        }
        if instruction_text is not None:
            inputs["instruction"] = truncate_large_output(instruction_text)

        call = client.create_call(
            op="ken_e_agent",
            inputs=inputs,
            attributes=root_attrs,
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

    Reads ``state["_last_model_output"]`` — stashed by
    ``capture_last_model_output_after_model_callback`` on the final model call —
    and surfaces it as ``output["text"]`` on the finished span so MER-E can
    inspect the agent's response text at trace time.

    Returns None so the agent proceeds normally.
    """
    call = _current_agent_call.get(None)
    if not call:
        return None
    try:
        # Read last model output text stashed by the after_model callback.
        last_text: str | None = None
        try:
            if hasattr(callback_context, "state") and hasattr(
                callback_context.state, "get"
            ):
                last_text = callback_context.state.get("_last_model_output")
        except Exception:
            pass

        output: dict[str, Any] = {"status": "completed"}
        if last_text:
            output["text"] = last_text

        client = _weave_get_client()
        if client:
            client.finish_call(call, output=output)
        _weave_call_context.pop_call(call.id)
    except Exception:
        logger.warning("Failed to finish Weave parent span", exc_info=True)
        try:
            _weave_call_context.pop_call(call.id)
        except Exception:
            pass
    finally:
        _current_agent_call.set(None)
        # Exit the weave.attributes() context entered in before_agent_callback
        goal_ctx = _current_agent_goal_ctx.get(None)
        if goal_ctx:
            try:
                goal_ctx.__exit__(None, None, None)
            except Exception:
                pass
            _current_agent_goal_ctx.set(None)
    return None


# ---------------------------------------------------------------------------
# LLM reasoning capture callback
# ---------------------------------------------------------------------------

_MAX_REASONING_LENGTH = 2000


async def adk_after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Extract LLM reasoning text and stash in session state for tool spans.

    When the model decides to call a tool, the response typically includes
    thought parts (reasoning) alongside function_call parts. This callback
    extracts the reasoning, stores it in state["_last_reasoning"], and strips
    thought parts from the response so they don't appear in the chat.

    Returns None if no thought parts were stripped, or the modified response.
    """
    if not llm_response.content or not llm_response.content.parts:
        return None

    reasoning_parts = []
    has_thought_parts = False
    for part in llm_response.content.parts:
        text = getattr(part, "text", None)
        if not text:
            continue
        if getattr(part, "thought", False):
            reasoning_parts.append(text)
            has_thought_parts = True

    # Fall back to regular text parts if no thought parts exist
    if not reasoning_parts:
        for part in llm_response.content.parts:
            text = getattr(part, "text", None)
            if text and not getattr(part, "function_call", None):
                reasoning_parts.append(text)

    if (
        reasoning_parts
        and hasattr(callback_context, "state")
        and hasattr(callback_context.state, "__setitem__")
    ):
        reasoning_text = "\n".join(reasoning_parts)
        callback_context.state["_last_reasoning"] = reasoning_text[
            :_MAX_REASONING_LENGTH
        ]

    # Strip thought parts from the response so they don't leak into the chat
    if has_thought_parts:
        llm_response.content.parts = [
            p for p in llm_response.content.parts if not getattr(p, "thought", False)
        ]
        return llm_response

    return None


async def capture_last_model_output_after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Stash the final model text output in session state for the root Weave span.

    Joins non-thought, non-function_call text parts from the LlmResponse into a
    single string and stores it in ``state["_last_model_output"]``. This key is
    read by ``weave_after_agent_callback`` to populate ``finish_call(output=...)``
    so MER-E can inspect the agent's response text at trace time.

    Returns None so the response is not modified.
    """
    if not llm_response.content or not llm_response.content.parts:
        return None

    text_parts: list[str] = []
    for part in llm_response.content.parts:
        text = getattr(part, "text", None)
        if not text:
            continue
        if getattr(part, "thought", False):
            continue
        if getattr(part, "function_call", None):
            continue
        text_parts.append(text)

    if (
        text_parts
        and hasattr(callback_context, "state")
        and hasattr(callback_context.state, "__setitem__")
    ):
        callback_context.state["_last_model_output"] = "\n".join(text_parts)

    return None


_MAX_OUTPUT_BYTES = 100 * 1024  # 100KB


def truncate_large_output(output: Any, max_bytes: int = _MAX_OUTPUT_BYTES) -> Any:
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
        serialized = (
            json.dumps(output) if isinstance(output, (dict, list)) else str(output)
        )
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

        # NOTE: We deliberately do NOT write status/duration_ms via
        # weave.get_current_call().summary here. By the time after_tool_callback
        # fires, the tool's @weave.op span has already finished, so
        # get_current_call() returns the PARENT agent span — writing to it
        # leaks tool-level fields onto the parent. Instead:
        #   - duration_ms is already tracked natively by Weave on the L3 span
        #   - status can be inferred from the tool's return value (captured
        #     as the L3 span output by Weave)
        #   - tool_name is already set via weave.attributes() in
        #     adk_before_tool_callback (hooks.py)

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
    finally:
        if hasattr(tool_context, "state") and hasattr(
            tool_context.state, "__setitem__"
        ):
            # Append current tool to previous_tool_calls for the next tool call
            previous = tool_context.state.get("_previous_tool_calls", [])
            previous.append(tool.name)
            tool_context.state["_previous_tool_calls"] = previous

            # Exit the weave.attributes() context entered in adk_before_tool_callback
            attrs_ctx = tool_context.state.get("_trace_attrs_ctx")
            if attrs_ctx:
                attrs_ctx.__exit__(None, None, None)
                tool_context.state["_trace_attrs_ctx"] = None

    return None
