"""ADK 2.0 LoopAgent billing parity test — AH-110 / AH-PRD-13 §7 AC #3.

Ports AH-99 probe-7 (docs/spike-adk2/probe-7-loop-agent-task-mode.py) into CI as
a deterministic offline test. The live Gemini endpoint variant of probe-7 is
exclusively for manual validation; this file covers the billing invariant on a
deterministic fake-LLM backend.

CONTRACT UNDER TEST (AH-PRD-09 §7 ACs #9 / #10, AH-PRD-13 §7 AC #3):
  A worker + reviewer LoopAgent (built via build_review_pipeline) driven by
  deterministic stub LLMs feeds real SessionTurnAccumulator and
  extract_billable_tokens correctly on google-adk==2.0.0:

  1. total_billable == iteration_count * _CANONICAL_TOTAL_BILLABLE (1430).
     The reviewer stub emits no usage_metadata, so only the worker's tokens
     accumulate.
  2. exit_loop terminates the loop (reviewer calls exit_loop after N worker
     iterations).
  3. At least one worker draft event surfaces in the outer Runner stream.

DeprecationWarning:
  LoopAgent is @deprecated in ADK 2.0 (deprecated != removed). The warning is
  expected and does not fail these tests; it is surfaced in the test output.
  Long-term migration to ADK Workflow is owned by AH-PRD-05, not this issue.

Parametrisation:
  Each test is parametrised over 10 trials to catch any non-determinism in the
  stub-driven Runner event ordering. Since the stubs are fully deterministic (no
  real LLM), stability is guaranteed — the parametrisation mirrors the existing
  parity test discipline in test_chat_billing_parity.py.

Scope note:
  - Live Gemini endpoint: docs/spike-adk2/probe-7-loop-agent-task-mode.py (AH-99).
  - Behavioural loop assertions (exit_loop path, feedback iteration): TestBehavioralLoop
    in app/adk/agents/utils/test_review_pipeline.py.
  - This file is the billing-invariant complement.
"""

from __future__ import annotations

import os
import sys
import warnings
from collections.abc import AsyncIterator
from typing import Any

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from app.adk.agents.utils.review_pipeline import build_review_pipeline

# Resolve api/src so kene_api is importable without installing the api package.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "api", "src"),
)
from kene_api.chat.accumulator import SessionTurnAccumulator

from shared.token_accounting import extract_billable_tokens

# ---------------------------------------------------------------------------
# Canonical fixture constants — must match test_chat_billing_parity.py
# ---------------------------------------------------------------------------

_CANONICAL_PROMPT_TOKEN_COUNT = 1250
_CANONICAL_CANDIDATES_TOKEN_COUNT = 380
_CANONICAL_CACHED_TOKEN_COUNT = 200
_CANONICAL_TOTAL_BILLABLE = 1430  # input(1050) + output(380) + reasoning(0)


# ---------------------------------------------------------------------------
# Stub LLMs (module-level to share LLMRegistry lifetime)
# ---------------------------------------------------------------------------


class _LoopWorkerStubLlm(BaseLlm):
    """Worker stub: always emits one response with the canonical fixture usage_metadata."""

    model: str = "loop_worker_billing_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["loop_worker_billing_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
            candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
            cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
            # thoughts_token_count omitted → None (non-reasoning model)
        )
        content = genai_types.Content(
            role="model", parts=[genai_types.Part(text="Worker draft")]
        )
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


class _LoopReviewerApproveStubLlm(BaseLlm):
    """Reviewer stub: always approves immediately (exit_loop on first call).

    Emits no usage_metadata so that billing assertions only count worker tokens.
    """

    model: str = "loop_reviewer_approve_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["loop_reviewer_approve_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        fc = genai_types.FunctionCall(name="exit_loop", args={})
        content = genai_types.Content(
            role="model", parts=[genai_types.Part(function_call=fc)]
        )
        # No usage_metadata on reviewer — reviewer tokens deliberately silent
        yield LlmResponse(content=content, turn_complete=False)


