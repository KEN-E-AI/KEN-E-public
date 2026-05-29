"""Unit tests for app.adk.agents.agent_factory.sandbox_pool.SandboxPool.

No live GCP or ADK install required — ``SandboxPool._construct`` is stubbed in
every test that exercises the pool internals.  ``time.monotonic`` is patched in
TTL-sensitive tests via ``unittest.mock.patch``.

The pool is synchronous (it backs ADK's synchronous code-executor contract);
concurrency is exercised with real ``threading.Thread``s rather than
``asyncio.gather``.

Coverage map
------------
* AC-11 — SandboxPool reuse: same key returns same executor; ``_construct``
  called exactly once (tests 2, 3, 4).
* AC-12 — SandboxPool eviction cleanup: LRU + TTL eviction paths remove the
  entry and keep pool integrity (``AgentEngineSandboxCodeExecutor`` has no
  ``aclose``; eviction just drops the reference) (tests 5, 6, 7).
* AC-14 — SandboxPool concurrent safety: same-key single-flight under a thread
  fan-out of 10; the slow path (``_clear_tmp``) runs lock-free so different
  keys overlap (tests 9, 10).
* Edge cases: unknown-key evict no-op, start/stop lifecycle, start idempotency,
  resource name format (tests 11-16).
* AC-8 — Weave span content (tests 17-22): cache_hit, pool_size_after,
  reason correctness for each eviction path; no-op evict still emits a span.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.adk.agents.agent_factory.sandbox_pool import (
    SandboxPool,
    _get_vertexai_client,
    _sandbox_resource_name,
)

# ---------------------------------------------------------------------------
# Fake executor factory
# ---------------------------------------------------------------------------


def _make_executor() -> MagicMock:
    """Return a fresh MagicMock standing in for a pooled executor.

    The real ``AgentEngineSandboxCodeExecutor`` exposes no ``aclose``/``close``
    (its MRO is pydantic ``BaseModel``), so eviction simply drops the pool's
    reference — there is nothing to assert about cleanup beyond entry removal.
    """
    return MagicMock()


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


def test_idempotency_same_key() -> None:
    """get_or_create twice for the same key returns the same executor by identity."""
    pool = SandboxPool()
    executor = _make_executor()
    call_count = 0

    def _fake_construct(**_: Any) -> Any:
        nonlocal call_count
        call_count += 1
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    first = pool.get_or_create(account_id="acc", config_id="cfg")
    second = pool.get_or_create(account_id="acc", config_id="cfg")

    assert first is second  # AC-11 identity
    assert call_count == 1  # AC-11 single construction


# ---------------------------------------------------------------------------
# Test 3 — different keys produce different instances
# ---------------------------------------------------------------------------


def test_idempotency_different_keys() -> None:
    """get_or_create for different keys returns different executor instances."""
    pool = SandboxPool()
    executors: list[MagicMock] = []
    call_count = 0

    def _fake_construct(**_: Any) -> Any:
        nonlocal call_count
        call_count += 1
        ex = _make_executor()
        executors.append(ex)
        return ex

    pool._construct = _fake_construct  # type: ignore[method-assign]

    a = pool.get_or_create(account_id="acc", config_id="x")
    b = pool.get_or_create(account_id="acc", config_id="y")

    assert a is not b
    assert call_count == 2


# ---------------------------------------------------------------------------
# Test 4 — LRU bump on hit: re-accessed entry survives the next eviction
# ---------------------------------------------------------------------------


def test_lru_bump_on_hit() -> None:
    """With _MAX_ENTRIES=4, re-accessing the oldest entry protects it from
    the next over-cap eviction; the second-oldest is evicted instead."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 4  # type: ignore[assignment]

    def _fake_construct(*, account_id: str, config_id: str) -> Any:
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    # Fill all 4 slots: k0 (oldest), k1, k2, k3 (newest)
    for i in range(4):
        pool.get_or_create(account_id="acc", config_id=f"k{i}")

    # Re-access k0 — it should now be MRU
    pool.get_or_create(account_id="acc", config_id="k0")

    # Insert k4 → over cap; k1 should be evicted (now the LRU)
    pool.get_or_create(account_id="acc", config_id="k4")

    remaining = list(pool._pool.keys())
    assert ("acc", "k1") not in remaining, "k1 should have been evicted (LRU)"
    assert ("acc", "k0") in remaining, "k0 should still be present (bumped to MRU)"


