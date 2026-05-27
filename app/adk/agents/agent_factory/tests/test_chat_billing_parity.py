"""Phase 2 parity test — Chat + Billing (AH-61, merge blocker for AH-PRD-09 Phase 2).

CANONICAL FIXTURE (from api/tests/unit/chat/test_token_accounting_parity.py):
  prompt_token_count        = 1250
  candidates_token_count    =  380
  thoughts_token_count      = None  (non-reasoning model)
  cached_content_token_count=  200
  → input=1050, output=380, reasoning=0, total_billable=1430

CONTRACT UNDER TEST:
  ADK event propagation from inner Runner (delegate_to_specialist / specialist_runtime.run)
  to outer Runner must be preserved so that:
  - Chat's SessionTurnAccumulator.add_event() sees the same per-event usage_metadata
  - Billing's extract_billable_tokens(event).total_billable sums to the same total

MERGE-BLOCKER SEMANTICS:
  If this file fails, Phase 2 (delegate_to_specialist + specialist_runtime) cannot merge.
  Mode B may currently fail (specialist events trapped in inner Runner without propagation).
  That failure IS the merge-blocker contract — see AH-PRD-09 §7 ACs #9 and #10.
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types
from google.genai.types import Content, FunctionCall, Part

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from shared.token_accounting import extract_billable_tokens

# Resolve api/src so kene_api is importable without installing the api package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "api", "src"))

from kene_api.chat.accumulator import SessionTurnAccumulator

# ---------------------------------------------------------------------------
# Canonical fixture constants (must match api/tests/unit/chat/test_token_accounting_parity.py)
# ---------------------------------------------------------------------------

_CANONICAL_PROMPT_TOKEN_COUNT = 1250
_CANONICAL_CANDIDATES_TOKEN_COUNT = 380
_CANONICAL_THOUGHTS_TOKEN_COUNT = None  # non-reasoning model: SDK returns None
_CANONICAL_CACHED_TOKEN_COUNT = 200

_EXPECTED_INPUT = 1050
_EXPECTED_OUTPUT = 380
_EXPECTED_REASONING = 0
_EXPECTED_TOTAL_BILLABLE = 1430  # input + output + reasoning

# ---------------------------------------------------------------------------
# Stub LLM models
# ---------------------------------------------------------------------------


class _CanonicalStubLlm(BaseLlm):
    """Emits one response with the canonical fixture usage_metadata."""

    model: str = "canonical_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["canonical_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ):
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
            candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
            cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
            # thoughts_token_count omitted → None, matching real SDK behavior
        )
        content = Content(
            role="model", parts=[Part.from_text(text="Specialist response")]
        )
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


class _RouterStubLlm(BaseLlm):
    """Mode A root: routes to the canonical specialist via transfer_to_agent."""

    model: str = "router_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["router_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ):
        func_call = FunctionCall(
            name="transfer_to_agent", args={"agent_name": "canonical_stub_agent"}
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


class _DelegateStubLlm(BaseLlm):
    """Mode B root: first turn calls delegate_to_specialist, second yields final text."""

    model: str = "delegate_stub"
    call_count: int = 0

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["delegate_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ):
        self.call_count += 1
        if self.call_count == 1:
            func_call = FunctionCall(
                name="delegate_to_specialist",
                args={"name": "test_specialist", "query": "hello"},
            )
            content = Content(role="model", parts=[Part(function_call=func_call)])
            yield LlmResponse(content=content, turn_complete=False)
        else:
            content = Content(role="model", parts=[Part.from_text(text="Done!")])
            yield LlmResponse(content=content, turn_complete=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deterministic_specialist(name: str = "canonical_stub_agent") -> LlmAgent:
    """Return an LlmAgent backed by _CanonicalStubLlm."""
    return LlmAgent(
        name=name,
        model=_CanonicalStubLlm(),
        instruction="Test specialist",
    )


def _increments_equal(a: Any, b: Any) -> bool:
    """Compare two firestore.Increment objects by their .value attribute."""
    return getattr(a, "value", a) == getattr(b, "value", b)


async def _capture_mode_a_events(
    specialist: LlmAgent,
    query: str = "hello",
) -> list[Any]:
    """Run Mode A (sub-agent) outer Runner and return all events."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    root = LlmAgent(
        name="root_agent",
        model=_RouterStubLlm(),
        instruction="Route queries.",
        sub_agents=[specialist],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="parity_test", user_id="test_user"
    )
    runner = Runner(
        agent=root,
        app_name="parity_test",
        session_service=session_service,
    )
    events: list[Any] = []
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=genai_types.Content(
            role="user", parts=[genai_types.Part.from_text(text=query)]
        ),
    ):
        events.append(event)
    return events


