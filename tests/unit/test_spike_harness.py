"""Unit tests for scripts/spike/sandbox_test_harness.py pure helpers.

These tests cover the three verification layers added in Wave 2.5 (AC-1, AC-2,
AC-3) plus the status-priority aggregation logic. They do NOT call any Vertex
AI API — the tested functions are pure Python with no external I/O.
"""

from __future__ import annotations

import os

from scripts.spike.sandbox_test_harness import (
    _STATUS_SEVERITY,
    _check_script_tampering,
    _sha256_short,
    _status_severity_key,
    _worst_status,
)

# ---------------------------------------------------------------------------
# _sha256_short
# ---------------------------------------------------------------------------


class TestSha256Short:
    def test_returns_12_chars(self) -> None:
        result = _sha256_short("hello")
        assert len(result) == 12

    def test_all_hex_chars(self) -> None:
        result = _sha256_short("test input")
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_inputs_differ(self) -> None:
        assert _sha256_short("a") != _sha256_short("b")


# ---------------------------------------------------------------------------
# _status_severity_key and _worst_status
# ---------------------------------------------------------------------------


class TestStatusSeverity:
    def test_script_tampered_is_worst(self) -> None:
        key = _status_severity_key(
            "error: script_tampered (expected=abc, observed=def, diff=/tmp/x.diff)"
        )
        assert key == 0

    def test_ok_maps_above_all_named_errors(self) -> None:
        ok_key = _status_severity_key("ok")
        # "ok" is not in _STATUS_SEVERITY so it maps to len(_STATUS_SEVERITY)
        assert ok_key == len(_STATUS_SEVERITY)

    def test_named_statuses_ordered(self) -> None:
        keys = [_status_severity_key(f"error: {s}") for s in _STATUS_SEVERITY]
        assert keys == sorted(keys)

    def test_executor_outcome_is_named_and_ordered(self) -> None:
        key = _status_severity_key("error: executor outcome OUTCOME_ERROR")
        # Must be in _STATUS_SEVERITY, not the generic fallback bucket
        assert key < len(_STATUS_SEVERITY)

    def test_unknown_error_treated_as_medium_severity(self) -> None:
        key = _status_severity_key("error (SomeException): oops")
        # Falls to the fallback bucket — same key as "ok", but _worst_status
        # pre-filters "ok" so the two never collide in aggregation.
        assert key == len(_STATUS_SEVERITY)

    def test_executor_outcome_worse_than_generic_exception(self) -> None:
        outcome_key = _status_severity_key("error: executor outcome OUTCOME_ERROR")
        generic_key = _status_severity_key("error (SomeException): oops")
        assert outcome_key < generic_key


class TestWorstStatus:
    def test_all_ok_returns_ok(self) -> None:
        assert _worst_status("ok", "ok", "ok") == "ok"

    def test_single_non_ok_returned(self) -> None:
        result = _worst_status("ok", "error: agent emitted no executable_code", "ok")
        assert result == "error: agent emitted no executable_code"

    def test_script_tampered_beats_text_leakage(self) -> None:
        result = _worst_status(
            "error: agent emitted text alongside executable_code",
            "error: script_tampered (expected=abc, observed=xyz, diff=/tmp/x.diff)",
        )
        assert "script_tampered" in result

    def test_script_tampered_beats_all_named_statuses(self) -> None:
        all_statuses = [f"error: {s}" for s in _STATUS_SEVERITY]
        result = _worst_status(*all_statuses)
        assert "script_tampered" in result

    def test_canary_verification_beats_no_executable_code(self) -> None:
        result = _worst_status(
            "error: canary_verification_failed: sha256_mismatch",
            "error: agent emitted no executable_code",
        )
        assert "canary_verification_failed" in result

    def test_empty_returns_ok(self) -> None:
        assert _worst_status() == "ok"

    def test_single_ok_returns_ok(self) -> None:
        assert _worst_status("ok") == "ok"


# ---------------------------------------------------------------------------
# _check_script_tampering
# ---------------------------------------------------------------------------


class TestCheckScriptTampering:
    def test_no_captured_parts_returns_none(self) -> None:
        result = _check_script_tampering("print('hello')\n", [])
        assert result is None

    def test_matching_part_returns_none(self) -> None:
        script = "print('hello')\n"
        result = _check_script_tampering(script, [script])
        assert result is None

    def test_matching_multiple_parts_returns_none(self) -> None:
        script = "x = 1\nprint(x)\n"
        result = _check_script_tampering(script, [script, script])
        assert result is None

    def test_tampered_part_returns_error_string(self) -> None:
        original = "print(2**73 - 1)\n"
        tampered = "print(2**63 - 1)\n"
        result = _check_script_tampering(original, [tampered])
        assert result is not None
        assert "script_tampered" in result

    def test_error_includes_sha256_shorts(self) -> None:
        original = "x = 'original'\n"
        tampered = "x = 'tampered'\n"
        result = _check_script_tampering(original, [tampered])
        assert result is not None
        assert "expected=" in result
        assert "observed=" in result

    def test_error_includes_diff_path(self) -> None:
        result = _check_script_tampering("a = 1\n", ["b = 2\n"])
        assert result is not None
        assert "diff=" in result
        # Diff sidecar should be written to a real file
        diff_path = result.split("diff=")[-1].rstrip(")")
        assert os.path.exists(diff_path), f"Diff sidecar not found: {diff_path}"

    def test_first_mismatch_wins(self) -> None:
        script = "print('ok')\n"
        good = script
        bad = "print('tampered')\n"
        # First captured part matches; second does not — should still flag
        result = _check_script_tampering(script, [good, bad])
        assert result is not None
        assert "script_tampered" in result

    def test_whitespace_difference_is_tampered(self) -> None:
        # Even trailing newline difference counts
        result = _check_script_tampering("print('hi')", ["print('hi')\n"])
        assert result is not None
        assert "script_tampered" in result

    def test_empty_string_from_none_code_field_is_tampered(self) -> None:
        # When ec.code is None, the harness substitutes "" — guaranteed ≠ any
        # real script (which can never be empty after _validate_script).
        result = _check_script_tampering("print('hi')\n", [""])
        assert result is not None
        assert "script_tampered" in result
