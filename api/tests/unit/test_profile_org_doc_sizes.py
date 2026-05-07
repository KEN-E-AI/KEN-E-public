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

import pytest

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


# ---------------------------------------------------------------------------
# Per-org loop-body silent-swallow guards (DM-35 PO verification, 2026-05-07)
#
# The per-org `try/except` at main():317 must catch processing errors and log
# a warning per org, while the surviving orgs still produce a valid summary.
# These tests exercise the loop-body's defensive paths directly via a stub
# generator, decoupled from `firestore.Client` initialisation.
# ---------------------------------------------------------------------------


def _profile_org_loop_body(
    org_id: str, doc_dict: dict[str, object]
) -> tuple[mod.OrgProfile | None, list[int]]:
    """Mirror of main()'s inner loop body for direct unit testing.

    Returns (profile, per_org_account_byte_sizes). On exception the per-org
    handler in main() logs a warning and skips — this helper raises so the
    test can assert error propagation; main() wraps it.
    """
    byte_size = mod.approx_doc_bytes(doc_dict)
    accounts_map = doc_dict.get("accounts", {})
    if not isinstance(accounts_map, dict):
        accounts_map = {}
    account_count = len(accounts_map)
    per_acc_sizes: list[int] = []
    org_max_funnel_depth = 0
    for _account_id, acc_data in accounts_map.items():
        if not isinstance(acc_data, dict):
            acc_data = {}
        acc_size = mod.approx_doc_bytes(acc_data)
        per_acc_sizes.append(acc_size)
        funnels = acc_data.get("funnels", {})
        if not isinstance(funnels, dict):
            funnels = {}
        depth = mod.max_funnel_depth(funnels)
        if depth > org_max_funnel_depth:
            org_max_funnel_depth = depth
    max_account_byte_size = max(per_acc_sizes) if per_acc_sizes else 0
    profile = mod.OrgProfile(
        org_id=org_id,
        byte_size=byte_size,
        account_count=account_count,
        max_account_byte_size=max_account_byte_size,
        max_funnel_depth=org_max_funnel_depth,
    )
    return profile, per_acc_sizes


class TestLoopBodyEdgeCases:
    """Defensive paths in the per-org loop body that drive the Style A/B decision.

    A regression that crashes inside the loop body gets swallowed by the
    `try/except` at main():317 and silently drops the org — biasing every
    percentile and threshold counter the architectural decision depends on.
    """

    def test_org_without_accounts_field_yields_zero_accounts(self) -> None:
        # Regression target: replacing `.get("accounts", {})` with `["accounts"]`
        # would crash and silently drop the org.
        profile, per_acc = _profile_org_loop_body(
            "org_no_accounts_field", {"name": "no_accounts_org"}
        )
        assert profile is not None
        assert profile.account_count == 0
        assert profile.max_account_byte_size == 0
        assert profile.max_funnel_depth == 0
        assert per_acc == []

    def test_org_with_non_dict_accounts_value_coerces_to_empty(self) -> None:
        # Regression target: removing the `isinstance(accounts_map, dict)` guard
        # would crash on `accounts_map.items()` if `accounts` is None / list / str.
        for bad_accounts in (None, ["not", "a", "dict"], "scalar_string", 42):
            profile, _ = _profile_org_loop_body(
                "org_bad_accounts_type", {"accounts": bad_accounts}
            )
            assert profile is not None, f"crashed on accounts={bad_accounts!r}"
            assert profile.account_count == 0

    def test_org_with_non_dict_account_value_survives(self) -> None:
        # Regression target: removing the per-account `isinstance(acc_data, dict)`
        # guard would crash on `acc_data.get(...)` when an account_id maps to
        # None/list/string.
        profile, per_acc = _profile_org_loop_body(
            "org_mixed",
            {
                "accounts": {
                    "acc_x": None,
                    "acc_y": "broken",
                    "acc_z": [1, 2, 3],
                    "acc_real": {"funnels": {"a": {"b": {}}}},
                }
            },
        )
        assert profile is not None
        assert profile.account_count == 4
        # Three coerced-to-{} accounts each contribute approx_doc_bytes({}) == 2.
        # The real account's byte size dominates the max.
        assert profile.max_account_byte_size > 0
        assert profile.max_funnel_depth >= 1

    def test_main_swallows_per_org_exception_and_continues(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A bug inside the loop body must not abort the whole profile.

        Stubs `_iter_org_docs` to yield three docs, the middle one of which
        triggers a ValueError when its bytes are measured. The loop must:
          - log a WARNING citing the failing org_id
          - skip the failing org (no entry in summary.orgs)
          - keep the surviving orgs and emit a valid ProfileSummary
        """
        good_a = {"accounts": {"a1": {}}}
        bad = {"accounts": {"trigger": {}}}  # marker
        good_b = {"accounts": {"b1": {}}}

        def stub_iter(_client: object) -> object:
            yield "org_good_a", good_a
            yield "org_bad", bad
            yield "org_good_b", good_b

        original_approx = mod.approx_doc_bytes

        def raise_on_bad(doc: dict[str, object]) -> int:
            if doc.get("accounts", {}).get("trigger") is not None:
                raise ValueError("intentional test failure")
            return original_approx(doc)

        # Stub Firestore client init so main() doesn't try to connect.
        class _StubClient:
            pass

        class _StubFirestoreModule:
            @staticmethod
            def Client(**_: object) -> "_StubClient":
                return _StubClient()

        import sys as _sys

        monkeypatch.setattr(mod, "_iter_org_docs", stub_iter)
        monkeypatch.setattr(mod, "approx_doc_bytes", raise_on_bad)
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "test-project")
        # main() uses argparse on sys.argv — clear pytest's args so it doesn't choke.
        monkeypatch.setattr(_sys, "argv", ["profile_org_doc_sizes"])
        monkeypatch.setitem(_sys.modules, "google.cloud", type(_sys)("google.cloud"))
        monkeypatch.setitem(
            _sys.modules, "google.cloud.firestore", _StubFirestoreModule
        )
        # Capture stdout to retrieve the JSON summary block.
        import io as _io
        from contextlib import redirect_stdout as _redirect_stdout

        buf = _io.StringIO()
        with caplog.at_level("WARNING"), _redirect_stdout(buf):
            exit_code = mod.main()

        assert exit_code == mod.EXIT_SUCCESS
        # Warning log must mention the offending org_id (operator must be able
        # to grep logs to find which org dropped out).
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("org_bad" in r.getMessage() for r in warnings), (
            f"no warning mentions 'org_bad'; got: {[r.getMessage() for r in warnings]}"
        )
        # The two good orgs survive in the summary.
        stdout = buf.getvalue()
        json_block_start = stdout.find("=== JSON SUMMARY ===")
        assert json_block_start >= 0, "JSON SUMMARY delimiter not in stdout"
        summary_json = stdout[json_block_start:].split("\n", 2)[2]
        parsed = json.loads(summary_json)
        org_ids = {o["org_id"] for o in parsed["orgs"]}
        assert org_ids == {"org_good_a", "org_good_b"}, (
            f"expected only the two good orgs in summary, got: {org_ids}"
        )
        assert parsed["total_orgs"] == 2
