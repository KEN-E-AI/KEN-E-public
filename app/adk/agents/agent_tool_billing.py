"""Per-turn token capture for isolated agent-as-tool leaves (AH-PRD-15 §5).

Background — why this exists
----------------------------
The built-in ``google_search`` grounding tool (and the ``numerical_analyst``
code-execution leaf) must be the *only* tool in their agent's LLM request:
Gemini rejects ``400 INVALID_ARGUMENT: "Multiple tools are supported only when
they are all search tools."`` when a search/grounding or code-execution tool
shares the request with any function declaration. Every in-hierarchy sub-agent
mode injects a function tool next to it (``mode='task'`` → ``FinishTaskTool``;
``mode='chat'`` → ``transfer_to_agent``), so the leaf can only be isolated by
running it inside an ADK ``AgentTool`` — its own sub-runner, no injected sibling
tool. (See ``builtin-google-search-needs-agenttool-isolation``; this replaces the
AH-114 task-mode migration that 400'd in prod, AH-121.)

But ``AgentTool.run_async`` runs the leaf in a private inner ``Runner`` and never
appends the leaf's inner events to the outer ``session.events`` (GitHub
``google/adk-python#3984``, OPEN). The authoritative meter
(``chat_after_agent_callback`` → ``_gather_turn_events(session.events)`` →
``extract_billable_tokens``) therefore never sees the leaf's ``usage_metadata``:
the search/analyst tokens go uncounted. That is the exact AH-75 billing defect.

The fix — off-state per-turn capture
------------------------------------
Recover the dropped ``usage_metadata`` with a tiny ``after_model_callback`` on
the leaf (:func:`capture_agent_tool_usage`) that pushes each model call's billable
tokens into a per-turn sink. The root's ``chat_after_agent_callback`` drains the
sink (:func:`drain_turn_billing`) and folds the total into the turn delta.

Two pieces, mirroring the proven ``app/adk/tracking/tool_trace_context.py``
pattern (a module-level stash, *not* session state — ``AgentTool.run_async``
deep-copies parent state into the child session, which is exactly why state-based
bridging broke ``agent.google_search`` before):

* ``_OUTER_TURN_ID`` — a ``ContextVar`` carrying the outer turn's
  ``invocation_id``. It is set once at turn start (root ``before_agent_callback``)
  and read by the leaf callback. ``AgentTool.run_async`` iterates the inner runner
  *in the same asyncio task*, and ``asyncio.gather`` (parallel google_search,
  AH-98 AC #9) copies the context — copies inherit the value, so the leaf reads
  the correct turn id even under parallel dispatch.
* ``_BILLING_SINK`` — a process-global ``dict[turn_id -> list[counts]]``. The leaf
  callback *appends* (additive: parallel leaf calls accumulate, no clobber); the
  root callback pops at end of turn (bounded memory). Off-state, so it survives
  the ``AgentTool`` deep-copy and never has to be serialised.

No double counting: the leaf's events never reach ``session.events`` (that is the
#3984 drop this compensates for), so ``_build_turn_delta`` never counts them — the
sink is the *only* source. If #3984 is ever fixed upstream and inner events start
reaching the outer stream, this additive read would double-count and must be gated
off; that is called out in the PRD and tracked.

All functions are top-level (no closures) so the leaf's ``after_model_callback``
reference survives cloudpickle into the Agent Engine artifact.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

from shared.token_accounting import BillableTokenCounts, extract_billable_tokens

logger = logging.getLogger(__name__)

# Outer-turn invocation id, set by the root before_agent_callback and read by the
# isolated leaf's after_model_callback. Plain-string value → safe to inherit across
# the asyncio.gather context copy that parallel google_search dispatch incurs.
_OUTER_TURN_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "kene_outer_turn_id", default=None
)

# Per-turn capture sink, keyed by outer invocation_id. Off-state (module-global),
# so it survives AgentTool.run_async's deep-copy of session state.
_BILLING_SINK: dict[str, list[BillableTokenCounts]] = {}

# Bound the sink so a turn that aborts before its after_agent_callback drains it
# cannot leak unboundedly. A turn appends O(1-3) entries; 256 live turns is far
# beyond real concurrency on one worker process.
_MAX_TRACKED_TURNS = 256


def set_outer_turn_id(invocation_id: str | None) -> None:
    """Bind *invocation_id* as the current turn's billing key (root turn start).

    Call once from the root ``before_agent_callback``. Initialises (or resets) the
    sink bucket for this turn so :func:`drain_turn_billing` always finds a list,
    and evicts the oldest bucket when the bound is exceeded (defensive cleanup for
    turns that errored out before draining).
    """
    _OUTER_TURN_ID.set(invocation_id)
    if not invocation_id:
        return
    if invocation_id not in _BILLING_SINK:
        if len(_BILLING_SINK) >= _MAX_TRACKED_TURNS:
            # Drop the oldest-inserted bucket (insertion-ordered dict).
            oldest = next(iter(_BILLING_SINK), None)
            if oldest is not None:
                _BILLING_SINK.pop(oldest, None)
        _BILLING_SINK[invocation_id] = []


def capture_agent_tool_usage(callback_context: Any, llm_response: Any) -> None:
    """ADK ``after_model_callback`` for an isolated AgentTool leaf.

    Attached at construction to the ``google_search`` / ``numerical_analyst`` leaf
    (see ``tools/agent_tools/*.py``). Extracts the leaf model call's billable
    tokens and appends them to the current turn's sink so the root callback can
    bill them — they are otherwise dropped by ``AgentTool.run_async`` (#3984).

    Returns ``None`` (the original model response is used unchanged) and never
    raises — a billing-capture failure must not break a model turn. Adding only a
    callback (not a tool) keeps the leaf's request carrying *only* its search /
    code-execution tool, so the "all tools must be search tools" 400 cannot recur.
    """
    try:
        turn_id = _OUTER_TURN_ID.get()
        if not turn_id:
            return None
        counts = extract_billable_tokens(llm_response)
        if counts.total_billable:
            _BILLING_SINK.setdefault(turn_id, []).append(counts)
    except Exception:  # pragma: no cover - defensive; billing must not break turns
        logger.debug("capture_agent_tool_usage failed (non-blocking)", exc_info=True)
    return None


def drain_turn_billing(invocation_id: str | None) -> BillableTokenCounts:
    """Pop and sum the captured isolated-agent-tool tokens for *invocation_id*.

    Call once from the root ``after_agent_callback``. Removes the turn's bucket
    (one-shot — a second call returns zeros) and returns the summed
    ``BillableTokenCounts`` to fold into the turn delta. Returns zeros when there
    is no id or nothing was captured (the common no-web-search turn).
    """
    if not invocation_id:
        return BillableTokenCounts()
    captured = _BILLING_SINK.pop(invocation_id, [])
    if not captured:
        return BillableTokenCounts()
    return BillableTokenCounts(
        input=sum(c.input for c in captured),
        output=sum(c.output for c in captured),
        reasoning=sum(c.reasoning for c in captured),
    )


def reset_for_tests() -> None:
    """Clear the sink and unset the turn id. Test isolation only."""
    _BILLING_SINK.clear()
    _OUTER_TURN_ID.set(None)
