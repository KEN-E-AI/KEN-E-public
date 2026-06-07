"""Schema-conformance assertions for the google_search_task_mode staging fixture.

Validates that google_search_task_mode_trace.json satisfies the AH-PRD-15 trace
contract documented in docs/trace-structure-spec.md §17 and
docs/design/components/agentic-harness/projects/AH-PRD-15-agenttool-migration-cutover.md
§7.2 (AC #2).

This fixture covers the observability half of the AH-PRD-15 migration: after
agent.google_search is migrated off AgentTool.run_async to mode='task' sub-agent
dispatch (AH-115/116), the inner google_search grounded-search tool calls must
appear as emitted spans in the outer stream — no missing spans vs the intended
shape (GitHub google/adk-python#3984 was the defect; task-mode is the fix).

The fixture covers the specialist-assignment path (AH-115) as the baseline: the
google_analytics_specialist worker invokes request_task_google_search, which runs
the google_search_agent as a mode='task' leaf. The root-assignment variant (AH-116)
produces an identical leaf shape; a separate fixture can discriminate if MER-E
requires it later (see D-A2 in the AH-118 Implementation Plan).

Every span carries emission_status='emitted' or 'deferred'. The google.genai
LLM-call span inside the task-mode leaf is 'deferred' — the Weave autopatch
fragility carry-forward documented in docs/trace-structure-spec.md §4.5 and
AH-PRD-13 §9. TestEmissionStatus.test_emitted_spans_are_exactly_the_runtime_set
locks this deferred classification so a future autopatch fix that flips the span
to 'emitted' breaks CI intentionally, prompting a spec + fixture update.

MER-E extractor authors should run this test to confirm that the fixture is a
valid target for validation tooling before updating extractor queries, and must
treat 'deferred' spans/fields as absent in live traces until their owning
follow-up ships.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.adk.tracking.compliance import validate_trace_compliance

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "google_search_task_mode_trace.json"
)

# node_path format sourced from AH-99 probe-1 evidence:
# docs/spike-adk2-supervisor-orchestration-live.md §4
# '<agent>@<index>/<agent_name>@<id>' for task-mode nested paths
# Shared pattern with test_supervisor_orchestration_fixture.py:_NODE_PATH_RE
_NODE_PATH_RE = re.compile(r"^[a-z][a-z0-9_]+@[\w-]+(\/[a-z][a-z0-9_]+@[\w-]+)*$")

_SPECIALIST_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    return json.loads(_FIXTURE_PATH.read_text())


def _walk(node: dict) -> list[dict]:
    """Recursively collect all span nodes in the tree."""
    out = [node]
    for child in node.get("children", []):
        out.extend(_walk(child))
    return out


def _all_spans(fixture_data: dict) -> list[dict]:
    spans: list[dict] = []
    for top in fixture_data["spans"]:
        spans.extend(_walk(top))
    return spans


def _find_spans_by_name(fixture_data: dict, name: str) -> list[dict]:
    return [s for s in _all_spans(fixture_data) if s.get("name") == name]


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


class TestFixtureTopLevel:
    def test_fixture_file_exists(self) -> None:
        assert _FIXTURE_PATH.exists(), (
            f"Fixture not found at {_FIXTURE_PATH}. "
            "Run the AH-118 implementation before executing these tests."
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
        result = validate_trace_compliance(
            fixture_data["metadata"], trace_id=fixture_data.get("trace_id")
        )
        assert result.is_compliant, (
            f"Fixture metadata is not compliant per validate_trace_compliance: "
            f"{[i.message for i in result.issues]}"
        )

    def test_task_mode_agent_tools_feature_flag_is_true(
        self, fixture_data: dict
    ) -> None:
        """AH-PRD-15: the fixture must represent a task-mode agent-tools trace."""
        flags = fixture_data["metadata"].get("feature_flags", {})
        assert flags.get("agentic_harness_task_mode_agent_tools") is True, (
            "Fixture must represent a task-mode agent-tools trace "
            "(agentic_harness_task_mode_agent_tools: true in feature_flags)"
        )

    def test_no_AgentTool_artifact_in_fixture(self, fixture_data: dict) -> None:
        """AH-PRD-15 AC #4: no span in the chat-tree 2.0 fixture should carry
        AgentTool / agent_tool / dispatch_to_* markers — those are the pre-2.0
        inner-Runner artefacts this migration eliminates.

        This assertion locks AC #1 of AH-PRD-15 at the fixture layer: if a
        regression reintroduces an AgentTool span into the chat path, this test
        breaks CI before the shape reaches production.
        """
        for span in _all_spans(fixture_data):
            name = span.get("name", "")
            summary = span.get("summary", {})
            assert "AgentTool" not in name, (
                f"Span name {name!r} contains 'AgentTool' — this is the pre-2.0 "
                "inner-Runner artefact that AH-PRD-15 eliminates."
            )
            assert "agent_tool" not in name.lower(), (
                f"Span name {name!r} contains 'agent_tool' — check that this is "
                "not a pre-2.0 AgentTool span."
            )
            assert not name.startswith("dispatch_to_"), (
                f"Span {name!r} is a pre-AH-75 dispatch_to_* artefact and must "
                "not appear in a task-mode trace."
            )
            tool_name = summary.get("tool_name", "")
            assert "AgentTool" not in tool_name, (
                f"summary.tool_name {tool_name!r} contains 'AgentTool' — regression."
            )

    def test_no_delegate_to_specialist_span_anywhere(self, fixture_data: dict) -> None:
        """AH-75: the delegate_to_specialist function tool was removed. No span
        anywhere in the tree should carry that name."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "delegate_to_specialist" not in every_name, (
            "delegate_to_specialist span appeared in the fixture but the "
            "function tool was deleted in AH-75. Re-export the fixture from "
            "the current ADK runtime."
        )


