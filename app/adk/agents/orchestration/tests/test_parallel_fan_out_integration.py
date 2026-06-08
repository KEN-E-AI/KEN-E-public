"""Integration test: parallel fan-out of independent tasks via ctx.run_node (AH-141).

Design reference:
  ``app/adk/tools/agent_tools/tests/test_google_search_concurrency.py``
  (AH-119 precedent — proves ``ctx.run_node`` fan-out for ``google_search``
  at the leaf level; AH-141 applies the same pattern at the supervisor level).

ADK context note:
  An ``LlmAgent(mode='chat')`` coordinator dispatches task FCs **sequentially**
  via ``_llm_agent_wrapper.run_llm_agent_as_node`` (one ``await _dispatch_task_fc``
  per FC in a for-loop).  True parallel fan-out at the coordinator level requires
  explicit ``asyncio.gather(*[ctx.run_node(...)])`` — the "conceptual shape" of
  PRD §4.3.  Three tests cover the complete story:

1. ``test_two_task_specialists_fanned_out_via_ctx_run_node``
   — calls ``ctx.run_node`` on two distinct task-mode stubs in parallel
   via ``asyncio.gather``; both block on ``asyncio.Barrier(2)`` proving
   genuine overlap (``max_in_flight == 2``); both result_keys present.

2. ``test_ctx_run_node_invoked_per_branch``
   — pins ADK 2.0 ``_ParallelWorker._run_impl`` (``asyncio.create_task``,
   ``ctx.run_node``, ``asyncio.wait``).  Fails loudly on any ADK bump that
   serialises parallel dispatch.

3. ``test_branch_failure_writes_sentinel_and_sibling_succeeds``
   — one branch raises; its result_key receives ``BRANCH_ERROR_SENTINEL_PREFIX``;
   sibling result_key is present and NOT a sentinel.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
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

from app.adk.agents.orchestration.supervisor import (
    BRANCH_ERROR_SENTINEL_PREFIX,
    make_branch_failure_sentinel_after_agent_callback,
)
from app.adk.tools.registry.agent_tool_registry import (
    clear_agent_tool_registry,
    get_agent_subagent,
    register_agent_subagent,
    task_mode_supported,
)

# ---------------------------------------------------------------------------
# Overlap tracker (mirrors AH-119 _OverlapTracker)
# ---------------------------------------------------------------------------


class _OverlapTracker:
    """Records the peak number of simultaneously in-flight LLM calls.

    The ``Barrier`` is load-bearing: every concurrent run must reach it before
    *any* is released, so ``max_in_flight`` can only reach N if all N ran at
    once.  A serialised implementation blocks the first run at the barrier
    indefinitely — surfaced by the ``asyncio.wait_for`` timeout in the test.
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


# Module-level tracker — set by each test before driving ctx.run_node.
_active_tracker: _OverlapTracker | None = None

_USAGE = types.GenerateContentResponseUsageMetadata(
    prompt_token_count=200,
    candidates_token_count=50,
)


# ---------------------------------------------------------------------------
# Stub LLMs for the two specialists
# ---------------------------------------------------------------------------


class _StubGaFanOutLlm(BaseLlm):
    """GA specialist stub for fan-out test: blocks on tracker barrier."""

    model: str = "stub_ga_fan_out_llm"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^stub_ga_fan_out_llm$"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        tracker = _active_tracker
        if tracker is not None:
            await tracker.enter()
            await tracker.barrier.wait()
            await tracker.leave()
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="GA fan-out result")]),
            usage_metadata=_USAGE,
            turn_complete=True,
        )


class _StubMetaFanOutLlm(BaseLlm):
    """Meta Ads specialist stub for fan-out test: blocks on tracker barrier."""

    model: str = "stub_meta_fan_out_llm"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^stub_meta_fan_out_llm$"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        tracker = _active_tracker
        if tracker is not None:
            await tracker.enter()
            await tracker.barrier.wait()
            await tracker.leave()
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="Meta fan-out result")]),
            usage_metadata=_USAGE,
            turn_complete=True,
        )


