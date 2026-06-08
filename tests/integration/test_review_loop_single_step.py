"""Single-step end-to-end integration tests for the review loop (AC#8-#11).

Exercises §7 ACs from AH-PRD-01 by calling dispatch_to_company_news and
dispatch_to_google_analytics with a FakeLlm backend:
  AC#8  — Regression guard: no review loop when acceptance_criteria is absent/empty/whitespace.
  AC#9  — Happy path: first-pass approval updates state and fires tracing calls.
  AC#10 — Exhaustion: max_iterations reached without approval.
  AC#11 — Hallucinated-approval detection fires observability span + warning log.

Test design:
  - _FakeItLlm (pattern "^fake-it-.*") drains module-level _fake_response_queue.
    Disjoint from the unit-test pattern "^fake-behavioral-.*" so queues don't
    cross-contaminate when both suites run in one pytest process.
  - build_review_pipeline is shimmed to inject reviewer_model="fake-it-reviewer"
    and cap max_iterations=2.  The real LoopAgent executes end-to-end.
  - get_registry() is patched to return a fake specialist with model="fake-it-worker".
  - invoke_pipeline is NOT mocked; all LLM I/O flows through _FakeItLlm.
  - emit_iteration_span / set_pipeline_attrs are spied on via patch.
  - _emit_hallucination_span is patched via patch.object on the review_pipeline
    module to capture calls without triggering Weave I/O.
"""

import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── neo4j mock — must precede any app imports ─────────────────────────────────
_neo4j_mock = MagicMock()
_neo4j_mock.exceptions = MagicMock()
_neo4j_mock.exceptions.ServiceUnavailable = Exception
_neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", _neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", _neo4j_mock.exceptions)

# ── sys.path: expose app/ as import root ──────────────────────────────────────
_app_dir = Path(__file__).parents[2] / "app"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

os.environ.setdefault("VERTEX_AI_NEWS_DATASTORE_ID", "test-datastore")

# ── Imports ────────────────────────────────────────────────────────────────────
import adk.agents.utils.review_pipeline as _rp_module  # noqa: E402
from adk.agents.utils.dispatch_handlers import (  # noqa: E402
    dispatch_to_company_news,
    dispatch_to_google_analytics,
)
from adk.agents.utils.review_pipeline import (  # noqa: E402
    build_review_pipeline as _orig_build,
)
from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models.base_llm import BaseLlm  # noqa: E402
from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.adk.models.registry import LLMRegistry  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

# ── FakeLlm ────────────────────────────────────────────────────────────────────

_fake_response_queue: list[LlmResponse] = []


