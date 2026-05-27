"""Weave span callbacks for SkillToolset tool invocations (SK-PRD-02 §4).

Three callbacks complete SkillToolset observability:

  skill_spans_before_agent_callback — turn-start: seeds skills_allowed_tools
      in session state (consumed by SK-24 skill filter) and emits a degraded
      skill.list span when the sidecar marks skill_load_total_failure (AC-2a).

  skill_spans_before_tool_callback — opens a Weave child span for
      list_skills / load_skill / load_skill_resource; stores the in-flight
      call + resolved skill_id in a ContextVar.

  skill_spans_after_tool_callback — closes the span; adds response-derived
      output attrs (instruction_bytes, resource_bytes); sets
      state["active_skill_id"] on a successful load_skill invocation.

All three degrade open: any exception is caught, logged at WARNING, and the
callback returns None so the agent continues unaffected.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any

from weave.trace.api import get_client as _weave_get_client
from weave.trace.context import call_context as _weave_call_context

from app.adk.agents.agent_factory.skill_metadata import get_skill_build_metadata
from app.adk.agents.skill_tool_filter import parse_allowed_tools
from shared.structured_logging import get_structured_logger

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types

logger = get_structured_logger(__name__)

_SKILL_TOOL_NAMES = frozenset({"list_skills", "load_skill", "load_skill_resource"})

# Tracks the in-flight Weave call and resolved metadata between
# before_tool and after_tool for a single skill tool invocation.
# Shape: {"call": WeaveCall, "skill_id": str | None}
_current_skill_ctx: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("_current_skill_ctx", default=None)
)


def _get_skill_name_index(context: Any) -> dict[str, dict]:
    """Return skill_name_index from the agent sidecar, or {}."""
    try:
        ic = getattr(context, "_invocation_context", None)
        if ic is not None:
            agent = getattr(ic, "agent", None)
            if agent is not None:
                return get_skill_build_metadata(agent).get("skill_name_index", {})
    except Exception:
        pass
    return {}


def _get_agent_meta(context: Any) -> dict[str, Any]:
    """Return full sidecar metadata for the agent, or {}."""
    try:
        ic = getattr(context, "_invocation_context", None)
        if ic is not None:
            agent = getattr(ic, "agent", None)
            if agent is not None:
                return get_skill_build_metadata(agent)
    except Exception:
        pass
    return {}


def _emit_total_failure_span(account_id: str) -> None:
    """Open and immediately close a skill.list span flagged as degraded (AC-2a).

    Called from skill_spans_before_agent_callback when the sidecar marks
    skill_load_total_failure so MER-E can score the session as degraded even
    though list_skills will never fire (no SkillToolset was attached).
    """
    client = _weave_get_client()
    if not client:
        return
    call = client.create_call(
        op="skill.list",
        inputs={},
        attributes={
            "account_id": account_id,
            "skill_count": 0,
            "skill_ids": [],
            "skill_load_total_failure": True,
        },
        use_stack=True,
    )
    client.finish_call(call, output={"status": "degraded"})
    _weave_call_context.pop_call(call.id)


def skill_spans_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Seed turn-start session state; emit degraded skill.list span if needed.

    Runs after weave_before_agent_callback so the L1 agent span is active when
    _emit_total_failure_span fires, making the degraded span a child of the
    turn root.

    State keys written:
      active_skill_id        — cleared to None to reset from any prior turn.
      skills_allowed_tools   — maps skill_id → pre-parsed allowed patterns (or
                               None) for every skill in the sidecar; consumed by
                               skill_allowed_tools_before_tool_callback (SK-24).
    """
    try:
        state: Any = {}
        if hasattr(callback_context, "state") and hasattr(
            callback_context.state, "get"
        ):
            state = callback_context.state

        # Reset active_skill_id so the SK-24 filter starts clean each turn.
        try:
            state["active_skill_id"] = None
        except Exception:
            pass

        meta = _get_agent_meta(callback_context)
        skill_name_index: dict[str, dict] = meta.get("skill_name_index", {})

        if skill_name_index:
            skills_allowed_tools: dict[str, Any] = {
                entry["skill_id"]: parse_allowed_tools(entry.get("allowed_tools"))
                for entry in skill_name_index.values()
            }
            try:
                state["skills_allowed_tools"] = skills_allowed_tools
            except Exception:
                pass

        if meta.get("skill_load_total_failure"):
            account_id = "unknown"
            try:
                account_id = str(state.get("account_id") or "unknown")
            except Exception:
                pass
            try:
                _emit_total_failure_span(account_id)
            except Exception:
                logger.warning(
                    "skill_spans: failed to emit total-failure skill.list span",
                    exc_info=True,
                )
    except Exception:
        logger.warning(
            "skill_spans_before_agent_callback failed (non-blocking)", exc_info=True
        )
    return None


