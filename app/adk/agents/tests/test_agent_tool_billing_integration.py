"""Integration test: isolated-AgentTool leaf billing propagates through a REAL
AgentTool inner runner (AH-PRD-15 §5 / re-plan).

The unit tests in ``test_agent_tool_billing.py`` call ``capture_agent_tool_usage``
directly. This test closes the gap finding #1 flagged on the PR: the ACTUAL
crux — that the leaf's ``after_model_callback``, firing inside
``AgentTool.run_async``'s inner Runner, reads the outer turn's ContextVar and
lands its ``usage_metadata`` in the per-turn sink — was otherwise only exercised
by the live-Gemini staging smoke. Here it runs **offline in CI**: a stub root LLM
calls the isolated AgentTool, whose leaf runs a stub model (no real Gemini, no
400), and we assert the leaf tokens reach the sink + the root drain.

This validates the propagation mechanism; the live smoke still validates the
real-Gemini "no 400" that only a real model can surface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

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

# Leaf usage the inner AgentTool model "bills" — this is what must reach the sink.
_LEAF_PROMPT = 311
_LEAF_CANDIDATES = 97
_LEAF_CACHED = 11
_EXPECTED_LEAF_INPUT = _LEAF_PROMPT - _LEAF_CACHED  # 300
_EXPECTED_LEAF_OUTPUT = _LEAF_CANDIDATES  # 97


def _has_function_response(llm_request: Any) -> bool:
    """True if the request already carries a function_response (tool has run)."""
    for content in getattr(llm_request, "contents", None) or []:
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "function_response", None) is not None:
                return True
    return False


class _LeafStubLlm(BaseLlm):
    """The isolated leaf's model — emits one response carrying leaf usage_metadata."""

    model: str = "leaf_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["leaf_stub"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: Any, stream: bool = False
    ) -> AsyncIterator[LlmResponse]:
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_LEAF_PROMPT,
            candidates_token_count=_LEAF_CANDIDATES,
            cached_content_token_count=_LEAF_CACHED,
        )
        content = Content(role="model", parts=[Part.from_text(text="grounded answer")])
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


class _RootCallsAgentToolStubLlm(BaseLlm):
    """Root model: first call dispatches the AgentTool; once it has run, finishes.

    Stateless across the two ADK loop iterations — decides by inspecting whether
    the request already carries the AgentTool's function_response.
    """

    model: str = "root_calls_agent_tool_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["root_calls_agent_tool_stub"]

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


def _build_isolated_agent_tool() -> AgentTool:
    """The same shape as create_google_search_agent_tool(), but with a stub model.

    Tests the billing-propagation plumbing (callback → ContextVar → sink) without a
    real Gemini call: the leaf has no built-in tool here because the 400 is a
    server-side composition error that only a real model surfaces (covered by the
    live smoke); the propagation under test is model-agnostic.
    """
    leaf = LlmAgent(
        name="google_search",
        model=_LeafStubLlm(),
        description="stub search leaf",
        instruction="search",
        after_model_callback=capture_agent_tool_usage,
    )
    return AgentTool(agent=leaf)


@pytest.fixture(autouse=True)
def _isolate_sink():
    reset_for_tests()
    yield
    reset_for_tests()


@pytest.mark.asyncio
async def test_leaf_usage_propagates_through_agenttool_inner_runner() -> None:
    """A real AgentTool inner-runner turn lands the leaf's usage_metadata in the
    per-turn sink, keyed by the outer invocation_id — the #3984 recovery path."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    captured_turn_ids: list[str] = []

    def _bind_turn_id(callback_context: Any) -> None:
        # Mimics chat_before_agent_callback: bind the outer turn id so the leaf's
        # after_model_callback (firing inside AgentTool.run_async) can find it.
        inv = getattr(callback_context, "_invocation_context", None)
        inv_id = getattr(inv, "invocation_id", None)
        set_outer_turn_id(inv_id)
        if inv_id:
            captured_turn_ids.append(inv_id)
        return None

    root = LlmAgent(
        name="root_agent",
        model=_RootCallsAgentToolStubLlm(),
        instruction="Use the google_search tool, then answer.",
        tools=[_build_isolated_agent_tool()],
        before_agent_callback=_bind_turn_id,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="billing_itest", user_id="u"
    )
    runner = Runner(
        agent=root, app_name="billing_itest", session_service=session_service
    )

    saw_agent_tool_call = False
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text="news?")]
        ),
    ):
        for fc in event.get_function_calls() or []:
            if fc.name == "google_search":
                saw_agent_tool_call = True

    assert saw_agent_tool_call, "Root never dispatched the google_search AgentTool."
    assert captured_turn_ids, "before_agent_callback never bound a turn id."

    # The crux: the leaf's tokens, dropped from session.events by AgentTool
    # (#3984), were captured in the sink under the outer turn id.
    drained = drain_turn_billing(captured_turn_ids[-1])
    assert drained.input == _EXPECTED_LEAF_INPUT, (
        f"Leaf input tokens did not reach the sink: got {drained.input}, "
        f"expected {_EXPECTED_LEAF_INPUT}. The ContextVar did not propagate into "
        "the AgentTool inner runner — the #3984 billing recovery is broken."
    )
    assert drained.output == _EXPECTED_LEAF_OUTPUT


@pytest.mark.asyncio
async def test_leaf_events_absent_from_outer_session_events() -> None:
    """Regression anchor for WHY the sink is needed: confirm the leaf's
    usage_metadata is NOT in the outer session.events (the #3984 drop), so the
    sink is the only source and there is no double-count."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    set_outer_turn_id("itest-inv")

    root = LlmAgent(
        name="root_agent",
        model=_RootCallsAgentToolStubLlm(),
        instruction="Use the google_search tool, then answer.",
        tools=[_build_isolated_agent_tool()],
    )
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="billing_itest2", user_id="u"
    )
    runner = Runner(
        agent=root, app_name="billing_itest2", session_service=session_service
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
        == _LEAF_PROMPT
        for e in events
    )
    assert not leaf_usage_in_outer, (
        "Leaf usage_metadata unexpectedly appeared in the outer session.events — "
        "if ADK ever fixes #3984, the additive sink read must be gated to avoid "
        "double-counting (see agent_tool_billing.py)."
    )
