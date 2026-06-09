"""End-to-end billing pipeline test for isolated AgentTool leaves (AH-147 / AH-PRD-05 §7 AC-3).

Verifies the full chain:
  chat_before_agent_callback → set_outer_turn_id
  AgentTool.run_async (inner runner) → capture_agent_tool_usage (leaf after_model_callback)
  → _BILLING_SINK[invocation_id] ← leaf tokens appended
  chat_after_agent_callback → drain_turn_billing → _build_turn_delta(events, now, extra=captured)
  → _post_side_table_update(delta=delta.to_wire_dict(), ...)
  → delta["input_tokens_total"] == {"_increment": 1050} (the leaf's billable input)

The root model (_RootCallsAgentToolStubLlm) emits NO usage_metadata on either turn
(turn 1 is a FunctionCall-only response; turn 2 is text without usage_metadata). So
the session.events scan in _build_turn_delta yields 0 tokens. Only the drain_turn_billing
extra provides tokens (from the leaf). This proves the leaf recovery path works end-to-end.

This test closes the gap between:
  test_leaf_usage_propagates_through_agenttool_inner_runner (tests the SINK directly)
and the full chat-callback pipeline test (tests the SINK → delta → wire-dict path).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
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
# Canonical leaf token values (CH-10)
# prompt=1250, candidates=380, cached=200 → input=1050, output=380, total=1430
# ---------------------------------------------------------------------------

_CANONICAL_LEAF_PROMPT = 1250
_CANONICAL_LEAF_CANDIDATES = 380
_CANONICAL_LEAF_CACHED = 200
_EXPECTED_LEAF_INPUT = _CANONICAL_LEAF_PROMPT - _CANONICAL_LEAF_CACHED  # 1050
_EXPECTED_LEAF_OUTPUT = _CANONICAL_LEAF_CANDIDATES  # 380
_EXPECTED_LEAF_TOTAL = _EXPECTED_LEAF_INPUT + _EXPECTED_LEAF_OUTPUT  # 1430


# ---------------------------------------------------------------------------
# Stub LLM models
# ---------------------------------------------------------------------------


class _CanonicalLeafStubLlm(BaseLlm):
    """Leaf LLM emitting CH-10 canonical tokens (matching the billing parity suite)."""

    model: str = "canonical_leaf_stub_e2e"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["canonical_leaf_stub_e2e"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_CANONICAL_LEAF_PROMPT,
            candidates_token_count=_CANONICAL_LEAF_CANDIDATES,
            cached_content_token_count=_CANONICAL_LEAF_CACHED,
        )
        content = Content(role="model", parts=[Part.from_text(text="leaf result")])
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


def _has_function_response(llm_request: Any) -> bool:
    """True if the request already carries a function_response (tool has run)."""
    for content in getattr(llm_request, "contents", None) or []:
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "function_response", None) is not None:
                return True
    return False


class _RootCallsAgentToolStubLlm(BaseLlm):
    """Root model: first call dispatches the AgentTool; once it has run, finishes.

    Stateless across the two ADK loop iterations — decides by inspecting whether
    the request already carries the AgentTool's function_response.

    Emits NO usage_metadata on either turn so the session.events scan contributes
    0 tokens — the delta's token fields come entirely from the drain_turn_billing
    extra (the leaf capture).
    """

    model: str = "root_calls_agent_tool_stub_e2e"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["root_calls_agent_tool_stub_e2e"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        if _has_function_response(llm_request):
            content = Content(role="model", parts=[Part.from_text(text="Done.")])
            yield LlmResponse(content=content, turn_complete=True)
            return
        func_call = FunctionCall(name="google_search", args={"request": "latest news"})
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


class _PlainTextStubLlm(BaseLlm):
    """Emits plain text with no usage_metadata and no tool calls."""

    model: str = "plain_text_stub_e2e"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["plain_text_stub_e2e"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        content = Content(role="model", parts=[Part.from_text(text="Plain answer.")])
        yield LlmResponse(content=content, turn_complete=True)


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _build_isolated_agent_tool_e2e() -> AgentTool:
    """Build an isolated AgentTool with the canonical leaf stub (CH-10 tokens)."""
    leaf = LlmAgent(
        name="google_search",
        model=_CanonicalLeafStubLlm(),
        description="stub canonical leaf",
        instruction="search",
        after_model_callback=capture_agent_tool_usage,
    )
    return AgentTool(agent=leaf)


# ---------------------------------------------------------------------------
# Autouse fixture — isolate billing sink state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_sink() -> Generator[None, None, None]:
    reset_for_tests()
    yield
    reset_for_tests()


# ---------------------------------------------------------------------------
# Full-pipeline runner helper
# ---------------------------------------------------------------------------


async def _run_pipeline_with_callbacks(
    use_agent_tool: bool = True,
    account_id: str = "test-e2e-account",
) -> list[dict[str, Any]]:
    """Run a root agent with (or without) the isolated AgentTool, with chat callbacks.

    Returns list of kwargs dicts captured from _post_side_table_update calls.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.chat_callbacks import attach_chat_side_table_callbacks

    tools: list[Any] = [_build_isolated_agent_tool_e2e()] if use_agent_tool else []
    root_model: BaseLlm = (
        _RootCallsAgentToolStubLlm() if use_agent_tool else _PlainTextStubLlm()
    )

    root = LlmAgent(
        name="root_agent",
        model=root_model,
        instruction="Use the google_search tool if available, then answer.",
        tools=tools,
    )
    attach_chat_side_table_callbacks(root)

    posted: list[dict[str, Any]] = []

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="billing_e2e_test",
        user_id="u1",
        state={"account_id": account_id},
    )
    runner = Runner(
        agent=root, app_name="billing_e2e_test", session_service=session_service
    )

    with patch(
        "app.adk.agents.chat_callbacks._post_side_table_update",
        side_effect=lambda **kw: posted.append(kw),
    ):
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text="news?")]
            ),
        ):
            pass

    return posted