async def skill_spans_before_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """Open a Weave child span for a SkillToolset tool invocation.

    No-ops for tools outside _SKILL_TOOL_NAMES.  Span attributes are built
    from session state (account_id) and the agent sidecar (skill_name_index).
    The created call is stored in _current_skill_ctx for after_tool to close.

    Returns None — never blocks tool execution.
    """
    if tool.name not in _SKILL_TOOL_NAMES:
        return None
    try:
        state: Any = {}
        if hasattr(tool_context, "state") and hasattr(tool_context.state, "get"):
            state = tool_context.state

        account_id = "unknown"
        try:
            account_id = str(state.get("account_id") or "unknown")
        except Exception:
            pass

        skill_name_index = _get_skill_name_index(tool_context)

        client = _weave_get_client()
        if not client:
            return None

        call = None
        resolved_skill_id: str | None = None

        if tool.name == "list_skills":
            skill_ids = [entry["skill_id"] for entry in skill_name_index.values()]
            call = client.create_call(
                op="skill.list",
                inputs={},
                attributes={
                    "account_id": account_id,
                    "skill_count": len(skill_ids),
                    "skill_ids": skill_ids,
                },
                use_stack=True,
            )

        elif tool.name == "load_skill":
            skill_name = str(args.get("name", ""))
            entry = skill_name_index.get(skill_name, {})
            resolved_skill_id = entry.get("skill_id")
            call = client.create_call(
                op="skill.load",
                inputs={"name": skill_name},
                attributes={
                    "account_id": account_id,
                    "skill_id": resolved_skill_id or "unknown",
                    "skill_name": skill_name,
                    "skill_version": entry.get("version", 0),
                },
                use_stack=True,
            )

        elif tool.name == "load_skill_resource":
            skill_name = str(args.get("skill_name", ""))
            rel_path = str(args.get("path", ""))
            entry = skill_name_index.get(skill_name, {})
            resolved_skill_id = entry.get("skill_id")
            call = client.create_call(
                op="skill.load_resource",
                inputs={"skill_name": skill_name, "path": rel_path},
                attributes={
                    "account_id": account_id,
                    "skill_id": resolved_skill_id or "unknown",
                    "rel_path": rel_path,
                },
                use_stack=True,
            )

        if call is not None:
            _current_skill_ctx.set({"call": call, "skill_id": resolved_skill_id})
    except Exception:
        logger.warning(
            "skill_spans_before_tool_callback failed (non-blocking)", exc_info=True
        )
    return None


async def skill_spans_after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
    """Close the Weave span opened by skill_spans_before_tool_callback.

    Also:
    - load_skill success (no "error" key in response): sets
      state["active_skill_id"] = skill_id so the SK-24 filter applies the
      skill's allowed-tools restriction for subsequent tool calls this turn.
    - load_skill: extracts instruction_bytes from the response.
    - load_skill_resource: extracts resource_bytes from the response.

    Returns None — never modifies tool_response.
    """
    if tool.name not in _SKILL_TOOL_NAMES:
        return None

    ctx = _current_skill_ctx.get(None)
    if ctx is None:
        return None

    call = ctx.get("call")
    skill_id: str | None = ctx.get("skill_id")

    try:
        state: Any = {}
        if hasattr(tool_context, "state") and hasattr(tool_context.state, "get"):
            state = tool_context.state

        output: dict[str, Any] = {}

        if tool.name == "load_skill":
            instructions = tool_response.get("instructions") or tool_response.get(
                "instruction", ""
            )
            if instructions and isinstance(instructions, str):
                output["instruction_bytes"] = len(instructions.encode("utf-8"))
            # Set active_skill_id only on success (no error key present).
            if not tool_response.get("error") and skill_id:
                try:
                    state["active_skill_id"] = skill_id
                except Exception:
                    pass

        elif tool.name == "load_skill_resource":
            content = (
                tool_response.get("content")
                or tool_response.get("resource_content", "")
                or tool_response.get("resource", "")
            )
            if content and isinstance(content, str):
                output["resource_bytes"] = len(content.encode("utf-8"))

        client = _weave_get_client()
        if client and call is not None:
            client.finish_call(call, output=output or {"status": "completed"})
        if call is not None:
            _weave_call_context.pop_call(call.id)
    except Exception:
        logger.warning(
            "skill_spans_after_tool_callback failed (non-blocking)", exc_info=True
        )
        if call is not None:
            try:
                _weave_call_context.pop_call(call.id)
            except Exception:
                pass
    finally:
        _current_skill_ctx.set(None)

    return None
