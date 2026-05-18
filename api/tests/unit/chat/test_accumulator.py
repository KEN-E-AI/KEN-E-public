"""Unit tests for SessionTurnAccumulator.

Covers every branch of add_event() (tokens, tool-call, compaction, final-text,
message-count, mixed authors) and every key in build_delta() output (Increment
values, literal post-compaction current_context_tokens, missing search_text
key, datetime stamps, preview truncation).

References: CH-PRD-01 §5.2, §7 AC-6, AC-9, AC-10.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from google.cloud.firestore_v1.transforms import Increment

# Resolve the api/src package so the test runner finds kene_api.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat.accumulator import (
    SessionTurnAccumulator,
    compute_post_compaction_window_tokens,
)

# ---------------------------------------------------------------------------
# Event fixture helpers (follow the SimpleNamespace pattern from
# test_token_accounting.py)
# ---------------------------------------------------------------------------


def _make_token_event(
    prompt: int = 0,
    candidates: int = 0,
    thoughts: int = 0,
    cached: int = 0,
) -> SimpleNamespace:
    """Build an event with usage_metadata but no special type/author."""
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt,
            candidates_token_count=candidates,
            thoughts_token_count=thoughts,
            cached_content_token_count=cached,
        ),
        type=None,
        author=None,
        is_final_text=False,
        text="",
        content=None,
    )


def _make_tool_call_event() -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=None,
        type="tool_call",
        author=None,
        is_final_text=False,
        text="",
        content=None,
    )


def _make_author_event(author: str) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=None,
        type=None,
        author=author,
        is_final_text=False,
        text="",
        content=None,
    )


def _make_final_text_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=None,
        type=None,
        author="model",
        is_final_text=True,
        text=text,
        content=None,
    )


def _make_compaction_event(summary: str = "summary", total_token_count: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(total_token_count=total_token_count),
        type="compaction_summary",
        author=None,
        is_final_text=False,
        text="",
        content=summary,
    )


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_all_counters_zero(self) -> None:
        a = SessionTurnAccumulator()
        assert a._input == 0
        assert a._output == 0
        assert a._reasoning == 0
        assert a.tool_call_count == 0
        assert a.message_count_delta == 0
        assert a.compaction_count_delta == 0

    def test_latest_summary_none(self) -> None:
        a = SessionTurnAccumulator()
        assert a.latest_summary is None

    def test_post_compaction_context_tokens_none(self) -> None:
        a = SessionTurnAccumulator()
        assert a.post_compaction_context_tokens is None

    def test_final_text_empty(self) -> None:
        a = SessionTurnAccumulator()
        assert a.final_text == ""


# ---------------------------------------------------------------------------
# Token aggregation (uses the CH-10 parity fixture)
# ---------------------------------------------------------------------------


class TestTokenAggregation:
    def test_ch10_parity_fixture(self) -> None:
        """Canonical fixture: prompt=1250, cached=200, candidates=380 → input=1050, output=380."""
        a = SessionTurnAccumulator()
        event = _make_token_event(prompt=1250, candidates=380, cached=200)
        a.add_event(event)
        assert a._input == 1050
        assert a._output == 380
        assert a._reasoning == 0

    def test_reasoning_tokens_counted(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=500, candidates=200, thoughts=100))
        assert a._reasoning == 100

    def test_multiple_events_accumulate(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=1250, candidates=380, cached=200))  # input=1050, output=380
        a.add_event(_make_token_event(prompt=500, candidates=100, cached=0))     # input=500, output=100
        assert a._input == 1550
        assert a._output == 480

    def test_missing_usage_metadata_no_raise(self) -> None:
        a = SessionTurnAccumulator()
        event = SimpleNamespace(usage_metadata=None, type=None, author=None, is_final_text=False, text="")
        a.add_event(event)  # must not raise
        assert a._input == 0
        assert a._output == 0


# ---------------------------------------------------------------------------
# Tool-call count
# ---------------------------------------------------------------------------


class TestToolCallCount:
    def test_tool_call_event_increments(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_tool_call_event())
        assert a.tool_call_count == 1

    def test_non_tool_call_does_not_increment(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=100, candidates=50))
        assert a.tool_call_count == 0

    def test_multiple_tool_calls(self) -> None:
        a = SessionTurnAccumulator()
        for _ in range(3):
            a.add_event(_make_tool_call_event())
        assert a.tool_call_count == 3


# ---------------------------------------------------------------------------
# Message count (AC-9)
# ---------------------------------------------------------------------------


class TestMessageCount:
    def test_user_event_increments(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_author_event("user"))
        assert a.message_count_delta == 1

    def test_model_event_increments(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_author_event("model"))
        assert a.message_count_delta == 1

    def test_system_event_does_not_increment(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_author_event("system"))
        assert a.message_count_delta == 0

    def test_tool_author_does_not_increment(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_author_event("tool"))
        assert a.message_count_delta == 0

    def test_mixed_sequence_counts_only_user_model(self) -> None:
        """user, model, system, tool, user, model — delta must be 4."""
        a = SessionTurnAccumulator()
        for author in ("user", "model", "system", "tool", "user", "model"):
            a.add_event(_make_author_event(author))
        assert a.message_count_delta == 4


# ---------------------------------------------------------------------------
# Compaction summary
# ---------------------------------------------------------------------------


class TestCompactionSummary:
    def test_compaction_event_sets_summary(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event(summary="A rich summary.", total_token_count=1000))
        assert a.latest_summary == "A rich summary."

    def test_compaction_event_sets_compaction_count_delta(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event())
        assert a.compaction_count_delta == 1

    def test_multiple_compactions_accumulate_count(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event(summary="s1", total_token_count=500))
        a.add_event(_make_compaction_event(summary="s2", total_token_count=400))
        assert a.compaction_count_delta == 2
        assert a.latest_summary == "s2"  # last one wins

    def test_non_compaction_does_not_set_summary(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=100, candidates=50))
        assert a.latest_summary is None


# ---------------------------------------------------------------------------
# Final-text
# ---------------------------------------------------------------------------


class TestFinalText:
    def test_final_text_event_stored(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_final_text_event("Hello world"))
        assert a.final_text == "Hello world"

    def test_last_final_text_wins(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_final_text_event("First"))
        a.add_event(_make_final_text_event("Second"))
        assert a.final_text == "Second"

    def test_non_final_text_event_does_not_set(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_author_event("model"))
        assert a.final_text == ""


# ---------------------------------------------------------------------------
# build_delta — normal (non-compaction) turn
# ---------------------------------------------------------------------------


class TestBuildDeltaNormal:
    def test_required_keys_present(self) -> None:
        a = SessionTurnAccumulator()
        delta = a.build_delta()
        for key in (
            "last_agent_stopped_at",
            "updated_at",
            "last_agent_message_at",
            "input_tokens_total",
            "output_tokens_total",
            "reasoning_tokens_total",
            "tool_call_count",
            "message_count",
            "last_message_preview",
            "current_context_tokens",
        ):
            assert key in delta, f"Missing key: {key}"

    def test_search_text_absent(self) -> None:
        """search_text is NOT produced by the accumulator — side-table service responsibility."""
        a = SessionTurnAccumulator()
        delta = a.build_delta()
        assert "search_text" not in delta

    def test_datetime_stamps_are_utc_and_recent(self) -> None:
        a = SessionTurnAccumulator()
        before = datetime.now(timezone.utc)
        delta = a.build_delta()
        after = datetime.now(timezone.utc)
        for key in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            stamp = delta[key]
            assert isinstance(stamp, datetime)
            assert stamp.tzinfo is not None
            assert before <= stamp <= after

    def test_counter_fields_are_increments(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=1250, candidates=380, cached=200))
        a.add_event(_make_tool_call_event())
        a.add_event(_make_author_event("user"))
        delta = a.build_delta()
        assert isinstance(delta["input_tokens_total"], Increment)
        assert isinstance(delta["output_tokens_total"], Increment)
        assert isinstance(delta["reasoning_tokens_total"], Increment)
        assert isinstance(delta["tool_call_count"], Increment)
        assert isinstance(delta["message_count"], Increment)

    def test_increment_values_correct(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=1250, candidates=380, cached=200))  # input=1050, output=380
        a.add_event(_make_tool_call_event())
        a.add_event(_make_author_event("user"))
        a.add_event(_make_author_event("model"))
        delta = a.build_delta()
        assert delta["input_tokens_total"].value == 1050
        assert delta["output_tokens_total"].value == 380
        assert delta["reasoning_tokens_total"].value == 0
        assert delta["tool_call_count"].value == 1
        assert delta["message_count"].value == 2

    def test_current_context_tokens_is_increment_on_normal_turn(self) -> None:
        """No compaction → current_context_tokens = Increment(turn_tokens)."""
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=1250, candidates=380, cached=200))  # input=1050, output=380
        delta = a.build_delta()
        cct = delta["current_context_tokens"]
        assert isinstance(cct, Increment)
        assert cct.value == 1050 + 380  # input + output

    def test_last_message_preview_truncated_to_160(self) -> None:
        long_text = "x" * 500
        a = SessionTurnAccumulator()
        a.add_event(_make_final_text_event(long_text))
        delta = a.build_delta()
        assert delta["last_message_preview"] == "x" * 160

    def test_last_message_preview_short_text_unchanged(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_final_text_event("Short text"))
        delta = a.build_delta()
        assert delta["last_message_preview"] == "Short text"

    def test_compaction_keys_absent_on_normal_turn(self) -> None:
        a = SessionTurnAccumulator()
        delta = a.build_delta()
        assert "latest_summary" not in delta
        assert "summary_updated_at" not in delta
        assert "compaction_count" not in delta

    def test_counter_values_stable_across_repeated_calls(self) -> None:
        """Counter Increment values are stable across repeated build_delta() calls.

        Note: each call produces a new dict with a fresh timestamp, so dicts are
        not identical objects. The one-shot contract (CH-13) must prevent double-
        application of Increments; this test only verifies that repeated reads
        return the same token values.
        """
        a = SessionTurnAccumulator()
        a.add_event(_make_token_event(prompt=100, candidates=50))
        d1 = a.build_delta()
        d2 = a.build_delta()
        assert d1["input_tokens_total"].value == d2["input_tokens_total"].value
        assert d1["output_tokens_total"].value == d2["output_tokens_total"].value


# ---------------------------------------------------------------------------
# build_delta — compaction turn (AC-10)
# ---------------------------------------------------------------------------


class TestBuildDeltaCompaction:
    def test_compaction_keys_present(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event(summary="Compact summary", total_token_count=800))
        delta = a.build_delta()
        assert "latest_summary" in delta
        assert "summary_updated_at" in delta
        assert "compaction_count" in delta

    def test_current_context_tokens_is_literal_int_on_compaction(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event(summary="s", total_token_count=800))
        delta = a.build_delta()
        cct = delta["current_context_tokens"]
        assert type(cct) is int, f"Expected plain int, got {type(cct)}"

    def test_current_context_tokens_value_equals_sum(self) -> None:
        """AC-10: sum of usage_metadata.total_token_count across retained window."""
        a = SessionTurnAccumulator()
        # Add some retained events before the compaction
        for _ in range(5):
            ev = SimpleNamespace(
                usage_metadata=SimpleNamespace(total_token_count=200),
                type=None,
                author=None,
                is_final_text=False,
                text="",
                content=None,
            )
            a.add_event(ev)
        compaction_ev = _make_compaction_event(summary="s", total_token_count=1200)
        a.add_event(compaction_ev)
        delta = a.build_delta()
        # buffer: 5 retained events (200 each) + compaction event (1200) = 6 items
        # sum = 5*200 + 1200 = 2200
        assert delta["current_context_tokens"] == 2200

    def test_compaction_count_is_increment(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event())
        delta = a.build_delta()
        assert isinstance(delta["compaction_count"], Increment)
        assert delta["compaction_count"].value == 1

    def test_latest_summary_in_delta(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_make_compaction_event(summary="My summary"))
        delta = a.build_delta()
        assert delta["latest_summary"] == "My summary"


# ---------------------------------------------------------------------------
# compute_post_compaction_window_tokens (standalone)
# ---------------------------------------------------------------------------


class TestComputePostCompactionWindowTokens:
    def test_canonical_fixture_returns_4400(self) -> None:
        """AC-10 canonical fixture: compaction=1200, 10 retained events."""
        compaction_ev = SimpleNamespace(usage_metadata=SimpleNamespace(total_token_count=1200))
        retained = [
            SimpleNamespace(usage_metadata=SimpleNamespace(total_token_count=t))
            for t in [800, 600, 500, 400, 300, 200, 100, 100, 100, 100]
        ]
        result = compute_post_compaction_window_tokens(compaction_ev, retained)
        assert result == 4400

    def test_empty_retained_window(self) -> None:
        compaction_ev = SimpleNamespace(usage_metadata=SimpleNamespace(total_token_count=500))
        assert compute_post_compaction_window_tokens(compaction_ev, []) == 500

    def test_missing_usage_metadata_contributes_zero(self) -> None:
        compaction_ev = SimpleNamespace(usage_metadata=None)
        retained = [SimpleNamespace(usage_metadata=None)]
        assert compute_post_compaction_window_tokens(compaction_ev, retained) == 0

    def test_partial_missing_usage_metadata(self) -> None:
        compaction_ev = SimpleNamespace(usage_metadata=SimpleNamespace(total_token_count=100))
        retained = [
            SimpleNamespace(usage_metadata=None),
            SimpleNamespace(usage_metadata=SimpleNamespace(total_token_count=200)),
        ]
        assert compute_post_compaction_window_tokens(compaction_ev, retained) == 300

    def test_missing_total_token_count_field(self) -> None:
        compaction_ev = SimpleNamespace(usage_metadata=SimpleNamespace())  # no total_token_count
        result = compute_post_compaction_window_tokens(compaction_ev, [])
        assert result == 0
