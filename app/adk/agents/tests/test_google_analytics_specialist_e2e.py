"""End-to-end tests for the Google Analytics Specialist (AH-PRD-03).

AH-27 — code execution verification (AC #6):
    Builds a ``LlmAgent`` from the GA specialist config with
    ``code_executor=BuiltInCodeExecutor()`` and verifies that numerical queries
    produce ``executable_code`` + ``code_execution_result(OUTCOME_OK)`` parts in
    the ADK event stream. Bypasses Firestore/MCP to isolate code-execution
    behaviour.

AH-28 — OAuth error handling (AC #9):
    Exercises ``ga_oauth_after_tool_callback`` directly to assert that a 401
    response from GA MCP sets ``_requires_reauth=True`` and
    ``_reauth_service="google-analytics"`` in session state and returns a
    user-visible error message. Does not require a live model.

AH-29 — Multi-tenant OAuth isolation (AC #10):
    Two concurrent sessions with different ``ga_credentials`` each use their
    own OAuth tokens via ``_make_header_provider("ga_oauth")``. Verifies
    ``McpToolsetPool`` keys on ``(kind, server_id, account_id,
    sha256(mcp_creds))`` and that no cross-session header bleed occurs.

AH-32 — Code-execution error handling (AC #7):
    Drives ``numerical_analyst_agent`` directly with a prompt that deterministically
    triggers ``OUTCOME_FAILED`` (divide-by-zero).  Asserts the agent either retries
    with corrected code or returns a clear, human-readable error message — and never
    surfaces a raw stack trace or the literal ``OUTCOME_FAILED`` token, and never
    fabricates a numerical answer as if the calculation succeeded.

Marking convention:
    Tests that require a live Gemini model are marked ``@pytest.mark.llm``
    so CI can opt-in without breaking the default fast suite. AH-28 and
    AH-29 tests do NOT require a live model call.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any, Final
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.adk.tools.function_tool import FunctionTool
from google.genai import types as genai_types
from google.genai.errors import ClientError
from google.genai.types import Content, FunctionCall, Outcome, Part

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory import sub_agent_attacher as attacher
from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
from app.adk.agents.agent_factory.header_provider import _make_header_provider
from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
from app.adk.security.hooks import ga_oauth_after_tool_callback

_GEMINI_CREDS_AVAILABLE = bool(
    os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT")
)

# ---------------------------------------------------------------------------
# Stub LLMs (AH-29)
# ---------------------------------------------------------------------------


class _TransferToGaSpecialistStubLlm(BaseLlm):
    """Root LLM that emits transfer_to_agent(agent_name='google_analytics_specialist')."""

    model: str = "transfer_to_ga_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["transfer_to_ga_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        func_call = FunctionCall(
            name="transfer_to_agent",
            args={"agent_name": "google_analytics_specialist"},
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


class _GaSpecialistStubLlm(BaseLlm):
    """Specialist LLM that emits a single deterministic text response."""

    model: str = "ga_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["ga_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        content = Content(
            role="model", parts=[Part.from_text(text="GA specialist response")]
        )
        yield LlmResponse(content=content, turn_complete=True)


# ---------------------------------------------------------------------------
# AH-33: Fake LLM for review-loop iteration test
#
# Uses a distinct model-name pattern ("^fake-ga-iter-.*") to avoid any
# coupling with the "^fake-behavioral-.*" pattern registered by
# app.adk.agents.utils.test_review_pipeline._FakeLlm.  Both worker and
# reviewer drain from the same FIFO queue — the response order encodes the
# iteration sequence (worker-1, reviewer-1, worker-2, reviewer-2).
# ---------------------------------------------------------------------------

_GA_ITER_QUEUE: list[LlmResponse] = []


class _GaIterFakeLlm(BaseLlm):
    """Fake LLM that drains responses from _GA_ITER_QUEUE in FIFO order.

    Handles both "fake-ga-iter-worker" (worker) and "fake-ga-iter-reviewer"
    (reviewer) model strings.  Response assignment is purely positional, which
    makes the queue the single source of truth for the iteration sequence.
    """

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^fake-ga-iter-.*"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        if _GA_ITER_QUEUE:
            yield _GA_ITER_QUEUE.pop(0)
        else:
            raise AssertionError(
                "_GA_ITER_QUEUE exhausted — the LoopAgent consumed more responses "
                "than were queued. Ensure the test loads all 4 expected responses "
                "(worker-1, reviewer-1, worker-2, reviewer-2) and that "
                "max_iterations was not exceeded."
            )


# Register once per process; idempotent — ADK's registry has no deregister API.
# Pattern "^fake-ga-iter-.*" is intentionally disjoint from the "^fake-behavioral-.*"
# pattern in app.adk.agents.utils.test_review_pipeline to prevent registry collisions.
# If you add a new fake-LLM subclass here, choose a distinct pattern that does not
# overlap with any existing registration in this file or sibling test files.
LLMRegistry.register(_GaIterFakeLlm)


# ---------------------------------------------------------------------------
# GA specialist instruction + stub tools (AH-27)
# ---------------------------------------------------------------------------

_GA_TEST_INSTRUCTION = """You are a Google Analytics specialist.

Retrieve data using the GA MCP tools, then delegate ALL arithmetic to the
numerical_analyst tool. Never compute numbers in-context.

When you need to calculate a percentage, average, growth rate, or any other
arithmetic, pass the specific numbers and a description of the calculation to
the numerical_analyst tool, then include its returned figure and formula verbatim
in your reply.

Available tools:
- get_account_summaries_mt - list GA accounts (no required params)
- run_report_mt - run analytics reports (params: property_id, date_ranges, metrics)
- numerical_analyst - compute arithmetic; pass specific numbers and calculation description
"""


def get_account_summaries_mt() -> str:
    """List all Google Analytics accounts and properties."""
    return '{"accounts": [{"displayName": "Test Account", "propertySummaries": [{"property": "properties/123456789", "displayName": "Test Property"}]}]}'


def run_report_mt(
    property_id: str,
    date_ranges: list,
    metrics: list | None = None,
    dimensions: list | None = None,
) -> str:
    """Run a GA analytics report."""
    return '{"rows": [{"metricValues": [{"value": "4823"}]}, {"metricValues": [{"value": "5391"}]}]}'


_NUMERICAL_QUERIES = [
    (
        "percentage",
        "Property 123456789: sessions were 4823 last week and 5391 this week. "
        "What is the percentage change week-over-week?",
    ),
    (
        "trend",
        "Property 123456789: daily sessions for the last 7 days are "
        "[421, 489, 510, 478, 502, 521, 548]. What is the week-over-week trend?",
    ),
    (
        "average",
        "Property 123456789: bounce rates for the past 7 days are "
        "[0.42, 0.38, 0.45, 0.41, 0.39, 0.40, 0.43]. What is the average bounce rate?",
    ),
]

# ---------------------------------------------------------------------------
# Shared helpers (AH-29)
# ---------------------------------------------------------------------------


def _make_ga_specialist_agent() -> LlmAgent:
    """Return an LlmAgent named 'google_analytics_specialist' backed by the stub LLM."""
    return LlmAgent(
        name="google_analytics_specialist",
        model=_GaSpecialistStubLlm(),
        instruction="Google Analytics specialist",
        disallow_transfer_to_parent=True,
    )


def _make_ga_config() -> MergedAgentConfig:
    """Return a MergedAgentConfig for the GA specialist (pure-mock variant)."""
    return MergedAgentConfig(
        instruction="You are a Google Analytics specialist.",
        model="ga_specialist_stub",
        description="Google Analytics specialist",
        mcp_servers=["google_analytics_mcp"],
        ken_e_sub_agent=True,
    )


def _compute_creds_hash(mcp_creds: dict[str, Any]) -> str:
    """Reproduce the creds_hash logic from specialist_runtime._build_specialist."""
    return hashlib.sha256(
        json.dumps(mcp_creds, sort_keys=True, default=str).encode()
    ).hexdigest()


async def _run_ga_specialist_for_session(
    *,
    account_id: str,
    ga_credentials: dict[str, Any],
    mcp_creds: dict[str, Any],
    specialist_agent: LlmAgent,
) -> list[Any]:
    """Spin up a Runner for one session and return all events."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    root = LlmAgent(
        name="root_agent",
        model=_TransferToGaSpecialistStubLlm(),
        instruction="Route queries.",
        tools=[],
        before_agent_callback=[attacher.attach_specialists_before_agent_callback],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=f"mt_isolation_test_{account_id}",
        user_id=f"user_{account_id}",
        state={
            "account_id": account_id,
            "ga_credentials": ga_credentials,
            "mcp_creds_google_analytics_mcp": mcp_creds,
        },
    )
    runner = Runner(
        agent=root,
        app_name=f"mt_isolation_test_{account_id}",
        session_service=session_service,
    )

    events: list[Any] = []
    ga_config = _make_ga_config()
    with (
        patch.object(
            attacher,
            "list_account_agent_configs_cached",
            return_value=["google_analytics_specialist"],
        ),
        patch.object(attacher, "resolve_config", return_value=ga_config),
        patch.object(attacher, "resolve_agent", return_value=specialist_agent),
    ):
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[Part.from_text(text="Show me GA data")],
            ),
        ):
            events.append(event)

    return events


# ---------------------------------------------------------------------------
# Shared test infrastructure (AH-28)
# ---------------------------------------------------------------------------


@dataclass
class _MockState:
    """Dict-like mock of ADK session state."""

    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data


@dataclass
class _MockToolContext:
    """Minimal mock of ADK ToolContext."""

    state: _MockState = field(default_factory=_MockState)


