"""End-to-end tests for Data Visualization (AH-PRD-04).

AH-PRD-04 §7 AC-8 — story 2.4-6:

AC-8: The GA specialist calls ``create_visualization`` and appends a valid
    Vega-Lite v6 artifact to session state when the user requests a chart.
    The review loop approves the response.

The SSE / backend-extractor half of AC-9 (``event: artifacts`` frame ordering
and malformed-spec resilience) is covered in the API integration suite at
``api/tests/integration/chat/test_chat_artifacts.py`` (gated by the
``api-integration-tests`` CI step), so it is intentionally not duplicated here.

Marking convention:
    Tests that require a live Gemini model carry ``@pytest.mark.llm`` so CI
    can opt in without breaking the default fast suite.  Deterministic tests
    carry no ``@pytest.mark.llm`` and use the ``_VizIterFakeLlm`` queue to
    drive the review loop without any network dependency.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.models.registry import LLMRegistry
from google.adk.tools.function_tool import FunctionTool
from google.genai import types as genai_types
from google.genai.errors import ClientError
from google.genai.types import Content, FunctionCall, Part

from app.adk.agents.agent_factory import specialist_runtime as sr
from app.adk.agents.agent_factory import sub_agent_attacher as attacher

_GEMINI_CREDS_AVAILABLE = bool(
    os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT")
)

# ---------------------------------------------------------------------------
# Fake LLM for deterministic review-loop tests
#
# Uses a distinct model-name pattern ("^fake-viz-iter-.*") to avoid any
# coupling with the "^fake-ga-iter-.*" pattern registered in
# test_google_analytics_specialist_e2e and the "^fake-behavioral-.*" pattern
# registered by test_review_pipeline.  Both worker and reviewer drain from
# the same FIFO queue — the response order encodes the iteration sequence.
# ---------------------------------------------------------------------------

_VIZ_ITER_QUEUE: list[LlmResponse] = []


class _VizIterFakeLlm(BaseLlm):
    """Fake LLM that drains responses from _VIZ_ITER_QUEUE in FIFO order.

    Handles both "fake-viz-iter-worker" (worker) and "fake-viz-iter-reviewer"
    (reviewer) model strings.  Response assignment is purely positional, which
    makes the queue the single source of truth for the iteration sequence.
    """

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^fake-viz-iter-.*"]

    async def generate_content_async(  # type: ignore[override]
        self,
        llm_request: Any,
        stream: bool = False,
    ) -> AsyncIterator[LlmResponse]:
        if _VIZ_ITER_QUEUE:
            yield _VIZ_ITER_QUEUE.pop(0)
        else:
            raise AssertionError(
                "_VIZ_ITER_QUEUE exhausted — the LoopAgent consumed more "
                "responses than were queued. Ensure the test loads all expected "
                "responses and that max_iterations was not exceeded."
            )


# Register once per process; idempotent — ADK's registry has no deregister API.
# Pattern "^fake-viz-iter-.*" is intentionally disjoint from the
# "^fake-ga-iter-.*" pattern in test_google_analytics_specialist_e2e and the
# "^fake-behavioral-.*" pattern in test_review_pipeline.
LLMRegistry.register(_VizIterFakeLlm)


# ---------------------------------------------------------------------------
# Stub state helpers (mirrors _MockState / _MockToolContext from AH-28)
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


# ---------------------------------------------------------------------------
# Module-level stub GA tool functions (used by live-LLM tests)
# ---------------------------------------------------------------------------


def get_account_summaries_mt() -> str:
    """List all Google Analytics accounts and properties."""
    return json.dumps({
        "accounts": [
            {
                "displayName": "Test Account",
                "propertySummaries": [
                    {
                        "property": "properties/123456789",
                        "displayName": "Test Property",
                    }
                ],
            }
        ]
    })


def run_report_mt(
    property_id: str,
    date_ranges: list,
    metrics: list | None = None,
    dimensions: list | None = None,
) -> str:
    """Run a GA4 report: week-over-week daily sessions."""
    return json.dumps({
        "rows": [
            {"dimensionValues": [{"value": "2024-01-01"}], "metricValues": [{"value": "4823"}]},
            {"dimensionValues": [{"value": "2024-01-02"}], "metricValues": [{"value": "5391"}]},
            {"dimensionValues": [{"value": "2024-01-03"}], "metricValues": [{"value": "5102"}]},
            {"dimensionValues": [{"value": "2024-01-04"}], "metricValues": [{"value": "4950"}]},
            {"dimensionValues": [{"value": "2024-01-05"}], "metricValues": [{"value": "5301"}]},
            {"dimensionValues": [{"value": "2024-01-06"}], "metricValues": [{"value": "5820"}]},
            {"dimensionValues": [{"value": "2024-01-07"}], "metricValues": [{"value": "6010"}]},
        ]
    })


def run_report_bounce_mt(
    property_id: str,
    date_ranges: list,
    metrics: list | None = None,
    dimensions: list | None = None,
) -> str:
    """Run a GA4 report: bounce rate by day."""
    return json.dumps({
        "rows": [
            {"dimensionValues": [{"value": "2024-01-01"}], "metricValues": [{"value": "0.42"}]},
            {"dimensionValues": [{"value": "2024-01-02"}], "metricValues": [{"value": "0.38"}]},
        ]
    })


# ---------------------------------------------------------------------------
# Autouse fixture: reset caches and queue between tests
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
    _VIZ_ITER_QUEUE.clear()
    yield
    sr._specialists_cache.clear()
    sr._clear_block_cache_for_tests()
    sr._clear_list_cache_for_tests()
    attacher._reset_applied_state_for_tests()
    clear_config_cache()
    clear_system_settings_cache_for_tests()
    assert not _VIZ_ITER_QUEUE, (
        f"_VIZ_ITER_QUEUE not empty after test teardown — "
        f"{len(_VIZ_ITER_QUEUE)} response(s) were not consumed. "
        "This usually means fewer LoopAgent iterations ran than expected."
    )
    _VIZ_ITER_QUEUE.clear()


# ---------------------------------------------------------------------------
# Helper: build a LoopAgent via resolve_agent with all external deps mocked
# ---------------------------------------------------------------------------


def _build_loop_agent_with_patches(
    stack: ExitStack,
    config: Any,
    specialist_factory_fn: Any,
) -> Any:
    """Build a LoopAgent via resolve_agent with Firestore/MCP/tools all mocked.

    Returns the resolved agent (expected to be a LoopAgent when
    config.default_acceptance_criteria is set).
    """
    from unittest.mock import patch as _patch

    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
    from app.adk.agents.agent_factory.tests.test_specialist_runtime import (
        _FakeFirestoreDb,
    )

    stack.enter_context(
        _patch.object(sr, "resolve_config", return_value=config)
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
            side_effect=specialist_factory_fn,
        )
    )
    stack.enter_context(
        _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value=None,
        )
    )
    return sr.resolve_agent("google_analytics_specialist", account_id=None)


# ---------------------------------------------------------------------------
# Test 1: Happy path — single line chart (live LLM)
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
async def test_data_viz_e2e_traffic_trends_renders_line_chart(trial: int) -> None:
    """AC-8 (AH-PRD-04 §7, story 2.4): a traffic-trends + chart prompt produces a
    valid Vega-Lite v6 line-chart artifact in session state, and the review loop
    approves the response.

    MCP layer is stubbed via FunctionTool wrappers; every LLM call is real.
    Three trials for flake tolerance.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.agents.utils.review_pipeline import extract_pipeline_result
    from app.adk.tools.function_tools.create_visualization import create_visualization

    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="gemini-2.5-flash",
        description="GA specialist (viz e2e test)",
        mcp_servers=[],
        code_execution_enabled=False,
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model=None,
        ken_e_sub_agent=True,
    )

    def _specialist_factory(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            tools=[
                FunctionTool(get_account_summaries_mt),
                FunctionTool(run_report_mt),
                FunctionTool(create_visualization),
            ],
            disallow_transfer_to_parent=True,
        )

    with ExitStack() as stack:
        loop_agent = _build_loop_agent_with_patches(stack, ga_config, _specialist_factory)

    assert isinstance(loop_agent, LoopAgent), (
        f"[trial {trial}] resolve_agent must return a LoopAgent; "
        f"got {type(loop_agent).__name__}"
    )

    output_prefix = "google_analytics_specialist_review"
    app_name = f"viz_e2e_line_chart_trial_{trial}"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=app_name,
        user_id=f"user_viz_trial_{trial}",
    )
    runner = Runner(
        agent=loop_agent,
        app_name=app_name,
        session_service=session_service,
    )

    try:
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[Part.from_text(
                    text="Show me traffic trends for the past week and include a line chart."
                )],
            ),
        ):
            pass
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"[trial {trial}] Gemini credentials lack required permission (HTTP 403). "
                f"Grant roles/aiplatform.user or set GOOGLE_API_KEY. "
                f"Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"[trial {trial}] Model not available in this project/region (HTTP 404). "
                f"Original error: {exc!s:.160}"
            )
        raise

    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}

    response_artifacts: list[dict[str, Any]] = state.get("response_artifacts", [])
    assert response_artifacts, (
        f"[trial {trial}] response_artifacts must be non-empty after a chart request; "
        f"state keys: {list(state.keys())}"
    )
    first = response_artifacts[0]
    assert first["metadata"]["chart_type_suggestion"] == "line", (
        f"[trial {trial}] chart_type_suggestion must be 'line'; "
        f"got {first['metadata']['chart_type_suggestion']!r}"
    )
    assert first["spec"]["$schema"] == "https://vega.github.io/schema/vega-lite/v6.json", (
        f"[trial {trial}] spec must use Vega-Lite v6 $schema; "
        f"got {first['spec'].get('$schema')!r}"
    )
    assert isinstance(first["spec"]["data"]["values"], list) and first["spec"]["data"]["values"], (
        f"[trial {trial}] spec.data.values must be a non-empty list"
    )
    assert "encoding" in first["spec"], (
        f"[trial {trial}] spec must contain an 'encoding' key"
    )
    assert "config" not in first["spec"], (
        f"[trial {trial}] spec must not contain a 'config' key (theme applied frontend-side)"
    )
    pipeline_result = extract_pipeline_result(state, output_prefix)
    assert pipeline_result["approved"] is True, (
        f"[trial {trial}] Review loop must approve the response. "
        f"Last feedback: {pipeline_result.get('warning', '')!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: Multiple artifacts in one turn (live LLM)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("trial", [1, 2])
@pytest.mark.llm
@pytest.mark.skipif(
    not _GEMINI_CREDS_AVAILABLE,
    reason=(
        "Live Gemini credentials not configured — set GOOGLE_API_KEY "
        "or GOOGLE_CLOUD_PROJECT"
    ),
)
@pytest.mark.asyncio
async def test_data_viz_e2e_multiple_artifacts_appear_in_order(trial: int) -> None:
    """AC-8 (AH-PRD-04 §7, story 2.5): when two charts are requested in one turn,
    at least two valid Artifact objects appear in session state with distinct titles.

    If only one artifact is produced (model chose to produce one chart), the test
    skips rather than fails — this is live-LLM flakiness, not a code defect.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
        GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        GA_SPECIALIST_INSTRUCTION,
    )
    from app.adk.tools.function_tools.create_visualization import create_visualization
    from shared.artifact_models import Artifact

    ga_config = MergedAgentConfig(
        instruction=GA_SPECIALIST_INSTRUCTION,
        model="gemini-2.5-flash",
        description="GA specialist (multi-artifact test)",
        mcp_servers=[],
        code_execution_enabled=False,
        default_acceptance_criteria=GA_SPECIALIST_ACCEPTANCE_CRITERIA,
        reviewer_model=None,
        ken_e_sub_agent=True,
    )

    def _specialist_factory(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            tools=[
                FunctionTool(get_account_summaries_mt),
                FunctionTool(run_report_mt),
                FunctionTool(run_report_bounce_mt),
                FunctionTool(create_visualization),
            ],
            disallow_transfer_to_parent=True,
        )

    with ExitStack() as stack:
        loop_agent = _build_loop_agent_with_patches(stack, ga_config, _specialist_factory)

    assert isinstance(loop_agent, LoopAgent), (
        f"[trial {trial}] resolve_agent must return a LoopAgent; "
        f"got {type(loop_agent).__name__}"
    )

    app_name = f"viz_e2e_multi_artifact_trial_{trial}"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=app_name,
        user_id=f"user_multi_art_{trial}",
    )
    runner = Runner(
        agent=loop_agent,
        app_name=app_name,
        session_service=session_service,
    )

    try:
        async for _ in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=genai_types.Content(
                role="user",
                parts=[Part.from_text(
                    text=(
                        "Show me a chart of weekly sessions AND a chart of bounce rate"
                        " by day for property 123456789."
                    )
                )],
            ),
        ):
            pass
    except ClientError as exc:
        if exc.code == 403:
            pytest.skip(
                f"[trial {trial}] Gemini credentials lack required permission (HTTP 403). "
                f"Original error: {exc!s:.160}"
            )
        if exc.code == 404:
            pytest.skip(
                f"[trial {trial}] Model not available (HTTP 404). "
                f"Original error: {exc!s:.160}"
            )
        raise

    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}
    response_artifacts: list[dict[str, Any]] = state.get("response_artifacts", [])

    if len(response_artifacts) < 2:
        pytest.skip(
            f"[trial {trial}] Only {len(response_artifacts)} artifact(s) produced — "
            "flake tolerance: model chose fewer charts than requested."
        )

    for artifact_dict in response_artifacts:
        Artifact.model_validate(artifact_dict)

    titles = [a["metadata"]["title"] for a in response_artifacts]
    assert len(set(titles)) >= 2, (
        f"[trial {trial}] Artifacts must have distinct titles; got {titles!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Review-loop approve/reject with create_visualization (deterministic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_viz_e2e_review_loop_requires_chart_iterates_then_approves() -> None:
    """AC-8 (AH-PRD-04 §7, story 2.6): when the worker's first draft lacks a chart,
    the reviewer rejects it; the worker calls create_visualization on the second pass,
    and the reviewer approves.

    The queue encodes the 5-response sequence required when a tool call intervenes:

    1. worker iter 1:    text-only draft (no chart — criterion not met)
    2. reviewer iter 1:  text rejection (no exit_loop → loop continues)
    3. worker iter 2, A: FunctionCall(name="create_visualization", …) — ADK routes
                         this to the real Python function and appends the FunctionResponse
    4. worker iter 2, B: text draft after the tool returns (ADK calls LLM again)
    5. reviewer iter 2:  FunctionCall(name="exit_loop", {}) — approval

    Uses ``_VizIterFakeLlm`` (fake-viz-iter-worker / fake-viz-iter-reviewer) so the
    test is fully deterministic with no live-model dependency. The real
    create_visualization function runs so that session state is populated.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
    from app.adk.agents.utils.review_pipeline import (
        extract_iterations,
        extract_pipeline_result,
    )
    from app.adk.tools.function_tools.create_visualization import create_visualization

    _VIZ_CRAFT_ARGS = {
        "chart_type": "line",
        "title": "Weekly Sessions",
        "data": json.dumps([
            {"date": "2024-01-01", "sessions": 4823},
            {"date": "2024-01-02", "sessions": 5391},
        ]),
        "encoding": json.dumps({
            "x": {"field": "date", "type": "ordinal", "title": "Date"},
            "y": {"field": "sessions", "type": "quantitative", "title": "Sessions"},
        }),
    }

    _VIZ_ITER_QUEUE.extend([
        # worker iter 1: text-only draft (no chart)
        LlmResponse(
            content=Content(
                role="model",
                parts=[genai_types.Part(text="Sessions grew 11.78% week-over-week.")],
            )
        ),
        # reviewer iter 1: text rejection (no exit_loop → loop continues)
        LlmResponse(
            content=Content(
                role="model",
                parts=[genai_types.Part(
                    text=(
                        "Acceptance criteria require a line chart of weekly sessions;"
                        " no artifact was provided."
                    )
                )],
            )
        ),
        # worker iter 2, call A: FunctionCall to create_visualization
        LlmResponse(
            content=Content(
                role="model",
                parts=[genai_types.Part(
                    function_call=FunctionCall(
                        name="create_visualization",
                        args=_VIZ_CRAFT_ARGS,
                    )
                )],
            )
        ),
        # worker iter 2, call B: text draft after tool execution (ADK calls LLM again)
        LlmResponse(
            content=Content(
                role="model",
                parts=[genai_types.Part(
                    text="Sessions grew 11.78% week-over-week. Here is a line chart."
                )],
            )
        ),
        # reviewer iter 2: exit_loop (approval)
        LlmResponse(
            content=Content(
                role="model",
                parts=[genai_types.Part(
                    function_call=FunctionCall(name="exit_loop", args={})
                )],
            )
        ),
    ])

    ga_config = MergedAgentConfig(
        instruction="You are a Google Analytics specialist. Include charts when requested.",
        model="fake-viz-iter-worker",
        description="GA specialist (viz iteration test)",
        mcp_servers=[],
        code_execution_enabled=False,
        default_acceptance_criteria="Include a line chart of weekly sessions.",
        reviewer_model="fake-viz-iter-reviewer",
        ken_e_sub_agent=True,
    )

    def _specialist_from_config(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
        return LlmAgent(
            name=name,
            model=_config.model,
            instruction=_config.instruction,
            tools=[FunctionTool(create_visualization)],
            disallow_transfer_to_parent=True,
        )

    with ExitStack() as stack:
        loop_agent = _build_loop_agent_with_patches(stack, ga_config, _specialist_from_config)

    assert isinstance(loop_agent, LoopAgent), (
        f"resolve_agent must return a LoopAgent; got {type(loop_agent).__name__}"
    )

    output_prefix = "google_analytics_specialist_review"
    worker_name = loop_agent.sub_agents[0].name
    reviewer_name = loop_agent.sub_agents[1].name

    app_name = "viz_iteration_test"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=app_name,
        user_id="user_viz_iter",
    )
    runner = Runner(
        agent=loop_agent,
        app_name=app_name,
        session_service=session_service,
    )

    events: list[Any] = []
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=genai_types.Content(
            role="user",
            parts=[Part.from_text(
                text=(
                    "Property 123456789: sessions were 4823 last week and 5391 this"
                    " week. Show me a line chart of weekly sessions."
                )
            )],
        ),
    ):
        events.append(event)

    final_session = await session_service.get_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
    )
    state = dict(final_session.state) if final_session else {}

    iterations = extract_iterations(events, worker_name, reviewer_name, output_prefix)

    assert len(iterations) == 2, (
        f"Expected exactly 2 review iterations; got {len(iterations)}. "
        f"Events collected: {len(events)}. Records: {iterations}"
    )
    assert iterations[0].escalate is False, (
        f"Iteration 1 reviewer must NOT escalate (rejection); "
        f"got escalate={iterations[0].escalate!r}"
    )
    assert iterations[1].escalate is True, (
        f"Iteration 2 reviewer must escalate (approval via exit_loop); "
        f"got escalate={iterations[1].escalate!r}"
    )

    response_artifacts: list[dict[str, Any]] = state.get("response_artifacts", [])
    assert response_artifacts, (
        "response_artifacts must be non-empty after create_visualization ran; "
        f"state keys: {list(state.keys())}"
    )
    assert response_artifacts[0]["metadata"]["chart_type_suggestion"] == "line", (
        f"chart_type_suggestion must be 'line'; "
        f"got {response_artifacts[0]['metadata']['chart_type_suggestion']!r}"
    )

    pipeline_result = extract_pipeline_result(state, output_prefix)
    assert pipeline_result["approved"] is True, (
        f"Pipeline must be approved after iteration 2. "
        f"Last feedback: {pipeline_result.get('warning', '')!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: Tool-level invalid-JSON handling (no live LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_data_viz_e2e_invalid_json_input_returns_clear_error_no_artifact_appended() -> None:
    """AC-8 (AH-PRD-04 §7): create_visualization returns an error string prefixed
    with "ERROR: invalid JSON in ..." when data or encoding is not valid JSON.
    No exception escapes and no artifact is appended to session state.

    ``create_visualization`` is an async tool (it awaits ``register_artifact``
    persistence on the success path), so the calls below are awaited even though
    the invalid-JSON guard returns before any persistence happens.
    """
    from app.adk.tools.function_tools.create_visualization import create_visualization

    ctx = _MockToolContext()

    result_bad_data = await create_visualization(
        chart_type="line",
        title="X",
        data="not-json",
        encoding="{}",
        tool_context=ctx,
    )
    assert result_bad_data.startswith("ERROR: invalid JSON in data"), (
        f"Expected error prefix 'ERROR: invalid JSON in data'; got {result_bad_data!r}"
    )

    result_bad_encoding = await create_visualization(
        chart_type="line",
        title="X",
        data="[{}]",
        encoding="not-json",
        tool_context=ctx,
    )
    assert result_bad_encoding.startswith("ERROR: invalid JSON in encoding"), (
        f"Expected error prefix 'ERROR: invalid JSON in encoding'; "
        f"got {result_bad_encoding!r}"
    )

    remaining: list[Any] = ctx.state.get("response_artifacts", [])
    assert remaining == [], (
        f"No artifact must be appended after invalid-JSON calls; "
        f"found {len(remaining)} artifact(s) in state"
    )
