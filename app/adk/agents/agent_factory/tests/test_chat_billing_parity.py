"""Phase 2 parity test — Chat + Billing (AH-61, merge blocker for AH-PRD-09 Phase 2).

MERGE BLOCKER STATUS (AH-110 / AH-PRD-13 §7 AC #3):
  This file is the canonical merge gate for the ADK 2.0 Foundation migration
  (AH-PRD-13). It must remain green on google-adk==2.0.0 with agent.google_search
  unassigned (GitHub #3984 leaves AgentTool.run_async dropping inner events on 2.0;
  the AgentTool cutover is AH-PRD-15 and gates prod, not this merge).

  Evidence trail:
  - AH-104 (Phase-0 de-risking spike) locally verified total_billable=1430 for both
    Mode A and Mode B under the .venv-adk2 environment with the AlwaysTrueSubAgentList
    shim. See docs/spike-ah104-deploy-sandbox-weave.md §3.2.1.
  - AH-105 (PR #843) committed the AlwaysTrueSubAgentList shim in hierarchy.py and
    sub_agent_attacher.py and verified 24/24 pass on the pinned 2.0.0 stack.
  - AH-110 (this issue) codifies the merge-gate status, adds the AgentTool exclusion
    regression guard (TestNoAgentToolInGate), and ports the AH-99 probe assertions
    into the CI test suite.

AH-117 MERGE BLOCKER (AH-PRD-15 §7 AC #1):
  `TestAgentGoogleSearchTaskModeParity` (bottom of this file) is the integration-level
  merge gate for the agent.google_search task-mode migration (AH-114/115/116). On ADK
  2.0, a turn invoking agent.google_search via the migrated task-mode path must yield
  the search sub-agent's usage_metadata to the outer stream so extract_billable_tokens
  + SessionTurnAccumulator count its gemini-2.5-flash tokens — on both the specialist
  (AH-115) and root/coordinator (AH-116) assignment paths. Shipping 2.0 to prod without
  this gate is a billing regression on every web-search turn.

AH-129 MERGE BLOCKER (AH-PRD-14 §7 AC-6):
  `TestMultiTaskChatBillingParity` (bottom of this file) is the integration-level
  merge gate for the multi-task / fan-out accumulator work shipped in AH-123
  (`SessionTurnAccumulator`) and AH-128 (`_build_turn_delta`). It feeds a single
  synthetic event list (4 task specialists, one fan-out group) to BOTH codepaths
  and asserts aggregate equality vs the sum of single-specialist baselines. A
  future change that drifts the two aggregators apart fails here even if both
  unit suites pass individually. Re-confirm against a live 2.0 runner event stream
  once AH-PRD-13 + AH-PRD-05 land (see TestMultiTaskChatBillingParity docstring).

CANONICAL FIXTURE (from api/tests/unit/chat/test_token_accounting_parity.py):
  prompt_token_count        = 1250
  candidates_token_count    =  380
  thoughts_token_count      = None  (non-reasoning model)
  cached_content_token_count=  200
  → input=1050, output=380, reasoning=0, total_billable=1430

CONTRACT UNDER TEST (AH-PRD-09 §7 ACs #9 and #10):
  ADK event propagation from a specialist invocation to the outer Runner must
  be preserved so that:
  - Chat's SessionTurnAccumulator.add_event() sees the same per-event usage_metadata
  - Billing's extract_billable_tokens(event).total_billable sums to the same total
  ...regardless of whether the specialist is reached via a deploy-time sub_agents
  declaration (Mode A) or a per-turn runtime attachment (Mode B / AH-75).

AH-75: Mode B is satisfied by ADK's native transfer_to_agent + sub_agents populated
by attach_specialists_before_agent_callback. Both modes route through ADK's built-in
transfer mechanism, so specialist LLM-response events (carrying usage_metadata)
appear in the outer Runner's event stream natively.

Prior history (PR #697): the parity assertions were marked xfail(strict=True)
because the AH-PRD-09 Phase 2 delegate_to_specialist function-tool dispatch could
not forward inner-Runner events. AH-75 (this PR) removes the function tool;
xfail markers are dropped and the test must pass.
"""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from types import SimpleNamespace
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
from app.adk.agents.agent_factory.sub_agent_attacher import AlwaysTrueSubAgentList
from app.adk.agents.chat_callbacks import _build_turn_delta
from shared.token_accounting import extract_billable_tokens

