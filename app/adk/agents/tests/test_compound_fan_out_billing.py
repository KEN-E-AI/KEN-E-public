"""Compound fan-out billing additivity test (AH-147 / AH-PRD-05 §7 AC-4).

Verifies that parallel specialists fanned out via ctx.run_node + asyncio.gather,
each internally invoking an isolated AgentTool leaf, accumulate their leaf tokens
ADDITIVELY in the off-state sink under the single outer invocation_id — no clobber
across asyncio.gather-copied contexts.

Design reference:
  app/adk/agents/agent_tool_billing.py (ContextVar + _BILLING_SINK + additive capture)
  app/adk/agents/orchestration/tests/test_parallel_fan_out_integration.py (_OverlapTracker + ctx.run_node pattern)
  app/adk/agents/tests/test_agent_tool_billing_integration.py (_build_isolated_agent_tool pattern)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Generator
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types
from google.genai.types import Content, FunctionCall, Part

from app.adk.agents.agent_tool_billing import (
    capture_agent_tool_usage,
    drain_turn_billing,
    reset_for_tests,
    set_outer_turn_id,
)

# ---------------------------------------------------------------------------
# Branch token shapes — distinct so clobber detection works
# ---------------------------------------------------------------------------

_BRANCH_A_PROMPT = 311
_BRANCH_A_CANDIDATES = 97
_BRANCH_A_CACHED = 11
_BRANCH_A_EXPECTED_INPUT = _BRANCH_A_PROMPT - _BRANCH_A_CACHED  # 300
_BRANCH_A_EXPECTED_OUTPUT = _BRANCH_A_CANDIDATES  # 97

_BRANCH_B_PROMPT = 413
_BRANCH_B_CANDIDATES = 121
_BRANCH_B_CACHED = 13
_BRANCH_B_EXPECTED_INPUT = _BRANCH_B_PROMPT - _BRANCH_B_CACHED  # 400
_BRANCH_B_EXPECTED_OUTPUT = _BRANCH_B_CANDIDATES  # 121

_EXPECTED_ADDITIVE_INPUT = _BRANCH_A_EXPECTED_INPUT + _BRANCH_B_EXPECTED_INPUT  # 700
_EXPECTED_ADDITIVE_OUTPUT = _BRANCH_A_EXPECTED_OUTPUT + _BRANCH_B_EXPECTED_OUTPUT  # 218


# ---------------------------------------------------------------------------
# Overlap tracker (mirrors _OverlapTracker from test_parallel_fan_out_integration.py)
# ---------------------------------------------------------------------------


class _OverlapTracker:
    """Records the peak number of simultaneously in-flight LLM calls.

    The ``Barrier`` is load-bearing: every concurrent run must reach it before
    *any* is released, so ``max_in_flight`` can only reach N if all N ran at
    once. A serialised implementation blocks the first run at the barrier
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


# Module-level tracker — set by the barrier test before driving ctx.run_node.
_active_billing_tracker: _OverlapTracker | None = None


# ---------------------------------------------------------------------------
# Leaf stub LLMs — emit branch-specific token shapes; barrier-aware
# ---------------------------------------------------------------------------


class _BranchALeafStubLlm(BaseLlm):
    """Branch A leaf model — emits distinct token shape; participates in barrier."""

    model: str = "branch_a_leaf_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["branch_a_leaf_stub"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        tracker = _active_billing_tracker
        if tracker is not None:
            await tracker.enter()
            await tracker.barrier.wait()
            await tracker.leave()
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_BRANCH_A_PROMPT,
            candidates_token_count=_BRANCH_A_CANDIDATES,
            cached_content_token_count=_BRANCH_A_CACHED,
        )
        content = Content(role="model", parts=[Part.from_text(text="branch a leaf result")])
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


class _BranchBLeafStubLlm(BaseLlm):
    """Branch B leaf model — emits distinct token shape; participates in barrier."""

    model: str = "branch_b_leaf_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["branch_b_leaf_stub"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        tracker = _active_billing_tracker
        if tracker is not None:
            await tracker.enter()
            await tracker.barrier.wait()
            await tracker.leave()
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_BRANCH_B_PROMPT,
            candidates_token_count=_BRANCH_B_CANDIDATES,
            cached_content_token_count=_BRANCH_B_CACHED,
        )
        content = Content(role="model", parts=[Part.from_text(text="branch b leaf result")])
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


# ---------------------------------------------------------------------------
# Specialist stub LLM
# ---------------------------------------------------------------------------


def _has_function_response(llm_request: Any) -> bool:
    """True if the request already carries a function_response (AgentTool has run)."""
    for content in getattr(llm_request, "contents", None) or []:
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "function_response", None) is not None:
                return True
    return False