# ---------------------------------------------------------------------------
# Test 5 — LRU eviction removes the LRU entry
# ---------------------------------------------------------------------------


def test_lru_eviction_removes_entry() -> None:
    """Inserting the 5th key with _MAX_ENTRIES=4 removes the LRU entry (AC-12)."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 4  # type: ignore[assignment]

    def _fake_construct(*, account_id: str, config_id: str) -> Any:
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    for i in range(4):
        pool.get_or_create(account_id="acc", config_id=f"k{i}")

    # k0 is the LRU; inserting k4 should evict it.
    pool.get_or_create(account_id="acc", config_id="k4")

    assert ("acc", "k0") not in pool._pool, "LRU entry k0 should have been removed"
    assert len(pool._pool) == 4, "Pool must stay at the cap after eviction"


# ---------------------------------------------------------------------------
# Test 6 — TTL sweep evicts old entries
# ---------------------------------------------------------------------------


def test_sweep_idle_ttl() -> None:
    """sweep_idle() evicts all entries whose last_used is before the TTL cutoff."""
    pool = SandboxPool()

    def _fake_construct(**_: Any) -> Any:
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_start = 1_000.0

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_start

        # Populate 3 entries at t=1000
        for i in range(3):
            pool.get_or_create(account_id="acc", config_id=f"k{i}")

        # Advance time past TTL
        mock_time.monotonic.return_value = t_start + pool._IDLE_TTL_SECONDS + 1

        pool.sweep_idle()

    assert len(pool._pool) == 0  # all swept (AC-12 TTL path)


# ---------------------------------------------------------------------------
# Test 7 — partial sweep: only stale entries removed
# ---------------------------------------------------------------------------


def test_sweep_idle_partial() -> None:
    """sweep_idle() removes only entries older than the TTL, leaving fresh ones."""
    pool = SandboxPool()

    def _fake_construct(*, account_id: str, config_id: str) -> Any:
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        t_base = 1_000.0
        # Populate 2 stale entries at t=1000
        mock_time.monotonic.return_value = t_base
        pool.get_or_create(account_id="acc", config_id="stale1")
        pool.get_or_create(account_id="acc", config_id="stale2")

        # Populate 1 fresh entry at t=1000+TTL (right on the boundary — not stale)
        fresh_time = t_base + pool._IDLE_TTL_SECONDS
        mock_time.monotonic.return_value = fresh_time
        pool.get_or_create(account_id="acc", config_id="fresh")

        # Sweep at t=1000+TTL+1 → stale entries cross cutoff; fresh does not
        mock_time.monotonic.return_value = fresh_time + 1
        pool.sweep_idle()

    assert ("acc", "fresh") in pool._pool
    assert ("acc", "stale1") not in pool._pool
    assert ("acc", "stale2") not in pool._pool


# ---------------------------------------------------------------------------
# Test 9 — concurrent same-key single-flight (AC-14)
# ---------------------------------------------------------------------------


def test_concurrent_same_key_single_flight() -> None:
    """10 concurrent get_or_create calls for the same key all get the same executor.

    ``_construct`` runs under the structural lock, so the first thread to enter
    constructs (held briefly by a sleep) while the others block, then observe
    the cache hit — a single-flight guarantee.
    """
    pool = SandboxPool()
    construct_count = 0

    def _fake_construct(**_: Any) -> Any:
        nonlocal construct_count
        construct_count += 1  # serialised: _construct runs under the pool lock
        time.sleep(0.05)  # widen the race window for the other threads
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    results: list[Any] = []
    results_lock = threading.Lock()

    def _worker() -> None:
        r = pool.get_or_create(account_id="acc", config_id="cfg")
        with results_lock:
            results.append(r)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(results) == 10
    assert all(r is results[0] for r in results), "All results should be identical"
    assert construct_count == 1, "_construct should be called exactly once"  # AC-14


# ---------------------------------------------------------------------------
# Test 10 — concurrent different-key leases run their slow path in parallel (AC-14)
# ---------------------------------------------------------------------------


def test_concurrent_different_keys_clear_in_parallel() -> None:
    """Two different-key leases run ``_clear_tmp`` concurrently.

    The structural lock is held only for the (I/O-free) refcount bump +
    construction; the slow ``_clear_tmp`` runs lock-free.  Two leases on
    different keys therefore overlap their clears rather than serialising —
    the core concurrency guarantee of the single-lock design.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    delay = 0.05

    def _fake_construct(*, account_id: str, config_id: str) -> Any:
        return _make_executor()

    def _slow_clear(_executor: Any) -> None:
        time.sleep(delay)

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = _slow_clear  # type: ignore[method-assign]

    def _worker(cfg: str) -> None:
        with pool.lease(account_id="acc", config_id=cfg):
            pass

    start = time.monotonic()
    tx = threading.Thread(target=_worker, args=("x",))
    ty = threading.Thread(target=_worker, args=("y",))
    tx.start()
    ty.start()
    tx.join(timeout=10)
    ty.join(timeout=10)
    elapsed = time.monotonic() - start

    # If parallel: ~delay; if serial: ~2*delay. Allow 1.8x as the threshold.
    assert elapsed < 1.8 * delay, (
        f"Parallel _clear_tmp took {elapsed:.3f}s - expected < {1.8 * delay:.3f}s"
    )


