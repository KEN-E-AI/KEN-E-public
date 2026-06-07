"""Concurrency test for Google web search via ctx.run_node fan-out (AH-119).

AH-PRD-15 §7 AC #3: AH-98's parallel-search AC #9 passes under ctx.run_node
concurrency (not AgentTool.run_async / asyncio.gather from 1.x).

ADK 1.x dispatched one turn's function calls in parallel via
``handle_function_call_list_async`` → ``asyncio.gather`` over
``asyncio.create_task``. AH-114 migrated the google_search registry entry
from an ``AgentTool`` to a task-mode ``LlmAgent(mode='task')``; the ADK 2.0
parallel fan-out pathway is ``_ParallelWorker._run_impl`` →
``asyncio.create_task(ctx.run_node(...))`` + ``asyncio.wait``.

Two facets are pinned here:

* ``test_task_mode_subagent_runs_concurrent_ctx_run_node_calls_without_cross_talk``
  drives N concurrent ``ctx.run_node(<task-mode stub>, ...)`` calls via
  ``asyncio.gather``, using a stub task-mode ``LlmAgent`` registered through
  ``register_agent_subagent`` whose leaf work blocks on an ``asyncio.Barrier``
  until all N enter; asserts ``tracker.max_in_flight == N`` (genuine overlap)
  and a non-empty event yield per call (no events dropped relative to the
  AH-98 1.x parallel baseline).

* ``test_adk_parallel_fanout_uses_create_task_over_ctx_run_node`` pins the
  ADK 2.0 parallel fan-out site at
  ``google/adk/workflow/_parallel_worker.py`` (``asyncio.create_task`` +
  ``ctx.run_node`` + ``asyncio.wait``). A future ADK bump that serialises
  parallel dispatch trips this loudly.

Design references: AH-PRD-15 §7 AC #3, §2 (re-validate AH-98
parallel-search), §8 (Test Plan), §9 (mechanism-swap risk).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from app.adk.tools.registry.agent_tool_registry import (
    clear_agent_tool_registry,
    get_agent_subagent,
    register_agent_subagent,
)

# ── fakes ────────────────────────────────────────────────────────────────────


class _OverlapTracker:
    """Records the peak number of simultaneously in-flight leaf runs.

    The ``Barrier`` is load-bearing: every concurrent run must reach it before
    *any* is released, so ``max_in_flight`` can only reach N if all N ran at
    once. A serialised implementation blocks the first run at the barrier
    forever — surfaced by the ``wait_for`` timeout in the test.
    """

    def __init__(self, parties: int) -> None:
        self.barrier = asyncio.Barrier(parties)
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = asyncio.Lock()

    async def enter(self) -> None:
        async with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)

    async def leave(self) -> None:
        async with self._lock:
            self.in_flight -= 1


# ── module-level fake LLM ─────────────────────────────────────────────────────

# Set per-test by the tracker fixture; read inside _ConcurrentSearchFakeLlm.
_active_tracker: _OverlapTracker | None = None


class _ConcurrentSearchFakeLlm(BaseLlm):
    """Fake LLM that blocks on the active _OverlapTracker barrier.

    All N concurrent ``ctx.run_node`` calls block here until every party is
    in-flight, proving genuine concurrency without a network or Gemini call.
    A serialised implementation would deadlock at the barrier.

    Model pattern ``"^fake-concurrent-search$"`` is intentionally disjoint
    from any production model name — test files are never imported by
    production code.
    """

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^fake-concurrent-search$"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: object, stream: bool = False
    ):
        tracker = _active_tracker
        assert tracker is not None, (
            "_active_tracker is None — set it before calling the fake LLM."
        )
        await tracker.enter()
        # All N parties must reach this barrier before any is released.
        # A serialised caller never reaches N parties → asyncio.wait_for timeout.
        await tracker.barrier.wait()
        try:
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="ok")],
                )
            )
        finally:
            await tracker.leave()


# Register once per process; idempotent.
LLMRegistry.register(_ConcurrentSearchFakeLlm)


# ── helpers ───────────────────────────────────────────────────────────────────


def _create_test_search_subagent() -> LlmAgent:
    """Factory for a task-mode google_search stub backed by the fake LLM.

    Minting a fresh instance per call is required by the ADK 2.0 single-parent
    guard: the same ``LlmAgent`` instance cannot be attached to more than one
    parent, so each ``get_agent_subagent`` call (and each
    ``register_agent_subagent`` validation) must receive a distinct object.
    """
    return LlmAgent(
        name="google_search",
        mode="task",
        model="fake-concurrent-search",
    )


async def _consume_event_queue(
    ic: InvocationContext,
    sentinel: object,
    svc: InMemorySessionService,
    session: Any,
) -> list[Any]:
    """Drain ``ic._event_queue`` as Runner._consume_event_queue does.

    Non-partial events carry an ``asyncio.Event`` signal that
    ``InvocationContext._enqueue_event`` blocks on. We set it after appending
    the event to the session so each producer unblocks and the node can proceed
    to the next step. Without this consumer the producers would deadlock on
    the first non-partial event.
    """
    collected: list[Any] = []
    while True:
        item, processed_signal = await ic._event_queue.get()
        if item is sentinel:
            return collected
        collected.append(item)
        await svc.append_event(session=session, event=item)
        if processed_signal is not None:
            processed_signal.set()


def _make_test_context(
    svc: InMemorySessionService, session: Any
) -> tuple[InvocationContext, Context]:
    """Build a minimal InvocationContext + Context for standalone ctx.run_node.

    ``node=None`` gives ``_node_rerun_on_resume=True`` (the required guard for
    ctx.run_node). ``_event_queue`` is initialised here so the NodeRunner's
    ``_enqueue_event`` path does not raise RuntimeError.
    """
    ic = InvocationContext(
        invocation_id="test-concurrent-search",
        session=session,
        session_service=svc,
        run_config=RunConfig(),
    )
    ic._event_queue = asyncio.Queue()
    ctx = Context(invocation_context=ic, node=None)
    return ic, ctx


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_registry() -> Any:
    """Clear the agent tool registry before and after each test.

    Prevents leaking the real ``google_search`` registration (loaded by the
    production import-time side effect in ``google_search.py``) or a prior
    test's stub into adjacent tests.
    """
    clear_agent_tool_registry()
    yield
    clear_agent_tool_registry()


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_mode_subagent_runs_concurrent_ctx_run_node_calls_without_cross_talk() -> (
    None
):
    """AH-PRD-15 §7 AC #3 — parallel-search AC #9 under ctx.run_node.

    Behavioural half: N concurrent ``ctx.run_node(<task-mode stub>, ...)`` calls
    via ``asyncio.gather`` must genuinely overlap — they cannot be serialised.

    The ``asyncio.Barrier(parties=N)`` is the load-bearing proof:
    * Concurrent (correct): all N enter the barrier simultaneously → released.
    * Serialised (regression): only 1-of-N enters the barrier → blocked
      forever → ``asyncio.wait_for`` raises ``TimeoutError`` in < 10 s.

    Also verifies:
    * The parent ctx event queue receives ≥ N events (one per concurrent run)
      — no events dropped relative to the AH-98 1.x parallel baseline.
    * All N ``ctx.run_node`` calls complete without exception or deadlock.

    No ``AgentTool`` is imported or used — consistent with AH-120's
    no-``AgentTool``-in-chat-tree CI guard.
    """
    global _active_tracker
    n = 3
    tracker = _OverlapTracker(parties=n)
    _active_tracker = tracker
    consumer_task: asyncio.Task[list[Any]] | None = None

    try:
        # Register the stub factory so get_agent_subagent can mint fresh
        # parentless instances (ADK 2.0 "already has a parent" guard).
        register_agent_subagent("google_search", _create_test_search_subagent)

        svc = InMemorySessionService()
        session = await svc.create_session(
            app_name="test_concurrent_search", user_id="u1"
        )
        ic, ctx = _make_test_context(svc, session)

        sentinel = object()
        # Background consumer unblocks _enqueue_event's processed.wait() so
        # each NodeRunner step can proceed after emitting its event.
        consumer_task = asyncio.create_task(
            _consume_event_queue(ic, sentinel, svc, session)
        )

        # Mint N fresh sub-agent instances — one per concurrent run.
        # get_agent_subagent calls the factory so each agent is a distinct,
        # parentless LlmAgent (required by the ADK 2.0 single-parent guard).
        agents = [get_agent_subagent("google_search") for _ in range(n)]
        assert all(a is not None for a in agents), (
            "get_agent_subagent returned None; is the stub factory registered?"
        )

        # Fan out N concurrent ctx.run_node calls — the same _ParallelWorker
        # pattern: asyncio.create_task(ctx.run_node(...)) + asyncio.wait.
        # use_sub_branch=True isolates each run's branch in the shared session.
        results = await asyncio.wait_for(
            asyncio.gather(
                *[
                    ctx.run_node(
                        agent,
                        node_input={"request": f"q{i}"},
                        use_sub_branch=True,
                    )
                    for i, agent in enumerate(agents)
                ]
            ),
            timeout=10,
        )

        # All N calls were in-flight at once → genuine concurrency, not serialised.
        assert tracker.max_in_flight == n, (
            f"Expected {n} concurrent in-flight calls, got {tracker.max_in_flight}. "
            "A value < N means ctx.run_node calls were serialised — the barrier "
            "would deadlock if not for the timeout guard above."
        )

        # Drain and collect events from the shared queue.
        await ic._event_queue.put((sentinel, None))
        events = await consumer_task

        # Each concurrent run emits at least one event (one LLM response) — no
        # events were dropped relative to the AH-98 1.x parallel baseline.
        assert len(events) >= n, (
            f"Expected ≥ {n} events (one per concurrent run), got {len(events)}. "
            "Events were dropped from the outer-stream event queue."
        )

        # All N ctx.run_node calls completed (no exception, no deadlock).
        assert len(results) == n
    finally:
        _active_tracker = None
        # Cancel the consumer if it is still running (e.g. on TimeoutError from
        # wait_for) so it does not leak as a pending task.
        if consumer_task is not None and not consumer_task.done():
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


def test_adk_parallel_fanout_uses_create_task_over_ctx_run_node() -> None:
    """AH-PRD-15 §7 AC #3 — framework half: pin the ADK 2.0 parallel fan-out.

    Pins ``_ParallelWorker._run_impl``
    (``google/adk/workflow/_parallel_worker.py``) so a future ADK bump that
    serialises parallel dispatch — by removing ``asyncio.create_task``,
    ``ctx.run_node``, or ``asyncio.wait`` — fails loudly here before any
    billing/tracing regression reaches production.

    Three substring checks are tolerant of minor refactors (renamed helpers,
    split loop body) that preserve the underlying concurrency semantics.
    Validated against ``google-adk==2.0.0``; re-validate on each ADK bump.
    """
    from google.adk.workflow._parallel_worker import _ParallelWorker

    source = inspect.getsource(_ParallelWorker._run_impl)
    assert "asyncio.create_task" in source, (
        "ADK _ParallelWorker._run_impl no longer uses asyncio.create_task. "
        "Verify the parallel fan-out is still concurrent (AH-PRD-15 §9)."
    )
    assert "ctx.run_node" in source, (
        "ADK _ParallelWorker._run_impl no longer calls ctx.run_node. "
        "Verify the dispatch mechanism is still task-mode compatible (AH-PRD-15 §9)."
    )
    assert "asyncio.wait" in source, (
        "ADK _ParallelWorker._run_impl no longer uses asyncio.wait. "
        "Verify the parallel fan-out is still concurrent (AH-PRD-15 §9)."
    )
