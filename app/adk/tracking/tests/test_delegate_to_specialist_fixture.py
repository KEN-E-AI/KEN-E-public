"""Schema-conformance assertions for the delegate_to_specialist staging fixture.

Validates that delegate_to_specialist_trace.json satisfies the AH-PRD-09 trace
contract documented in docs/trace-structure-spec.md §14 and
docs/design/components/agentic-harness/projects/AH-PRD-09-trace-contract-diff.md.

MER-E extractor authors should run this test to confirm that the fixture is a
valid target for validation tooling before updating extractor queries.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "delegate_to_specialist_trace.json"
)


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    return json.loads(_FIXTURE_PATH.read_text())


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


class TestFixtureTopLevel:
    def test_fixture_file_exists(self) -> None:
        assert _FIXTURE_PATH.exists(), (
            f"Fixture not found at {_FIXTURE_PATH}. "
            "Run the AH-67 implementation before executing these tests."
        )

    def test_has_trace_id(self, fixture_data: dict) -> None:
        assert "trace_id" in fixture_data
        assert fixture_data["trace_id"]

    def test_has_spans_list(self, fixture_data: dict) -> None:
        assert "spans" in fixture_data
        assert isinstance(fixture_data["spans"], list)
        assert len(fixture_data["spans"]) >= 1

    def test_has_metadata_block(self, fixture_data: dict) -> None:
        assert "metadata" in fixture_data

    def test_metadata_has_required_fields(self, fixture_data: dict) -> None:
        meta = fixture_data["metadata"]
        for field in ("account_id", "session_id", "environment", "rollout_percentage"):
            assert field in meta, f"metadata missing required field: {field}"

    def test_per_turn_dispatch_flag_is_true(self, fixture_data: dict) -> None:
        flags = fixture_data["metadata"].get("feature_flags", {})
        assert flags.get("agentic_harness_per_turn_dispatch") is True, (
            "Fixture must represent a post-AH-PRD-09 trace "
            "(agentic_harness_per_turn_dispatch: true)"
        )


# ---------------------------------------------------------------------------
# delegate_to_specialist span
# ---------------------------------------------------------------------------


class TestDelegateToSpecialistSpan:
    @pytest.fixture
    def delegate_span(self, fixture_data: dict) -> dict:
        spans = fixture_data["spans"]
        matched = [s for s in spans if s.get("name") == "delegate_to_specialist"]
        assert matched, "No span named 'delegate_to_specialist' found in fixture"
        return matched[0]

    def test_span_name_is_delegate_to_specialist(self, delegate_span: dict) -> None:
        assert delegate_span["name"] == "delegate_to_specialist"

    def test_summary_has_specialist_name(self, delegate_span: dict) -> None:
        summary = delegate_span.get("summary", {})
        assert "specialist_name" in summary, (
            "delegate_to_specialist span must have 'specialist_name' in summary"
        )
        assert isinstance(summary["specialist_name"], str)
        assert summary["specialist_name"]
        assert re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", summary["specialist_name"]), (
            f"specialist_name {summary['specialist_name']!r} must match "
            "^[a-z][a-z0-9_]{0,63}$ (the dispatch validation regex)"
        )

    def test_summary_has_cache_hit(self, delegate_span: dict) -> None:
        summary = delegate_span.get("summary", {})
        assert "cache_hit" in summary, (
            "delegate_to_specialist span must have 'cache_hit' in summary"
        )
        assert isinstance(summary["cache_hit"], bool)

    def test_summary_does_not_have_mcp_pool_hit(self, delegate_span: dict) -> None:
        """mcp_pool_hit is TODO(AH-62) — must be absent in this release."""
        summary = delegate_span.get("summary", {})
        assert "mcp_pool_hit" not in summary, (
            "mcp_pool_hit must not appear in the fixture until AH-62 lands"
        )

    def test_has_specialist_run_child(self, delegate_span: dict) -> None:
        children = delegate_span.get("children", [])
        child_names = [c.get("name") for c in children]
        assert "specialist_run" in child_names, (
            "delegate_to_specialist span must have a 'specialist_run' child"
        )


# ---------------------------------------------------------------------------
# specialist_run child span
# ---------------------------------------------------------------------------


class TestSpecialistRunSpan:
    @pytest.fixture
    def specialist_run_span(self, fixture_data: dict) -> dict:
        delegate = next(
            s for s in fixture_data["spans"] if s.get("name") == "delegate_to_specialist"
        )
        children = delegate.get("children", [])
        matched = [c for c in children if c.get("name") == "specialist_run"]
        assert matched, "No 'specialist_run' child found under delegate_to_specialist"
        return matched[0]

    def test_summary_has_acceptance_criteria(self, specialist_run_span: dict) -> None:
        summary = specialist_run_span.get("summary", {})
        assert "acceptance_criteria" in summary

    def test_summary_has_exit_reason(self, specialist_run_span: dict) -> None:
        summary = specialist_run_span.get("summary", {})
        assert "exit_reason" in summary
        assert summary["exit_reason"] in ("approved", "max_iterations"), (
            f"exit_reason must be 'approved' or 'max_iterations', got: {summary['exit_reason']!r}"
        )

    def test_summary_has_total_iterations(self, specialist_run_span: dict) -> None:
        summary = specialist_run_span.get("summary", {})
        assert "total_iterations" in summary
        assert isinstance(summary["total_iterations"], int)
        assert summary["total_iterations"] >= 0

    def test_summary_has_output_key_prefix(self, specialist_run_span: dict) -> None:
        summary = specialist_run_span.get("summary", {})
        assert "output_key_prefix" in summary
        assert isinstance(summary["output_key_prefix"], str)

    def test_has_review_loop_iteration_grandchild(
        self, specialist_run_span: dict
    ) -> None:
        grandchildren = specialist_run_span.get("children", [])
        names = [g.get("name") for g in grandchildren]
        assert "review_loop_iteration" in names, (
            "specialist_run span must have at least one 'review_loop_iteration' child"
        )


# ---------------------------------------------------------------------------
# review_loop_iteration grandchild span
# ---------------------------------------------------------------------------


class TestReviewLoopIterationSpan:
    @pytest.fixture
    def iteration_span(self, fixture_data: dict) -> dict:
        delegate = next(
            s for s in fixture_data["spans"] if s.get("name") == "delegate_to_specialist"
        )
        sr = next(c for c in delegate.get("children", []) if c.get("name") == "specialist_run")
        iterations = [c for c in sr.get("children", []) if c.get("name") == "review_loop_iteration"]
        assert iterations, "No 'review_loop_iteration' found under specialist_run"
        return iterations[0]

    def test_summary_has_iteration_index(self, iteration_span: dict) -> None:
        summary = iteration_span.get("summary", {})
        assert "iteration" in summary
        assert isinstance(summary["iteration"], int)
        assert summary["iteration"] >= 1

    def test_summary_has_specialist_output(self, iteration_span: dict) -> None:
        summary = iteration_span.get("summary", {})
        assert "specialist_output" in summary

    def test_summary_has_reviewer_output(self, iteration_span: dict) -> None:
        summary = iteration_span.get("summary", {})
        assert "reviewer_output" in summary