# ---------------------------------------------------------------------------
# Test 11 — evict unknown key is a no-op
# ---------------------------------------------------------------------------


def test_evict_unknown_key_noop() -> None:
    """Calling evict() on a key not in the pool does not raise."""
    pool = SandboxPool()
    pool.evict(("nonexistent", "key"))  # must not raise


# ---------------------------------------------------------------------------
# Test 12 — start / stop lifecycle
# ---------------------------------------------------------------------------


def test_start_stop_lifecycle() -> None:
    """start() arms a sweep daemon thread; stop() signals + joins it cleanly."""
    pool = SandboxPool()
    pool.start()
    assert pool._sweep_thread is not None
    assert pool._sweep_thread.is_alive()

    pool.stop()
    assert pool._sweep_thread is None


# ---------------------------------------------------------------------------
# Test 13 — start is idempotent
# ---------------------------------------------------------------------------


def test_start_idempotent() -> None:
    """Calling start() twice does not spawn a second sweep thread."""
    pool = SandboxPool()
    pool.start()
    thread_first = pool._sweep_thread

    pool.start()  # second call
    assert pool._sweep_thread is thread_first  # same thread object

    pool.stop()


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


def test_stale_before_guard_skips_refreshed_entry() -> None:
    """evict(..., stale_before=cutoff) skips an entry whose last_used was
    updated after the sweep snapshot was taken — the TOCTOU guard."""
    pool = SandboxPool()
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_stale = 1_000.0

    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_stale
        pool.get_or_create(account_id="acc", config_id="cfg")

    key = ("acc", "cfg")

    # Simulate a concurrent hit that refreshed last_used after the snapshot
    t_fresh = t_stale + pool._IDLE_TTL_SECONDS + 10
    pool._pool[key] = (executor, t_fresh, 0, False)

    # The cutoff was computed before the refresh, so the key appeared stale then
    cutoff = t_stale + pool._IDLE_TTL_SECONDS + 1

    pool.evict(key, stale_before=cutoff)

    # Entry must NOT have been removed — it was refreshed past the cutoff
    assert key in pool._pool, "Refreshed entry should not be evicted"


# ===========================================================================
# AC-8 — Weave span-content assertions (tests 17-22)
#
# ``emit_sandbox_pool_span`` is patched to a recording context manager so
# tests can inspect (name, attrs) tuples without requiring a live Weave install.
# ===========================================================================

_SPAN_PATH = "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span"


def _make_span_recorder() -> tuple[list[tuple[str, dict]], object]:
    """Return (recorded_spans list, context-manager patch target).

    Each emitted span is appended as ``(name, attrs)`` to *recorded_spans*.
    """
    recorded: list[tuple[str, dict]] = []

    @contextlib.contextmanager
    def _recording_span(name: str, attrs: dict) -> Any:
        recorded.append((name, dict(attrs)))
        yield

    return recorded, _recording_span


# ---------------------------------------------------------------------------
# Test 17 — cache miss emits sandbox_pool.get with cache_hit=False
# ---------------------------------------------------------------------------


