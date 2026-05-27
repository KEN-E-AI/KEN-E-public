"""Unit tests for derive_is_agent_running (CH-PRD-01 §7.7 AC-7).

Table-driven coverage of all 6 timestamp states: never-started, running-fresh,
running-stuck, stopped-after-start, stopped-at-eq-started,
running-fresh-after-prior-stop.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat.side_table import STUCK_THRESHOLD, derive_is_agent_running

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "started_at, stopped_at, now_offset, expected",
    [
        # never-started
        pytest.param(None, None, timedelta(minutes=1), False, id="never_started"),
        # running-fresh: started, no stop, within threshold
        pytest.param(_T0, None, timedelta(minutes=1), True, id="running_fresh"),
        # running-stuck: started, no stop, beyond threshold
        pytest.param(_T0, None, timedelta(minutes=11), False, id="running_stuck"),
        # stopped normally (stopped_at > started_at)
        pytest.param(
            _T0,
            _T0 + timedelta(minutes=5),
            timedelta(minutes=6),
            False,
            id="stopped_after_start",
        ),
        # stopped_at == started_at (edge: stopped_at >= started_at)
        pytest.param(_T0, _T0, timedelta(minutes=1), False, id="stopped_at_eq_started"),
        # running fresh after a prior turn's stop (started_at > stopped_at)
        pytest.param(
            _T0,
            _T0 - timedelta(minutes=1),
            timedelta(minutes=1),
            True,
            id="running_fresh_after_prior_stop",
        ),
    ],
)
def test_derive_is_agent_running_states(
    started_at: datetime | None,
    stopped_at: datetime | None,
    now_offset: timedelta,
    expected: bool,
) -> None:
    now = _T0 + now_offset
    assert derive_is_agent_running(started_at, stopped_at, now=now) is expected


def test_custom_threshold_overrides_default() -> None:
    """Custom threshold of 1 minute causes a 2-minute-old turn to appear stuck."""
    assert (
        derive_is_agent_running(
            _T0,
            None,
            now=_T0 + timedelta(minutes=2),
            threshold=timedelta(minutes=1),
        )
        is False
    )


def test_default_now_does_not_raise() -> None:
    """Calling without explicit now uses datetime.now(utc) and returns a bool."""
    result = derive_is_agent_running(_T0 - timedelta(days=1), None)
    assert isinstance(result, bool)
    assert result is False  # a 1-day-old turn is stuck


def test_stuck_threshold_constant() -> None:
    """STUCK_THRESHOLD is exactly 10 minutes per PRD §7.7."""
    assert STUCK_THRESHOLD == timedelta(minutes=10)
