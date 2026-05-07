"""Unit tests for hash_bucket — deterministic percentage-rollout bucketing.

Covers FF-PRD-01 AC-3 and §8 test plan:
  - Range: every (flag_key, entity_id) pair returns an int in [0, 99].
  - Determinism: repeated calls for the same pair always return the same value.
  - Distribution spot-check: different flag_keys yield different buckets for
    the same entity_id (anti-collision sanity, not a statistical test).
  - Golden-value guard: pinned integer literals catch byte-level algorithm
    drift (e.g., swapping sha256 for sha1 or changing the join character).
"""

import random
from typing import ClassVar

import pytest
from src.kene_api.services.feature_flag_service import hash_bucket


class TestHashBucketRange:
    """Test 1 — return value is always in [0, 99] for 10 000 random pairs."""

    def test_range_across_random_pairs(self) -> None:
        rng = random.Random(42)
        chars = "abcdefghijklmnopqrstuvwxyz0123456789_"

        def rand_str(length: int = 8) -> str:
            return "".join(rng.choices(chars, k=length))

        pairs = [(rand_str(), rand_str()) for _ in range(10_000)]
        assert all(0 <= hash_bucket(k, e) <= 99 for k, e in pairs)


class TestHashBucketDeterminism:
    """Test 2 — 1 000 calls for each of 10 seeded pairs return the same value."""

    SEEDED_PAIRS: ClassVar[list[tuple[str, str]]] = [
        ("demo_flag", "u_001"),
        ("billing_enabled", "org_42"),
        ("chat_v2_enabled", "acct_abc"),
        ("automations_beta", "user_xyz"),
        ("performance_dashboards_tab", "acct_001"),
        ("new_onboarding_flow", "org_999"),
        ("skills_sandbox", "u_007"),
        ("knowledge_graph_v2", "acct_deadbeef"),
        ("integrations_oauth_v2", "org_alpha"),
        ("data_pipeline_v3", "u_999"),
    ]

    @pytest.mark.parametrize("flag_key,entity_id", SEEDED_PAIRS)
    def test_determinism_1000_calls(self, flag_key: str, entity_id: str) -> None:
        first = hash_bucket(flag_key, entity_id)
        results = [hash_bucket(flag_key, entity_id) for _ in range(1_000)]
        # Single assertion per T-8: entire result set matches expected.
        assert results == [first] * 1_000, (
            f"hash_bucket({flag_key!r}, {entity_id!r}) was not deterministic"
        )


class TestHashBucketDistribution:
    """Test 3 — anti-collision spot-check: different flag_keys yield different
    buckets for the same entity_id.

    This is a sanity check that the flag_key salt actually diversifies the
    distribution — not a rigorous statistical test.  Three flags sharing one
    entity_id must not all land in the same bucket.
    """

    def test_different_flags_produce_different_buckets(self) -> None:
        entity_id = "shared_user_acct_001"
        buckets = {
            hash_bucket("flag_a", entity_id),
            hash_bucket("flag_b", entity_id),
            hash_bucket("flag_c", entity_id),
        }
        # Anti-collision sanity: at least two distinct values among three keys.
        assert len(buckets) > 1, (
            "All three flag_keys produced the same bucket for the same entity_id; "
            "the flag_key salt may not be working."
        )


class TestHashBucketGoldenValues:
    """Test 4 — pinned integer literals catch byte-level algorithm drift.

    These constants were computed once out-of-band from the PRD §4 algorithm:
      int(sha256(f"{flag_key}:{entity_id}").hexdigest()[:8], 16) % 100

    Any change to the hash function, join character, byte encoding, digit count,
    or modulus will cause this test to fail, surfacing algorithmic drift in CI
    before it silently reshuffles rollout cohorts.  Do NOT derive these from
    hash_bucket itself — that would make the gate circular.
    """

    def test_hardcoded_golden_demo_flag(self) -> None:
        # python3 -c "import hashlib; print(int(hashlib.sha256(b'demo_flag:user_001').hexdigest()[:8],16)%100)"
        assert hash_bucket("demo_flag", "user_001") == 33

    def test_hardcoded_golden_billing_enabled(self) -> None:
        # python3 -c "import hashlib; print(int(hashlib.sha256(b'billing_enabled:org_42').hexdigest()[:8],16)%100)"
        assert hash_bucket("billing_enabled", "org_42") == 98