# ---------------------------------------------------------------------------
# Root agent span
# ---------------------------------------------------------------------------


class TestRootAgentSpan:
    @pytest.fixture
    def root_span(self, fixture_data: dict) -> dict:
        spans = fixture_data["spans"]
        assert spans, "fixture must contain at least one top-level span"
        return spans[0]

    def test_top_level_span_is_root_agent(self, root_span: dict) -> None:
        summary = root_span.get("summary", {})
        is_root = (
            summary.get("agent_kind") == "root" or root_span.get("name") == "ken_e"
        )
        assert is_root, (
            f"Top-level span must identify the root agent "
            f"(got name={root_span.get('name')!r}, summary={summary!r})"
        )

    def test_root_has_transfer_to_agent_child(self, root_span: dict) -> None:
        """The root LLM emits a transfer_to_agent function call before dispatching
        to the google_analytics_specialist. The AH-75 dispatch mechanism."""
        children = root_span.get("children", [])
        transfers = [c for c in children if c.get("name") == "transfer_to_agent"]
        assert transfers, (
            "Root agent span must include a 'transfer_to_agent' child — that is the "
            "AH-75 dispatch mechanism."
        )
        target = transfers[0].get("summary", {}).get("agent_name", "")
        assert _SPECIALIST_NAME_RE.fullmatch(target), (
            f"transfer_to_agent target {target!r} must match ^[a-z][a-z0-9_]{{0,63}}$"
        )

    def test_root_has_specialist_child_with_specialist_name(
        self, root_span: dict
    ) -> None:
        """The specialist sub-agent span must be a direct child of the root and
        must carry specialist_name in its summary — the MER-E per-specialist
        scoring anchor."""
        children = root_span.get("children", [])
        specialist_children = [
            c for c in children if c.get("name") != "transfer_to_agent"
        ]
        assert specialist_children, "Root must have a specialist sub-agent child span."
        specialist = specialist_children[0]
        summary = specialist.get("summary", {})
        specialist_name = summary.get("specialist_name", "")
        assert _SPECIALIST_NAME_RE.fullmatch(specialist_name), (
            f"Specialist child span must carry specialist_name in summary "
            f"matching ^[a-z][a-z0-9_]{{0,63}}$ (got {specialist_name!r}). "
            "This is the MER-E per-specialist scoring anchor."
        )
        assert specialist.get("name") == specialist_name, (
            f"Specialist span name {specialist.get('name')!r} must equal "
            f"summary.specialist_name {specialist_name!r} — AH-75 contract."
        )

    def test_root_span_is_emitted(self, root_span: dict) -> None:
        assert root_span.get("emission_status") == "emitted"