def test_span_get_cache_miss() -> None:
    """A cache miss emits sandbox_pool.get with cache_hit=False and pool_size_after=1."""
    pool = SandboxPool()
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        pool.get_or_create(account_id="acc", config_id="cfg")

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


def test_span_get_cache_hit() -> None:
    """A cache hit emits sandbox_pool.get with cache_hit=True."""
    pool = SandboxPool()
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    # Prime the pool with one call (span recorded but ignored)
    _recorded_first, pt_first = _make_span_recorder()
    with patch(_SPAN_PATH, pt_first):
        pool.get_or_create(account_id="acc", config_id="cfg")

    # Second call — should be a cache hit
    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        pool.get_or_create(account_id="acc", config_id="cfg")

    get_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.get"]
    assert len(get_spans) == 1
    _, attrs = get_spans[0]
    assert attrs["cache_hit"] is True
    assert attrs["pool_size_after"] == 1


# ---------------------------------------------------------------------------
# Test 19 — LRU-triggered eviction emits sandbox_pool.evict with reason="lru"
# ---------------------------------------------------------------------------


def test_span_evict_lru_reason() -> None:
    """LRU eviction (via _evict_if_over_cap) emits sandbox_pool.evict with reason='lru'."""
    pool = SandboxPool()
    pool._MAX_ENTRIES = 1  # type: ignore[assignment]

    def _fake_construct(*, account_id: str, config_id: str) -> Any:
        return _make_executor()

    pool._construct = _fake_construct  # type: ignore[method-assign]

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        pool.get_or_create(account_id="acc", config_id="k0")
        pool.get_or_create(account_id="acc", config_id="k1")  # triggers LRU evict

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) >= 1
    lru_spans = [(n, a) for n, a in evict_spans if a["reason"] == "lru"]
    assert lru_spans, "Expected at least one sandbox_pool.evict span with reason='lru'"


# ---------------------------------------------------------------------------
# Test 20 — TTL sweep emits sandbox_pool.evict with reason="ttl"
# ---------------------------------------------------------------------------


def test_span_evict_ttl_reason() -> None:
    """TTL sweep (via sweep_idle) emits sandbox_pool.evict with reason='ttl'."""
    pool = SandboxPool()
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    t_start = 1_000.0
    with patch("app.adk.agents.agent_factory.sandbox_pool.time") as mock_time:
        mock_time.monotonic.return_value = t_start
        _recorded_first, pt_first = _make_span_recorder()
        with patch(_SPAN_PATH, pt_first):
            pool.get_or_create(account_id="acc", config_id="cfg")

        mock_time.monotonic.return_value = t_start + pool._IDLE_TTL_SECONDS + 1

        recorded, patch_target = _make_span_recorder()
        with patch(_SPAN_PATH, patch_target):
            pool.sweep_idle()

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) == 1
    _, attrs = evict_spans[0]
    assert attrs["reason"] == "ttl"


# ---------------------------------------------------------------------------
# Test 21 — direct evict() call uses reason="manual" by default
# ---------------------------------------------------------------------------


def test_span_evict_manual_reason() -> None:
    """Direct pool.evict(key) emits sandbox_pool.evict with reason='manual'."""
    pool = SandboxPool()
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    _recorded_first, pt_first = _make_span_recorder()
    with patch(_SPAN_PATH, pt_first):
        pool.get_or_create(account_id="acc", config_id="cfg")

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        pool.evict(("acc", "cfg"))

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


def test_span_evict_noop_absent_key_emits_span() -> None:
    """Calling evict() on a key not in the pool still emits a sandbox_pool.evict
    span with pool_size_after reflecting the unchanged pool size (0)."""
    pool = SandboxPool()

    recorded, patch_target = _make_span_recorder()
    with patch(_SPAN_PATH, patch_target):
        pool.evict(("nonexistent", "key"))

    evict_spans = [(n, a) for n, a in recorded if n == "sandbox_pool.evict"]
    assert len(evict_spans) == 1
    _, attrs = evict_spans[0]
    assert attrs["account_id"] == "nonexistent"
    assert attrs["config_id"] == "key"
    assert attrs["pool_size_after"] == 0