def _make_tool(name: str = "run_report_mt") -> MagicMock:
    t = MagicMock()
    t.name = name
    return t


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_caches() -> Any:
    """Reset specialist/config/fingerprint caches before and after every test."""
    from app.adk.agents.utils.config_cache import clear_config_cache
    from app.adk.agents.utils.system_settings import (
        clear_system_settings_cache_for_tests,
    )

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    attacher._reset_applied_state_for_tests()
    clear_config_cache()
    clear_system_settings_cache_for_tests()
    _GA_ITER_QUEUE.clear()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    attacher._reset_applied_state_for_tests()
    clear_config_cache()
    clear_system_settings_cache_for_tests()
    assert not _GA_ITER_QUEUE, (
        f"_GA_ITER_QUEUE not empty after test teardown — "
        f"{len(_GA_ITER_QUEUE)} response(s) were not consumed. "
        "This usually means fewer LoopAgent iterations ran than expected."
    )
    _GA_ITER_QUEUE.clear()


# ---------------------------------------------------------------------------
# AH-27 (AH-149 refresh): code execution E2E tests
#
# AH-149 restructured the GA specialist so code execution lives exclusively
# in a ``numerical_analyst`` leaf agent exposed as an AgentTool.  These tests
# are updated to reflect the split shape:
#
#   1. The parent GA specialist is built WITHOUT a code_executor (validates
#      that it no longer triggers the Gemini 2.5+ multi-tool 400 error).
#   2. The numerical_analyst leaf agent is driven DIRECTLY via its own Runner
#      to assert that executable_code + code_execution_result(OUTCOME_OK) parts
#      appear in its own event stream.  This bypasses the known AH-75 limitation
#      (AgentTool.run_async discards inner sub-agent events from the outer
#      stream); propagating those events to the parent stream is AH-PRD-15 scope.
# ---------------------------------------------------------------------------

_NUMERICAL_ANALYST_TEST_INSTRUCTION = """You are a numerical computation assistant.

Given numbers and a description of the calculation, write and execute a short
Python snippet to compute the result, then return the figure and the formula.
"""


@pytest.mark.parametrize("query_name,query_text", _NUMERICAL_QUERIES)
@pytest.mark.parametrize("trial", [1, 2, 3])
@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_ga_numerical_query_uses_code_execution(
    trial: int, query_name: str, query_text: str
) -> None:
    """AC #6 (AH-PRD-03 §7, AH-149 refresh): the numerical_analyst sub-agent
    must produce executable_code + code_execution_result(OUTCOME_OK) parts
    when driven with a numerical prompt.

    The parent GA specialist is also built to verify it can be constructed
    without the Gemini 2.5+ multi-tool 400 error (no code_executor on the
    parent; AgentTool carries the analyst).
    """
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.agent_tool import AgentTool

    # --- Build the split shape (AH-149) ---

    # Child: code-execution only, no function tools.
    numerical_analyst_agent = Agent(
        name="numerical_analyst_agent",
        model="gemini-2.5-flash",
        code_executor=BuiltInCodeExecutor(),
        instruction=_NUMERICAL_ANALYST_TEST_INSTRUCTION,
    )

    # Parent: modern Gemini, GA MCP stubs, AgentTool wrapping the analyst.
    # No code_executor — building this agent with a modern Gemini model and
    # the AgentTool validates there is no 400 multi-tool rejection.
    parent_instruction = (
        _GA_TEST_INSTRUCTION
        + "\nFor any arithmetic, call the numerical_analyst tool with only the"
        " specific numbers and a description of the calculation."
    )
    LlmAgent(  # built to verify no HTTP 400 on construction (Gemini 2.5+ rejects code-exec + function tools)
        name="google_analytics_specialist",
        model="gemini-2.5-flash",
        instruction=parent_instruction,
        tools=[
            AgentTool(agent=numerical_analyst_agent),
            FunctionTool(get_account_summaries_mt),
            FunctionTool(run_report_mt),
        ],
        disallow_transfer_to_parent=True,
    )

    # --- Drive the numerical_analyst leaf directly (AH-75: AgentTool drops
    #     inner events from the outer stream; assert code-exec on its own
    #     Runner, which is the methodology validated in the issue). ---
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="numerical_analyst_e2e", user_id="test_user"
    )
    runner = Runner(
        agent=numerical_analyst_agent,
        app_name="numerical_analyst_e2e",
        session_service=session_service,
    )

    all_parts: list[Part] = []
    try:
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=query_text)],
            ),
        ):
            if event.content and event.content.parts:
                all_parts.extend(event.content.parts)
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"Gemini credentials lack required permission (HTTP 403). "
                f"To run this test grant `roles/aiplatform.user` to the "
                f"service account, or set GOOGLE_API_KEY for the Google AI "
                f"API path. Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"Model 'gemini-2.5-flash' is not available in this Vertex "
                f"project/region (HTTP 404). Run where gemini-2.5-flash is "
                f"enabled or check project quotas. Original error: {exc!s:.160}"
            )
        raise

    has_exec_code = any(
        p.executable_code and p.executable_code.code for p in all_parts
    )
    has_exec_result = any(
        p.code_execution_result
        and p.code_execution_result.outcome == Outcome.OUTCOME_OK
        for p in all_parts
    )

    assert has_exec_code, (
        f"[{query_name} trial {trial}] numerical_analyst: no executable_code part. "
        f"Parts collected: {[type(p).__name__ for p in all_parts]}"
    )
    assert has_exec_result, (
        f"[{query_name} trial {trial}] numerical_analyst: no OUTCOME_OK code_execution_result. "
        f"Parts collected: {[type(p).__name__ for p in all_parts]}"
    )


