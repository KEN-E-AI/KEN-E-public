"""Process-wide pool of AgentEngineSandboxCodeExecutor instances.

SK-PRD-02 §4.6 — SandboxPool.

Under AH-PRD-09's per-turn dispatch model the agent factory rebuilds every
specialist ``LlmAgent`` on each chat turn.  Constructing a fresh
``AgentEngineSandboxCodeExecutor`` per rebuild would pay a sandbox cold-start
on every message — latency-dominating for any sandbox-attached specialist.
This pool keeps executor instances alive across ``LlmAgent`` rebuilds so the
sandbox process outlives any single agent instance.

The pool is **synchronous** because ADK's code-executor contract is
synchronous: ``BaseCodeExecutor.execute_code`` (and the concrete
``AgentEngineSandboxCodeExecutor.execute_code``) are plain ``def``s that ADK's
``_code_execution`` flow invokes un-awaited and whose ``.stdout``/``.stderr``
it reads immediately.  ``LeasedSandboxExecutor`` therefore drives ``lease()``
synchronously, and nothing in the pool's hot path performs ``await``-able I/O:
``_construct`` only parses a resource-name regex (the real sandbox cold-start
lives inside the inner ``execute_code``), and ``_clear_tmp``'s Vertex SDK call
is itself synchronous.  Concurrency is handled with a single ``threading.Lock``
guarding the pool dict and ``threading.Event``s for the clearing handshake.

Lifecycle: the pool is a process-wide singleton.  Call ``start()`` once after
construction (from the Cloud Run startup path, owned by SK-26) to arm the
background idle-sweep daemon thread.  Call ``stop()`` on graceful shutdown to
signal it.  Both methods are idempotent.

``AgentEngineSandboxCodeExecutor`` is lazily imported inside ``_construct`` so
this module remains importable in test environments that do not have a live ADK
install — matching the pattern in ``agent_factory/mcp.py:372``.
"""

from __future__ import annotations

import contextlib
import functools
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Literal

from app.adk.tracking.sandbox_pool_spans import emit_sandbox_pool_span
from shared.structured_logging import get_structured_logger

if TYPE_CHECKING:
    from google.adk.code_executors.agent_engine_sandbox_code_executor import (
        AgentEngineSandboxCodeExecutor,
    )

logger = get_structured_logger(__name__)


def _sandbox_resource_name(account_id: str, config_id: str) -> str:
    """Return a deterministic Vertex AI sandbox resource name.

    Format follows SK-PRD-02 §4.6 literal.  The correct GCP resource path
    format (``sandboxEnvironments/`` vs. ``reasoningEngines/`` vs. the PRD
    placeholder ``sandboxes/``) is resolved in SK-26 when ``_build_code_executor``
    is wired to a live executor.  SK-23 tests stub ``_construct`` so this
    value never reaches a real ADK constructor.

    The slash-separated ``account_id/config_id`` suffix avoids the collision
    that a flat underscore separator would introduce: e.g. ``("acc_x", "y")``
    and ``("acc", "x_y")`` would produce identical names under a flat scheme.
    Both IDs are validated to be slash-free; a slash in either would make the
    path ambiguous and produce a malformed GCP resource name.

    See ``docs/spike/q1-network-egress.md:188`` and SK-26 for final path format.
    """
    if "/" in account_id or "/" in config_id:
        raise ValueError(
            "account_id and config_id must not contain '/'; "
            f"got account_id={account_id!r}, config_id={config_id!r}"
        )
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    return (
        f"projects/{project_id}/locations/{location}/sandboxes/{account_id}/{config_id}"
    )


# ---------------------------------------------------------------------------
# Pool entry tuple shape
# ---------------------------------------------------------------------------
# Entry shape: (executor, last_used_monotonic_time, refcount, pending_evict)
# - executor: the AgentEngineSandboxCodeExecutor instance
# - last_used: monotonic timestamp updated on every get_or_create / lease hit
# - refcount: number of active ExecutorLease holders; 0 means no in-flight use
# - pending_evict: True when an LRU/TTL eviction was deferred because
#   refcount > 0; the deferred evict fires when refcount drops to 0
_PoolEntry = tuple[Any, float, int, bool]