class _SpecialistCallsAgentToolStubLlm(BaseLlm):
    """Specialist model: turn 1 emits FunctionCall('google_search'); turn 2 emits final text.

    Stateless — decides by inspecting whether the request already carries a
    function_response from the AgentTool leaf.
    """

    model: str = "specialist_calls_agent_tool_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["specialist_calls_agent_tool_stub"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        if _has_function_response(llm_request):
            content = Content(role="model", parts=[Part.from_text(text="Done.")])
            yield LlmResponse(content=content, turn_complete=True)
        else:
            func_call = FunctionCall(name="google_search", args={"request": "search"})
            content = Content(role="model", parts=[Part(function_call=func_call)])
            yield LlmResponse(content=content, turn_complete=False)


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _build_isolated_agent_tool_for_branch(branch: str) -> AgentTool:
    """Build an isolated AgentTool leaf with branch-specific stub model."""
    leaf_model = _BranchALeafStubLlm() if branch == "a" else _BranchBLeafStubLlm()
    leaf = LlmAgent(
        name="google_search",
        model=leaf_model,
        description=f"stub search leaf branch {branch}",
        instruction="search",
        after_model_callback=capture_agent_tool_usage,
    )
    return AgentTool(agent=leaf)


def _make_branch_specialist(branch: str) -> LlmAgent:
    """Build a task-mode specialist that calls an isolated AgentTool leaf."""
    return LlmAgent(
        name=f"branch_{branch}_specialist",
        model=_SpecialistCallsAgentToolStubLlm(),
        mode="task",
        instruction=f"Branch {branch} specialist.",
        tools=[_build_isolated_agent_tool_for_branch(branch)],
    )


# ---------------------------------------------------------------------------
# ctx.run_node helpers (mirrors test_parallel_fan_out_integration.py pattern)
# ---------------------------------------------------------------------------


def _make_test_context(
    svc: InMemorySessionService, session: Any
) -> tuple[InvocationContext, Context]:
    """Build a minimal InvocationContext + Context for standalone ctx.run_node."""
    ic = InvocationContext(
        invocation_id="test-compound-fan-out",
        session=session,
        session_service=svc,
        run_config=RunConfig(),
    )
    ic._event_queue = asyncio.Queue()
    ctx = Context(invocation_context=ic, node=None)
    return ic, ctx


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_sink() -> Generator[None, None, None]:
    global _active_billing_tracker
    _active_billing_tracker = None
    reset_for_tests()
    yield
    _active_billing_tracker = None
    reset_for_tests()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compound_fan_out_leaves_accumulate_additively_under_single_invocation_id() -> None:
    """AH-147 / AH-PRD-05 §7 AC-4 — compound fan-out billing additivity.

    Two task-mode specialists, each internally invoking an isolated AgentTool leaf,
    are fanned out via ctx.run_node + asyncio.gather with a single outer
    invocation_id bound via set_outer_turn_id. All leaf tokens must accumulate
    ADDITIVELY in the off-state sink under that single invocation_id with no clobber
    across asyncio.gather-copied contexts.
    """
    from app.adk.tools.registry.agent_tool_registry import task_mode_supported

    if not task_mode_supported():
        pytest.skip("task-mode specialists require ADK 2.0+")

    # Bind outer turn id BEFORE gather (asyncio.gather copies context to child tasks)
    outer_inv_id = "compound-fan-out-billing-test"
    set_outer_turn_id(outer_inv_id)

    spec_a = _make_branch_specialist("a")
    spec_b = _make_branch_specialist("b")

    svc = InMemorySessionService()
    session = await svc.create_session(app_name="compound_fan_out_billing", user_id="u1")
    ic, ctx = _make_test_context(svc, session)

    sentinel = object()
    consumer_task = asyncio.create_task(_consume_event_queue(ic, sentinel, svc, session))

    try:
        await asyncio.wait_for(
            asyncio.gather(
                ctx.run_node(spec_a, node_input={"query": "branch a data"}, use_sub_branch=True),
                ctx.run_node(spec_b, node_input={"query": "branch b data"}, use_sub_branch=True),
            ),
            timeout=15,
        )
    finally:
        await ic._event_queue.put((sentinel, None))
        await consumer_task

    drained = drain_turn_billing(outer_inv_id)

    assert drained.input == _EXPECTED_ADDITIVE_INPUT, (
        f"Additive input mismatch: got {drained.input}, expected {_EXPECTED_ADDITIVE_INPUT} "
        f"(branch_a={_BRANCH_A_EXPECTED_INPUT} + branch_b={_BRANCH_B_EXPECTED_INPUT}). "
        "A value equal to only one branch means asyncio.gather context-copy semantics "
        "caused a clobber in the _BILLING_SINK. "
        "AH-147 / AH-PRD-05 §7 AC-4 — MERGE BLOCKER"
    )
    assert drained.output == _EXPECTED_ADDITIVE_OUTPUT, (
        f"Additive output mismatch: got {drained.output}, expected {_EXPECTED_ADDITIVE_OUTPUT}. "
        "AH-147 / AH-PRD-05 §7 AC-4 — MERGE BLOCKER"
    )