# ---------------------------------------------------------------------------
# Task-mode leaf — the google_search_agent mode='task' span
# ---------------------------------------------------------------------------


class TestTaskModeLeaf:
    @pytest.fixture
    def task_mode_leaf(self, fixture_data: dict) -> dict:
        """Find the google_search_agent task-mode leaf in the fixture tree."""
        candidates = _find_spans_by_name(fixture_data, "google_search_agent")
        assert candidates, (
            "Fixture must contain a 'google_search_agent' span — the task-mode "
            "leaf produced by the AH-115/116 migration."
        )
        return candidates[0]

    def test_leaf_is_emitted(self, task_mode_leaf: dict) -> None:
        assert task_mode_leaf.get("emission_status") == "emitted", (
            "google_search_agent task-mode leaf must be emission_status='emitted' — "
            "it is the primary observability signal for AH-PRD-15 AC #2."
        )

    def test_leaf_carries_agent_kind_task_mode(self, task_mode_leaf: dict) -> None:
        summary = task_mode_leaf.get("summary", {})
        assert summary.get("agent_kind") == "task_mode", (
            "google_search_agent span must carry agent_kind='task_mode' in summary — "
            "this distinguishes the task-mode path from a pre-migration AgentTool path."
        )

    def test_leaf_carries_task_id(self, task_mode_leaf: dict) -> None:
        summary = task_mode_leaf.get("summary", {})
        task_id = summary.get("task_id")
        assert isinstance(task_id, str) and task_id, (
            "google_search_agent span must carry a non-empty task_id in summary — "
            "this is the correlation key for MER-E task-level attribution."
        )

    def test_leaf_carries_node_path(self, task_mode_leaf: dict) -> None:
        summary = task_mode_leaf.get("summary", {})
        node_path = summary.get("node_path")
        assert isinstance(node_path, str) and node_path, (
            "google_search_agent span must carry a non-empty node_path in summary. "
            "node_path is sourced from AH-99 probe-1 evidence "
            "(docs/spike-adk2-supervisor-orchestration-live.md §4)."
        )

    def test_leaf_node_path_matches_adk_format(self, task_mode_leaf: dict) -> None:
        """node_path must match the nested task-mode format observed in AH-99 probe-1:
        '<specialist>@<index>/task_specialist@adk-<uuid>'."""
        node_path = task_mode_leaf["summary"]["node_path"]
        assert _NODE_PATH_RE.fullmatch(node_path), (
            f"node_path {node_path!r} does not match expected ADK 2.0 nested "
            "task-mode format. Expected: "
            "'<specialist>@<index>/task_specialist@adk-<uuid>' — "
            "see docs/spike-adk2-supervisor-orchestration-live.md §4."
        )

    def test_leaf_node_path_contains_task_specialist_segment(
        self, task_mode_leaf: dict
    ) -> None:
        """The node_path second segment should identify the task_specialist per
        probe-1 evidence. This validates the nesting depth distinguishes
        task-mode leaf from coordinator-level spans."""
        node_path = task_mode_leaf["summary"]["node_path"]
        assert "/task_specialist@" in node_path, (
            f"node_path {node_path!r} must contain a '/task_specialist@' segment — "
            "this is the distinguishing pattern for a task-mode leaf nested under a "
            "specialist, per AH-99 probe-1 (docs/spike-adk2-supervisor-orchestration-live.md §4)."
        )

    def test_request_task_tool_precedes_leaf(self, fixture_data: dict) -> None:
        """The task-mode leaf must be a child of a request_task_google_search tool
        span — this validates the full dispatch chain: specialist worker invokes
        request_task_google_search, which runs google_search_agent as a task node."""
        req_task_spans = _find_spans_by_name(fixture_data, "request_task_google_search")
        assert req_task_spans, (
            "Fixture must contain a 'request_task_google_search' span — this is the "
            "tool ADK auto-generates for invoking a mode='task' sub-agent."
        )
        for span in req_task_spans:
            children = span.get("children", [])
            leaf_children = [
                c for c in children if c.get("name") == "google_search_agent"
            ]
            assert leaf_children, (
                "request_task_google_search span must have 'google_search_agent' as a "
                "child — the task-mode leaf is dispatched via this tool call."
            )

    def test_task_id_correlates_request_task_to_leaf(self, fixture_data: dict) -> None:
        """Per docs/trace-structure-spec.md §17.4 point 4, task_id is the
        correlation key between request_task_<name> and the task-mode leaf.

        This test guards against a fixture edit that accidentally diverges
        the two task_id values — MER-E joins on task_id to build a single
        logical task_delegation → leaf → inner-tool span chain."""
        req_task_spans = _find_spans_by_name(fixture_data, "request_task_google_search")
        leaf_spans = _find_spans_by_name(fixture_data, "google_search_agent")
        assert req_task_spans and leaf_spans, (
            "Both request_task_google_search and google_search_agent must be present "
            "to assert task_id correlation."
        )
        req_task_id = req_task_spans[0].get("summary", {}).get("task_id", "")
        leaf_task_id = leaf_spans[0].get("summary", {}).get("task_id", "")
        assert req_task_id, (
            "request_task_google_search span must have a non-empty task_id."
        )
        assert leaf_task_id, "google_search_agent span must have a non-empty task_id."
        assert req_task_id == leaf_task_id, (
            f"task_id must match between request_task_google_search "
            f"({req_task_id!r}) and google_search_agent ({leaf_task_id!r}) — "
            "task_id is the MER-E correlation key per trace-structure-spec.md §17.4."
        )


