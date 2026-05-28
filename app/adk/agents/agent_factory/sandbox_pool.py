"""Process-wide pool of AgentEngineSandboxCodeExecutor instances.

SK-PRD-02 §4.6 — SandboxPool.

Under AH-PRD-09's per-turn dispatch model the agent factory rebuilds every
specialist ``LlmAgent`` on each chat turn.  Constructing a fresh
``AgentEngineSandboxCodeExecutor`` per rebuild would pay a sandbox cold-start
on every message — latency-dominating for any sandbox-attached specialist.
This pool keeps executor instances alive across ``LlmAgent`` rebuilds so the
sandbox process outlives any single agent instance.

Design intentionally mirrors AH-PRD-09's ``McpToolsetPool`` (RFC §4.8) for
operational consistency: LRU cap, idle TTL, ``aclose()``-on-eviction,
per-key striped locks.

Lifecycle: the pool is a process-wide singleton.  Call ``start()`` once after
construction (from the Cloud Run startup path, owned by SK-26) to arm the
background idle-sweep task.  Call ``stop()`` on graceful shutdown to cancel it.
Both methods are no-ops if called out of order.

``AgentEngineSandboxCodeExecutor`` is lazily imported inside ``_construct`` so
this module remains importable in test environments that do not have a live ADK
install — matching the pattern in ``agent_factory/mcp.py:372``.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import os
import time
from collections import OrderedDict
from collections.abc import AsyncGenerator
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
    calls is safe (SK-43 thread-safety verification).

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
    * **Idle TTL** (``_IDLE_TTL_SECONDS=900``): the background sweep task
      (``_sweep_loop``) runs every ``_SWEEP_INTERVAL_SECONDS=60`` seconds and
      evicts entries whose last-used timestamp is older than the TTL.

    Concurrency
    -----------
    A 32-slot striped ``asyncio.Lock`` map provides per-key single-flight
    semantics: concurrent ``lease()`` calls for the **same** key all wait
    on the same lock and receive the single constructed executor; concurrent
    calls for **different** keys that hash to different stripes do not
    serialise.

    ``_clear_tmp`` fires only on the **0 → 1 refcount transition** inside
    ``lease().__aenter__``, not on every ``get_or_create`` call.  This
    eliminates the SK-42 CLOBBER hazard: the clear runs only when no caller
    is currently holding the executor, so it can never destroy in-flight
    ``/tmp`` data belonging to another caller.

    Cleanup
    -------
    ``aclose()`` is invoked on every executor before its reference is dropped.
    Failures in ``aclose()`` are caught, logged, and swallowed — pool
    integrity takes priority over retention of a possibly-broken executor.

    Eviction with active lease
    --------------------------
    LRU and TTL eviction paths that encounter ``refcount > 0`` mark the entry
    as ``pending_evict=True`` and leave the executor alive for in-flight
    callers.  The entry remains in the pool dict (still counts against the cap)
    but ``_evict_if_over_cap`` skips ``pending_evict=True`` entries when
    choosing the LRU candidate.  When refcount drops to 0 in ``_release``,
    the deferred eviction fires (``aclose()`` + pool removal).
    """

    _MAX_ENTRIES: int = 64
    _IDLE_TTL_SECONDS: int = 900
    _SWEEP_INTERVAL_SECONDS: int = 60
    # SK-35 LEAK-branch defence-in-depth: live probe (2026-05-27, 50/50 LEAK)
    # confirmed Vertex reuses container /tmp across executor sessions sharing
    # the same sandbox resource name.  Flag enabled to clear /tmp on the
    # 0 → 1 refcount transition inside lease().__aenter__.  See
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
        # Lazily initialised per-stripe lock map (32 slots).
        self._stripe_locks: dict[int, asyncio.Lock] = {}
        self._sweep_task: asyncio.Task[None] | None = None
        # Serialises cap-enforcement passes so concurrent misses that both exit
        # their stripe locks cannot race on next(iter(self._pool)).
        self._cap_lock: asyncio.Lock = asyncio.Lock()
        # Per-key asyncio.Events set by lease() after _clear_tmp() completes.
        # A concurrent caller that arrives while refcount is 0→1 and the clear
        # is in flight waits on this event before acquiring the executor.
        # Registered inside the stripe lock in _acquire(); deleted + set in
        # lease()'s finally block once the clear finishes (or fails).
        self._clearing: dict[tuple[str, str], asyncio.Event] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def lease(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AsyncGenerator[AgentEngineSandboxCodeExecutor, None]:
        """Async context manager that leases a pooled executor for one use.

        Usage::

            async with pool.lease(account_id=..., config_id=...) as executor:
                await executor.execute_code(...)

        **Concurrency contract (SK-42):** ``_clear_tmp`` fires only on the
        0 → 1 refcount transition — i.e., only when this is the first active
        lease holder and no other caller's ``execute_code`` is in flight.
        Concurrent callers that arrive while ``refcount ≥ 1`` share the
        executor without triggering a clear, so no in-flight ``/tmp`` data
        is destroyed.

        **Exception safety:** ``__aexit__`` is guaranteed by Python's
        ``async with`` protocol regardless of whether the body raises.
        The refcount is always decremented and the deferred-evict path is
        always checked on exit.

        Emits a ``sandbox_pool.lease`` Weave span on entry (after
        construction and any clearing) carrying ``cleared_tmp``,
        ``tmp_clear_failed``, and ``client_cache_hit`` (whether ``_clear_tmp``
        reused the lru-cached ``vertexai.Client`` — SK-43), and a
        ``sandbox_pool.release`` span on exit.
        """
        key = (account_id, config_id)
        executor, _zero_to_one, clearing_event = await self._acquire(key)

        cleared_tmp = False
        tmp_clear_failed = False
        client_cache_hit = False
        if clearing_event is not None:
            # We are the 0→1 transition holder responsible for clearing /tmp.
            # Finish the clear and then unblock any concurrent callers that
            # are waiting on the clearing event before receiving the executor.
            # Snapshot the cached-client hit count around the clear so the span
            # reports whether _clear_tmp reused the lru-cached vertexai.Client
            # (SK-43). Best-effort under concurrency: a hit credited by a
            # concurrent _clear_tmp on another stripe could be attributed here;
            # MER-E aggregates over time windows so per-call jitter is tolerable.
            pre_hits = _get_vertexai_client.cache_info().hits
            try:
                await self._clear_tmp(executor)
                cleared_tmp = True
            except Exception:
                tmp_clear_failed = True
                logger.warning(
                    "SandboxPool._clear_tmp failed; returning executor uncleared",
                    extra={"account_id": account_id, "config_id": config_id},
                )
            finally:
                client_cache_hit = _get_vertexai_client.cache_info().hits > pre_hits
                # Delete before set so waiting callers see no event on retry.
                del self._clearing[key]
                clearing_event.set()

        refcount_after = self._entry_refcount(key)
        async with emit_sandbox_pool_span(
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

        try:
            yield executor
        finally:
            triggered_evict = await self._release(key)
            release_refcount = self._entry_refcount(key)
            async with emit_sandbox_pool_span(
                "sandbox_pool.release",
                {
                    "account_id": account_id,
                    "config_id": config_id,
                    "refcount_after": release_refcount,
                    "triggered_pending_evict": triggered_evict,
                },
            ):
                pass

    async def get_or_create(
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
        misses.  Span emission occurs outside the stripe lock to keep the lock
        window tight.
        """
        key = (account_id, config_id)
        cache_hit: bool
        async with self._stripe(key):
            entry = self._pool.get(key)
            now = time.monotonic()
            if entry is not None:
                executor, _, refcount, pending_evict = entry
                self._pool.move_to_end(key)
                self._pool[key] = (executor, now, refcount, pending_evict)
                cache_hit = True
            else:
                executor = await self._construct(
                    account_id=account_id, config_id=config_id
                )
                self._pool[key] = (executor, now, 0, False)
                cache_hit = False

        # Cap enforcement runs outside the stripe lock so that evict() can
        # acquire the stripe lock for the LRU entry without deadlocking.
        if not cache_hit:
            await self._evict_if_over_cap()

        # pool_size_after is sampled outside the lock; concurrent inserts can
        # shift it by ±1 between eviction and the snapshot.
        async with emit_sandbox_pool_span(
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

    async def evict(
        self,
        key: tuple[str, str],
        *,
        stale_before: float | None = None,
        reason: Literal["lru", "ttl", "manual"] = "manual",
    ) -> None:
        """Remove the entry for ``key`` and close its executor via ``aclose()``.

        No-op if the key is not present.  ``aclose()`` failures are caught and
        logged; the entry is removed regardless so the pool remains consistent.

        ``stale_before`` (monotonic timestamp): when provided the entry is only
        evicted if its ``last_used`` timestamp is strictly less than this value.
        This closes the TOCTOU window in ``sweep_idle``: the snapshot is taken
        outside the lock but the timestamp is re-validated inside it, so an
        entry that was refreshed between the snapshot and the lock acquisition
        is skipped rather than incorrectly closed.

        **Active-lease deferral (SK-42):** if the entry's ``refcount > 0``
        the eviction is deferred — ``pending_evict`` is set to ``True`` and
        the executor is NOT closed.  The entry remains in the pool dict
        (``_evict_if_over_cap`` skips it when choosing the LRU candidate) so
        that ``_release`` can find and close it when refcount drops to 0.

        ``reason`` is forwarded to the ``sandbox_pool.evict`` Weave span so
        MER-E can distinguish LRU-cap, TTL-sweep, and direct-caller evictions.
        Internal callers pass ``reason=\"lru\"`` or ``reason=\"ttl\"``; external
        callers receive the default ``\"manual\"``.

        Span emission occurs outside the stripe lock (attrs are snapshotted
        inside, emitted after release) to keep the lock window tight.
        """
        account_id, config_id = key
        deferred = False
        async with self._stripe(key):
            entry = self._pool.get(key)
            if entry is None:
                # No-op evictions still emit a span per the PRD — truthful
                # pool_size_after is still useful signal (TTL-vs-refresh races).
                pool_size_after = len(self._pool)
            else:
                executor, last_used, refcount, _pending_evict = entry
                if stale_before is not None and last_used >= stale_before:
                    pool_size_after = len(self._pool)
                elif refcount > 0:
                    # Active lease — defer eviction; mark pending_evict and keep
                    # executor alive.  Entry stays in the pool dict so _release
                    # can find it; _evict_if_over_cap skips pending_evict entries
                    # when choosing the next LRU candidate.
                    self._pool[key] = (executor, last_used, refcount, True)
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
                    try:
                        await executor.aclose()
                    except Exception:
                        logger.exception(
                            "SandboxPool eviction aclose() failed",
                            extra={"key": key},
                        )

        async with emit_sandbox_pool_span(
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

    async def sweep_idle(self) -> None:
        """Evict entries whose last-used time predates the idle TTL cutoff.

        Collects stale keys into a list before iterating so the pool dict is
        not mutated during traversal.  Passes ``stale_before`` to ``evict``
        so that entries refreshed between the snapshot and the lock acquisition
        are not incorrectly closed.
        """
        cutoff = time.monotonic() - self._IDLE_TTL_SECONDS
        stale_keys = [k for k, (_, last, _, _) in self._pool.items() if last < cutoff]
        for k in stale_keys:
            await self.evict(k, stale_before=cutoff, reason="ttl")

    def start(self) -> None:
        """Arm the background idle-sweep task.

        Must be called after the asyncio event loop is running (i.e., from
        async context or Cloud Run startup).  Idempotent — calling ``start()``
        while the task is already running has no effect.
        """
        if self._sweep_task is None or self._sweep_task.done():
            self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def stop(self) -> None:
        """Cancel the background sweep task and wait for it to finish.

        No-op if the pool was never started.
        """
        if self._sweep_task is not None and not self._sweep_task.done():
            self._sweep_task.cancel()
            await asyncio.gather(self._sweep_task, return_exceptions=True)
        self._sweep_task = None

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

    def _stripe(self, key: tuple[str, str]) -> asyncio.Lock:
        """Return the per-key stripe lock (lazily initialised)."""
        idx = hash(key) % 32
        return self._stripe_locks.setdefault(idx, asyncio.Lock())

    async def _acquire(
        self, key: tuple[str, str]
    ) -> tuple[AgentEngineSandboxCodeExecutor, bool, asyncio.Event | None]:
        """Increment refcount for ``key``, constructing on miss.

        Returns ``(executor, zero_to_one, clearing_event)`` where:
        - ``zero_to_one`` is True when this call transitioned refcount 0 → 1.
        - ``clearing_event`` is a non-None asyncio.Event that the caller MUST
          set (after ``_clear_tmp`` completes) when ``zero_to_one`` is True and
          ``_CLEAR_TMP_ON_REUSE`` is set.  Concurrent callers that see the event
          in ``self._clearing`` wait for it before receiving the executor, closing
          the window where a second caller could receive the executor while the
          first caller's ``_clear_tmp`` is still running.

        Called by ``lease().__aenter__``.  Runs under the stripe lock to
        preserve single-flight construction semantics and atomic refcount bump.
        The clearing event is registered *inside* the stripe lock so no
        concurrent caller can increment refcount (and receive the executor)
        before the event is visible to them.

        Cap enforcement fires outside the lock (same as ``get_or_create``) to
        avoid a deadlock when the LRU key hashes to the same stripe.
        """
        account_id, config_id = key
        cache_miss: bool = False
        zero_to_one: bool = False
        clearing_event_out: asyncio.Event | None = None
        executor: Any

        while True:
            # Wait for any in-progress _clear_tmp on this key before acquiring
            # the stripe lock.  The event is registered inside the lock in a
            # previous _acquire() call, so it is always visible here.
            pending = self._clearing.get(key)
            if pending is not None:
                await pending.wait()
                continue  # re-check: a new clear might have started immediately

            to_wait: asyncio.Event | None = None
            async with self._stripe(key):
                # Double-check inside the lock: another coroutine may have
                # registered a clearing event between our outer check above and
                # acquiring the lock.
                pending_inner = self._clearing.get(key)
                if pending_inner is not None:
                    # Can't await inside the lock; save and break out.
                    to_wait = pending_inner
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
                            clearing_event_out = asyncio.Event()
                            self._clearing[key] = clearing_event_out
                    else:
                        executor = await self._construct(
                            account_id=account_id, config_id=config_id
                        )
                        self._pool[key] = (executor, now, 1, False)
                        zero_to_one = True
                        cache_miss = True
                        if self._CLEAR_TMP_ON_REUSE:
                            clearing_event_out = asyncio.Event()
                            self._clearing[key] = clearing_event_out

            if to_wait is not None:
                await to_wait.wait()
                continue  # retry after in-lock-detected clear completes

            break

        if cache_miss:
            await self._evict_if_over_cap()

        return executor, zero_to_one, clearing_event_out

    async def _release(self, key: tuple[str, str]) -> bool:
        """Decrement refcount for ``key`` and fire deferred eviction on 0.

        Returns ``True`` if a deferred eviction was triggered.

        Called by ``lease().__aexit__``.  Runs under the stripe lock to
        atomically decrement the refcount and check ``pending_evict``.
        If ``pending_evict=True`` and ``refcount`` just dropped to 0,
        performs the deferred ``aclose()`` and removes the entry.
        """
        triggered = False
        async with self._stripe(key):
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
                # Deferred eviction: close executor and remove entry now.
                del self._pool[key]
                triggered = True
                try:
                    await executor.aclose()
                except Exception:
                    logger.exception(
                        "SandboxPool deferred-evict aclose() failed",
                        extra={"key": key},
                    )
            else:
                self._pool[key] = (executor, last_used, new_refcount, pending_evict)

        return triggered

    async def _construct(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Construct a new ``AgentEngineSandboxCodeExecutor`` for the key.

        ADK is imported lazily to keep the module importable in test
        environments without a live ADK install — the same pattern used by
        ``agent_factory/mcp.py:372``.

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

    async def _clear_tmp(self, executor: AgentEngineSandboxCodeExecutor) -> None:
        """Purge /tmp inside the sandbox container (SK-35 LEAK-branch defence-in-depth).

        Called on the 0 → 1 refcount transition inside ``lease().__aenter__``
        when ``_CLEAR_TMP_ON_REUSE`` is ``True``.  Only fires when no other
        caller holds the executor (refcount was 0 before this lease acquired
        it), so it never races with in-flight ``execute_code`` calls from
        concurrent leaseholders (SK-42).

        Best-effort: ``asyncio.TimeoutError`` and any other exception propagate
        to the caller (``lease().__aenter__``), which catches and logs them so
        the executor is still returned.

        The Vertex SDK call is synchronous, so it runs via ``asyncio.to_thread``
        to avoid blocking the event loop.  Uses ``_get_vertexai_client`` (module-
        level ``@functools.lru_cache(maxsize=2)``) so the client is constructed
        once per ``(project, location)`` pair for the lifetime of the Cloud Run
        instance rather than on every call.  Thread-safety is verified in SK-43:
        gRPC channels are documented thread-safe (see ``_get_vertexai_client``
        docstring) so sharing a single cached instance across concurrent
        ``_clear_tmp`` calls is correct.

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
        await asyncio.wait_for(
            asyncio.to_thread(
                client.agent_engines.sandboxes.execute_code,
                name=resource_name,
                input_data={"code": self._PURGE_TMP_SCRIPT},
            ),
            timeout=self._TMP_CLEAR_TIMEOUT_SECONDS,
        )

    async def _evict_if_over_cap(self) -> None:
        """Evict the LRU entry until the pool is at or below ``_MAX_ENTRIES``.

        Held under ``_cap_lock`` to serialise concurrent eviction passes:
        multiple concurrent ``lease()`` / ``get_or_create`` misses each insert
        an entry then race here, and without the lock they could both call
        ``next(iter(self._pool))`` concurrently while the other is mid-eviction.
        The ``while`` loop re-checks the cap after each eviction so transiently
        over-cap states (from concurrent inserts that slip through) are still
        corrected.  OrderedDict iteration order is oldest-first because evictions
        call ``del`` and hits call ``move_to_end`` — the LRU invariant.

        Entries with ``pending_evict=True`` are already deferred and have been
        conceptually removed from the LRU ordering; they are skipped here so
        the pool does not double-evict them.
        """
        async with self._cap_lock:
            while len(self._pool) > self._MAX_ENTRIES:
                # Find oldest non-deferred entry to evict.
                oldest_key: tuple[str, str] | None = None
                for k, (_, _, _, pending) in self._pool.items():
                    if not pending:
                        oldest_key = k
                        break
                if oldest_key is None:
                    # All entries are pending_evict — nothing safe to close now.
                    break
                await self.evict(oldest_key, reason="lru")

    async def _sweep_loop(self) -> None:
        """Background coroutine that periodically sweeps idle entries."""
        while True:
            await asyncio.sleep(self._SWEEP_INTERVAL_SECONDS)
            try:
                await self.sweep_idle()
            except Exception:
                logger.exception(
                    "SandboxPool._sweep_loop: sweep_idle() raised unexpectedly"
                )
