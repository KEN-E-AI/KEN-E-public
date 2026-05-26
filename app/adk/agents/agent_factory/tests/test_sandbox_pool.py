"""Unit tests for app.adk.agents.agent_factory.sandbox_pool.SandboxPool.

No live GCP or ADK install required — ``SandboxPool._construct`` is stubbed in
every test that exercises the pool internals.  ``time.monotonic`` is patched in
TTL-sensitive tests via ``unittest.mock.patch``.

Coverage map
------------
* AC-11 — SandboxPool reuse: same key returns same executor; ``_construct``
  called exactly once (tests 2, 3, 4).
* AC-12 — SandboxPool eviction cleanup: LRU + TTL eviction paths call
  ``aclose()`` exactly once; ``aclose()`` raising is caught + pool integrity
  preserved (tests 5, 6, 7, 8).
* AC-14 — SandboxPool concurrent safety: same-key single-flight via
  ``asyncio.gather`` x 10; different-key calls do not serialise (tests 9, 10).
* Edge cases: unknown-key evict no-op, start/stop lifecycle, start idempotency,
  resource name format (tests 11-14).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adk.agents.agent_factory.sandbox_pool import (
    SandboxPool,
    _sandbox_resource_name,
)

# ---------------------------------------------------------------------------
# Fake executor factory
# ---------------------------------------------------------------------------


def _make_executor() -> AsyncMock:
    """Return a fresh AsyncMock that tracks ``aclose()`` calls."""
    mock = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# Test 1 — module imports work without ADK installed
# ---------------------------------------------------------------------------


def test_module_imports() -> None:
    """Importing the module and class succeeds without a live ADK install."""
    from app.adk.agents.agent_factory.sandbox_pool import SandboxPool as _SP

    assert _SP._MAX_ENTRIES == 64
    assert _SP._IDLE_TTL_SECONDS == 900
    assert _SP._SWEEP_INTERVAL_SECONDS == 60


# ---------------------------------------------------------------------------
# Test 2 — idempotency: same key → same instance, _construct called once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_same_key() -> None:
    """get_or_create twice for the same key returns the same executor by identity."""
    pool = SandboxPool()
    executor = _make_executor()
    call_count = 0

    async def _fake_construct(**_: Any) -> Any:
        nonlocal call_count
        call_count += 1
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    first = await pool.get_or_create(account_id="acc", config_id="cfg")
    second = await pool.get_or_create(account_id="acc", config_id="cfg")

    assert first is second  # AC-11 identity
    assert call_count == 1  # AC-11 single construction


# ---------------------------------------------------------------------------
# Test 3 — different keys produce different instances
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_different_keys() -> None:
    """get_or_create for different keys returns different executor instances."""
    pool = SandboxPool()
    executors: list[AsyncMock] = []
    call_count = 0

    async def _fake_construct(**_: Any) -> Any:
        nonlocal call_count
        call_count += 1
        ex = _make_executor()
        executors.append(ex)
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    a = await pool.get_or_create(account_id="acc", config_id="x")
    b = await pool.get_or_create(account_id="acc", config_id="y")

    assert a is not b
    assert call_count == 2


# ---------------------------------------------------------------------------
# Test 4 — LRU bump on hit: re-accessed entry survives the next eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_bump_on_hit() -> None:
    """With _MAX_ENTRIES=4, re-accessing the oldest entry protects it from
    the next over-cap eviction; the second-oldest is evicted instead."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 4  # type: ignore[assignment]

    executors: dict[str, AsyncMock] = {}

    async def _fake_construct(*, account_id: str, config_id: str) -> Any:
        ex = _make_executor()
        executors[config_id] = ex
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    # Fill all 4 slots: k0 (oldest), k1, k2, k3 (newest)
    for i in range(4):
        await pool.get_or_create(account_id="acc", config_id=f"k{i}")

    # Re-access k0 — it should now be MRU
    await pool.get_or_create(account_id="acc", config_id="k0")

    # Insert k4 → over cap; k1 should be evicted (now the LRU)
    await pool.get_or_create(account_id="acc", config_id="k4")

    remaining = list(pool._pool.keys())
    assert ("acc", "k1") not in remaining, "k1 should have been evicted (LRU)"
    assert ("acc", "k0") in remaining, "k0 should still be present (bumped to MRU)"