# ---------------------------------------------------------------------------
# Test 1: Leaf tokens folded into turn delta via chat_after_agent_callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leaf_tokens_folded_into_turn_delta_via_chat_after_agent_callback() -> (
    None
):
    """The after-callback call's delta carries the leaf's CH-10 canonical token counts.

    The root model emits no usage_metadata, so all tokens in the delta originate
    from the isolated AgentTool leaf captured in the billing sink. Validates the
    full chain: set_outer_turn_id → capture_agent_tool_usage → drain_turn_billing
    → _build_turn_delta(extra=captured) → _post_side_table_update.
    """
    posted = await _run_pipeline_with_callbacks(use_agent_tool=True)

    # Identify the after-callback post: its idempotency_key contains ":turn:"
    after_posts = [p for p in posted if ":turn:" in p.get("idempotency_key", "")]
    assert after_posts, (
        "No _post_side_table_update call with ':turn:' idempotency key found. "
        "chat_after_agent_callback may not have fired."
    )
    captured_delta = after_posts[-1]["delta"]

    # to_wire_dict() serialises counter ints as {"_increment": n}
    assert captured_delta["input_tokens_total"] == {"_increment": _EXPECTED_LEAF_INPUT}, (
        f"Expected input_tokens_total={{'_increment': {_EXPECTED_LEAF_INPUT}}}, "
        f"got {captured_delta.get('input_tokens_total')!r}. "
        "Leaf tokens did not propagate through the full billing pipeline."
    )
    assert captured_delta["output_tokens_total"] == {
        "_increment": _EXPECTED_LEAF_OUTPUT
    }, (
        f"Expected output_tokens_total={{'_increment': {_EXPECTED_LEAF_OUTPUT}}}, "
        f"got {captured_delta.get('output_tokens_total')!r}."
    )


# ---------------------------------------------------------------------------
# Test 2: No double-count — leaf events absent from outer session.events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_double_count_leaf_events_absent_from_outer_session_events() -> None:
    """Regression anchor: the leaf's usage_metadata is NOT in the outer session.events.

    Confirms the #3984 drop is active — the sink is the only source for leaf
    tokens and there is no double-count from the event scan.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    # Pre-bind a turn id so capture_agent_tool_usage has a key to write to —
    # we only care about the outer event stream here, not the full callback chain.
    set_outer_turn_id("e2e-absent-test-inv")

    root = LlmAgent(
        name="root_agent",
        model=_RootCallsAgentToolStubLlm(),
        instruction="Use the google_search tool, then answer.",
        tools=[_build_isolated_agent_tool_e2e()],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="billing_e2e_absent_test", user_id="u2"
    )
    runner = Runner(
        agent=root,
        app_name="billing_e2e_absent_test",
        session_service=session_service,
    )

    events: list[Any] = []
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text="news?")]
        ),
    ):
        events.append(event)

    # No outer event carries the leaf's exact prompt_token_count — the inner
    # Runner's events never surface to the outer stream (AgentTool / #3984).
    leaf_usage_in_outer = any(
        getattr(getattr(e, "usage_metadata", None), "prompt_token_count", None)
        == _CANONICAL_LEAF_PROMPT
        for e in events
    )
    assert not leaf_usage_in_outer, (
        "Leaf usage_metadata unexpectedly appeared in the outer session.events — "
        "if ADK ever fixes #3984, the additive sink read must be gated to avoid "
        "double-counting (see agent_tool_billing.py)."
    )


# ---------------------------------------------------------------------------
# Test 3: No extra tokens when no AgentTool is used
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_extra_tokens_on_no_agent_tool_turn() -> None:
    """When no AgentTool is invoked, the drain returns zeros and the delta is zero-filled.

    The _PlainTextStubLlm emits no usage_metadata and no tool calls, so both the
    session.events scan and the drain_turn_billing extra contribute 0 tokens.
    This confirms that the leaf capture mechanism does not leak tokens across turns.
    """
    posted = await _run_pipeline_with_callbacks(use_agent_tool=False)

    after_posts = [p for p in posted if ":turn:" in p.get("idempotency_key", "")]
    assert after_posts, (
        "No _post_side_table_update call with ':turn:' idempotency key found. "
        "chat_after_agent_callback may not have fired."
    )
    captured_delta = after_posts[-1]["delta"]

    # Both token counters must be zero-increment — no leaf capture, no root usage.
    assert captured_delta["input_tokens_total"] == {"_increment": 0}, (
        f"Expected zero input tokens on a no-AgentTool turn, "
        f"got {captured_delta.get('input_tokens_total')!r}."
    )
    assert captured_delta["output_tokens_total"] == {"_increment": 0}, (
        f"Expected zero output tokens on a no-AgentTool turn, "
        f"got {captured_delta.get('output_tokens_total')!r}."
    )

    # Belt-and-suspenders: confirm drain_turn_billing is also clear (no leaked state)
    drained = drain_turn_billing("any-hypothetical-inv-id")
    assert drained.input == 0
    assert drained.output == 0
