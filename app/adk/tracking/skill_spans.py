"""Weave span callbacks for SkillToolset tool invocations (SK-PRD-02 §4).

Three callbacks complete SkillToolset observability:

  skill_spans_before_agent_callback — turn-start: seeds skills_allowed_tools
      in session state (consumed by SK-24 skill filter) and emits a degraded
      skill.list span when the sidecar marks skill_load_total_failure (AC-2a).

  skill_spans_before_tool_callback — opens a Weave child span for
      list_skills / load_skill / load_skill_resource; stores the in-flight
      call + resolved skill_id in the per-call registry keyed by
      tool_context.function_call_id.

  skill_spans_after_tool_callback — closes the span for the matching
      function_call_id; adds response-derived output attrs
      (instruction_bytes, resource_bytes); sets state["active_skill_id"] on a
      successful load_skill invocation.

All three degrade open: any exception is caught, logged at WARNING, and the
callback returns None so the agent continues unaffected.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from app.adk.agents.skill_tool_filter import parse_allowed_tools
from shared.structured_logging import get_structured_logger

# Lazy import guard — mirrors app/adk/tracking/sandbox_pool_spans.py.  builder.py
# imports the skill_spans_* callbacks at module top, so a Weave import failure
# would cascade into the entire agent factory becoming unimportable.  Both
# bindings fall back to ``None`` and every call site checks before use.
_weave_get_client: Callable[[], Any] | None = None
_weave_call_context: Any | None = None
try:
    from weave.trace.api import get_client as _weave_get_client
    from weave.trace.context import call_context as _weave_call_context
except ImportError:  # pragma: no cover
    pass

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types

logger = get_structured_logger(__name__)

_SKILL_TOOL_NAMES = frozenset({"list_skills", "load_skill", "load_skill_resource"})

# Maximum character length for LLM-supplied string values written to Weave
# span attributes/inputs.  Guards against data-volume abuse.
_MAX_SPAN_STRING = 256

# SK-PRD-05 forward-compat: every v1 skill is account-owned.  SK-PRD-05 will
# replace this constant with a per-skill lookup once the loader surfaces a
# system/account owner type; the span schema does not change here.
_DEFAULT_SKILL_OWNER_TYPE: Literal["account", "system"] = "account"

# Per-call registry: maps function_call_id → {"call": WeaveCall, "skill_id": str | None}
# Stored inside a ContextVar[dict] so each asyncio task (agent turn) has its
# own isolated copy while before_tool and after_tool within the same task can
# share entries.  Keyed by ADK's function_call_id, which is stable across the
# before/after pair for any dispatch model — parallel, nested, or serial.
# When function_call_id is None (fallback for future ADK changes), a sentinel
# key "_single_slot" replicates the old single-slot behaviour with a WARNING.
_skill_ctx_registry: contextvars.ContextVar[dict[str, dict[str, Any]] | None] = (
    contextvars.ContextVar("_skill_ctx_registry", default=None)
)


def _get_skill_name_index(context: Any) -> dict[str, dict]:
    """Return skill_name_index from the agent sidecar, or {}."""
    try:
        ic = getattr(context, "_invocation_context", None)
        if ic is not None:
            agent = getattr(ic, "agent", None)
            if agent is not None:
                # Deferred import — avoids circular dependency through
                # app.adk.agents.agent_factory.__init__ → builder → skill_spans.
                from app.adk.agents.agent_factory.skill_metadata import (
                    get_skill_build_metadata,
                )

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
                # Deferred import — avoids circular dependency through
                # app.adk.agents.agent_factory.__init__ → builder → skill_spans.
                from app.adk.agents.agent_factory.skill_metadata import (
                    get_skill_build_metadata,
                )

                return get_skill_build_metadata(agent)
    except Exception:
        pass
    return {}


def _emit_total_failure_span(
    account_id: str,
    *,
    skill_load_total_failure: bool = False,
    skill_load_timeout: bool = False,
) -> None:
    """Open and immediately close a skill.list span flagged as degraded (AC-2a).

    Called when the sidecar marks skill_load_total_failure or skill_load_timeout
    so MER-E can score the session as degraded even though list_skills will never
    fire (no SkillToolset was attached).  Emits at most once per session turn —
    the caller sets state["_skill_failure_span_emitted"] after this returns.
    """
    if _weave_get_client is None:
        return
    client = _weave_get_client()
    if not client:
        return
    attrs: dict[str, Any] = {
        "account_id": account_id,
        "skill_count": 0,
        "skill_ids": [],
        "skill_owner_type": _DEFAULT_SKILL_OWNER_TYPE,
    }
    if skill_load_total_failure:
        attrs["skill_load_total_failure"] = True
    if skill_load_timeout:
        attrs["skill_load_timeout"] = True
    call = client.create_call(
        op="skill.list",
        inputs={},
        attributes=attrs,
        use_stack=True,
    )
    if call is None:
        return
    try:
        client.finish_call(call, output={"status": "degraded"})
    finally:
        if _weave_call_context is not None:
            try:
                _weave_call_context.pop_call(call.id)
            except Exception:
                pass


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

        _total_failure = meta.get("skill_load_total_failure")
        _load_timeout = meta.get("skill_load_timeout")
        # Emit at most once per session — re-emitting on every turn would
        # produce N spans per session and make MER-E scoring noisy.
        if (_total_failure or _load_timeout) and not state.get(
            "_skill_failure_span_emitted"
        ):
            account_id = "unknown"
            try:
                account_id = str(state.get("account_id") or "unknown")
            except Exception:
                pass
            try:
                _emit_total_failure_span(
                    account_id,
                    skill_load_total_failure=bool(_total_failure),
                    skill_load_timeout=bool(_load_timeout),
                )
                try:
                    state["_skill_failure_span_emitted"] = True
                except Exception:
                    pass
            except Exception:
                logger.warning(
                    "skill_spans: failed to emit failure skill.list span",
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
    The created call is stored in _skill_ctx_registry keyed by
    tool_context.function_call_id so concurrent invocations remain isolated.

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

        if _weave_get_client is None:
            return None
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
                    "skill_owner_type": _DEFAULT_SKILL_OWNER_TYPE,
                },
                use_stack=True,
            )

        elif tool.name == "load_skill":
            skill_name = str(args.get("name", ""))[:_MAX_SPAN_STRING]
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
                    "skill_owner_type": _DEFAULT_SKILL_OWNER_TYPE,
                },
                use_stack=True,
            )

        elif tool.name == "load_skill_resource":
            skill_name = str(args.get("skill_name", ""))[:_MAX_SPAN_STRING]
            rel_path = str(args.get("path", ""))[:_MAX_SPAN_STRING]
            entry = skill_name_index.get(skill_name, {})
            resolved_skill_id = entry.get("skill_id")
            call = client.create_call(
                op="skill.load_resource",
                inputs={"skill_name": skill_name, "path": rel_path},
                attributes={
                    "account_id": account_id,
                    "skill_id": resolved_skill_id or "unknown",
                    "rel_path": rel_path,
                    "skill_owner_type": _DEFAULT_SKILL_OWNER_TYPE,
                },
                use_stack=True,
            )

        if call is not None:
            call_id: str | None = getattr(tool_context, "function_call_id", None)
            if call_id is None:
                logger.warning(
                    "skill_spans: tool_context.function_call_id is None; "
                    "falling back to single-slot registry key — "
                    "concurrent skill-tool dispatch may corrupt span pairing",
                    extra={"tool_name": tool.name},
                )
                call_id = "_single_slot"

            existing = _skill_ctx_registry.get() or {}
            updated = {**existing, call_id: {"call": call, "skill_id": resolved_skill_id}}
            _skill_ctx_registry.set(updated)
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

    Looks up the in-flight call by tool_context.function_call_id in the
    per-call registry, pops the entry, and closes that exact call.

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

    call_id: str | None = getattr(tool_context, "function_call_id", None)
    if call_id is None:
        logger.warning(
            "skill_spans: tool_context.function_call_id is None in after_tool; "
            "falling back to single-slot registry key",
            extra={"tool_name": tool.name},
        )
        call_id = "_single_slot"

    registry = _skill_ctx_registry.get() or {}
    entry = registry.get(call_id)
    if entry is None:
        return None

    call = entry.get("call")
    skill_id: str | None = entry.get("skill_id")

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

        client = _weave_get_client() if _weave_get_client is not None else None
        if client and call is not None:
            client.finish_call(call, output=output or {"status": "completed"})
        if call is not None and _weave_call_context is not None:
            _weave_call_context.pop_call(call.id)
    except Exception:
        logger.warning(
            "skill_spans_after_tool_callback failed (non-blocking)", exc_info=True
        )
        if call is not None and _weave_call_context is not None:
            try:
                _weave_call_context.pop_call(call.id)
            except Exception:
                pass
    finally:
        # Pop the entry from the registry copy-on-write style.
        current = _skill_ctx_registry.get() or {}
        updated = {k: v for k, v in current.items() if k != call_id}
        _skill_ctx_registry.set(updated)

    return None