# ---------------------------------------------------------------------------
# Test 5 — LRU eviction calls aclose exactly once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lru_eviction_calls_aclose() -> None:
    """Inserting the 5th key with _MAX_ENTRIES=4 evicts the LRU and calls aclose."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 4  # type: ignore[assignment]

    executors: dict[str, AsyncMock] = {}

    async def _fake_construct(*, account_id: str, config_id: str) -> Any:
        ex = _make_executor()
        executors[config_id] = ex
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    for i in range(4):
        await pool.get_or_create(account_id="acc", config_id=f"k{i}")

    # k0 is the LRU; inserting k4 should evict it
    await pool.get_or_create(account_id="acc", config_id="k4")

    executors["k0"].aclose.assert_called_once()  # AC-12


# ---------------------------------------------------------------------------
# Test 6 — TTL sweep evicts old entries and calls aclose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweep_idle_ttl() -> None:
    """sweep_idle() evicts all entries whose last_used is before the TTL cutoff."""
    pool = SandboxPool()

    executors: list[AsyncMock] = []

    async def _fake_construct(**_: Any) -> Any:
        ex = _make_executor()
        executors.append(ex)
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_start = 1_000.0

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_start

        # Populate 3 entries at t=1000
        for i in range(3):
            await pool.get_or_create(account_id="acc", config_id=f"k{i}")

        # Advance time past TTL
        mock_time.monotonic.return_value = t_start + pool._IDLE_TTL_SECONDS + 1

        await pool.sweep_idle()

    assert len(pool._pool) == 0  # all swept
    for ex in executors:
        ex.aclose.assert_called_once()  # AC-12 TTL path


# ---------------------------------------------------------------------------
# Test 7 — partial sweep: only stale entries removed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweep_idle_partial() -> None:
    """sweep_idle() removes only entries older than the TTL, leaving fresh ones."""
    pool = SandboxPool()
    executors: dict[str, AsyncMock] = {}

    async def _fake_construct(*, account_id: str, config_id: str) -> Any:
        ex = _make_executor()
        executors[config_id] = ex
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        t_base = 1_000.0
        # Populate 2 stale entries at t=1000
        mock_time.monotonic.return_value = t_base
        await pool.get_or_create(account_id="acc", config_id="stale1")
        await pool.get_or_create(account_id="acc", config_id="stale2")

        # Populate 1 fresh entry at t=1000+TTL (right on the boundary — not stale)
        fresh_time = t_base + pool._IDLE_TTL_SECONDS
        mock_time.monotonic.return_value = fresh_time
        await pool.get_or_create(account_id="acc", config_id="fresh")

        # Sweep at t=1000+TTL+1 → stale entries cross cutoff; fresh does not
        mock_time.monotonic.return_value = fresh_time + 1
        await pool.sweep_idle()

    assert ("acc", "fresh") in pool._pool
    assert ("acc", "stale1") not in pool._pool
    assert ("acc", "stale2") not in pool._pool
    executors["stale1"].aclose.assert_called_once()
    executors["stale2"].aclose.assert_called_once()
    executors["fresh"].aclose.assert_not_called()


# ---------------------------------------------------------------------------
# Test 8 — aclose() raising is tolerated; entry still removed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aclose_raise_tolerated() -> None:
    """If aclose() raises, the entry is still removed and pool integrity is preserved."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 1  # type: ignore[assignment]

    boom_executor = _make_executor()
    boom_executor.aclose.side_effect = RuntimeError("sandbox exploded")

    async def _fake_construct(**_: Any) -> Any:
        return boom_executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    # Fill the single slot
    await pool.get_or_create(account_id="acc", config_id="boom")
    assert len(pool._pool) == 1

    # Insert a second key → triggers LRU eviction of "boom" whose aclose raises
    second_executor = _make_executor()

    async def _fake_construct2(*, account_id: str, config_id: str) -> Any:
        return second_executor

    pool._construct = _fake_construct2  # type: ignore[method-assign]

    await pool.get_or_create(account_id="acc", config_id="safe")

    # The erroring entry must be removed and the pool must still be usable
    assert ("acc", "boom") not in pool._pool  # AC-12 entry removed
    assert len(pool._pool) == 1  # pool is consistent
    boom_executor.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# Test 9 — concurrent same-key single-flight (AC-14)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_same_key_single_flight() -> None:
    """10 concurrent get_or_create calls for the same key all get the same executor."""
    pool = SandboxPool()
    construct_count = 0

    async def _fake_construct(**_: Any) -> Any:
        nonlocal construct_count
        construct_count += 1
        await asyncio.sleep(0.05)  # simulate slow constructor
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    results = await asyncio.gather(
        *[pool.get_or_create(account_id="acc", config_id="cfg") for _ in range(10)]
    )

    # All 10 results must be the same instance
    assert all(r is results[0] for r in results), "All results should be identical"
    assert construct_count == 1, "_construct should be called exactly once"  # AC-14


