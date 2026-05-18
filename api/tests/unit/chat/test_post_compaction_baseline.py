"""Dedicated test for the post-compaction context baseline — AC-10.

CH-PRD-01 §7 AC-10: Unit test constructs a fake compaction event + active
window; asserts `current_context_tokens` equals the SUM of
`usage_metadata.total_token_count` across the retained events — NOT zero.

Two test paths:
  (a) Call compute_post_compaction_window_tokens() directly.
  (b) Feed events into SessionTurnAccumulator, assert build_delta() result.

Edge cases: empty window, missing usage_metadata, non-compaction turn.

References: CH-PRD-01 §7 AC-10 (\"NOT zero\"), §5.2 (post-compaction baseline).
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from google.cloud.firestore_v1.transforms import Increment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat.accumulator import (
    SessionTurnAccumulator,
    compute_post_compaction_window_tokens,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COMPACTION_TOTAL = 1200
_RETAINED_TOTALS = [800, 600, 500, 400, 300, 200, 100, 100, 100, 100]
_CANONICAL_SUM = _COMPACTION_TOTAL + sum(_RETAINED_TOTALS)  # 4400


def _compaction_event(total_token_count: int = _COMPACTION_TOTAL) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(total_token_count=total_token_count),
        type="compaction_summary",
        author=None,
        is_final_text=False,
        text="",
        content="summary text",
    )


def _retained_event(total_token_count: int) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(total_token_count=total_token_count),
        type=None,
        author=None,
        is_final_text=False,
        text="",
        content=None,
    )


def _make_canonical_retained() -> list[SimpleNamespace]:
    return [_retained_event(t) for t in _RETAINED_TOTALS]


# ---------------------------------------------------------------------------
# (a) compute_post_compaction_window_tokens — direct tests
# ---------------------------------------------------------------------------


class TestComputePostCompactionWindowTokensDirectly:
    def test_canonical_fixture_4400(self) -> None:
        """AC-10 canonical fixture: compaction=1200, 10 retained, sum=4400."""
        result = compute_post_compaction_window_tokens(
            _compaction_event(), _make_canonical_retained()
        )
        assert result == _CANONICAL_SUM

    def test_result_not_zero_when_there_are_tokens(self) -> None:
        """Explicitly assert NOT zero — the AC-10 rule."""
        result = compute_post_compaction_window_tokens(_compaction_event(500), [])
        assert result != 0
        assert result == 500

    def test_empty_retained_window_equals_compaction_only(self) -> None:
        result = compute_post_compaction_window_tokens(_compaction_event(300), [])
        assert result == 300

    def test_missing_compaction_usage_metadata(self) -> None:
        ev = SimpleNamespace(usage_metadata=None)
        retained = [_retained_event(200)]
        assert compute_post_compaction_window_tokens(ev, retained) == 200

    def test_missing_retained_usage_metadata(self) -> None:
        retained = [SimpleNamespace(usage_metadata=None), _retained_event(150)]
        result = compute_post_compaction_window_tokens(_compaction_event(100), retained)
        assert result == 250  # 100 + 0 + 150

    def test_all_missing_usage_metadata_returns_zero(self) -> None:
        ev = SimpleNamespace(usage_metadata=None)
        retained = [SimpleNamespace(usage_metadata=None)]
        assert compute_post_compaction_window_tokens(ev, retained) == 0


# ---------------------------------------------------------------------------
# (b) End-to-end accumulator tests
# ---------------------------------------------------------------------------


class TestAccumulatorPostCompactionBaseline:
    def test_current_context_tokens_literal_int_not_increment(self) -> None:
        """AC-10: current_context_tokens after compaction must be a plain int."""
        a = SessionTurnAccumulator()
        for ev in _make_canonical_retained():
            a.add_event(ev)
        a.add_event(_compaction_event())
        delta = a.build_delta()
        cct = delta["current_context_tokens"]
        assert type(cct) is int, f"Expected plain int, got {type(cct)}"

    def test_current_context_tokens_equals_sum_not_zero(self) -> None:
        """AC-10 end-to-end: accumulator produces the correct sum."""
        a = SessionTurnAccumulator()
        for ev in _make_canonical_retained():
            a.add_event(ev)
        a.add_event(_compaction_event())
        delta = a.build_delta()
        # The buffer holds at most 11 events (maxlen=11).
        # We added 10 retained + 1 compaction = 11 events — all in buffer.
        # Sum = 1200 + 4 * (800+600+500+400+300+200+100+100+100+100)?
        # Wait — the buffer contains the 10 retained events (each used in
        # compute_post_compaction_window_tokens) plus the compaction event.
        # canonical sum = 4400.
        assert delta["current_context_tokens"] == _CANONICAL_SUM

    def test_normal_turn_current_context_tokens_is_increment(self) -> None:
        """Negative test: non-compaction turn produces Increment, not literal."""
        a = SessionTurnAccumulator()
        ev = SimpleNamespace(
            usage_metadata=SimpleNamespace(
                prompt_token_count=500,
                candidates_token_count=200,
                thoughts_token_count=0,
                cached_content_token_count=0,
            ),
            type=None,
            author=None,
            is_final_text=False,
            text="",
            content=None,
        )
        a.add_event(ev)
        delta = a.build_delta()
        cct = delta["current_context_tokens"]
        assert isinstance(cct, Increment)
        assert cct.value == 700  # input(500) + output(200)

    def test_no_compaction_no_literal_in_delta(self) -> None:
        """Verify compaction-specific keys are absent on a normal turn."""
        a = SessionTurnAccumulator()
        delta = a.build_delta()
        assert "latest_summary" not in delta
        assert "summary_updated_at" not in delta
        assert "compaction_count" not in delta

    def test_buffer_maxlen_does_not_cause_incorrect_sum(self) -> None:
        """More than 11 events — buffer evicts oldest; sum uses only buffered events."""
        a = SessionTurnAccumulator()
        # Add 15 events of 100 tokens each before compaction
        for _ in range(15):
            a.add_event(_retained_event(100))
        # Now add compaction event (200 tokens)
        a.add_event(_compaction_event(200))
        delta = a.build_delta()
        # buffer maxlen=11: after 15 retained events, the buffer has the last 10 retained + compaction
        # on add_event(compaction_event), buffer is:
        #   [retained(100)] * 10 + [compaction(200)] = 11 items total
        # compute_post_compaction: compaction_ev (200) + retained (10 * 100) = 1200
        cct = delta["current_context_tokens"]
        assert type(cct) is int
        assert cct == 200 + 10 * 100  # 1200

    def test_single_compaction_event_no_retained(self) -> None:
        """Compaction is the very first event — baseline equals compaction total_token_count."""
        a = SessionTurnAccumulator()
        a.add_event(_compaction_event(total_token_count=900))
        delta = a.build_delta()
        assert delta["current_context_tokens"] == 900