class _StubMetaSilentCompleteLlm(BaseLlm):
    """Meta Ads specialist stub that completes WITHOUT writing result_key.

    Simulates a specialist that runs to completion but produces no output —
    the canonical case for the branch-failure sentinel: the after_agent_callback
    fires, sees result_key is absent, and writes the ERROR: sentinel.

    Note: ADK does NOT call after_agent_callback when the LLM *raises* —
    that failure mode leaves result_key absent (no sentinel), which is
    an accepted gap (coordinator sees the key as absent and treats it as
    failed).  The sentinel path is specifically for silent-complete failures.
    """

    model: str = "stub_meta_silent_complete_llm"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^stub_meta_silent_complete_llm$"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        # Succeeds but returns no useful output — result_key stays absent.
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="(no data)")]),
            usage_metadata=_USAGE,
            turn_complete=True,
        )


# Register once per process; idempotent.
LLMRegistry.register(_StubGaFanOutLlm)
LLMRegistry.register(_StubMetaFanOutLlm)
LLMRegistry.register(_StubMetaSilentCompleteLlm)


# ---------------------------------------------------------------------------
# Helpers (mirrors test_google_search_concurrency pattern)
# ---------------------------------------------------------------------------


async def _consume_event_queue(
    ic: InvocationContext,
    sentinel: object,
    svc: InMemorySessionService,
    session: Any,
) -> list[Any]:
    """Drain ``ic._event_queue``, unblocking each producer's processed signal."""
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
    """Build a minimal InvocationContext + Context for standalone ctx.run_node."""
    ic = InvocationContext(
        invocation_id="test-fan-out",
        session=session,
        session_service=svc,
        run_config=RunConfig(),
    )
    ic._event_queue = asyncio.Queue()
    ctx = Context(invocation_context=ic, node=None)
    return ic, ctx


def _make_ga_stub() -> LlmAgent:
    """Return a parentless task-mode GA stub that writes to 'ga_result'."""
    result_key = "ga_result"

    def _write_result(callback_context: Any) -> None:
        state_obj = getattr(callback_context, "state", None)
        if state_obj is not None and hasattr(state_obj, "__setitem__"):
            if state_obj.get(result_key) is None:
                state_obj[result_key] = "GA fan-out result"

    return LlmAgent(
        name="stub_ga_specialist",
        mode="task",
        model="stub_ga_fan_out_llm",
        after_agent_callback=_write_result,
    )


