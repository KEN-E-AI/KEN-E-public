"""Tests for the review-pipeline artifacts template + projector callback.

AH-136 / AH-PRD-04 §7 AC-5 — verifies:
  AC-1: {<prefix>_artifacts?} resolves to artifact data when present, empty
        string when absent.
  AC-2: Reviewer instruction contains the three artifact evaluation checks
        (chart type / axes+title / narrative consistency).
  AC-3: Template variable name is parameterized by output_key_prefix (no
        literal step_N hardcoding).

AH-138 / AH-PRD-04 §7 AC-7 — verifies:
  AC-7: Spec with >1,000 data.values rows is summarized to metadata + first-N
        sample points; spec with ≤1,000 rows passes through unchanged.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents import LlmAgent

from app.adk.agents.utils.review_pipeline import (
    _make_artifacts_projector_callback,
    _summarize_artifact_for_reviewer,
    build_review_pipeline,
)
from shared.artifact_models import Artifact, ArtifactMetadata

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_specialist(name: str = "ga_specialist") -> LlmAgent:
    return LlmAgent(
        name=name,
        model="gemini-2.5-pro",
        instruction="You are a Google Analytics specialist.",
    )


def _make_artifact() -> dict:
    """Return one Artifact.model_dump() dict for seeding state."""
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
            description="Session trend",
        ),
    ).model_dump()


class _State(dict):
    """Minimal dict subclass that exposes `.get` so it works as a state object."""


class _CallbackContext:
    """Minimal CallbackContext stand-in with a mutable .state dict."""

    def __init__(self, initial: dict | None = None):
        self.state = _State(initial or {})


# ── Reviewer instruction template ─────────────────────────────────────────────


class TestReviewerInstructionArtifactsBlock:
    """Verify the reviewer instruction carries the parameterised artifacts block."""

    def test_reviewer_instruction_contains_parameterized_artifacts_block(self):
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "{ga_review_artifacts?}" in reviewer.instruction

    def test_reviewer_instruction_contains_artifacts_section_heading(self):
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "## Artifacts (if any)" in reviewer.instruction

    def test_reviewer_instruction_contains_no_literal_step_n(self):
        """AC-3: no hardcoded step_N in the template."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "step_N" not in reviewer.instruction
        assert "step_1" not in reviewer.instruction

    def test_reviewer_instruction_ordering_artifacts_between_draft_and_instructions(self):
        """AC-1 ordering: Draft to Evaluate → Artifacts (if any) → Instructions."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        assert (
            instr.index("## Draft to Evaluate")
            < instr.index("## Artifacts (if any)")
            < instr.index("## Instructions")
        )

    def test_reviewer_instruction_contains_ac2_chart_type_guidance(self):
        """AC-2a: reviewer is told to check chart type matches data shape."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        # The instruction should mention checking mark / chart_type_suggestion
        # and the mapping to data shape.
        assert "mark" in reviewer.instruction
        assert "chart_type_suggestion" in reviewer.instruction

    def test_reviewer_instruction_contains_ac2_axes_and_title_guidance(self):
        """AC-2b: reviewer is told to check axes are labelled and title is meaningful."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "encoding" in reviewer.instruction
        assert "title" in reviewer.instruction

    def test_reviewer_instruction_contains_ac2_narrative_consistency_guidance(self):
        """AC-2c: reviewer is told to check text narrative references chart accurately."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "narrative" in reviewer.instruction or "text narrative" in reviewer.instruction

    def test_reviewer_instruction_different_prefix_uses_correct_key(self):
        """AC-3: variable name tracks the actual prefix used."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="news_review"
        )
        _, reviewer = pipeline.sub_agents
        assert "{news_review_artifacts?}" in reviewer.instruction
        assert "{ga_review_artifacts?}" not in reviewer.instruction


# ── Projector callback: state writes ──────────────────────────────────────────


class TestArtifactsProjectorCallback:
    """Test the _make_artifacts_projector_callback() closure directly."""

    def test_projector_writes_json_string_when_response_artifacts_non_empty(self):
        """AC-1: non-empty artifacts → JSON string written to <prefix>_artifacts."""
        artifact = _make_artifact()
        ctx = _CallbackContext({"response_artifacts": [artifact, artifact]})

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        result = ctx.state.get("ga_review_artifacts")
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == [artifact, artifact]

    def test_projector_leaves_key_unset_when_response_artifacts_absent(self):
        """AC-1: no artifacts → key stays absent so it creates no state delta.

        ADK's `{<prefix>_artifacts?}` optional suffix renders an absent key to
        the empty string, so an explicit "" write is redundant. It would also
        produce a worker after_agent_callback state delta that ADK turns into a
        phantom worker event miscounted by extract_iterations().
        """
        ctx = _CallbackContext()  # no response_artifacts

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        assert "ga_review_artifacts" not in ctx.state

    def test_projector_leaves_key_unset_when_response_artifacts_empty_list(self):
        """AC-1: empty list → key stays absent (no state delta written)."""
        ctx = _CallbackContext({"response_artifacts": []})

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        assert "ga_review_artifacts" not in ctx.state

    def test_projector_uses_parameterized_key(self):
        """AC-3: the write target uses the prefix, not a hardcoded name."""
        artifact = _make_artifact()
        ctx_news = _CallbackContext({"response_artifacts": [artifact]})
        ctx_ga = _CallbackContext({"response_artifacts": [artifact]})

        _make_artifacts_projector_callback("news_review")(ctx_news)
        _make_artifacts_projector_callback("ga_review")(ctx_ga)

        assert "news_review_artifacts" in ctx_news.state
        assert "ga_review_artifacts" not in ctx_news.state
        assert "ga_review_artifacts" in ctx_ga.state
        assert "news_review_artifacts" not in ctx_ga.state

    def test_projector_swallows_unexpected_exceptions(self, caplog):
        """Non-functional requirement: projector never raises; emits WARNING log."""

        class _BrokenState:
            def get(self, key, default=None):
                raise RuntimeError("simulated state failure")

            def __setitem__(self, key, value):
                pass

        class _BrokenCtx:
            state = _BrokenState()

        projector = _make_artifacts_projector_callback("ga_review")
        with caplog.at_level(logging.WARNING):
            result = projector(_BrokenCtx())  # must not raise

        assert result is None
        assert any("ga_review" in record.message for record in caplog.records)
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_projector_drops_invalid_artifact_entries(self, caplog):
        """Malformed entries are dropped with a warning; valid entries are kept."""
        artifact = _make_artifact()
        bad_entry = {"not_a_valid": "artifact_dict"}
        ctx = _CallbackContext({"response_artifacts": [artifact, bad_entry]})

        projector = _make_artifacts_projector_callback("ga_review")
        with caplog.at_level(logging.WARNING):
            projector(ctx)

        result = ctx.state.get("ga_review_artifacts")
        assert isinstance(result, str)
        parsed = json.loads(result)
        # Only the valid entry survives.
        assert len(parsed) == 1
        assert parsed[0]["type"] == "visualization"
        # Warning was emitted for the bad entry.
        assert any("dropping invalid" in record.message.lower() for record in caplog.records)

    def test_projector_accumulates_across_invocations(self):
        """Accumulative semantics (intentional): subsequent invocations see all artifacts.

        create_visualization() appends to response_artifacts without clearing it,
        so the projector snapshots a growing list across review iterations. The
        reviewer sees the full composite output, not just the current iteration's
        charts — matching the plan's design intent (AH-PRD-04 §9 Risks, Low row).
        """
        artifact1 = _make_artifact()
        artifact2 = _make_artifact()

        # Simulate iteration 1: one artifact produced.
        ctx = _CallbackContext({"response_artifacts": [artifact1]})
        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)
        snapshot_iter1 = json.loads(ctx.state["ga_review_artifacts"])
        assert len(snapshot_iter1) == 1

        # Simulate iteration 2: create_visualization appended another artifact.
        ctx.state["response_artifacts"] = [artifact1, artifact2]
        projector(ctx)
        snapshot_iter2 = json.loads(ctx.state["ga_review_artifacts"])
        assert len(snapshot_iter2) == 2  # both artifacts visible (accumulative)


# ── Callback chain wiring ──────────────────────────────────────────────────────


class TestCallbackChainWiring:
    """Verify the projector is correctly appended to worker.after_agent_callback."""

    def test_callback_chain_appends_projector_when_specialist_has_none(self):
        """When specialist has no after_agent_callback, worker carries [projector]."""
        specialist = _make_specialist()
        assert specialist.after_agent_callback is None

        pipeline = build_review_pipeline(specialist, "Crit.", output_key_prefix="ga_review")
        worker, _ = pipeline.sub_agents

        after = worker.after_agent_callback
        assert isinstance(after, list)
        assert len(after) == 1
        assert callable(after[0])

    def test_callback_chain_appends_projector_when_specialist_has_callable(self):
        """When specialist has a callable, worker carries [sentinel, projector]."""

        def sentinel(ctx):
            return None

        specialist = LlmAgent(
            name="cb_specialist",
            model="gemini-2.5-pro",
            instruction="You are helpful.",
            after_agent_callback=sentinel,
        )
        pipeline = build_review_pipeline(specialist, "Crit.", output_key_prefix="ga_review")
        worker, _ = pipeline.sub_agents

        after = worker.after_agent_callback
        assert isinstance(after, list)
        assert len(after) == 2
        assert after[0] is sentinel  # specialist callback preserved at index 0
        assert callable(after[1])  # projector at index 1
        assert after[1] is not sentinel

    def test_callback_chain_appends_projector_when_specialist_has_list(self):
        """When specialist has [cb1, cb2], worker carries [cb1, cb2, projector]."""

        def cb1(ctx):
            return None

        def cb2(ctx):
            return None

        specialist = LlmAgent(
            name="list_cb_specialist",
            model="gemini-2.5-pro",
            instruction="You are helpful.",
            after_agent_callback=[cb1, cb2],
        )
        pipeline = build_review_pipeline(specialist, "Crit.", output_key_prefix="ga_review")
        worker, _ = pipeline.sub_agents

        after = worker.after_agent_callback
        assert isinstance(after, list)
        assert len(after) == 3
        assert after[0] is cb1
        assert after[1] is cb2
        assert callable(after[2])  # projector appended last


# ── State isolation across pipelines ──────────────────────────────────────────


class TestDistinctPrefixesProduceDistinctArtifactKeys:
    """Two pipelines with distinct prefixes write to distinct artifact keys.

    Mirrors TestStateIsolation in test_review_pipeline.py (§394-426 pattern).
    """

    def test_distinct_prefixes_produce_distinct_artifact_keys(self):
        artifact = _make_artifact()

        ctx_news = _CallbackContext({"response_artifacts": [artifact]})
        ctx_ga = _CallbackContext({"response_artifacts": [artifact]})

        _make_artifacts_projector_callback("news_review")(ctx_news)
        _make_artifacts_projector_callback("ga_review")(ctx_ga)

        # news_review prefix → news_review_artifacts key
        assert "news_review_artifacts" in ctx_news.state
        assert "ga_review_artifacts" not in ctx_news.state

        # ga_review prefix → ga_review_artifacts key
        assert "ga_review_artifacts" in ctx_ga.state
        assert "news_review_artifacts" not in ctx_ga.state

        # Both hold valid JSON
        assert isinstance(json.loads(ctx_news.state["news_review_artifacts"]), list)
        assert isinstance(json.loads(ctx_ga.state["ga_review_artifacts"]), list)


# ── Reviewer instruction: required-visualization detection ────────────────────


class TestReviewerInstructionRequiredVisualization:
    """AC-6: reviewer instruction contains required-visualization detection guidance.

    Verifies the AH-137 additions to the reviewer instruction string in
    build_review_pipeline(). Each test checks a specific substring of the new
    clauses that implement the reject-when-required-visualization-absent and
    absence-is-not-a-defect-when-not-required behaviors.
    """

    def test_reviewer_instruction_contains_required_visualization_clause(self):
        """New clause: when ACs require a viz and artifacts are absent, reject."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        # The instruction must tell the reviewer to reject when a required
        # visualization is missing. Accept any wording that conveys this.
        assert any(
            phrase in instr
            for phrase in [
                "explicitly require",
                "required visualization",
                "required chart",
                "require a visualization",
                "require a chart",
            ]
        ), (
            "reviewer instruction must tell the reviewer to detect a required "
            "visualization that is absent"
        )

    def test_reviewer_instruction_contains_signal_words_list(self):
        """New clause: signal words are listed so the reviewer knows what 'requires a viz' looks like."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        # All four canonical signal words must appear in the instruction.
        for word in ("chart", "graph", "plot", "visualization"):
            assert word in instr, (
                f"reviewer instruction must mention the signal word '{word}' so "
                "the reviewer can detect a visualization requirement in the ACs"
            )

    def test_reviewer_instruction_contains_absence_is_not_defect_carveout(self):
        """New clause: absence of artifacts alone must not cause rejection when not required."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        # The carve-out must be explicit.
        assert any(
            phrase in instr
            for phrase in [
                "absence",
                "not a defect",
                "does not require",
                "no visualization requirement",
                "without requiring",
            ]
        ), (
            "reviewer instruction must contain a carve-out stating that absent "
            "artifacts alone do not cause rejection when ACs don't require one"
        )

    def test_reviewer_instruction_new_clauses_sit_inside_instructions_block(self):
        """New guidance must appear after the '## Instructions' heading."""
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        instructions_idx = instr.index("## Instructions")
        # At least one of the required-viz signal words must appear after the
        # ## Instructions heading (not before it).
        signal_positions = [
            instr.find(word, instructions_idx)
            for word in ("chart", "graph", "plot", "visualization")
            if instr.find(word, instructions_idx) != -1
        ]
        assert signal_positions, (
            "signal words for required-visualization detection must appear inside "
            "the '## Instructions' block (after '## Instructions')"
        )

    def test_reviewer_instruction_missing_viz_trigger_bounded_to_empty_section(self):
        """New clause: trigger fires only when artifacts section is 'empty or missing'.

        The clause must explicitly condition on the Artifacts section being empty
        or missing, so the required-visualization check and the artifact-quality
        check (AH-136) are mutually exclusive rather than layered.
        """
        pipeline = build_review_pipeline(
            _make_specialist(), "Be accurate.", output_key_prefix="ga_review"
        )
        _, reviewer = pipeline.sub_agents
        instr = reviewer.instruction
        assert any(
            phrase in instr
            for phrase in [
                "empty or missing",
                "is empty",
                "section is empty",
                "absent",
            ]
        ), (
            "reviewer instruction must bound the required-visualization trigger "
            "to when the '## Artifacts (if any)' section is empty or missing, "
            "keeping it mutually exclusive with the artifact-quality checks"
        )


