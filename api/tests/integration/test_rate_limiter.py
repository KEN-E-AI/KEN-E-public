"""Integration tests for RedisRateLimiter against a real Redis instance (AH-70).

These tests verify properties that fakeredis.aioredis cannot prove:
- Lua atomicity under genuine concurrent Redis clients (AC-9)
- Cross-instance shared state across two Redis connections (AC-10)
- Real Redis TTL precision (AC-13)

Running these tests requires a real Redis server:

    # Start local Redis (Docker):
    docker run --rm -p 6379:6379 redis:7-alpine

    # Run integration tests:
    REDIS_HOST=localhost pytest api/tests/integration/test_rate_limiter.py -v -m integration

Tests are automatically skipped when REDIS_HOST is unset or Redis is unreachable.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Module-level Redis availability guard
# ---------------------------------------------------------------------------

_REDIS_HOST = os.environ.get("REDIS_HOST", "")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# This skip is evaluated at collection time — if REDIS_HOST is unset, the entire
# module is skipped without importing redis.asyncio (which avoids misleading
# collection errors in CI environments that don't have Redis running).
if not _REDIS_HOST:
    pytest.skip(
        "REDIS_HOST is not set — skipping Redis integration tests. "
        "Set REDIS_HOST=localhost (after `docker run --rm -p 6379:6379 redis:7-alpine`) "
        "to run these tests.",
        allow_module_level=True,
    )

import redis.asyncio as aioredis  # noqa: E402 — conditional import after skip guard
from fastapi import HTTPException, Request  # noqa: E402
from src.kene_api.rate_limiter import (  # noqa: E402
    RedisRateLimiter,
    ip_only_key_strategy,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_redis() -> aioredis.Redis:
    """Async fixture providing a real Redis connection.

    Skips the test if Redis is unreachable (e.g. REDIS_HOST is set but the
    server is down). Uses a unique test-specific key prefix to avoid
    polluting other data.
    """
    client = aioredis.Redis(
        host=_REDIS_HOST,
        port=_REDIS_PORT,
        password=os.environ.get("REDIS_PASSWORD") or None,
        db=int(os.environ.get("REDIS_DB", "0")),
        decode_responses=False,
    )
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        # If REDIS_HOST is set, the operator INTENDED these tests to run.
        # Silent-skip on unreachable Redis was the false-PASS pattern we just
        # fixed elsewhere — fail loudly unless the operator opts back in.
        if os.environ.get("KENE_REDIS_INTEGRATION_SKIP_ON_UNREACHABLE", "").lower() in (
            "1",
            "true",
        ):
            pytest.skip(f"Redis at {_REDIS_HOST}:{_REDIS_PORT} unreachable: {exc}")
        pytest.fail(
            f"REDIS_HOST is set but Redis at {_REDIS_HOST}:{_REDIS_PORT} is "
            f"unreachable: {exc}. Set KENE_REDIS_INTEGRATION_SKIP_ON_UNREACHABLE=1 "
            f"to opt back into the skip behaviour (not recommended in CI)."
        )

    yield client

    # Clean up all test keys
    await client.flushdb()
    await client.aclose()


def _make_request(
    forwarded_for: str | None = "203.0.113.5",
    url_path: str = "/test",
) -> Request:
    """Create a minimal mock FastAPI Request for test use."""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    headers: dict[str, str] = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    request.headers = headers
    request.url = MagicMock()
    request.url.path = url_path
    return request


def _make_limiter(
    redis_client: aioredis.Redis,
    requests_per_minute: int = 5,
    requests_per_hour: int = 100,
    limiter_name: str | None = None,
) -> RedisRateLimiter:
    """Construct a RedisRateLimiter backed by the provided Redis client."""
    # Use a unique limiter name per test to isolate key namespaces
    name = limiter_name or f"integ_{uuid.uuid4().hex[:8]}"
    return RedisRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        redis_client=redis_client,
        key_strategy=ip_only_key_strategy,
        limiter_name=name,
    )


# ---------------------------------------------------------------------------
# AC-9: Atomic Lua under genuine concurrency
# ---------------------------------------------------------------------------


class TestAtomicLuaIntegration:
    """Verify Lua atomicity under genuine concurrent Redis clients.

    Unlike the unit tests (which use fakeredis and serialize Lua evaluation),
    these tests use asyncio.gather against a real Redis instance to verify
    that the 2-key sliding-window script prevents concurrent requests from
    racing past the limit.
    """

    @pytest.mark.integration
    async def test_concurrent_requests_exactly_limit_allowed(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """10 concurrent requests with limit=5 → exactly 5 succeed, 5 blocked.

        Runs 10 trial rounds to prove the result is consistent (not lucky).
        Each round uses a fresh limiter name to reset state.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request()

        for trial in range(10):
            limiter = _make_limiter(
                real_redis,
                requests_per_minute=5,
                requests_per_hour=100,
            )

            results: list[bool] = []

            async def _attempt(
                _limiter: RedisRateLimiter = limiter,
                _results: list[bool] = results,
            ) -> None:
                try:
                    await _limiter.check_rate_limit(request)
                    _results.append(True)
                except HTTPException:
                    _results.append(False)

            await asyncio.gather(*[_attempt() for _ in range(10)])

            successes = sum(results)
            failures = len(results) - successes
            assert successes == 5, (
                f"Trial {trial + 1}/10: Expected 5 allowed, got {successes}. "
                f"Full results: {results}"
            )
            assert failures == 5, (
                f"Trial {trial + 1}/10: Expected 5 blocked, got {failures}. "
                f"Full results: {results}"
            )


