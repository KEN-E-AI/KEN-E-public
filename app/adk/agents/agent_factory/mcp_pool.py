"""Process-wide pool of ADK McpToolset instances (AH-PRD-09 Phase 3).

Prevents SSE connection leaks that occur when the per-turn specialist resolver
(Phase 2) rebuilds each specialist every turn, opening new MCP SSE connections
on every cold build without closing the previous ones.

Pool characteristics:
* LRU cap of 128 entries — oldest entry is evicted when cap is reached.
* Idle-TTL of 600 s (10 min) — entries unused for 10 minutes are closed by the
  background sweep.
* 60-second background sweep interval — background task that walks the pool and
  evicts TTL-expired entries (armed via ``start()``; dormant until then).
* 32-slot striped ``threading.Lock`` for per-key single-flight semantics —
  concurrent pool lookups for the same key serialise; different keys proceed
  in parallel.  ``threading.Lock`` is used (not ``asyncio.Lock``) because the
  pool is accessed from worker threads via ``asyncio.run()``, each of which
  creates its own event loop; ``asyncio.Lock`` is not safe across event-loop
  boundaries.
* Separate ``_cap_lock`` (``threading.Lock``) for LRU cap enforcement — runs
  outside the stripe lock to prevent same-stripe self-deadlock.
* ``aclose()`` on every eviction path — the McpToolset ``aclose()`` closes the
  underlying SSE transport.  Called on LRU eviction, TTL sweep, and manual
  evict.  ``aclose()`` raising is caught and logged so pool integrity is never
  compromised.

Kind-specific key shapes:
* ``cloud_run``: ``(server_id, account_id, creds_hash)``
* ``zapier``: ``(account_id, token_hash)`` — reserved for Phase 4 / R2.

The internal pool key is ``(kind.value,) + kind_key`` to prevent collisions
across kinds.

Usage::

    toolset = await _DEFAULT_MCP_POOL.get_or_create(
        kind=McpServerKind.CLOUD_RUN,
        key=(server_id, account_id, creds_hash),
        build_fn=lambda: build_toolset_for_doc(server_id, doc),
    )

start() is called from attach_specialists_before_agent_callback (AH-78),
which arms the idle-TTL background sweep on the first turn per process.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from enum import Enum
from typing import Any

from app.adk.tracking.mcp_pool_spans import emit_mcp_pool_span
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# 32 stripe slots — same count as ``SandboxPool``. Each stripe lock is held
# only across dict-mutation operations, not across ``build_fn`` execution
# (AH-77 Item G per-key Future pattern).  Concurrent callers for the *same*
# key coalesce on a ``concurrent.futures.Future`` stored in ``_pending``; callers
# for *different* keys that hash to the same slot proceed in parallel once each
# has installed its own Future placeholder.
_STRIPE_COUNT: int = 32


class McpServerKind(str, Enum):
    """MCP server deployment kind.

    Used as the first element of the pool key to prevent collisions across
    kinds that share overlapping key components.

    ZAPIER is reserved for Phase 4 / R2 (AH-PRD-09).  Passing it to
    ``get_or_create`` raises ``NotImplementedError``.
    """

    CLOUD_RUN = "cloud_run"
    ZAPIER = "zapier"


class McpToolsetPool:
    """Process-wide LRU + idle-TTL pool of ADK McpToolset connections.

    Mirrors :class:`~app.adk.agents.agent_factory.sandbox_pool.SandboxPool`
    verbatim for operational consistency: same lock patterns, same eviction
    paths, same Weave span discipline.

    Instantiate once per process (see ``_DEFAULT_MCP_POOL`` below).  Tests
    inject a fresh pool or ``MagicMock`` via the ``mcp_pool=`` kwarg on
    ``_build_specialist`` so the module global is never mutated by test code.
    """

    _MAX_ENTRIES: int = 128
    _IDLE_TTL_SECONDS: int = 600
    _SWEEP_INTERVAL_SECONDS: int = 60

    def __init__(self) -> None:
        self._pool: OrderedDict[tuple[str, ...], tuple[Any, float]] = OrderedDict()
        # Per-key in-flight Futures for single-flight coalescing (AH-77 Item G).
        # A Future is stored here from the moment a caller decides to build until
        # it sets the result (success) or exception (failure) and pops the entry.
        # Guarded by the same per-stripe lock as ``_pool``, but only for the
        # dict-mutation operations — ``build_fn`` runs *outside* the stripe lock.
        self._pending: dict[tuple[str, ...], concurrent.futures.Future[Any]] = {}
        # Pre-populated list — eliminates lazy-creation race when multiple
        # asyncio.run() calls from different worker threads access the pool
        # concurrently. threading.Lock (not asyncio.Lock) provides cross-thread
        # serialisation; asyncio.Lock is event-loop-bound and unsafe across
        # threads.
        self._stripe_locks: list[threading.Lock] = [
            threading.Lock() for _ in range(_STRIPE_COUNT)
        ]
        self._sweep_task: asyncio.Task[None] | None = None
        self._cap_lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        *,
        kind: McpServerKind,
        key: tuple[str, ...],
        build_fn: Callable[[], Any],
        timeout: float | None = None,
    ) -> Any:
        """Return a cached McpToolset or build a new one.

        Single-flight (AH-77 Item G): concurrent callers for the *same* key
        coalesce on a ``concurrent.futures.Future`` stored in ``_pending``.
        The stripe lock is held only during dict-mutation operations; ``build_fn``
        runs *outside* it so concurrent callers for *different* keys that hash
        to the same stripe slot build in parallel.

        Args:
            kind: The deployment kind of the MCP server.
            key: Kind-specific key tuple.  ``cloud_run`` → ``(server_id,
                account_id, creds_hash)``; ``zapier`` → ``(account_id,
                token_hash)``.
            build_fn: Zero-argument sync callable that constructs and returns
                a new McpToolset when the pool has no entry for this key.
                Called *outside* the stripe lock; must not call back into
                the pool for the same key (that would dead-wait on the Future).
            timeout: Optional wall-clock bound (seconds) on the wait for an
                in-flight build.  ``None`` means wait forever.

        Returns:
            A ready-to-use McpToolset instance.

        Raises:
            NotImplementedError: ``kind`` is ``McpServerKind.ZAPIER`` (Phase 4).
            concurrent.futures.TimeoutError: the in-flight build did not finish
                within *timeout* seconds.
            Any exception raised by ``build_fn`` propagates to all coalesced
            callers; the pool entry is not created and ``_pending`` is cleaned
            up so the next caller retries.
        """
        if kind is McpServerKind.ZAPIER:
            raise NotImplementedError(
                "zapier MCP kind is reserved for Phase 4 / R2 (AH-PRD-09)"
            )

        pool_key = (kind.value, *key)
        stripe = self._stripe(pool_key)

        # Step 1: under the stripe lock, decide what to do.
        #   a) Cache hit — return the cached toolset immediately.
        #   b) Concurrent build in flight — snapshot the Future, release lock,
        #      wait outside.
        #   c) First caller for this key — install a placeholder Future in
        #      _pending, release lock, call build_fn outside.
        is_builder = False
        build_future: concurrent.futures.Future[Any] | None = None
        toolset: Any = None
        cache_hit = False

        with stripe:
            entry = self._pool.get(pool_key)
            if entry is not None:
                # (a) Cache hit.
                toolset, _ = entry
                self._pool.move_to_end(pool_key)
                self._pool[pool_key] = (toolset, time.monotonic())
                cache_hit = True
            elif pool_key in self._pending:
                # (b) Concurrent build already in flight.
                build_future = self._pending[pool_key]
            else:
                # (c) First caller — install placeholder.
                build_future = concurrent.futures.Future()
                self._pending[pool_key] = build_future
                is_builder = True

        if not cache_hit:
            if is_builder:
                # Build outside the stripe lock so other stripe-colliding keys
                # can proceed concurrently.
                try:
                    toolset = build_fn()
                    build_future.set_result(toolset)  # type: ignore[union-attr]
                except Exception as exc:
                    build_future.set_exception(exc)  # type: ignore[union-attr]
                    with stripe:
                        self._pending.pop(pool_key, None)
                    raise
                with stripe:
                    self._pending.pop(pool_key, None)
                    self._pool[pool_key] = (toolset, time.monotonic())
            else:
                # Wait for the in-flight build to complete.
                toolset = build_future.result(timeout=timeout)  # type: ignore[union-attr]

        # ``len(self._pool)`` is read after releasing the stripe lock —
        # deliberate, not a race: ``len()`` on a dict is GIL-atomic, and
        # snapshotting the size for the Weave span outside the critical
        # section keeps the (potentially I/O-bound) span emission off the
        # single-flight path. The reported value may be one entry stale if a
        # concurrent eviction runs between these two lines; that's acceptable
        # for an observability counter and not worth widening the lock for.
        pool_size_after = len(self._pool)
        # AH-77 Item E: emit only (kind, server_id) — never pool_key, account_id,
        # or creds_hash, which would pin credential identity alongside account_id
        # in long-retention telemetry.  server_id is pool_key[1] for CLOUD_RUN
        # (pool_key = (kind.value, server_id, account_id, creds_hash)).
        # For ZAPIER the key shape differs but ZAPIER raises NotImplementedError
        # above, so this path is CLOUD_RUN-only today.
        span_server_id = pool_key[1] if len(pool_key) > 1 else None
        async with emit_mcp_pool_span(
            "mcp_pool.get",
            {
                "kind": kind.value,
                "server_id": span_server_id,
                "cache_hit": cache_hit,
                "pool_size_after": pool_size_after,
            },
        ):
            pass

        logger.info(
            "mcp_pool_checkout",
            extra={
                "kind": kind.value,
                "server_id": span_server_id,
                "cache_hit": cache_hit,
                "pool_size_after": pool_size_after,
            },
        )

        await self._evict_if_over_cap()
        return toolset

    async def evict(
        self,
        pool_key: tuple[str, ...],
        *,
        stale_before: float | None = None,
        reason: str = "manual",
    ) -> None:
        """Evict and close the pool entry for ``pool_key``.

        No-op if ``pool_key`` is not in the pool (always emits a span).

        Args:
            pool_key: Full internal pool key — ``(kind.value,) + kind_key``.
            stale_before: When set, skips the eviction if the entry's
                ``last_used`` timestamp is ≥ this value (TOCTOU guard for the
                TTL sweep: an entry refreshed after the sweep snapshot is
                not stale).
            reason: Eviction reason forwarded to the span — ``"lru"``,
                ``"ttl"``, or ``"manual"``.
        """
        stripe = self._stripe(pool_key)
        toolset_to_close = None

        # threading.Lock — acquire, do dict ops, release; no await inside.
        with stripe:
            entry = self._pool.get(pool_key)
            if entry is not None:
                _, last_used = entry
                if stale_before is not None and last_used >= stale_before:
                    # Entry refreshed after the sweep snapshot — not stale.
                    return
                del self._pool[pool_key]
                toolset_to_close, _ = entry

        # Span and aclose() outside the lock — both can yield to the event loop.
        pool_size_after = len(self._pool)
        # AH-77 Item E: emit (kind, server_id) only — no pool_key or creds_hash.
        evict_kind = pool_key[0] if pool_key else None
        evict_server_id = pool_key[1] if len(pool_key) > 1 else None
        async with emit_mcp_pool_span(
            "mcp_pool.evict",
            {
                "kind": evict_kind,
                "server_id": evict_server_id,
                "reason": reason,
                "pool_size_after": pool_size_after,
            },
        ):
            pass

        if toolset_to_close is not None:
            try:
                await toolset_to_close.aclose()
            except Exception:
                logger.warning(
                    "mcp_pool_aclose_failed",
                    # AH-77 Item E: log kind + server_id only.
                    extra={
                        "kind": evict_kind,
                        "server_id": evict_server_id,
                        "reason": reason,
                    },
                    exc_info=True,
                )

    async def sweep_idle(self) -> None:
        """Evict all entries whose ``last_used`` exceeds ``_IDLE_TTL_SECONDS``.

        Snapshot taken without a lock (safe under Python's GIL for async
        single-thread reads).  Each eviction uses the TOCTOU guard so entries
        refreshed between the snapshot and the stripe-lock acquisition are
        not closed.
        """
        now = time.monotonic()
        cutoff = now - self._IDLE_TTL_SECONDS
        stale_keys = [
            k for k, (_, last_used) in list(self._pool.items()) if last_used < cutoff
        ]
        for pool_key in stale_keys:
            await self.evict(pool_key, stale_before=cutoff, reason="ttl")

    def start(self) -> None:
        """Arm the background idle-TTL sweep task.

        Idempotent: calling ``start()`` more than once does not spawn a second
        task.  Must be called from within a running event loop (e.g. FastAPI
        lifespan startup).
        """
        if self._sweep_task is not None:
            return
        self._sweep_task = asyncio.ensure_future(self._sweep_loop())

    async def stop(self) -> None:
        """Cancel the background sweep and wait for it to exit cleanly."""
        if self._sweep_task is None:
            return
        self._sweep_task.cancel()
        try:
            await self._sweep_task
        except asyncio.CancelledError:
            pass
        self._sweep_task = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _stripe(self, key: tuple[str, ...]) -> threading.Lock:
        """Return the pre-populated stripe lock for *key*."""
        return self._stripe_locks[hash(key) % _STRIPE_COUNT]

    async def _evict_if_over_cap(self) -> None:
        """Evict LRU entries until the pool is within ``_MAX_ENTRIES``.

        Runs outside the stripe lock (cap enforcement uses ``_cap_lock``) to
        prevent a same-stripe self-deadlock when the LRU entry and the freshly
        inserted entry share a stripe slot.

        Pool integrity is maintained by deleting entries from ``_pool`` before
        awaiting ``aclose()``: the cap lock is released before any I/O so
        other pool operations are not blocked during close.

        Locking note: ``_pool`` is guarded by two distinct locks — the per-key
        stripe locks (for single-flight ``get_or_create`` / ``evict``) and the
        process-wide ``_cap_lock`` (for LRU cap enforcement here). They cover
        disjoint critical sections, not the same one: stripe locks serialise
        operations on a particular key; ``_cap_lock`` serialises the
        "pop_lru → release → aclose" sweep across all keys. Raw dict mutations
        (``del``, iteration of ``items()``) are GIL-atomic, so the two locks do
        not race for ``OrderedDict`` integrity — they coordinate higher-level
        semantics. Consolidating them into one lock would re-introduce the
        same-stripe self-deadlock this function is designed to avoid.
        """
        to_close: list[tuple[tuple[str, ...], Any, int]] = []
        with self._cap_lock:
            while len(self._pool) > self._MAX_ENTRIES:
                lru_key, (toolset, _) = next(iter(self._pool.items()))
                del self._pool[lru_key]
                to_close.append((lru_key, toolset, len(self._pool)))

        for lru_key, toolset, pool_size_after in to_close:
            # AH-77 Item E: emit (kind, server_id) only.
            lru_kind = lru_key[0] if lru_key else None
            lru_server_id = lru_key[1] if len(lru_key) > 1 else None
            async with emit_mcp_pool_span(
                "mcp_pool.evict",
                {
                    "kind": lru_kind,
                    "server_id": lru_server_id,
                    "reason": "lru",
                    "pool_size_after": pool_size_after,
                },
            ):
                pass
            try:
                await toolset.aclose()
            except Exception:
                logger.warning(
                    "mcp_pool_lru_aclose_failed",
                    # AH-77 Item E: log kind + server_id only.
                    extra={"kind": lru_kind, "server_id": lru_server_id},
                    exc_info=True,
                )

    async def _sweep_loop(self) -> None:
        """Periodic loop that calls ``sweep_idle()`` every ``_SWEEP_INTERVAL_SECONDS``."""
        while True:
            try:
                await asyncio.sleep(self._SWEEP_INTERVAL_SECONDS)
                await self.sweep_idle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("mcp_pool_sweep_error", exc_info=True)
