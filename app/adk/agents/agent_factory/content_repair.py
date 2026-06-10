"""Repair orphaned function calls in outgoing model-request history.

ADK 2.0's chat-mode task-dispatch wrapper (``run_llm_agent_as_node`` /
``_llm_agent_wrapper.py``) breaks out of the agent's event generator as soon
as it detects task-delegation FunctionCalls in a model turn. Any REGULAR tool
call the model emitted in the same parallel turn (e.g. ``set_todo_list``
alongside two specialist dispatches) is left unanswered: its function-response
event is discarded with the closed generator, the session persists a model
turn with N function calls followed by fewer than N function responses, and
every subsequent request that replays that history is rejected by Gemini —
``400 INVALID_ARGUMENT: Please ensure that the number of function response
parts is equal to the number of function call parts`` — permanently poisoning
the session (staging incident 2026-06-10; session ID in internal incident log).

``repair_orphaned_function_calls_before_model`` walks ``llm_request.contents``
and pads every HISTORICAL model turn's unanswered function calls with a
synthetic "interrupted" function response, restoring the call/response pairing
Gemini requires. The trailing model turn is never touched — its responses are
legitimately still pending when the request is built mid-turn.

Scope caveat: this repairs the OUTGOING request copy on every call — the
stored session events keep the imbalance forever, so affected sessions work
only while this callback stays registered. Disabling it re-breaks every
session that ever hit the drop. It also does not execute the dropped tool
call (the model is told the call was interrupted and may re-issue it). The
proper fix is upstream in ADK's wrapper — see ``docs/adk-upstream-tracker.md``
for the filed bug, fix-watch criteria, and monitoring narrative. This callback
should outlive the upstream fix as a safety net for anything else that orphans
a call (e.g. a turn crashing between call and response).

Matching prefers function-call ids; when ids are absent (they can be stripped
between event storage and request assembly) it falls back to name-multiset
matching, which resolves same-name parallel calls by count.
"""

from __future__ import annotations

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

_INTERRUPTED_RESULT: dict[str, str] = {
    "result": (
        "This tool call was interrupted before a response was recorded. "
        "Do not assume it executed."
    )
}


def _unanswered(
    fcs: list[types.FunctionCall], frs: list[types.FunctionResponse]
) -> list[types.FunctionCall]:
    """Return the function calls with no matching response (id, then name)."""
    unused = list(frs)
    missing: list[types.FunctionCall] = []
    for fc in fcs:
        match = None
        if fc.id:
            match = next((fr for fr in unused if fr.id == fc.id), None)
        if match is None:
            match = next((fr for fr in unused if fr.name == fc.name), None)
        if match is None:
            missing.append(fc)
        else:
            unused.remove(match)
    return missing


def repair_orphaned_function_calls_before_model(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    """Pad unanswered historical function calls with synthetic responses.

    Registered as a ``before_model_callback`` on the root agent; mutates
    ``llm_request.contents`` in place and always returns ``None`` so the
    (repaired) request proceeds to the model.
    """
    contents = llm_request.contents or []
    i = 0
    while i < len(contents):
        content = contents[i]
        if getattr(content, "role", None) != "model":
            i += 1
            continue
        parts = getattr(content, "parts", None) or []
        fcs = [p.function_call for p in parts if p.function_call is not None]
        if not fcs or i == len(contents) - 1:
            # No calls to pair, or the live trailing turn (responses pending).
            i += 1
            continue

        # The responses for a model FC turn live in the contiguous run of
        # non-model contents that follows it (ADK normally merges them into
        # one user content immediately after).
        j = i + 1
        fr_contents: list[types.Content] = []
        while j < len(contents) and getattr(contents[j], "role", None) != "model":
            if any(
                p.function_response is not None
                for p in (contents[j].parts or [])
            ):
                fr_contents.append(contents[j])
            j += 1
        frs = [
            p.function_response
            for c in fr_contents
            for p in (c.parts or [])
            if p.function_response is not None
        ]

        missing = _unanswered(fcs, frs)
        if missing:
            pad = [
                types.Part(
                    function_response=types.FunctionResponse(
                        id=fc.id,
                        name=fc.name,
                        response=dict(_INTERRUPTED_RESULT),
                    )
                )
                for fc in missing
            ]
            if fr_contents:
                target = fr_contents[-1]
                target.parts = list(target.parts or []) + pad
            else:
                contents.insert(
                    i + 1, types.Content(role="user", parts=pad)
                )
            logger.warning(
                "Padded synthetic function responses for orphaned function "
                "calls in model-request history.",
                extra={
                    "padded_names": [fc.name for fc in missing],
                    "content_index": i,
                },
            )
        i += 1
    return None