async def _capture_mode_b_events(
    specialist: LlmAgent,
    query: str = "hello",
) -> list[Any]:
    """Run Mode B (delegate_to_specialist) outer Runner and return all events.

    Primes the specialist cache so delegate_to_specialist can resolve the
    specialist without a Firestore call, and patches resolve_config to return
    the test MergedAgentConfig so resolve_agent's content-hash lookup succeeds.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

    test_config = MergedAgentConfig(
        instruction="Test specialist",
        model="canonical_stub",
        description="Test specialist for parity tests",
    )
    content_hash = hashlib.sha256(test_config.model_dump_json().encode()).hexdigest()
    cache_key: tuple[str, str | None, str] = ("test_specialist", None, content_hash)
    sr._specialists_cache.put(cache_key, specialist)

    root = LlmAgent(
        name="root_agent",
        model=_DelegateStubLlm(),
        instruction="Delegate queries.",
        tools=[delegate_to_specialist],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="parity_test_b", user_id="test_user"
    )
    runner = Runner(
        agent=root,
        app_name="parity_test_b",
        session_service=session_service,
    )
    events: list[Any] = []
    with patch.object(sr, "resolve_config", return_value=test_config):
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=query)]
            ),
        ):
            events.append(event)
    return events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_specialists_cache() -> Any:
    """Each test starts with a clean agent cache, config cache, and block cache."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    clear_config_cache()


# ---------------------------------------------------------------------------
# TestCaptureHarness — validates that both capture helpers return non-empty
# event lists and that Mode A yields at least as many events as Mode B.
# These tests PASS under both the current (pre-propagation) and future
# (post-propagation) implementations.
# ---------------------------------------------------------------------------


class TestCaptureHarness:
    @pytest.mark.asyncio
    async def test_mode_a_events_non_empty(self) -> None:
        specialist = _make_deterministic_specialist()
        events = await _capture_mode_a_events(specialist)
        assert len(events) >= 1, "Mode A outer Runner must yield at least one event"

    @pytest.mark.asyncio
    async def test_mode_b_events_non_empty(self) -> None:
        specialist = _make_deterministic_specialist("test_specialist")
        events = await _capture_mode_b_events(specialist)
        assert len(events) >= 1, "Mode B outer Runner must yield at least one event"

    @pytest.mark.asyncio
    async def test_mode_a_event_count_ge_mode_b(self) -> None:
        specialist_a = _make_deterministic_specialist()
        specialist_b = _make_deterministic_specialist("test_specialist")
        events_a = await _capture_mode_a_events(specialist_a)
        events_b = await _capture_mode_b_events(specialist_b)
        assert len(events_a) >= len(events_b), (
            f"Mode A ({len(events_a)} events) must yield >= Mode B ({len(events_b)} events). "
            "Mode A includes specialist events in the outer stream; Mode B currently does not."
        )


# ---------------------------------------------------------------------------
# TestChatParity — MERGE BLOCKER.
# Verifies that SessionTurnAccumulator.build_delta() produces identical
# input/output/reasoning Increment values for Mode A and Mode B.
# CURRENTLY FAILS for Mode B: specialist events are trapped in the inner
# Runner and never reach the outer stream, so all token counts are 0.
# Fix: propagate inner-Runner events to the outer stream in
# specialist_runtime.run() / delegate_to_specialist.
# ---------------------------------------------------------------------------


