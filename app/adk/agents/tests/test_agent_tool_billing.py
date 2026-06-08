"""Unit tests for the isolated agent-as-tool billing capture (AH-PRD-15 §5).

Pure-logic tests: no ADK, no network. The capture path is exercised with
synthetic ``llm_response`` objects shaped like ADK's ``LlmResponse``
(``usage_metadata`` duck-typed via ``SimpleNamespace``), matching how
``extract_billable_tokens`` reads tokens.
"""

from __future__ import annotations

import asyncio
import contextvars
from types import SimpleNamespace

import pytest

from app.adk.agents.agent_tool_billing import (
    capture_agent_tool_usage,
    drain_turn_billing,
    reset_for_tests,
    set_outer_turn_id,
)


def _llm_response(
    prompt: int = 0, candidates: int = 0, thoughts: int = 0, cached: int = 0
):
    """Build a synthetic LlmResponse carrying usage_metadata."""
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt,
            candidates_token_count=candidates,
            thoughts_token_count=thoughts,
            cached_content_token_count=cached,
        )
    )


@pytest.fixture(autouse=True)
def _isolate_sink():
    reset_for_tests()
    yield
    reset_for_tests()


def test_capture_then_drain_round_trip():
    set_outer_turn_id("inv-1")
    capture_agent_tool_usage(
        None, _llm_response(prompt=1250, candidates=380, cached=200)
    )

    drained = drain_turn_billing("inv-1")

    # input = prompt - cached = 1050; output = 380; reasoning = 0
    assert (drained.input, drained.output, drained.reasoning) == (1050, 380, 0)


def test_multiple_captures_accumulate_additively():
    set_outer_turn_id("inv-2")
    capture_agent_tool_usage(None, _llm_response(prompt=100, candidates=10))
    capture_agent_tool_usage(None, _llm_response(prompt=200, candidates=20, thoughts=5))

    drained = drain_turn_billing("inv-2")

    assert (drained.input, drained.output, drained.reasoning) == (300, 30, 5)


def test_parallel_appends_in_copied_context_share_one_sink():
    """asyncio.gather copies the context for each parallel google_search call.

    A copied context inherits the ContextVar *value* (the turn id) and the leaf
    appends to the same module-level sink, so parallel leaf calls accumulate
    rather than clobber (AH-98 AC #9 under AgentTool/asyncio.gather).
    """
    set_outer_turn_id("inv-parallel")

    def _branch(prompt: int) -> None:
        capture_agent_tool_usage(None, _llm_response(prompt=prompt, candidates=1))

    # Run each branch in its OWN copied context (what gather/ensure_future does).
    for prompt in (10, 20, 30):
        contextvars.copy_context().run(_branch, prompt)

    drained = drain_turn_billing("inv-parallel")
    assert (drained.input, drained.output) == (60, 3)


def test_capture_is_noop_without_turn_id():
    # No set_outer_turn_id → ContextVar is None → capture does nothing.
    capture_agent_tool_usage(None, _llm_response(prompt=999, candidates=999))
    assert drain_turn_billing("anything").total_billable == 0


def test_drain_is_one_shot():
    set_outer_turn_id("inv-3")
    capture_agent_tool_usage(None, _llm_response(prompt=50, candidates=5))

    first = drain_turn_billing("inv-3")
    second = drain_turn_billing("inv-3")

    assert first.total_billable == 55
    assert second.total_billable == 0


def test_zero_usage_response_is_not_recorded():
    set_outer_turn_id("inv-4")
    # Partial streaming chunk with no usage → no append.
    capture_agent_tool_usage(None, SimpleNamespace(usage_metadata=None))
    assert drain_turn_billing("inv-4").total_billable == 0


def test_turns_are_isolated_by_id():
    set_outer_turn_id("turn-A")
    capture_agent_tool_usage(None, _llm_response(prompt=100, candidates=0))
    set_outer_turn_id("turn-B")
    capture_agent_tool_usage(None, _llm_response(prompt=7, candidates=0))

    assert drain_turn_billing("turn-A").input == 100
    assert drain_turn_billing("turn-B").input == 7


def test_drain_unknown_turn_returns_zero():
    assert drain_turn_billing(None).total_billable == 0
    assert drain_turn_billing("never-seen").total_billable == 0


# ---------------------------------------------------------------------------
# Companion guard (AH-PRD-15 §7.7): the sanctioned isolation leaves MUST carry the
# billing callback and ONLY their built-in tool. Pairs with the no-AgentTool lint
# allow-list so an AgentTool can never be reintroduced without billing.
# ---------------------------------------------------------------------------


