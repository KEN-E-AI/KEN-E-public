"""Unit tests for scripts/spike/canary_verifier.py."""

from __future__ import annotations

import hashlib
import time

import pytest

from scripts.spike.canary_verifier import _BIG_INT_EXPECTED, verify_canary


def _make_stdout(
    time_ns: int | None = None,
    urandom_hex: str | None = None,
    sha256_proof: str | None = None,
    big_int_check: int | str | None = None,
    extra_lines: str = "",
) -> str:
    """Build a canary stdout string with controllable values."""
    ns = time_ns if time_ns is not None else time.time_ns()
    rand = bytes.fromhex(urandom_hex) if urandom_hex else b"\xab" * 32
    rand_hex = urandom_hex if urandom_hex is not None else rand.hex()
    payload = str(ns).encode() + b"|" + rand
    digest = (
        sha256_proof
        if sha256_proof is not None
        else hashlib.sha256(payload).hexdigest()
    )
    big_int = big_int_check if big_int_check is not None else _BIG_INT_EXPECTED
    return "\n".join(
        [
            f"time_ns={ns}",
            f"urandom_hex={rand_hex}",
            f"sha256_proof={digest}",
            f"big_int_check={big_int}",
            extra_lines,
        ]
    )


class TestVerifyCanaryPass:
    def test_valid_stdout_returns_verified(self) -> None:
        stdout = _make_stdout()
        ok, _reason = verify_canary(stdout)
        assert ok is True

    def test_extra_lines_ignored(self) -> None:
        stdout = _make_stdout(extra_lines="some_extra=value\nignore=this")
        ok, reason = verify_canary(stdout)
        assert ok is True
        assert reason == "verified"

    def test_order_independent_parsing(self) -> None:
        ns = time.time_ns()
        rand = b"\x01" * 32
        rand_hex = rand.hex()
        payload = str(ns).encode() + b"|" + rand
        digest = hashlib.sha256(payload).hexdigest()
        stdout = "\n".join(
            [
                f"sha256_proof={digest}",
                f"big_int_check={_BIG_INT_EXPECTED}",
                f"urandom_hex={rand_hex}",
                f"time_ns={ns}",
            ]
        )
        ok, _reason = verify_canary(stdout)
        assert ok is True


class TestVerifyCanaryMissingFields:
    @pytest.mark.parametrize(
        "missing", ["time_ns", "urandom_hex", "sha256_proof", "big_int_check"]
    )
    def test_missing_field_returns_false(self, missing: str) -> None:
        lines = _make_stdout().splitlines()
        lines = [ln for ln in lines if not ln.startswith(f"{missing}=")]
        stdout = "\n".join(lines)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert f"missing_field: {missing}" in reason

    def test_empty_stdout_returns_missing_time_ns(self) -> None:
        ok, reason = verify_canary("")
        assert ok is False
        assert "missing_field" in reason


class TestVerifyCanaryTamperedSha256:
    def test_wrong_sha256_returns_false(self) -> None:
        stdout = _make_stdout(sha256_proof="a" * 64)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert "sha256_mismatch" in reason

    def test_sha256_truncated_to_16_chars_in_reason(self) -> None:
        stdout = _make_stdout(sha256_proof="b" * 64)
        ok, reason = verify_canary(stdout)
        assert ok is False
        # Both expected and observed prefixes should appear
        assert "expected=" in reason
        assert "got=" in reason


class TestVerifyCanaryTamperedBigInt:
    def test_wrong_big_int_returns_false(self) -> None:
        # INT64_MAX — the classic LLM hallucination
        stdout = _make_stdout(big_int_check=2**63 - 1)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert "big_int_mismatch" in reason

    def test_big_int_mismatch_shows_both_values(self) -> None:
        stdout = _make_stdout(big_int_check=42)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert str(_BIG_INT_EXPECTED) in reason
        assert "42" in reason

    def test_correct_big_int_passes(self) -> None:
        stdout = _make_stdout(big_int_check=_BIG_INT_EXPECTED)
        ok, _reason = verify_canary(stdout)
        assert ok is True


class TestVerifyCanaryInvalidHex:
    def test_0x_prefixed_urandom_hex_returns_false(self) -> None:
        # "0x" + 31 * "ab" = 64 chars, passes length check but fails _is_hex
        ns = time.time_ns()
        bad_hex = "0x" + "ab" * 31
        payload = str(ns).encode() + b"|" + (b"\xab" * 31)
        digest = hashlib.sha256(payload).hexdigest()
        stdout = "\n".join(
            [
                f"time_ns={ns}",
                f"urandom_hex={bad_hex}",
                f"sha256_proof={digest}",
                f"big_int_check={_BIG_INT_EXPECTED}",
            ]
        )
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert "invalid_field" in reason


class TestVerifyCanaryStaleTimestamp:
    def test_stale_timestamp_returns_false(self) -> None:
        stale_ns = time.time_ns() - (25 * 60 * 60 * 10**9)  # 25 hours ago
        stdout = _make_stdout(time_ns=stale_ns)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert "timestamp_stale" in reason

    def test_future_timestamp_within_24h_passes(self) -> None:
        future_ns = time.time_ns() + (23 * 60 * 60 * 10**9)  # 23 hours from now
        stdout = _make_stdout(time_ns=future_ns)
        ok, _reason = verify_canary(stdout)
        assert ok is True

    def test_future_timestamp_beyond_24h_returns_false(self) -> None:
        future_ns = time.time_ns() + (25 * 60 * 60 * 10**9)  # 25 hours from now
        stdout = _make_stdout(time_ns=future_ns)
        ok, reason = verify_canary(stdout)
        assert ok is False
        assert "timestamp_stale" in reason