# ===========================================================================
# Tests 23-25 — SK-35 LEAK-branch: _clear_tmp called on the 0 → 1 transition
#
# ``_CLEAR_TMP_ON_REUSE`` is True by the class default; ``_clear_tmp`` is
# replaced with a MagicMock so no real Vertex call is made.
# ===========================================================================


def test_tmp_clear_on_lease_0_to_1() -> None:
    """_clear_tmp is called on the 0 → 1 refcount transition (SK-42)."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock()  # type: ignore[method-assign]

    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor

    pool._clear_tmp.assert_called_once_with(executor)


def test_tmp_clear_on_cache_hit() -> None:
    """_clear_tmp fires again on the 0 → 1 transition of a second lease (entry reuse)."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock()  # type: ignore[method-assign]

    # First lease: populates cache, fires _clear_tmp at 0→1 transition
    with pool.lease(account_id="acc", config_id="cfg"):
        pass
    pool._clear_tmp.reset_mock()

    # Second lease: cache hit with refcount 0→1 again — _clear_tmp fires
    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor

    pool._clear_tmp.assert_called_once_with(executor)


def test_tmp_clear_timeout_returns_executor() -> None:
    """When _clear_tmp raises (e.g. TimeoutError), executor is still yielded."""
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    def _raise_timeout(_executor: Any) -> None:
        raise TimeoutError("simulated _clear_tmp timeout")

    pool._clear_tmp = _raise_timeout  # type: ignore[method-assign]

    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor


# ---------------------------------------------------------------------------
# Tests 26-28 — PR #722 review concerns: defensive guard + tmp_clear_failed span
# ---------------------------------------------------------------------------
# These cover the WARN-on-guard behaviour from concern #2 and the
# tmp_clear_failed span attribute from concern #4.  See PR #722 description.


def test_clear_tmp_guard_warns_on_missing_resource_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_clear_tmp logs a WARNING and short-circuits when sandbox_resource_name is missing."""
    pool = SandboxPool()

    class _ExecutorMissingAttr:
        pass

    with caplog.at_level("WARNING", logger="app.adk.agents.agent_factory.sandbox_pool"):
        pool._clear_tmp(_ExecutorMissingAttr())  # type: ignore[arg-type]

    assert any(
        "SandboxPool._clear_tmp skipped" in record.message for record in caplog.records
    ), "guard should log a WARNING when sandbox_resource_name is absent"


def test_clear_tmp_guard_warns_on_empty_resource_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_clear_tmp logs a WARNING and short-circuits when sandbox_resource_name is ""."""
    pool = SandboxPool()

    class _ExecutorEmptyName:
        sandbox_resource_name = ""

    with caplog.at_level("WARNING", logger="app.adk.agents.agent_factory.sandbox_pool"):
        pool._clear_tmp(_ExecutorEmptyName())  # type: ignore[arg-type]

    assert any(
        "SandboxPool._clear_tmp skipped" in record.message for record in caplog.records
    )