def test_google_search_isolation_leaf_carries_billing_callback_and_only_search_tool():
    from app.adk.tools.agent_tools.google_search import create_google_search_agent_tool

    tool = create_google_search_agent_tool()
    leaf = tool.agent
    assert tool.name == "google_search"  # matches the agent.google_search tool id
    assert leaf.after_model_callback is capture_agent_tool_usage
    # Exactly one tool, the built-in google_search grounding tool — no sibling.
    assert len(leaf.tools) == 1


def test_numerical_analyst_isolation_leaf_carries_billing_callback_and_no_function_tools():
    from app.adk.tools.agent_tools.numerical_analyst import (
        create_numerical_analyst_agent_tool,
    )

    tool = create_numerical_analyst_agent_tool()
    leaf = tool.agent
    assert tool.name == "numerical_analyst"
    assert leaf.after_model_callback is capture_agent_tool_usage
    # Code execution only — no function tools alongside the built-in code executor.
    assert not leaf.tools
    assert leaf.code_executor is not None


# ---------------------------------------------------------------------------
# Real asyncio.gather parallel-additivity tests (AH-146 / AH-PRD-05 §7 AC-9)
#
# The supervisor fan-out path dispatches multiple AgentTool branches via
# ctx.run_node + asyncio.gather. The existing test
# test_parallel_appends_in_copied_context_share_one_sink covers the
# contextvars.copy_context().run() simulation, but NOT the real event-loop
# scheduling that asyncio.gather uses. These tests verify that real parallel
# branches under gather accumulate additively in the same turn sink (no clobber,
# no under-count) — a real event-loop policy change that the copy_context
# simulation would miss is caught here.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_capture_under_asyncio_gather_accumulates_additively():
    """Real asyncio.gather branches accumulate additively in the turn sink.

    Models the supervisor fan-out path: N concurrent AgentTool leaf callbacks
    (each triggered by asyncio.gather inside ctx.run_node) must each append to
    the same sink bucket under one outer invocation_id. The drain must equal the
    sum of all branch contributions — no clobber, no under-count.

    Complements test_parallel_appends_in_copied_context_share_one_sink (which
    uses contextvars.copy_context().run()) by exercising the production
    asyncio.gather primitive directly. A future event-loop policy change
    (e.g., a change to how gather copies contexts) that the copy_context
    simulation would miss will be caught here.
    """
    set_outer_turn_id("inv-gather-additivity")

    async def branch(prompt: int) -> None:
        await asyncio.sleep(0)  # yield to the event loop, then capture
        capture_agent_tool_usage(None, _llm_response(prompt=prompt, candidates=1))

    await asyncio.gather(*(branch(p) for p in (10, 20, 30, 40)))

    drained = drain_turn_billing("inv-gather-additivity")
    # input = sum([10, 20, 30, 40]) = 100 (prompt - cached=0)
    # output = 4 * 1 = 4 (candidates)
    assert (drained.input, drained.output) == (100, 4), (
        f"asyncio.gather branches must accumulate additively. "
        f"Got input={drained.input}, output={drained.output}, expected (100, 4). "
        "Likely cause: gather branches are writing to separate sinks or clobbering "
        "each other. Check _BILLING_SINK thread safety and _OUTER_TURN_ID context "
        "propagation under asyncio.gather."
    )


@pytest.mark.asyncio
async def test_gather_branches_without_turn_id_are_noop():
    """asyncio.gather branches without an outer turn id contribute nothing.

    No-op guard: if set_outer_turn_id is not called before gather, no branch
    should write to any sink. Guards against a regression where a gather branch
    somehow inherits a stale turn id from a previous test (the autouse
    _isolate_sink fixture resets the ContextVar between tests, so this must
    stay at zero).
    """
    # Deliberately skip set_outer_turn_id — branches must be no-ops.
    async def branch(prompt: int) -> None:
        await asyncio.sleep(0)
        capture_agent_tool_usage(None, _llm_response(prompt=prompt, candidates=1))

    await asyncio.gather(*(branch(p) for p in (10, 20, 30)))

    assert drain_turn_billing("inv-gather-noop").total_billable == 0, (
        "Gather branches without a prior set_outer_turn_id must not write to any "
        "sink bucket. Check that _isolate_sink (autouse fixture) calls reset_for_tests "
        "before each test — a non-zero result means a stale turn id leaked from a "
        "prior test or set_outer_turn_id was called unexpectedly."
    )
