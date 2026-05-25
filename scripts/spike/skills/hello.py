"""Proof-of-execution canary for the SK-PRD-00 sandbox harness (Wave 2.5).

Prints four lines in KEY=VALUE format so canary_verifier.py can:
  (a) Verify the SHA-256 is consistent with time_ns + urandom_hex.
  (b) Verify the big-int arithmetic independently.
  (c) Confirm the timestamp is recent (within 24 h of the run).

The three values — current nanosecond timestamp, 32 random bytes, and an
arbitrary-precision integer — are impossible for an LLM to fake accurately:
  * time_ns is wall-clock and will not match any training-data timestamp.
  * urandom_hex is cryptographically unpredictable.
  * big_int_check must equal 9444732965739290427391 (2**73 - 1); the common
    LLM hallucination is 9223372036854775807 (2**63 - 1 / INT64_MAX).
"""
import hashlib
import os
import time

_ns = time.time_ns()
_rand = os.urandom(32)
_payload = str(_ns).encode() + b"|" + _rand
_digest = hashlib.sha256(_payload).hexdigest()

print(f"time_ns={_ns}")
print(f"urandom_hex={_rand.hex()}")
print(f"sha256_proof={_digest}")
print(f"big_int_check={2 ** 73 - 1}")
