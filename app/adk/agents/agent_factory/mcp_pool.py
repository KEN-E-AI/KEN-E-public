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
* 32-slot striped ``asyncio.Lock`` for per-key single-flight semantics —
  concurrent pool lookups for the same key serialise; different keys proceed
  in parallel.
* Separate ``_cap_lock`` for LRU cap enforcement — runs outside the stripe lock
  to prevent same-stripe self-deadlock.
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

TODOs:
* Nothing calls ``_DEFAULT_MCP_POOL.start()`` today, so the idle-TTL background
  sweep is dormant in production — only the LRU cap evicts.  SK-37 wires
  ``start()`` / ``stop()`` from the runtime entrypoint (FastAPI lifespan or
  Cloud Run startup); the same ticket covers McpToolsetPool.
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable
from enum import Enum
from typing import Any

from app.adk.tracking.mcp_pool_spans import emit_mcp_pool_span
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

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
        self._stripe_locks: dict[int, asyncio.Lock] = {}
        self._sweep_task: asyncio.Task[None] | None = None
        self._cap_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        *,
        kind: McpServerKind,
        key: tuple[str, ...],
        build_fn: Callable[[], Any],
    ) -> Any:
        """Return a cached McpToolset or build a new one.

        Single-flight: concurrent calls for the same ``(kind, key)`` serialise
        via the per-slot stripe lock so ``build_fn`` is called at most once per
        distinct pool key.

        Args:
            kind: The deployment kind of the MCP server.
            key: Kind-specific key tuple.  ``cloud_run`` → ``(server_id,
                account_id, creds_hash)``; ``zapier`` → ``(account_id,
                token_hash)``.
            build_fn: Zero-argument sync callable that constructs and returns
                a new McpToolset when the pool has no entry for this key.
                Called while the stripe lock is held; must not call back into
                the pool or attempt to acquire the same stripe lock.

        Returns:
            A ready-to-use McpToolset instance.

        Raises:
            NotImplementedError: ``kind`` is ``McpServerKind.ZAPIER`` (Phase 4).
            Any exception raised by ``build_fn`` propagates to the caller;
            the pool entry is not created on failure.
        """
        if kind is McpServerKind.ZAPIER:
            raise NotImplementedError(
                "zapier MCP kind is reserved for Phase 4 / R2 (AH-PRD-09)"
            )

        pool_key = (kind.value, *key)
        stripe = self._stripe(pool_key)

        async with stripe:
            entry = self._pool.get(pool_key)
            if entry is not None:
                toolset, _ = entry
                self._pool.move_to_end(pool_key)
                self._pool[pool_key] = (toolset, time.monotonic())
                cache_hit = True
            else:
                toolset = build_fn()
                self._pool[pool_key] = (toolset, time.monotonic())
                cache_hit = False

        pool_size_after = len(self._pool)
        async with emit_mcp_pool_span(
            "mcp_pool.get",
            {
                "kind": kind.value,
                "pool_key": str(pool_key),
                "cache_hit": cache_hit,
                "pool_size_after": pool_size_after,
            },
        ):
            pass

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

        async with stripe:
            entry = self._pool.get(pool_key)
            if entry is None:
                pool_size_after = len(self._pool)
                async with emit_mcp_pool_span(
                    "mcp_pool.evict",
                    {
                        "pool_key": str(pool_key),
                        "reason": reason,
                        "pool_size_after": pool_size_after,
                    },
                ):
                    pass
                return

            _, last_used = entry
            if stale_before is not None and last_used >= stale_before:
                # Entry refreshed after the sweep snapshot — not stale.
                return

            del self._pool[pool_key]
            toolset_to_close, _ = entry

        pool_size_after = len(self._pool)
        async with emit_mcp_pool_span(
            "mcp_pool.evict",
            {
                "pool_key": str(pool_key),
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
                    extra={"pool_key": str(pool_key), "reason": reason},
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

    def _stripe(self, key: tuple[str, ...]) -> asyncio.Lock:
        """Return the stripe lock for *key*, creating it lazily if needed."""
        slot = hash(key) % _STRIPE_COUNT
        if slot not in self._stripe_locks:
            self._stripe_locks[slot] = asyncio.Lock()
        return self._stripe_locks[slot]

    async def _evict_if_over_cap(self) -> None:
        """Evict LRU entries until the pool is within ``_MAX_ENTRIES``.

        Runs outside the stripe lock (cap enforcement uses ``_cap_lock``) to
        prevent a same-stripe self-deadlock when the LRU entry and the freshly
        inserted entry share a stripe slot.

        Pool integrity is maintained by deleting the entry from ``_pool``
        before awaiting ``aclose()``.
        """
        async with self._cap_lock:
            while len(self._pool) > self._MAX_ENTRIES:
                lru_key, (toolset, _) = next(iter(self._pool.items()))
                del self._pool[lru_key]
                pool_size_after = len(self._pool)
                async with emit_mcp_pool_span(
                    "mcp_pool.evict",
                    {
                        "pool_key": str(lru_key),
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
                        extra={"pool_key": str(lru_key)},
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
