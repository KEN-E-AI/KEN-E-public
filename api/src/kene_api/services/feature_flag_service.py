"""Feature Flags evaluation primitives.

This module is the home for all Feature Flags evaluation logic as defined in
FF-PRD-01. hash_bucket is landed in FF-2; the evaluator, service class, and
is_feature_enabled helper are appended by FF-3, FF-4, and FF-5 respectively.
"""

import hashlib


def hash_bucket(flag_key: str, entity_id: str) -> int:
    """Return a deterministic bucket in [0, 99] for a (flag_key, entity_id) pair.

    Uses sha256(f"{flag_key}:{entity_id}") truncated to 8 hex chars, parsed as
    base-16, reduced modulo 100.  This algorithm is pinned by FF-PRD-01 §4 —
    any change to the byte sequence or modulus breaks cross-process
    determinism and silently shuffles users between rollout cohorts.

    Salting on flag_key gives each flag an independent hash distribution per
    entity.  entity_id MUST be an opaque identifier (ULID, UUID, branded
    string) — never an email address or any PII-bearing field (feature-flags
    README §7.3).
    """
    digest = hashlib.sha256(f"{flag_key}:{entity_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100
