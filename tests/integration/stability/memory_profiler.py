"""RSS-based memory profiler for the Sprint 6 stability stories.

Used to satisfy ACs 6.14 (OTEL memory delta < 10%) and 6.21 (long-session
memory delta < 10%). Wraps a workload in a `MemoryProfiler()` context and
reports baseline / peak / final RSS plus a sampled time series.

Sampling runs on a daemon thread so it never blocks teardown. The sampler
is best-effort: if `psutil.Process(...)` raises (process gone, permission
error), the sampler exits silently rather than poison the workload.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from types import TracebackType

import psutil


@dataclass
class MemoryProfile:
    baseline_rss: int = 0
    samples: list[tuple[float, int]] = field(default_factory=list)
    final_rss: int = 0
    peak_rss: int = 0
    delta_pct: float = 0.0


class MemoryProfiler:
    """Context manager that samples RSS for `target_pid` until exit."""

    def __init__(
        self,
        sample_interval_s: float = 5.0,
        target_pid: int | None = None,
    ) -> None:
        if sample_interval_s <= 0:
            raise ValueError("sample_interval_s must be positive")
        self.sample_interval_s = sample_interval_s
        self._target_pid = target_pid or psutil.Process().pid
        self._proc: psutil.Process | None = None
        self._stop = threading.Event()
        self._sampler: threading.Thread | None = None
        self._t0: float = 0.0
        self._profile = MemoryProfile()

    def __enter__(self) -> MemoryProfiler:
        self._proc = psutil.Process(self._target_pid)
        self._t0 = time.monotonic()
        baseline = self._proc.memory_info().rss
        self._profile = MemoryProfile(
            baseline_rss=baseline,
            samples=[(0.0, baseline)],
            peak_rss=baseline,
        )
        self._sampler = threading.Thread(
            target=self._run_sampler, name="MemoryProfilerSampler", daemon=True
        )
        self._sampler.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        if self._sampler is not None:
            # Bound the wait so a stuck sampler doesn't block teardown.
            self._sampler.join(timeout=self.sample_interval_s + 1.0)

        try:
            assert self._proc is not None
            final = self._proc.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, AssertionError):
            # Process gone — fall back to last sample if any.
            final = (
                self._profile.samples[-1][1]
                if self._profile.samples
                else self._profile.baseline_rss
            )

        self._profile.final_rss = final
        self._profile.peak_rss = max(self._profile.peak_rss, final)
        baseline = self._profile.baseline_rss
        self._profile.delta_pct = (
            ((final - baseline) / baseline * 100.0) if baseline > 0 else 0.0
        )

    def result(self) -> MemoryProfile:
        return self._profile

    def _run_sampler(self) -> None:
        while not self._stop.wait(self.sample_interval_s):
            try:
                assert self._proc is not None
                rss = self._proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, AssertionError):
                return
            ts = time.monotonic() - self._t0
            self._profile.samples.append((ts, rss))
            if rss > self._profile.peak_rss:
                self._profile.peak_rss = rss
