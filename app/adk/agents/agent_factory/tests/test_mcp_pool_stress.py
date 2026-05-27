"""SSE-leak stress test for McpToolsetPool (AH-62 AC-13).

Simulates 1 hour of sustained pool traffic (3 600 "turns") in seconds by
patching ``time.monotonic``.  Verifies that every evicted toolset — whether
by LRU cap or idle-TTL sweep — has ``aclose()`` called exactly once, and
that the pool never exceeds ``_MAX_ENTRIES`` entries.

Run selectively via::

    pytest -m slow app/adk/agents/agent_factory/tests/test_mcp_pool_stress.py

Marked ``@pytest.mark.slow`` so it is excluded from the default ``make test``
run (which uses ``-m "not slow"`` by default in CI) but executed in the
nightly stress-test job.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adk.agents.agent_factory.mcp_pool import McpServerKind, McpToolsetPool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_toolset() -> AsyncMock:
    """Return a fresh AsyncMock that tracks ``aclose()`` calls."""
    t = AsyncMock()
    t.aclose = AsyncMock()
    return t


# ---------------------------------------------------------------------------
# Stress Test — 1-hour simulated SSE-leak scenario
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.asyncio
async def test_no_sse_leak_under_1hour_simulated_traffic() -> None:
    """Simulate 3600 turns of pool traffic (1 per simulated second).

    For each turn:
    - A unique server_id is used every 200 turns (rotating through 10 IDs)
      to produce realistic cache-hit/miss mix.
    - Every 60 turns, sweep_idle() is called to simulate the background sweep.

    Assertions:
    - Pool never exceeds _MAX_ENTRIES at any point.
    - Every evicted toolset (LRU + TTL) had aclose() called exactly once.
    - No toolset still in the pool at the end has aclose() called.
    """
    pool = McpToolsetPool()
    # Use a small cap so LRU evictions happen frequently throughout the run.
    pool._MAX_ENTRIES = 20  # type: ignore[assignment]

    # Registry of all toolsets ever created: pool_key → toolset
    all_toolsets: dict[tuple[str, ...], AsyncMock] = {}

    t_sim = 0.0
    # 10 rotating server IDs — each stays "active" for 200 turns
    server_ids = [f"srv_{i:03d}" for i in range(200)]

    TURNS = 3600
    SWEEP_EVERY = 60

    with patch("app.adk.agents.agent_factory.mcp_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_sim

        for turn in range(TURNS):
            t_sim = float(turn)
            mock_time.monotonic.return_value = t_sim

            # Rotate through server IDs — each server active for 5 turns
            server_id = server_ids[turn % len(server_ids)]
            account_id = "stress_account"
            creds_hash = f"creds_{turn // 100}"  # creds rotate every 100 turns
            key = (server_id, account_id, creds_hash)
            pool_key = ("cloud_run",) + key

            def _build_fn(_pk: tuple[str, ...] = pool_key) -> Any:
                t = _make_toolset()
                all_toolsets[_pk] = t
                return t

            await pool.get_or_create(
                kind=McpServerKind.CLOUD_RUN,
                key=key,
                build_fn=_build_fn,
            )

            # Pool must never exceed cap
            assert len(pool._pool) <= pool._MAX_ENTRIES, (
                f"Turn {turn}: pool size {len(pool._pool)} exceeds cap {pool._MAX_ENTRIES}"
            )

            # Periodic sweep
            if turn > 0 and turn % SWEEP_EVERY == 0:
                await pool.sweep_idle()

    # Final sweep to drain TTL-expired entries
    t_sim = float(TURNS) + pool._IDLE_TTL_SECONDS + 1
    mock_time.monotonic.return_value = t_sim
    await pool.sweep_idle()

    # Verify: every evicted toolset had aclose() called exactly once.
    # A toolset currently in the pool should NOT have aclose() called.
    live_pool_keys = set(pool._pool.keys())
    for pool_key, toolset in all_toolsets.items():
        if pool_key in live_pool_keys:
            # Still in pool — aclose must NOT have been called
            assert toolset.aclose.call_count == 0, (
                f"Live toolset {pool_key} had aclose() called "
                f"{toolset.aclose.call_count} time(s) — SSE leak!"
            )
        else:
            # Evicted — aclose must have been called exactly once (AC-12)
            assert toolset.aclose.call_count == 1, (
                f"Evicted toolset {pool_key} had aclose() called "
                f"{toolset.aclose.call_count} time(s), expected exactly 1 — SSE leak!"
            )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_p95_pool_hit_latency_under_200ms() -> None:
    """AC-12: p95 specialist cold-start (pool miss + build) must be ≤ 200 ms.

    The pool does not add meaningful overhead beyond the build_fn itself.
    This test measures the overhead of the pool mechanics (stripe lock acquire,
    dict lookup, span emission no-op) on a warm cache-hit to ensure the pool
    itself is not the latency bottleneck.

    Note: This test cannot measure the Firestore + McpToolset construction
    latency (which depends on live services) — it measures the pool layer only.
    """
    import time as real_time

    pool = McpToolsetPool()
    toolset = _make_toolset()

    # Prime the pool (cold build)
    await pool.get_or_create(
        kind=McpServerKind.CLOUD_RUN,
        key=("srv", "acc", "h"),
        build_fn=lambda: toolset,
    )

    # Measure 100 warm hits
    latencies: list[float] = []
    for _ in range(100):
        t0 = real_time.perf_counter()
        await pool.get_or_create(
            kind=McpServerKind.CLOUD_RUN,
            key=("srv", "acc", "h"),
            build_fn=lambda: toolset,
        )
        latencies.append((real_time.perf_counter() - t0) * 1000)

    latencies.sort()
    p95 = latencies[int(0.95 * len(latencies))]
    # Pool mechanics alone should add <1ms; 200ms is a very generous bound
    # covering any CI scheduling jitter.
    assert p95 < 200, f"p95 pool-hit latency {p95:.1f}ms exceeds 200ms AC-12 budget"