class _FakeItLlm(BaseLlm):
    """Drains responses from _fake_response_queue FIFO; emits fallback when empty."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"^fake-it-.*"]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: object, stream: bool = False
    ):
        if _fake_response_queue:
            yield _fake_response_queue.pop(0)
        else:
            yield LlmResponse(
                content=genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text="(no response queued)")],
                )
            )


LLMRegistry.register(_FakeItLlm)


# ── Response factories ─────────────────────────────────────────────────────────


def _text(text: str) -> LlmResponse:
    return LlmResponse(
        content=genai_types.Content(role="model", parts=[genai_types.Part(text=text)])
    )


def _exit_loop_response() -> LlmResponse:
    return LlmResponse(
        content=genai_types.Content(
            role="model",
            parts=[
                genai_types.Part(
                    function_call=genai_types.FunctionCall(name="exit_loop", args={})
                )
            ],
        )
    )


# ── Fixtures and helpers ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clear_queue():
    _fake_response_queue.clear()
    yield
    _fake_response_queue.clear()


def _stub_specialist(name: str) -> LlmAgent:
    return LlmAgent(name=name, model="fake-it-worker", instruction="You are helpful.")


def _registry_ctx(specialist: LlmAgent):
    mock_registry = MagicMock()
    mock_registry.get.return_value = specialist
    return patch("adk.agents.registry.get_registry", return_value=mock_registry)


def _pipeline_shim_ctx():
    """Wraps build_review_pipeline: forces reviewer_model='fake-it-reviewer' and max_iterations=2."""

    def _shim(
        specialist,
        acceptance_criteria,
        output_key_prefix=None,
        max_iterations=None,
        reviewer_model=None,
    ):
        return _orig_build(
            specialist=specialist,
            acceptance_criteria=acceptance_criteria,
            output_key_prefix=output_key_prefix,
            max_iterations=2,
            reviewer_model="fake-it-reviewer",
        )

    return patch(
        "adk.agents.utils.dispatch_handlers.build_review_pipeline", side_effect=_shim
    )


# ── Scenario 1: Regression Guard (AC#8) ───────────────────────────────────────


class TestScenario1RegressionGuard:
    """AC#8 — build_review_pipeline never called when acceptance_criteria is absent, empty, or whitespace."""

    @pytest.mark.parametrize(
        "criteria",
        [None, "", "   "],
        ids=["none", "empty", "whitespace"],
    )
    def test_news_no_loop_single_pass(self, criteria):
        specialist = _stub_specialist("news")
        with (
            _registry_ctx(specialist),
            patch(
                "adk.agents.utils.dispatch_handlers.invoke_agent_with_retry"
            ) as mock_invoke,
            patch(
                "adk.agents.utils.dispatch_handlers.build_review_pipeline"
            ) as mock_brp,
        ):
            mock_invoke.return_value = "news result"
            result = dispatch_to_company_news("query", acceptance_criteria=criteria)

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result == {
            "status": "success",
            "query": "query",
            "result": "news result",
            "source": "company_news_specialist",
            "agent": "news",
        }

    @pytest.mark.parametrize(
        "criteria",
        [None, "", "   "],
        ids=["none", "empty", "whitespace"],
    )
    def test_ga_no_loop_single_pass(self, criteria):
        specialist = _stub_specialist("google_analytics")
        with (
            _registry_ctx(specialist),
            patch(
                "adk.agents.utils.dispatch_handlers.invoke_agent_with_retry"
            ) as mock_invoke,
            patch(
                "adk.agents.utils.dispatch_handlers.build_review_pipeline"
            ) as mock_brp,
        ):
            mock_invoke.return_value = "ga result"
            result = dispatch_to_google_analytics("query", acceptance_criteria=criteria)

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"
        assert result["result"] == "ga result"


# ── Scenario 2: Happy Path (AC#9) ─────────────────────────────────────────────


class TestScenario2HappyPath:
    """AC#9 — Reviewer approves on iteration 1 via exit_loop."""

    def test_approved_outcome_and_tracing(self):
        _fake_response_queue.extend(
            [
                _text("Detailed news analysis with three cited data points."),
                _exit_loop_response(),
            ]
        )
        specialist = _stub_specialist("news")

        with (
            _registry_ctx(specialist),
            _pipeline_shim_ctx(),
            patch(
                "adk.agents.utils.dispatch_handlers.emit_iteration_span"
            ) as mock_emit,
            patch(
                "adk.agents.utils.dispatch_handlers.set_pipeline_attrs"
            ) as mock_set_attrs,
            patch.object(_rp_module, "_emit_hallucination_span") as mock_hall,
        ):
            result = dispatch_to_company_news(
                "What is happening at Acme Corp?",
                acceptance_criteria="Include at least three data points.",
            )

        assert result["status"] == "success"
        assert result["approved"] is True
        assert "warning" not in result
        assert (
            result["result"] == "Detailed news analysis with three cited data points."
        )
        mock_emit.assert_called_once()
        mock_set_attrs.assert_called_once()
        mock_hall.assert_not_called()


# ── Scenario 3: Exhaustion (AC#10) ────────────────────────────────────────────