@functools.lru_cache(maxsize=2)
def _get_vertexai_client(project: str, location: str) -> Any:
    """Return a cached ``vertexai.Client`` for the given project and location.

    Thread-safety: gRPC channels (which back all Google Cloud Python clients)
    are documented as thread-safe in the Python gRPC API reference:
    https://grpc.github.io/grpc/python/grpc.html — "Channels are thread-safe."
    ``vertexai.Client`` wraps the google-genai SDK client which in turn uses a
    gRPC channel, so sharing a single instance across concurrent ``_clear_tmp``
    calls is safe (SK-43 thread-safety verification).  Under a concurrent cold
    start, two coroutines may both miss the cache and each construct a
    ``vertexai.Client`` before either populates it; ``lru_cache`` keeps exactly
    one entry and silently discards the duplicate — harmless wasted work because
    both instances are thread-safe per the gRPC-channel guarantee above (SK-49).

    ``maxsize=2`` covers the typical dev + prod environment in one process.
    Revisit if the ``client_cache_hit`` rate on the ``sandbox_pool.lease`` span
    (MER-E) drops below ~95% — that would signal multi-region or multi-project
    agent configs (SK-43).

    Lazily imports ``vertexai`` so this module remains importable in test
    environments without a live Vertex AI install — the same pattern used by
    ``_construct`` and ``_clear_tmp``.

    **Credential rotation note:** the google-auth library handles short-lived
    token refresh internally, so the cached client remains valid across the
    standard 1-hour ADC token cycle.  If the service account itself is revoked
    (e.g., incident-response key rotation), all ``_clear_tmp`` calls will begin
    returning 401/403 — the process must be recycled (Cloud Run rolling deploy)
    to pick up new credentials.  ``tmp_clear_failed=True`` in MER-E spans is
    the alerting path for this condition (SK-43).
    """
    import vertexai  # lazy — not required in tests

    return vertexai.Client(project=project, location=location)


