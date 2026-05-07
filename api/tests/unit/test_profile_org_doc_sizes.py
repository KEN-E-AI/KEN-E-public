"""Unit tests for profile_org_doc_sizes.py pure-function helpers and Pydantic models.

Covers (per task spec):
- approx_doc_bytes: empty dict, known string, nested vs flat, non-serialisable value
- max_funnel_depth: empty dict, non-dict argument, single-level, two-level, deep PRD shape
- percentile: empty list, single element, two-element boundary values, interpolation
- Pydantic round-trip: OrgProfile and ProfileSummary
- CLI: missing GOOGLE_CLOUD_PROJECT_ID exits with code 2 and prints env-var name to stderr
"""

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — add api/scripts/ so the module is importable without install.
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import profile_org_doc_sizes as mod  # noqa: E402
from profile_org_doc_sizes import (  # noqa: E402
    OrgProfile,
    ProfileSummary,
    approx_doc_bytes,
    max_funnel_depth,
    percentile,
)

# ---------------------------------------------------------------------------
# approx_doc_bytes
# ---------------------------------------------------------------------------


class TestApproxDocBytes:
    def test_empty_dict_returns_small_positive_integer(self) -> None:
        result = approx_doc_bytes({})
        # json.dumps({}) == '{}' → 2 bytes
        assert result > 0
        assert result < 10

    def test_known_payload_returns_correct_byte_count(self) -> None:
        d = {"key": "value"}
        expected = len(json.dumps(d, default=str).encode("utf-8"))
        assert approx_doc_bytes(d) == expected

    def test_nested_dict_larger_than_flat_dict(self) -> None:
        # A single-key flat dict is small; a deeply nested dict of equal "content"
        # adds many extra braces and key strings and is therefore larger.
        flat = {"key": "hello"}
        nested = {"a": {"b": {"c": {"d": "hello"}}}}
        assert approx_doc_bytes(nested) > approx_doc_bytes(flat)

    def test_datetime_value_does_not_raise(self) -> None:
        """Non-JSON-serialisable types (e.g. datetime) must be handled by default=str."""
        import datetime

        d = {"created_at": datetime.datetime(2025, 1, 1, 12, 0, 0)}
        # Should not raise; default=str converts datetime to its string representation
        result = approx_doc_bytes(d)
        assert result > 0


# ---------------------------------------------------------------------------
# max_funnel_depth
# ---------------------------------------------------------------------------


class TestMaxFunnelDepth:
    def test_empty_dict_returns_zero(self) -> None:
        assert max_funnel_depth({}) == 0

    def test_none_argument_returns_zero(self) -> None:
        assert max_funnel_depth(None) == 0  # type: ignore[arg-type]

    def test_string_argument_returns_zero(self) -> None:
        assert max_funnel_depth("not a dict") == 0  # type: ignore[arg-type]

    def test_single_level_dict_returns_one(self) -> None:
        # {"step1": {}} — one level of nesting
        assert max_funnel_depth({"step1": {}}) == 1

    def test_two_level_dict_returns_two(self) -> None:
        # {"org": {"1": {}}} — depth 1 at "org", depth 2 at "1", then {} is empty
        # so _depth returns 2 (current=2 when it hits the empty inner dict).
        funnels = {"org": {"1": {}}}
        assert max_funnel_depth(funnels) == 2

    def test_prd_example_shape_returns_at_least_four(self) -> None:
        """PRD §5 shape: big_bets path is the deepest branch.

        The algorithm calls _depth(funnels, 0) which increments current on each
        non-empty dict layer:
          funnels(0) → big_bets(1) → bet_1(2) → 1(3) → channels(4) → ch1(5) → tactics(6) → t1(7)
          t1 maps to {} (empty) so recursion stops and returns 7.
        """
        funnels = {
            "organization": {"1": {}, "2": {}},
            "big_bets": {
                "bet_1": {"1": {"channels": {"ch1": {"tactics": {"t1": {}}}}}}
            },
        }
        depth = max_funnel_depth(funnels)
        assert depth >= 4
        assert depth == 7