# ---------------------------------------------------------------------------
# Grounded-search tool steps — the primary observability signal
# ---------------------------------------------------------------------------


class TestGroundedSearchSteps:
    @pytest.fixture
    def google_search_spans(self, fixture_data: dict) -> list[dict]:
        """Find all google_search tool spans inside the task-mode leaf."""
        leaf_candidates = _find_spans_by_name(fixture_data, "google_search_agent")
        assert leaf_candidates, "Fixture must contain a google_search_agent span."
        leaf = leaf_candidates[0]
        search_spans = [
            c for c in leaf.get("children", []) if c.get("name") == "google_search"
        ]
        assert search_spans, (
            "google_search_agent leaf must contain at least one 'google_search' "
            "child span — these are the grounded-search steps that AH-PRD-15 §7.2 "
            "AC #2 requires to appear in the trace (the defect under #3984 was that "
            "they vanished when dispatched via AgentTool.run_async on 2.0)."
        )
        return search_spans

    def test_grounded_search_spans_are_emitted(
        self, google_search_spans: list[dict]
    ) -> None:
        """Core AC #2 assertion: grounded-search steps must be emitted, not deferred."""
        for span in google_search_spans:
            assert span.get("emission_status") == "emitted", (
                "google_search span must be emission_status='emitted' — "
                "this is the primary assertion of AH-PRD-15 §7.2 AC #2: "
                "grounded-search steps must appear in the trace on the migrated path."
            )

    def test_grounded_search_spans_carry_tool_name(
        self, google_search_spans: list[dict]
    ) -> None:
        for span in google_search_spans:
            tool_name = span.get("summary", {}).get("tool_name")
            assert tool_name == "google_search", (
                f"google_search span summary must carry tool_name='google_search', "
                f"got {tool_name!r}. MER-E extracts tool calls via "
                "'op_name == tool:google_search' per docs/trace-structure-spec.md §3."
            )

    def test_grounded_search_spans_carry_status_success(
        self, google_search_spans: list[dict]
    ) -> None:
        for span in google_search_spans:
            status = span.get("summary", {}).get("status")
            assert status == "success", (
                f"google_search span summary must carry status='success' in this "
                f"fixture (representative happy-path invocations), got {status!r}."
            )

    def test_grounded_search_spans_carry_full_input(
        self, google_search_spans: list[dict]
    ) -> None:
        """Per docs/trace-structure-spec.md §6, tool call spans must carry full
        (unsummarized) input — required for MER-E Query Quality evaluation."""
        for span in google_search_spans:
            tool_input = span.get("summary", {}).get("input")
            assert isinstance(tool_input, dict), (
                "google_search span must carry 'input' as a dict in summary — "
                "full (unsummarized) tool input is required per trace-structure-spec.md §6."
            )
            assert tool_input, "google_search span 'input' must be non-empty."
            assert "query" in tool_input, (
                "google_search tool input must contain a 'query' key — "
                "that is the primary input field for grounded-search calls."
            )
            assert isinstance(tool_input["query"], str) and tool_input["query"], (
                "google_search tool input 'query' must be a non-empty string."
            )

    def test_grounded_search_spans_carry_full_output(
        self, google_search_spans: list[dict]
    ) -> None:
        """Per docs/trace-structure-spec.md §6, tool call spans must carry full
        (unsummarized) output — required for MER-E Result Utilization evaluation."""
        for span in google_search_spans:
            tool_output = span.get("summary", {}).get("output")
            assert isinstance(tool_output, dict), (
                "google_search span must carry 'output' as a dict in summary — "
                "full (unsummarized) tool output is required per trace-structure-spec.md §6."
            )
            assert tool_output, "google_search span 'output' must be non-empty."
            assert "results" in tool_output, (
                "google_search tool output must contain a 'results' key — "
                "that is the standard output field for grounded-search calls."
            )
            assert isinstance(tool_output["results"], list), (
                "google_search tool output 'results' must be a list."
            )
            assert tool_output["results"], (
                "google_search tool output 'results' must be non-empty in a "
                "representative happy-path fixture."
            )

    def test_fixture_has_at_least_two_search_invocations(
        self, google_search_spans: list[dict]
    ) -> None:
        """The fixture must include at least two representative google_search
        invocations to demonstrate that multiple grounded-search steps are
        captured (parallel or sequential calls in a single web-research task)."""
        assert len(google_search_spans) >= 2, (
            f"Fixture must include at least two 'google_search' spans under the "
            f"task-mode leaf (got {len(google_search_spans)}). Two representative "
            "invocations demonstrate that all grounded-search steps are captured, "
            "not just the first."
        )

    def test_search_invocations_have_distinct_queries(
        self, google_search_spans: list[dict]
    ) -> None:
        """Distinct queries across invocations ensure the fixture represents a
        realistic multi-query web-research turn, not a degenerate single-call case."""
        queries = [
            span.get("summary", {}).get("input", {}).get("query", "")
            for span in google_search_spans
        ]
        assert len(set(queries)) > 1, (
            f"At least two google_search invocations must carry distinct queries "
            f"(got queries={queries!r}). Distinct queries validate that the fixture "
            "models a realistic multi-query web-research turn."
        )