# ---------------------------------------------------------------------------
# AH-32: Code-execution error handling — OUTCOME_FAILED retry or clear error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("trial", [1, 2, 3])
@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_numerical_analyst_handles_outcome_failed(trial: int) -> None:
    """AC #7 (AH-PRD-03 §7, AH-32): when code execution returns OUTCOME_FAILED,
    the numerical_analyst must either (a) retry with corrected code or (b) report
    a clear, human-readable error — never surface a raw stack trace or the literal
    token OUTCOME_FAILED, and never fabricate a successful numerical answer.

    Uses a divide-by-zero prompt to deterministically trigger OUTCOME_FAILED
    (ZeroDivisionError reliably maps to that outcome in the Gemini sandbox).
    Drives numerical_analyst_agent directly via its own Runner (same AH-75
    workaround as AH-27: AgentTool.run_async discards inner events from the
    outer stream).

    Three trials via @pytest.mark.parametrize for flake tolerance: each trial
    validates independently; assertions (2)-(4) hold even if a trial does not
    exercise code execution at all (text-only answer is also an acceptable path).
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.tools.agent_tools.numerical_analyst import (
        create_numerical_analyst_agent,
    )

    numerical_analyst_agent = create_numerical_analyst_agent()

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=f"outcome_failed_test_trial_{trial}",
        user_id=f"test_user_trial_{trial}",
    )
    runner = Runner(
        agent=numerical_analyst_agent,
        app_name=f"outcome_failed_test_trial_{trial}",
        session_service=session_service,
    )

    all_parts: list[Part] = []
    try:
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[
                    genai_types.Part.from_text(
                        text=(
                            "Compute 1 / 0 using Python code execution. "
                            "Return the result and the formula."
                        )
                    )
                ],
            ),
        ):
            if event.content and event.content.parts:
                all_parts.extend(event.content.parts)
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"Gemini credentials lack required permission (HTTP 403). "
                f"To run this test grant `roles/aiplatform.user` to the "
                f"service account, or set GOOGLE_API_KEY for the Google AI "
                f"API path. Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"Model 'gemini-2.5-flash' is not available in this Vertex "
                f"project/region (HTTP 404). Run where gemini-2.5-flash is "
                f"enabled or check project quotas. Original error: {exc!s:.160}"
            )
        raise

    # Collect text parts and failure indicators.
    text_parts = [p for p in all_parts if p.text]
    final_text = " ".join(p.text for p in text_parts if p.text)
    failed_parts = [
        p
        for p in all_parts
        if p.code_execution_result
        and p.code_execution_result.outcome == Outcome.OUTCOME_FAILED
    ]
    exec_code_parts = [p for p in all_parts if p.executable_code and p.executable_code.code]
    # Define before assertion (1) so the gate condition is available.
    has_correction_retry = len(exec_code_parts) >= 2  # second attempt = retry

    # (1) If code ran exactly once (no retry), OUTCOME_FAILED must appear —
    # confirms the failure path was exercised rather than suppressed.
    # A two-attempt retry path is also valid: the first attempt fails and the
    # second may succeed, so we do NOT require OUTCOME_FAILED when a retry ran.
    if exec_code_parts and not has_correction_retry:
        assert failed_parts, (
            f"[trial {trial}] executable_code ran once but no "
            f"OUTCOME_FAILED code_execution_result found. Parts: "
            f"{[type(p).__name__ for p in all_parts]}"
        )

    # (2) The final text must not contain a raw Python stack trace marker.
    assert "Traceback (most recent call last)" not in final_text, (
        f"[trial {trial}] Specialist leaked a raw Python stack trace. "
        f"Final text excerpt: {final_text[:400]!r}"
    )

    # (3) The literal token OUTCOME_FAILED must not appear in the reply.
    assert "OUTCOME_FAILED" not in final_text, (
        f"[trial {trial}] Specialist leaked the raw OUTCOME_FAILED enum token. "
        f"Final text excerpt: {final_text[:400]!r}"
    )

    # (4) The response must not silently fabricate a numeric result for 1/0.
    # A correct handler either (a) acknowledges the failure with a specific
    # phrase, or (b) retried with corrected code.  "error" alone is excluded
    # from the phrase list because it is too broad — any incidental mention of
    # "error" would satisfy the check even if the agent fabricated a result.
    failure_acknowledged = any(
        phrase in final_text.lower()
        for phrase in (
            "division by zero",
            "cannot compute",
            "cannot be computed",
            "undefined",
            "zero division",
            "zerodivisionerror",  # lowercase to match .lower() output
        )
    )
    assert failure_acknowledged or has_correction_retry, (
        f"[trial {trial}] Specialist neither acknowledged the division-by-zero "
        f"failure nor produced a correction retry. This suggests silent in-context "
        f"fallback. Final text excerpt: {final_text[:400]!r}"
    )

    # (5) The response must contain at least one text part (non-empty reply).
    assert text_parts, (
        f"[trial {trial}] Specialist produced no text parts at all. "
        f"All parts: {[type(p).__name__ for p in all_parts]}"
    )


# ---------------------------------------------------------------------------
# AH-28: GA OAuth 401 → _requires_reauth integration tests
# ---------------------------------------------------------------------------


class TestGaOauth401ErrorHandling:
    """Integration tests for the OAuth-expiry error-handling path (AH-28).

    These tests do NOT require a live model — they exercise
    ``ga_oauth_after_tool_callback`` directly to reproduce the full session-
    state mutation that PRD §7 AC #9 requires.
    """

    @pytest.mark.asyncio
    async def test_401_response_sets_requires_reauth_flag(self) -> None:
        """AC #9 (part 1): _requires_reauth is True in session state after 401."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "401 Unauthorized from GA MCP"}

        await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert ctx.state["_requires_reauth"] is True

    @pytest.mark.asyncio
    async def test_401_response_sets_reauth_service(self) -> None:
        """_reauth_service is set to 'google-analytics' after 401."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "token expired"}

        await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert ctx.state["_reauth_service"] == "google-analytics"

    @pytest.mark.asyncio
    async def test_401_response_returns_user_visible_message(self) -> None:
        """AC #9 (part 2): response contains a clear, user-visible message."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "invalid_grant"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None, "Callback must return a non-None replacement dict"
        assert "Please reconnect Google Analytics" in result["message"]

    @pytest.mark.asyncio
    async def test_401_message_contains_no_token_internals(self) -> None:
        """AC #9: error message must not leak token bytes or stack traces."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {
            "error": True,
            "message": "token has been revoked",
            "_raw_token": "ya29.secret_access_token_bytes",
        }

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None
        assert "ya29" not in result["message"]
        assert "secret_access_token_bytes" not in result["message"]
        assert "Traceback" not in result["message"]

    @pytest.mark.asyncio
    async def test_specialist_does_not_silent_retry_on_401(self) -> None:
        """AC: callback returns non-None to prevent silent retry."""
        ctx = _MockToolContext()
        tool = _make_tool()
        mcp_401_response = {"error": True, "message": "401 Unauthorized"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, mcp_401_response)

        assert result is not None
        assert result["error"] == "authentication_required"

    @pytest.mark.asyncio
    async def test_token_expiry_variants_all_trigger_reauth(self) -> None:
        """Multiple real-world 401 response shapes from GA MCP all set _requires_reauth."""
        real_world_responses = [
            {"error": True, "message": "Request had invalid authentication credentials. "
             "Expected OAuth 2 access token, login cookie or other valid authentication "
             "credential. See https://developers.google.com/identity/sign-in/web/devconsole-project. "
             "401"},
            {"isError": True, "message": "invalid_grant: Token has been expired or revoked."},
            {"_error": "HTTPStatusError: 401 Unauthorized"},
            "token has been revoked by the user",
        ]

        for response in real_world_responses:
            ctx = _MockToolContext()
            result = await ga_oauth_after_tool_callback(_make_tool(), {}, ctx, response)
            assert ctx.state.get("_requires_reauth") is True, (
                f"Expected _requires_reauth=True for response: {response!r}"
            )
            assert result is not None, f"Expected non-None result for response: {response!r}"

    @pytest.mark.asyncio
    async def test_successful_ga_response_does_not_set_reauth(self) -> None:
        """A successful GA MCP response must not trigger reauth."""
        ctx = _MockToolContext()
        tool = _make_tool()
        success_response = {
            "rows": [{"dimensions": ["2024-01-01"], "metrics": [{"values": ["1000"]}]}],
            "totals": [{"values": ["7000"]}],
        }

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, success_response)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data

    @pytest.mark.asyncio
    async def test_permission_denied_does_not_set_reauth(self) -> None:
        """Non-401 errors (e.g. permission_denied) must not set _requires_reauth."""
        ctx = _MockToolContext()
        tool = _make_tool()
        permission_denied = {"error": "permission_denied", "message": "User lacks access"}

        result = await ga_oauth_after_tool_callback(tool, {}, ctx, permission_denied)

        assert result is None
        assert "_requires_reauth" not in ctx.state._data


# ---------------------------------------------------------------------------
# AH-29 — Multi-tenant OAuth isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_analytics_specialist_multi_tenant_isolation() -> None:
    """AC #10 (AH-PRD-03 §7): two concurrent sessions with different ``ga_credentials``
    each use their own OAuth tokens; ``McpToolsetPool`` returns distinct entries
    keyed on ``(server_id, account_id, sha256(mcp_creds))``; no cross-session
    header bleed.
    """
    ACCOUNT_A = "acct_a_tenant_isolation"
    ACCOUNT_B = "acct_b_tenant_isolation"

    GA_CREDS_A: dict[str, Any] = {"access_token": "tok_A", "tenant_id": "tenant_A"}
    GA_CREDS_B: dict[str, Any] = {"access_token": "tok_B", "tenant_id": "tenant_B"}

    MCP_CREDS_A: dict[str, Any] = {"refresh_signature": "sig_A"}
    MCP_CREDS_B: dict[str, Any] = {"refresh_signature": "sig_B"}

    # --- Assertion 1: closure isolation ------------------------------------
    provider = _make_header_provider("ga_oauth")

    ctx_a: MagicMock = MagicMock()
    ctx_a.state = {"ga_credentials": GA_CREDS_A}

    ctx_b: MagicMock = MagicMock()
    ctx_b.state = {"ga_credentials": GA_CREDS_B}

    headers_a = provider(ctx_a)
    headers_b = provider(ctx_b)

    assert headers_a.get("Authorization") == "Bearer tok_A", (
        f"Session A header provider must return tok_A; got {headers_a}"
    )
    assert headers_a.get("X-Tenant-ID") == "tenant_A", (
        f"Session A header provider must return tenant_A; got {headers_a}"
    )
    assert headers_b.get("Authorization") == "Bearer tok_B", (
        f"Session B header provider must return tok_B; got {headers_b}"
    )
    assert headers_b.get("X-Tenant-ID") == "tenant_B", (
        f"Session B header provider must return tenant_B; got {headers_b}"
    )
    assert headers_a != headers_b
    assert "tok_B" not in headers_a.values()
    assert "tok_A" not in headers_b.values()

    # --- Assertion 2 & 3: pool isolation via _build_specialist -------------
    shared_pool = McpToolsetPool()
    toolset_calls: list[str] = []

    def _tracking_build_toolset(server_id: str, _doc: Any, **_kw: Any) -> MagicMock:
        toolset_calls.append(server_id)
        return MagicMock(name=f"toolset_{server_id}_{len(toolset_calls)}")

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=shared_pool,
            )
        )
        from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
            _FakeFirestoreDb,
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): {"enabled": True}}
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=fake_db,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
                side_effect=_tracking_build_toolset,
            )
        )
        stack.enter_context(
            patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=lambda config, *, name, tools=None, **_kw: MagicMock(
                    name=f"llmagent_{name}", tools=tools or []
                ),
            )
        )

        ga_config = _make_ga_config()

        async def _build_for(account_id: str, session_state: dict[str, Any]) -> Any:
            return await asyncio.to_thread(
                sr._build_specialist,
                ga_config,
                "google_analytics_specialist",
                account_id,
                session_state=session_state,
                mcp_pool=shared_pool,
            )

        specialist_a, specialist_b = await asyncio.gather(
            _build_for(
                ACCOUNT_A,
                {"ga_credentials": GA_CREDS_A, "mcp_creds_google_analytics_mcp": MCP_CREDS_A},
            ),
            _build_for(
                ACCOUNT_B,
                {"ga_credentials": GA_CREDS_B, "mcp_creds_google_analytics_mcp": MCP_CREDS_B},
            ),
        )

    assert len(shared_pool._pool) == 2, (
        f"Shared pool must have exactly 2 entries; got {len(shared_pool._pool)}"
    )

    pool_keys = list(shared_pool._pool.keys())
    assert all(len(k) == 4 for k in pool_keys)

    kinds = {k[0] for k in pool_keys}
    server_ids = {k[1] for k in pool_keys}
    account_ids_in_keys = {k[2] for k in pool_keys}
    creds_hashes = {k[3] for k in pool_keys}

    assert kinds == {"cloud_run"}
    assert server_ids == {"google_analytics_mcp"}
    assert account_ids_in_keys == {ACCOUNT_A, ACCOUNT_B}
    assert len(creds_hashes) == 2, (
        f"Pool keys must have two distinct creds_hashes; got {creds_hashes}"
    )

    expected_hash_a = _compute_creds_hash(MCP_CREDS_A)
    expected_hash_b = _compute_creds_hash(MCP_CREDS_B)
    assert creds_hashes == {expected_hash_a, expected_hash_b}

    assert len(toolset_calls) == 2, (
        f"build_toolset_for_doc must be called exactly twice; got {len(toolset_calls)}"
    )
    assert all(s == "google_analytics_mcp" for s in toolset_calls)
    assert specialist_a is not specialist_b

    headers_a_again = provider(ctx_a)
    headers_b_again = provider(ctx_b)
    assert headers_a_again == headers_a
    assert headers_b_again == headers_b


# ---------------------------------------------------------------------------
# AH-30 — Backward-compatibility regression suite
# ---------------------------------------------------------------------------


# Curated legacy GA query patterns (AH-PRD-03 §7 AC #3, §8 Regression).
#
# Provenance: pulled from GA_AGENT_INSTRUCTION §"Tool Usage" examples
# (google_analytics_agent_v4.py:143-174) and the pre-existing
# ``_NUMERICAL_QUERIES`` block in the AH-27 section above.
#
# Categories:
#   pure_metrics  — asks for a single-scalar metric with no trend/comparison
#   trend         — asks for change or direction over time
#   top_n         — asks for a ranking or "highest/top" result
#   comparison    — asks to compare two periods or dimensions
#
# How to extend this corpus:
#   1. Add a tuple ``(query_name, query_text, category)`` to the list below.
#   2. If the new query belongs to a *new* category, add the category name to
#      the docstring above and note its provenance.
#   3. Run ``pytest app/adk/agents/tests/test_google_analytics_specialist_e2e.py
#      ::TestBackwardCompatRegression -v --collect-only`` to confirm the new
#      case is collected.
#
# Next-add candidate: realtime queries (``run_realtime_report_mt``, line 159 of
# google_analytics_agent_v4.py) once a representative chat log surfaces.
_LEGACY_GA_QUERY_PATTERNS: list[tuple[str, str, str]] = [
    # (query_name, query_text, category)
    (
        "sessions_last_week",
        "What were my sessions last week?",
        "pure_metrics",
    ),
    (
        "traffic_trends_past_week",
        "Show me traffic trends for the past week.",
        "trend",
    ),
    (
        "highest_pageviews_this_month",
        "Which page had the highest pageviews this month?",
        "top_n",
    ),
    (
        "bounce_rate_month_over_month",
        "Compare bounce rate this month vs. last month.",
        "comparison",
    ),
]

# Baseline response shape locked as a regression contract.
#
# The GA specialist's terminal response event MUST have:
#   - role == "model"
#   - at least one text Part
#   - no function_call parts on the final event (the specialist has finished)
#   - no error_code set
#
# This shape is deliberately non-textual — asserting on the stub LLM's
# deterministic literal ("GA specialist response") would be tautological.
# The shape assertion catches the real failure modes: dispatch returns
# nothing, an error part slips in, or the wrong agent answers.
#
# If AH-PRD-04 ships structured artifact output from the GA specialist,
# extend this dict with ``"allows_artifact_parts": True`` and update the
# helper below.
BASELINE_RESPONSE_SHAPE: Final[dict[str, Any]] = {
    "role": "model",
    "min_text_parts": 1,
    "no_function_call_parts": True,
    "no_error_code": True,
}


def _assert_baseline_response_shape(
    events: list[Any],
    query_name: str,
) -> None:
    """Walk the event stream and assert the specialist's terminal event matches
    BASELINE_RESPONSE_SHAPE.

    Raises ``pytest.fail`` with a descriptive message naming the query and the
    offending event repr on any mismatch.
    """
    # Collect all events that look like the specialist's final text response:
    # role=="model", at least one text part, no function_call, not partial.
    terminal_events = [
        e
        for e in events
        if (
            e.content
            and e.content.role == "model"
            and e.content.parts
            and not any(p.function_call for p in e.content.parts)
            and not getattr(e, "partial", False)
        )
    ]

    if not terminal_events:
        pytest.fail(
            f"[{query_name}] No terminal model-role event found in stream. "
            f"All events: {[repr(e) for e in events]}"
        )

    # Take the last terminal event (the specialist's final response).
    final_event = terminal_events[-1]

    # Check role.
    actual_role = final_event.content.role
    if actual_role != BASELINE_RESPONSE_SHAPE["role"]:
        pytest.fail(
            f"[{query_name}] Expected role={BASELINE_RESPONSE_SHAPE['role']!r}, "
            f"got role={actual_role!r}. Event: {final_event!r}"
        )

    # Check at least min_text_parts text parts.
    text_parts = [p for p in final_event.content.parts if p.text]
    if len(text_parts) < BASELINE_RESPONSE_SHAPE["min_text_parts"]:
        pytest.fail(
            f"[{query_name}] Expected ≥{BASELINE_RESPONSE_SHAPE['min_text_parts']} "
            f"text part(s), got {len(text_parts)}. "
            f"Parts: {[repr(p) for p in final_event.content.parts]}"
        )

    # Check no function_call parts.
    if BASELINE_RESPONSE_SHAPE["no_function_call_parts"]:
        fc_parts = [p for p in final_event.content.parts if p.function_call]
        if fc_parts:
            pytest.fail(
                f"[{query_name}] Final specialist event must not have function_call "
                f"parts; found: {[repr(p) for p in fc_parts]}. Event: {final_event!r}"
            )

    # Check no error_code.
    if BASELINE_RESPONSE_SHAPE["no_error_code"]:
        error_code = getattr(final_event, "error_code", None)
        if error_code:
            pytest.fail(
                f"[{query_name}] Final specialist event has error_code="
                f"{error_code!r}. Event: {final_event!r}"
            )


class TestBackwardCompatRegression:
    """Backward-compatibility regression suite for existing GA query patterns.

    AH-30 — AC #3 (AH-PRD-03 §7): existing query patterns (from
    google_analytics_agent_v4.py and production chat logs) continue to route
    to the GA specialist via ADK-native ``transfer_to_agent`` under the
    post-AH-PRD-09 per-turn dispatch.

    **Architecture note (D-2):** the issue body still references
    ``delegate_to_specialist`` but AH-PRD-03 §1 "Architecture-refresh note
    (2026-06)" and AH-75 (Approach 1) supersede that. The deployed root
    carries ``tools=[]`` and dispatches via ADK's native ``transfer_to_agent``.
    Asserting on ``transfer_to_agent`` is correct; the old function tool was
    deleted (AH-66).

    Suite structure
    ---------------
    1. Stub layer (no ``@pytest.mark.llm``, no credentials):
       ``test_legacy_ga_query_routes_via_transfer_to_agent``
       Locks the per-turn dispatch *plumbing* — verifies that for every pattern
       in ``_LEGACY_GA_QUERY_PATTERNS`` the root emits exactly one
       ``transfer_to_agent(agent_name="google_analytics_specialist")`` event
       and the specialist responds with the expected response shape. Runs in
       every CI lane, no network.

    2. Live layer (``@pytest.mark.llm``, skipped without credentials):
       ``test_legacy_ga_query_routes_against_live_gemini``
       Drives the same corpus against ``gemini-2.0-flash`` with the seeded GA
       instruction + stub MCP tools; catches model-level routing regressions
       when credentials are present. Default CI skips cleanly.
    """

    # --- stub-layer tests ---------------------------------------------------

    @pytest.mark.parametrize(
        "query_name,query_text,category",
        _LEGACY_GA_QUERY_PATTERNS,
        ids=[p[0] for p in _LEGACY_GA_QUERY_PATTERNS],
    )
    @pytest.mark.asyncio
    async def test_legacy_ga_query_routes_via_transfer_to_agent(
        self,
        query_name: str,
        query_text: str,
        category: str,  # corpus metadata; not used in the test body
    ) -> None:
        """AC #3 (stub layer): each legacy query routes to the GA specialist
        via ``transfer_to_agent`` and the specialist returns the baseline shape.

        Assertions:
        (a) At least one event carries ``function_call.name == "transfer_to_agent"``
            with ``args["agent_name"] == "google_analytics_specialist"``.
        (b) The specialist's terminal event satisfies BASELINE_RESPONSE_SHAPE.
        (c) No event has ``error_code`` set.
        """
        specialist_agent = _make_ga_specialist_agent()
        ga_credentials: dict[str, Any] = {"access_token": "tok_stub", "tenant_id": "t1"}
        mcp_creds: dict[str, Any] = {"refresh_signature": "sig_stub"}

        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        root = LlmAgent(
            name="root_agent",
            model=_TransferToGaSpecialistStubLlm(),
            instruction="Route queries.",
            tools=[],
            before_agent_callback=[attacher.attach_specialists_before_agent_callback],
        )

        ga_config = _make_ga_config()
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=f"compat_stub_{query_name}",
            user_id="user_compat_stub",
            state={
                "account_id": "acct_compat_stub",
                "ga_credentials": ga_credentials,
                "mcp_creds_google_analytics_mcp": mcp_creds,
            },
        )
        runner = Runner(
            agent=root,
            app_name=f"compat_stub_{query_name}",
            session_service=session_service,
        )

        events: list[Any] = []
        with (
            patch.object(
                attacher,
                "list_account_agent_configs_cached",
                return_value=["google_analytics_specialist"],
            ),
            patch.object(attacher, "resolve_config", return_value=ga_config),
            patch.object(attacher, "resolve_agent", return_value=specialist_agent),
        ):
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[Part.from_text(text=query_text)],
                ),
            ):
                events.append(event)

        # (a) Root must emit transfer_to_agent(agent_name="google_analytics_specialist").
        transfer_events = [
            e
            for e in events
            if e.content
            and e.content.parts
            and any(
                p.function_call
                and p.function_call.name == "transfer_to_agent"
                and p.function_call.args.get("agent_name") == "google_analytics_specialist"
                for p in e.content.parts
            )
        ]
        assert transfer_events, (
            f"[{query_name}] No transfer_to_agent(agent_name='google_analytics_specialist') "
            f"event found. Events: {[repr(e) for e in events]}"
        )

        # (b) Specialist's terminal event satisfies BASELINE_RESPONSE_SHAPE.
        _assert_baseline_response_shape(events, query_name)

        # (c) No event has error_code set.
        error_events = [e for e in events if getattr(e, "error_code", None)]
        assert not error_events, (
            f"[{query_name}] Unexpected error events: {[repr(e) for e in error_events]}"
        )

    # --- live-layer tests ---------------------------------------------------

    @pytest.mark.parametrize(
        "query_name,query_text,category",
        _LEGACY_GA_QUERY_PATTERNS,
        ids=[p[0] for p in _LEGACY_GA_QUERY_PATTERNS],
    )
    @pytest.mark.llm
    @pytest.mark.skipif(
        not _GEMINI_CREDS_AVAILABLE,
        reason=(
            "Live Gemini credentials not configured — set GOOGLE_API_KEY "
            "or GOOGLE_CLOUD_PROJECT"
        ),
    )
    @pytest.mark.asyncio
    async def test_legacy_ga_query_routes_against_live_gemini(
        self,
        query_name: str,
        query_text: str,
        category: str,  # corpus metadata; not used in the test body
    ) -> None:
        """AC #3 (live layer): each legacy query produces a non-empty model
        response of the correct shape when driven against ``gemini-2.0-flash``
        with the GA specialist instruction and stub MCP tools.

        Skipped when live credentials are absent — default CI stays green.
        Single trial per query (D-7): one trial is sufficient for a regression
        smoke; AH-27 uses three only for code-execution output stability.
        """
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        agent = LlmAgent(
            name="google_analytics_specialist",
            model="gemini-2.0-flash",
            instruction=_GA_TEST_INSTRUCTION,
            tools=[FunctionTool(get_account_summaries_mt), FunctionTool(run_report_mt)],
            disallow_transfer_to_parent=True,
        )

        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name=f"compat_live_{query_name}",
            user_id="user_compat_live",
        )
        runner = Runner(
            agent=agent,
            app_name=f"compat_live_{query_name}",
            session_service=session_service,
        )

        events: list[Any] = []
        try:
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=query_text)],
                ),
            ):
                events.append(event)
        except ClientError as exc:
            if exc.code == 403:
                pytest.skip(
                    f"Gemini credentials lack required permission (HTTP 403). "
                    f"To run this test grant ``roles/aiplatform.user`` to the "
                    f"service account, or set GOOGLE_API_KEY for the Google AI "
                    f"API path. Original error: {exc!s:.160}"
                )
            if exc.code == 404:
                pytest.skip(
                    f"Model 'gemini-2.0-flash' is not available in this Vertex "
                    f"project/region (HTTP 404). Run where it is enabled "
                    f"or update the pinned model. Original error: {exc!s:.160}"
                )
            raise

        # At least one model-role event with content (non-empty response).
        model_events = [
            e
            for e in events
            if e.content and e.content.role == "model" and e.content.parts
        ]
        assert model_events, (
            f"[{query_name}] No model-role events returned from live Gemini run. "
            f"All events: {[repr(e) for e in events]}"
        )

        # Response shape matches the baseline contract.
        _assert_baseline_response_shape(events, query_name)

        # No event has error_code set (mirrors the stub-layer assertion (c)).
        error_events = [e for e in events if getattr(e, "error_code", None)]
        assert not error_events, (
            f"[{query_name}] Unexpected error events in live run: "
            f"{[repr(e) for e in error_events]}"
        )


# AH-31: Review-loop integration — config-driven via default_acceptance_criteria
# ---------------------------------------------------------------------------
# AC #4 (AH-PRD-03 §7): when agent_configs/google_analytics_specialist
# .default_acceptance_criteria is set, specialist_runtime.resolve_agent wraps
# the resolved specialist in build_review_pipeline() (specialist + reviewer as
# a LoopAgent).  When unset/empty, resolve_agent returns a single-pass LlmAgent.
# ---------------------------------------------------------------------------


def test_resolve_agent_wraps_ga_specialist_in_review_loopagent() -> None:
    """AC #4 (AH-31 positive): resolve_agent builds a LoopAgent when
    default_acceptance_criteria is set on the GA specialist config.

    Uses the actual GA_SPECIALIST_ACCEPTANCE_CRITERIA from the production seed
    (AH-25) and lets build_review_pipeline run unpatched, so the reviewer
    child's instruction and model can be inspected directly.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from google.adk.agents import LlmAgent, LoopAgent

    from app.adk.agents.agent_factory import specialist_runtime as sr
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.agents.utils.review_pipeline import DEFAULT_REVIEWER_MODEL

    # Config mirroring the production GA seed (AH-25).
    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="gemini-2.0-flash",
        description=(
            "Google Analytics 4 specialist. Use for any query about website or app"
            " traffic: sessions, users, pageviews, bounce rate, engagement, traffic"
            " sources, conversion events, real-time data, or custom GA4 reports."
            " Performs accurate numerical analysis (percentages, trends, averages)"
            " using Gemini code execution."
        ),
        mcp_servers=["google_analytics_mcp"],
        code_execution_enabled=True,
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model=None,  # → DEFAULT_REVIEWER_MODEL (gemini-2.5-pro)
        ken_e_sub_agent=True,
    )

    def _real_specialist_from_config(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
        """Return a real LlmAgent so build_review_pipeline (unpatched) can wrap it."""
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            description=_config.description,
        )

    with ExitStack() as stack:
        # resolve_config is patched to return the GA config (drives resolve_agent).
        stack.enter_context(
            _patch.object(sr, "resolve_config", return_value=ga_config)
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=McpToolsetPool(),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=_FakeFirestoreDb({}),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
                side_effect=lambda server_id, _doc, **_kw: MagicMock(
                    name=f"toolset_{server_id}"
                ),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_real_specialist_from_config,
            )
        )
        # Prevent _resolve_reviewer_model from hitting Firestore for system_settings.
        stack.enter_context(
            _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value=None,
            )
        )
        # build_review_pipeline runs UNPATCHED so the returned LoopAgent is real.
        result = sr.resolve_agent("google_analytics_specialist", account_id=None)

    # --- Shape: LoopAgent with doc_id name -----------------------------------
    assert isinstance(result, LoopAgent), (
        f"resolve_agent must return a LoopAgent when default_acceptance_criteria "
        f"is set; got {type(result).__name__}"
    )
    # _build_specialist renames the LoopAgent to the doc_id (line ~715).
    assert result.name == "google_analytics_specialist"
    assert len(result.sub_agents) == 2
    worker_agent, reviewer_agent = result.sub_agents
    # build_review_pipeline only adds LlmAgents as sub_agents.
    assert isinstance(worker_agent, LlmAgent)
    assert isinstance(reviewer_agent, LlmAgent)

    # --- Worker -----------------------------------------------------------
    assert worker_agent.name == "google_analytics_specialist_worker"

    # --- Reviewer ---------------------------------------------------------
    # output_key_prefix = f"{name}_review" = "google_analytics_specialist_review"
    # reviewer name = f"{output_key_prefix}_reviewer"
    expected_reviewer_name = "google_analytics_specialist_review_reviewer"
    assert reviewer_agent.name == expected_reviewer_name, (
        f"Expected reviewer name {expected_reviewer_name!r}; got {reviewer_agent.name!r}"
    )
    assert reviewer_agent.model == DEFAULT_REVIEWER_MODEL, (
        f"reviewer_model=None must fall back to DEFAULT_REVIEWER_MODEL "
        f"({DEFAULT_REVIEWER_MODEL!r}); got {reviewer_agent.model!r}"
    )
    assert reviewer_agent.include_contents == "none", (
        f"Reviewer must use include_contents='none'; got {reviewer_agent.include_contents!r}"
    )
    reviewer_tool_names = [
        getattr(t, "name", None) or getattr(t, "__name__", None)
        for t in reviewer_agent.tools or []
    ]
    assert "exit_loop" in reviewer_tool_names, (
        f"Reviewer must have an exit_loop tool; tools found: {reviewer_tool_names}"
    )

    # --- GA-criteria phrases in reviewer instruction ----------------------
    # Proves AC #4's three concerns (data accuracy / completeness /
    # calculation correctness) are surfaced verbatim to the reviewer so it
    # can evaluate the draft against them.
    assert isinstance(reviewer_agent.instruction, str)
    reviewer_instruction: str = reviewer_agent.instruction
    # AH-149: "code execution" was removed from GA_SPECIALIST_ACCEPTANCE_CRITERIA
    # when the parent GA specialist stopped executing code directly (code
    # execution now lives in the numerical_analyst leaf).  The reviewer
    # instruction is built from the criteria string verbatim, so "code execution"
    # is intentionally absent.  The remaining phrases ARE in the criteria.
    for phrase in (
        "property identifier",
        "absolute date range",
        "formula",
        "metric name",
        "decimal",
    ):
        assert phrase in reviewer_instruction, (
            f"Reviewer instruction is missing GA-criteria phrase {phrase!r}. "
            f"Instruction excerpt: {reviewer_instruction[:400]!r}"
        )


