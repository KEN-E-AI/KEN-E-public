"""Schema-conformance assertions for the transfer_to_specialist staging fixture.

Validates that transfer_to_specialist_trace.json satisfies the post-AH-75 trace
contract documented in docs/trace-structure-spec.md and
docs/design/components/agentic-harness/projects/AH-PRD-09-trace-contract-diff.md.

Under AH-75 the deploy-time / per-turn distinction in dispatch dropped away:
both modes route through ADK's native ``transfer_to_agent`` + ``sub_agents``,
so the trace shape is one ``transfer_to_agent`` action followed by a
sub-agent span named after the specialist's doc_id. When the specialist's
config has ``default_acceptance_criteria`` set, its agent span IS a
``LoopAgent`` (renamed back to the doc_id) wrapping worker + reviewer
iteration sub-spans.

The fixture is the canonical **target** shape. Each span carries an
``emission_status`` of ``"emitted"`` (written by the current KEN-E runtime) or
``"deferred"`` (target shape the runtime does not yet emit — e.g. the
``*_review_reviewer`` span and the ``*_worker`` iteration annotations, which live
under ``deferred_summary``). ``TestEmissionStatus`` pins that labelling so the
fixture cannot silently claim to emit something the runtime does not.

MER-E extractor authors should run this test to confirm that the fixture is a
valid target for validation tooling before updating extractor queries, and must
treat ``deferred`` spans/fields as absent in live traces.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.adk.tracking.compliance import validate_trace_compliance

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "transfer_to_specialist_trace.json"


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
            "Run the AH-75 implementation before executing these tests."
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
        for field in (
            "agent_id",
            "agent_version",
            "account_id",
            "session_id",
            "environment",
            "rollout_percentage",
        ):
            assert field in meta, f"metadata missing required field: {field}"

    def test_metadata_passes_validate_trace_compliance(
        self, fixture_data: dict
    ) -> None:
        # Delegate to the same validator that the trace-compliance-check CI
        # step runs so this conformance test cannot drift from the CI gate's
        # requirements (any field added to REQUIRED_FIELDS in compliance.py is
        # automatically enforced here).
        result = validate_trace_compliance(
            fixture_data["metadata"], trace_id=fixture_data.get("trace_id")
        )
        assert result.is_compliant, (
            f"Fixture metadata is not compliant per validate_trace_compliance: "
            f"{[i.message for i in result.issues]}"
        )

    def test_transfer_to_agent_dispatch_flag_is_true(self, fixture_data: dict) -> None:
        """AH-75: the fixture must represent a transfer_to_agent dispatch run."""
        flags = fixture_data["metadata"].get("feature_flags", {})
        assert flags.get("agentic_harness_transfer_to_agent_dispatch") is True, (
            "Fixture must represent a post-AH-75 trace "
            "(agentic_harness_transfer_to_agent_dispatch: true)"
        )

    def test_no_delegate_to_specialist_span_anywhere(self, fixture_data: dict) -> None:
        """AH-75: the delegate_to_specialist function tool was removed. No span
        anywhere in the tree should carry that name."""

        def walk_names(node: dict) -> list[str]:
            names = [node.get("name", "")]
            for child in node.get("children", []):
                names.extend(walk_names(child))
            return names

        every_name: list[str] = []
        for top in fixture_data["spans"]:
            every_name.extend(walk_names(top))
        assert "delegate_to_specialist" not in every_name, (
            "delegate_to_specialist span appeared in the fixture but the "
            "function tool was deleted in AH-75. Re-export the fixture from "
            "the current ADK runtime."
        )


# ---------------------------------------------------------------------------
# Root agent span — emits the transfer_to_agent action
# ---------------------------------------------------------------------------


class TestRootAgentSpan:
    @pytest.fixture
    def root_span(self, fixture_data: dict) -> dict:
        spans = fixture_data["spans"]
        assert spans, "fixture must contain at least one top-level span"
        return spans[0]

    def test_top_level_span_is_root_agent(self, root_span: dict) -> None:
        summary = root_span.get("summary", {})
        # Accept either summary.agent_kind == "root" or a top-level span
        # named "ken_e" — both are unambiguous signals.
        is_root = (
            summary.get("agent_kind") == "root" or root_span.get("name") == "ken_e"
        )
        assert is_root, (
            f"Top-level span must identify the root agent (got "
            f"name={root_span.get('name')!r}, summary={summary!r})"
        )

    def test_root_has_transfer_to_agent_child(self, root_span: dict) -> None:
        """The root LLM emits a transfer_to_agent function call. ADK's flow
        produces a child span named 'transfer_to_agent' carrying the target
        ``agent_name`` in its summary."""
        children = root_span.get("children", [])
        transfers = [c for c in children if c.get("name") == "transfer_to_agent"]
        assert transfers, (
            "Root agent span must include a 'transfer_to_agent' child — that "
            "is the AH-75 dispatch mechanism."
        )
        target = transfers[0].get("summary", {}).get("agent_name", "")
        assert re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", target), (
            f"transfer_to_agent target {target!r} must match the specialist "
            "name regex ^[a-z][a-z0-9_]{0,63}$"
        )


# ---------------------------------------------------------------------------
# Specialist sub-agent span — the per-specialist scoring anchor for MER-E
# ---------------------------------------------------------------------------


class TestSpecialistSubAgentSpan:
    @pytest.fixture
    def specialist_span(self, fixture_data: dict) -> dict:
        """The first non-transfer_to_agent child of the root agent span.

        Under AH-75, this is the agent ADK transferred control to — either a
        plain LlmAgent (no review wrap) or a LoopAgent renamed to the doc_id
        (review-wrapped).
        """
        root = fixture_data["spans"][0]
        children = root.get("children", [])
        matched = [c for c in children if c.get("name") != "transfer_to_agent"]
        assert matched, "No specialist sub-agent span found under the root"
        return matched[0]

    def test_summary_has_specialist_name(self, specialist_span: dict) -> None:
        summary = specialist_span.get("summary", {})
        assert "specialist_name" in summary, (
            "specialist sub-agent span must have 'specialist_name' in summary "
            "for MER-E per-specialist scoring"
        )
        assert isinstance(summary["specialist_name"], str)
        assert summary["specialist_name"]
        assert re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", summary["specialist_name"]), (
            f"specialist_name {summary['specialist_name']!r} must match "
            "^[a-z][a-z0-9_]{0,63}$ (the dispatch validation regex)"
        )

    def test_specialist_span_name_matches_specialist_name(
        self, specialist_span: dict
    ) -> None:
        """AH-75: the sub-agent span's name must equal its specialist_name —
        ADK's transfer_to_agent looks up by name, and review-wrapped LoopAgent
        is renamed back to the doc_id by _build_specialist."""
        summary = specialist_span.get("summary", {})
        assert specialist_span["name"] == summary["specialist_name"]

    def test_review_wrapped_specialist_carries_exit_reason(
        self, specialist_span: dict
    ) -> None:
        """When the specialist's config has default_acceptance_criteria set,
        its agent_kind is 'loop_pipeline' and the summary records exit_reason
        + total_iterations so MER-E can score the review loop."""
        summary = specialist_span.get("summary", {})
        if summary.get("agent_kind") != "loop_pipeline":
            pytest.skip("specialist is not review-wrapped (no review loop fields)")
        assert "exit_reason" in summary
        assert summary["exit_reason"] in ("approved", "max_iterations")
        assert "total_iterations" in summary
        assert isinstance(summary["total_iterations"], int)
        assert summary["total_iterations"] >= 0
        assert "output_key_prefix" in summary

    def test_review_wrapped_specialist_has_worker_and_reviewer_children(
        self, specialist_span: dict
    ) -> None:
        """A LoopAgent review wrap carries per-iteration worker + reviewer
        sub-spans in the target shape. Both names MUST be present when
        agent_kind=loop_pipeline, but their emission_status records that only the
        worker span is emitted today; the reviewer span is deferred (see
        TestEmissionStatus and trace-structure-spec.md §14.2)."""
        summary = specialist_span.get("summary", {})
        if summary.get("agent_kind") != "loop_pipeline":
            pytest.skip("specialist is not review-wrapped (no iteration sub-spans)")
        spec_name = summary["specialist_name"]
        children = specialist_span.get("children", [])
        worker = [c for c in children if c.get("name") == f"{spec_name}_worker"]
        reviewer = [c for c in children if c.get("name", "").endswith("_reviewer")]
        assert worker, f"LoopAgent specialist must have a {spec_name}_worker child"
        assert reviewer, "LoopAgent specialist must have a *_reviewer child"
        # Honesty guard: the reviewer span is documented as not emitted today.
        assert reviewer[0].get("emission_status") == "deferred", (
            "The reviewer LlmAgent has no agent-span callbacks, so the "
            "*_review_reviewer span is not emitted; the fixture must tag it "
            "'deferred'. If the runtime now emits it, update this test, the "
            "fixture, and trace-structure-spec.md §14.2 together."
        )


# ---------------------------------------------------------------------------
# Worker / reviewer iteration sub-spans (DEFERRED target shape)
#
# These validate the *target* iteration-level shape. Per trace-structure-spec.md
# §14.2 the runtime does not emit it yet: the ``_worker`` span's iteration
# annotations live under ``deferred_summary`` (its live ``summary`` is empty), and
# the ``_review_reviewer`` span is not emitted at all. MER-E must not key required
# logic on these until the deferral is lifted.
# ---------------------------------------------------------------------------


class TestIterationSubSpans:
    @pytest.fixture
    def worker_span(self, fixture_data: dict) -> dict:
        root = fixture_data["spans"][0]
        specialist = next(
            c for c in root["children"] if c.get("name") != "transfer_to_agent"
        )
        if specialist.get("summary", {}).get("agent_kind") != "loop_pipeline":
            pytest.skip("specialist is not review-wrapped (no iteration sub-spans)")
        spec_name = specialist["summary"]["specialist_name"]
        matched = [
            c
            for c in specialist.get("children", [])
            if c.get("name") == f"{spec_name}_worker"
        ]
        assert matched, f"Worker span not found for specialist {spec_name!r}"
        return matched[0]

    @pytest.fixture
    def reviewer_span(self, fixture_data: dict) -> dict:
        root = fixture_data["spans"][0]
        specialist = next(
            c for c in root["children"] if c.get("name") != "transfer_to_agent"
        )
        if specialist.get("summary", {}).get("agent_kind") != "loop_pipeline":
            pytest.skip("specialist is not review-wrapped (no iteration sub-spans)")
        matched = [
            c
            for c in specialist.get("children", [])
            if c.get("name", "").endswith("_reviewer")
        ]
        assert matched, "Reviewer span not found"
        return matched[0]

    def test_worker_iteration_annotations_are_deferred_not_in_live_summary(
        self, worker_span: dict
    ) -> None:
        """The worker span is emitted but its live ``summary`` carries none of the
        iteration annotations — they are the deferred target under
        ``deferred_summary``."""
        assert worker_span.get("emission_status") == "emitted"
        assert "iteration" not in worker_span.get("summary", {}), (
            "iteration must not appear in the worker's live summary — the runtime "
            "writes only output={status, text}; iteration annotations are deferred"
        )

    def test_worker_deferred_summary_has_iteration_index(
        self, worker_span: dict
    ) -> None:
        deferred = worker_span.get("deferred_summary", {})
        assert "iteration" in deferred
        assert isinstance(deferred["iteration"], int)
        assert deferred["iteration"] >= 1

    def test_worker_deferred_summary_has_specialist_output(
        self, worker_span: dict
    ) -> None:
        assert "specialist_output" in worker_span.get("deferred_summary", {})

    def test_reviewer_span_is_deferred(self, reviewer_span: dict) -> None:
        assert reviewer_span.get("emission_status") == "deferred"
        assert reviewer_span.get("deferred_reason"), (
            "deferred reviewer span must carry a deferred_reason"
        )

    def test_reviewer_target_summary_has_iteration_index(
        self, reviewer_span: dict
    ) -> None:
        summary = reviewer_span.get("summary", {})
        assert "iteration" in summary
        assert isinstance(summary["iteration"], int)
        assert summary["iteration"] >= 1

    def test_reviewer_target_summary_has_reviewer_output(
        self, reviewer_span: dict
    ) -> None:
        assert "reviewer_output" in reviewer_span.get("summary", {})


# ---------------------------------------------------------------------------
# Emission-status honesty contract
#
# Pins which spans the current runtime actually emits, so the fixture cannot
# drift into advertising a span/field MER-E would never find in a live trace.
# ---------------------------------------------------------------------------


class TestEmissionStatus:
    def _walk(self, node: dict) -> list[dict]:
        out = [node]
        for child in node.get("children", []):
            out.extend(self._walk(child))
        return out

    def test_every_span_declares_emission_status(self, fixture_data: dict) -> None:
        for top in fixture_data["spans"]:
            for span in self._walk(top):
                assert span.get("emission_status") in ("emitted", "deferred"), (
                    f"span {span.get('name')!r} must declare emission_status "
                    "as 'emitted' or 'deferred'"
                )

    def test_deferred_spans_carry_a_reason(self, fixture_data: dict) -> None:
        for top in fixture_data["spans"]:
            for span in self._walk(top):
                if span.get("emission_status") == "deferred":
                    assert span.get("deferred_reason"), (
                        f"deferred span {span.get('name')!r} must explain why via "
                        "deferred_reason"
                    )

    def test_emitted_spans_are_exactly_the_runtime_set(
        self, fixture_data: dict
    ) -> None:
        """Lock the emitted set to what the runtime writes today: root,
        transfer_to_agent, the specialist span, and the {doc_id}_worker span.
        The reviewer span is the only deferred span. Changing this set requires a
        matching runtime + spec change (trace-structure-spec.md §14.2)."""
        emitted = {
            s["name"]
            for top in fixture_data["spans"]
            for s in self._walk(top)
            if s.get("emission_status") == "emitted"
        }
        deferred = {
            s["name"]
            for top in fixture_data["spans"]
            for s in self._walk(top)
            if s.get("emission_status") == "deferred"
        }
        assert emitted == {
            "ken_e",
            "transfer_to_agent",
            "business_researcher",
            "business_researcher_worker",
        }
        assert deferred == {"business_researcher_review_reviewer"}