# ---------------------------------------------------------------------------
# Test 10 — concurrent different-key calls do not serialise (AC-14)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_different_keys_parallel() -> None:
    """Two get_or_create calls for different keys run in parallel, not serially."""
    pool = SandboxPool()
    delay = 0.05

    async def _fake_construct(**_: Any) -> Any:
        await asyncio.sleep(delay)
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    start = asyncio.get_event_loop().time()
    await asyncio.gather(
        pool.get_or_create(account_id="acc", config_id="x"),
        pool.get_or_create(account_id="acc", config_id="y"),
    )
    elapsed = asyncio.get_event_loop().time() - start

    # If parallel: ~delay; if serial: ~2*delay. Allow 1.8x as the threshold.
    assert elapsed < 1.8 * delay, (
        f"Parallel construct took {elapsed:.3f}s - expected < {1.8 * delay:.3f}s"
    )


# ---------------------------------------------------------------------------
# Test 11 — evict unknown key is a no-op
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evict_unknown_key_noop() -> None:
    """Calling evict() on a key not in the pool does not raise."""
    pool = SandboxPool()
    await pool.evict(("nonexistent", "key"))  # must not raise


# ---------------------------------------------------------------------------
# Test 12 — start / stop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_stop_lifecycle() -> None:
    """start() arms a sweep task; stop() cancels it cleanly."""
    pool = SandboxPool()
    pool.start()
    assert pool._sweep_task is not None
    assert not pool._sweep_task.done()

    await pool.stop()
    assert pool._sweep_task is None


# ---------------------------------------------------------------------------
# Test 13 — start is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_idempotent() -> None:
    """Calling start() twice does not spawn a second task."""
    pool = SandboxPool()
    pool.start()
    task_first = pool._sweep_task

    pool.start()  # second call
    assert pool._sweep_task is task_first  # same task object

    await pool.stop()


# ---------------------------------------------------------------------------
# Test 14 — _sandbox_resource_name format
# ---------------------------------------------------------------------------


def test_sandbox_resource_name_format() -> None:
    """_sandbox_resource_name returns the expected GCP resource-name string."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_CLOUD_PROJECT_ID": "test-project",
            "VERTEX_AI_LOCATION": "europe-west1",
        },
    ):
        name = _sandbox_resource_name("acc_123", "cfg_xyz")

    assert name == (
        "projects/test-project/locations/europe-west1/sandboxes/acc_123/cfg_xyz"
    )