# Resolve api/src so kene_api is importable without installing the api package.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "api", "src"),
)

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
    ) -> AsyncIterator[LlmResponse]:
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
    ) -> AsyncIterator[LlmResponse]:
        func_call = FunctionCall(
            name="transfer_to_agent", args={"agent_name": "canonical_stub_agent"}
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


class _TransferToSpecialistStubLlm(BaseLlm):
    """Mode B root (AH-75): emits transfer_to_agent(agent_name='test_specialist').

    Under the AH-75 dispatch model, the root LLM picks a specialist from the
    Available Specialists block and uses ADK's native transfer_to_agent — there
    is no delegate_to_specialist function tool to call.
    """

    model: str = "transfer_to_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["transfer_to_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        func_call = FunctionCall(
            name="transfer_to_agent", args={"agent_name": "test_specialist"}
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deterministic_specialist(name: str = "canonical_stub_agent") -> LlmAgent:
    """Return an LlmAgent backed by _CanonicalStubLlm.

    Sets ``disallow_transfer_to_parent=True`` to mirror production: AH-75's
    ``_build_specialist`` sets this flag on every resolved specialist so
    ADK's ``_find_agent_to_run`` returns to the root for each new user turn
    instead of staying with the last-invoked specialist. See the
    ``TestMultiTurnRouting`` regression guard below for why this matters.
    """
    return LlmAgent(
        name=name,
        model=_CanonicalStubLlm(),
        instruction="Test specialist",
        disallow_transfer_to_parent=True,
    )


def _increments_equal(a: Any, b: Any) -> bool:
    """Compare two firestore.Increment objects by their .value attribute."""
    return getattr(a, "value", a) == getattr(b, "value", b)


class _MultiTaskEvent:
    """Shared synthetic event satisfying both accumulator (attribute) and
    _build_turn_delta (method) API surfaces simultaneously.

    Anchored to the canonical trace fixture task_ids (AH-125) and the CH-10
    canonical token shape (prompt=1250, candidates=380, cached=200,
    thoughts=None → input=1050, output=380, total_billable=1430).

    The accumulator uses attribute duck-typing (event.type, event.is_final_text);
    _build_turn_delta uses method calls (event.get_function_calls(),
    event.is_final_response()). A single class satisfying both surfaces guarantees
    the two paths see semantically identical input so divergence cannot be
    attributed to fixture skew (AH-PRD-14 §2).
    """

    def __init__(
        self,
        *,
        task_id: str,
        event_id: str,
        author: str = "google_analytics_specialist",
        invocation_id: str = "inv_multi_task",
        node_info: object = None,
        isolation_scope: str | None = None,
    ) -> None:
        self.usage_metadata = SimpleNamespace(
            prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
            candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
            thoughts_token_count=_CANONICAL_THOUGHTS_TOKEN_COUNT,
            cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
        )
        self.author = author
        self.id = event_id
        self.invocation_id = invocation_id
        self.type = None  # not a tool_call or compaction_summary
        self.is_final_text = False
        self.text = ""
        self.content = None
        # ADK 2.0 fields — only set for fan-out events (tolerance guard)
        if node_info is not None:
            self.node_info = node_info
        if isolation_scope is not None:
            self.isolation_scope = isolation_scope
        # Suppress unused parameter warning — task_id is carried for traceability
        self._task_id = task_id

    def get_function_calls(self) -> list[Any]:
        """Real ADK Event API used by _build_turn_delta."""
        return []

    def is_final_response(self) -> bool:
        """Real ADK Event API used by _build_turn_delta."""
        return False


def _build_canonical_multi_task_events() -> list[_MultiTaskEvent]:
    """Return 4 synthetic events anchored to supervisor_orchestration_trace.json.

    Matches the trace fixture's task_ids, assignees, and node_path values
    (AH-125) so swapping to a recorded stream when AH-PRD-13 lands is 1:1.

    Layout:
      task_001_analyze_traffic  — sequential task_delegation (no fan-out)
      task_002_performance_data — fan-out branch A (specialist_a@1)
      task_003_competitor_data  — fan-out branch B (specialist_b@1)
      task_004_synthesis        — synthesis task_delegation

    Each event carries the CH-10 canonical token shape (input=1050, output=380,
    total_billable=1430). All events share invocation_id="inv_multi_task".
    """
    node_path_a = SimpleNamespace(path="specialist_a@1", output_for=[])
    node_path_b = SimpleNamespace(path="specialist_b@1", output_for=[])

    return [
        _MultiTaskEvent(
            task_id="task_001_analyze_traffic",
            event_id="evt_task_001",
        ),
        _MultiTaskEvent(
            task_id="task_002_performance_data",
            event_id="evt_task_002",
            node_info=node_path_a,
            isolation_scope="fc_branch_a",
        ),
        _MultiTaskEvent(
            task_id="task_003_competitor_data",
            event_id="evt_task_003",
            node_info=node_path_b,
            isolation_scope="fc_branch_b",
        ),
        _MultiTaskEvent(
            task_id="task_004_synthesis",
            event_id="evt_task_004",
        ),
    ]


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
    """Run Mode B (AH-75: per-turn runtime attachment via transfer_to_agent)
    outer Runner and return all events.

    Wires the production attach_specialists_before_agent_callback onto the
    root, then mocks the three resolver functions it calls so the test
    specialist is the sole "visible" entry. The callback adds the specialist
    to root.sub_agents during the before-agent step; the stub LLM emits
    transfer_to_agent(agent_name='test_specialist'); ADK's built-in transfer
    mechanism resolves to the attached specialist and runs it. The
    specialist's LLM-response event (with usage_metadata) appears in the
    outer Runner's stream natively — no inner-Runner needed.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory import sub_agent_attacher as attacher

    test_config = MergedAgentConfig(
        instruction="Test specialist",
        model="canonical_stub",
        description="Test specialist for parity tests",
    )

    root = LlmAgent(
        name="root_agent",
        model=_TransferToSpecialistStubLlm(),
        instruction="Route queries.",
        tools=[],
        before_agent_callback=[attacher.attach_specialists_before_agent_callback],
    )
    # ADK 2.0: DynamicNodeScheduler gating shim (AH-105 / AH-PRD-13).
    # Runner._run_node_async checks bool(root.sub_agents) on the pre-clone root;
    # AlwaysTrueSubAgentList ensures the scheduler activates even when empty.
    root.sub_agents = AlwaysTrueSubAgentList()

    session_service = InMemorySessionService()
    # Pre-seed account_id in session state so the attacher callback finds it
    # and resolves the test specialist for this account.
    session = await session_service.create_session(
        app_name="parity_test_b",
        user_id="test_user",
        state={"account_id": "test_account"},
    )
    runner = Runner(
        agent=root,
        app_name="parity_test_b",
        session_service=session_service,
    )
    events: list[Any] = []
    # Patch the three resolver entry points the attacher calls, scoped to the
    # sub_agent_attacher module since that's where they're imported.
    with (
        patch.object(
            attacher,
            "list_account_agent_configs_cached",
            return_value=["test_specialist"],
        ),
        patch.object(attacher, "resolve_config", return_value=test_config),
        patch.object(attacher, "resolve_agent", return_value=specialist),
    ):
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
    """Each test starts with a clean agent cache, config cache, block cache, and applied-state slot."""
    from app.adk.agents.agent_factory import sub_agent_attacher as saa
    from app.adk.agents.utils.config_cache import clear_config_cache

    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._reset_applied_state_for_tests()
    clear_config_cache()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    saa._reset_applied_state_for_tests()
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
        billable_events = [
            e for e in events if getattr(e, "usage_metadata", None) is not None
        ]
        assert len(billable_events) >= 1, (
            "Mode A must include at least one event with usage_metadata (specialist events "
            "must be present in outer stream for token accounting to work)"
        )

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

        # CH-58: attach_specialists_before_agent_callback now writes
        # _available_specialists to session state, which ADK surfaces as a
        # pure state-delta event (content=None, usage_metadata=None) in Mode B.
        # That event carries no LLM output — it is a callback side-effect.
        # Compare only "content-bearing" events (content is not None OR
        # usage_metadata is not None) to preserve the original intent of this
        # assertion: Mode A must surface specialist LLM output in the outer
        # stream.
        def _content_bearing(event: Any) -> bool:
            return (
                getattr(event, "content", None) is not None
                or getattr(event, "usage_metadata", None) is not None
            )

        meaningful_a = [e for e in events_a if _content_bearing(e)]
        meaningful_b = [e for e in events_b if _content_bearing(e)]
        assert len(meaningful_a) >= len(meaningful_b), (
            f"Mode A ({len(meaningful_a)} content-bearing events) must yield >= "
            f"Mode B ({len(meaningful_b)} content-bearing events). "
            "Both modes route through ADK's native transfer_to_agent (AH-75); "
            "specialist LLM events appear in both streams. "
            "Pure state-delta events (e.g. from CH-58's _available_specialists write) "
            "are excluded from this count."
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

        AH-75: now passes because both modes route through ADK's native
        transfer_to_agent — specialist events appear in the outer Runner's
        stream regardless of whether sub_agents was set at deploy (Mode A) or
        attached per-turn by attach_specialists_before_agent_callback (Mode B).
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

        AH-75: now passes via native transfer_to_agent event propagation (see
        TestChatParity for the full propagation rationale).
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
            "Mode B billable=0 means specialist events never reached the outer stream. "
            "AH-105 shim likely reverted: check AlwaysTrueSubAgentList assignment in "
            "hierarchy.py and the in-place sub_agents[:] = keep update in _reconcile "
            "(app/adk/agents/agent_factory/sub_agent_attacher.py)."
        )


# ---------------------------------------------------------------------------
# TestMultiTurnRouting — AH-75 regression guard.
#
# Reviewer concern (PR #703): after transfer_to_agent + specialist response,
# does turn N+1 from the user return to root, or stay with the specialist?
#
# ADK answer (invocation_context.py): yes, control returns to root. ADK's
# ``_get_subagent_to_resume`` calls ``_get_events(current_invocation=True)``
# which filters events by ``event.invocation_id == ctx.invocation_id``. Each
# new user message starts a NEW invocation with a new invocation_id, so the
# lookup only sees the current turn's events — not previous turns' transfer
# history. Root handles every new user message fresh.
#
# This test pins that behavior. If a future ADK version widens the resume
# scope to cross-invocation history, this test surfaces it as a hard failure
# before users encounter "stuck on specialist" symptoms.
# ---------------------------------------------------------------------------


class TestMultiTurnRouting:
    @pytest.mark.asyncio
    async def test_second_user_turn_returns_to_root(self) -> None:
        """After turn 1's transfer_to_agent + specialist response, a new user
        message on turn 2 must invoke the root agent (not the specialist)."""
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from app.adk.agents.agent_factory import sub_agent_attacher as attacher

        specialist = _make_deterministic_specialist("test_specialist")
        test_config = MergedAgentConfig(
            instruction="Test specialist",
            model="canonical_stub",
            description="Test specialist for multi-turn routing test",
        )

        root = LlmAgent(
            name="root_agent",
            model=_TransferToSpecialistStubLlm(),
            instruction="Route queries.",
            tools=[],
            before_agent_callback=[attacher.attach_specialists_before_agent_callback],
        )
        # ADK 2.0: DynamicNodeScheduler gating shim (AH-105 / AH-PRD-13).
        root.sub_agents = AlwaysTrueSubAgentList()

        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="multi_turn_routing",
            user_id="test_user",
            state={"account_id": "test_account"},
        )
        runner = Runner(
            agent=root,
            app_name="multi_turn_routing",
            session_service=session_service,
        )

        async def _run_turn(message: str) -> list[Any]:
            captured: list[Any] = []
            async for event in runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=message)],
                ),
            ):
                captured.append(event)
            return captured

        with (
            patch.object(
                attacher,
                "list_account_agent_configs_cached",
                return_value=["test_specialist"],
            ),
            patch.object(attacher, "resolve_config", return_value=test_config),
            patch.object(attacher, "resolve_agent", return_value=specialist),
        ):
            turn1 = await _run_turn("hello")
            turn2 = await _run_turn("follow-up question")

        # Sanity: turn 1 reached the specialist (transfer worked).
        turn1_authors = [getattr(e, "author", None) for e in turn1]
        assert "root_agent" in turn1_authors, (
            f"Turn 1 must include a root_agent event; got authors {turn1_authors}"
        )
        assert "test_specialist" in turn1_authors, (
            f"Turn 1 must reach the specialist via transfer_to_agent; "
            f"got authors {turn1_authors}"
        )

        # Core assertion: turn 2 must hit root_agent. If ADK's resume logic
        # ever drifted to cross-invocation event scoping, turn 2 would skip
        # the root and go straight to the specialist — this assertion catches
        # that regression before it ships.
        turn2_authors = [getattr(e, "author", None) for e in turn2]
        assert "root_agent" in turn2_authors, (
            f"Turn 2 must invoke root_agent (ADK's per-invocation event "
            f"scoping should return control to root for every new user "
            f"message). Got authors {turn2_authors} — if this fails, "
            f"investigate ADK's _get_subagent_to_resume + "
            f"_get_events(current_invocation=True) behavior."
        )


# ---------------------------------------------------------------------------
# TestNoAgentToolInGate — AH-110 / AH-PRD-13 §3 + §9 regression guard.
#
# PRD §3 + §9 require Foundation to be validated with agent.google_search
# unassigned. GitHub #3984 (still OPEN) means AgentTool.run_async drops inner
# events on ADK 2.0 — any AgentTool in the parity-gate topology would make
# billing/trace assertions unreliable. The AgentTool cutover is AH-PRD-15 and
# gates prod cutover, not this merge.
#
# This test walks the Mode A and Mode B test topologies and asserts that no
# google.adk.tools.agent_tool.AgentTool instance is present. It fails as soon
# as any AgentTool is introduced, catching AH-PRD-15-deferred surfaces before
# they silently corrupt the merge gate.
# ---------------------------------------------------------------------------


def _collect_tools_recursive(agent: Any) -> list[Any]:
    """Walk an agent tree and collect all tool objects (recursive).

    Covers ``.tools`` on each node and recurses into ``.sub_agents``.  Used by
    both ``TestNoAgentToolInGate`` and ``TestNoAgentToolInSupervisorPath`` so
    any future ADK tool-attachment surface only needs to be added once.
    """
    tools: list[Any] = list(getattr(agent, "tools", None) or [])
    for sub in getattr(agent, "sub_agents", None) or []:
        tools.extend(_collect_tools_recursive(sub))
    return tools


class TestNoAgentToolInGate:
    """Regression guard: no AgentTool must be present in the parity-gate topology.

    AH-114 (registry migration): the agent_tool_registry no longer produces
    AgentTool instances — it stores task-mode LlmAgent instances instead. This
    guard now enforces post-migration state across the entire chat tree: any
    future change that re-introduces AgentTool (e.g. a premature AH-PRD-15
    consumer migration that lands AgentTool on a specialist) will be caught here.

    If this test fails after a future refactor, stop and read AH-PRD-15 before
    proceeding — the AgentTool cutover is a separate gated migration (prod
    cutover gate), not a parity-gate concern.
    """

    def _collect_tools(self, agent: LlmAgent) -> list[Any]:
        """Delegate to module-level _collect_tools_recursive."""
        return _collect_tools_recursive(agent)

    def _build_mode_a_topology(self) -> LlmAgent:
        """Mode A: root with sub_agents=[specialist] as in _capture_mode_a_events."""
        specialist = _make_deterministic_specialist()
        return LlmAgent(
            name="root_agent",
            model=_RouterStubLlm(),
            instruction="Route queries.",
            sub_agents=[specialist],
        )

    def _build_mode_b_topology(self) -> LlmAgent:
        """Mode B: root with AlwaysTrueSubAgentList as in _capture_mode_b_events."""
        from app.adk.agents.agent_factory import sub_agent_attacher as attacher

        specialist = _make_deterministic_specialist("test_specialist")
        root = LlmAgent(
            name="root_agent",
            model=_TransferToSpecialistStubLlm(),
            instruction="Route queries.",
            tools=[],
            before_agent_callback=[attacher.attach_specialists_before_agent_callback],
        )
        root.sub_agents = AlwaysTrueSubAgentList()
        # Manually attach the specialist so the topology walk can inspect it.
        root.sub_agents.append(specialist)
        return root

    def test_no_agent_tool_in_mode_a_topology(self) -> None:
        """Mode A topology must contain no AgentTool instance.

        Protects the merge gate from AH-PRD-15-deferred agent.google_search
        surface (#3984 still OPEN: AgentTool.run_async drops inner events on 2.0).
        """
        try:
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable — skip guard (ADK version check)")

        root = self._build_mode_a_topology()
        all_tools = self._collect_tools(root)
        agent_tools = [t for t in all_tools if isinstance(t, AgentTool)]
        assert agent_tools == [], (
            "Mode A parity-gate topology must not contain any AgentTool instance. "
            f"Found: {[getattr(t, 'name', repr(t)) for t in agent_tools]}. "
            "AgentTool cutover is AH-PRD-15 (prod-cutover gate) — do not introduce "
            "AgentTool into the parity-gate topology before that migration lands."
        )

    def test_no_agent_tool_in_mode_b_topology(self) -> None:
        """Mode B topology must contain no AgentTool instance.

        Same rationale as test_no_agent_tool_in_mode_a_topology.
        """
        try:
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable — skip guard (ADK version check)")

        root = self._build_mode_b_topology()
        all_tools = self._collect_tools(root)
        agent_tools = [t for t in all_tools if isinstance(t, AgentTool)]
        assert agent_tools == [], (
            "Mode B parity-gate topology must not contain any AgentTool instance. "
            f"Found: {[getattr(t, 'name', repr(t)) for t in agent_tools]}. "
            "AgentTool cutover is AH-PRD-15 (prod-cutover gate) — do not introduce "
            "AgentTool into the parity-gate topology before that migration lands."
        )

    def test_no_google_search_tool_by_name(self) -> None:
        """No tool named 'google_search' must be present in either topology.

        Explicitly guards the AH-PRD-15-deferred agent.google_search surface
        regardless of AgentTool class name changes in future ADK versions.
        """
        root_a = self._build_mode_a_topology()
        root_b = self._build_mode_b_topology()

        for mode, root in (("A", root_a), ("B", root_b)):
            all_tools = self._collect_tools(root)
            named_search = [
                t for t in all_tools
                if getattr(t, "name", None) == "google_search"
            ]
            assert named_search == [], (
                f"Mode {mode} parity-gate topology must not contain a tool named "
                f"'google_search'. Found: {named_search}. "
                "agent.google_search is deferred to AH-PRD-15 (prod-cutover gate)."
            )


# ---------------------------------------------------------------------------
# TestNoAgentToolInSupervisorPath — AH-146 / AH-PRD-05 §7 AC-9 regression guard.
#
# The supervisor dispatch path (coordinator(mode='chat') + mode='task' specialist)
# is the second dispatch surface alongside transfer_to_agent. Any AgentTool
# introduced here — other than the two sanctioned isolation leaves (google_search,
# numerical_analyst) — silently re-introduces the AH-75 / GitHub #3984 billing drop:
# AgentTool.run_async discards inner sub-agent events so the leaf's
# gemini-2.5-flash tokens go uncounted. This guard walks the coordinator +
# specialist tree and enforces the allow-list of exactly two sanctioned leaves,
# each of which must carry the capture_agent_tool_usage billing callback.
#
# Three test methods mirror TestNoAgentToolInGate's pattern:
#   test_no_unsanctioned_agent_tool_in_supervisor_topology — allow-list check
#   test_sanctioned_agent_tool_carries_billing_callback — callback contract check
#   test_unsanctioned_agent_tool_in_supervisor_topology_is_flagged — regression
#     triangulation (red→green→red): proves the guard fires on an unsanctioned leaf
#
# Skip-on-import for AgentTool (D6): matches TestNoAgentToolInGate:792 — keeps
# the guard green on the strategy-tree ADK 1.34.x CI matrix.
# ---------------------------------------------------------------------------


class TestNoAgentToolInSupervisorPath:
    """AH-146 / AH-PRD-05 §7 AC-9 (re-planned, AH-121) regression guard.

    Verifies that a supervisor-orchestration topology (coordinator mode='chat' +
    task-mode specialist) contains no *isolation-leaf* AgentTool except the two
    sanctioned ones (google_search, numerical_analyst), each of which must carry
    the capture_agent_tool_usage billing callback to recover the usage_metadata
    that AgentTool.run_async drops (#3984).

    Important ADK 2.0 distinction — two AgentTool subclasses, two behaviours:
      ``AgentTool`` (exact class)  — isolation-leaf pattern; uses a private inner
          Runner and drops inner events (#3984). Only the two sanctioned leaves
          may use this; each must carry the billing callback. <<< WHAT WE CHECK >>>
      ``_TaskAgentTool`` (subclass) — ADK 2.0's task delegation mechanism; injected
          automatically into coordinator.tools for every mode='task' sub_agent.
          Dispatches via ctx.run_node, properly propagates events, needs NO billing
          callback. <<< EXCLUDED FROM THE CHECK (type(t) is AgentTool, not isinstance) >>>

    Delegates the tree walk to module-level ``_collect_tools_recursive`` —
    shared with TestNoAgentToolInGate: if ADK 2.0 introduces a new
    tool-attachment surface not covered by (.tools + .sub_agents), both guards
    fail together at the single update point, making the gap visible.
    """

    _SANCTIONED_NAMES: frozenset[str] = frozenset({"google_search", "numerical_analyst"})

    def _collect_isolation_leaf_agent_tools(
        self, agent: LlmAgent, AgentTool: type
    ) -> list[Any]:
        """Return only exact-AgentTool instances (not _TaskAgentTool subclasses).

        Uses ``type(t) is AgentTool`` (exact class check) to exclude
        ``_TaskAgentTool`` (ADK 2.0 task delegation), which IS a subclass of
        AgentTool but uses ctx.run_node and does not have the #3984 billing gap.
        Only the isolation-leaf AgentTool pattern (own inner Runner) is checked.

        Delegates the recursive tree walk to the module-level
        ``_collect_tools_recursive`` — shared with TestNoAgentToolInGate to
        form a single point of update for new ADK tool-attachment surfaces.
        """
        return [t for t in _collect_tools_recursive(agent) if type(t) is AgentTool]

    def _build_supervisor_topology(self, specialist_tools: list[Any]) -> LlmAgent:
        """Build coordinator(mode='chat') + task-mode specialist with given tools.

        Constructs the topology with stub LlmAgent instances directly (D2) — the
        supervisor builder (AH-141+) is mid-implementation; decoupling the
        verification from the builder keeps this test at est=1 and shipable in
        parallel. The invariant under test is a topology property, not a builder
        internal.
        """
        from app.adk.tools.registry.agent_tool_registry import task_mode_supported

        if not task_mode_supported():
            pytest.skip("mode= field unavailable (ADK 1.34.x strategy deploy tree)")

        specialist = LlmAgent(
            name="ga_specialist",
            model=_CanonicalStubLlm(),
            mode="task",
            instruction="GA specialist",
            tools=specialist_tools,
            disallow_transfer_to_parent=True,
        )
        return LlmAgent(
            name="coordinator",
            model=_RouterStubLlm(),
            mode="chat",
            instruction="Coordinator",
            sub_agents=[specialist],
        )

    def test_no_unsanctioned_agent_tool_in_supervisor_topology(self) -> None:
        """Supervisor topology with the two sanctioned leaves must pass the allow-list.

        Walks the coordinator → specialist tree collecting exact-AgentTool
        instances (excludes _TaskAgentTool subclasses — those are ADK 2.0 task
        delegation and correctly propagate events). Every isolation-leaf AgentTool
        found must be named in _SANCTIONED_NAMES.
        """
        try:
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable — skip guard (ADK version check)")

        from app.adk.tools.agent_tools.google_search import (
            create_google_search_agent_tool,
        )

        coordinator = self._build_supervisor_topology([create_google_search_agent_tool()])

        isolation_tools = self._collect_isolation_leaf_agent_tools(coordinator, AgentTool)
        unsanctioned = [
            t for t in isolation_tools if t.name not in self._SANCTIONED_NAMES
        ]

        assert unsanctioned == [], (
            f"Supervisor topology contains unsanctioned isolation-leaf AgentTool(s): "
            f"{[getattr(t, 'name', repr(t)) for t in unsanctioned]}. "
            f"Only {sorted(self._SANCTIONED_NAMES)!r} are sanctioned isolation leaves. "
            "Any other AgentTool silently re-introduces the AH-75/#3984 billing drop "
            "(AgentTool.run_async discards inner events → uncounted tokens). "
            "(_TaskAgentTool subclass is excluded from this check — it dispatches via "
            "ctx.run_node and properly propagates events.) "
            "See AH-PRD-15 §7.7 and AH-PRD-05 §7 AC-9 (re-planned, AH-121)."
        )

    def test_sanctioned_agent_tool_carries_billing_callback(self) -> None:
        """Every isolation-leaf AgentTool in the supervisor topology carries
        capture_agent_tool_usage.

        The billing callback on the leaf is the ONLY mechanism that recovers the
        usage_metadata that AgentTool.run_async drops (#3984). An AgentTool without
        it silently under-bills the leaf's tokens — the exact AH-75 defect.

        _TaskAgentTool instances are excluded (dispatches via ctx.run_node,
        properly propagates events, needs no billing callback).
        """
        try:
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable — skip guard (ADK version check)")

        from app.adk.agents.agent_tool_billing import capture_agent_tool_usage
        from app.adk.tools.agent_tools.google_search import (
            create_google_search_agent_tool,
        )

        coordinator = self._build_supervisor_topology([create_google_search_agent_tool()])

        isolation_tools = self._collect_isolation_leaf_agent_tools(coordinator, AgentTool)

        for tool in isolation_tools:
            leaf = tool.agent
            cb = getattr(leaf, "after_model_callback", None)
            has_callback = cb is capture_agent_tool_usage or (
                isinstance(cb, (list, tuple)) and capture_agent_tool_usage in cb
            )
            assert has_callback, (
                f"Isolation-leaf AgentTool {tool.name!r} in the supervisor topology is "
                "missing capture_agent_tool_usage on its wrapped leaf. "
                "AgentTool.run_async drops the leaf's usage_metadata (#3984) — "
                "without this callback those tokens go unbilled (AH-75 defect). "
                "See app/adk/agents/agent_tool_billing.py and AH-PRD-15 §5."
            )

    def test_unsanctioned_agent_tool_in_supervisor_topology_is_flagged(self) -> None:
        """Regression triangulation: an unsanctioned isolation-leaf AgentTool is detected.

        Extends the topology with a fake AgentTool (exact class, not a subclass)
        not in _SANCTIONED_NAMES and confirms the allow-list guard fires. Mirrors
        TestNoAgentToolInGate's red→green→red pattern so a future refactor cannot
        accidentally hollow out the guard to a vacuous pass.

        Verifies that the exact-type check (type(t) is AgentTool) still catches a
        directly-constructed unsanctioned AgentTool while skipping _TaskAgentTool.
        """
        try:
            from google.adk.tools.agent_tool import AgentTool
        except ImportError:
            pytest.skip("AgentTool not importable — skip guard (ADK version check)")

        from app.adk.tools.registry.agent_tool_registry import task_mode_supported

        if not task_mode_supported():
            pytest.skip("mode= field unavailable (ADK 1.34.x strategy deploy tree)")

        # Build a fake AgentTool (exact class) not in the sanctioned set — simulates
        # a future mistaken addition of a built-in-tool leaf outside the two
        # sanctioned ones. Uses LlmAgent as the leaf (any agent name works here;
        # AgentTool.name mirrors agent.name).
        stub_leaf = LlmAgent(
            name="unsanctioned_leaf",
            model=_CanonicalStubLlm(),
            instruction="Unsanctioned stub leaf",
        )
        unsanctioned_tool = AgentTool(agent=stub_leaf)

        coordinator = self._build_supervisor_topology([unsanctioned_tool])

        isolation_tools = self._collect_isolation_leaf_agent_tools(coordinator, AgentTool)
        unsanctioned = [
            t for t in isolation_tools if t.name not in self._SANCTIONED_NAMES
        ]

        assert len(unsanctioned) >= 1, (
            "Regression triangulation FAILED: the topology built with an unsanctioned "
            "isolation-leaf AgentTool ('unsanctioned_leaf') was not detected by the "
            "allow-list check. Either _collect_isolation_leaf_agent_tools is not walking "
            "the tree correctly, or _SANCTIONED_NAMES was widened to include "
            "'unsanctioned_leaf'. If this is intentional, update the triangulation test "
            "to use a different unsanctioned name."
        )


# ---------------------------------------------------------------------------
# TestMultiTaskChatBillingParity — AH-129 / AH-PRD-14 §7 AC-6 MERGE BLOCKER.
#
# Integration-level gate: a single synthetic event list (4 task specialists,
# one fan-out group) is fed to BOTH SessionTurnAccumulator and _build_turn_delta.
# Both must produce aggregate token / tool-call / message counts equal to the
# sum of single-specialist baselines (4 x CH-10 canonical fixture), and the two
# codepaths must produce identical aggregate values — the divergence guard.
#
# AH-PRD-13 RE-CONFIRM GATE: re-run against a live 2.0 runner event stream once
# AH-PRD-13 + AH-PRD-05 land and the coordinator starts emitting the supervisor
# event shape. Swap _build_canonical_multi_task_events() for a recorded stream
# fixture at that point.
#
# All four tests are synchronous — the class consumes synthetic events directly
# without Runner.run_async involvement (mirrors api/tests/unit/chat/test_accumulator.py
# and app/adk/agents/tests/test_chat_callbacks.py patterns; no pytest.mark.asyncio).
# ---------------------------------------------------------------------------


class TestMultiTaskChatBillingParity:
    """AH-PRD-14 §7 AC-6 / AH-129 MERGE BLOCKER.

    Integration-level gate across SessionTurnAccumulator and _build_turn_delta
    for the supervisor-model multi-task / fan-out event stream.
    """

    def test_accumulator_aggregate_equals_sum_of_baselines(self) -> None:
        """AC-1: SessionTurnAccumulator sums 4 task specialists to 4x CH-10 baseline."""
        events = _build_canonical_multi_task_events()
        acc = SessionTurnAccumulator()
        for ev in events:
            acc.add_event(ev)
        delta = acc.build_delta()

        expected_input = 4 * _EXPECTED_INPUT
        expected_output = 4 * _EXPECTED_OUTPUT
        expected_context = expected_input + expected_output  # reasoning=0

        assert _increments_equal(delta["input_tokens_total"], expected_input), (
            f"accumulator input_tokens_total="
            f"{getattr(delta['input_tokens_total'], 'value', delta['input_tokens_total'])} "
            f"expected {expected_input} (4 x {_EXPECTED_INPUT})"
        )
        assert _increments_equal(delta["output_tokens_total"], expected_output), (
            f"accumulator output_tokens_total="
            f"{getattr(delta['output_tokens_total'], 'value', delta['output_tokens_total'])} "
            f"expected {expected_output} (4 x {_EXPECTED_OUTPUT})"
        )
        assert _increments_equal(delta["reasoning_tokens_total"], 0), (
            f"accumulator reasoning_tokens_total="
            f"{getattr(delta['reasoning_tokens_total'], 'value', delta['reasoning_tokens_total'])} "
            "expected 0 (non-reasoning model)"
        )
        assert _increments_equal(delta["message_count"], 4), (
            f"accumulator message_count="
            f"{getattr(delta['message_count'], 'value', delta['message_count'])} "
            "expected 4 (one LLM-response event per task specialist)"
        )
        assert _increments_equal(delta["current_context_tokens"], expected_context), (
            f"accumulator current_context_tokens="
            f"{getattr(delta['current_context_tokens'], 'value', delta['current_context_tokens'])} "
            f"expected {expected_context} (input + output, reasoning=0)"
        )

    def test_build_turn_delta_aggregate_equals_sum_of_baselines(self) -> None:
        """AC-2: _build_turn_delta sums 4 task specialists to 4x CH-10 baseline."""
        events = _build_canonical_multi_task_events()
        now = datetime.now(timezone.utc)
        turn_delta = _build_turn_delta(events, now)

        expected_input = 4 * _EXPECTED_INPUT
        expected_output = 4 * _EXPECTED_OUTPUT
        expected_context = expected_input + expected_output

        assert turn_delta.input_tokens_increment == expected_input, (
            f"_build_turn_delta input_tokens_increment={turn_delta.input_tokens_increment} "
            f"expected {expected_input} (4 x {_EXPECTED_INPUT})"
        )
        assert turn_delta.output_tokens_increment == expected_output, (
            f"_build_turn_delta output_tokens_increment={turn_delta.output_tokens_increment} "
            f"expected {expected_output} (4 x {_EXPECTED_OUTPUT})"
        )
        assert turn_delta.reasoning_tokens_increment == 0, (
            f"_build_turn_delta reasoning_tokens_increment={turn_delta.reasoning_tokens_increment} "
            "expected 0 (non-reasoning model)"
        )
        assert turn_delta.message_count == 4, (
            f"_build_turn_delta message_count={turn_delta.message_count} "
            "expected 4 (one LLM-response event per task specialist)"
        )
        assert turn_delta.current_context_tokens == expected_context, (
            f"_build_turn_delta current_context_tokens={turn_delta.current_context_tokens} "
            f"expected {expected_context} (input + output, reasoning=0)"
        )

    def test_billing_total_billable_equals_sum_of_baselines(self) -> None:
        """AC-3: billing total across 4 task specialists equals 4x CH-10 baseline."""
        events = _build_canonical_multi_task_events()
        total = sum(extract_billable_tokens(ev).total_billable for ev in events)

        assert total == 4 * _EXPECTED_TOTAL_BILLABLE, (
            f"billing total_billable={total} "
            f"expected {4 * _EXPECTED_TOTAL_BILLABLE} (4 x {_EXPECTED_TOTAL_BILLABLE})"
        )

    def test_codepaths_produce_identical_aggregate(self) -> None:
        """AC-4: accumulator and _build_turn_delta produce identical aggregate
        counts from the same event list — the divergence guard.

        Feeds ONE shared event list to both codepaths and asserts pairwise
        equality across all counter fields. A future change that drifts the two
        aggregators apart fails here even if both unit suites pass individually.
        """
        events = _build_canonical_multi_task_events()
        now = datetime.now(timezone.utc)

        acc = SessionTurnAccumulator()
        for ev in events:
            acc.add_event(ev)
        acc_delta = acc.build_delta()
        # Same list — accumulator and _build_turn_delta each maintain their own
        # seen_event_ids so re-feeding the same list to both is correct and intentional.
        turn_delta = _build_turn_delta(events, now)

        assert _increments_equal(
            acc_delta["input_tokens_total"], turn_delta.input_tokens_increment
        ), (
            f"input divergence: accumulator="
            f"{getattr(acc_delta['input_tokens_total'], 'value', acc_delta['input_tokens_total'])} "
            f"_build_turn_delta={turn_delta.input_tokens_increment}"
        )
        assert _increments_equal(
            acc_delta["output_tokens_total"], turn_delta.output_tokens_increment
        ), (
            f"output divergence: accumulator="
            f"{getattr(acc_delta['output_tokens_total'], 'value', acc_delta['output_tokens_total'])} "
            f"_build_turn_delta={turn_delta.output_tokens_increment}"
        )
        assert _increments_equal(
            acc_delta["reasoning_tokens_total"], turn_delta.reasoning_tokens_increment
        ), (
            f"reasoning divergence: accumulator="
            f"{getattr(acc_delta['reasoning_tokens_total'], 'value', acc_delta['reasoning_tokens_total'])} "
            f"_build_turn_delta={turn_delta.reasoning_tokens_increment}"
        )
        assert _increments_equal(
            acc_delta["tool_call_count"], turn_delta.tool_call_count
        ), (
            f"tool_call_count divergence: accumulator="
            f"{getattr(acc_delta['tool_call_count'], 'value', acc_delta['tool_call_count'])} "
            f"_build_turn_delta={turn_delta.tool_call_count}"
        )
        assert _increments_equal(
            acc_delta["message_count"], turn_delta.message_count
        ), (
            f"message_count divergence: accumulator="
            f"{getattr(acc_delta['message_count'], 'value', acc_delta['message_count'])} "
            f"_build_turn_delta={turn_delta.message_count}"
        )
        assert _increments_equal(
            acc_delta["current_context_tokens"], turn_delta.current_context_tokens
        ), (
            f"context_tokens divergence: accumulator="
            f"{getattr(acc_delta['current_context_tokens'], 'value', acc_delta['current_context_tokens'])} "
            f"_build_turn_delta={turn_delta.current_context_tokens}"
        )


# ---------------------------------------------------------------------------
# TestAgentGoogleSearchTaskModeParity — AH-117 / AH-PRD-15 §7 AC #1 MERGE BLOCKER.
#
# Integration-level gate: when a 2.0 turn invokes agent.google_search via the
# migrated task-mode path (AH-114/115/116), the search sub-agent's usage_metadata
# reaches the outer Runner stream and the production billing pipeline —
# extract_billable_tokens + SessionTurnAccumulator — counts its tokens correctly.
# Verified on both the specialist assignment path (AH-115) and the root/coordinator
# assignment path (AH-116). This is the billing half of the AH-PRD-15 cutover gate.
#
# The google_search sub-agent is registered through the real AH-114 registry API
# (register_agent_subagent) with a stub BaseLlm emitting the canonical CH-10 fixture
# (prompt=1250 / candidates=380 / cached=200 → total_billable=1430). Assertions run
# against the real extract_billable_tokens + SessionTurnAccumulator — no mocks at
# the accumulator/extractor boundary. The structural guard (assertion a) ensures the
# test does not pass vacuously if the task-mode dispatch fails silently.
# ---------------------------------------------------------------------------


class _GoogleSearchTaskModeStubLlm(BaseLlm):
    """Task-mode google_search sub-agent stub (AH-117 merge gate).

    Advertises model='gemini-2.5-flash' to match the production
    create_google_search_subagent() so reviewers can see the model identity in
    captured events. Emits the canonical CH-10 fixture usage_metadata on one call
    with turn_complete=True — the task-mode sub-agent runs once per task delegation.
    """

    model: str = "gemini-2.5-flash"

    @classmethod
    def supported_models(cls) -> list[str]:
        # Use a synthetic name distinct from the real "gemini-2.5-flash" to avoid
        # shadowing the production Gemini class in LLMRegistry if this stub were
        # ever inadvertently registered via LLMRegistry.register(). The model: str
        # field stays "gemini-2.5-flash" for human readability in captured events;
        # supported_models() is only consulted by LLMRegistry.resolve(), which is
        # bypassed when the stub is passed as a pre-instantiated object to LlmAgent().
        return ["test-stub-google-search-task-mode"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        usage = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
            candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
            cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
        )
        content = Content(
            role="model",
            parts=[Part.from_text(text="Google search results for your query.")],
        )
        yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)


class _SearchCallerStubLlm(BaseLlm):
    """Stateless stub for an agent (specialist or root) that calls agent.google_search.

    ADK 2.0 exposes task-mode sub-agents as ``_TaskAgentTool`` with the sub-agent's
    name as the tool name (``google_search``, not ``request_task_google_search``).

    Turn 1 (no function_response in contents): emits ``FunctionCall(name='google_search')``
    so ADK dispatches the task-mode google_search sub-agent via ``ctx.run_node``.
    Turn 2 (function_response present — sub-agent has completed): emits final text with
    canonical CH-10 tokens so the caller contributes its own usage_metadata alongside
    the sub-agent's.
    """

    model: str = "search_caller_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["search_caller_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        # Detect turn 2: a function_response part in the conversation means the
        # task-mode google_search sub-agent has already run and returned its result.
        has_function_response = any(
            getattr(part, "function_response", None) is not None
            for content in (getattr(llm_request, "contents", None) or [])
            for part in (getattr(content, "parts", None) or [])
        )
        if has_function_response:
            usage = genai_types.GenerateContentResponseUsageMetadata(
                prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
                candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
                cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
            )
            content = Content(
                role="model",
                parts=[Part.from_text(text="Search complete, here is the summary.")],
            )
            yield LlmResponse(content=content, usage_metadata=usage, turn_complete=True)
        else:
            # ADK 2.0: task-mode sub-agents are exposed as _TaskAgentTool with the
            # sub-agent's name as the tool name (not request_task_<name>).
            func_call = FunctionCall(
                name="google_search", args={"query": "test query"}
            )
            content = Content(role="model", parts=[Part(function_call=func_call)])
            yield LlmResponse(content=content, turn_complete=False)


class _RouterToGoogleSearchSpecialistStubLlm(BaseLlm):
    """Root LLM that routes to 'google_search_specialist' via transfer_to_agent."""

    model: str = "router_to_gs_specialist_stub"

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["router_to_gs_specialist_stub"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        func_call = FunctionCall(
            name="transfer_to_agent", args={"agent_name": "google_search_specialist"}
        )
        content = Content(role="model", parts=[Part(function_call=func_call)])
        yield LlmResponse(content=content, turn_complete=False)


def _make_google_search_task_mode_subagent() -> LlmAgent:
    """Build a fresh task-mode google_search sub-agent backed by the stub LLM.

    Returns a new parentless LlmAgent(mode='task') on every call — required by
    register_agent_subagent (factory contract): ADK 2.0 rejects reparenting a
    sub-agent, so each resolve must mint a fresh instance (AH-114 module docstring).
    """
    return LlmAgent(
        name="google_search",
        model=_GoogleSearchTaskModeStubLlm(),
        mode="task",
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information. Focus on official sources.",
    )


@pytest.fixture()
def register_task_mode_google_search() -> Any:
    """Register stub google_search task-mode sub-agent; restore production on teardown.

    Teardown calls clear_agent_tool_registry() and reloads ALL production
    agent-tool producer modules (google_search AND numerical_analyst) to
    re-execute their import-time register_agent_subagent side-effects, restoring
    the process-global registry to its production state for adjacent test suites
    in the same session. Reloading only google_search would leave
    numerical_analyst cleared — an order-dependent cross-test leak, since its
    import-time registration does not re-run after clear_agent_tool_registry().
    """
    import app.adk.tools.agent_tools.google_search as _gs_mod
    import app.adk.tools.agent_tools.numerical_analyst as _na_mod
    from app.adk.tools.registry.agent_tool_registry import (
        clear_agent_tool_registry,
        register_agent_subagent,
    )

    clear_agent_tool_registry()
    register_agent_subagent("google_search", _make_google_search_task_mode_subagent)
    yield
    clear_agent_tool_registry()
    # Restore BOTH producers' import-time registrations (not just google_search).
    importlib.reload(_gs_mod)
    importlib.reload(_na_mod)
    # If task_mode_supported() returns False (ADK 1.34.x), the reloads skip
    # registration and the registry stays empty — acceptable for that environment
    # since task-mode dispatch is gated by the same check in production code.


async def _capture_specialist_google_search_events(
    query: str = "search for marketing data",
) -> list[Any]:
    """Run specialist with agent.google_search in sub_agents; return outer Runner events.

    The specialist has google_search as a task-mode sub-agent (AH-115 path). ADK
    auto-injects a _TaskAgentTool for it at specialist construction time (model_post_init).
    When the specialist's LLM calls 'google_search', ADK dispatches it via ctx.run_node
    and its usage_metadata flows to the outer Runner stream (AH-99 probe-1 contract).

    Key: specialist is built with rerun_on_resume=True so ctx.run_node inside the
    DynamicNodeScheduler transfer path has _node_rerun_on_resume=True. This mirrors
    what build_node() sets when the specialist runs as the direct agent_to_run on
    subsequent turns in production.

    Root routes to the specialist via transfer_to_agent (standard single-specialist
    dispatch; same as Mode A / Mode B).
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.tools.registry.agent_tool_registry import get_agent_subagent

    # get_agent_subagent calls the registered factory (AH-114) to produce a fresh
    # parentless LlmAgent(mode='task'). Passing it at construction wires ADK's
    # model_post_init to auto-inject _TaskAgentTool(google_search) into specialist.tools
    # so the task-delegation FC is dispatched via ctx.run_node, not the legacy
    # handle_function_calls_async path.
    google_search_subagent = get_agent_subagent("google_search")
    assert google_search_subagent is not None, (
        "google_search task-mode sub-agent not registered — "
        "use register_task_mode_google_search fixture."
    )

    specialist = LlmAgent(
        name="google_search_specialist",
        model=_SearchCallerStubLlm(),
        instruction="Research agent that uses google_search for web research.",
        disallow_transfer_to_parent=True,
        # rerun_on_resume=True is required so that ctx.run_node inside the specialist
        # (when it dispatches the google_search task-mode sub-agent) sees
        # _node_rerun_on_resume=True in the DynamicNodeScheduler transfer path.
        # build_node() sets this when running the specialist as the direct agent_to_run
        # in subsequent turns; we set it here to enable the same within a single turn.
        rerun_on_resume=True,
        sub_agents=[google_search_subagent],
    )
    root = LlmAgent(
        name="root_agent",
        model=_RouterToGoogleSearchSpecialistStubLlm(),
        instruction="Route queries to specialists.",
        sub_agents=[specialist],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="gs_specialist_gate", user_id="test_user"
    )
    runner = Runner(
        agent=root,
        app_name="gs_specialist_gate",
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


async def _capture_root_google_search_events(
    query: str = "search for marketing data",
) -> list[Any]:
    """Run root with agent.google_search in sub_agents as coordinator; return events.

    The root has google_search as a task-mode sub-agent at construction time (AH-116
    path). ADK auto-injects _TaskAgentTool(google_search) in model_post_init. When the
    root's LLM calls 'google_search', run_llm_agent_as_node detects it as a task-delegation
    FC via _extract_task_delegation_fcs and dispatches it via ctx.run_node — the root
    already has rerun_on_resume=True from build_node() in the Runner, so the dispatch
    succeeds. The sub-agent's usage_metadata flows to the outer stream (AH-116).

    Note: We use construct-time attachment (sub_agents at construction) to ensure
    model_post_init creates the _TaskAgentTool entry in root.tools. Dynamic attachment
    via attach_root_tools_before_agent_callback is tested separately in
    test_root_tools_attacher.py; this capture function exercises the root-as-coordinator
    billing contract that AH-116 wires up.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.tools.registry.agent_tool_registry import get_agent_subagent

    google_search_subagent = get_agent_subagent("google_search")
    assert google_search_subagent is not None, (
        "google_search task-mode sub-agent not registered — "
        "use register_task_mode_google_search fixture."
    )

    # Root with google_search in sub_agents at construction: model_post_init creates
    # _TaskAgentTool(google_search) in root.tools so the task-delegation FC is
    # recognized by _safe_canonical_tools_dict and dispatched via ctx.run_node.
    # The Runner sets root.mode='chat' and build_node(root) adds rerun_on_resume=True.
    root = LlmAgent(
        name="root_agent",
        model=_SearchCallerStubLlm(),
        instruction="Root agent with google_search capability.",
        sub_agents=[google_search_subagent],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="gs_root_gate",
        user_id="test_user",
    )
    runner = Runner(
        agent=root,
        app_name="gs_root_gate",
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


class TestAgentGoogleSearchTaskModeParity:
    """AH-117 / AH-PRD-15 §7 AC #1 MERGE BLOCKER.

    Verifies that on ADK 2.0 a turn invoking agent.google_search via the migrated
    task-mode path (AH-114/115/116) yields the search sub-agent's usage_metadata to
    the outer stream and the production billing pipeline counts its tokens — on both
    the specialist (AH-115) and root/coordinator (AH-116) assignment paths.
    """

    @pytest.mark.asyncio
    async def test_specialist_path_search_tokens_counted(
        self, register_task_mode_google_search: Any
    ) -> None:
        """AC-1 (specialist clause): google_search task-mode tokens counted via AH-115.

        The specialist has agent.google_search in sub_agents (construct-time). ADK
        auto-injects _TaskAgentTool(google_search) at construction. When the specialist's
        LLM emits FunctionCall(name='google_search'), ADK dispatches it via ctx.run_node
        and the sub-agent's usage_metadata reaches the outer Runner stream — merge blocker.
        """
        events = await _capture_specialist_google_search_events()

        # (a) Structural guard: at least one event with author=='google_search' carrying
        # usage_metadata must be present — a vacuous test (no task delegation) fails here
        # because no google_search-authored event appears. Mirrors TestCaptureHarness
        # test_mode_a_events_non_empty's role for the specialist parity tests.
        search_events = [
            e
            for e in events
            if getattr(e, "author", None) == "google_search"
            and getattr(e, "usage_metadata", None) is not None
        ]
        assert len(search_events) >= 1, (
            f"No event with author=='google_search' and usage_metadata found. "
            f"Event authors: {[getattr(e, 'author', None) for e in events]}. "
            "task-mode dispatch likely failed — verify google_search is in "
            "specialist.sub_agents at construction time (model_post_init creates "
            "_TaskAgentTool(google_search)) and rerun_on_resume=True is set."
        )

        # (b) Per-search-event extractor sum == canonical CH-10 total.
        search_billable = sum(
            extract_billable_tokens(e).total_billable for e in search_events
        )
        assert search_billable == _EXPECTED_TOTAL_BILLABLE, (
            f"specialist path: search event billable total={search_billable}, "
            f"expected {_EXPECTED_TOTAL_BILLABLE} (CH-10 canonical fixture). "
            "usage_metadata from the google_search sub-agent is not reaching "
            "extract_billable_tokens — task-mode event propagation broken."
        )

        # (c) SessionTurnAccumulator over search-only events matches canonical totals.
        acc = SessionTurnAccumulator()
        for e in search_events:
            acc.add_event(e)
        delta = acc.build_delta()

        assert _increments_equal(delta["input_tokens_total"], _EXPECTED_INPUT), (
            f"specialist path: accumulator input_tokens_total="
            f"{getattr(delta['input_tokens_total'], 'value', delta['input_tokens_total'])} "
            f"expected {_EXPECTED_INPUT}"
        )
        assert _increments_equal(delta["output_tokens_total"], _EXPECTED_OUTPUT), (
            f"specialist path: accumulator output_tokens_total="
            f"{getattr(delta['output_tokens_total'], 'value', delta['output_tokens_total'])} "
            f"expected {_EXPECTED_OUTPUT}"
        )
        assert _increments_equal(delta["reasoning_tokens_total"], _EXPECTED_REASONING), (
            f"specialist path: accumulator reasoning_tokens_total="
            f"{getattr(delta['reasoning_tokens_total'], 'value', delta['reasoning_tokens_total'])} "
            f"expected {_EXPECTED_REASONING}"
        )

        # (d) Divergence guard: extractor sum == accumulator delta (input+output+reasoning).
        acc_total = (
            getattr(delta["input_tokens_total"], "value", delta["input_tokens_total"])
            + getattr(delta["output_tokens_total"], "value", delta["output_tokens_total"])
            + getattr(
                delta["reasoning_tokens_total"], "value", delta["reasoning_tokens_total"]
            )
        )
        assert acc_total == search_billable, (
            f"specialist path divergence: extract_billable_tokens total={search_billable} "
            f"!= accumulator (input+output+reasoning)={acc_total}. "
            "A future drift between the two billing codepaths would surface here."
        )

    @pytest.mark.asyncio
    async def test_root_path_search_tokens_counted(
        self, register_task_mode_google_search: Any
    ) -> None:
        """AC-1 (root clause) + AC-2 setup: root/coordinator path tokens counted via AH-116.

        The root has agent.google_search in sub_agents at construct-time (mirroring
        AH-116's end state). ADK auto-injects _TaskAgentTool(google_search) via
        model_post_init. Runner's build_node() adds rerun_on_resume=True. When the root's
        LLM emits FunctionCall(name='google_search'), ctx.run_node dispatches the sub-agent
        and its usage_metadata flows to the outer stream — merge blocker.
        """
        events = await _capture_root_google_search_events()

        search_events = [
            e
            for e in events
            if getattr(e, "author", None) == "google_search"
            and getattr(e, "usage_metadata", None) is not None
        ]
        assert len(search_events) >= 1, (
            f"No event with author=='google_search' and usage_metadata found. "
            f"Event authors: {[getattr(e, 'author', None) for e in events]}. "
            "task-mode dispatch failed on the root path — verify google_search is in "
            "root.sub_agents at construction time (model_post_init creates "
            "_TaskAgentTool(google_search); Runner's build_node adds rerun_on_resume=True)."
        )

        search_billable = sum(
            extract_billable_tokens(e).total_billable for e in search_events
        )
        assert search_billable == _EXPECTED_TOTAL_BILLABLE, (
            f"root path: search event billable total={search_billable}, "
            f"expected {_EXPECTED_TOTAL_BILLABLE} (CH-10 canonical fixture). "
            "usage_metadata from the google_search sub-agent is not reaching "
            "extract_billable_tokens on the root/coordinator path."
        )

        acc = SessionTurnAccumulator()
        for e in search_events:
            acc.add_event(e)
        delta = acc.build_delta()

        assert _increments_equal(delta["input_tokens_total"], _EXPECTED_INPUT), (
            f"root path: accumulator input_tokens_total="
            f"{getattr(delta['input_tokens_total'], 'value', delta['input_tokens_total'])} "
            f"expected {_EXPECTED_INPUT}"
        )
        assert _increments_equal(delta["output_tokens_total"], _EXPECTED_OUTPUT), (
            f"root path: accumulator output_tokens_total="
            f"{getattr(delta['output_tokens_total'], 'value', delta['output_tokens_total'])} "
            f"expected {_EXPECTED_OUTPUT}"
        )
        assert _increments_equal(delta["reasoning_tokens_total"], _EXPECTED_REASONING), (
            f"root path: accumulator reasoning_tokens_total="
            f"{getattr(delta['reasoning_tokens_total'], 'value', delta['reasoning_tokens_total'])} "
            f"expected {_EXPECTED_REASONING}"
        )

        acc_total = (
            getattr(delta["input_tokens_total"], "value", delta["input_tokens_total"])
            + getattr(delta["output_tokens_total"], "value", delta["output_tokens_total"])
            + getattr(
                delta["reasoning_tokens_total"], "value", delta["reasoning_tokens_total"]
            )
        )
        assert acc_total == search_billable, (
            f"root path divergence: extract_billable_tokens total={search_billable} "
            f"!= accumulator (input+output+reasoning)={acc_total}"
        )

    @pytest.mark.asyncio
    async def test_specialist_and_root_paths_have_identical_search_token_totals(
        self, register_task_mode_google_search: Any
    ) -> None:
        """AC-2 (no path divergence): specialist and root paths count identical tokens.

        Drives both capture helpers in the same test and asserts that the per-google_search-
        event billable total is identical. A future drift between the specialist resolver
        (AH-115) and the root reconciler (AH-116) that strips usage_metadata on one path
        fails here even if both single-path tests pass individually.
        """
        specialist_events = await _capture_specialist_google_search_events()
        root_events = await _capture_root_google_search_events()

        specialist_search = [
            e
            for e in specialist_events
            if getattr(e, "author", None) == "google_search"
            and getattr(e, "usage_metadata", None) is not None
        ]
        root_search = [
            e
            for e in root_events
            if getattr(e, "author", None) == "google_search"
            and getattr(e, "usage_metadata", None) is not None
        ]

        # Structural guards: if task dispatch silently failed on EITHER path, both
        # totals would be 0 and the equality would report spurious "divergence". Guard
        # separately so failures on individual paths produce actionable diagnostics.
        assert len(specialist_search) >= 1, (
            f"specialist path produced no google_search events with usage_metadata. "
            f"Authors: {[getattr(e, 'author', None) for e in specialist_events]}. "
            "task-mode dispatch failed on the specialist path."
        )
        assert len(root_search) >= 1, (
            f"root path produced no google_search events with usage_metadata. "
            f"Authors: {[getattr(e, 'author', None) for e in root_events]}. "
            "task-mode dispatch failed on the root path."
        )

        specialist_total = sum(
            extract_billable_tokens(e).total_billable for e in specialist_search
        )
        root_total = sum(
            extract_billable_tokens(e).total_billable for e in root_search
        )

        assert specialist_total == root_total == _EXPECTED_TOTAL_BILLABLE, (
            f"Path divergence: specialist total={specialist_total}, "
            f"root total={root_total}, expected both=={_EXPECTED_TOTAL_BILLABLE}. "
            "Check AH-115 (specialist resolver) and AH-116 (root reconciler) for "
            "usage_metadata strip on one path but not the other."
        )