def _make_meta_stub(silent_fail: bool = False) -> LlmAgent:
    """Return a parentless task-mode Meta Ads stub.

    When ``silent_fail=True``, the LLM completes normally but the stub's
    ``_write_result`` callback deliberately does NOT write ``result_key``.
    The sentinel callback (second list entry) then fires and writes the ERROR:
    sentinel — this is the primary use case for AH-141's sentinel mechanism.

    The sentinel callback is wired as a separate list entry (not chained
    inside ``_write_result``) to match the production append pattern in
    ``_build_specialist`` (AH-141).
    """
    result_key = "meta_result"
    model_id = "stub_meta_silent_complete_llm" if silent_fail else "stub_meta_fan_out_llm"

    def _write_result(callback_context: Any) -> None:
        # When silent_fail, deliberately skip writing result_key so the
        # sentinel callback fires.
        if silent_fail:
            return
        state_obj = getattr(callback_context, "state", None)
        if state_obj is not None and hasattr(state_obj, "__setitem__"):
            if state_obj.get(result_key) is None:
                state_obj[result_key] = "Meta fan-out result"

    # Append sentinel_cb as a separate list entry — mirrors the production
    # _build_specialist wiring rather than calling it inline.
    sentinel_cb = make_branch_failure_sentinel_after_agent_callback("stub_meta_specialist")

    return LlmAgent(
        name="stub_meta_specialist",
        mode="task",
        model=model_id,
        after_agent_callback=[_write_result, sentinel_cb],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_agent_registry() -> Any:
    """Clear the agent-tool registry before and after each test."""
    clear_agent_tool_registry()
    yield
    clear_agent_tool_registry()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_task_specialists_fanned_out_via_ctx_run_node() -> None:
    """AH-141 AC-1/AC-3 — genuine parallel fan-out via asyncio.gather + ctx.run_node.

    Calls ``ctx.run_node`` on two distinct task-mode stubs via ``asyncio.gather``
    (the production PRD §4.3 conceptual shape).  Both stubs block on an
    ``asyncio.Barrier(parties=2)`` proving genuine concurrency
    (``max_in_flight == 2``).

    Also verifies:
    - Both ctx.run_node calls completed without exception (``len(results) == 2``).
    - The parent ctx event queue received ≥2 events (one per concurrent run).

    No ``AgentTool`` is constructed anywhere — consistent with AH-120's
    no-AgentTool-in-chat-tree CI guard.
    """
    if not task_mode_supported():
        pytest.skip("task-mode specialists require ADK 2.0+")

    global _active_tracker
    n = 2
    tracker = _OverlapTracker(parties=n)
    _active_tracker = tracker
    consumer_task: asyncio.Task[list[Any]] | None = None

    try:
        register_agent_subagent("stub_ga_specialist", _make_ga_stub)
        register_agent_subagent("stub_meta_specialist", lambda: _make_meta_stub(silent_fail=False))

        svc = InMemorySessionService()
        session = await svc.create_session(
            app_name="test_fan_out", user_id="u1"
        )
        ic, ctx = _make_test_context(svc, session)

        sentinel = object()
        consumer_task = asyncio.create_task(
            _consume_event_queue(ic, sentinel, svc, session)
        )

        # Mint fresh parentless instances — ADK 2.0 single-parent guard.
        ga_agent = get_agent_subagent("stub_ga_specialist")
        meta_agent = get_agent_subagent("stub_meta_specialist")
        assert ga_agent is not None
        assert meta_agent is not None

        # Parallel fan-out: asyncio.gather over ctx.run_node — PRD §4.3 shape.
        results = await asyncio.wait_for(
            asyncio.gather(
                ctx.run_node(ga_agent, node_input={"query": "ga data"}, use_sub_branch=True),
                ctx.run_node(meta_agent, node_input={"query": "meta data"}, use_sub_branch=True),
            ),
            timeout=10,
        )

        # AC-1: genuine concurrency.
        assert tracker.max_in_flight == n, (
            f"Expected max_in_flight=2 (genuine parallel fan-out); got {tracker.max_in_flight}. "
            "A value < 2 means ctx.run_node calls were serialised — the barrier deadlocks."
        )
        # AC-3: both ctx.run_node calls completed.
        assert len(results) == n, (
            f"Expected {n} results from asyncio.gather; got {len(results)}"
        )

        # AC-2: both result_keys present in session state.
        state = dict(ctx.session.state)
        assert state.get("ga_result") == "GA fan-out result", (
            f"ga_result must be present in session state after stub_ga_specialist completes; "
            f"got {state.get('ga_result')!r}. state keys: {list(state.keys())}"
        )
        assert state.get("meta_result") == "Meta fan-out result", (
            f"meta_result must be present in session state after stub_meta_specialist completes; "
            f"got {state.get('meta_result')!r}. state keys: {list(state.keys())}"
        )

        # Events from both branches reached the parent event queue.
        await ic._event_queue.put((sentinel, None))
        events = await consumer_task
        assert len(events) >= n, (
            f"Expected ≥{n} events (one per concurrent run); got {len(events)}. "
            "Events were dropped from the outer-stream event queue."
        )
    finally:
        _active_tracker = None
        if consumer_task is not None and not consumer_task.done():
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


def test_ctx_run_node_invoked_per_branch() -> None:
    """AH-141 AC-3 (framework half): pin ADK 2.0 _ParallelWorker._run_impl.

    Ensures a future ADK bump that removes concurrent dispatch via
    ``asyncio.create_task`` + ``ctx.run_node`` + ``asyncio.wait`` fails loudly
    here before any production regression (mirrors the AH-119 pin).
    """
    from google.adk.workflow._parallel_worker import _ParallelWorker

    source = inspect.getsource(_ParallelWorker._run_impl)
    assert "asyncio.create_task" in source, (
        "ADK _ParallelWorker._run_impl no longer uses asyncio.create_task. "
        "Verify the parallel fan-out is still concurrent (AH-141 §9)."
    )
    assert "ctx.run_node" in source, (
        "ADK _ParallelWorker._run_impl no longer calls ctx.run_node. "
        "Verify the dispatch mechanism is still task-mode compatible (AH-141 §9)."
    )
    assert "asyncio.wait" in source, (
        "ADK _ParallelWorker._run_impl no longer uses asyncio.wait. "
        "Verify the parallel fan-out is still concurrent (AH-141 §9)."
    )


@pytest.mark.asyncio
async def test_branch_failure_writes_sentinel_and_sibling_succeeds() -> None:
    """AH-141 AC-2 (failure path): when one branch completes without writing its
    result_key, the sentinel callback writes the BRANCH_ERROR_SENTINEL_PREFIX
    sentinel to that result_key; the sibling's result_key carries a real result.

    Uses asyncio.gather over ctx.run_node (same mechanism as the concurrency
    test).  The GA stub succeeds and writes ``ga_result``.  The Meta stub runs
    to LLM completion but deliberately does NOT write ``meta_result`` —
    ``silent_fail=True`` skips the write in ``_write_result``.  The appended
    sentinel callback (second list entry in ``after_agent_callback``) detects
    the absent ``meta_result`` and writes the ERROR: sentinel.

    Note: ADK does NOT call after_agent_callback when the LLM *raises* — that
    case leaves result_key absent (no sentinel written, coordinator sees it as
    missing).  The sentinel path is specifically for the silent-complete failure
    case, which is the primary design intent of AH-141.
    """
    if not task_mode_supported():
        pytest.skip("task-mode specialists require ADK 2.0+")

    global _active_tracker
    _active_tracker = None  # no barrier needed for this test

    register_agent_subagent("stub_ga_specialist", _make_ga_stub)
    register_agent_subagent(
        "stub_meta_specialist", lambda: _make_meta_stub(silent_fail=True)
    )

    svc = InMemorySessionService()
    session = await svc.create_session(
        app_name="test_fan_out_failure", user_id="u1"
    )
    # Seed the supervisor ledger so the sentinel callback can find the meta item.
    session.state["todo_lists"] = {
        "supervisor_ledger": [
            {
                "assignee": "stub_ga_specialist",
                "status": "pending",
                "result_key": "ga_result",
            },
            {
                "assignee": "stub_meta_specialist",
                "status": "pending",
                "result_key": "meta_result",
            },
        ]
    }
    ic, ctx = _make_test_context(svc, session)

    ga_agent = get_agent_subagent("stub_ga_specialist")
    meta_agent = get_agent_subagent("stub_meta_specialist")
    assert ga_agent is not None
    assert meta_agent is not None

    sentinel = object()
    consumer_task: asyncio.Task[list[Any]] | None = None
    try:
        consumer_task = asyncio.create_task(
            _consume_event_queue(ic, sentinel, svc, session)
        )

        # Fan out — meta stub completes normally (no raise) but does not write
        # result_key; the sentinel callback fires and writes the ERROR: sentinel.
        await asyncio.wait_for(
            asyncio.gather(
                ctx.run_node(
                    ga_agent,
                    node_input={"query": "ga data"},
                    use_sub_branch=True,
                ),
                ctx.run_node(
                    meta_agent,
                    node_input={"query": "meta data"},
                    use_sub_branch=True,
                ),
            ),
            timeout=10,
        )

        state = dict(ctx.session.state)

        # GA succeeded → real result present, not a sentinel.
        ga_val = state.get("ga_result", "")
        assert ga_val, (
            "ga_result must be present in session state after stub_ga_specialist succeeds. "
            f"state keys: {list(state.keys())}"
        )
        assert not str(ga_val).startswith(BRANCH_ERROR_SENTINEL_PREFIX), (
            f"stub_ga_specialist succeeded — ga_result should NOT be a sentinel; "
            f"got {ga_val!r}"
        )

        # Meta silent-complete (no result_key write) → sentinel callback fires;
        # meta_result must be present and start with ERROR:.
        meta_val = state.get("meta_result", "")
        assert meta_val, (
            "meta_result must be written (sentinel) when stub_meta_specialist "
            "completes without writing result_key. "
            f"state keys: {list(state.keys())}"
        )
        assert str(meta_val).startswith(BRANCH_ERROR_SENTINEL_PREFIX), (
            f"meta_result must be a sentinel ({BRANCH_ERROR_SENTINEL_PREFIX!r}) "
            f"when stub_meta_specialist silent-fails; got {meta_val!r}"
        )
    finally:
        if consumer_task is not None:
            await ic._event_queue.put((sentinel, None))
            await asyncio.gather(consumer_task, return_exceptions=True)