class TestScenario3Exhaustion:
    """AC#10 — Loop reaches max_iterations=2 without reviewer approval."""

    def test_exhaustion_not_approved_warning_present(self):
        _fake_response_queue.extend(
            [
                _text("First draft — only mentions one data point."),
                _text("Criteria not met: needs at least three data points."),
                _text("Second draft — mentions two data points."),
                _text("Still missing: needs three data points minimum."),
            ]
        )
        specialist = _stub_specialist("news")

        with (
            _registry_ctx(specialist),
            _pipeline_shim_ctx(),
            patch(
                "adk.agents.utils.dispatch_handlers.emit_iteration_span"
            ) as mock_emit,
            patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs"),
            patch.object(_rp_module, "_emit_hallucination_span") as mock_hall,
        ):
            result = dispatch_to_company_news(
                "What is happening at Acme Corp?",
                acceptance_criteria="Include at least three data points.",
            )

        assert result["status"] == "success"
        assert result["approved"] is False
        assert isinstance(result.get("warning"), str) and result["warning"]
        assert mock_emit.call_count == 2
        mock_hall.assert_not_called()


# ── Scenario 4: Hallucinated Approval (AC#11) ─────────────────────────────────


class TestScenario4HallucinatedApproval:
    """AC#11 — Reviewer writes approval text without calling exit_loop; span fires and warning logged."""

    def test_hallucination_span_and_warning_logged(self, caplog):
        hallucination_text = "All criteria are met. Calling exit_loop."
        _fake_response_queue.extend(
            [
                _text("Initial draft content."),
                _text(hallucination_text),
                _text("Improved draft content."),
                _text(hallucination_text),
            ]
        )
        specialist = _stub_specialist("news")

        with (
            _registry_ctx(specialist),
            _pipeline_shim_ctx(),
            patch("adk.agents.utils.dispatch_handlers.emit_iteration_span"),
            patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs"),
            patch.object(_rp_module, "_emit_hallucination_span") as mock_hall,
            caplog.at_level(logging.WARNING, logger="adk.agents.utils.review_pipeline"),
        ):
            dispatch_to_company_news(
                "What is happening at Acme Corp?",
                acceptance_criteria="Include at least three data points.",
            )

        # _check_hallucinated_approval is a single post-run call, not per-iteration.
        # It inspects only the final reviewer event, so span fires exactly once.
        mock_hall.assert_called_once()
        assert any(
            "Hallucinated approval" in r.message and r.levelno == logging.WARNING
            for r in caplog.records
        )


# ── Scenario 5: Required-Visualization Loop Contract (AH-137) ─────────────────


