"""Tests for the memory profiler."""

from __future__ import annotations

import time

import pytest

from tests.integration.stability.memory_profiler import MemoryProfiler


def test_profiler_captures_baseline_and_final() -> None:
    with MemoryProfiler(sample_interval_s=0.05) as p:
        # Allocate a chunk to nudge RSS up a touch.
        _bytes = bytearray(2 * 1024 * 1024)
        time.sleep(0.15)
        del _bytes
    profile = p.result()
    assert profile.baseline_rss > 0
    assert profile.final_rss > 0
    assert profile.peak_rss >= profile.baseline_rss


def test_sampler_records_at_least_one_sample() -> None:
    with MemoryProfiler(sample_interval_s=0.05):
        time.sleep(0.25)
    # The baseline counts as the first sample, so >= 2 means the daemon ticked.
    # We re-enter to exercise this cleanly:
    p2 = MemoryProfiler(sample_interval_s=0.05)
    with p2:
        time.sleep(0.25)
    assert len(p2.result().samples) >= 2


def test_delta_pct_is_bounded() -> None:
    with MemoryProfiler(sample_interval_s=0.05) as p:
        _ = bytearray(1024 * 1024)
        time.sleep(0.1)
    profile = p.result()
    # Within a tiny test we never blow past 100%.
    assert -50.0 < profile.delta_pct < 100.0


def test_invalid_interval_rejected() -> None:
    with pytest.raises(ValueError):
        MemoryProfiler(sample_interval_s=0)