def test_tmp_clear_failed_set_on_span_when_clear_raises() -> None:
    """tmp_clear_failed=True is attached to the sandbox_pool.lease span when _clear_tmp raises.

    The MER-E alert rule depends on this attribute; if the span attrs change shape
    or this value goes missing the security observability degrades silently.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    def _raise(_executor: Any) -> None:
        raise RuntimeError("simulated clear failure")

    pool._clear_tmp = _raise  # type: ignore[method-assign]

    captured_attrs: list[dict[str, Any]] = []

    @contextlib.contextmanager
    def _fake_emit(op_name: str, attrs: dict[str, Any]) -> Any:
        captured_attrs.append({"op_name": op_name, **attrs})
        yield

    with patch(
        "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span",
        _fake_emit,
    ):
        with pool.lease(account_id="acc", config_id="cfg"):
            pass

    lease_spans = [a for a in captured_attrs if a["op_name"] == "sandbox_pool.lease"]
    assert len(lease_spans) == 1
    assert lease_spans[0]["tmp_clear_failed"] is True, (
        "tmp_clear_failed must be True when _clear_tmp raises — MER-E alerts depend on it"
    )


def test_client_cache_hit_on_lease_span() -> None:
    """client_cache_hit reflects the vertexai.Client lru_cache state during _clear_tmp (SK-43).

    The autouse fixture clears the cache first, so the first lease's _clear_tmp
    constructs the client (cache miss → client_cache_hit=False); a second lease
    cycle on the same key is another 0→1 transition whose _clear_tmp hits the
    cache (client_cache_hit=True).
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True

    class _Executor:
        sandbox_resource_name = (
            "projects/test-proj/locations/us-central1/sandboxes/acc/cfg"
        )

    executor = _Executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    captured_attrs: list[dict[str, Any]] = []

    @contextlib.contextmanager
    def _fake_emit(op_name: str, attrs: dict[str, Any]) -> Any:
        captured_attrs.append({"op_name": op_name, **attrs})
        yield

    mock_vertexai = MagicMock()
    mock_vertexai.Client.return_value = MagicMock()

    try:
        with (
            patch.dict(sys.modules, {"vertexai": mock_vertexai}),
            patch(
                "app.adk.agents.agent_factory.sandbox_pool.emit_sandbox_pool_span",
                _fake_emit,
            ),
        ):
            with pool.lease(account_id="acc", config_id="cfg"):
                pass
            # Refcount returned to 0, so this is a fresh 0→1 transition → _clear_tmp
            # fires again and reuses the cached client.
            with pool.lease(account_id="acc", config_id="cfg"):
                pass
    finally:
        pool.stop()  # shut down the lazily-created _clear_tmp executor

    lease_hits = [
        a["client_cache_hit"]
        for a in captured_attrs
        if a["op_name"] == "sandbox_pool.lease"
    ]
    assert lease_hits == [False, True]
    mock_vertexai.Client.assert_called_once()


# ===========================================================================
# Test 29 — SK-42 CLOBBER fix: concurrent leases block _clear_tmp while
#           another caller is in-flight
# ===========================================================================


def test_concurrent_clobber_lease_blocks_clear_during_inflight() -> None:
    """_clear_tmp never fires while another lease is in-flight (SK-42 CLOBBER fix).

    Two concurrent ``lease()`` callers (on real threads) share the same pool
    key.  Caller A enters first and holds the lease while caller B acquires.
    Because ``refcount`` is already 1 when B acquires (0 → 1 already fired for
    A), B's lease acquisition is NOT a 0 → 1 transition and therefore does NOT
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

    def _fake_construct(**_: Any) -> Any:
        return executor

    def _count_clear(_executor: Any) -> None:
        nonlocal clear_count
        clear_count += 1

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = _count_clear  # type: ignore[method-assign]

    key = ("acc", "cfg")
    received: list[Any] = []
    errors: list[BaseException] = []

    # Caller A acquires the lease and holds it while caller B acquires.
    # Use events to synchronise: A signals B after acquiring, then both exit.
    a_acquired = threading.Event()
    b_acquired = threading.Event()

    def caller_a() -> None:
        try:
            with pool.lease(account_id="acc", config_id="cfg") as ex:
                received.append(ex)
                a_acquired.set()
                assert b_acquired.wait(timeout=5), "caller_b never acquired"
        except BaseException as exc:  # surface thread failures to the main thread
            errors.append(exc)

    def caller_b() -> None:
        try:
            assert a_acquired.wait(timeout=5), "caller_a never acquired"
            with pool.lease(account_id="acc", config_id="cfg") as ex:
                received.append(ex)
                b_acquired.set()
        except BaseException as exc:  # surface thread failures to the main thread
            errors.append(exc)

    ta = threading.Thread(target=caller_a)
    tb = threading.Thread(target=caller_b)
    ta.start()
    tb.start()
    ta.join(timeout=10)
    tb.join(timeout=10)

    assert not errors, f"thread failures: {errors}"
    assert clear_count == 1, (
        f"_clear_tmp should fire exactly once (0→1 transition); fired {clear_count} times"
    )
    assert received[0] is executor
    assert received[1] is executor
    assert pool._entry_refcount(key) == 0, "Refcount must be 0 after both leases exit"


# ---------------------------------------------------------------------------
# Test 30 — deferred eviction: evict during an active lease defers removal
#           until the lease releases
# ---------------------------------------------------------------------------


def test_deferred_evict_removes_entry_on_release() -> None:
    """evict() while a lease is active sets pending_evict=True; release removes the entry.

    Scenario:
    1. Acquire a lease (refcount=1).
    2. Call evict() while the lease is held → pending_evict=True, entry kept.
    3. Release the lease (refcount→0) → deferred evict fires: entry removed.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = False
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    pool._construct = _fake_construct  # type: ignore[method-assign]

    key = ("acc_d", "cfg_d")
    lease_ctx = pool.lease(account_id="acc_d", config_id="cfg_d")
    lease_ctx.__enter__()

    # Lease is held — evict should defer.
    assert pool._entry_refcount(key) == 1
    pool.evict(key)
    assert pool._entry_refcount(key) == 1, "Entry must stay alive while lease is held"
    assert key in pool._pool, "Entry must remain (deferred) while the lease is active"

    # Release the lease → deferred evict must fire.
    lease_ctx.__exit__(None, None, None)

    assert key not in pool._pool, "Entry must be removed from pool after deferred evict"
    assert pool._entry_refcount(key) == 0


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
        assert c1 is c2, (
            "Same (project, location) key must return the same client instance"
        )
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