# ---------------------------------------------------------------------------
# Emission-status honesty contract
#
# Pins which spans the current runtime actually emits so the fixture cannot
# drift into advertising a span MER-E would never find in a live trace.
# ---------------------------------------------------------------------------


class TestEmissionStatus:
    def test_every_span_declares_emission_status(self, fixture_data: dict) -> None:
        for span in _all_spans(fixture_data):
            assert span.get("emission_status") in ("emitted", "deferred"), (
                f"span {span.get('name')!r} must declare emission_status "
                "as 'emitted' or 'deferred'"
            )

    def test_deferred_spans_carry_a_reason(self, fixture_data: dict) -> None:
        for span in _all_spans(fixture_data):
            if span.get("emission_status") == "deferred":
                assert span.get("deferred_reason"), (
                    f"deferred span {span.get('name')!r} must explain why via "
                    "deferred_reason"
                )

    def test_generate_content_span_is_deferred(self, fixture_data: dict) -> None:
        """The google.genai LLM-call span inside the task-mode leaf is the autopatch
        carry-forward classified in AH-PRD-13 §9 + trace-structure-spec.md §4.5.
        It must be 'deferred' — not 'emitted' — until a future Weave or google.genai
        release fixes the autopatch on ADK 2.0."""
        gen_content_spans = _find_spans_by_name(fixture_data, "generate_content")
        # The fixture includes the generate_content span as the deferred target.
        for span in gen_content_spans:
            assert span.get("emission_status") == "deferred", (
                "generate_content (google.genai LLM-call) span must be "
                "emission_status='deferred' — this is the autopatch carry-forward "
                "per AH-PRD-13 §9 and docs/trace-structure-spec.md §4.5. If a "
                "future patch makes it emit, flip to 'emitted', update "
                "test_emitted_spans_are_exactly_the_runtime_set, and remove the "
                "§4.5 carry-forward note."
            )

    def test_emitted_spans_are_exactly_the_runtime_set(
        self, fixture_data: dict
    ) -> None:
        """Lock the emitted set to what the runtime writes today after AH-115/116.

        Emitted: root (ken_e), the AH-75 transfer_to_agent action, the specialist
        span (google_analytics_specialist), the worker span
        (google_analytics_specialist_worker), the request_task_google_search tool
        span (emitted by the task-mode dispatch mechanism), the google_search_agent
        task-mode leaf, and the two representative google_search tool invocations.

        Deferred: the google.genai LLM-call span (autopatch carry-forward) and the
        review-loop reviewer span (no agent callbacks on the reviewer LlmAgent).

        Changing this set requires a matching runtime + spec change
        (docs/trace-structure-spec.md §17 + AH-PRD-15 §7.2).
        """
        emitted = {
            s["name"]
            for s in _all_spans(fixture_data)
            if s.get("emission_status") == "emitted"
        }
        deferred = {
            s["name"]
            for s in _all_spans(fixture_data)
            if s.get("emission_status") == "deferred"
        }
        expected_emitted = {
            "ken_e",
            "transfer_to_agent",
            "google_analytics_specialist",
            "google_analytics_specialist_worker",
            "request_task_google_search",
            "google_search_agent",
            "google_search",
        }
        expected_deferred = {
            "generate_content",
            "google_analytics_specialist_review_reviewer",
        }
        assert emitted == expected_emitted, (
            f"Emitted span set does not match the expected runtime set.\n"
            f"  Expected: {sorted(expected_emitted)}\n"
            f"  Got:      {sorted(emitted)}\n"
            "If the runtime now emits additional spans (e.g. generate_content "
            "autopatch was fixed), update this test, the fixture, and "
            "docs/trace-structure-spec.md §17 together."
        )
        assert deferred == expected_deferred, (
            f"Deferred span set does not match the expected set.\n"
            f"  Expected: {sorted(expected_deferred)}\n"
            f"  Got:      {sorted(deferred)}\n"
            "If a deferred span now emits (e.g. generate_content), move it to "
            "the expected_emitted set above after verifying the runtime change."
        )
