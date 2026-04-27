"""Tests for the Redis TTL controller.

These tests skip cleanly if dev Redis is unreachable — they're meant as a
local self-check rather than a CI gate.
"""

from __future__ import annotations

from tests.integration.sprint6_harness.redis_ttl_fixture import TTLController


def test_seed_and_expire_round_trip(ttl_controller: TTLController) -> None:
    key = "sprint6_harness:roundtrip"
    try:
        assert ttl_controller.seed(key, "hello", ttl_s=60)
        assert ttl_controller.get(key) == "hello"
        assert ttl_controller.expire_now(key)
        assert ttl_controller.get(key) is None
    finally:
        ttl_controller.delete_key(key)


def test_flush_pattern_removes_only_matching(ttl_controller: TTLController) -> None:
    keys = ["sprint6_harness:flush:a", "sprint6_harness:flush:b"]
    other = "sprint6_harness:other"
    try:
        for k in keys:
            ttl_controller.seed(k, "x", ttl_s=60)
        ttl_controller.seed(other, "y", ttl_s=60)

        deleted = ttl_controller.flush_pattern("sprint6_harness:flush:*")
        assert deleted == 2
        assert ttl_controller.get(other) == "y"
    finally:
        for k in (*keys, other):
            ttl_controller.delete_key(k)
