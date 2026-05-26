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
from typing import TYPE_CHECKING, Any

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

    See ``docs/spike/q1-network-egress.md:188`` and SK-26 for final path format.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    return (
        f"projects/{project_id}/locations/{location}"
        f"/sandboxes/sb_{account_id}_{config_id}"
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

    def __init__(self) -> None:
        # OrderedDict maintains insertion/access order for LRU tracking.
        # Entry shape: (executor, last_used_monotonic_time)
        self._pool: OrderedDict[tuple[str, str], tuple[Any, float]] = OrderedDict()
        # Lazily initialised per-stripe lock map (32 slots).
        self._stripe_locks: dict[int, asyncio.Lock] = {}
        self._sweep_task: asyncio.Task[None] | None = None

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
        """
        key = (account_id, config_id)
        async with self._stripe(key):
            entry = self._pool.get(key)
            now = time.monotonic()
            if entry is not None:
                executor, _ = entry
                self._pool.move_to_end(key)
                self._pool[key] = (executor, now)
                return executor  # type: ignore[return-value]

            executor = await self._construct(account_id=account_id, config_id=config_id)
            self._pool[key] = (executor, now)
            self._pool.move_to_end(key)
            await self._evict_if_over_cap()
            return executor  # type: ignore[return-value]

    async def evict(self, key: tuple[str, str]) -> None:
        """Remove the entry for ``key`` and close its executor via ``aclose()``.

        No-op if the key is not present.  ``aclose()`` failures are caught and
        logged; the entry is removed regardless so the pool remains consistent.
        """
        async with self._stripe(key):
            entry = self._pool.pop(key, None)
            if entry is None:
                return
            executor, _ = entry
            try:
                await executor.aclose()
            except Exception:
                logger.exception(
                    "SandboxPool eviction aclose() failed",
                    extra={"key": key},
                )

    async def sweep_idle(self) -> None:
        """Evict entries whose last-used time predates the idle TTL cutoff.

        Collects stale keys into a list before iterating so the pool dict is
        not mutated during traversal.
        """
        cutoff = time.monotonic() - self._IDLE_TTL_SECONDS
        stale_keys = [k for k, (_, last) in self._pool.items() if last < cutoff]
        for k in stale_keys:
            await self.evict(k)

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

    async def _evict_if_over_cap(self) -> None:
        """Evict the LRU entry until the pool is at or below ``_MAX_ENTRIES``."""
        while len(self._pool) > self._MAX_ENTRIES:
            oldest_key = next(iter(self._pool))
            await self.evict(oldest_key)

    async def _sweep_loop(self) -> None:
        """Background coroutine that periodically sweeps idle entries."""
        while True:
            await asyncio.sleep(self._SWEEP_INTERVAL_SECONDS)
            await self.sweep_idle()
