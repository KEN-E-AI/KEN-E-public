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
import os
import time
from collections import OrderedDict
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
    semantics: concurrent ``get_or_create`` calls for the **same** key all wait
    on the same lock and receive the single constructed executor; concurrent
    calls for **different** keys that hash to different stripes do not
    serialise.

    Cleanup
    -------
    ``aclose()`` is invoked on every executor before its reference is dropped.
    Failures in ``aclose()`` are caught, logged, and swallowed — pool
    integrity takes priority over retention of a possibly-broken executor.
    """

    _MAX_ENTRIES: int = 64
    _IDLE_TTL_SECONDS: int = 900
    _SWEEP_INTERVAL_SECONDS: int = 60
    # SK-35 LEAK-branch defence-in-depth: set True after live probe confirms
    # Vertex reuses container /tmp across executor sessions.  Inactive by
    # default (CLEAN branch) — no latency cost until probe result is known.
    _CLEAR_TMP_ON_REUSE: bool = False
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
        # Entry shape: (executor, last_used_monotonic_time)
        self._pool: OrderedDict[tuple[str, str], tuple[Any, float]] = OrderedDict()
        # Lazily initialised per-stripe lock map (32 slots).
        self._stripe_locks: dict[int, asyncio.Lock] = {}
        self._sweep_task: asyncio.Task[None] | None = None
        # Serialises cap-enforcement passes so concurrent misses that both exit
        # their stripe locks cannot race on next(iter(self._pool)).
        self._cap_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        *,
        account_id: str,
        config_id: str,
    ) -> AgentEngineSandboxCodeExecutor:
        """Return a pooled executor for ``(account_id, config_id)``.

        On a cache hit the entry is LRU-bumped and its ``last_used`` timestamp
        refreshed.  On a miss a new executor is constructed and the LRU cap is
        enforced.

        ``_evict_if_over_cap`` is called **outside** the stripe lock to avoid a
        deadlock: if the LRU key hashes to the same stripe as the new key,
        ``evict`` would try to acquire a lock already held by this coroutine.
        ``asyncio.Lock`` is not re-entrant, so the coroutine would deadlock.

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
                executor, _ = entry
                self._pool.move_to_end(key)
                self._pool[key] = (executor, now)
                cache_hit = True
            else:
                executor = await self._construct(
                    account_id=account_id, config_id=config_id
                )
                self._pool[key] = (executor, now)
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

        if self._CLEAR_TMP_ON_REUSE:
            try:
                await self._clear_tmp(executor)
            except Exception:
                logger.warning(
                    "SandboxPool._clear_tmp failed; returning executor uncleared",
                    extra={"account_id": account_id, "config_id": config_id},
                )

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

        ``reason`` is forwarded to the ``sandbox_pool.evict`` Weave span so
        MER-E can distinguish LRU-cap, TTL-sweep, and direct-caller evictions.
        Internal callers pass ``reason=\"lru\"`` or ``reason=\"ttl\"``; external
        callers receive the default ``\"manual\"``.

        Span emission occurs outside the stripe lock (attrs are snapshotted
        inside, emitted after release) to keep the lock window tight.
        """
        account_id, config_id = key
        async with self._stripe(key):
            entry = self._pool.get(key)
            if entry is None:
                # No-op evictions still emit a span per the PRD — truthful
                # pool_size_after is still useful signal (TTL-vs-refresh races).
                pool_size_after = len(self._pool)
            else:
                executor, last_used = entry
                if stale_before is not None and last_used >= stale_before:
                    pool_size_after = len(self._pool)
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
        stale_keys = [k for k, (_, last) in self._pool.items() if last < cutoff]
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
    # Internal helpers
    # ------------------------------------------------------------------

    def _stripe(self, key: tuple[str, str]) -> asyncio.Lock:
        """Return the per-key stripe lock (lazily initialised)."""
        idx = hash(key) % 32
        return self._stripe_locks.setdefault(idx, asyncio.Lock())

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

        Called on every ``get_or_create`` return path when
        ``_CLEAR_TMP_ON_REUSE`` is ``True``.  Best-effort: ``asyncio.TimeoutError``
        and any other exception propagate to the caller, which catches and logs
        them so the executor is still returned.

        The Vertex SDK call is synchronous, so it runs via ``asyncio.to_thread``
        to avoid blocking the event loop.  Creating a fresh ``vertexai.Client``
        per call avoids threading issues with a shared client instance.
        """
        resource_name: str = getattr(executor, "sandbox_resource_name", "")
        project = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")

        import vertexai  # lazy — not required in tests

        client = vertexai.Client(project=project, location=location)
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
        multiple concurrent ``get_or_create`` misses each insert an entry then
        race here, and without the lock they could both call
        ``next(iter(self._pool))`` concurrently while the other is mid-eviction.
        The ``while`` loop re-checks the cap after each eviction so transiently
        over-cap states (from concurrent inserts that slip through) are still
        corrected.  OrderedDict iteration order is oldest-first because evictions
        call ``del`` and hits call ``move_to_end`` — the LRU invariant.
        """
        async with self._cap_lock:
            while len(self._pool) > self._MAX_ENTRIES:
                oldest_key = next(iter(self._pool))
                await self.evict(oldest_key, reason="lru")

    async def _sweep_loop(self) -> None:
        """Background coroutine that periodically sweeps idle entries."""
        while True:
            await asyncio.sleep(self._SWEEP_INTERVAL_SECONDS)
            await self.sweep_idle()