def test_resolve_agent_returns_single_pass_llmagent_when_criteria_empty() -> None:
    """AC #4 (AH-31 negative): resolve_agent returns a plain LlmAgent when
    default_acceptance_criteria is None, empty, or whitespace-only —
    build_review_pipeline is never called for any of these variants.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from google.adk.agents import LlmAgent, LoopAgent

    from app.adk.agents.agent_factory import specialist_runtime as sr
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )

    base_config = MergedAgentConfig(
        instruction="You are a Google Analytics specialist.",
        model="gemini-2.0-flash",
        description="GA specialist",
        mcp_servers=[],  # no MCP servers — tests the criteria logic in isolation
        ken_e_sub_agent=True,
    )

    def _real_specialist_from_config(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
        )

    for criteria in (None, "", "   "):
        config_variant = base_config.model_copy(
            update={"default_acceptance_criteria": criteria}
        )
        # Clear the agent cache between iterations so each variant builds fresh.
        sr._specialists_cache.clear()

        with ExitStack() as stack:
            stack.enter_context(
                _patch.object(sr, "resolve_config", return_value=config_variant)
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_real_specialist_from_config,
                )
            )
            mock_build_pipeline = stack.enter_context(
                _patch("app.adk.agents.utils.review_pipeline.build_review_pipeline")
            )
            result = sr.resolve_agent("google_analytics_specialist", account_id=None)

        assert not isinstance(result, LoopAgent), (
            f"criteria={criteria!r}: resolve_agent must return a plain LlmAgent "
            f"(not LoopAgent) when default_acceptance_criteria is falsy; "
            f"got {type(result).__name__}"
        )
        assert result.name == "google_analytics_specialist", (
            f"criteria={criteria!r}: returned agent name must match the doc_id; "
            f"got {result.name!r}"
        )
        mock_build_pipeline.assert_not_called()


@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_ga_review_loop_approves_well_formed_numerical_response() -> None:
    """Behavioral integration (AH-31): the review LoopAgent built by resolve_agent
    approves a well-formed numerical response within max_iterations.

    Uses real Gemini models (specialist + reviewer) with stub GA tool functions
    so the test is deterministic and does not require a live GA MCP connection.
    Mirrors the AH-27 stub-tool pattern from get_account_summaries_mt /
    run_report_mt defined at the top of this file.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from google.adk.agents import LoopAgent
    from google.adk.code_executors import BuiltInCodeExecutor
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.errors import ClientError

    from app.adk.agents.agent_factory import specialist_runtime as sr
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.agents.utils.review_pipeline import extract_pipeline_result

    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="gemini-2.0-flash",
        description="GA specialist",
        mcp_servers=[],  # tools injected via build_agent side_effect below
        code_execution_enabled=True,
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model=None,
        ken_e_sub_agent=True,
    )

    def _specialist_with_stub_tools(
        _config: Any, *, name: str, **_kw: Any
    ) -> LlmAgent:
        """Real LlmAgent with stub GA tools and Gemini code execution."""
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            code_executor=BuiltInCodeExecutor(),
            tools=[
                FunctionTool(get_account_summaries_mt),
                FunctionTool(run_report_mt),
            ],
            disallow_transfer_to_parent=True,
        )

    with ExitStack() as stack:
        stack.enter_context(
            _patch.object(sr, "resolve_config", return_value=ga_config)
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=McpToolsetPool(),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=_FakeFirestoreDb({}),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_specialist_with_stub_tools,
            )
        )
        # Prevent _resolve_reviewer_model from hitting Firestore for system_settings.
        stack.enter_context(
            _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value=None,
            )
        )
        loop_agent = sr.resolve_agent("google_analytics_specialist", account_id=None)

    assert isinstance(loop_agent, LoopAgent), (
        f"resolve_agent must return a LoopAgent; got {type(loop_agent).__name__}"
    )

    output_prefix = "google_analytics_specialist_review"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="ga_review_loop_behavioral_test",
        user_id="test_user_behavioral",
    )
    runner = Runner(
        agent=loop_agent,
        app_name="ga_review_loop_behavioral_test",
        session_service=session_service,
    )

    try:
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[
                    Part.from_text(
                        text=(
                            "Property 123456789: sessions were 4823 last week and"
                            " 5391 this week. What is the percentage change"
                            " week-over-week?"
                        )
                    )
                ],
            ),
        ):
            pass
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"Gemini credentials lack required permission (HTTP 403). "
                f"Grant roles/aiplatform.user or set GOOGLE_API_KEY. "
                f"Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"Model not available in this project/region (HTTP 404). "
                f"Original error: {exc!s:.160}"
            )
        raise

    final_session = await session_service.get_session(
        app_name="ga_review_loop_behavioral_test",
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}
    pipeline_result = extract_pipeline_result(state, output_prefix)

    # --- Approval: reviewer called exit_loop (feedback key empty) -----------
    assert pipeline_result["approved"], (
        "Review loop must approve the response within max_iterations. "
        f"Last reviewer feedback: {pipeline_result.get('warning', '')!r}"
    )

    # --- Content: draft references the query data --------------------------
    draft = pipeline_result["result"]
    for expected in ("123456789", "4823", "5391"):
        assert expected in draft, (
            f"Approved draft must reference {expected!r}. "
            f"Draft excerpt: {draft[:400]!r}"
        )
    assert any(marker in draft for marker in ("%", "percentage", "percent")), (
        f"Approved draft must include a percentage result. "
        f"Draft excerpt: {draft[:400]!r}"
    )


