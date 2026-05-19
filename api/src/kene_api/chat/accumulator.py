"""Per-turn in-memory delta accumulator for the Chat component.

References: CH-PRD-01 §5.2 (reference implementation), §7 AC-6, AC-9, AC-10.

The `SessionTurnAccumulator` is instantiated once per streaming completion
request, receives every ADK event via `add_event(event)` as they stream, and
produces a single Firestore-update dict via `build_delta()` at end-of-turn.
That one dict is passed to `ChatSessionSideTableService.update_from_delta(...)`
— writes never block the SSE stream.

Design decisions (per CH-12 Implementation Plan):
 - Token extraction calls `extract_billable_tokens` (Billing-owned helper).
   No duplicate definition here — see models/chat.py lines 178-184.
 - `firestore.Increment(n)` values are produced directly in `build_delta()`.
   The side-table service passes the dict straight into `doc_ref.update()`.
 - `current_context_tokens`: on a compaction event, a literal int (the
   recomputed post-compaction baseline); otherwise `Increment(turn_tokens)`.
 - `search_text` is NOT computed here — requires title + category_name that
   the accumulator does not have. The side-table service recomputes it when
   `latest_summary` is present in the delta.
 - Rolling buffer of the last 11 events (summary + overlap + last 10 retained)
   is maintained in a `collections.deque(maxlen=11)` for the post-compaction
   helper. Memory ceiling = 11 x per-event size, bounded.
 - `last_agent_message_at = now()` is stamped on every `build_delta()` (PRD
   §5.2). Approximation: pure-tool-error turns still stamp now(). Acceptable
   for v1 — the typical turn produces one assistant message.
 - `build_delta()` is one-shot by contract. CH-13 (callback wiring) must
   guarantee a single call per turn. This is documented, not enforced, so
   the state remains readable for testing.
"""

from __future__ import annotations

import os
import sys
from collections import deque
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from google.cloud import firestore

# ---------------------------------------------------------------------------
# Import the Billing-owned token-accounting helper.
# The app/ package lives next to api/ in the workspace root.
# tests/unit/chat/test_token_accounting.py uses the same sys.path pattern to
# resolve this cross-package import.  We follow that precedent here so local
# development and CI both work without editable-install trickery.
# TODO(CH-13): replace with an editable install of app/adk in the Dockerfile.
# ---------------------------------------------------------------------------
_ADK_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "app", "adk"))
if _ADK_PATH not in sys.path:
    sys.path.insert(0, _ADK_PATH)

from token_accounting import BillableTokenCounts, extract_billable_tokens  # noqa: E402


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Pure-function helper (AC-10 contract)
# ---------------------------------------------------------------------------


def compute_post_compaction_window_tokens(
    compaction_event: Any,
    retained_events: list[Any],
) -> int:
    """Return the sum of usage_metadata.total_token_count for the retained window.

    Called with the compaction-summary event itself plus the (up to 10)
    retained-window events that follow it in the accumulator's rolling buffer.
    Events missing `usage_metadata` or `total_token_count` contribute 0.

    AC-10 (CH-PRD-01 §7): the result MUST be a recomputed sum, NOT zero —
    resetting to zero would understate true context usage after compaction.

    Args:
        compaction_event: The ADK compaction-summary event.
        retained_events: Subsequent events in the post-compaction active window
                         (summary + overlap invocation + last ≤10 retained).

    Returns:
        Non-negative integer token count.
    """
    total = 0
    for event in [compaction_event, *retained_events]:
        usage = getattr(event, "usage_metadata", None)
        if usage is not None:
            total += int(getattr(usage, "total_token_count", 0) or 0)
    return total


# ---------------------------------------------------------------------------
# Private event-type detector helpers
# ---------------------------------------------------------------------------
# Detection heuristics are duck-typed against synthetic-event fixtures so
# unit tests remain zero-dependency on the real ADK Event type.  CH-13 will
# empirically confirm the real ADK 1.27.5 event-attribute shapes when wiring
# callbacks against a live runner and update these helpers if needed.


def _is_compaction_summary_event(event: Any) -> bool:
    """Return True if the event is an ADK compaction-summary event.

    Current heuristic: `event.type == "compaction_summary"` per PRD §5.2
    pseudocode.  CH-13 is the validation point for the real ADK shape.
    """
    return getattr(event, "type", None) == "compaction_summary"


