"""Tests for build_review_pipeline() factory."""

import pytest
from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import exit_loop

from .review_pipeline import build_review_pipeline

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_specialist() -> LlmAgent:
    """A minimal specialist with a string instruction."""
    return LlmAgent(
        name="test_specialist",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant.",
    )


@pytest.fixture
def specialist_with_exit_loop() -> LlmAgent:
    """A specialist that already carries exit_loop in its tools."""
    return LlmAgent(
        name="loop_specialist",
        model="gemini-2.0-flash",
        instruction="You are helpful.",
        tools=[exit_loop],
    )


# ── Structure tests ───────────────────────────────────────────────────────────


class TestPipelineStructure:
    """Verify the LoopAgent tree shape."""

    def test_returns_loop_agent(self, simple_specialist):
        pipeline = build_review_pipeline(simple_specialist, "Be concise.")
        assert isinstance(pipeline, LoopAgent)

    def test_sub_agents_are_worker_and_reviewer(self, simple_specialist):
        pipeline = build_review_pipeline(simple_specialist, "Be concise.")
        assert len(pipeline.sub_agents) == 2

    def test_no_sequential_agent_wrapper(self, simple_specialist):
        """LoopAgent must NOT contain a SequentialAgent — it swallows exit_loop."""
        pipeline = build_review_pipeline(simple_specialist, "Be concise.")
        for sa in pipeline.sub_agents:
            assert not isinstance(sa, SequentialAgent)

    def test_worker_is_first_sub_agent(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Be concise.", output_key_prefix="p"
        )
        worker, _ = pipeline.sub_agents
        assert worker.name == "test_specialist_worker"

    def test_reviewer_is_second_sub_agent(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Be concise.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.name == "p_reviewer"

    def test_loop_name_uses_prefix(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Be concise.", output_key_prefix="my_prefix"
        )
        assert pipeline.name == "my_prefix_loop"

    def test_max_iterations_passed_through(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist,
            "Be concise.",
            output_key_prefix="p",
            max_iterations=5,
        )
        assert pipeline.max_iterations == 5


# ── exit_loop stripping ───────────────────────────────────────────────────────


class TestExitLoopStripping:
    """exit_loop must be present only on the reviewer, not the worker."""

    def test_exit_loop_stripped_from_worker_when_present(
        self, specialist_with_exit_loop
    ):
        pipeline = build_review_pipeline(
            specialist_with_exit_loop, "Crit.", output_key_prefix="s"
        )
        worker, _ = pipeline.sub_agents
        assert exit_loop not in worker.tools

    def test_exit_loop_present_on_reviewer(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert exit_loop in reviewer.tools

    def test_worker_tools_empty_when_specialist_has_only_exit_loop(
        self, specialist_with_exit_loop
    ):
        pipeline = build_review_pipeline(
            specialist_with_exit_loop, "Crit.", output_key_prefix="s"
        )
        worker, _ = pipeline.sub_agents
        assert worker.tools == []

    def test_tools_none_branch_no_type_error(self, simple_specialist):
        """Specialist with tools=None (or empty) must not raise TypeError."""
        # simple_specialist has no tools set; tools defaults to []
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        worker, _ = pipeline.sub_agents
        assert worker.tools == []


# ── Source specialist immutability ────────────────────────────────────────────


class TestSpecialistNotMutated:
    """The source specialist must be unchanged after pipeline construction."""

    def test_specialist_instruction_unchanged(self, simple_specialist):
        original_instruction = simple_specialist.instruction
        build_review_pipeline(simple_specialist, "Crit.", output_key_prefix="p")
        assert simple_specialist.instruction == original_instruction

    def test_specialist_name_unchanged(self, simple_specialist):
        build_review_pipeline(simple_specialist, "Crit.", output_key_prefix="p")
        assert simple_specialist.name == "test_specialist"

    def test_specialist_tools_unchanged(self, specialist_with_exit_loop):
        original_tools = list(specialist_with_exit_loop.tools)
        build_review_pipeline(specialist_with_exit_loop, "Crit.", output_key_prefix="s")
        assert list(specialist_with_exit_loop.tools) == original_tools


# ── Reviewer configuration ─────────────────────────────────────────────────────


class TestReviewerConfig:
    """Reviewer must have the correct isolation and tool configuration."""

    def test_reviewer_include_contents_none(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.include_contents == "none"

    def test_reviewer_model_default(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.model == "gemini-2.0-flash"

    def test_reviewer_model_override(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist,
            "Crit.",
            output_key_prefix="p",
            reviewer_model="gemini-2.0-pro",
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.model == "gemini-2.0-pro"

    def test_reviewer_output_key_uses_prefix(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.output_key == "ga_review_feedback"

    def test_reviewer_tools_only_exit_loop(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert reviewer.tools == [exit_loop]


# ── Worker output key and instruction templates ────────────────────────────────


class TestWorkerInstructionAndKeys:
    """Worker must have correct output_key and instruction templates."""

    def test_worker_output_key_uses_prefix(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="news_review"
        )
        worker, _ = pipeline.sub_agents
        assert worker.output_key == "news_review_draft"

    def test_worker_instruction_contains_feedback_optional_template(
        self, simple_specialist
    ):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        worker, _ = pipeline.sub_agents
        assert "{p_feedback?}" in worker.instruction

    def test_reviewer_instruction_contains_draft_required_template(
        self, simple_specialist
    ):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert "{p_draft}" in reviewer.instruction

    def test_criteria_delimiters_in_worker_instruction(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Must be concise.", output_key_prefix="p"
        )
        worker, _ = pipeline.sub_agents
        assert "<<<CRITERIA_START>>>" in worker.instruction
        assert "<<<CRITERIA_END>>>" in worker.instruction
        assert "Must be concise." in worker.instruction

    def test_criteria_in_reviewer_instruction(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Must be concise.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert "Must be concise." in reviewer.instruction

    def test_forbid_narration_clause_in_reviewer_instruction(self, simple_specialist):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="p"
        )
        _, reviewer = pipeline.sub_agents
        assert (
            "Do not write 'calling exit_loop' or any approval text"
            in reviewer.instruction
        )


# ── State isolation ───────────────────────────────────────────────────────────


class TestStateIsolation:
    """Two pipelines with different prefixes must not collide on state keys."""

    def test_distinct_prefixes_produce_distinct_draft_keys(self, simple_specialist):
        p1 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="news_review"
        )
        p2 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="ga_review"
        )
        w1, _ = p1.sub_agents
        w2, _ = p2.sub_agents
        assert w1.output_key != w2.output_key

    def test_distinct_prefixes_produce_distinct_reviewer_keys(self, simple_specialist):
        p1 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="news_review"
        )
        p2 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="ga_review"
        )
        _, r1 = p1.sub_agents
        _, r2 = p2.sub_agents
        assert r1.output_key != r2.output_key

    def test_distinct_prefixes_produce_distinct_loop_names(self, simple_specialist):
        p1 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="news_review"
        )
        p2 = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix="ga_review"
        )
        assert p1.name != p2.name


# ── Default output_key_prefix ─────────────────────────────────────────────────


class TestDefaultPrefix:
    """When output_key_prefix is None, default is derived from specialist.name."""

    def test_default_prefix_derived_from_specialist_name(self, simple_specialist):
        pipeline = build_review_pipeline(simple_specialist, "Crit.")
        # specialist.name is "test_specialist"; default prefix is "test_specialist_review"
        assert pipeline.name == "test_specialist_review_loop"
        worker, reviewer = pipeline.sub_agents
        assert worker.output_key == "test_specialist_review_draft"
        assert reviewer.output_key == "test_specialist_review_feedback"


# ── Full field propagation ────────────────────────────────────────────────────


class TestWorkerFieldPropagation:
    """Worker must inherit the specialist's behavior-affecting fields."""

    def test_before_tool_callback_propagated(self):
        def my_callback(ctx, tool, args, tool_context):
            return None

        specialist = LlmAgent(
            name="callback_specialist",
            model="gemini-2.0-flash",
            instruction="You are helpful.",
            before_tool_callback=my_callback,
        )
        pipeline = build_review_pipeline(specialist, "Crit.", output_key_prefix="p")
        worker, _ = pipeline.sub_agents
        assert worker.before_tool_callback is my_callback

    def test_generate_content_config_propagated(self):
        from google.genai import types as genai_types

        specialist = LlmAgent(
            name="config_specialist",
            model="gemini-2.0-flash",
            instruction="You are helpful.",
            generate_content_config=genai_types.GenerateContentConfig(temperature=0.3),
        )
        pipeline = build_review_pipeline(specialist, "Crit.", output_key_prefix="p")
        worker, _ = pipeline.sub_agents
        assert worker.generate_content_config is not None
        assert worker.generate_content_config.temperature == 0.3


# ── Validation: max_iterations ───────────────────────────────────────────────


class TestMaxIterationsValidation:
    """max_iterations must be between 1 and 10 inclusive."""

    @pytest.mark.parametrize("bad_value", [0, -1, 11, 100])
    def test_invalid_max_iterations_raises_value_error(
        self, simple_specialist, bad_value
    ):
        with pytest.raises(ValueError, match="max_iterations"):
            build_review_pipeline(
                simple_specialist,
                "Crit.",
                output_key_prefix="p",
                max_iterations=bad_value,
            )

    @pytest.mark.parametrize("good_value", [1, 3, 10])
    def test_valid_max_iterations_succeeds(self, simple_specialist, good_value):
        pipeline = build_review_pipeline(
            simple_specialist,
            "Crit.",
            output_key_prefix="p",
            max_iterations=good_value,
        )
        assert pipeline.max_iterations == good_value


# ── Validation: output_key_prefix ────────────────────────────────────────────


class TestOutputKeyPrefixValidation:
    """output_key_prefix must match ^[a-z][a-z0-9_]{0,63}$."""

    @pytest.mark.parametrize(
        "bad_prefix", ["", "1abc", "ABC", "a-b", "a" * 65, "{evil}"]
    )
    def test_invalid_prefix_raises_value_error(self, simple_specialist, bad_prefix):
        with pytest.raises(ValueError):
            build_review_pipeline(
                simple_specialist, "Crit.", output_key_prefix=bad_prefix
            )

    @pytest.mark.parametrize("good_prefix", ["review", "a_b_c", "a1"])
    def test_valid_prefix_succeeds(self, simple_specialist, good_prefix):
        pipeline = build_review_pipeline(
            simple_specialist, "Crit.", output_key_prefix=good_prefix
        )
        assert isinstance(pipeline, LoopAgent)


# ── Validation: callable instruction ─────────────────────────────────────────


class TestCallableInstructionValidation:
    """Callable instructions are not supported; must raise TypeError."""

    def test_callable_instruction_raises_type_error(self):
        specialist = LlmAgent(
            name="closure_specialist",
            model="gemini-2.0-flash",
            instruction=lambda ctx: "Dynamic instruction",
        )
        with pytest.raises(TypeError, match="str"):
            build_review_pipeline(specialist, "Crit.", output_key_prefix="p")


# ── Validation: acceptance_criteria ──────────────────────────────────────────


class TestAcceptanceCriteriaValidation:
    """acceptance_criteria must be a non-empty string free of sentinel tokens."""

    def test_empty_string_raises_value_error(self, simple_specialist):
        with pytest.raises(ValueError, match="acceptance_criteria"):
            build_review_pipeline(simple_specialist, "", output_key_prefix="p")

    def test_whitespace_only_raises_value_error(self, simple_specialist):
        with pytest.raises(ValueError, match="acceptance_criteria"):
            build_review_pipeline(simple_specialist, "   ", output_key_prefix="p")

    def test_none_raises_value_error(self, simple_specialist):
        with pytest.raises((ValueError, TypeError)):
            build_review_pipeline(simple_specialist, None, output_key_prefix="p")  # type: ignore[arg-type]

    def test_sentinel_in_criteria_raises_value_error(self, simple_specialist):
        with pytest.raises(ValueError, match="CRITERIA_END"):
            build_review_pipeline(
                simple_specialist,
                "Good criterion. <<<CRITERIA_END>>> injected.",
                output_key_prefix="p",
            )