@pytest.mark.asyncio
async def test_compound_fan_out_concurrency_proven_via_barrier() -> None:
    """AH-147 / AH-PRD-05 §7 AC-4 (b) — genuine concurrent leaf execution.

    Both AgentTool leaf models block on asyncio.Barrier(2) ensuring both are
    in-flight simultaneously under asyncio.gather. max_in_flight must equal 2.
    """
    from app.adk.tools.registry.agent_tool_registry import task_mode_supported

    if not task_mode_supported():
        pytest.skip("task-mode specialists require ADK 2.0+")

    global _active_billing_tracker
    tracker = _OverlapTracker(parties=2)
    _active_billing_tracker = tracker

    outer_inv_id = "compound-barrier-test"
    set_outer_turn_id(outer_inv_id)

    spec_a = _make_branch_specialist("a")
    spec_b = _make_branch_specialist("b")

    svc = InMemorySessionService()
    session = await svc.create_session(app_name="compound_barrier", user_id="u1")
    ic, ctx = _make_test_context(svc, session)

    sentinel = object()
    consumer_task = asyncio.create_task(_consume_event_queue(ic, sentinel, svc, session))

    try:
        await asyncio.wait_for(
            asyncio.gather(
                ctx.run_node(spec_a, node_input={}, use_sub_branch=True),
                ctx.run_node(spec_b, node_input={}, use_sub_branch=True),
            ),
            timeout=15,
        )
        assert tracker.max_in_flight == 2, (
            f"Expected max_in_flight=2 (genuine parallel leaf execution); "
            f"got {tracker.max_in_flight}. "
            "Both AgentTool leaf models must run concurrently under asyncio.gather. "
            "AH-147 / AH-PRD-05 §7 AC-4 (b) — concurrency guard"
        )
    finally:
        _active_billing_tracker = None
        await ic._event_queue.put((sentinel, None))
        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            consumer_task.cancel()
            await asyncio.gather(consumer_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_compound_fan_out_no_leakage_across_invocation_ids() -> None:
    """AH-147 / AH-PRD-05 §7 AC-4 (c) — no token leakage to sibling invocation_id.

    Leaf tokens captured under the active outer_inv_id must not appear when
    a different sibling_inv_id is drained.
    """
    from app.adk.tools.registry.agent_tool_registry import task_mode_supported

    if not task_mode_supported():
        pytest.skip("task-mode specialists require ADK 2.0+")

    outer_inv_id = "compound-leakage-test"
    sibling_inv_id = "sibling-invocation-id"
    set_outer_turn_id(outer_inv_id)

    spec_a = _make_branch_specialist("a")
    spec_b = _make_branch_specialist("b")

    svc = InMemorySessionService()
    session = await svc.create_session(app_name="compound_leakage", user_id="u1")
    ic, ctx = _make_test_context(svc, session)

    sentinel = object()
    consumer_task = asyncio.create_task(_consume_event_queue(ic, sentinel, svc, session))

    try:
        await asyncio.wait_for(
            asyncio.gather(
                ctx.run_node(spec_a, node_input={}, use_sub_branch=True),
                ctx.run_node(spec_b, node_input={}, use_sub_branch=True),
            ),
            timeout=15,
        )
    finally:
        await ic._event_queue.put((sentinel, None))
        await consumer_task

    # Drain the real turn id (clears it from sink)
    drained_real = drain_turn_billing(outer_inv_id)
    assert drained_real.input > 0, "Real turn should have captured tokens"

    # Drain a sibling id — should be zero (no leakage)
    drained_sibling = drain_turn_billing(sibling_inv_id)
    assert drained_sibling.input == 0, (
        f"Sibling invocation_id drained {drained_sibling.input} input tokens, expected 0. "
        "Leaf tokens leaked into a wrong sink key. "
        "AH-147 / AH-PRD-05 §7 AC-4 (c)"
    )
    assert drained_sibling.output == 0, (
        f"Sibling invocation_id drained {drained_sibling.output} output tokens, expected 0."
    )