class TestChatParity:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("trial", range(10))
    async def test_session_turn_accumulator_delta_matches(self, trial: int) -> None:
        """AC-9 (AH-PRD-09): accumulator deltas must match between Mode A and Mode B.

        MERGE BLOCKER: This test currently fails for Mode B because specialist
        events are trapped in the inner Runner. It will pass once inner-Runner
        events are propagated to the outer stream.
        """
        specialist_a = _make_deterministic_specialist()
        specialist_b = _make_deterministic_specialist("test_specialist")

        events_a = await _capture_mode_a_events(specialist_a)
        events_b = await _capture_mode_b_events(specialist_b)

        acc_a = SessionTurnAccumulator()
        for e in events_a:
            acc_a.add_event(e)
        delta_a = acc_a.build_delta()

        acc_b = SessionTurnAccumulator()
        for e in events_b:
            acc_b.add_event(e)
        delta_b = acc_b.build_delta()

        assert _increments_equal(
            delta_a["input_tokens_total"], delta_b["input_tokens_total"]
        ), (
            f"[trial={trial}] input_tokens_total mismatch: "
            f"Mode A={getattr(delta_a['input_tokens_total'], 'value', delta_a['input_tokens_total'])}, "
            f"Mode B={getattr(delta_b['input_tokens_total'], 'value', delta_b['input_tokens_total'])}. "
            f"Expected both == {_EXPECTED_INPUT}. "
            "MERGE BLOCKER: inner-Runner events not propagated to outer stream."
        )
        assert _increments_equal(
            delta_a["output_tokens_total"], delta_b["output_tokens_total"]
        ), (
            f"[trial={trial}] output_tokens_total mismatch: "
            f"Mode A={getattr(delta_a['output_tokens_total'], 'value', delta_a['output_tokens_total'])}, "
            f"Mode B={getattr(delta_b['output_tokens_total'], 'value', delta_b['output_tokens_total'])}. "
            f"Expected both == {_EXPECTED_OUTPUT}. "
            "MERGE BLOCKER: inner-Runner events not propagated to outer stream."
        )
        assert _increments_equal(
            delta_a["reasoning_tokens_total"], delta_b["reasoning_tokens_total"]
        ), (
            f"[trial={trial}] reasoning_tokens_total mismatch: "
            f"Mode A={getattr(delta_a['reasoning_tokens_total'], 'value', delta_a['reasoning_tokens_total'])}, "
            f"Mode B={getattr(delta_b['reasoning_tokens_total'], 'value', delta_b['reasoning_tokens_total'])}. "
            f"Expected both == {_EXPECTED_REASONING}. "
            "MERGE BLOCKER: inner-Runner events not propagated to outer stream."
        )


# ---------------------------------------------------------------------------
# TestBillingParity — MERGE BLOCKER.
# Verifies that extract_billable_tokens().total_billable sums to 1430 for
# BOTH Mode A and Mode B event streams.
# CURRENTLY FAILS for Mode B (total == 0, not 1430).
# ---------------------------------------------------------------------------


class TestBillingParity:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("trial", range(10))
    async def test_billable_token_totals_match(self, trial: int) -> None:
        """AC-10 (AH-PRD-09): total billable tokens must equal 1430 for both modes.

        MERGE BLOCKER: This test currently fails for Mode B because specialist
        events are trapped in the inner Runner. It will pass once inner-Runner
        events are propagated to the outer stream.
        """
        specialist_a = _make_deterministic_specialist()
        specialist_b = _make_deterministic_specialist("test_specialist")

        events_a = await _capture_mode_a_events(specialist_a)
        events_b = await _capture_mode_b_events(specialist_b)

        total_a = sum(extract_billable_tokens(e).total_billable for e in events_a)
        total_b = sum(extract_billable_tokens(e).total_billable for e in events_b)

        assert total_a == _EXPECTED_TOTAL_BILLABLE, (
            f"[trial={trial}] Mode A total billable = {total_a}, expected {_EXPECTED_TOTAL_BILLABLE}. "
            "Mode A baseline broken — check _CanonicalStubLlm usage_metadata."
        )
        assert total_b == _EXPECTED_TOTAL_BILLABLE, (
            f"[trial={trial}] Mode B total billable = {total_b}, expected {_EXPECTED_TOTAL_BILLABLE}. "
            "MERGE BLOCKER: inner-Runner events not propagated to outer stream. "
            "Specialist billable tokens are trapped in the inner Runner and lost."
        )
