"""Proof-of-execution canary verifier for the SK-PRD-00 sandbox harness.

Parses the stdout produced by scripts/spike/skills/hello.py and verifies that
the output is internally consistent and arithmetically correct. Returns
(True, "verified") on full match or (False, reason) on any failure.

This module is a pure function — no I/O, no imports beyond stdlib — so it is
trivially unit-testable without any Vertex AI credentials.

Expected stdout schema (four KEY=VALUE lines, order matters only for readability;
the parser is order-independent):

    time_ns=<integer nanoseconds since epoch>
    urandom_hex=<64 hex chars — 32 random bytes>
    sha256_proof=<64 hex chars — SHA-256 of str(time_ns).encode() + b"|" + bytes.fromhex(urandom_hex)>
    big_int_check=<integer — must equal 9444732965739290427391 (2**73 - 1)>
"""

from __future__ import annotations

import hashlib
import time

_BIG_INT_EXPECTED: int = 2**73 - 1
_REQUIRED_FIELDS: tuple[str, ...] = ("time_ns", "urandom_hex", "sha256_proof", "big_int_check")
_MAX_STALENESS_NS: int = 24 * 60 * 60 * 10**9  # 24 hours in nanoseconds


def verify_canary(stdout: str) -> tuple[bool, str]:
    """Verify proof-of-execution canary output.

    Args:
        stdout: Raw stdout string from the sandbox execution of hello.py.

    Returns:
        (True, "verified") when all checks pass, or (False, reason) on failure.
    """
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if "=" in line:
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()

    for field in _REQUIRED_FIELDS:
        if field not in fields:
            return False, f"missing_field: {field}"

    try:
        time_ns = int(fields["time_ns"])
    except ValueError:
        return False, "invalid_field: time_ns is not an integer"

    urandom_hex = fields["urandom_hex"]
    if len(urandom_hex) != 64 or not _is_hex(urandom_hex):
        return False, f"invalid_field: urandom_hex must be 64 hex chars, got {len(urandom_hex)}"

    try:
        rand_bytes = bytes.fromhex(urandom_hex)
    except ValueError:
        return False, "invalid_field: urandom_hex is not valid hex"

    payload = str(time_ns).encode() + b"|" + rand_bytes
    expected_digest = hashlib.sha256(payload).hexdigest()
    observed_digest = fields["sha256_proof"]
    if observed_digest != expected_digest:
        return False, f"sha256_mismatch: expected={expected_digest[:16]}…, got={observed_digest[:16]}…"

    try:
        big_int = int(fields["big_int_check"])
    except ValueError:
        return False, "invalid_field: big_int_check is not an integer"

    if big_int != _BIG_INT_EXPECTED:
        return False, f"big_int_mismatch: expected={_BIG_INT_EXPECTED}, got={big_int}"

    now_ns = time.time_ns()
    age_ns = abs(now_ns - time_ns)
    if age_ns > _MAX_STALENESS_NS:
        age_h = age_ns / (60 * 60 * 10**9)
        return False, f"timestamp_stale: age={age_h:.1f}h exceeds 24h threshold"

    return True, "verified"


def _is_hex(s: str) -> bool:
    return bool(s) and all(c in "0123456789abcdefABCDEF" for c in s)