def _is_tool_call_event(event: Any) -> bool:
    """Return True if the event represents a tool call."""
    return getattr(event, "type", None) == "tool_call"


def _is_final_text_event(event: Any) -> bool:
    """Return True if the event carries a final assistant text chunk.

    Current heuristic: `event.is_final_text` is truthy.  CH-13 validation
    point for real ADK shape.
    """
    return bool(getattr(event, "is_final_text", False))


def _is_user_or_model_author_event(event: Any) -> bool:
    """Return True iff event.author is exactly 'user' or 'model'.

    AC-9 (CH-PRD-01 §7): case-sensitive exact-string match.  'User', 'USER',
    'assistant', 'agent', '' all return False.  ADK documents lowercase strings
    (CH-7 spike confirmed author='root' for the root agent; 'user' for the
    human turn; 'model' for assistant response).
    """
    author = getattr(event, "author", None)
    return author in ("user", "model")


# ---------------------------------------------------------------------------
# Main accumulator class
# ---------------------------------------------------------------------------


class SessionTurnAccumulator:
    """In-memory per-turn delta for the Chat side-table.

    Usage pattern (CH-13 will wire this):

        accumulator = SessionTurnAccumulator()
        async for event in runner.run_async(...):
            accumulator.add_event(event)
            yield format_sse(event)
        # finally / after_agent_callback:
        delta = accumulator.build_delta()
        await side_table.update_from_delta(session_id, delta)

    `build_delta()` is one-shot by contract: call it exactly once per turn.
    Calling it twice returns the same dict (the accumulator's per-turn state
    is read-only after first build), but double-applying Increments would
    corrupt counters — CH-13 must guarantee a single call.
    """

    def __init__(self) -> None:
        # Token counters (cumulative across all events this turn)
        self._input: int = 0
        self._output: int = 0
        self._reasoning: int = 0

        # Activity counters
        self.tool_call_count: int = 0
        self.message_count_delta: int = 0
        self.compaction_count_delta: int = 0

        # Compaction-summary state
        self.latest_summary: str | None = None
        self.post_compaction_context_tokens: int | None = None

        # Final-text preview (last 160 chars of the most recent final-text event)
        self.final_text: str = ""

        # ADK invocation id, captured from the first stream chunk that carries
        # one (add_stream_chunk path only). The /completions finally block uses
        # it to build the shared per-turn idempotency key.
        self.invocation_id: str | None = None

        # Rolling buffer: last 11 events (summary + overlap + 10 retained)
        # Used by compute_post_compaction_window_tokens on compaction.
        self._event_buffer: deque[Any] = deque(maxlen=11)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_event(self, event: Any) -> None:
        """Fold one ADK event into the running per-turn totals.

        Called for every event in the streaming response before it is
        forwarded to the SSE client — this path must be fast and non-blocking.
        """
        # Always push to the rolling buffer first so compaction helper has the
        # full window including the compaction event itself.
        self._event_buffer.append(event)

        # Token accounting via the Billing-owned helper.
        counts: BillableTokenCounts = extract_billable_tokens(event)
        self._input += counts.input
        self._output += counts.output
        self._reasoning += counts.reasoning

        # Tool-call count
        if _is_tool_call_event(event):
            self.tool_call_count += 1

        # Message count (AC-9): user + model events only.
        if _is_user_or_model_author_event(event):
            self.message_count_delta += 1

        # Compaction: capture summary + recompute baseline (AC-10).
        if _is_compaction_summary_event(event):
            raw_content = getattr(event, "content", None)
            self.latest_summary = raw_content if isinstance(raw_content, str) else None
            self.compaction_count_delta += 1
            # The buffer at this point contains the compaction event plus the
            # retained-window events that precede it in the turn.  Per PRD §2
            # step 2: summary + overlap invocation + last 10 retained.
            # We pass the entire buffer (up to 11 items) to the helper.
            buffer_list = list(self._event_buffer)
            # The compaction event is the last item added; retained events are
            # the earlier items in the buffer.
            compaction_ev = buffer_list[-1]
            retained = buffer_list[:-1]
            self.post_compaction_context_tokens = compute_post_compaction_window_tokens(
                compaction_ev, retained
            )

        # Final-text preview (keep the most recent)
        if _is_final_text_event(event):
            text = getattr(event, "text", "") or ""
            self.final_text = text

    def add_stream_chunk(self, chunk: Any) -> None:
        """Fold one Agent Engine ``stream_query`` chunk into the running totals.

        Unlike `add_event`, which receives ADK Event objects, this normalises
        the JSON-shaped dict that Agent Engine yields over the wire. Only token
        counts and the invocation id are extracted — enough for the
        `/completions` finally block to flush partial token counts when a
        stream is cancelled (CH-PRD-01 §7 AC-8). Non-dict chunks (bare text
        fragments) and chunks without `usage_metadata` are ignored.

        message_count / tool_call_count / final-text are NOT derived here — the
        wire chunk shape for those is not guaranteed, and `after_agent_callback`
        writes them authoritatively from `session.events`.
        """
        if not isinstance(chunk, dict):
            return

        if self.invocation_id is None:
            invocation_id = chunk.get("invocation_id")
            if invocation_id:
                self.invocation_id = str(invocation_id)

        usage = chunk.get("usage_metadata")
        if isinstance(usage, dict):
            counts: BillableTokenCounts = extract_billable_tokens(
                SimpleNamespace(usage_metadata=SimpleNamespace(**usage))
            )
            self._input += counts.input
            self._output += counts.output
            self._reasoning += counts.reasoning

    def build_delta(self) -> dict[str, Any]:
        """Produce the Firestore update dict for this turn.

        Return value is ready to pass directly to `doc_ref.update(delta)`.
        Counter fields use `firestore.Increment(n)` so concurrent writes are
        safe.  `current_context_tokens` is a literal int on compaction turns
        (the recomputed post-compaction baseline) and `Increment(turn_tokens)`
        on normal turns.

        `search_text` is NOT included — the side-table service recomputes it
        when `latest_summary` is present in the delta, since it already has
        the title and category_name in hand.  See CH-PRD-01 §2 step 9.

        One-shot contract: call exactly once per turn (CH-13 responsibility).
        """
        now = _now_utc()
        turn_tokens = self._input + self._output + self._reasoning

        delta: dict[str, Any] = {
            "last_agent_stopped_at": now,
            "updated_at": now,
            "last_agent_message_at": now,  # v1 approximation: stamped on every turn; pure-tool turns may not have one
            # TODO(CH-13): stamp last_user_message_at on user-authored turns
            "input_tokens_total": firestore.Increment(self._input),
            "output_tokens_total": firestore.Increment(self._output),
            "reasoning_tokens_total": firestore.Increment(self._reasoning),
            "tool_call_count": firestore.Increment(self.tool_call_count),
            "message_count": firestore.Increment(self.message_count_delta),
            "last_message_preview": self.final_text[:160],
        }

        if self.post_compaction_context_tokens is not None:
            # Compaction turn: write the recomputed baseline as a literal so
            # the counter is reset to the true post-compaction window size.
            delta["current_context_tokens"] = self.post_compaction_context_tokens
            delta["latest_summary"] = self.latest_summary
            delta["summary_updated_at"] = now
            delta["compaction_count"] = firestore.Increment(self.compaction_count_delta)
        else:
            # Normal turn: accumulate tokens into the running context counter.
            delta["current_context_tokens"] = firestore.Increment(turn_tokens)

        return delta

    def build_stream_delta(self) -> dict[str, Any]:
        """Produce a partial side-table delta from `add_stream_chunk` data.

        Returned by the `/completions` finally block on a cancelled or failed
        streaming turn: a stop-stamp plus the partial token increments observed
        before the stream ended (CH-PRD-01 §7 AC-8). Counter fields are
        `firestore.Increment` so the write composes with prior counter state.

        Deliberately omits message_count / tool_call_count /
        last_message_preview — those need ADK Event objects (`add_event`) and
        are written authoritatively by `after_agent_callback`. Writing them
        here from incomplete stream data would clobber the real values.
        """
        now = _now_utc()
        turn_tokens = self._input + self._output + self._reasoning
        return {
            "last_agent_stopped_at": now,
            "updated_at": now,
            "input_tokens_total": firestore.Increment(self._input),
            "output_tokens_total": firestore.Increment(self._output),
            "reasoning_tokens_total": firestore.Increment(self._reasoning),
            "current_context_tokens": firestore.Increment(turn_tokens),
        }
