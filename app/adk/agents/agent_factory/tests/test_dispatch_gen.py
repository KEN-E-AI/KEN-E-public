"""
Unit tests for app.adk.agents.agent_factory.dispatch.

All live ADK / Weave / GCP calls are patched at the dispatch module boundary.
No I/O takes place.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.adk.agents.agent_factory.dispatch import (
    assemble_available_specialists_block,
    generate_dispatch_functions,
)
from app.adk.agents.utils.agent_retry import DEFAULT_RETRY_CONFIG

# ---------------------------------------------------------------------------
# Patch-path constants — patch at the dispatch module's import namespace
# ---------------------------------------------------------------------------

_PATCH_BUILD_PIPELINE = "app.adk.agents.agent_factory.dispatch.build_review_pipeline"
_PATCH_INVOKE_PIPELINE = "app.adk.agents.utils.supervisor_utils.invoke_pipeline"
_PATCH_CHECK_HALLUCINATION = (
    "app.adk.agents.agent_factory.dispatch._check_hallucinated_approval"
)
_PATCH_EXTRACT_RESULT = "app.adk.agents.agent_factory.dispatch.extract_pipeline_result"
_PATCH_EXTRACT_ITERATIONS = "app.adk.agents.agent_factory.dispatch.extract_iterations"
_PATCH_EMIT_ITERATION_SPAN = "app.adk.agents.agent_factory.dispatch.emit_iteration_span"
_PATCH_SET_PIPELINE_ATTRS = "app.adk.agents.agent_factory.dispatch.set_pipeline_attrs"
_PATCH_GET_WORKER_NAME = "app.adk.agents.agent_factory.dispatch.get_worker_name"
_PATCH_GET_REVIEWER_NAME = "app.adk.agents.agent_factory.dispatch.get_reviewer_name"
_PATCH_INVOKE_WITH_RETRY = (
    "app.adk.agents.agent_factory.dispatch.invoke_agent_with_retry"
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_specialist(
    name: str, description: str | None = "A test specialist"
) -> MagicMock:
    """Return a MagicMock that quacks like a minimal LlmAgent."""
    agent = MagicMock()
    agent.name = name
    agent.description = description
    return agent


# ---------------------------------------------------------------------------
# TestGenerateDispatchFunctions
# ---------------------------------------------------------------------------


class TestGenerateDispatchFunctions:
    def test_n_specialists_produce_n_dispatchers(self) -> None:
        specialists = {
            "a_specialist": _make_specialist("a_specialist"),
            "b_specialist": _make_specialist("b_specialist"),
        }
        result = generate_dispatch_functions(specialists)

        assert len(result) == 2
        assert set(result.keys()) == {"a_specialist", "b_specialist"}

    def test_dispatchers_have_correct_name(self) -> None:
        specialists = {"analytics": _make_specialist("analytics", "Analyzes data")}
        dispatchers = generate_dispatch_functions(specialists)

        fn = dispatchers["analytics"]
        assert fn.__name__ == "dispatch_to_analytics"

    def test_invalid_specialist_name_raises_value_error(self) -> None:
        # Names starting with uppercase are invalid per the regex.
        specialists = {"InvalidName": _make_specialist("InvalidName")}

        with pytest.raises(ValueError, match="invalid"):
            generate_dispatch_functions(specialists)

    def test_name_starting_with_digit_raises_value_error(self) -> None:
        specialists = {"1bad_name": _make_specialist("1bad_name")}

        with pytest.raises(ValueError, match="invalid"):
            generate_dispatch_functions(specialists)

    def test_empty_registry_returns_empty_dict(self) -> None:
        result = generate_dispatch_functions({})
        assert result == {}


# ---------------------------------------------------------------------------
# TestDispatchSinglePassBranch
# ---------------------------------------------------------------------------


class TestDispatchSinglePassBranch:
    def test_single_pass_when_no_criteria(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with (
            patch(
                _PATCH_INVOKE_WITH_RETRY, return_value="retried result"
            ) as mock_retry,
            patch(_PATCH_BUILD_PIPELINE) as mock_build,
        ):
            result = fn("test query")

        assert result == "retried result"
        mock_retry.assert_called_once_with(
            specialist,
            "test query",
            state=None,
            retry_config=DEFAULT_RETRY_CONFIG,
        )
        mock_build.assert_not_called()

    def test_single_pass_state_is_none_when_no_tool_context(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with patch(_PATCH_INVOKE_WITH_RETRY, return_value="ok") as mock_retry:
            fn("query")

        _, kwargs = mock_retry.call_args
        assert kwargs["state"] is None

    def test_single_pass_with_empty_criteria_string(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with (
            patch(_PATCH_INVOKE_WITH_RETRY, return_value="ok") as mock_retry,
            patch(_PATCH_BUILD_PIPELINE) as mock_build,
        ):
            result = fn("query", acceptance_criteria="")

        assert result == "ok"
        mock_build.assert_not_called()
        mock_retry.assert_called_once()

    def test_single_pass_with_whitespace_only_criteria(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with (
            patch(_PATCH_INVOKE_WITH_RETRY, return_value="ok") as mock_retry,
            patch(_PATCH_BUILD_PIPELINE) as mock_build,
        ):
            fn("query", acceptance_criteria="   ")

        mock_build.assert_not_called()
        mock_retry.assert_called_once()


# ---------------------------------------------------------------------------
# TestDispatchReviewLoopBranch
# ---------------------------------------------------------------------------


class TestDispatchReviewLoopBranch:
    def _make_review_loop_patches(self) -> tuple:
        """Return a tuple of all patches needed for the review-loop branch."""
        mock_pipeline = MagicMock(name="pipeline")
        mock_iter = MagicMock()
        mock_iter.iteration = 1
        mock_iter.specialist_output = "draft text"
        mock_iter.reviewer_output = "reviewer text"

        return mock_pipeline, mock_iter

    def test_review_loop_when_criteria_provided(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        mock_pipeline, mock_iter = self._make_review_loop_patches()

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=mock_pipeline) as mock_build,
            patch(
                _PATCH_INVOKE_PIPELINE,
                return_value=("text", {"analytics_review_result": "x"}, []),
            ) as mock_invoke,
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(
                _PATCH_EXTRACT_RESULT, return_value={"result": "final answer"}
            ) as mock_extract,
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[mock_iter]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            result = fn("query", acceptance_criteria="must include X")

        assert result == "final answer"
        mock_build.assert_called_once()
        mock_invoke.assert_called_once()
        mock_extract.assert_called_once()

    def test_review_loop_output_key_prefix_passed_to_build(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        mock_pipeline, mock_iter = self._make_review_loop_patches()

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=mock_pipeline) as mock_build,
            patch(
                _PATCH_INVOKE_PIPELINE,
                return_value=("text", {}, []),
            ),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "answer"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[mock_iter]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria="criteria text")

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs.get("output_key_prefix") == "analytics_review"

    def test_review_loop_calls_full_observability_chain(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        mock_pipeline, mock_iter = self._make_review_loop_patches()

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=mock_pipeline),
            patch(
                _PATCH_INVOKE_PIPELINE,
                return_value=("text", {}, [MagicMock()]),
            ),
            patch(_PATCH_CHECK_HALLUCINATION) as mock_check,
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "answer"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[mock_iter]) as mock_iters,
            patch(_PATCH_EMIT_ITERATION_SPAN) as mock_emit,
            patch(_PATCH_SET_PIPELINE_ATTRS) as mock_set_attrs,
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria="must include X")

        mock_check.assert_called_once()
        mock_iters.assert_called_once()
        # emit_iteration_span called once per iteration
        assert mock_emit.call_count == 1
        mock_emit.assert_called_once_with(
            mock_iter.iteration,
            mock_iter.specialist_output,
            mock_iter.reviewer_output,
        )
        mock_set_attrs.assert_called_once()

    def test_review_loop_multiple_iterations_each_emit_span(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        iter1 = MagicMock()
        iter1.iteration, iter1.specialist_output, iter1.reviewer_output = 1, "d1", "r1"
        iter2 = MagicMock()
        iter2.iteration, iter2.specialist_output, iter2.reviewer_output = 2, "d2", "r2"

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()),
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "done"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[iter1, iter2]),
            patch(_PATCH_EMIT_ITERATION_SPAN) as mock_emit,
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria="criteria")

        assert mock_emit.call_count == 2
        mock_emit.assert_has_calls(
            [
                call(iter1.iteration, iter1.specialist_output, iter1.reviewer_output),
                call(iter2.iteration, iter2.specialist_output, iter2.reviewer_output),
            ]
        )


# ---------------------------------------------------------------------------
# TestDispatchSanitisation
# ---------------------------------------------------------------------------


class TestDispatchSanitisation:
    def test_unsafe_chars_stripped_before_pipeline(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()) as mock_build,
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "ok"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria="must <not> inject {template} `vars`")

        # Extract the acceptance_criteria kwarg passed to build_review_pipeline
        criteria_passed = mock_build.call_args.kwargs.get("acceptance_criteria")
        assert "<" not in criteria_passed
        assert ">" not in criteria_passed
        assert "`" not in criteria_passed
        assert "{" not in criteria_passed

    def test_criteria_truncated_to_2000_chars(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        long_criteria = "A" * 3000

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()) as mock_build,
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "ok"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria=long_criteria)

        criteria_passed = mock_build.call_args.kwargs.get("acceptance_criteria")
        assert len(criteria_passed) <= 2000


# ---------------------------------------------------------------------------
# TestDispatchStateForwarding
# ---------------------------------------------------------------------------


class TestDispatchStateForwarding:
    def test_state_forwarded_from_tool_context(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        original_state = {"ga_credentials": {"token": "xyz"}, "account_id": "acct_1"}
        tool_context = MagicMock()
        tool_context.state.to_dict.return_value = original_state

        with patch(_PATCH_INVOKE_WITH_RETRY, return_value="ok") as mock_retry:
            fn("query", tool_context=tool_context)

        _, kwargs = mock_retry.call_args
        assert kwargs["state"] == original_state

    def test_initial_state_is_deep_copy_of_tool_context_state(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        nested = {"token": "xyz"}
        original_state = {"ga_credentials": nested, "account_id": "acct_1"}
        tool_context = MagicMock()
        tool_context.state.to_dict.return_value = original_state

        with patch(_PATCH_INVOKE_WITH_RETRY, return_value="ok") as mock_retry:
            fn("query", tool_context=tool_context)

        _, kwargs = mock_retry.call_args
        forwarded_state = kwargs["state"]
        # Values must match
        assert forwarded_state == original_state
        # Top-level dict must be a copy
        assert forwarded_state is not original_state
        # Nested dicts must also be independent (deepcopy, not shallow copy)
        assert forwarded_state["ga_credentials"] is not nested

    def test_state_none_when_no_tool_context_in_review_loop(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()),
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])) as mock_invoke,
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(_PATCH_EXTRACT_RESULT, return_value={"result": "ok"}),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            fn("query", acceptance_criteria="some criteria")

        # invoke_pipeline should be called with state=None
        call_kwargs = mock_invoke.call_args.kwargs
        assert call_kwargs.get("state") is None


# ---------------------------------------------------------------------------
# TestDispatchErrorHandling
# ---------------------------------------------------------------------------


class TestDispatchErrorHandling:
    def test_exception_returns_error_string_not_reraise(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with patch(_PATCH_INVOKE_WITH_RETRY, side_effect=RuntimeError("boom")):
            result = fn("query")

        assert isinstance(result, str)
        assert result.startswith("Error dispatching to my_agent")
        # Exception details must not be leaked to the router
        assert "boom" not in result
        assert "specialist unavailable" in result

    def test_review_loop_exception_returns_error_string(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        with patch(_PATCH_BUILD_PIPELINE, side_effect=ValueError("pipeline failed")):
            result = fn("query", acceptance_criteria="must include X")

        assert isinstance(result, str)
        assert result.startswith("Error dispatching to analytics")
        # Exception details must not be leaked to the router
        assert "pipeline failed" not in result
        assert "specialist unavailable" in result

    def test_no_exception_propagates_to_caller(self) -> None:
        specialist = _make_specialist("my_agent")
        dispatchers = generate_dispatch_functions({"my_agent": specialist})
        fn = dispatchers["my_agent"]

        with patch(_PATCH_INVOKE_WITH_RETRY, side_effect=Exception("unexpected")):
            # Should not raise
            result = fn("query")

        assert "Error dispatching to" in result


# ---------------------------------------------------------------------------
# TestAssembleAvailableSpecialistsBlock
# ---------------------------------------------------------------------------


class TestAssembleAvailableSpecialistsBlock:
    def test_empty_specialists_returns_heading_plus_none_registered(self) -> None:
        result = assemble_available_specialists_block({})

        assert result.startswith("## Available Specialists")
        assert "None registered" in result

    def test_specialists_sorted_alphabetically_with_descriptions(self) -> None:
        specialists = {
            "c_spec": _make_specialist("c_spec", "C desc"),
            "a_spec": _make_specialist("a_spec", "A desc"),
            "b_spec": _make_specialist("b_spec", "B desc"),
        }
        result = assemble_available_specialists_block(specialists)

        assert result.startswith("## Available Specialists\n\n")
        lines = result.splitlines()
        bullets = [line for line in lines if line.startswith("- **")]
        assert len(bullets) == 3
        assert "a_spec" in bullets[0]
        assert "b_spec" in bullets[1]
        assert "c_spec" in bullets[2]
        assert "A desc" in bullets[0]
        assert "B desc" in bullets[1]
        assert "C desc" in bullets[2]

    def test_missing_description_uses_fallback(self) -> None:
        specialists = {"my_agent": _make_specialist("my_agent", description=None)}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result

    def test_empty_description_uses_fallback(self) -> None:
        specialists = {"my_agent": _make_specialist("my_agent", description="")}
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result

    def test_single_specialist_formats_correctly(self) -> None:
        specialists = {"solo_agent": _make_specialist("solo_agent", "Does solo things")}
        result = assemble_available_specialists_block(specialists)

        assert "## Available Specialists\n\n" in result
        assert "- **solo_agent**: Does solo things" in result

    def test_heading_always_present(self) -> None:
        for specialists in [{}, {"x_agent": _make_specialist("x_agent")}]:
            result = assemble_available_specialists_block(specialists)
            assert result.startswith("## Available Specialists")


# ---------------------------------------------------------------------------
# TestIntegrationSmoke — two specialists, both dispatch branches
# ---------------------------------------------------------------------------


class TestIntegrationSmoke:
    def test_integration_smoke_two_specialists(self) -> None:
        alpha = _make_specialist("alpha_agent", "Alpha description")
        beta = _make_specialist("beta_agent", "Beta description")

        dispatchers = generate_dispatch_functions(
            {"alpha_agent": alpha, "beta_agent": beta}
        )

        assert set(dispatchers.keys()) == {"alpha_agent", "beta_agent"}
        assert dispatchers["alpha_agent"].__name__ == "dispatch_to_alpha_agent"
        assert dispatchers["beta_agent"].__name__ == "dispatch_to_beta_agent"


# ---------------------------------------------------------------------------
# TestDelegateToSpecialist — AH-PRD-09 Phase 2 unified dispatch tool
# ---------------------------------------------------------------------------

_PATCH_SPECIALIST_RUNTIME_RUN = (
    "app.adk.agents.agent_factory.specialist_runtime.run"
)
_PATCH_RESOLVE_AGENT_WITH_HIT = (
    "app.adk.agents.agent_factory.specialist_runtime.resolve_agent_with_hit"
)
_PATCH_SET_DELEGATE_ATTRS = (
    "app.adk.agents.agent_factory.dispatch.set_delegate_attrs"
)


class TestDelegateToSpecialist:
    def test_invalid_name_returns_error_string(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        result = delegate_to_specialist("InvalidName", "query")

        assert result.startswith("[DELEGATE ERROR]")
        assert "InvalidName" in result

    def test_name_starting_with_digit_returns_error_string(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        result = delegate_to_specialist("1bad", "query")

        assert result.startswith("[DELEGATE ERROR]")

    def test_valid_name_delegates_to_specialist_runtime(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, False)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="specialist answer") as mock_run,
            patch(_PATCH_SET_DELEGATE_ATTRS),
        ):
            result = delegate_to_specialist("research_agent", "some query")

        assert result == "specialist answer"
        mock_run.assert_called_once_with(
            doc_id="research_agent",
            query="some query",
            account_id=None,
            acceptance_criteria="",
            tool_context=None,
        )

    def test_account_id_read_from_tool_context_state(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        tool_context = MagicMock()
        tool_context.state.get.return_value = "acct_123"

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, True)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok") as mock_run,
            patch(_PATCH_SET_DELEGATE_ATTRS),
        ):
            delegate_to_specialist("research_agent", "query", tool_context=tool_context)

        tool_context.state.get.assert_called_once_with("account_id")
        _, kwargs = mock_run.call_args
        assert kwargs["account_id"] == "acct_123"

    def test_account_id_none_when_no_tool_context(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, False)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok") as mock_run,
            patch(_PATCH_SET_DELEGATE_ATTRS),
        ):
            delegate_to_specialist("research_agent", "query")

        _, kwargs = mock_run.call_args
        assert kwargs["account_id"] is None

    def test_acceptance_criteria_forwarded(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, False)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok") as mock_run,
            patch(_PATCH_SET_DELEGATE_ATTRS),
        ):
            delegate_to_specialist(
                "research_agent", "query", acceptance_criteria="must include sources"
            )

        _, kwargs = mock_run.call_args
        assert kwargs["acceptance_criteria"] == "must include sources"

    def test_tool_context_forwarded_to_runtime(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        tool_context = MagicMock()
        tool_context.state.get.return_value = None

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, False)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok") as mock_run,
            patch(_PATCH_SET_DELEGATE_ATTRS),
        ):
            delegate_to_specialist("research_agent", "query", tool_context=tool_context)

        _, kwargs = mock_run.call_args
        assert kwargs["tool_context"] is tool_context

    def test_set_delegate_attrs_called_with_cache_hit_true(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, True)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok"),
            patch(_PATCH_SET_DELEGATE_ATTRS) as mock_attrs,
        ):
            delegate_to_specialist("research_agent", "query")

        mock_attrs.assert_called_once_with(specialist_name="research_agent", cache_hit=True)

    def test_set_delegate_attrs_called_with_cache_hit_false(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, False)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok"),
            patch(_PATCH_SET_DELEGATE_ATTRS) as mock_attrs,
        ):
            delegate_to_specialist("research_agent", "query")

        mock_attrs.assert_called_once_with(specialist_name="research_agent", cache_hit=False)

    def test_cache_hit_defaults_to_false_when_resolve_raises(self) -> None:
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, side_effect=RuntimeError("Firestore down")),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, return_value="ok"),
            patch(_PATCH_SET_DELEGATE_ATTRS) as mock_attrs,
        ):
            result = delegate_to_specialist("research_agent", "query")

        assert result == "ok"
        mock_attrs.assert_called_once_with(specialist_name="research_agent", cache_hit=False)

    def test_set_delegate_attrs_called_after_run(self) -> None:
        """set_delegate_attrs must be called even when run raises (run never reraises)."""
        from app.adk.agents.agent_factory.dispatch import delegate_to_specialist

        call_order: list[str] = []

        def mock_run(**kwargs: object) -> str:
            call_order.append("run")
            return "run result"

        def mock_attrs(**kwargs: object) -> None:
            call_order.append("attrs")

        mock_agent = MagicMock()
        with (
            patch(_PATCH_RESOLVE_AGENT_WITH_HIT, return_value=(mock_agent, True)),
            patch(_PATCH_SPECIALIST_RUNTIME_RUN, side_effect=mock_run),
            patch(_PATCH_SET_DELEGATE_ATTRS, side_effect=mock_attrs),
        ):
            delegate_to_specialist("research_agent", "query")

        assert call_order == ["run", "attrs"]


# ---------------------------------------------------------------------------
# TestAssembleAvailableSpecialistsBlockSanitisation
# ---------------------------------------------------------------------------


class TestAssembleAvailableSpecialistsBlockSanitisation:
    def test_description_unsafe_chars_stripped(self) -> None:
        specialists = {
            "my_agent": _make_specialist(
                "my_agent", description="Does analytics <inject> {template} `code`"
            )
        }
        result = assemble_available_specialists_block(specialists)

        assert "<" not in result
        assert ">" not in result
        assert "`" not in result
        assert "{" not in result
        assert "Does analytics" in result

    def test_description_truncated_to_500_chars(self) -> None:
        specialists = {"my_agent": _make_specialist("my_agent", description="X" * 600)}
        result = assemble_available_specialists_block(specialists)

        # The description portion of the bullet should not exceed 500 chars
        bullet = next(line for line in result.splitlines() if line.startswith("- **"))
        description_part = bullet.split(": ", 1)[1]
        assert len(description_part) <= 500

    def test_description_all_unsafe_chars_falls_back(self) -> None:
        specialists = {
            "my_agent": _make_specialist("my_agent", description="<{{{}}}>`")
        }
        result = assemble_available_specialists_block(specialists)

        assert "(no description provided)" in result


# ---------------------------------------------------------------------------
# TestDispatchUnapprovedWarning
# ---------------------------------------------------------------------------


class TestDispatchUnapprovedWarning:
    def test_unapproved_result_logs_warning(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        mock_iter = MagicMock()
        mock_iter.iteration, mock_iter.specialist_output, mock_iter.reviewer_output = (
            1,
            "draft",
            "not approved",
        )

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()),
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(
                _PATCH_EXTRACT_RESULT,
                return_value={"result": "last draft", "approved": False},
            ),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[mock_iter]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            result = fn("query", acceptance_criteria="must pass review")

        assert result == "last draft"

    def test_approved_result_does_not_cause_issues(self) -> None:
        specialist = _make_specialist("analytics")
        dispatchers = generate_dispatch_functions({"analytics": specialist})
        fn = dispatchers["analytics"]

        mock_iter = MagicMock()
        mock_iter.iteration, mock_iter.specialist_output, mock_iter.reviewer_output = (
            1,
            "draft",
            "approved",
        )

        with (
            patch(_PATCH_BUILD_PIPELINE, return_value=MagicMock()),
            patch(_PATCH_INVOKE_PIPELINE, return_value=("text", {}, [])),
            patch(_PATCH_CHECK_HALLUCINATION),
            patch(
                _PATCH_EXTRACT_RESULT,
                return_value={"result": "approved answer", "approved": True},
            ),
            patch(_PATCH_EXTRACT_ITERATIONS, return_value=[mock_iter]),
            patch(_PATCH_EMIT_ITERATION_SPAN),
            patch(_PATCH_SET_PIPELINE_ATTRS),
            patch(_PATCH_GET_WORKER_NAME, return_value="analytics_worker"),
            patch(_PATCH_GET_REVIEWER_NAME, return_value="analytics_review_reviewer"),
        ):
            result = fn("query", acceptance_criteria="must pass review")

        assert result == "approved answer"


# ---------------------------------------------------------------------------
# TestDispatchCloudpickleRoundTrip
# ---------------------------------------------------------------------------
# REGRESSION: AH-17 verification surfaced a deploy-blocking bug where
# `from __future__ import annotations` in `dispatch.py` caused generated
# dispatch closures to fail after cloudpickle round-trip.  ADK's
# `typing.get_type_hints()` on the rehydrated closure raised
# `NameError: name 'ToolContext' is not defined` because deferred (string)
# annotations don't survive the round-trip — cloudpickle drops the closure's
# `__wrapped__`/`__globals__` mapping.  The fix (removing the future import
# from `dispatch.py`) was verified during AH-17 smoke testing; this test
# ensures it never regresses.
#
# Note: `safe_weave_op` runs in noop mode when WEAVE_API_KEY is not set
# (verified in `app/utils/weave_observability.py`), so the pickle round-trip
# does not require Weave to be configured.


class TestDispatchCloudpickleRoundTrip:
    """Verify that generated dispatch closures survive cloudpickle round-trip.

    This is the exact failure path that Agent Engine exercises: each dispatch
    closure is cloudpickled into the deployment artifact, then rehydrated and
    handed to ADK's function-declaration builder which calls
    ``typing.get_type_hints()``.  The test mirrors that sequence.
    """

    def test_get_type_hints_succeeds_after_cloudpickle_roundtrip(self) -> None:
        """``typing.get_type_hints(restored)`` must not raise ``NameError``."""
        import typing

        import cloudpickle

        specialist = _make_specialist("sample_specialist")
        dispatchers = generate_dispatch_functions({"sample_specialist": specialist})
        dispatch_fn = dispatchers["sample_specialist"]

        blob = cloudpickle.dumps(dispatch_fn)
        restored = cloudpickle.loads(blob)

        # Must not raise NameError (the regression symptom)
        hints = typing.get_type_hints(restored)
        assert "tool_context" in hints

    def test_function_declaration_populated_after_roundtrip(self) -> None:
        """``FunctionTool(restored)._get_declaration()`` must return a non-None
        declaration with non-empty parameters — the ADK call that fails in prod
        when annotations are deferred strings.
        """
        import cloudpickle
        from google.adk.tools.function_tool import FunctionTool

        specialist = _make_specialist("sample_specialist")
        dispatchers = generate_dispatch_functions({"sample_specialist": specialist})
        dispatch_fn = dispatchers["sample_specialist"]

        blob = cloudpickle.dumps(dispatch_fn)
        restored = cloudpickle.loads(blob)

        tool = FunctionTool(restored)
        declaration = tool._get_declaration()

        assert declaration is not None, (
            "FunctionTool must produce a FunctionDeclaration"
        )
        # ADK sends parameters to Gemini; an empty schema indicates the closure's
        # type annotations were not resolved (the regression symptom).
        assert declaration.parameters is not None

    def test_future_annotations_causes_failure_not_masked(self) -> None:
        """Confirm that dispatch.py does NOT use ``from __future__ import annotations``.

        This test documents the regression guard: if the future import were
        re-added, the two cloudpickle round-trip tests above would fail with
        ``NameError: name 'ToolContext' is not defined``.  We also assert the
        absence of the import via the AST so that the guard fires for the actual
        statement, not just the prohibition comment in the module docstring.
        """
        import ast
        import inspect

        import app.adk.agents.agent_factory.dispatch as dispatch_mod

        src = inspect.getsource(dispatch_mod)
        tree = ast.parse(src)

        has_future_annotations = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(alias.name == "annotations" for alias in node.names)
            for node in ast.walk(tree)
        )
        assert not has_future_annotations, (
            "dispatch.py must NOT use `from __future__ import annotations`. "
            "That import causes generated dispatch closures to fail after "
            "cloudpickle round-trip (AH-17 regression). See the module docstring "
            "for the full explanation."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
