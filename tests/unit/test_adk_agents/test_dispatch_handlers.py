"""Unit tests for dispatch_handlers acceptance_criteria parameter (AH-4).

Tests the criteria-branch and regression-guard (single-pass) paths for both
dispatch_to_company_news and dispatch_to_google_analytics.

Import strategy: mock neo4j before importing the module under test, then add
the app directory to sys.path so relative imports resolve correctly.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# ── import setup ──────────────────────────────────────────────────────────────
# Mock neo4j before any app imports (supervisor_utils → context_loader →
# neo4j_tools → neo4j triggers the chain).
_neo4j_mock = MagicMock()
_neo4j_mock.exceptions = MagicMock()
_neo4j_mock.exceptions.ServiceUnavailable = Exception
_neo4j_mock.exceptions.SessionExpired = Exception
sys.modules.setdefault("neo4j", _neo4j_mock)
sys.modules.setdefault("neo4j.exceptions", _neo4j_mock.exceptions)

_app_dir = Path(__file__).parents[3] / "app"
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

from adk.agents.utils.dispatch_handlers import (  # noqa: E402
    dispatch_to_company_news,
    dispatch_to_google_analytics,
)

# ── helpers ───────────────────────────────────────────────────────────────────

_NEWS_PREFIX = "news_review"
_GA_PREFIX = "ga_review"


def _mock_tool_context(state: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state or {}
    return ctx


def _make_registry_mock(agent_key: str) -> tuple[MagicMock, MagicMock]:
    """Return (mock_get_registry_fn, mock_agent)."""
    mock_agent = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_agent
    mock_get_registry = MagicMock(return_value=mock_registry)
    return mock_get_registry, mock_agent


# ── TestDispatchToCompanyNewsNoCriteria (regression guard) ────────────────────


class TestDispatchToCompanyNewsNoCriteria:
    """Single-pass path is preserved when acceptance_criteria is absent / falsy."""

    def _run(self, criteria, mock_invoke, mock_get_registry):
        mock_invoke.return_value = "News about Acme"
        result = dispatch_to_company_news(
            "Get news about Acme Corp",
            acceptance_criteria=criteria,
        )
        return result

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_none_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "News"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_company_news("query", acceptance_criteria=None)

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"
        assert result["agent"] == "news"
        assert result["source"] == "company_news_specialist"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_empty_string_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "News"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_company_news("query", acceptance_criteria="")

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_whitespace_only_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "News"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_company_news("query", acceptance_criteria="   ")

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_single_pass_return_shape(self, mock_invoke, mock_get_registry):
        """Single-pass return shape is unchanged from pre-AH-4 (regression guard)."""
        mock_get_registry.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent
        mock_invoke.return_value = "News about the company"

        result = dispatch_to_company_news("Get news about Acme Corp")

        assert result == {
            "status": "success",
            "query": "Get news about Acme Corp",
            "result": "News about the company",
            "source": "company_news_specialist",
            "agent": "news",
        }


# ── TestDispatchToCompanyNewsWithCriteria ─────────────────────────────────────


class TestDispatchToCompanyNewsWithCriteria:
    """Criteria branch: build_review_pipeline → invoke_pipeline_with_events → extract_pipeline_result."""

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_approval_path_return_shape(
        self,
        mock_invoke_retry,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """Approved result: returns {status, query, result, approved=True, source, agent}."""
        mock_agent = MagicMock()
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent

        mock_pipeline = MagicMock()
        mock_build_pipeline.return_value = mock_pipeline
        mock_invoke_with_events.return_value = ("draft text", {"news_review_draft": "draft text"}, [])
        mock_extract.return_value = {"result": "draft text", "approved": True}

        result = dispatch_to_company_news("Get news", acceptance_criteria="Must cite sources.")

        assert result == {
            "status": "success",
            "query": "Get news",
            "result": "draft text",
            "approved": True,
            "source": "company_news_specialist",
            "agent": "news",
        }
        mock_invoke_retry.assert_not_called()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_pipeline_called_with_correct_args(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """build_review_pipeline receives the specialist, criteria, and prefix."""
        mock_agent = MagicMock()
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent

        mock_pipeline = MagicMock()
        mock_build_pipeline.return_value = mock_pipeline
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        criteria = "Must be factual. Must include date."
        dispatch_to_company_news("query", acceptance_criteria=criteria)

        mock_build_pipeline.assert_called_once_with(
            specialist=mock_agent,
            acceptance_criteria=criteria,
            output_key_prefix=_NEWS_PREFIX,
        )
        mock_invoke_with_events.assert_called_once_with(mock_pipeline, "query")

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_exhaustion_path_propagates_warning(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """Exhausted loop: approved=False and warning propagate into the return."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()

        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("last draft", {"news_review_feedback": "needs sources"}, [])
        mock_extract.return_value = {
            "result": "last draft",
            "approved": False,
            "warning": "needs sources",
        }

        result = dispatch_to_company_news("Get news", acceptance_criteria="Must cite sources.")

        assert result["status"] == "success"
        assert result["approved"] is False
        assert result["warning"] == "needs sources"
        assert result["result"] == "last draft"
        assert result["source"] == "company_news_specialist"
        assert result["agent"] == "news"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_query_field_present_in_criteria_branch(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """query key present in criteria-branch return (parity with single-pass shape)."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "answer", "approved": True}

        result = dispatch_to_company_news("my query", acceptance_criteria="be concise")

        assert result["query"] == "my query"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_long_criteria_is_truncated(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """acceptance_criteria > 2000 chars is truncated before build_review_pipeline."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="x" * 2500)

        call_criteria = mock_build_pipeline.call_args.kwargs.get("acceptance_criteria")
        # 2000-char hard cap applied first, then _sanitise_criteria limits each line to
        # _MAX_CRITERIA_LINE_LEN (200) chars, so a single-line string is capped at 200.
        assert call_criteria is not None
        assert len(call_criteria) <= 200

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_fixed_keys_take_precedence_over_outcome(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """Fixed return-dict keys (status, source, agent) override any matching outcome keys."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {
            "result": "draft",
            "approved": True,
            "source": "injected_value",
            "agent": "injected_agent",
        }

        result = dispatch_to_company_news("query", acceptance_criteria="criteria")

        assert result["source"] == "company_news_specialist"
        assert result["agent"] == "news"
        assert result["status"] == "success"
        assert result["result"] == "draft"
        assert result["approved"] is True


# ── TestDispatchToGoogleAnalyticsNoCriteria (regression guard) ─────────────────


class TestDispatchToGoogleAnalyticsNoCriteria:
    """Single-pass path is preserved when acceptance_criteria is absent / falsy."""

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_none_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "Analytics"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_google_analytics("sessions last week", acceptance_criteria=None)

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"
        assert result["agent"] == "analytics"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_empty_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "Analytics"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_google_analytics("query", acceptance_criteria="")

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()
        assert result["status"] == "success"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_whitespace_criteria_uses_single_pass(self, mock_invoke, mock_get_registry):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "Analytics"

        with patch("adk.agents.utils.dispatch_handlers.build_review_pipeline") as mock_brp:
            result = dispatch_to_google_analytics("query", acceptance_criteria="\t  ")

        mock_brp.assert_not_called()
        mock_invoke.assert_called_once()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_single_pass_return_shape(self, mock_invoke, mock_get_registry):
        """Single-pass return shape is unchanged from pre-AH-4 (regression guard)."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "Analytics data"

        result = dispatch_to_google_analytics("sessions last week")

        assert result["status"] == "success"
        assert result["query"] == "sessions last week"
        assert result["result"] == "Analytics data"
        assert result["source"] == "google_analytics_specialist"
        assert result["agent"] == "analytics"
        assert "tenant_id" in result


# ── TestDispatchToGoogleAnalyticsWithCriteria ─────────────────────────────────


class TestDispatchToGoogleAnalyticsWithCriteria:
    """Criteria branch for GA: state forwarded to invoke_pipeline_with_events."""

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_approval_return_shape(
        self,
        mock_invoke_retry,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """Approved result has expected shape including tenant_id."""
        mock_agent = MagicMock()
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent

        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("draft", {"ga_review_draft": "draft"}, [])
        mock_extract.return_value = {"result": "draft", "approved": True}

        result = dispatch_to_google_analytics(
            "bounce rate by country", acceptance_criteria="Include table."
        )

        assert result["status"] == "success"
        assert result["approved"] is True
        assert result["result"] == "draft"
        assert result["source"] == "google_analytics_specialist"
        assert result["agent"] == "analytics"
        assert "tenant_id" in result
        mock_invoke_retry.assert_not_called()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_ga_credentials_forwarded_to_invoke_pipeline_with_events(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """invoke_pipeline_with_events receives state={ga_credentials: ...} when creds in tool_context."""
        ga_creds = {
            "access_token": "tok_abc",
            "refresh_token": "ref_xyz",
            "tenant_id": "acc_123",
            "selected_property_ids": ["prop_1"],
        }
        mock_get_registry.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent

        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        tool_ctx = _mock_tool_context({"account_id": "acc_123", "ga_credentials": ga_creds})
        dispatch_to_google_analytics(
            "bounce rate", tool_context=tool_ctx, acceptance_criteria="Include chart."
        )

        _pipeline_arg, _query_arg = mock_invoke_with_events.call_args.args
        state_kwarg = mock_invoke_with_events.call_args.kwargs.get("state")
        assert state_kwarg == {"ga_credentials": ga_creds}

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_none_credentials_passes_none_state(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """When no GA credentials, invoke_pipeline_with_events receives state=None."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        tool_ctx = _mock_tool_context({"account_id": "acc_123"})
        dispatch_to_google_analytics(
            "sessions", tool_context=tool_ctx, acceptance_criteria="Cover 7 days."
        )

        state_kwarg = mock_invoke_with_events.call_args.kwargs.get("state")
        assert state_kwarg is None

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_pipeline_called_with_correct_prefix(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """GA pipeline uses 'ga_review' prefix (disjoint from 'news_review')."""
        mock_agent = MagicMock()
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = mock_agent

        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="criteria")

        mock_build_pipeline.assert_called_once_with(
            specialist=mock_agent,
            acceptance_criteria="criteria",
            output_key_prefix=_GA_PREFIX,
        )

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_exhaustion_propagates_warning(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("last draft", {}, [])
        mock_extract.return_value = {
            "result": "last draft",
            "approved": False,
            "warning": "missing date range",
        }

        result = dispatch_to_google_analytics("sessions", acceptance_criteria="Cover 7 days.")

        assert result["approved"] is False
        assert result["warning"] == "missing date range"
        assert result["result"] == "last draft"

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_long_criteria_is_truncated(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_extract,
        mock_get_registry,
    ):
        """acceptance_criteria > 2000 chars is truncated before build_review_pipeline."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("", {}, [])
        mock_extract.return_value = {"result": "", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="y" * 2500)

        call_criteria = mock_build_pipeline.call_args.kwargs.get("acceptance_criteria")
        # Same two-stage trimming as the news path: 2000-char hard cap then per-line
        # limit of _MAX_CRITERIA_LINE_LEN (200) characters.
        assert call_criteria is not None
        assert len(call_criteria) <= 200


# ── TestPrefixIsolation ────────────────────────────────────────────────────────


class TestPrefixIsolation:
    """News and GA use distinct output_key_prefix values so state keys cannot collide."""

    def test_prefixes_are_distinct(self):
        assert _NEWS_PREFIX != _GA_PREFIX

    def test_news_prefix_value(self):
        assert _NEWS_PREFIX == "news_review"

    def test_ga_prefix_value(self):
        assert _GA_PREFIX == "ga_review"


# ── TestDispatchReviewLoopTracing (AH-7) ──────────────────────────────────────


def _make_iteration(iteration: int, escalate: bool):
    """Return a ReviewIteration for use in dispatch tracing tests."""
    from adk.agents.utils.review_pipeline import ReviewIteration

    return ReviewIteration(
        iteration=iteration,
        specialist_output=f"specialist output {iteration}",
        reviewer_output="" if escalate else f"feedback {iteration}",
        escalate=escalate,
    )


def _standard_pipeline_mock(worker_name: str = "worker", reviewer_name: str = "reviewer"):
    """Return a MagicMock pipeline with two named sub_agents."""
    mock_worker = MagicMock()
    mock_worker.name = worker_name
    mock_reviewer = MagicMock()
    mock_reviewer.name = reviewer_name
    mock_pipeline = MagicMock()
    mock_pipeline.sub_agents = [mock_worker, mock_reviewer]
    return mock_pipeline


# Common patch stack for criteria-branch tests (bottom to top as listed in decorator order,
# which is reversed in argument order).  Both handlers share the same criteria-branch structure.
_CRITERIA_PATCHES = [
    "adk.agents.utils.dispatch_handlers.build_review_pipeline",
    "adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events",
    "adk.agents.utils.dispatch_handlers.emit_iteration_span",
    "adk.agents.utils.dispatch_handlers.set_pipeline_attrs",
    "adk.agents.utils.dispatch_handlers.extract_iterations",
    "adk.agents.utils.dispatch_handlers.extract_pipeline_result",
    "adk.agents.registry.get_registry",
]


class TestDispatchReviewLoopTracingNews:
    """AH-7: per-iteration tracing wiring for dispatch_to_company_news criteria branch."""

    # ── criteria branch uses invoke_pipeline_with_events ────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_criteria_branch_uses_pipeline_with_events(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """Criteria branch must call invoke_pipeline_with_events."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        mock_invoke_with_events.return_value = (
            "result text",
            {"news_review_draft": "draft", "news_review_feedback": ""},
            [],
        )
        mock_extract_iters.return_value = []
        mock_extract_result.return_value = {"result": "result text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="Be concise.")

        mock_invoke_with_events.assert_called_once()

    # ── emit_iteration_span called per iteration ─────────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_emit_iteration_span_called_once_per_iteration(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """emit_iteration_span is called once for each ReviewIteration record."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        mock_invoke_with_events.return_value = ("text", {"news_review_feedback": ""}, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="Be concise.")

        assert mock_emit.call_count == 2
        assert mock_emit.call_args_list[0].args[0] == 1
        assert mock_emit.call_args_list[1].args[0] == 2

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_emit_iteration_span_receives_specialist_and_reviewer_outputs(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """emit_iteration_span receives the iteration index and both output strings."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        mock_invoke_with_events.return_value = ("text", {}, [])

        it = _make_iteration(1, escalate=True)
        mock_extract_iters.return_value = [it]
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="crit")

        mock_emit.assert_called_once_with(
            it.iteration, it.specialist_output, it.reviewer_output
        )

    # ── set_pipeline_attrs called exactly once ────────────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_set_pipeline_attrs_called_exactly_once(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """set_pipeline_attrs is called exactly once after iteration emission."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        final_state = {"news_review_feedback": ""}
        mock_invoke_with_events.return_value = ("text", final_state, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="crit")

        mock_set_attrs.assert_called_once()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_set_pipeline_attrs_total_iterations_matches_extract_count(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """set_pipeline_attrs receives total_iterations == len(extract_iterations result)."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        final_state = {"news_review_feedback": ""}
        mock_invoke_with_events.return_value = ("text", final_state, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="crit")

        call_kwargs = mock_set_attrs.call_args
        # set_pipeline_attrs(criteria, final_state, prefix, total_iterations)
        assert call_kwargs.args[3] == 2

    # ── empty-criteria path emits ZERO tracing calls ─────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_empty_criteria_no_tracing_calls(
        self,
        mock_invoke,
        mock_emit,
        mock_set_attrs,
        mock_get_registry,
    ):
        """When acceptance_criteria is absent/empty, tracing helpers must not be called."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "result"

        dispatch_to_company_news("query")

        mock_emit.assert_not_called()
        mock_set_attrs.assert_not_called()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_none_criteria_no_tracing_calls(
        self,
        mock_invoke,
        mock_emit,
        mock_set_attrs,
        mock_get_registry,
    ):
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "result"

        dispatch_to_company_news("query", acceptance_criteria=None)

        mock_emit.assert_not_called()
        mock_set_attrs.assert_not_called()

    # ── worker/reviewer names from pipeline.sub_agents ───────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_extract_iterations_called_with_sub_agent_names(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """extract_iterations is called with the actual sub_agent names from the pipeline."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()

        mock_pipeline = _standard_pipeline_mock(
            worker_name="news_specialist_worker",
            reviewer_name="news_review_reviewer",
        )
        mock_build_pipeline.return_value = mock_pipeline

        mock_invoke_with_events.return_value = ("text", {}, [])
        mock_extract_iters.return_value = []
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_company_news("query", acceptance_criteria="crit")

        mock_extract_iters.assert_called_once()
        call_args = mock_extract_iters.call_args
        # extract_iterations(events, specialist_worker_name, reviewer_name, prefix)
        assert call_args.args[1] == "news_specialist_worker"
        assert call_args.args[2] == "news_review_reviewer"


class TestDispatchReviewLoopTracingGA:
    """AH-7: per-iteration tracing wiring for dispatch_to_google_analytics criteria branch."""

    # ── criteria branch uses invoke_pipeline_with_events ────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_criteria_branch_uses_pipeline_with_events(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """GA criteria branch must call invoke_pipeline_with_events."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        mock_invoke_with_events.return_value = (
            "result text",
            {"ga_review_draft": "draft", "ga_review_feedback": ""},
            [],
        )
        mock_extract_iters.return_value = []
        mock_extract_result.return_value = {"result": "result text", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="Include a table.")

        mock_invoke_with_events.assert_called_once()

    # ── emit_iteration_span called per iteration ─────────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_emit_iteration_span_called_once_per_iteration(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """emit_iteration_span is called once for each ReviewIteration record."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        mock_invoke_with_events.return_value = ("text", {"ga_review_feedback": ""}, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="Include a table.")

        assert mock_emit.call_count == 2
        assert mock_emit.call_args_list[0].args[0] == 1
        assert mock_emit.call_args_list[1].args[0] == 2

    # ── set_pipeline_attrs called exactly once ────────────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_set_pipeline_attrs_called_exactly_once(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """set_pipeline_attrs is called exactly once after GA iteration emission."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        final_state = {"ga_review_feedback": ""}
        mock_invoke_with_events.return_value = ("text", final_state, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="Include a table.")

        mock_set_attrs.assert_called_once()

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_set_pipeline_attrs_total_iterations_matches_extract_count(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """GA set_pipeline_attrs receives total_iterations == len(extract_iterations result)."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = _standard_pipeline_mock()
        final_state = {"ga_review_feedback": ""}
        mock_invoke_with_events.return_value = ("text", final_state, [])

        iterations = [_make_iteration(1, escalate=False), _make_iteration(2, escalate=True)]
        mock_extract_iters.return_value = iterations
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="Include a table.")

        call_kwargs = mock_set_attrs.call_args
        assert call_kwargs.args[3] == 2

    # ── empty-criteria path emits ZERO tracing calls ─────────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_agent_with_retry")
    def test_empty_criteria_no_tracing_calls(
        self,
        mock_invoke,
        mock_emit,
        mock_set_attrs,
        mock_get_registry,
    ):
        """When GA acceptance_criteria is absent/empty, tracing helpers must not be called."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_invoke.return_value = "result"

        dispatch_to_google_analytics("query")

        mock_emit.assert_not_called()
        mock_set_attrs.assert_not_called()

    # ── worker/reviewer names from pipeline.sub_agents ───────────────────────

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers.extract_iterations")
    @patch("adk.agents.utils.dispatch_handlers.set_pipeline_attrs")
    @patch("adk.agents.utils.dispatch_handlers.emit_iteration_span")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_extract_iterations_called_with_sub_agent_names(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_emit,
        mock_set_attrs,
        mock_extract_iters,
        mock_extract_result,
        mock_get_registry,
    ):
        """extract_iterations is called with actual sub_agent names from the GA pipeline."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()

        mock_pipeline = _standard_pipeline_mock(
            worker_name="google_analytics_worker",
            reviewer_name="ga_review_reviewer",
        )
        mock_build_pipeline.return_value = mock_pipeline

        mock_invoke_with_events.return_value = ("text", {}, [])
        mock_extract_iters.return_value = []
        mock_extract_result.return_value = {"result": "text", "approved": True}

        dispatch_to_google_analytics("query", acceptance_criteria="crit")

        mock_extract_iters.assert_called_once()
        call_args = mock_extract_iters.call_args
        assert call_args.args[1] == "google_analytics_worker"
        assert call_args.args[2] == "ga_review_reviewer"


# ── TestHallucinatedApprovalDetectionDispatch ─────────────────────────────────


def _make_event(author: str, text: str, escalate: bool | None = None, partial: bool = False):
    """Build a minimal mock ADK Event for hallucination detection tests."""
    event = MagicMock()
    event.author = author
    event.partial = partial
    part = MagicMock()
    part.text = text
    content = MagicMock()
    content.parts = [part]
    event.content = content
    if escalate is not None:
        event.actions = MagicMock()
        event.actions.escalate = escalate
    else:
        event.actions = None
    return event


class TestHallucinatedApprovalDetectionDispatch:
    """dispatch_to_company_news and dispatch_to_google_analytics call
    _check_hallucinated_approval with the events returned by invoke_pipeline."""

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers._check_hallucinated_approval")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_news_check_called_with_events(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_check_hallucination,
        mock_extract,
        mock_get_registry,
    ):
        """dispatch_to_company_news passes events to _check_hallucinated_approval."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()

        reviewer_event = _make_event("news_review_reviewer", "All criteria met.")
        mock_invoke_with_events.return_value = ("draft", {"news_review_draft": "draft"}, [reviewer_event])
        mock_extract.return_value = {"result": "draft", "approved": True}

        dispatch_to_company_news("Get news", acceptance_criteria="Must cite sources.")

        mock_check_hallucination.assert_called_once_with([reviewer_event], "news_review")

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers._check_hallucinated_approval")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_ga_check_called_with_events(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_check_hallucination,
        mock_extract,
        mock_get_registry,
    ):
        """dispatch_to_google_analytics passes events to _check_hallucinated_approval."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()

        reviewer_event = _make_event("ga_review_reviewer", "Approved.")
        mock_invoke_with_events.return_value = ("draft", {"ga_review_draft": "draft"}, [reviewer_event])
        mock_extract.return_value = {"result": "draft", "approved": True}

        dispatch_to_google_analytics("bounce rate", acceptance_criteria="Include table.")

        mock_check_hallucination.assert_called_once_with([reviewer_event], "ga_review")

    @patch("adk.agents.registry.get_registry")
    @patch("adk.agents.utils.dispatch_handlers.extract_pipeline_result")
    @patch("adk.agents.utils.dispatch_handlers._check_hallucinated_approval")
    @patch("adk.agents.utils.dispatch_handlers.invoke_pipeline_with_events")
    @patch("adk.agents.utils.dispatch_handlers.build_review_pipeline")
    def test_news_check_called_with_empty_events_on_timeout(
        self,
        mock_build_pipeline,
        mock_invoke_with_events,
        mock_check_hallucination,
        mock_extract,
        mock_get_registry,
    ):
        """Empty events list (timeout sentinel) is passed through unchanged."""
        mock_get_registry.return_value = MagicMock()
        mock_get_registry.return_value.get.return_value = MagicMock()
        mock_build_pipeline.return_value = MagicMock()
        mock_invoke_with_events.return_value = ("Error: timed out", {}, [])
        mock_extract.return_value = {"result": "", "approved": False, "warning": "no draft"}

        dispatch_to_company_news("Get news", acceptance_criteria="Must cite sources.")

        mock_check_hallucination.assert_called_once_with([], "news_review")