# ---------------------------------------------------------------------------
# percentile
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_empty_list_returns_zero(self) -> None:
        assert percentile([], 0.95) == 0

    def test_single_element_any_p_returns_that_element(self) -> None:
        assert percentile([100], 0.00) == 100
        assert percentile([100], 0.50) == 100
        assert percentile([100], 1.00) == 100

    def test_two_elements_p50_returns_midpoint(self) -> None:
        assert percentile([0, 100], 0.50) == 50

    def test_two_elements_p0_returns_minimum(self) -> None:
        assert percentile([0, 100], 0.00) == 0

    def test_two_elements_p100_returns_maximum(self) -> None:
        assert percentile([0, 100], 1.00) == 100

    def test_three_elements_p95_linear_interpolation(self) -> None:
        # sorted: [0, 50, 100]; n=3; idx = 0.95 * 2 = 1.90
        # lo=1 (value=50), hi=2 (value=100), frac=0.90
        # result = int(50 + 0.90 * (100 - 50)) = int(50 + 45) = 95
        assert percentile([0, 50, 100], 0.95) == 95

    def test_p95_result_consistent_with_statistics_quantiles(self) -> None:
        """Implementation should agree with statistics.quantiles to within 1%."""
        values = list(range(1, 101))  # 1..100, known distribution
        result = percentile(values, 0.95)
        # statistics.quantiles with n=100 gives cut points; index 94 is P95
        stdlib_p95 = statistics.quantiles(values, n=100)[94]
        tolerance = max(1, stdlib_p95 * 0.01)
        assert abs(result - stdlib_p95) <= tolerance


# ---------------------------------------------------------------------------
# Pydantic round-trip
# ---------------------------------------------------------------------------


class TestOrgProfileRoundTrip:
    def test_model_dump_json_and_validate_json(self) -> None:
        org = OrgProfile(
            org_id="org_1",
            byte_size=1234,
            account_count=2,
            max_account_byte_size=600,
            max_funnel_depth=3,
        )
        serialised = org.model_dump_json()
        restored = OrgProfile.model_validate_json(serialised)
        assert restored == org


class TestProfileSummaryRoundTrip:
    def _make_summary(self) -> ProfileSummary:
        org_a = OrgProfile(
            org_id="org_a",
            byte_size=100_000,
            account_count=1,
            max_account_byte_size=80_000,
            max_funnel_depth=2,
        )
        org_b = OrgProfile(
            org_id="org_b",
            byte_size=200_000,
            account_count=3,
            max_account_byte_size=150_000,
            max_funnel_depth=4,
        )
        return ProfileSummary(
            total_orgs=2,
            total_accounts=4,
            total_size_p50=150_000,
            total_size_p95=190_000,
            total_size_p99=199_000,
            per_account_size_p50=80_000,
            per_account_size_p95=145_000,
            per_account_size_p99=149_000,
            orgs_over_500_kib=0,
            orgs_over_750_kib=0,
            accounts_over_500_kib=0,
            accounts_over_750_kib=0,
            max_funnel_depth_overall=4,
            byte_size_methodology=mod.BYTE_SIZE_METHODOLOGY,
            orgs=[org_a, org_b],
        )

    def test_model_dump_json_produces_valid_json_with_total_orgs(self) -> None:
        summary = self._make_summary()
        raw = summary.model_dump_json(indent=2)
        parsed = json.loads(raw)
        assert parsed["total_orgs"] == 2

    def test_model_dump_json_round_trips_via_model_validate_json(self) -> None:
        summary = self._make_summary()
        restored = ProfileSummary.model_validate_json(summary.model_dump_json())
        assert restored.total_orgs == 2
        assert len(restored.orgs) == 2
        assert restored.orgs[0].org_id == "org_a"
        assert restored.orgs[1].org_id == "org_b"


# ---------------------------------------------------------------------------
# CLI integration — missing GOOGLE_CLOUD_PROJECT_ID → exit code 2
# ---------------------------------------------------------------------------


class TestCliMissingEnvVar:
    def test_exits_with_code_2_when_project_id_missing(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GOOGLE_CLOUD_PROJECT_ID"}
        result = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(Path(__file__).parent.parent.parent),
                "python",
                "scripts/profile_org_doc_sizes.py",
            ],
            env=env,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 2
        assert b"GOOGLE_CLOUD_PROJECT_ID" in result.stderr
