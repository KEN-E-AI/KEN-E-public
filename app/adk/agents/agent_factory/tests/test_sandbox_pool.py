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
  resource name format (tests 11-14, 15, 16).
* AC-8 — Weave span content (tests 17-22): cache_hit, pool_size_after,
  reason correctness for each eviction path; no-op evict still emits a span.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adk.agents.agent_factory.sandbox_pool import (
    SandboxPool,
    _get_vertexai_client,
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
    # This test only measures stripe-lock-induced serialisation.  Disable
    # _clear_tmp explicitly so its logger.warning() guard path (active for Mock
    # executors when _CLEAR_TMP_ON_REUSE=True, the post-SK-35 class default)
    # does not contribute to the timing budget — keeps the 1.8x threshold
    # stable on loaded test runners.
    pool._CLEAR_TMP_ON_REUSE = False
    delay = 0.05

    async def _fake_construct(**_: Any) -> Any:
        await asyncio.sleep(delay)
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    loop = asyncio.get_running_loop()
    start = loop.time()
    await asyncio.gather(
        pool.get_or_create(account_id="acc", config_id="x"),
        pool.get_or_create(account_id="acc", config_id="y"),
    )
    elapsed = loop.time() - start

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


# ---------------------------------------------------------------------------
# Test 15 — _sandbox_resource_name rejects slash in account_id / config_id
# ---------------------------------------------------------------------------


def test_sandbox_resource_name_rejects_slash() -> None:
    """_sandbox_resource_name raises ValueError if either ID contains '/'."""
    with pytest.raises(ValueError, match="must not contain '/'"):
        _sandbox_resource_name("acc/x", "cfg")

    with pytest.raises(ValueError, match="must not contain '/'"):
        _sandbox_resource_name("acc", "cfg/y")


# ---------------------------------------------------------------------------
# Test 16 — stale_before guard skips entries refreshed between snapshot and lock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_before_guard_skips_refreshed_entry() -> None:
    """evict(..., stale_before=cutoff) skips an entry whose last_used was
    updated after the sweep snapshot was taken — the TOCTOU guard."""
    pool = SandboxPool()
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_stale = 1_000.0

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_stale
        await pool.get_or_create(account_id="acc", config_id="cfg")

    key = ("acc", "cfg")

    # Simulate a concurrent hit that refreshed last_used after the snapshot
    t_fresh = t_stale + pool._IDLE_TTL_SECONDS + 10
    pool._pool[key] = (executor, t_fresh, 0, False)

    # The cutoff was computed before the refresh, so the key appeared stale then
    cutoff = t_stale + pool._IDLE_TTL_SECONDS + 1

    await pool.evict(key, stale_before=cutoff)

    # Entry must NOT have been removed — it was refreshed past the cutoff
    assert key in pool._pool, "Refreshed entry should not be evicted"
    executor.aclose.assert_not_called()


# ===========================================================================
# AC-8 — Weave span-content assertions (tests 17-22)
#
# ``emit_sandbox_pool_span`` is patched to a recording async context manager so
# tests can inspect (name, attrs) tuples without requiring a live Weave install.
# ===========================================================================

_SPAN_PATH = "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span"


def _make_span_recorder() -> tuple[list[tuple[str, dict]], object]:
    """Return (recorded_spans list, AsyncContextManager patch target).

    Each emitted span is appended as ``(name, attrs)`` to *recorded_spans*.
    """
    recorded: list[tuple[str, dict]] = []

    import contextlib

    @contextlib.asynccontextmanager
    async def _recording_span(name: str, attrs: dict) -> Any:
        recorded.append((name, dict(attrs)))
        yield

    return recorded, _recording_span


# ---------------------------------------------------------------------------
# Test 17 — cache miss emits sandbox_pool.get with cache_hit=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_get_cache_miss() -> None:
    """A cache miss emits sandbox_pool.get with cache_hit=False and pool_size_after=1."""
    pool = SandboxPool()
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        await pool.get_or_create(account_id="acc", config_id="cfg")

    get_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.get"]
    assert len(get_spans) == 1
    _, attrs = get_spans[0]
    assert attrs["account_id"] == "acc"
    assert attrs["config_id"] == "cfg"
    assert attrs["cache_hit"] is False
    assert attrs["pool_size_after"] == 1


# ---------------------------------------------------------------------------
# Test 18 — cache hit emits sandbox_pool.get with cache_hit=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_get_cache_hit() -> None:
    """A cache hit emits sandbox_pool.get with cache_hit=True."""
    pool = SandboxPool()
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    # Prime the pool with one call (span recorded but ignored)
    _recorded_first, pt_first = _make_span_recorder()
    with patch(_SPAN_PATH, pt_first):
        await pool.get_or_create(account_id="acc", config_id="cfg")

    # Second call — should be a cache hit
    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        await pool.get_or_create(account_id="acc", config_id="cfg")

    get_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.get"]
    assert len(get_spans) == 1
    _, attrs = get_spans[0]
    assert attrs["cache_hit"] is True
    assert attrs["pool_size_after"] == 1


# ---------------------------------------------------------------------------
# Test 19 — LRU-triggered eviction emits sandbox_pool.evict with reason="lru"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_evict_lru_reason() -> None:
    """LRU eviction (via _evict_if_over_cap) emits sandbox_pool.evict with reason='lru'."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 1  # type: ignore[assignment]

    call_n = 0

    async def _fake_construct(*, account_id: str, config_id: str) -> Any:
        nonlocal call_n
        call_n += 1
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        await pool.get_or_create(account_id="acc", config_id="k0")
        await pool.get_or_create(account_id="acc", config_id="k1")  # triggers LRU evict

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) >= 1
    lru_spans = [(n, a) for n, a in evict_spans if a["reason"] == "lru"]
    assert lru_spans, "Expected at least one sandbox_pool.evict span with reason='lru'"


# ---------------------------------------------------------------------------
# Test 20 — TTL sweep emits sandbox_pool.evict with reason="ttl"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_evict_ttl_reason() -> None:
    """TTL sweep (via sweep_idle) emits sandbox_pool.evict with reason='ttl'."""
    pool = SandboxPool()
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_start = 1_000.0
    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_start
        _recorded_first, pt_first = _make_span_recorder()
        with patch(_SPAN_PATH, pt_first):
            await pool.get_or_create(account_id="acc", config_id="cfg")

        mock_time.monotonic.return_value = t_start + pool._IDLE_TTL_SECONDS + 1

        recorded, patch_target = _make_span_recorder()
        with patch(_SPAN_PATH, patch_target):
            await pool.sweep_idle()

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) == 1
    _, attrs = evict_spans[0]
    assert attrs["reason"] == "ttl"


# ---------------------------------------------------------------------------
# Test 21 — direct evict() call uses reason="manual" by default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_evict_manual_reason() -> None:
    """Direct pool.evict(key) emits sandbox_pool.evict with reason='manual'."""
    pool = SandboxPool()
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    _recorded_first, pt_first = _make_span_recorder()
    with patch(_SPAN_PATH, pt_first):
        await pool.get_or_create(account_id="acc", config_id="cfg")

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        await pool.evict(("acc", "cfg"))

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) == 1
    _, attrs = evict_spans[0]
    assert attrs["reason"] == "manual"
    assert attrs["account_id"] == "acc"
    assert attrs["config_id"] == "cfg"
    assert attrs["pool_size_after"] == 0


# ---------------------------------------------------------------------------
# Test 22 — no-op evict on absent key still emits a span with unchanged size
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_span_evict_noop_absent_key_emits_span() -> None:
    """Calling evict() on a key not in the pool still emits a sandbox_pool.evict
    span with pool_size_after reflecting the unchanged pool size (0)."""
    pool = SandboxPool()

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        await pool.evict(("nonexistent", "key"))

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) == 1
    _, attrs = evict_spans[0]
    assert attrs["account_id"] == "nonexistent"
    assert attrs["config_id"] == "key"
    assert attrs["pool_size_after"] == 0


# ===========================================================================
# Tests 23-25 — SK-35 LEAK-branch: _clear_tmp called on hit/miss/timeout
#
# ``_CLEAR_TMP_ON_REUSE`` is set True on the pool instance (class default is
# False) and ``_clear_tmp`` is replaced with an AsyncMock so no real Vertex
# call is made.
# ===========================================================================


@pytest.mark.asyncio
async def test_tmp_clear_on_lease_0_to_1() -> None:
    """_clear_tmp is awaited on the 0 → 1 refcount transition (SK-42)."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = AsyncMock()  # type: ignore[method-assign]

    async with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor

    pool._clear_tmp.assert_awaited_once_with(executor)


@pytest.mark.asyncio
async def test_tmp_clear_on_cache_hit() -> None:
    """_clear_tmp fires again on the 0 → 1 transition of a second lease (entry reuse)."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = AsyncMock()  # type: ignore[method-assign]

    # First lease: populates cache, fires _clear_tmp at 0→1 transition
    async with pool.lease(account_id="acc", config_id="cfg"):
        pass
    pool._clear_tmp.reset_mock()

    # Second lease: cache hit with refcount 0→1 again — _clear_tmp fires
    async with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor

    pool._clear_tmp.assert_awaited_once_with(executor)


@pytest.mark.asyncio
async def test_tmp_clear_timeout_returns_executor() -> None:
    """When _clear_tmp raises (e.g. asyncio.TimeoutError), executor is still yielded."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    async def _raise_timeout(_executor: Any) -> None:
        raise asyncio.TimeoutError("simulated _clear_tmp timeout")

    pool._clear_tmp = _raise_timeout  # type: ignore[method-assign]

    async with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor


# ---------------------------------------------------------------------------
# Tests 26-28 — PR #722 review concerns: defensive guard + tmp_clear_failed span
# ---------------------------------------------------------------------------
# These cover the WARN-on-guard behaviour from concern #2 and the
# tmp_clear_failed span attribute from concern #4.  See PR #722 description.


@pytest.mark.asyncio
async def test_clear_tmp_guard_warns_on_missing_resource_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_clear_tmp logs a WARNING and short-circuits when sandbox_resource_name is missing."""
    pool = SandboxPool()

    class _ExecutorMissingAttr:
        pass

    with caplog.at_level("WARNING", logger="app.adk.agents.agent_factory.sandbox_pool"):
        await pool._clear_tmp(_ExecutorMissingAttr())  # type: ignore[arg-type]

    assert any(
        "SandboxPool._clear_tmp skipped" in record.message for record in caplog.records
    ), "guard should log a WARNING when sandbox_resource_name is absent"


@pytest.mark.asyncio
async def test_clear_tmp_guard_warns_on_empty_resource_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_clear_tmp logs a WARNING and short-circuits when sandbox_resource_name is ""."""
    pool = SandboxPool()

    class _ExecutorEmptyName:
        sandbox_resource_name = ""

    with caplog.at_level("WARNING", logger="app.adk.agents.agent_factory.sandbox_pool"):
        await pool._clear_tmp(_ExecutorEmptyName())  # type: ignore[arg-type]

    assert any(
        "SandboxPool._clear_tmp skipped" in record.message for record in caplog.records
    )


@pytest.mark.asyncio
async def test_tmp_clear_failed_set_on_span_when_clear_raises() -> None:
    """tmp_clear_failed=True is attached to the sandbox_pool.lease span when _clear_tmp raises.

    The MER-E alert rule depends on this attribute; if the span attrs change shape
    or this value goes missing the security observability degrades silently.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    async def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    async def _raise(_executor: Any) -> None:
        raise RuntimeError("simulated clear failure")

    pool._clear_tmp = _raise  # type: ignore[method-assign]

    captured_attrs: list[dict[str, Any]] = []

    @contextlib.asynccontextmanager
    async def _fake_emit(op_name: str, attrs: dict[str, Any]):
        captured_attrs.append({"op_name": op_name, **attrs})
        yield

    with patch(
        "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span",
        _fake_emit,
    ):
        async with pool.lease(account_id="acc", config_id="cfg"):
            pass

    lease_spans = [a for a in captured_attrs if a["op_name"] == "sandbox_pool.lease"]
    assert len(lease_spans) == 1
    assert lease_spans[0]["tmp_clear_failed"] is True, (
        "tmp_clear_failed must be True when _clear_tmp raises — MER-E alerts depend on it"
    )


# ===========================================================================
# Test 29 — SK-42 CLOBBER fix: concurrent leases block _clear_tmp while
#           another caller is in-flight
# ===========================================================================


@pytest.mark.asyncio
async def test_concurrent_clobber_lease_blocks_clear_during_inflight() -> None:
    """_clear_tmp never fires while another lease is in-flight (SK-42 CLOBBER fix).

    Two concurrent ``lease()`` callers share the same pool key.  Caller A
    enters first and holds the lease while caller B acquires.  Because
    ``refcount`` is already 1 when B acquires (0 → 1 already fired for A),
    B's lease acquisition is NOT a 0 → 1 transition and therefore does NOT
    trigger ``_clear_tmp``.  This ensures B cannot destroy A's in-flight
    /tmp data.

    The test verifies:
    * ``_clear_tmp`` is invoked exactly once (for the first 0 → 1 transition).
    * Both callers receive the same executor instance.
    * Refcount returns to 0 after both leases exit.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()
    clear_count = 0

    async def _fake_construct(**_: Any) -> Any:
        return executor

    async def _count_clear(_executor: Any) -> None:
        nonlocal clear_count
        clear_count += 1

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = _count_clear  # type: ignore[method-assign]

    key = ("acc", "cfg")
    received: list[Any] = []

    # Caller A acquires the lease and holds it while caller B acquires.
    # Use an event to synchronise: A signals B after acquiring, then both exit.
    a_acquired = asyncio.Event()
    b_acquired = asyncio.Event()

    async def caller_a() -> None:
        async with pool.lease(account_id="acc", config_id="cfg") as ex:
            received.append(ex)
            a_acquired.set()
            await b_acquired.wait()

    async def caller_b() -> None:
        await a_acquired.wait()
        async with pool.lease(account_id="acc", config_id="cfg") as ex:
            received.append(ex)
            b_acquired.set()

    await asyncio.gather(caller_a(), caller_b())

    assert clear_count == 1, (
        f"_clear_tmp should fire exactly once (0→1 transition); fired {clear_count} times"
    )
    assert received[0] is executor
    assert received[1] is executor
    assert pool._entry_refcount(key) == 0, (
        "Refcount must be 0 after both leases exit"
    )


@pytest.mark.asyncio
async def test_deferred_evict_fires_on_release() -> None:
    """evict() while a lease is active sets pending_evict=True; _release() fires aclose().

    Scenario:
    1. Acquire a lease (refcount=1).
    2. Call evict() while the lease is held → pending_evict=True, executor NOT closed.
    3. Release the lease (refcount→0) → deferred evict fires: aclose() called, entry removed.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = False
    executor = _make_executor()
    close_count = 0

    async def _fake_construct(**_: Any) -> Any:
        return executor

    async def _fake_aclose() -> None:
        nonlocal close_count
        close_count += 1

    executor.aclose = _fake_aclose  # type: ignore[attr-defined]
    pool._construct = _fake_construct  # type: ignore[method-assign]

    key = ("acc_d", "cfg_d")
    lease_ctx = pool.lease(account_id="acc_d", config_id="cfg_d")
    await lease_ctx.__aenter__()

    # Lease is held — evict should defer.
    assert pool._entry_refcount(key) == 1
    await pool.evict(key)
    assert pool._entry_refcount(key) == 1, "Entry must stay alive while lease is held"
    assert close_count == 0, "aclose() must not fire while lease is active"

    # Release the lease → deferred evict must fire.
    await lease_ctx.__aexit__(None, None, None)

    assert close_count == 1, "aclose() must fire exactly once when refcount drops to 0"
    assert key not in pool._pool, "Entry must be removed from pool after deferred evict"

# ===========================================================================
# SK-43 — _get_vertexai_client caching tests (tests 31-33)
#
# The autouse fixture clears the lru_cache before and after each test so no
# cross-test cache state can leak between them.  Individual tests that call
# _get_vertexai_client directly also patch sys.modules["vertexai"] to avoid
# requiring a live Vertex AI install.
# ===========================================================================


@pytest.fixture(autouse=True)
def _clear_vertexai_client_cache() -> Any:
    """Clear _get_vertexai_client's lru_cache before and after every test in this
    module (autouse=True is intentionally file-wide).  The pre-SK-43 tests don't
    interact with the cache, so the extra clear is a no-op for them; it ensures no
    SK-43 test can pollute the lru_cache state for any subsequent test."""
    _get_vertexai_client.cache_clear()
    yield
    _get_vertexai_client.cache_clear()


# ---------------------------------------------------------------------------
# Test 31 — _get_vertexai_client caches by (project, location) key
# ---------------------------------------------------------------------------


def test_get_vertexai_client_caches_by_key() -> None:
    """Two calls with the same (project, location) return the same instance;
    cache_info().hits == 1 after the second call."""
    mock_vertexai = MagicMock()
    with patch.dict(sys.modules, {"vertexai": mock_vertexai}):
        c1 = _get_vertexai_client("ken-e-dev", "us-central1")
        c2 = _get_vertexai_client("ken-e-dev", "us-central1")
        assert c1 is c2, "Same (project, location) key must return the same client instance"
        assert _get_vertexai_client.cache_info().hits == 1


# ---------------------------------------------------------------------------
# Test 32 — distinct (project, location) pairs produce distinct clients
# ---------------------------------------------------------------------------


def test_get_vertexai_client_distinct_keys_distinct_clients() -> None:
    """Different (project, location) keys produce distinct client instances;
    currsize == 2 after two distinct calls."""
    mock_vertexai = MagicMock()
    # Return a fresh MagicMock for each call so identity comparison works
    mock_vertexai.Client.side_effect = [MagicMock(), MagicMock()]

    with patch.dict(sys.modules, {"vertexai": mock_vertexai}):
        c_dev = _get_vertexai_client("ken-e-dev", "us-central1")
        c_prod = _get_vertexai_client("ken-e-prod", "us-central1")

    assert c_dev is not c_prod, "Different keys must produce distinct client instances"
    assert _get_vertexai_client.cache_info().currsize == 2


# ---------------------------------------------------------------------------
# Test 33 — _clear_tmp reuses the cached client across calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_tmp_reuses_cached_client() -> None:
    """Calling _clear_tmp twice results in vertexai.Client constructed exactly once;
    the second call hits the lru_cache so the constructor is not re-invoked."""
    pool = SandboxPool()

    class _FakeExecutor:
        sandbox_resource_name = (
            "projects/test-proj/locations/us-central1/sandboxes/acc/cfg"
        )

    mock_vertexai = MagicMock()
    mock_client = MagicMock()
    mock_vertexai.Client.return_value = mock_client

    with (
        patch.dict(sys.modules, {"vertexai": mock_vertexai}),
        patch("asyncio.wait_for", new=AsyncMock(return_value=None)),
    ):
        await pool._clear_tmp(_FakeExecutor())  # type: ignore[arg-type]
        await pool._clear_tmp(_FakeExecutor())  # type: ignore[arg-type]

    # vertexai.Client must have been called once despite two _clear_tmp calls
    mock_vertexai.Client.assert_called_once()