def test_clear_tmp_reuses_cached_client() -> None:
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

    try:
        with patch.dict(sys.modules, {"vertexai": mock_vertexai}):
            pool._clear_tmp(_FakeExecutor())  # type: ignore[arg-type]
            pool._clear_tmp(_FakeExecutor())  # type: ignore[arg-type]
    finally:
        pool.stop()  # shut down the lazily-created _clear_tmp executor

    # vertexai.Client must have been called once despite two _clear_tmp calls
    mock_vertexai.Client.assert_called_once()


# ---------------------------------------------------------------------------
# Test 34 — deadlock guard: a raise from _evict_if_over_cap during lease() must
#           not orphan the clearing event / refcount (PR #727 reviewer finding)
# ---------------------------------------------------------------------------


def test_lease_evict_failure_releases_clearing_event_and_refcount() -> None:
    """_evict_if_over_cap raising during lease() must not deadlock the key.

    The cache-miss path registers ``self._clearing[key]`` and bumps the refcount
    inside ``_acquire``'s structural lock; ``lease()`` then enforces the LRU cap.
    If that enforcement raises, ``lease()``'s ``try/finally`` must still pop + set
    the clearing event and release the refcount — otherwise every future
    ``_acquire`` for the key blocks forever on the never-set ``Event``.  Verifies
    the exception propagates, the state is clean, and a subsequent lease of the
    same key succeeds.
    """
    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True  # so the 0→1 miss registers a clearing event
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    def _raise_evict() -> None:
        raise RuntimeError("simulated cap-enforcement failure")

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock()  # type: ignore[method-assign]
    pool._evict_if_over_cap = _raise_evict  # type: ignore[method-assign]

    key = ("acc", "cfg")

    # First lease: cache miss → _evict_if_over_cap fires → raises before yield.
    with pytest.raises(RuntimeError, match="simulated cap-enforcement failure"):
        with pool.lease(account_id="acc", config_id="cfg"):
            pass  # never reached — lease() raises before yielding

    # No orphaned clearing event; refcount fully released.
    assert key not in pool._clearing
    assert pool._entry_refcount(key) == 0

    # The key is reusable: a subsequent lease (now a cache hit, so
    # _evict_if_over_cap is not called) acquires without deadlocking.
    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor


# ---------------------------------------------------------------------------
# Test 35 — cancellation guard (evict site): asyncio.CancelledError raised
#           inside _evict_if_over_cap during lease() must not orphan state
# ---------------------------------------------------------------------------