# ---------------------------------------------------------------------------
# AC-10: Cross-instance shared state
# ---------------------------------------------------------------------------


class TestCrossInstanceSharedStateIntegration:
    """Verify two separate RedisRateLimiter instances share state via Redis."""

    @pytest.mark.integration
    async def test_two_instances_share_state(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """Instance A increments the bucket; instance B sees A's writes."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")

        # Use the same limiter name so both instances target the same Redis keys
        shared_name = f"shared_{uuid.uuid4().hex[:8]}"
        limiter_a = _make_limiter(
            real_redis, requests_per_minute=3, requests_per_hour=100, limiter_name=shared_name
        )

        # Instance B uses the same Redis client and limiter name
        limiter_b = _make_limiter(
            real_redis, requests_per_minute=3, requests_per_hour=100, limiter_name=shared_name
        )

        request = _make_request()

        # A makes 2 requests
        await limiter_a.check_rate_limit(request)
        await limiter_a.check_rate_limit(request)

        # B should see the cumulative count (2 already used) and allow the 3rd
        await limiter_b.check_rate_limit(request)  # 3rd — should succeed

        # The 4th request (via A) must be blocked — bucket is full
        with pytest.raises(HTTPException) as exc_info:
            await limiter_a.check_rate_limit(request)

        assert exc_info.value.status_code == 429

    @pytest.mark.integration
    async def test_separate_key_prefixes_do_not_interfere(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """Two limiters with different key prefixes maintain independent buckets."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")

        shared_name = f"isolated_{uuid.uuid4().hex[:8]}"
        request = _make_request()

        limiter_a = RedisRateLimiter(
            requests_per_minute=2,
            requests_per_hour=100,
            redis_client=real_redis,
            key_strategy=ip_only_key_strategy,
            limiter_name=shared_name,
            key_prefix="namespace_a:ratelimit",
        )
        limiter_b = RedisRateLimiter(
            requests_per_minute=2,
            requests_per_hour=100,
            redis_client=real_redis,
            key_strategy=ip_only_key_strategy,
            limiter_name=shared_name,
            key_prefix="namespace_b:ratelimit",
        )

        # Fill A's bucket (2 requests)
        await limiter_a.check_rate_limit(request)
        await limiter_a.check_rate_limit(request)

        # A is now full
        with pytest.raises(HTTPException):
            await limiter_a.check_rate_limit(request)

        # B's bucket is independent — 2 requests should still succeed
        await limiter_b.check_rate_limit(request)
        await limiter_b.check_rate_limit(request)


# ---------------------------------------------------------------------------
# AC-13: Real Redis TTL precision
# ---------------------------------------------------------------------------


class TestRealRedisTtlPrecision:
    """Verify EXPIRE is set correctly on a real Redis instance."""

    @pytest.mark.integration
    async def test_minute_key_ttl_is_window_plus_60(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """Minute ZSET key TTL is set to 60 + 60 = 120 seconds on real Redis."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = _make_limiter(real_redis, limiter_name=f"ttl_test_{uuid.uuid4().hex[:8]}")
        request = _make_request(forwarded_for="198.51.100.99")

        await limiter.check_rate_limit(request)

        client_key = "ip:198.51.100.99"
        minute_key = f"kene:ratelimit:{limiter.limiter_name}:minute:{client_key}"
        ttl = await real_redis.ttl(minute_key)
        # TTL is 60 + 60 = 120; allow ±3s for execution time
        assert 117 <= ttl <= 123, f"Expected minute TTL ~120s on real Redis, got {ttl}"

    @pytest.mark.integration
    async def test_hour_key_ttl_is_window_plus_60(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """Hour ZSET key TTL is set to 3600 + 60 = 3660 seconds on real Redis."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = _make_limiter(real_redis, limiter_name=f"ttl_hr_{uuid.uuid4().hex[:8]}")
        request = _make_request(forwarded_for="198.51.100.99")

        await limiter.check_rate_limit(request)

        client_key = "ip:198.51.100.99"
        hour_key = f"kene:ratelimit:{limiter.limiter_name}:hour:{client_key}"
        ttl = await real_redis.ttl(hour_key)
        # TTL is 3600 + 60 = 3660; allow ±3s
        assert 3657 <= ttl <= 3663, f"Expected hour TTL ~3660s on real Redis, got {ttl}"

    @pytest.mark.integration
    async def test_ttl_is_positive_after_denial(
        self, real_redis: aioredis.Redis, monkeypatch: Any
    ) -> None:
        """TTL remains positive even after a 429 denial (EXPIRE still runs on deny path)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = _make_limiter(
            real_redis,
            requests_per_minute=1,
            requests_per_hour=100,
            limiter_name=f"ttl_deny_{uuid.uuid4().hex[:8]}",
        )
        request = _make_request(forwarded_for="198.51.100.50")

        # First request succeeds and sets TTL
        await limiter.check_rate_limit(request)

        # Second request is denied (minute limit=1 exhausted)
        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request)

        client_key = "ip:198.51.100.50"
        minute_key = f"kene:ratelimit:{limiter.limiter_name}:minute:{client_key}"
        ttl = await real_redis.ttl(minute_key)
        assert ttl > 0, f"TTL must be positive after a denial; got {ttl}"