# ---------------------------------------------------------------------------
# AH-33: Review iteration — flawed-draft → reviewer rejects → corrected → approved
#
# Architecture note: the issue body references ``delegate_to_specialist``, which
# was deleted in AH-66 and replaced by ADK-native ``transfer_to_agent`` (AH-75 /
# AH-PRD-03 §1 architecture-refresh note).  This test drives the resolved
# LoopAgent directly via ``Runner(agent=loop_agent, ...)`` — the same pattern
# AH-31's behavioral test established.  Routing coverage (transfer_to_agent
# path) is already provided by AH-30 / AH-29.
#
# Response sequence queued into _GA_ITER_QUEUE:
#
#   worker iter 1:    "Sessions grew 11.78% week-over-week."
#                     (FLAWED — formula missing; violates the production
#                     acceptance criterion "numerical aggregates are accompanied
#                     by the formula used to compute them")
#
#   reviewer iter 1:  "Criterion not met: the formula used to compute the
#                     percentage change is missing. Show the arithmetic."
#                     (plain text rejection — no exit_loop call →
#                     actions.escalate unset → LoopAgent continues)
#
#   worker iter 2:    "Sessions grew 11.78% week-over-week "
#                     "((5391-4823)/4823*100 = 11.78)."
#                     (CORRECTED — formula present; satisfies the criterion)
#
#   reviewer iter 2:  FunctionCall(exit_loop, {})
#                     (actions.escalate = True → LoopAgent exits; the
#                     _make_review_exit_loop wrapper clears the feedback key)
# ---------------------------------------------------------------------------