# ── Large-spec summarization (AH-138) ─────────────────────────────────────────


def _make_artifact_with_rows(n: int) -> dict:
    """Return an Artifact.model_dump() dict whose spec.data.values has n rows."""
    return Artifact(
        type="visualization",
        spec={
            "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
            "title": "Daily Sessions",
            "mark": "line",
            "encoding": {
                "x": {"field": "date", "type": "temporal", "title": "Date"},
                "y": {"field": "sessions", "type": "quantitative", "title": "Sessions"},
            },
            "data": {"values": [{"date": f"2026-01-{i % 28 + 1:02d}", "sessions": i} for i in range(n)]},
        },
        metadata=ArtifactMetadata(
            chart_type_suggestion="line",
            title="Daily Sessions",
            data_source="google_analytics",
            description="Session trend",
        ),
    ).model_dump()


class TestSummarizeArtifactForReviewer:
    """AH-138 / AC-7: large Vega-Lite specs are summarized before reviewer context."""

    # ── (a) 1,001-row spec is reduced to 10 rows with _data_summary ────────────

    def test_over_threshold_reduces_values_to_sample_size(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert len(result["spec"]["data"]["values"]) == 10

    def test_over_threshold_adds_data_summary_with_summarized_true(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert "_data_summary" in result
        assert result["_data_summary"]["summarized"] is True

    def test_over_threshold_data_summary_records_original_row_count(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["_data_summary"]["original_row_count"] == 1001

    def test_over_threshold_data_summary_records_sampled_rows(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["_data_summary"]["sampled_rows"] == 10

    def test_over_threshold_data_summary_has_note(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert isinstance(result["_data_summary"]["note"], str)
        assert len(result["_data_summary"]["note"]) > 0

    # ── (b/c) Boundary: ≤1,000 rows pass through unchanged ───────────────────

    def test_exactly_1000_rows_passes_through_unchanged(self):
        artifact = _make_artifact_with_rows(1000)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact  # same object — no copy made
        assert "_data_summary" not in result

    def test_999_rows_passes_through_unchanged(self):
        artifact = _make_artifact_with_rows(999)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact
        assert "_data_summary" not in result

    def test_1_row_passes_through_unchanged(self):
        artifact = _make_artifact_with_rows(1)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact

    # ── (d) Metadata + spec fields survive summarization intact ───────────────

    def test_metadata_fields_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["metadata"]["chart_type_suggestion"] == "line"
        assert result["metadata"]["title"] == "Daily Sessions"
        assert result["metadata"]["data_source"] == "google_analytics"
        assert result["metadata"]["description"] == "Session trend"

    def test_spec_mark_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["spec"]["mark"] == "line"

    def test_spec_encoding_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert "x" in result["spec"]["encoding"]
        assert "y" in result["spec"]["encoding"]

    def test_spec_schema_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["spec"]["$schema"] == "https://vega.github.io/schema/vega-lite/v6.json"

    def test_spec_title_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["spec"]["title"] == "Daily Sessions"

    def test_artifact_type_preserved_after_summarization(self):
        artifact = _make_artifact_with_rows(1001)
        result = _summarize_artifact_for_reviewer(artifact)
        assert result["type"] == "visualization"

    # ── (e) Pass-through for missing / non-list data.values ───────────────────

    def test_no_spec_data_passes_through_unchanged(self):
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {},
                # no "data" key
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact

    def test_non_list_data_values_passes_through_unchanged(self):
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {},
                "data": {"values": "not-a-list"},
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact

    def test_missing_spec_key_passes_through_unchanged(self):
        artifact = {
            "type": "visualization",
            "spec": "not-a-dict",
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        assert result is artifact

    # ── Input immutability: summarizer does not mutate the input dict ─────────

    def test_summarizer_does_not_mutate_input(self):
        artifact = _make_artifact_with_rows(1001)
        original_row_count = len(artifact["spec"]["data"]["values"])
        _ = _summarize_artifact_for_reviewer(artifact)
        assert len(artifact["spec"]["data"]["values"]) == original_row_count
        assert "_data_summary" not in artifact

    def test_summarizer_preserves_first_n_rows_in_order(self):
        artifact = _make_artifact_with_rows(1001)
        original_first_10 = artifact["spec"]["data"]["values"][:10]
        result = _summarize_artifact_for_reviewer(artifact)
        # Original rows have short string values, so they survive truncation intact.
        assert result["spec"]["data"]["values"] == original_first_10

    # ── Per-field string truncation (security: prompt-injection prevention) ───

    def test_long_string_field_truncated_in_sampled_rows(self):
        """String values longer than _MAX_FIELD_STR_LEN are truncated."""
        long_string = "A" * 10_000  # far above 500-char cap
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {"x": {"field": "name"}, "y": {"field": "v"}},
                "data": {
                    "values": [{"name": long_string, "v": i} for i in range(1001)]
                },
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        for row in result["spec"]["data"]["values"]:
            assert len(row["name"]) == 500

    def test_short_string_field_unchanged_in_sampled_rows(self):
        """String values at or below _MAX_FIELD_STR_LEN are not modified."""
        short_string = "Campaign Name"
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {"x": {"field": "name"}, "y": {"field": "v"}},
                "data": {
                    "values": [{"name": short_string, "v": i} for i in range(1001)]
                },
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        for row in result["spec"]["data"]["values"]:
            assert row["name"] == short_string

    def test_non_string_fields_in_rows_are_not_affected(self):
        """Numeric, bool, and None values in rows pass through unchanged."""
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {},
                "data": {
                    "values": [{"n": i, "f": 1.5, "b": True, "null": None} for i in range(1001)]
                },
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        result = _summarize_artifact_for_reviewer(artifact)
        for row in result["spec"]["data"]["values"]:
            assert isinstance(row["f"], float)
            assert isinstance(row["b"], bool)
            assert row["null"] is None

    def test_per_field_truncation_does_not_mutate_input(self):
        """String truncation must not modify the original row dicts."""
        long_string = "B" * 10_000
        artifact = {
            "type": "visualization",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {},
                "data": {
                    "values": [{"name": long_string, "v": i} for i in range(1001)]
                },
            },
            "metadata": {
                "chart_type_suggestion": "bar",
                "title": "Test",
                "data_source": "ga",
                "description": None,
            },
        }
        _ = _summarize_artifact_for_reviewer(artifact)
        # Original rows are untouched.
        for row in artifact["spec"]["data"]["values"]:
            assert len(row["name"]) == 10_000


class TestArtifactsProjectorCallbackSummarization:
    """(f) Projector applies summarization: >1,000 rows → _data_summary in JSON output."""

    def test_projector_output_contains_data_summary_when_over_threshold(self):
        artifact = _make_artifact_with_rows(1001)
        ctx = _CallbackContext({"response_artifacts": [artifact]})

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        result_json = ctx.state.get("ga_review_artifacts")
        assert isinstance(result_json, str)
        parsed = json.loads(result_json)
        assert len(parsed) == 1
        assert "_data_summary" in parsed[0]
        assert parsed[0]["_data_summary"]["summarized"] is True
        assert parsed[0]["_data_summary"]["original_row_count"] == 1001
        assert len(parsed[0]["spec"]["data"]["values"]) == 10

    def test_projector_output_no_data_summary_when_under_threshold(self):
        artifact = _make_artifact_with_rows(100)
        ctx = _CallbackContext({"response_artifacts": [artifact]})

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        result_json = ctx.state.get("ga_review_artifacts")
        parsed = json.loads(result_json)
        assert "_data_summary" not in parsed[0]
        assert len(parsed[0]["spec"]["data"]["values"]) == 100

    def test_projector_does_not_mutate_response_artifacts_in_state(self):
        """response_artifacts in state must be untouched so API ships full spec."""
        artifact = _make_artifact_with_rows(1001)
        ctx = _CallbackContext({"response_artifacts": [artifact]})

        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        # The original artifact in response_artifacts must still have all rows.
        original_in_state = ctx.state["response_artifacts"][0]
        assert len(original_in_state["spec"]["data"]["values"]) == 1001
        assert "_data_summary" not in original_in_state

    def test_projector_truncates_long_string_fields_in_reviewer_output(self):
        """Per-field string truncation applies through the projector path.

        We need 1001 rows to trigger row-count summarization, but the spec must
        stay under the 512 KB Artifact validation limit.  Use 600-char strings in
        only the first 10 rows (the sample) and short strings in the remaining 991
        rows — total spec JSON well under 512 KB.
        """
        long_str = "Y" * 600  # above _MAX_FIELD_STR_LEN=500, but only 10 rows have it
        rows = [{"name": long_str, "v": i} for i in range(10)] + [
            {"name": "short", "v": i} for i in range(991)
        ]
        artifact = Artifact(
            type="visualization",
            spec={
                "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
                "mark": "bar",
                "encoding": {"x": {"field": "name"}, "y": {"field": "v", "type": "quantitative"}},
                "data": {"values": rows},
            },
            metadata=ArtifactMetadata(
                chart_type_suggestion="bar",
                title="Long Field Test",
                data_source="google_analytics",
                description=None,
            ),
        ).model_dump()

        ctx = _CallbackContext({"response_artifacts": [artifact]})
        projector = _make_artifacts_projector_callback("ga_review")
        projector(ctx)

        assert "ga_review_artifacts" in ctx.state, "projector should have written the key"
        parsed = json.loads(ctx.state["ga_review_artifacts"])
        for row in parsed[0]["spec"]["data"]["values"]:
            assert len(row["name"]) == 500
        # Original artifact in state untouched.
        assert len(artifact["spec"]["data"]["values"][0]["name"]) == 600