def test_lease_cancellation_during_evict_releases_clearing_event_and_refcount() -> None:
    """CancelledError from _evict_if_over_cap must not deadlock the key.

    This mirrors test_lease_evict_failure_releases_clearing_event_and_refcount
    (Test 34) but raises ``asyncio.CancelledError`` instead of ``RuntimeError``.
    ``asyncio.CancelledError`` is a ``BaseException`` subclass since Python 3.8,
    so it flows past the inner ``except Exception`` block around ``_clear_tmp``
    (``sandbox_pool.py:289``) and is handled only by the outer ``try/finally``
    at ``sandbox_pool.py:317``.  Verifies that the outer backstop pops + sets
    any registered clearing event and releases the refcount regardless of which
    ``BaseException`` subclass propagates, leaving the key reusable.
    """
    import asyncio

    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True  # so the 0→1 miss registers a clearing event
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    def _raise_evict() -> None:
        raise asyncio.CancelledError(
            "simulated task cancellation during cap enforcement"
        )

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._clear_tmp = MagicMock()  # type: ignore[method-assign]
    pool._evict_if_over_cap = _raise_evict  # type: ignore[method-assign]

    key = ("acc", "cfg")

    # First lease: cache miss → _evict_if_over_cap fires → CancelledError raised.
    with pytest.raises(asyncio.CancelledError):
        with pool.lease(account_id="acc", config_id="cfg"):
            pass  # never reached — lease() raises before yielding

    # No orphaned clearing event; refcount fully released.
    assert key not in pool._clearing
    assert pool._entry_refcount(key) == 0

    # The key is reusable: a subsequent lease (now a cache hit, so
    # _evict_if_over_cap is not called) acquires without deadlocking.
    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor
    assert pool._entry_refcount(key) == 0


# ---------------------------------------------------------------------------
# Test 36 — cancellation guard (clear_tmp site): asyncio.CancelledError raised
#           inside _clear_tmp during lease() must not orphan state
# ---------------------------------------------------------------------------


def test_lease_cancellation_during_clear_tmp_releases_clearing_event_and_refcount() -> (
    None
):
    """CancelledError from _clear_tmp must not deadlock the key.

    Unlike Test 35 (which cancels at ``_evict_if_over_cap``), this test cancels
    at ``_clear_tmp`` (``sandbox_pool.py:287``).  At that point the clearing
    event has already been registered by ``_acquire`` and
    ``_evict_if_over_cap`` has succeeded, so execution is inside the inner
    ``if clearing_event is not None`` block.

    ``asyncio.CancelledError`` is a ``BaseException`` subclass, so it bypasses
    the inner ``except Exception`` at ``sandbox_pool.py:289`` (which only catches
    ``Exception``) and lands directly in the inner ``finally`` at
    ``sandbox_pool.py:295``.  That inner ``finally`` pops ``self._clearing[key]``
    and sets the event, unblocking waiters.  The outer ``finally`` then runs the
    backstop pop (a no-op because the inner ``finally`` already removed the entry)
    and releases the refcount.

    Verifies the three SK-48 invariants after the cancelled lease and confirms a
    subsequent lease of the same key succeeds without deadlocking.
    """
    import asyncio

    pool = SandboxPool()
    pool._CLEAR_TMP_ON_REUSE = True  # so the 0→1 miss registers a clearing event
    executor = _make_executor()

    def _fake_construct(**_: Any) -> Any:
        return executor

    def _noop_evict() -> None:
        pass  # cap enforcement succeeds; cancellation happens later at _clear_tmp

    _clear_tmp_calls = 0

    def _raise_clear_tmp(_executor: Any) -> None:
        nonlocal _clear_tmp_calls
        _clear_tmp_calls += 1
        if _clear_tmp_calls == 1:
            raise asyncio.CancelledError("simulated task cancellation during tmp clear")

    pool._construct = _fake_construct  # type: ignore[method-assign]
    pool._evict_if_over_cap = _noop_evict  # type: ignore[method-assign]
    pool._clear_tmp = _raise_clear_tmp  # type: ignore[method-assign]

    key = ("acc", "cfg")

    # First lease: cache miss → _clear_tmp fires → CancelledError bypasses
    # except Exception and hits the inner finally, which pops + sets the
    # clearing event, then re-raises into the outer finally, which releases
    # the refcount.
    with pytest.raises(asyncio.CancelledError):
        with pool.lease(account_id="acc", config_id="cfg"):
            pass  # never reached — lease() raises before yielding

    # Inner finally already cleaned up the clearing event; outer backstop
    # was a no-op.  Both invariants must hold.
    assert key not in pool._clearing
    assert pool._entry_refcount(key) == 0

    # The key is reusable: a subsequent lease (now a cache hit, so neither
    # _evict_if_over_cap nor _clear_tmp is called) acquires without deadlocking.
    with pool.lease(account_id="acc", config_id="cfg") as result:
        assert result is executor
    assert pool._entry_refcount(key) == 0
    assert pool._entry_refcount(key) == 0