class SandboxPool:
    """Process-wide pool of ``AgentEngineSandboxCodeExecutor`` instances.

    Keys: ``(account_id, config_id)``.  One sandbox per (account, agent) tuple.

    Eviction policy
    ---------------
    * **LRU cap** (``_MAX_ENTRIES=64``): when the 65th distinct key is inserted
      the least-recently-used entry is evicted.
    * **Idle TTL** (``_IDLE_TTL_SECONDS=900``): the background sweep thread
      (``_sweep_loop``) runs every ``_SWEEP_INTERVAL_SECONDS=60`` seconds and
      evicts entries whose last-used timestamp is older than the TTL.

    Concurrency
    -----------
    A single non-reentrant ``threading.Lock`` (``self._lock``) guards every
    structural read/write of the ``_pool`` dict and the ``_clearing`` map.
    Because ``_construct`` performs no I/O, holding the lock across construction
    is microsecond-cheap; the only slow work — ``_clear_tmp`` and the inner
    ``execute_code`` — runs with the lock released.  Eviction snapshots its span
    attributes under the lock and emits the Weave span afterwards so observability
    never holds the structural lock (hence a plain ``Lock``, not ``RLock``).

    ``_clear_tmp`` fires only on the **0 → 1 refcount transition** inside
    ``lease()``, not on every ``get_or_create`` call.  This eliminates the
    SK-42 CLOBBER hazard: the clear runs only when no caller is currently
    holding the executor, so it can never destroy in-flight ``/tmp`` data
    belonging to another caller.  A concurrent caller that arrives while the
    0 → 1 holder's clear is still in flight waits on a per-key
    ``threading.Event`` registered in ``_clearing`` before receiving the
    executor.

    Cleanup
    -------
    ``AgentEngineSandboxCodeExecutor`` exposes no ``aclose``/``close`` (its MRO
    is ``…→BaseCodeExecutor→pydantic BaseModel→object``).  Eviction therefore
    simply drops the pool's reference to the executor; the backing gRPC channel
    is reclaimed by GC.

    Eviction with active lease
    --------------------------
    LRU and TTL eviction paths that encounter ``refcount > 0`` mark the entry
    as ``pending_evict=True`` and leave the executor alive for in-flight
    callers.  The entry remains in the pool dict (still counts against the cap)
    but ``_evict_if_over_cap`` skips ``pending_evict=True`` entries when
    choosing the LRU candidate.  When refcount drops to 0 in ``_release``,
    the deferred eviction fires (the reference is dropped + entry removed).
    """

    _MAX_ENTRIES: int = 64
    _IDLE_TTL_SECONDS: int = 900
    _SWEEP_INTERVAL_SECONDS: int = 60
    # SK-35 LEAK-branch defence-in-depth: live probe (2026-05-27, 50/50 LEAK)
    # confirmed Vertex reuses container /tmp across executor sessions sharing
    # the same sandbox resource name.  Flag enabled to clear /tmp on the
    # 0 → 1 refcount transition inside lease().  See
    # docs/spike/sk-prd-02-cross-session-tmp-characterisation.md for findings.
    _CLEAR_TMP_ON_REUSE: bool = True
    _TMP_CLEAR_TIMEOUT_SECONDS: int = 5

    _PURGE_TMP_SCRIPT: str = (
        "import os as _os, shutil as _shutil\n"
        "for _e in _os.listdir('/tmp'):\n"
        "    _p = '/tmp/' + _e\n"
        "    try:\n"
        "        (_shutil.rmtree(_p, ignore_errors=True)\n"
        "         if _os.path.isdir(_p) else _os.unlink(_p))\n"
        "    except OSError:\n"
        "        pass\n"
    )

    def __init__(self) -> None:
        # OrderedDict maintains insertion/access order for LRU tracking.
        # Entry shape: (executor, last_used_monotonic_time, refcount, pending_evict)
        self._pool: OrderedDict[tuple[str, str], _PoolEntry] = OrderedDict()
        # Single non-reentrant structural lock guarding _pool and _clearing.
        self._lock = threading.Lock()
        # Background idle-sweep daemon thread + its stop signal.
        self._sweep_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Lazily created shared executor used to bound _clear_tmp's wall-clock
        # cost.  A shared pool (rather than a per-call ``with ThreadPoolExecutor``)
        # lets a hung Vertex call be abandoned on timeout without blocking the
        # caller in the executor's __exit__.
        self._clear_executor: ThreadPoolExecutor | None = None
        # Per-key threading.Events set by lease() after _clear_tmp() completes.
        # A concurrent caller that arrives while refcount is 0→1 and the clear
        # is in flight waits on this event before acquiring the executor.
        # Registered inside the structural lock in _acquire(); popped + set in
        # lease() once the clear finishes (or fails).
        self._clearing: dict[tuple[str, str], threading.Event] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def lease(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> Iterator[AgentEngineSandboxCodeExecutor]:
        """Context manager that leases a pooled executor for one use.

        Usage::

            with pool.lease(account_id=..., config_id=...) as executor:
                executor.execute_code(...)

        **Concurrency contract (SK-42):** ``_clear_tmp`` fires only on the
        0 → 1 refcount transition — i.e., only when this is the first active
        lease holder and no other caller's ``execute_code`` is in flight.
        Concurrent callers that arrive while ``refcount ≥ 1`` share the
        executor without triggering a clear, so no in-flight ``/tmp`` data
        is destroyed.

        **Exception safety:** every step after the refcount bump runs inside a
        single ``try/finally``.  The refcount is always decremented and the
        deferred-evict path always checked on exit, and a 0 → 1 holder's
        clearing ``Event`` is always ``set()`` (unblocking waiters) — even if
        ``_evict_if_over_cap`` or ``_clear_tmp`` raises.  This closes the window
        where an orphaned ``self._clearing[key]`` + refcount would permanently
        deadlock every future lease of the key.

        Emits a ``sandbox_pool.lease`` Weave span on entry (after
        construction and any clearing) carrying ``cleared_tmp``,
        ``tmp_clear_failed``, and ``client_cache_hit`` (whether ``_clear_tmp``
        reused the lru-cached ``vertexai.Client`` — SK-43), and a
        ``sandbox_pool.release`` span on exit.
        """
        key = (account_id, config_id)
        executor, _zero_to_one, clearing_event, cache_miss = self._acquire(key)

        # Everything after the refcount bump runs inside this try/finally so the
        # clearing event and refcount are always released.
        cleared_tmp = False
        tmp_clear_failed = False
        client_cache_hit = False
        try:
            if cache_miss:
                # Enforce the LRU cap for the freshly constructed entry.  Runs
                # here (not inside _acquire) so a raise lands in the finally
                # below and cannot orphan the clearing event / refcount.
                self._evict_if_over_cap()

            if clearing_event is not None:
                # We are the 0→1 transition holder responsible for clearing /tmp.
                # Finish the clear and then unblock any concurrent callers that
                # are waiting on the clearing event before receiving the executor.
                # Snapshot the cached-client hit count around the clear so the span
                # reports whether _clear_tmp reused the lru-cached vertexai.Client
                # (SK-43). Best-effort under concurrency: a hit credited by a
                # concurrent _clear_tmp could be attributed here; MER-E aggregates
                # over time windows so per-call jitter is tolerable.
                pre_hits = _get_vertexai_client.cache_info().hits
                try:
                    self._clear_tmp(executor)
                    cleared_tmp = True
                except Exception:
                    tmp_clear_failed = True
                    logger.warning(
                        "SandboxPool._clear_tmp failed; returning executor uncleared",
                        extra={"account_id": account_id, "config_id": config_id},
                    )
                finally:
                    client_cache_hit = _get_vertexai_client.cache_info().hits > pre_hits
                    # Pop before set so waiting callers see no event on retry.
                    with self._lock:
                        self._clearing.pop(key, None)
                    clearing_event.set()

            refcount_after = self._entry_refcount(key)
            with emit_sandbox_pool_span(
                "sandbox_pool.lease",
                {
                    "account_id": account_id,
                    "config_id": config_id,
                    "refcount_after": refcount_after,
                    "cleared_tmp": cleared_tmp,
                    "tmp_clear_failed": tmp_clear_failed,
                    "client_cache_hit": client_cache_hit,
                },
            ):
                pass

            yield executor
        finally:
            # Backstop: if our clearing event is still registered, we failed
            # before the clear block could set it (e.g. _evict_if_over_cap
            # raised).  Release it now so waiters unblock — they retry, find the
            # refcount back at 0, and reconstruct.  On the normal path the clear
            # block already popped it, so this is a no-op.  Checking the dict
            # (not a local) is safe: no concurrent caller can register a new
            # event for this key while we still hold the refcount.
            with self._lock:
                leaked_clearing = self._clearing.pop(key, None)
            if leaked_clearing is not None:
                leaked_clearing.set()
            triggered_evict = self._release(key)
            release_refcount = self._entry_refcount(key)
            with emit_sandbox_pool_span(
                "sandbox_pool.release",
                {
                    "account_id": account_id,
                    "config_id": config_id,
                    "refcount_after": release_refcount,
                    "triggered_pending_evict": triggered_evict,
                },
            ):
                pass

    def get_or_create(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Return a pooled executor for ``(account_id, config_id)``.

        **Diagnostic / test-only accessor.** Production callers MUST use
        ``lease()`` instead — only ``lease()`` tracks refcount and runs
        ``_clear_tmp`` at the correct 0 → 1 boundary (SK-42).

        On a cache hit the entry is LRU-bumped and its ``last_used`` timestamp
        refreshed.  On a miss a new executor is constructed and the LRU cap is
        enforced.

        A ``sandbox_pool.get`` Weave span is emitted after cap enforcement so
        that ``pool_size_after`` reflects post-eviction size for cap-triggering
        misses.  Span emission occurs outside the structural lock to keep the
        lock window tight.

        **AH-77 §G / AH-80 scope-out note:** The AH-77 Item G per-key Future
        pattern from McpToolsetPool (``mcp_pool.py``) is intentionally **not**
        applied here.  After SK-42 (DESIGN-REVIEW-LOG Review 38), ``_construct``
        is purely I/O-free (``_sandbox_resource_name`` regex parse + lazy ADK
        import); holding the single non-stripe ``threading.Lock`` across it is
        microsecond-cheap.  The stripe-collision pathology that Item G fixes in
        McpToolsetPool (lock held across 30-second-bounded Firestore + ADK
        construction) does not exist in SandboxPool.  See DESIGN-REVIEW-LOG
        Review 40 for the full rationale.  If ``_construct`` is ever changed to
        perform I/O this note must be revisited.
        """
        key = (account_id, config_id)
        cache_hit: bool
        with self._lock:
            entry = self._pool.get(key)
            now = time.monotonic()
            if entry is not None:
                executor, _, refcount, pending_evict = entry
                self._pool.move_to_end(key)
                self._pool[key] = (executor, now, refcount, pending_evict)
                cache_hit = True
            else:
                executor = self._construct(account_id=account_id, config_id=config_id)
                self._pool[key] = (executor, now, 0, False)
                cache_hit = False

        # Cap enforcement runs outside the structural lock so that evict() can
        # re-acquire the lock for the LRU entry without deadlocking.
        if not cache_hit:
            self._evict_if_over_cap()

        # pool_size_after is sampled outside the lock; concurrent inserts can
        # shift it by ±1 between eviction and the snapshot.
        with emit_sandbox_pool_span(
            "sandbox_pool.get",
            {
                "account_id": account_id,
                "config_id": config_id,
                "cache_hit": cache_hit,
                "pool_size_after": len(self._pool),
            },
        ):
            pass

        return executor

    def evict(
        self,
        key: tuple[str, str],
        *,
        stale_before: float | None = None,
        reason: Literal["lru", "ttl", "manual"] = "manual",
    ) -> None:
        """Remove the entry for ``key`` and drop its executor reference.

        No-op if the key is not present.  ``AgentEngineSandboxCodeExecutor`` has
        no ``aclose``/``close`` (its MRO is pydantic ``BaseModel``), so eviction
        simply removes the entry; the backing gRPC channel is reclaimed by GC.

        ``stale_before`` (monotonic timestamp): when provided the entry is only
        evicted if its ``last_used`` timestamp is strictly less than this value.
        This closes the TOCTOU window in ``sweep_idle``: the snapshot is taken
        under the lock but a concurrent ``lease()`` may refresh the timestamp
        between the snapshot and this re-acquisition, so an entry refreshed in
        that window is skipped rather than incorrectly removed.

        **Active-lease deferral (SK-42):** if the entry's ``refcount > 0``
        the eviction is deferred — ``pending_evict`` is set to ``True`` and
        the executor is kept.  The entry remains in the pool dict
        (``_evict_if_over_cap`` skips it when choosing the LRU candidate) so
        that ``_release`` can find and remove it when refcount drops to 0.

        ``reason`` is forwarded to the ``sandbox_pool.evict`` Weave span so
        MER-E can distinguish LRU-cap, TTL-sweep, and direct-caller evictions.
        Internal callers pass ``reason="lru"`` or ``reason="ttl"``; external
        callers receive the default ``"manual"``.

        Span emission occurs outside the structural lock (attrs are snapshotted
        inside, emitted after release) to keep the lock window tight.
        """
        account_id, config_id = key
        deferred = False
        with self._lock:
            entry = self._pool.get(key)
            if entry is None:
                # No-op evictions still emit a span per the PRD — truthful
                # pool_size_after is still useful signal (TTL-vs-refresh races).
                pool_size_after = len(self._pool)
            else:
                _executor, last_used, refcount, _pending_evict = entry
                if stale_before is not None and last_used >= stale_before:
                    pool_size_after = len(self._pool)
                elif refcount > 0:
                    # Active lease — defer eviction; mark pending_evict and keep
                    # executor alive.  Entry stays in the pool dict so _release
                    # can find it; _evict_if_over_cap skips pending_evict entries
                    # when choosing the next LRU candidate.
                    self._pool[key] = (_executor, last_used, refcount, True)
                    pool_size_after = len(self._pool)
                    deferred = True
                    logger.info(
                        "SandboxPool eviction deferred: active lease in progress",
                        extra={
                            "key": key,
                            "refcount": refcount,
                            "reason": reason,
                        },
                    )
                else:
                    del self._pool[key]
                    pool_size_after = len(self._pool)

        with emit_sandbox_pool_span(
            "sandbox_pool.evict",
            {
                "account_id": account_id,
                "config_id": config_id,
                "reason": reason,
                "pool_size_after": pool_size_after,
                "deferred": deferred,
            },
        ):
            pass

    def sweep_idle(self) -> None:
        """Evict entries whose last-used time predates the idle TTL cutoff.

        Snapshots the stale keys under the lock (materialised into a list) so
        the pool dict is not mutated during traversal by a concurrent lease.
        Passes ``stale_before`` to ``evict`` so that entries refreshed between
        the snapshot and the lock re-acquisition are not incorrectly removed.
        """
        cutoff = time.monotonic() - self._IDLE_TTL_SECONDS
        with self._lock:
            stale_keys = [
                k for k, (_, last, _, _) in self._pool.items() if last < cutoff
            ]
        for k in stale_keys:
            self.evict(k, stale_before=cutoff, reason="ttl")

    def start(self) -> None:
        """Arm the background idle-sweep daemon thread.

        Idempotent — calling ``start()`` while the sweep thread is already
        running has no effect.  Safe to call from any thread and from both
        runtime entrypoints (FastAPI lifespan + Agent Engine before_agent
        callback) on the same instance.
        """
        with self._lock:
            if self._sweep_thread is not None and self._sweep_thread.is_alive():
                return
            self._stop_event.clear()
            self._sweep_thread = threading.Thread(
                target=self._sweep_loop,
                name="sandbox-pool-sweep",
                daemon=True,
            )
            self._sweep_thread.start()

    def stop(self) -> None:
        """Signal the background sweep thread to exit and release resources.

        No-op if the pool was never started.  Joins the sweep thread (bounded)
        and shuts the ``_clear_tmp`` executor down without waiting on any
        in-flight (possibly hung) clear.
        """
        self._stop_event.set()
        thread = self._sweep_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self._SWEEP_INTERVAL_SECONDS + 1)
        self._sweep_thread = None
        clear_executor = self._clear_executor
        if clear_executor is not None:
            clear_executor.shutdown(wait=False)
            self._clear_executor = None

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def _entry_refcount(self, key: tuple[str, str]) -> int:
        """Return the current refcount for ``key``, or 0 if absent.

        Exposed for unit tests only — production callers should not need this.
        """
        entry = self._pool.get(key)
        if entry is None:
            return 0
        _, _, refcount, _ = entry
        return refcount

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _acquire(
        self, key: tuple[str, str]
    ) -> tuple[AgentEngineSandboxCodeExecutor, bool, threading.Event | None, bool]:
        """Increment refcount for ``key``, constructing on miss.

        Returns ``(executor, zero_to_one, clearing_event, cache_miss)`` where:
        - ``zero_to_one`` is True when this call transitioned refcount 0 → 1.
        - ``clearing_event`` is a non-None ``threading.Event`` that the caller
          MUST set (after ``_clear_tmp`` completes) when ``zero_to_one`` is True
          and ``_CLEAR_TMP_ON_REUSE`` is set.  Concurrent callers that see the
          event in ``self._clearing`` wait for it before receiving the executor,
          closing the window where a second caller could receive the executor
          while the first caller's ``_clear_tmp`` is still running.
        - ``cache_miss`` is True when this call constructed a new executor; the
          caller (``lease()``) enforces the LRU cap for it.

        Called by ``lease()``.  All structural work runs under ``self._lock``
        to preserve single-flight construction semantics and an atomic refcount
        bump; the clearing event is registered *inside* the lock so no
        concurrent caller can increment refcount (and receive the executor)
        before the event is visible to them.  When a clear is already in flight
        for ``key`` the call releases the lock, waits on that event, and retries.

        Cap enforcement is intentionally NOT performed here: it would run after
        the refcount bump + clearing-event registration, and if it raised it
        would orphan both (permanent per-key deadlock).  ``lease()`` runs it
        inside the same ``try/finally`` that guarantees their release.

        **AH-77 §G / AH-80 scope-out note:** The per-key Future pattern from
        ``mcp_pool.py:184-219`` is intentionally not applied here.  After SK-42,
        ``_construct`` is I/O-free; the single ``threading.Lock`` held across it
        is microsecond-cheap.  The correct single-flight mechanism for SandboxPool
        is the per-key ``threading.Event`` in ``self._clearing`` (registered
        inside the lock above) — that is the only point where concurrent callers
        need to wait (the 0 → 1 ``_clear_tmp`` boundary).  See DESIGN-REVIEW-LOG
        Review 40.  If ``_construct`` is changed to perform I/O this note must be
        revisited.
        """
        account_id, config_id = key
        cache_miss: bool = False
        zero_to_one: bool = False
        clearing_event_out: threading.Event | None = None
        executor: Any = None

        while True:
            to_wait: threading.Event | None = None
            with self._lock:
                pending = self._clearing.get(key)
                if pending is not None:
                    # A clear is in flight for this key — can't wait while
                    # holding the lock, so capture it and release.
                    to_wait = pending
                else:
                    entry = self._pool.get(key)
                    now = time.monotonic()
                    if entry is not None:
                        executor, _, refcount, pending_evict = entry
                        new_refcount = refcount + 1
                        zero_to_one = refcount == 0
                        self._pool.move_to_end(key)
                        self._pool[key] = (executor, now, new_refcount, pending_evict)
                        cache_miss = False
                        if zero_to_one and self._CLEAR_TMP_ON_REUSE:
                            # Register event inside the lock so concurrent
                            # callers always see it before incrementing refcount.
                            clearing_event_out = threading.Event()
                            self._clearing[key] = clearing_event_out
                    else:
                        executor = self._construct(
                            account_id=account_id, config_id=config_id
                        )
                        self._pool[key] = (executor, now, 1, False)
                        zero_to_one = True
                        cache_miss = True
                        if self._CLEAR_TMP_ON_REUSE:
                            clearing_event_out = threading.Event()
                            self._clearing[key] = clearing_event_out

            if to_wait is not None:
                to_wait.wait()
                continue  # retry after the in-flight clear completes

            break

        return executor, zero_to_one, clearing_event_out, cache_miss

    def _release(self, key: tuple[str, str]) -> bool:
        """Decrement refcount for ``key`` and fire deferred eviction on 0.

        Returns ``True`` if a deferred eviction was triggered.

        Called by ``lease()`` on exit.  Runs under the structural lock to
        atomically decrement the refcount and check ``pending_evict``.  If
        ``pending_evict=True`` and ``refcount`` just dropped to 0, removes the
        entry (dropping the executor reference — there is no ``aclose``).
        """
        triggered = False
        with self._lock:
            entry = self._pool.get(key)
            if entry is None:
                # Entry was already removed (e.g. manual evict raced with release).
                return False
            executor, last_used, refcount, pending_evict = entry
            if refcount == 0:
                # Invariant violation: _release called more times than _acquire.
                # Log and skip rather than silently clamping so MER-E can alert.
                logger.error(
                    "SandboxPool._release: refcount underflow for key %s — double release?",
                    key,
                )
                return False
            new_refcount = refcount - 1
            if new_refcount == 0 and pending_evict:
                # Deferred eviction: drop the entry (and its executor reference).
                del self._pool[key]
                triggered = True
            else:
                self._pool[key] = (executor, last_used, new_refcount, pending_evict)

        return triggered

    def _construct(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Construct a new ``AgentEngineSandboxCodeExecutor`` for the key.

        ADK is imported lazily to keep the module importable in test
        environments without a live ADK install — the same pattern used by
        ``agent_factory/mcp.py:372``.

        This performs no network I/O: ``AgentEngineSandboxCodeExecutor.__init__``
        only parses the resource-name regex.  The real sandbox cold-start
        (``sandboxes.create``) happens inside the inner ``execute_code`` — which
        is why holding ``self._lock`` across construction is cheap.

        Resource limits and network policy are set per SK-PRD-00 spike findings
        (``docs/spike-agent-engine-sandbox-findings.md``); the sandbox resource
        name format is confirmed in SK-26 (see ``_sandbox_resource_name``).
        """
        from google.adk.code_executors.agent_engine_sandbox_code_executor import (
            AgentEngineSandboxCodeExecutor,
        )

        return AgentEngineSandboxCodeExecutor(
            sandbox_resource_name=_sandbox_resource_name(account_id, config_id),
        )

    def _get_clear_executor(self) -> ThreadPoolExecutor:
        """Return the lazily-created shared executor for ``_clear_tmp`` timeouts."""
        with self._lock:
            if self._clear_executor is None:
                self._clear_executor = ThreadPoolExecutor(
                    thread_name_prefix="sandbox-clear-tmp",
                )
            return self._clear_executor

    def _clear_tmp(self, executor: AgentEngineSandboxCodeExecutor) -> None:
        """Purge /tmp inside the sandbox container (SK-35 LEAK-branch defence-in-depth).

        Called on the 0 → 1 refcount transition inside ``lease()`` when
        ``_CLEAR_TMP_ON_REUSE`` is ``True``.  Only fires when no other caller
        holds the executor (refcount was 0 before this lease acquired it), so it
        never races with in-flight ``execute_code`` calls from concurrent
        leaseholders (SK-42).

        Best-effort: ``TimeoutError`` and any other exception propagate to the
        caller (``lease()``), which catches and logs them so the executor is
        still returned.

        The Vertex SDK call is synchronous and is run on a **shared**
        ``ThreadPoolExecutor`` so its wall-clock cost can be bounded via
        ``future.result(timeout=…)``; on timeout the future is abandoned (the
        worker thread runs on) rather than blocked-on, so a hung Vertex call
        cannot stall the lease.  Uses ``_get_vertexai_client`` (module-level
        ``@functools.lru_cache(maxsize=2)``) so the client is constructed once
        per ``(project, location)`` pair for the lifetime of the Cloud Run
        instance.  Thread-safety is verified in SK-43: gRPC channels are
        documented thread-safe (see ``_get_vertexai_client`` docstring) so
        sharing a single cached instance across concurrent ``_clear_tmp`` calls
        is correct.

        Defensive guard: if ``sandbox_resource_name`` is missing or not a
        non-empty string (e.g. unit-test Mock executor, or a future regression
        in ``_sandbox_resource_name``), log a WARNING and return without
        issuing a network call.
        """
        resource_name = getattr(executor, "sandbox_resource_name", "")
        if not isinstance(resource_name, str) or not resource_name:
            logger.warning(
                "SandboxPool._clear_tmp skipped: missing or non-string sandbox_resource_name",
                extra={
                    "resource_name_type": type(resource_name).__name__,
                    "resource_name_empty": not resource_name,
                },
            )
            return

        project = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

        client = _get_vertexai_client(project, location)
        future = self._get_clear_executor().submit(
            client.agent_engines.sandboxes.execute_code,
            name=resource_name,
            input_data={"code": self._PURGE_TMP_SCRIPT},
        )
        future.result(timeout=self._TMP_CLEAR_TIMEOUT_SECONDS)

    def _evict_if_over_cap(self) -> None:
        """Evict the LRU entry until the pool is at or below ``_MAX_ENTRIES``.

        Each iteration re-checks the cap and picks the oldest non-deferred
        victim **under the structural lock**, then releases the lock and calls
        ``evict`` (which re-acquires it) — so the lock is never held across an
        ``evict`` call (it would self-deadlock on the non-reentrant lock) and
        Weave span emission stays lock-free.  OrderedDict iteration order is
        oldest-first because evictions ``del`` and hits ``move_to_end`` — the
        LRU invariant.

        Concurrent passes (from simultaneous misses) are each serialised at the
        per-iteration lock; ``evict`` is idempotent, so a victim picked by two
        passes is removed once and a no-op the second time.

        Entries with ``pending_evict=True`` are already deferred and have been
        conceptually removed from the LRU ordering; they are skipped here so
        the pool does not double-evict them.
        """
        while True:
            oldest_key: tuple[str, str] | None = None
            with self._lock:
                if len(self._pool) <= self._MAX_ENTRIES:
                    return
                for k, (_, _, _, pending) in self._pool.items():
                    if not pending:
                        oldest_key = k
                        break
            if oldest_key is None:
                # All entries are pending_evict — nothing safe to remove now.
                return
            self.evict(oldest_key, reason="lru")

    def _sweep_loop(self) -> None:
        """Background thread body that periodically sweeps idle entries.

        Waits on ``_stop_event`` with the sweep interval as a timeout: the wait
        returns ``True`` when ``stop()`` sets the event (exit the loop) and
        ``False`` on timeout (run a sweep).  This makes shutdown immediate
        rather than waiting out a full sleep interval.
        """
        while not self._stop_event.wait(self._SWEEP_INTERVAL_SECONDS):
            try:
                self.sweep_idle()
            except Exception:
                logger.exception(
                    "SandboxPool._sweep_loop: sweep_idle() raised unexpectedly"
                )