_FLAWED_DRAFT = "Sessions grew 11.78% week-over-week."
_CORRECTED_DRAFT = (
    "Sessions grew 11.78% week-over-week ((5391-4823)/4823*100 = 11.78)."
)
_REJECTION_FEEDBACK = (
    "Criterion not met: the formula used to compute the percentage change is "
    "missing. Show the arithmetic."
)


@pytest.mark.asyncio
async def test_ga_review_loop_iterates_then_approves() -> None:
    """AH-33 / PRD §7 AC #5: reviewer rejects a flawed draft; specialist
    iterates with a corrected draft (formula present) that satisfies the
    production acceptance criteria; reviewer approves on the subsequent pass.

    Uses ``_GaIterFakeLlm`` (fake-ga-iter-worker / fake-ga-iter-reviewer) so
    the test is fully deterministic with no live-model dependency.  Drives the
    production-shape LoopAgent (built by resolve_agent with the seeded
    GA_SPECIALIST_ACCEPTANCE_CRITERIA) through Runner + InMemorySessionService,
    then validates all five ACs from the AH-33 implementation plan.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from google.adk.agents import LoopAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory import specialist_runtime as sr
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.agents.utils.review_pipeline import (
        extract_iterations,
        extract_pipeline_result,
    )

    # --- Queue the reject-then-approve response sequence -------------------
    _GA_ITER_QUEUE.extend(
        [
            # worker iter 1: flawed draft (formula missing)
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=_FLAWED_DRAFT)],
                )
            ),
            # reviewer iter 1: text rejection (no exit_loop → loop continues)
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=_REJECTION_FEEDBACK)],
                )
            ),
            # worker iter 2: corrected draft (formula present)
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=_CORRECTED_DRAFT)],
                )
            ),
            # reviewer iter 2: exit_loop (approval)
            LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[
                        genai_types.Part(
                            function_call=genai_types.FunctionCall(
                                name="exit_loop", args={}
                            )
                        )
                    ],
                )
            ),
        ]
    )

    # --- Build the production-shape config with fake-LLM model names ------
    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="fake-ga-iter-worker",
        description="GA specialist (iteration test)",
        mcp_servers=[],  # tools injected via build_agent side_effect below
        code_execution_enabled=False,  # no real sandbox needed for this test
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model="fake-ga-iter-reviewer",
        ken_e_sub_agent=True,
    )

    def _specialist_from_config(
        _config: Any, *, name: str, **_kw: Any
    ) -> LlmAgent:
        """Build the specialist LlmAgent with the fake-LLM model name."""
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            disallow_transfer_to_parent=True,
        )

    # --- Build the LoopAgent through resolve_agent (mocked Firestore / MCP) -
    with ExitStack() as stack:
        stack.enter_context(
            _patch.object(sr, "resolve_config", return_value=ga_config)
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=McpToolsetPool(),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=_FakeFirestoreDb({}),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_specialist_from_config,
            )
        )
        # Prevent _resolve_reviewer_model from hitting Firestore for system_settings.
        stack.enter_context(
            _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value=None,
            )
        )
        loop_agent = sr.resolve_agent("google_analytics_specialist", account_id=None)

    assert isinstance(loop_agent, LoopAgent), (
        f"resolve_agent must return a LoopAgent when default_acceptance_criteria "
        f"is set; got {type(loop_agent).__name__}"
    )

    # Derive names directly from the LoopAgent's sub_agents so the test tracks
    # any future rename of the child naming convention in build_review_pipeline.
    output_prefix = "google_analytics_specialist_review"
    worker_name = loop_agent.sub_agents[0].name   # = get_worker_name(specialist)
    reviewer_name = loop_agent.sub_agents[1].name  # = get_reviewer_name(output_prefix)

    # --- Run the LoopAgent and collect events ------------------------------
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="ga_iteration_test",
        user_id="test_user_iteration",
    )
    runner = Runner(
        agent=loop_agent,
        app_name="ga_iteration_test",
        session_service=session_service,
    )

    events: list[Any] = []
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=genai_types.Content(
            role="user",
            parts=[
                Part.from_text(
                    text=(
                        "Property 123456789: sessions were 4823 last week and "
                        "5391 this week. What is the percentage change "
                        "week-over-week? Include the formula."
                    )
                )
            ],
        ),
    ):
        events.append(event)

    # Retrieve final session state
    final_session = await session_service.get_session(
        app_name="ga_iteration_test",
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}

    # --- AC1: real iteration occurred (two passes; first rejected) ---------
    iterations = extract_iterations(events, worker_name, reviewer_name, output_prefix)

    assert len(iterations) == 2, (
        f"Expected exactly 2 review iterations; got {len(iterations)}. "
        f"Events collected: {len(events)}. "
        f"Iteration records: {iterations}"
    )
    assert iterations[0].escalate is False, (
        f"Iteration 1 reviewer must NOT escalate (rejection); "
        f"got escalate={iterations[0].escalate!r}"
    )
    assert iterations[1].escalate is True, (
        f"Iteration 2 reviewer must escalate (approval via exit_loop); "
        f"got escalate={iterations[1].escalate!r}"
    )

    # --- AC2: drafts differ materially between iterations ------------------
    assert iterations[0].specialist_output != iterations[1].specialist_output, (
        "Specialist output must differ between iteration 1 (flawed) and "
        "iteration 2 (corrected)."
    )
    # Iter 1: formula absent (the flaw)
    assert "((5391-4823)/4823*100" not in iterations[0].specialist_output, (
        f"Iteration 1 draft must NOT contain the formula (the flaw to be "
        f"corrected). Draft: {iterations[0].specialist_output!r}"
    )
    # Iter 2: formula present (the correction)
    assert "((5391-4823)/4823*100" in iterations[1].specialist_output, (
        f"Iteration 2 draft must contain the formula (the correction). "
        f"Draft: {iterations[1].specialist_output!r}"
    )

    # --- AC3: rubber-stamping detector (reviewer wrote real feedback) ------
    assert iterations[0].reviewer_output, (
        "Iteration 1 reviewer output must be non-empty (rejection feedback). "
        "An empty reviewer output means the reviewer ran but produced no text, "
        "which may indicate rubber-stamping."
    )
    # On approval the exit_loop tool clears the feedback key to "".
    assert iterations[1].reviewer_output == "", (
        f"Iteration 2 reviewer output must be empty after exit_loop approval. "
        f"Got: {iterations[1].reviewer_output!r}"
    )

    # --- AC4: state deltas prove {prefix}_draft and {prefix}_feedback ------
    #     were written between iterations.
    draft_key = f"{output_prefix}_draft"
    feedback_key = f"{output_prefix}_feedback"

    # At least one event from the worker must carry a state_delta for the
    # draft key.
    worker_draft_writes = [
        e
        for e in events
        if (
            getattr(e, "author", None) == worker_name
            and getattr(getattr(e, "actions", None), "state_delta", None)
            and draft_key
            in (getattr(getattr(e, "actions", None), "state_delta", None) or {})
        )
    ]
    assert worker_draft_writes, (
        f"No worker event wrote to '{draft_key}' in state_delta. "
        f"Draft key must be updated by the worker on each iteration."
    )

    # At least one reviewer event between the iter-1 worker and iter-2 worker
    # must carry a state_delta for the feedback key (proving the rejection was
    # persisted so the worker could read it).
    reviewer_feedback_writes = [
        e
        for e in events
        if (
            getattr(e, "author", None) == reviewer_name
            and getattr(getattr(e, "actions", None), "state_delta", None)
            and feedback_key
            in (getattr(getattr(e, "actions", None), "state_delta", None) or {})
        )
    ]
    assert reviewer_feedback_writes, (
        f"No reviewer event wrote to '{feedback_key}' in state_delta. "
        f"Feedback key must be updated by the reviewer between iterations."
    )

    # --- AC5: exit_loop called only on iteration 2 -------------------------
    pipeline_result = extract_pipeline_result(state, output_prefix)

    assert pipeline_result["approved"], (
        "Pipeline must be approved after iteration 2. "
        f"Last feedback: {pipeline_result.get('warning', '')!r}"
    )
    assert pipeline_result["result"] == _CORRECTED_DRAFT, (
        f"Approved result must be the iteration-2 corrected draft. "
        f"Got: {pipeline_result['result']!r}"
    )
    # Exactly one escalate=True across all events (the iter-2 reviewer).
    escalating_events = [
        e
        for e in events
        if bool(getattr(getattr(e, "actions", None), "escalate", False))
    ]
    assert len(escalating_events) == 1, (
        f"Exactly 1 event must have actions.escalate=True (the iter-2 reviewer). "
        f"Got {len(escalating_events)}: {escalating_events}"
    )
    assert getattr(escalating_events[0], "author", None) == reviewer_name, (
        f"The escalating event must be authored by the reviewer "
        f"('{reviewer_name}'). "
        f"Got: {getattr(escalating_events[0], 'author', None)!r}"
    )

    # Sanity: the queue must be fully drained (all 4 responses consumed).
    assert not _GA_ITER_QUEUE, (
        f"Response queue must be empty after the test; "
        f"{len(_GA_ITER_QUEUE)} response(s) were not consumed. "
        f"This likely means fewer iterations ran than expected."
    )


# ---------------------------------------------------------------------------
# AH-34 — E2E happy path: "Show me traffic trends for the past week"
# ---------------------------------------------------------------------------
#
# This test proves the full Release-1 runtime chain:
#   (1) attach_specialists_before_agent_callback attaches GA specialist to root
#   (2) Live root Gemini emits transfer_to_agent(agent_name="google_analytics_specialist")
#   (3) specialist_runtime.resolve_agent returns a LoopAgent (review pipeline)
#   (4) GA McpToolset is stubbed via FunctionTool wrappers (no live MCP server)
#   (5) Stub MCP tools provide GA4 row data (sessions this week vs. prior week)
#   (6) numerical_analyst AgentTool computes the trend (code execution)
#   (7) Reviewer approves the draft via exit_loop
#   (8) extract_pipeline_result returns approved=True with a non-empty draft
#
# Distinction from AH-31: AH-31 drives the LoopAgent directly (no root agent,
# no transfer_to_agent dispatch). AH-34 drives the full root→transfer→loop chain
# exactly once per trial, proving the wiring end-to-end (AC #8).
#
# MCP layer: stubbed via FunctionTool wrappers around the module-level
# get_account_summaries_mt / run_report_mt (realistic GA4 row shapes).
# LLM layer: live Gemini for root (transfer selection), specialist (draft),
# reviewer (approval), and transitively numerical_analyst (code execution).
#
# Parametrized over 5 trials — makes flakiness visible as clean trial-level
# failures in CI rather than sporadic single-test failures (AH-PRD-03 §8).


@pytest.mark.parametrize("trial", [1, 2, 3, 4, 5])
@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_ga_specialist_e2e_traffic_trends_happy_path(trial: int) -> None:
    """AC #8 (AH-PRD-03 §7, AH-34): the full chain
    attach_specialists_before_agent_callback → root transfer_to_agent →
    resolve_agent (LoopAgent) → McpToolsetPool checkout → stub MCP data →
    numerical_analyst code execution → reviewer approval → approved draft
    produces a non-empty text result describing the weekly trend.

    Trial parametrisation (5x): surfaces per-trial flakiness in CI rather
    than a sporadic single-test failure. Tune GA_SPECIALIST_INSTRUCTION or
    GA_SPECIALIST_ACCEPTANCE_CRITERIA (via AH-25 seed) if the reviewer
    regularly rejects on the first pass for repeatable reasons.

    MCP layer is stubbed; every LLM call is real.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from google.adk.agents import Agent, LoopAgent
    from google.adk.code_executors import BuiltInCodeExecutor
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.adk.tools.agent_tool import AgentTool
    from google.genai.errors import ClientError

    from app.adk.agents.agent_factory import specialist_runtime as sr
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.agents.utils.review_pipeline import extract_pipeline_result

    # -----------------------------------------------------------------------
    # Build the split-shape GA specialist (AH-149): parent GA LlmAgent +
    # numerical_analyst AgentTool leaf with BuiltInCodeExecutor.
    # -----------------------------------------------------------------------

    numerical_analyst_agent = Agent(
        name="numerical_analyst",
        model="gemini-2.5-flash",
        code_executor=BuiltInCodeExecutor(),
        instruction=_NUMERICAL_ANALYST_TEST_INSTRUCTION,
    )

    # AH-34 fix: a week-over-week stub (date range + current/previous period) so
    # a "traffic trends" query yields a real trend, plus a parent instruction
    # that mirrors GA_SPECIALIST_ACCEPTANCE_CRITERIA (property id, absolute date
    # range, per-metric values, a verbatim formula per aggregate). The shared
    # _GA_TEST_INSTRUCTION / run_report_mt under-specified the reply relative to
    # the reviewer rubric, so approval within max_iterations was luck-dependent
    # (the live reviewer rejected drafts missing the property id / date range /
    # formula, exhausting the loop). Defined locally so the AH-27 / AH-31 tests
    # that reuse the shared stubs are untouched.
    def run_report_mt(
        property_id: str,
        date_ranges: list,
        metrics: list | None = None,
        dimensions: list | None = None,
    ) -> str:
        """Run a GA4 report: week-over-week sessions for the queried property."""
        return (
            '{"propertyId": "123456789", '
            '"dateRange": {"startDate": "2024-05-27", "endDate": "2024-06-02"}, '
            '"comparisonDateRange": '
            '{"startDate": "2024-05-20", "endDate": "2024-05-26"}, '
            '"rows": [{"metricName": "sessions", '
            '"currentPeriodValue": "5391", "previousPeriodValue": "4823"}]}'
        )

    rubric_aligned_instruction = (
        "You are a Google Analytics 4 specialist.\n"
        "When the user asks about website traffic or trends, ALWAYS fetch the "
        "data with the GA tools — never ask the user for the property ID or the "
        "date range; read both from the tool output.\n"
        "1. Call get_account_summaries_mt to find the property, then "
        "run_report_mt to fetch the metrics.\n"
        "2. Delegate ALL arithmetic to the numerical_analyst tool: pass only the "
        "specific numbers and a description of the calculation, then include the "
        "figure AND the formula it returns verbatim.\n"
        "3. For a traffic-trends query, compute the week-over-week percentage "
        "change between the current and previous period via numerical_analyst.\n"
        "Your final reply MUST always include:\n"
        "- the GA property identifier from the tool output;\n"
        "- the absolute date range (start and end dates) from the tool output;\n"
        "- every metric reported by name, rounded to at most 2 decimal places;\n"
        "- the verbatim formula for each aggregate (including the week-over-week "
        "percentage change) as returned by numerical_analyst.\n"
    )

    def _specialist_with_stub_tools_and_analyst(
        _config: MergedAgentConfig, *, name: str, **_kw: Any
    ) -> LlmAgent:
        """Real LlmAgent with stub GA MCP tools + numerical_analyst AgentTool.

        No code_executor on the parent — validates the AH-149 split shape
        avoids the Gemini 2.5+ HTTP 400 (code_executor + function tools on
        one agent).
        """
        return LlmAgent(
            name=name,
            model="gemini-2.5-flash",
            instruction=rubric_aligned_instruction,
            tools=[
                AgentTool(agent=numerical_analyst_agent),
                FunctionTool(get_account_summaries_mt),
                FunctionTool(run_report_mt),
            ],
            disallow_transfer_to_parent=True,
        )

    # -----------------------------------------------------------------------
    # Config mirroring the production GA seed (AH-25).
    # mcp_servers=[] — tools are injected via build_agent side_effect.
    # -----------------------------------------------------------------------

    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="gemini-2.5-flash",
        description=(
            "Google Analytics 4 specialist. Use for any query about website or app"
            " traffic: sessions, users, pageviews, bounce rate, engagement, traffic"
            " sources, conversion events, real-time data, or custom GA4 reports."
            " Performs accurate numerical analysis (percentages, trends, averages)"
            " using Gemini code execution."
        ),
        mcp_servers=[],  # tools injected via build_agent side_effect below
        code_execution_enabled=True,
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model=None,
        ken_e_sub_agent=True,
    )

    # -----------------------------------------------------------------------
    # Patch layer: resolve_config → ga_config, build_agent → split specialist,
    # mcp.build_toolset_for_doc → no-op MagicMock (defensive: the GA config has
    # mcp_servers=[], so the real pool checkout is never reached — MCP tools are
    # injected as FunctionTool wrappers on the specialist instead), and
    # system_settings → None.
    # -----------------------------------------------------------------------

    with ExitStack() as stack:
        stack.enter_context(
            _patch.object(sr, "resolve_config", return_value=ga_config)
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                new=McpToolsetPool(),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=_FakeFirestoreDb({}),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
                return_value=MagicMock(name="toolset_unused"),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=[],
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_specialist_with_stub_tools_and_analyst,
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value=None,
            )
        )

        # Resolve the GA specialist into a review LoopAgent.
        loop_agent = sr.resolve_agent(
            "google_analytics_specialist",
            account_id="acct_e2e_happy_path",
        )

    assert isinstance(loop_agent, LoopAgent), (
        f"[trial {trial}] resolve_agent must return a LoopAgent when "
        f"default_acceptance_criteria is set; got {type(loop_agent).__name__}"
    )

    # -----------------------------------------------------------------------
    # Build root agent and wire the before_agent_callback.
    # Patch attacher to return the already-resolved loop_agent.
    # -----------------------------------------------------------------------

    root = LlmAgent(
        name="root_agent",
        model="gemini-2.5-flash",
        instruction=(
            "You are a marketing analytics assistant. "
            "When the user asks about Google Analytics or website traffic, "
            "delegate to the google_analytics_specialist."
        ),
        tools=[],
        before_agent_callback=[attacher.attach_specialists_before_agent_callback],
    )

    account_id = "acct_e2e_happy_path"
    ga_credentials: dict[str, Any] = {"access_token": "tok_e2e", "tenant_id": "tenant_e2e"}
    mcp_creds: dict[str, Any] = {"refresh_signature": "sig_e2e"}

    app_name = f"e2e_happy_path_trial_{trial}"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=app_name,
        user_id=f"user_e2e_{trial}",
        state={
            "account_id": account_id,
            "ga_credentials": ga_credentials,
            "mcp_creds_google_analytics_mcp": mcp_creds,
        },
    )
    runner = Runner(
        agent=root,
        app_name=app_name,
        session_service=session_service,
    )

    output_prefix = "google_analytics_specialist_review"
    all_events: list[Any] = []

    with (
        patch.object(
            attacher,
            "list_account_agent_configs_cached",
            return_value=["google_analytics_specialist"],
        ),
        patch.object(attacher, "resolve_config", return_value=ga_config),
        patch.object(attacher, "resolve_agent", return_value=loop_agent),
    ):
        try:
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[Part.from_text(text="Show me traffic trends for the past week.")],
                ),
            ):
                all_events.append(event)
        except ClientError as exc:
            if exc.code == 403:
                pytest.skip(
                    f"[trial {trial}] Gemini credentials lack required permission "
                    f"(HTTP 403). Grant roles/aiplatform.user or set GOOGLE_API_KEY. "
                    f"Original error: {exc!s:.160}"
                )
            if exc.code == 404:
                pytest.skip(
                    f"[trial {trial}] Model not available in this project/region "
                    f"(HTTP 404). Original error: {exc!s:.160}"
                )
            raise

    # -----------------------------------------------------------------------
    # Assertion 1: root must emit transfer_to_agent(google_analytics_specialist)
    # -----------------------------------------------------------------------

    transfer_events = [
        e
        for e in all_events
        if e.content
        and e.content.parts
        and any(
            p.function_call
            and p.function_call.name == "transfer_to_agent"
            and p.function_call.args.get("agent_name") == "google_analytics_specialist"
            for p in e.content.parts
        )
    ]
    assert transfer_events, (
        f"[trial {trial}] No transfer_to_agent(agent_name='google_analytics_specialist') "
        f"event found in root stream. "
        f"Total events: {len(all_events)}. "
        f"Event authors: {[getattr(e, 'author', None) for e in all_events]}"
    )

    # -----------------------------------------------------------------------
    # Assertion 2: no error_code on any event
    # -----------------------------------------------------------------------

    error_events = [e for e in all_events if getattr(e, "error_code", None)]
    assert not error_events, (
        f"[trial {trial}] Unexpected error events: "
        f"{[repr(e) for e in error_events]}"
    )

    # -----------------------------------------------------------------------
    # Assertion 3: at least one model-role terminal event
    # -----------------------------------------------------------------------

    model_role_events = [
        e
        for e in all_events
        if e.content and e.content.role == "model" and e.content.parts
        and not getattr(e, "partial", False)
    ]
    assert model_role_events, (
        f"[trial {trial}] No model-role terminal events found. "
        f"Total events: {len(all_events)}"
    )

    # -----------------------------------------------------------------------
    # Assertion 4: attachment — root.sub_agents contains google_analytics_specialist
    # -----------------------------------------------------------------------

    sub_agent_names = [a.name for a in (root.sub_agents or [])]
    assert "google_analytics_specialist" in sub_agent_names, (
        f"[trial {trial}] root.sub_agents does not contain 'google_analytics_specialist' "
        f"after the run. Found: {sub_agent_names!r}"
    )

    # -----------------------------------------------------------------------
    # Assertion 5: review-loop approval via extract_pipeline_result
    # -----------------------------------------------------------------------

    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}

    draft_key = f"{output_prefix}_draft"
    assert draft_key in state, (
        f"[trial {trial}] Session state missing key {draft_key!r} — "
        f"the review loop never produced a draft. "
        f"State keys: {list(state.keys())}"
    )

    pipeline_result = extract_pipeline_result(state, output_prefix)
    assert pipeline_result["approved"], (
        f"[trial {trial}] Review loop must approve the response within max_iterations. "
        f"Last reviewer feedback: {pipeline_result.get('warning', '')!r}"
    )

    # -----------------------------------------------------------------------
    # Assertion 6: content quality — non-empty draft with formula/trend token
    # -----------------------------------------------------------------------

    draft = pipeline_result["result"]
    assert isinstance(draft, str) and len(draft) >= 60, (
        f"[trial {trial}] Approved draft must be a non-empty string of at least "
        f"60 characters; got {len(draft)} chars. Draft: {draft!r}"
    )

    assert any(
        marker in draft
        for marker in ("%", "percent", "average", "trend", "Trend", "Percent")
    ), (
        f"[trial {trial}] Approved draft must include a trend/percentage descriptor. "
        f"Draft excerpt: {draft[:400]!r}"
    )