class TestScenario5RequiredVisualization:
    """AH-137 — Required-visualization loop contract (FakeLlm plumbing test).

    Validates the loop state-transition machinery under the AH-137 contract:
      - Positive case: reviewer rejects text-only draft (iteration 1); specialist
        seeds response_artifacts (iteration 2); projector writes <prefix>_artifacts;
        reviewer approves (iteration 2). Loop terminates approved=True.
      - Negative case: ACs have no visualization requirement; reviewer approves
        text-only draft on iteration 1 (artifact absence alone is not a defect).

    NOTE: These tests use FakeLlm (scripted reviewer responses) so they validate
    loop plumbing and state-transition machinery, NOT actual LLM judgment of
    missing visualizations. True LLM-judgment validation lives in AH-140
    (E2E / @pytest.mark.llm). The test names and fixture comments explicitly
    document this plumbing-vs-judgement distinction.
    """

    @staticmethod
    def _make_artifact_entry() -> dict:
        """Minimal Artifact dict for seeding response_artifacts."""
        from shared.artifact_models import Artifact, ArtifactMetadata

        return Artifact(
            type="visualization",
            spec={
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "line",
                "encoding": {
                    "x": {"field": "date", "type": "temporal"},
                    "y": {"field": "sessions", "type": "quantitative"},
                },
                "data": {"values": [{"date": "2026-01-01", "sessions": 100}]},
            },
            metadata=ArtifactMetadata(
                chart_type_suggestion="line",
                title="Daily Sessions",
                data_source="google_analytics",
            ),
        ).model_dump()

    def test_reject_then_approve_when_artifact_added_on_iteration_2(self):
        """Positive case: iteration 1 rejects (no artifact), iteration 2 approves (artifact seeded).

        AH-137 contract: loop runs 2 iterations, ends approved=True, and the
        projector callback populates <prefix>_artifacts before the reviewer fires
        on iteration 2.

        The reviewer responses are scripted via FakeLlm — this test documents the
        plumbing contract (reject→continue→approve→exit), not LLM judgment.
        """
        # Scripted queue: worker1 → reviewer1-rejects → worker2 → reviewer2-approves.
        _fake_response_queue.extend(
            [
                _text("Here are the GA metrics for the past 7 days."),
                _text(
                    "Acceptance criteria require a line chart of daily sessions; "
                    "the draft contains no visualization."
                ),
                _text("Here are the GA metrics with a chart attached."),
                _exit_loop_response(),
            ]
        )

        # before_agent_callback that seeds response_artifacts on the second
        # specialist invocation (iteration 2). Seeding directly proves the
        # projector→reviewer path without simulating a full create_visualization
        # function-call event (which would double the test surface — see
        # implementation plan Decision §3).
        _call_counts = {"count": 0}
        artifact_entry = self._make_artifact_entry()

        def _seed_artifact_on_iter2(callback_context):
            _call_counts["count"] += 1
            if _call_counts["count"] >= 2:
                state = callback_context.state
                existing = list(state.get("response_artifacts") or [])
                existing.append(artifact_entry)
                state["response_artifacts"] = existing

        specialist = LlmAgent(
            name="news",
            model="fake-it-worker",
            instruction="You are helpful.",
            before_agent_callback=_seed_artifact_on_iter2,
        )

        # dispatch_to_company_news is used (not GA) because it is the canonical
        # FakeLlm fixture for review-loop transition tests (Scenarios 1-4). The
        # goal is loop plumbing, not specialist routing - the dispatch function
        # used does not affect the reject->approve state machine under test.
        with (
            _registry_ctx(specialist),
            _pipeline_shim_ctx(),
            patch("adk.agents.utils.dispatch_handlers.emit_iteration_span"),
            patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs"),
            patch.object(_rp_module, "_emit_hallucination_span"),
        ):
            result = dispatch_to_company_news(
                "Show me traffic trends for the past week",
                acceptance_criteria=(
                    "Include a line chart showing daily sessions with labeled axes."
                ),
            )

        assert result["status"] == "success"
        assert result["approved"] is True
        assert "warning" not in result
        # Confirm the full reject→approve queue was consumed (2 iterations ran).
        assert not _fake_response_queue

    def test_text_only_draft_approved_when_no_visualization_required(self):
        """Negative case: artifact absence alone is not a defect when ACs don't require a chart.

        AH-137 carve-out: reviewer approves on iteration 1 even though no artifact
        was produced. The reviewer response is scripted to exit_loop immediately.
        """
        # Scripted queue: worker text-only → reviewer exits immediately.
        _fake_response_queue.extend(
            [
                _text(
                    "Sessions increased 12% week-over-week, driven by organic search."
                ),
                _exit_loop_response(),
            ]
        )

        specialist = _stub_specialist("news")

        with (
            _registry_ctx(specialist),
            _pipeline_shim_ctx(),
            patch("adk.agents.utils.dispatch_handlers.emit_iteration_span"),
            patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs"),
            patch.object(_rp_module, "_emit_hallucination_span"),
        ):
            result = dispatch_to_company_news(
                "What drove traffic growth last week?",
                acceptance_criteria=(
                    "Explain the primary driver of the week-over-week traffic change."
                ),
            )

        assert result["status"] == "success"
        assert result["approved"] is True
        assert "warning" not in result
