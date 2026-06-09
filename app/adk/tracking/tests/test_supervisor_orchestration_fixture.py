"""Schema-conformance assertions for the supervisor-orchestration staging fixture.

Validates that supervisor_orchestration_trace.json satisfies the AH-PRD-05 trace
contract documented in docs/trace-structure-spec.md and
docs/design/components/agentic-harness/projects/AH-PRD-05-trace-contract-diff.md.

The fixture models §2.2 of the contract diff: one sequential task_delegation
(task-mode call-and-return), a fanout span with two parallel task_delegation
children (ctx.run_node + asyncio.gather), and a synthesis task_delegation whose
query references upstream result keys.

Every supervisor-specific span (task_delegation, fanout, mode='task' specialist
runs) carries emission_status='deferred' + a deferred_reason referencing AH-PRD-05.
The root ken_e span carries emission_status='emitted' since that behaviour is
unchanged. TestEmissionStatus pins that labelling so the fixture cannot silently
claim to emit something the runtime does not.

The node_path attribute in each task_delegation summary is sourced verbatim from
the AH-99 probe-1 / probe-4 evidence (docs/spike-adk2-supervisor-orchestration-live.md
§4): task-mode events carry 'coordinator@1/task_specialist@…'; fan-out branch events
carry 'specialist_a@1' / 'specialist_b@1'.

MER-E extractor authors should run this test to confirm that the fixture is a
valid target for validation tooling before updating extractor queries, and must
treat 'deferred' spans as absent in live traces until AH-PRD-05 ships.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.adk.tracking.compliance import validate_trace_compliance

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "supervisor_orchestration_trace.json"
)

_SPECIALIST_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# node_path format: '<agent_name>@<index>' or '<agent_name>@<index>/<agent_name>@<id>'
# sourced from AH-99 probe-1/probe-4 evidence in docs/spike-adk2-supervisor-orchestration-live.md §4
_NODE_PATH_RE = re.compile(r"^[a-z][a-z0-9_]+@[\w-]+(\/[a-z][a-z0-9_]+@[\w-]+)*$")

_TASK_DELEGATION_ATTRS = (
    "task_id",
    "assignee",
    "query",
    "criteria",
    "task_status",
    "cache_hit",
    "node_path",
)
_FANOUT_ATTRS = (
    "task_ids",
    "branch_count",
    "all_succeeded",
    "node_path",
)


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
            "Run AH-125 implementation before executing these tests."
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

    def test_no_delegate_to_specialist_span_anywhere(self, fixture_data: dict) -> None:
        """AH-75: the delegate_to_specialist function tool was removed. No span
        anywhere in the tree should carry that name."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "delegate_to_specialist" not in every_name, (
            "delegate_to_specialist span appeared in the fixture but the "
            "function tool was deleted in AH-75."
        )

    def test_no_dispatch_to_star_span_anywhere(self, fixture_data: dict) -> None:
        """Pre-AH-75 dispatch_to_* spans must not appear in a supervisor fixture."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        for name in every_name:
            assert not name.startswith("dispatch_to_"), (
                f"dispatch_to_* span {name!r} appeared in the fixture — these are "
                "pre-AH-75 artefacts and must not appear in supervisor traces."
            )

    def test_supervisor_orchestration_feature_flag_is_true(
        self, fixture_data: dict
    ) -> None:
        """The fixture must represent a supervisor-orchestration trace
        (supervisor_orchestration: true in feature_flags), so MER-E extractor
        authors can use the feature flag to discriminate trace modes."""
        flags = fixture_data["metadata"].get("feature_flags", {})
        assert flags.get("supervisor_orchestration") is True, (
            "Fixture must represent a supervisor-orchestration trace "
            "(supervisor_orchestration: true in feature_flags)"
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

    def test_root_has_coordinator_children(self, root_span: dict) -> None:
        """The supervisor coordinator runs as sub-spans under the root ken_e span.
        Expect at least one task_delegation or fanout child."""
        children = root_span.get("children", [])
        coordinator_children = [
            c
            for c in children
            if c.get("name") in ("task_delegation", "fanout")
        ]
        assert coordinator_children, (
            "Root agent span must include at least one task_delegation or fanout "
            "child — those are the supervisor-orchestration dispatch spans."
        )

    def test_root_emission_status_is_emitted(self, root_span: dict) -> None:
        assert root_span.get("emission_status") == "emitted", (
            "Root ken_e span must be emission_status='emitted' — its behaviour "
            "is unchanged by the supervisor model."
        )


# ---------------------------------------------------------------------------
# task_delegation spans — §3.1 attribute contract
# ---------------------------------------------------------------------------


class TestTaskDelegationSpans:
    @pytest.fixture
    def task_delegation_spans(self, fixture_data: dict) -> list[dict]:
        spans = _find_spans_by_name(fixture_data, "task_delegation")
        assert spans, "fixture must contain at least one task_delegation span"
        return spans

    def test_every_task_delegation_has_required_attributes(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            summary = span.get("summary", {})
            for attr in _TASK_DELEGATION_ATTRS:
                assert attr in summary, (
                    f"task_delegation span is missing required attribute "
                    f"'{attr}' (task_id={summary.get('task_id')!r})"
                )

    def test_task_id_is_non_empty_string(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            task_id = span["summary"]["task_id"]
            assert isinstance(task_id, str) and task_id, (
                f"task_id must be a non-empty string, got {task_id!r}"
            )

    def test_assignee_matches_specialist_name_regex(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            assignee = span["summary"]["assignee"]
            assert isinstance(assignee, str), (
                f"assignee must be a str, got {type(assignee).__name__!r}"
            )
            assert _SPECIALIST_NAME_RE.fullmatch(assignee), (
                f"assignee {assignee!r} must match ^[a-z][a-z0-9_]{{0,63}}$ "
                "(the specialist doc_id validation regex)"
            )

    def test_query_is_non_empty_string(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            query = span["summary"]["query"]
            assert isinstance(query, str) and query

    def test_criteria_is_string(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            criteria = span["summary"]["criteria"]
            assert isinstance(criteria, str)

    def test_task_status_is_valid(
        self, task_delegation_spans: list[dict]
    ) -> None:
        valid_statuses = {"completed", "failed"}
        for span in task_delegation_spans:
            status = span["summary"]["task_status"]
            assert status in valid_statuses, (
                f"task_status must be one of {valid_statuses}, got {status!r}"
            )

    def test_cache_hit_is_bool(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            cache_hit = span["summary"]["cache_hit"]
            assert isinstance(cache_hit, bool), (
                f"cache_hit must be bool, got {type(cache_hit).__name__!r}"
            )

    def test_node_path_is_non_empty_string(
        self, task_delegation_spans: list[dict]
    ) -> None:
        for span in task_delegation_spans:
            node_path = span["summary"]["node_path"]
            assert isinstance(node_path, str) and node_path, (
                f"node_path must be a non-empty string (task_id="
                f"{span['summary'].get('task_id')!r})"
            )

    def test_node_path_matches_adk_format(
        self, task_delegation_spans: list[dict]
    ) -> None:
        """node_path must match the ADK 2.0 path format observed in AH-99 probes:
        '<agent>@<index>' for fan-out branches, or
        '<agent>@<index>/<agent>@<id>' for nested task-mode paths."""
        for span in task_delegation_spans:
            node_path = span["summary"]["node_path"]
            assert _NODE_PATH_RE.fullmatch(node_path), (
                f"node_path {node_path!r} does not match expected ADK 2.0 format "
                f"(task_id={span['summary'].get('task_id')!r}). "
                "Expected: '<agent>@<id>' or '<agent>@<id>/<agent>@<id>' — "
                "see docs/spike-adk2-supervisor-orchestration-live.md §4."
            )

    def test_fixture_has_sequential_task_delegation(self, fixture_data: dict) -> None:
        """The fixture must include at least one sequential (non-fan-out) task_delegation
        as a direct child of the root span — the task-mode call-and-return pattern."""
        root_children = fixture_data["spans"][0].get("children", [])
        direct_delegations = [
            c for c in root_children if c.get("name") == "task_delegation"
        ]
        assert direct_delegations, (
            "Fixture must include at least one task_delegation as a direct child "
            "of the root span (sequential task-mode delegation)."
        )

    def test_synthesis_task_delegation_references_upstream_result_keys(
        self, task_delegation_spans: list[dict]
    ) -> None:
        """At least one task_delegation must reference an upstream result key in
        its query or criteria, demonstrating the fan-in synthesis pattern."""
        synthesis_candidates = [
            s
            for s in task_delegation_spans
            if "_result" in s["summary"].get("query", "")
            or "_result" in s["summary"].get("criteria", "")
        ]
        assert synthesis_candidates, (
            "Fixture must include at least one synthesis task_delegation whose "
            "query or criteria references an upstream result key (e.g. "
            "'task_002_performance_data_result'). This demonstrates the fan-in pattern."
        )


# ---------------------------------------------------------------------------
# fanout span — §3.2 attribute contract
# ---------------------------------------------------------------------------


class TestFanoutSpan:
    @pytest.fixture
    def fanout_spans(self, fixture_data: dict) -> list[dict]:
        spans = _find_spans_by_name(fixture_data, "fanout")
        assert spans, "fixture must contain at least one fanout span"
        return spans

    def test_every_fanout_has_required_attributes(
        self, fanout_spans: list[dict]
    ) -> None:
        for span in fanout_spans:
            summary = span.get("summary", {})
            for attr in _FANOUT_ATTRS:
                assert attr in summary, (
                    f"fanout span is missing required attribute '{attr}'"
                )

    def test_task_ids_is_list_of_strings(self, fanout_spans: list[dict]) -> None:
        for span in fanout_spans:
            task_ids = span["summary"]["task_ids"]
            assert isinstance(task_ids, list) and task_ids, (
                "task_ids must be a non-empty list"
            )
            for tid in task_ids:
                assert isinstance(tid, str) and tid

    def test_branch_count_matches_task_ids_length(
        self, fanout_spans: list[dict]
    ) -> None:
        for span in fanout_spans:
            summary = span["summary"]
            assert summary["branch_count"] == len(summary["task_ids"]), (
                f"branch_count ({summary['branch_count']}) must equal "
                f"len(task_ids) ({len(summary['task_ids'])})"
            )

    def test_all_succeeded_is_bool(self, fanout_spans: list[dict]) -> None:
        for span in fanout_spans:
            all_succeeded = span["summary"]["all_succeeded"]
            assert isinstance(all_succeeded, bool), (
                f"all_succeeded must be bool, got {type(all_succeeded).__name__!r}"
            )

    def test_node_path_is_non_empty_string(self, fanout_spans: list[dict]) -> None:
        for span in fanout_spans:
            node_path = span["summary"]["node_path"]
            assert isinstance(node_path, str) and node_path

    def test_node_path_matches_adk_format(self, fanout_spans: list[dict]) -> None:
        """fanout node_path must match the ADK 2.0 path format."""
        for span in fanout_spans:
            node_path = span["summary"]["node_path"]
            assert _NODE_PATH_RE.fullmatch(node_path), (
                f"fanout node_path {node_path!r} does not match expected ADK 2.0 format. "
                "Expected: '<agent>@<id>' (e.g., 'coordinator@1') — "
                "see docs/spike-adk2-supervisor-orchestration-live.md §4."
            )

    def test_fanout_task_ids_match_child_task_delegation_task_ids(
        self, fanout_spans: list[dict]
    ) -> None:
        """task_ids in the fanout summary must match the task_id values of the
        child task_delegation spans."""
        for span in fanout_spans:
            expected_ids = set(span["summary"]["task_ids"])
            child_task_delegations = [
                c for c in span.get("children", []) if c.get("name") == "task_delegation"
            ]
            child_ids = {c["summary"]["task_id"] for c in child_task_delegations}
            assert expected_ids == child_ids, (
                f"fanout.task_ids {expected_ids} must equal the set of child "
                f"task_delegation task_ids {child_ids}"
            )

    def test_fanout_has_at_least_two_parallel_branches(
        self, fanout_spans: list[dict]
    ) -> None:
        """A fan-out group is only meaningful with ≥2 parallel branches."""
        for span in fanout_spans:
            assert span["summary"]["branch_count"] >= 2, (
                f"fanout span must have branch_count >= 2, "
                f"got {span['summary']['branch_count']}"
            )


# ---------------------------------------------------------------------------
# Synthesis task_delegation — depends_on + result_key references
# ---------------------------------------------------------------------------


class TestSynthesisDelegation:
    def test_synthesis_task_delegation_exists(self, fixture_data: dict) -> None:
        """The fixture must contain a synthesis task_delegation (one that depends on
        upstream fan-out results, identified by result_key references in query/criteria)."""
        task_delegations = _find_spans_by_name(fixture_data, "task_delegation")
        synthesis = [
            s
            for s in task_delegations
            if "_result" in s["summary"].get("query", "")
            or "_result" in s["summary"].get("criteria", "")
        ]
        assert synthesis, (
            "Fixture must contain a synthesis task_delegation whose query or "
            "criteria references at least one upstream result_key (e.g. "
            "'task_002_performance_data_result'). This validates the fan-in pattern."
        )

    def test_synthesis_has_distinct_task_id(self, fixture_data: dict) -> None:
        """The synthesis delegation must have its own unique task_id."""
        task_delegations = _find_spans_by_name(fixture_data, "task_delegation")
        synthesis = [
            s
            for s in task_delegations
            if "_result" in s["summary"].get("query", "")
            or "_result" in s["summary"].get("criteria", "")
        ]
        for s in synthesis:
            task_id = s["summary"]["task_id"]
            assert task_id, "synthesis task_delegation must have a non-empty task_id"
            others = [
                t["summary"]["task_id"]
                for t in task_delegations
                if t is not s
            ]
            assert task_id not in others, (
                f"synthesis task_id {task_id!r} must be unique across all task_delegations"
            )


# ---------------------------------------------------------------------------
# Emission-status honesty contract
#
# Every supervisor-specific span (task_delegation, fanout, mode='task'
# specialist runs) must be tagged 'deferred'. Only the root ken_e span is
# 'emitted'. This lock prevents the fixture from advertising runtime emission
# that AH-PRD-05 has not yet shipped.
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

    def test_only_root_ken_e_span_is_emitted(self, fixture_data: dict) -> None:
        """Lock the emitted set to the root ken_e span only. All supervisor-specific
        spans (task_delegation, fanout, mode='task' specialist runs) must be deferred
        until AH-PRD-05 ships. Changing this set requires a runtime + spec change."""
        emitted = {
            s["name"]
            for s in _all_spans(fixture_data)
            if s.get("emission_status") == "emitted"
        }
        assert emitted == {"ken_e"}, (
            f"Only 'ken_e' should be emitted in the supervisor fixture; "
            f"got emitted={emitted!r}. If the supervisor runtime now emits "
            "additional spans, update this test, the fixture, and "
            "trace-structure-spec.md together."
        )

    def test_all_task_delegation_spans_are_deferred(self, fixture_data: dict) -> None:
        for span in _find_spans_by_name(fixture_data, "task_delegation"):
            assert span.get("emission_status") == "deferred", (
                f"task_delegation span (task_id={span.get('summary', {}).get('task_id')!r}) "
                "must be emission_status='deferred' — AH-PRD-05 has not shipped yet."
            )

    def test_all_fanout_spans_are_deferred(self, fixture_data: dict) -> None:
        for span in _find_spans_by_name(fixture_data, "fanout"):
            assert span.get("emission_status") == "deferred", (
                "fanout span must be emission_status='deferred' — "
                "AH-PRD-05 has not shipped yet."
            )


# ---------------------------------------------------------------------------
# Retired-pattern guards (§4 of AH-PRD-05-trace-contract-diff.md)
#
# The execute_workflow / invoke_pipeline inner-Runner shape was the anti-pattern
# documented in AH-75 and explicitly named as retired in §4 of the trace-contract
# diff.  No span carrying either name must ever appear in a supervisor fixture.
# ---------------------------------------------------------------------------


class TestRetiredPatterns:
    """Lock §4 Retired Patterns: execute_workflow and invoke_pipeline span names
    must never appear in the supervisor fixture tree.

    These are the inner-Runner anti-patterns that silently discard sub-agent events
    (the AH-75 defect). Presence in the fixture would signal extractor authors to
    search for them, which would produce extractor bugs at runtime.
    """

    def test_no_execute_workflow_span_anywhere(self, fixture_data: dict) -> None:
        """execute_workflow spans must not appear anywhere in the fixture tree.
        This span name is a retired inner-Runner anti-pattern per §4 of
        AH-PRD-05-trace-contract-diff.md."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "execute_workflow" not in every_name, (
            "execute_workflow span appeared in the supervisor fixture — "
            "this is a retired inner-Runner anti-pattern per "
            "AH-PRD-05-trace-contract-diff.md §4 and must not be used."
        )

    def test_no_invoke_pipeline_span_anywhere(self, fixture_data: dict) -> None:
        """invoke_pipeline spans must not appear anywhere in the fixture tree.
        This span name is a retired inner-Runner anti-pattern per §4 of
        AH-PRD-05-trace-contract-diff.md."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "invoke_pipeline" not in every_name, (
            "invoke_pipeline span appeared in the supervisor fixture — "
            "this is a retired inner-Runner anti-pattern per "
            "AH-PRD-05-trace-contract-diff.md §4 and must not be used."
        )


# ---------------------------------------------------------------------------
# Isolated AgentTool leaf carry-forward (AH-121 re-plan, §3.3 of
# AH-PRD-05-trace-contract-diff.md)
#
# Built-in-tool leaves (google_search, numerical_analyst) stay AgentTool-isolated
# inside specialists.  AgentTool.run_async drops their inner events (#3984), so
# no inner grounded-search / code-exec spans appear in the supervisor fixture.
# This test class locks that boundary so MER-E cannot accidentally start expecting
# those spans from the supervisor path.
#
# The asserted tokens: "AgentTool" and "off-state sink" — stable substrings in
# the fixture description that acknowledge the carry-forward gap.  Matching
# substrings (not full sentences) guards against minor wording drift.
# ---------------------------------------------------------------------------


class TestIsolatedAgentToolLeafCarryForward:
    """Lock the AH-121 re-plan AC #3 boundary.

    The supervisor fixture's scope is coordinator → task_delegation → fanout.
    Isolated AgentTool leaves (google_search, numerical_analyst) live INSIDE
    specialists and are owned by the AH-PRD-15 google_search_task_mode_trace.json
    fixture — they must NOT appear inside the supervisor fixture tree.

    Additionally, the fixture's top-level description must acknowledge the
    carry-forward gap so MER-E reading the fixture sees it inline.
    """

    def test_no_google_search_task_mode_leaf_span(self, fixture_data: dict) -> None:
        """google_search task-mode-leaf spans must not appear in the supervisor
        fixture.  Those spans live in the AH-PRD-15-owned
        google_search_task_mode_trace.json fixture — not here."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "google_search" not in every_name, (
            "google_search span appeared in the supervisor fixture — "
            "AgentTool-isolated leaf spans belong in "
            "google_search_task_mode_trace.json (AH-PRD-15), not here. "
            "See AH-PRD-05-trace-contract-diff.md §3.3."
        )

    def test_no_numerical_analyst_task_mode_leaf_span(
        self, fixture_data: dict
    ) -> None:
        """numerical_analyst task-mode-leaf spans must not appear in the supervisor
        fixture.  Like google_search, this built-in-tool leaf stays AgentTool-isolated
        and its representation belongs in the AH-PRD-15-owned fixture, not here."""
        every_name = [s.get("name", "") for s in _all_spans(fixture_data)]
        assert "numerical_analyst" not in every_name, (
            "numerical_analyst span appeared in the supervisor fixture — "
            "AgentTool-isolated leaf spans belong in the AH-PRD-15-owned "
            "fixture, not here. See AH-PRD-05-trace-contract-diff.md §3.3."
        )

    def test_fixture_description_acknowledges_agentool_carry_forward(
        self, fixture_data: dict
    ) -> None:
        """The fixture's top-level description must contain the stable tokens
        'AgentTool' and 'off-state sink' to signal to MER-E readers that the
        isolated-leaf gap is intentional and documented.

        This is the MER-E carry-forward acknowledgment lock — not a schema
        constraint on the description format.  Stable tokens are used (not a
        full-sentence match) to guard against minor wording drift.
        """
        description = fixture_data.get("description", "")
        assert "AgentTool" in description, (
            "Fixture description must contain the token 'AgentTool' to "
            "acknowledge the AH-121 isolated-leaf carry-forward gap. "
            "See AH-PRD-05-trace-contract-diff.md §3.3."
        )
        assert "off-state sink" in description, (
            "Fixture description must contain the token 'off-state sink' to "
            "acknowledge that leaf usage_metadata is read from the AH-PRD-15 "
            "off-state sink, not from leaf-level events. "
            "See AH-PRD-05-trace-contract-diff.md §3.3."
        )