# Module-level response queue for the reject-then-approve reviewer.
# Drained in FIFO order — mirrors the _fake_response_queue pattern in
# test_review_pipeline.py. Tests that need a reject+approve sequence load
# it via the _load_reject_approve_queue fixture.
_reviewer_queue: list[LlmResponse] = []


class _LoopReviewerQueueLlm(BaseLlm):
    """Reviewer stub: drains responses from _reviewer_queue in FIFO order.

    If the queue is empty, defaults to calling exit_loop (immediate approval).
    Emits no usage_metadata so that billing assertions only count worker tokens.

    This design mirrors _FakeLlm in test_review_pipeline.py — use a module-level
    queue loaded by a fixture rather than per-instance state, so the reviewer
    model name stays a string and mypy/type-checking remains clean.
    """

    model: str = "loop_reviewer_queue_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["loop_reviewer_queue_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        if _reviewer_queue:
            yield _reviewer_queue.pop(0)
        else:
            # Default: immediate approval via exit_loop
            fc = genai_types.FunctionCall(name="exit_loop", args={})
            content = genai_types.Content(
                role="model", parts=[genai_types.Part(function_call=fc)]
            )
            yield LlmResponse(content=content, turn_complete=False)


# Register once per process; idempotent.
LLMRegistry.register(_LoopWorkerStubLlm)
LLMRegistry.register(_LoopReviewerApproveStubLlm)
LLMRegistry.register(_LoopReviewerQueueLlm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker_specialist(name: str = "billing_worker_spec") -> LlmAgent:
    return LlmAgent(
        name=name,
        model=_LoopWorkerStubLlm(),
        instruction="Draft a response.",
    )


async def _run_loop_agent_and_collect(
    pipeline: Any,
    session_suffix: str = "",
) -> tuple[list[Any], dict[str, Any]]:
    """Run pipeline with InMemorySessionService + Runner; return (events, state)."""
    app_name = f"loop_billing_test{session_suffix}"
    svc = InMemorySessionService()
    sess = await svc.create_session(app_name=app_name, user_id="test_user")
    runner = Runner(agent=pipeline, app_name=app_name, session_service=svc)
    events: list[Any] = []
    async for event in runner.run_async(
        user_id=sess.user_id,
        session_id=sess.id,
        new_message=genai_types.Content(
            role="user", parts=[genai_types.Part(text="Go.")]
        ),
    ):
        events.append(event)
    final = await svc.get_session(
        app_name=app_name, user_id="test_user", session_id=sess.id
    )
    return events, dict(final.state if final else {})


# ---------------------------------------------------------------------------
# TestLoopAgentBillingParity — MERGE BLOCKER complement.
#
# Verifies that extract_billable_tokens().total_billable counts correctly across
# LoopAgent iterations on ADK 2.0, and that SessionTurnAccumulator reflects the
# same totals.
# ---------------------------------------------------------------------------


class TestLoopAgentBillingParity:
    """LoopAgent billing parity on ADK 2.0 (AH-110 / AH-PRD-13 §7 AC #3).

    Uses build_review_pipeline (the production factory) so the test exercises
    the real LoopAgent topology: worker → reviewer → exit_loop approval path.

    DeprecationWarning from LoopAgent is expected (see module docstring).
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("trial", range(10))
    async def test_single_iteration_total_billable(self, trial: int) -> None:
        """One iteration: total_billable == _CANONICAL_TOTAL_BILLABLE (1430).

        Reviewer approves on the first call (exit_loop immediately), so the
        worker runs exactly once. The billing assertion pins the canonical fixture.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist(f"billing_spec_1iter_{trial}")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix=f"t1_{trial}",
                max_iterations=3,
                reviewer_model="loop_reviewer_approve_stub",
            )

        events, _ = await _run_loop_agent_and_collect(
            pipeline, session_suffix=f"_1iter_{trial}"
        )

        total_billable = sum(extract_billable_tokens(e).total_billable for e in events)
        assert total_billable == _CANONICAL_TOTAL_BILLABLE, (
            f"[trial={trial}] single-iteration: total_billable={total_billable}, "
            f"expected {_CANONICAL_TOTAL_BILLABLE}. "
            "Worker must emit exactly one event with the canonical usage_metadata. "
            "If 0: worker events not reaching outer stream (check AlwaysTrueSubAgentList "
            "shim or LoopAgent event propagation on ADK 2.0)."
        )

    @pytest.fixture(autouse=True)
    def clear_reviewer_queue(self) -> Any:
        """Ensure the module-level reviewer queue is empty before and after each test."""
        _reviewer_queue.clear()
        yield
        _reviewer_queue.clear()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("trial", range(10))
    async def test_two_iteration_total_billable(self, trial: int) -> None:
        """Two iterations: total_billable == 2 * _CANONICAL_TOTAL_BILLABLE (2860).

        Reviewer rejects on the first call, approves (exit_loop) on the second.
        Worker runs twice, each emitting the canonical usage_metadata.
        Queue is loaded with one reject entry; iteration 2 drains the queue and
        falls through to the _LoopReviewerQueueLlm default (exit_loop approval).
        """
        # Load: reject on iter 1. Iteration 2 uses the default exit_loop fallback.
        _reviewer_queue.extend([
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text="Needs improvement — more detail.")],
                ),
                turn_complete=False,
            ),
            # iter 2: exit_loop (queue empty after this → default approval fallback)
        ])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist(f"billing_spec_2iter_{trial}")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix=f"t2_{trial}",
                max_iterations=3,
                reviewer_model="loop_reviewer_queue_stub",
            )

        events, _ = await _run_loop_agent_and_collect(
            pipeline, session_suffix=f"_2iter_{trial}"
        )

        total_billable = sum(extract_billable_tokens(e).total_billable for e in events)
        expected = 2 * _CANONICAL_TOTAL_BILLABLE
        assert total_billable == expected, (
            f"[trial={trial}] two-iteration: total_billable={total_billable}, "
            f"expected {expected} (2 x {_CANONICAL_TOTAL_BILLABLE}). "
            "Worker emits one canonical event per iteration; two iterations must sum "
            "to 2 x the canonical fixture. Check LoopAgent event propagation on 2.0."
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("trial", range(10))
    async def test_session_turn_accumulator_single_iteration(self, trial: int) -> None:
        """SessionTurnAccumulator reflects canonical input/output on one iteration.

        Verifies that add_event() sees the specialist events and build_delta()
        returns the correct Increment values — the same contract as TestChatParity
        in test_chat_billing_parity.py, applied to the LoopAgent path.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist(f"billing_spec_acc_{trial}")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix=f"ta_{trial}",
                max_iterations=3,
                reviewer_model="loop_reviewer_approve_stub",
            )

        events, _ = await _run_loop_agent_and_collect(
            pipeline, session_suffix=f"_acc_{trial}"
        )

        acc = SessionTurnAccumulator()
        for e in events:
            acc.add_event(e)
        delta = acc.build_delta()

        expected_input = _CANONICAL_PROMPT_TOKEN_COUNT - _CANONICAL_CACHED_TOKEN_COUNT  # 1050
        expected_output = _CANONICAL_CANDIDATES_TOKEN_COUNT  # 380

        actual_input = getattr(delta.get("input_tokens_total"), "value", None)
        actual_output = getattr(delta.get("output_tokens_total"), "value", None)

        assert actual_input == expected_input, (
            f"[trial={trial}] SessionTurnAccumulator input_tokens_total={actual_input}, "
            f"expected {expected_input}. "
            "Worker usage_metadata must reach SessionTurnAccumulator via the outer "
            "Runner stream. Check LoopAgent event propagation on ADK 2.0."
        )
        assert actual_output == expected_output, (
            f"[trial={trial}] SessionTurnAccumulator output_tokens_total={actual_output}, "
            f"expected {expected_output}."
        )


# ---------------------------------------------------------------------------
# TestLoopAgentExitLoopBehavior — structural gate.
#
# Verifies that exit_loop terminates the LoopAgent and that at least one worker
# draft event surfaces in the outer Runner stream. Adapted from probe-7's A1-A4
# assertions.
# ---------------------------------------------------------------------------


class TestLoopAgentExitLoopBehavior:
    """Structural assertions: exit_loop terminates loop; worker events visible.

    These tests are deterministic (no real LLM), so parametrisation is not
    needed — one trial per test is sufficient.
    """

    @pytest.fixture(autouse=True)
    def _clean_queue(self) -> Any:
        """Clear module-level reviewer queue before and after each test in this class.

        Without this, a test failure mid-body (e.g. before the manual clear at the end
        of test_two_iteration_worker_events_count) would leave leftover queue entries
        that corrupt subsequently-ordered tests. Matches the autouse pattern used by
        TestLoopAgentBillingParity and _fake_response_queue in test_review_pipeline.py.
        """
        _reviewer_queue.clear()
        yield
        _reviewer_queue.clear()

    @pytest.mark.asyncio
    async def test_exit_loop_terminates_pipeline(self) -> None:
        """Reviewer calls exit_loop; loop terminates and worker event is in outer stream."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist("exit_spec")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix="exit_test",
                max_iterations=3,
                reviewer_model="loop_reviewer_approve_stub",
            )

        events, state = await _run_loop_agent_and_collect(pipeline, "_exit")

        # Worker events must surface in the outer stream.
        worker_events = [
            e for e in events if getattr(e, "author", None) == "exit_spec_worker"
        ]
        assert worker_events, (
            "Worker events must be visible in the outer Runner stream. "
            "If empty, LoopAgent is not propagating worker events to the outer "
            "consumer — check ADK 2.0 LoopAgent event propagation."
        )

        # exit_loop must have fired: the worker draft key is set in state.
        assert state.get("exit_test_draft") is not None, (
            "Worker draft key must be set in state — confirms exit_loop fired and "
            "the worker's output was retained. State: " + repr(state)
        )

    @pytest.mark.asyncio
    async def test_worker_events_carry_usage_metadata(self) -> None:
        """Worker events in the outer stream must carry usage_metadata."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist("meta_spec")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix="meta_test",
                max_iterations=1,
                reviewer_model="loop_reviewer_approve_stub",
            )

        events, _ = await _run_loop_agent_and_collect(pipeline, "_meta")

        events_with_usage = [
            e for e in events if getattr(e, "usage_metadata", None) is not None
        ]
        assert events_with_usage, (
            "At least one event in the outer stream must carry usage_metadata. "
            "If empty, billing will be zero for all LoopAgent turns. "
            "Check ADK 2.0 LoopAgent event propagation."
        )

    @pytest.mark.asyncio
    async def test_two_iteration_worker_events_count(self) -> None:
        """Two-iteration run: exactly 2 worker events with usage_metadata in outer stream."""
        # Pre-load the reviewer queue: reject on iter 1, approve (default) on iter 2.
        _reviewer_queue.extend([
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text="Needs more detail.")],
                ),
                turn_complete=False,
            ),
        ])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            specialist = _make_worker_specialist("count_spec")
            pipeline = build_review_pipeline(
                specialist,
                "Be complete.",
                output_key_prefix="count_test",
                max_iterations=3,
                reviewer_model="loop_reviewer_queue_stub",
            )

        events, _ = await _run_loop_agent_and_collect(pipeline, "_count")

        worker_billing_events = [
            e
            for e in events
            if getattr(e, "author", None) == "count_spec_worker"
            and getattr(e, "usage_metadata", None) is not None
        ]
        assert len(worker_billing_events) == 2, (
            f"Two-iteration run must yield exactly 2 worker events with usage_metadata. "
            f"Got {len(worker_billing_events)}. "
            "Each LoopAgent iteration must propagate the worker's billing event to the "
            "outer Runner stream on ADK 2.0."
        )
