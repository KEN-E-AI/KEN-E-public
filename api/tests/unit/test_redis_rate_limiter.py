"""Unit tests for RedisRateLimiter and build_rate_limiter factory (AH-70).

All tests use ``fakeredis.aioredis.FakeRedis`` — no real Redis instance required.
pytest-asyncio is configured in ``asyncio_mode = auto`` (see pytest.ini) so
async test functions are collected and run automatically.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import time
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis  # type: ignore[import-untyped]
import pytest
from fastapi import HTTPException, Request, Response, status
from src.kene_api.auth.models import UserContext
from src.kene_api.rate_limiter import (
    _SENTINEL_CAP_PER_MINUTE,
    LocalRateLimiter,
    RedisRateLimiter,
    SwitchableRateLimiter,
    authenticated_key_strategy,
    build_rate_limiter,
    ip_only_key_strategy,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_request(
    forwarded_for: str | None = "203.0.113.5",
    url_path: str = "/test",
) -> Request:
    """Create a minimal mock FastAPI Request."""
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


def _make_ctx(user_id: str = "test_user_abc") -> UserContext:
    """Create a minimal UserContext."""
    return UserContext(
        user_id=user_id,
        email="test@example.com",
        organization_permissions={},
    )


async def _make_limiter(
    fake_redis: Any,
    requests_per_minute: int = 5,
    requests_per_hour: int = 100,
    limiter_name: str = "test",
    key_strategy: Any = ip_only_key_strategy,
    emit_remaining_on_success: bool = True,
    audit_logger: Any = None,
) -> RedisRateLimiter:
    """Construct a RedisRateLimiter backed by the provided fakeredis instance."""
    return RedisRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        redis_client=fake_redis,
        key_strategy=key_strategy,
        limiter_name=limiter_name,
        emit_remaining_on_success=emit_remaining_on_success,
        audit_logger=audit_logger,
    )


# ---------------------------------------------------------------------------
# 1. Interface contract
# ---------------------------------------------------------------------------


class TestRedisRateLimiterInterface:
    def test_check_rate_limit_is_coroutine_function(self):
        """check_rate_limit must be a coroutine function (async def)."""
        redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = RedisRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=redis,
            key_strategy=ip_only_key_strategy,
            limiter_name="iface_test",
        )
        assert inspect.iscoroutinefunction(limiter.check_rate_limit)

    def test_redis_client_is_async(self):
        """Constructor accepts a redis.asyncio.Redis — not the sync redis.Redis."""
        import redis.asyncio as aioredis

        redis_client = aioredis.Redis()
        limiter = RedisRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=redis_client,
            key_strategy=ip_only_key_strategy,
            limiter_name="async_test",
        )
        assert limiter.redis_client is redis_client

    def test_fallback_on_redis_error_now_vestigial(self):
        """AH-79: fallback_on_redis_error parameter is now vestigial (no longer raises
        NotImplementedError). Passing a non-False value logs INFO but constructs cleanly.
        Fallback logic moved to SwitchableRateLimiter."""
        redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        # Must NOT raise NotImplementedError (AH-79 dropped the raise)
        limiter = RedisRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=redis,
            key_strategy=ip_only_key_strategy,
            limiter_name="fallback_test",
            fallback_on_redis_error=True,
        )
        assert limiter is not None

    def test_fallback_false_is_accepted(self):
        """fallback_on_redis_error=False (default) constructs without error."""
        redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = RedisRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=redis,
            key_strategy=ip_only_key_strategy,
            limiter_name="fallback_false_test",
            fallback_on_redis_error=False,
        )
        assert limiter is not None


# ---------------------------------------------------------------------------
# 2. Sliding-window correctness
# ---------------------------------------------------------------------------


class TestSlidingWindowCorrectness:
    async def test_exactly_limit_requests_allowed(self, fake_redis: Any, monkeypatch: Any) -> None:
        """Exactly requests_per_minute requests are allowed; the next is blocked."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis, requests_per_minute=3, requests_per_hour=100)
        request = _make_request()

        # First 3 should succeed
        for _ in range(3):
            await limiter.check_rate_limit(request)

        # 4th must be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "3 requests per minute" in exc_info.value.detail

    async def test_requests_unblocked_after_window_slides(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """After the window slides past, the slot is freed and the next request succeeds."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis, requests_per_minute=2, requests_per_hour=100)
        request = _make_request()

        t0 = time.time()

        with patch("time.time", return_value=t0):
            await limiter.check_rate_limit(request)
            await limiter.check_rate_limit(request)
            with pytest.raises(HTTPException):
                await limiter.check_rate_limit(request)

        # Jump 61 seconds into the future — all earlier entries expire
        with patch("time.time", return_value=t0 + 61):
            await limiter.check_rate_limit(request)  # should not raise

    async def test_hour_limit_enforced(self, fake_redis: Any, monkeypatch: Any) -> None:
        """requests_per_hour limit is enforced independently of minute limit."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=100,
            requests_per_hour=2,
        )
        request = _make_request()

        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "2 requests per hour" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 3. ZSET key TTL
# ---------------------------------------------------------------------------


class TestZsetKeyTtl:
    async def test_minute_key_ttl_is_window_plus_60(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Minute ZSET key TTL is set to 60 + 60 = 120 seconds."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis, limiter_name="ttl_test")
        request = _make_request()

        await limiter.check_rate_limit(request)

        client_key = ip_only_key_strategy(request, None)
        minute_key = f"kene:ratelimit:ttl_test:minute:{client_key}"
        ttl = await fake_redis.ttl(minute_key)
        # TTL should be window (60) + 60 = 120; allow ±2s for execution time
        assert 118 <= ttl <= 122, f"Expected ~120s TTL, got {ttl}"

    async def test_hour_key_ttl_is_window_plus_60(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Hour ZSET key TTL is set to 3600 + 60 = 3660 seconds."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis, limiter_name="ttl_hr_test")
        request = _make_request()

        await limiter.check_rate_limit(request)

        client_key = ip_only_key_strategy(request, None)
        hour_key = f"kene:ratelimit:ttl_hr_test:hour:{client_key}"
        ttl = await fake_redis.ttl(hour_key)
        # TTL should be 3600 + 60 = 3660; allow ±2s
        assert 3658 <= ttl <= 3662, f"Expected ~3660s TTL, got {ttl}"


# ---------------------------------------------------------------------------
# 4. Cross-instance shared state
# ---------------------------------------------------------------------------


class TestCrossInstanceSharedState:
    async def test_two_limiters_share_state_via_same_redis(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Two RedisRateLimiter instances against the same Redis share state (AC-10)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter_a = await _make_limiter(
            fake_redis, requests_per_minute=3, requests_per_hour=100, limiter_name="shared"
        )
        limiter_b = await _make_limiter(
            fake_redis, requests_per_minute=3, requests_per_hour=100, limiter_name="shared"
        )
        request = _make_request()

        # Use limiter_a for 2 requests
        await limiter_a.check_rate_limit(request)
        await limiter_a.check_rate_limit(request)

        # limiter_b should see the existing count and block on the 3rd
        await limiter_b.check_rate_limit(request)  # 3rd succeeds

        with pytest.raises(HTTPException) as exc_info:
            await limiter_b.check_rate_limit(request)  # 4th blocked

        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# 5. Concurrent requests / atomicity
# ---------------------------------------------------------------------------


class TestAtomicLua:
    async def test_concurrent_requests_respect_limit(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Verify limit is respected by 10 gather'd calls with limit=5.

        NOTE: This test does NOT prove Lua atomicity under genuine concurrency.
        fakeredis.aioredis executes Lua via lupa synchronously on the event-loop
        thread — gather'd coroutines serialize at the Lua eval boundary, so this
        test would pass even with a non-atomic script. Real atomicity under
        concurrent Redis clients is verified in:
            api/tests/integration/test_rate_limiter.py::TestAtomicLuaIntegration

        This test's value is verifying the limit-enforcement logic end-to-end
        (key building, Lua parameter passing, 429 raising) — not concurrency.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis, requests_per_minute=5, requests_per_hour=100
        )
        request = _make_request()

        results: list[bool] = []

        async def _attempt() -> None:
            try:
                await limiter.check_rate_limit(request)
                results.append(True)
            except HTTPException:
                results.append(False)

        await asyncio.gather(*[_attempt() for _ in range(10)])

        successes = sum(results)
        failures = len(results) - successes
        # fakeredis serializes, so exactly 5 succeed and 5 fail (limit=5)
        assert successes == 5, f"Expected 5 allowed, got {successes}"
        assert failures == 5, f"Expected 5 blocked, got {failures}"

    async def test_unique_zadd_members_prevent_same_tick_collision(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Unique ZADD members ensure same-timestamp requests each add a distinct entry.

        The uniqueness guarantee is delivered by the Python-side uuid4 suffix in
        the ZADD member string (``f"{now}:{uuid4().hex[:16]}"``).  Two sequential
        calls must each add a distinct ZSET entry even when the system clock
        returns the exact same float.  We verify this by issuing 2 requests and
        checking ZCARD == 2.  We do NOT mock ``time.time`` here because the mock
        only affects the Python layer — Lua receives ``now`` as an explicit ARGV
        string that we construct in Python, so the unique suffix is still
        generated per-call regardless of the clock value.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis, requests_per_minute=5, requests_per_hour=100
        )
        request = _make_request()

        # Issue two requests with an artificially static timestamp to force
        # same-score ZADD: both calls pass the same ``now`` value to Lua.
        # The uuid4 suffix in the member string keeps them distinct.
        fixed_now = 1_700_000_000.0

        # Patch time.time in the rate_limiter module so `now` is static for both calls.
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.time.return_value = fixed_now
            await limiter.check_rate_limit(request)
            await limiter.check_rate_limit(request)

        # Both requests must have landed as distinct ZSET members
        client_key = ip_only_key_strategy(request, None)
        minute_key = f"kene:ratelimit:test:minute:{client_key}"
        cardinality = await fake_redis.zcard(minute_key)
        assert cardinality == 2, (
            f"Expected 2 distinct members in ZSET after 2 same-tick requests, got {cardinality}"
        )


# ---------------------------------------------------------------------------
# 6. X-RateLimit headers
# ---------------------------------------------------------------------------


class TestRateLimitHeaders:
    async def test_headers_set_on_response_when_provided(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """X-RateLimit-Limit, -Reset, and -Remaining are set on the Response."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=10,
            requests_per_hour=100,
            emit_remaining_on_success=True,
        )
        request = _make_request()
        response = Response()

        await limiter.check_rate_limit(request, response=response)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    async def test_remaining_omitted_on_success_when_emit_false(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """When emit_remaining_on_success=False, X-RateLimit-Remaining is not set on 200."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=10,
            requests_per_hour=100,
            emit_remaining_on_success=False,
        )
        request = _make_request()
        response = Response()

        await limiter.check_rate_limit(request, response=response)

        assert "X-RateLimit-Remaining" not in response.headers
        # Limit and Reset are still set
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    async def test_headers_on_429_response(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """On 429, HTTPException headers include Retry-After, Limit, Remaining, Reset."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis, requests_per_minute=2, requests_per_hour=100
        )
        request = _make_request()

        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        exc = exc_info.value
        assert exc.status_code == 429
        assert "Retry-After" in exc.headers
        assert "X-RateLimit-Limit" in exc.headers
        assert "X-RateLimit-Remaining" in exc.headers
        assert "X-RateLimit-Reset" in exc.headers
        # Remaining should be 0 on the blocked response
        assert exc.headers["X-RateLimit-Remaining"] == "0"

    async def test_retry_after_is_accurate_not_fixed(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Retry-After reflects actual time until oldest entry ages out (not fixed 60)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis, requests_per_minute=2, requests_per_hour=100
        )
        request = _make_request()
        t0 = time.time()

        # Issue first request 30 seconds ago
        with patch("time.time", return_value=t0 - 30):
            await limiter.check_rate_limit(request)

        # Second request now
        with patch("time.time", return_value=t0):
            await limiter.check_rate_limit(request)

        # Third request now should be blocked; Retry-After ≈ 30s (oldest entry at t0-30,
        # window=60, so it expires at t0+30)
        with patch("time.time", return_value=t0), pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        retry_after = int(exc_info.value.headers["Retry-After"])
        # Allow ±2s for execution time
        assert 28 <= retry_after <= 32, f"Expected Retry-After ~30s, got {retry_after}"

    async def test_no_headers_set_when_response_not_provided(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """No headers are injected when response=None (call site doesn't supply one)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis)
        request = _make_request()
        # Should not raise even without a response object
        await limiter.check_rate_limit(request)


# ---------------------------------------------------------------------------
# 7. Shared sentinel cap (AC-19)
# ---------------------------------------------------------------------------


class TestSentinelCap:
    async def test_sentinel_cap_blocks_after_5_requests(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """6 sentinel-keyed requests → 6th is blocked even if per-limiter threshold is higher."""
        # Use a limiter with a higher threshold than the sentinel cap
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "5")  # force short-chain sentinel
        limiter = await _make_limiter(
            fake_redis, requests_per_minute=50, requests_per_hour=1000
        )
        # Request with no XFF (short chain) → sentinel key
        request = _make_request(forwarded_for=None)

        # 5 requests should pass
        for _ in range(5):
            await limiter.check_rate_limit(request)

        # 6th must be blocked by the sentinel cap
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "sentinel cap" in exc_info.value.detail

    async def test_sentinel_cap_constant_is_5(self) -> None:
        """_SENTINEL_CAP_PER_MINUTE is 5 per PRD §4.3."""
        assert _SENTINEL_CAP_PER_MINUTE == 5

    async def test_sentinel_key_is_shared_across_limiters(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Two different limiters share the single sentinel Redis key."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "5")
        limiter_a = await _make_limiter(
            fake_redis, requests_per_minute=50, requests_per_hour=1000, limiter_name="lim_a"
        )
        limiter_b = await _make_limiter(
            fake_redis, requests_per_minute=50, requests_per_hour=1000, limiter_name="lim_b"
        )
        request = _make_request(forwarded_for=None)

        # 3 sentinel hits via limiter_a
        for _ in range(3):
            await limiter_a.check_rate_limit(request)

        # 2 more via limiter_b → total 5 hits in sentinel
        for _ in range(2):
            await limiter_b.check_rate_limit(request)

        # 6th hit via limiter_a must be blocked by shared sentinel
        with pytest.raises(HTTPException) as exc_info:
            await limiter_a.check_rate_limit(request)

        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# 8. Audit logger integration
# ---------------------------------------------------------------------------


class TestAuditLoggerIntegration:
    async def test_audit_logger_called_on_429(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """When a 429 is raised, audit_logger.log_rate_limit_exceeded is called."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=1,
            requests_per_hour=100,
            audit_logger=mock_audit,
        )
        request = _make_request()

        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request)

        mock_audit.log_rate_limit_exceeded.assert_awaited_once()
        call_kwargs = mock_audit.log_rate_limit_exceeded.call_args
        assert call_kwargs is not None

    async def test_audit_logger_passes_user_id_when_ctx_provided(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Audit log includes user_id from ctx on 429."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=1,
            requests_per_hour=100,
            audit_logger=mock_audit,
            key_strategy=authenticated_key_strategy,
        )
        request = _make_request()
        ctx = _make_ctx("user_xyz_123")

        await limiter.check_rate_limit(request, ctx=ctx)

        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request, ctx=ctx)

        call_kwargs = mock_audit.log_rate_limit_exceeded.call_args.kwargs
        assert call_kwargs.get("user_id") == "user_xyz_123"

    async def test_audit_logger_not_called_on_200(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Audit logger is NOT called on successful (non-429) responses."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=10,
            requests_per_hour=100,
            audit_logger=mock_audit,
        )
        request = _make_request()

        await limiter.check_rate_limit(request)

        mock_audit.log_rate_limit_exceeded.assert_not_awaited()

    async def test_audit_failure_does_not_replace_429_minute_window(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Regression guard for B2: if audit_logger raises during the
        minute-window 429 path, the HTTPException(429) must still surface to
        the caller (not be replaced by a 500 from the audit exception)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock(
            side_effect=RuntimeError("audit sink down")
        )

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=1,
            requests_per_hour=100,
            audit_logger=mock_audit,
        )
        request = _make_request()
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_audit_failure_does_not_replace_429_hour_window(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Regression guard for B2 on the hour-window 429 path."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock(
            side_effect=RuntimeError("audit sink down")
        )

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=100,
            requests_per_hour=1,
            audit_logger=mock_audit,
        )
        request = _make_request()
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_audit_failure_does_not_replace_429_sentinel_path(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Regression guard for B2 on the sentinel-cap 429 path."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock(
            side_effect=RuntimeError("audit sink down")
        )

        limiter = await _make_limiter(
            fake_redis,
            requests_per_minute=100,
            requests_per_hour=1000,
            audit_logger=mock_audit,
        )
        # No XFF header → triggers the sentinel path
        sentinel_request = _make_request(forwarded_for=None)
        # Sentinel cap is 5/min — exhaust it
        for _ in range(5):
            await limiter.check_rate_limit(sentinel_request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(sentinel_request)
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ---------------------------------------------------------------------------
# 9. build_rate_limiter factory
# ---------------------------------------------------------------------------


class TestBuildRateLimiterFactory:
    def test_memory_backend_returns_local_rate_limiter(self, monkeypatch: Any) -> None:
        """KENE_RATE_LIMIT_BACKEND=memory returns a LocalRateLimiter."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        limiter = build_rate_limiter(
            name="factory_test",
            requests_per_minute=10,
            requests_per_hour=100,
        )
        assert type(limiter).__name__ == "LocalRateLimiter"

    def test_redis_backend_with_explicit_client_returns_switchable_rate_limiter(
        self, monkeypatch: Any
    ) -> None:
        """KENE_RATE_LIMIT_BACKEND=redis with explicit redis_client returns SwitchableRateLimiter
        (AH-79: factory now returns the resilience wrapper, not raw RedisRateLimiter)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="factory_redis_test",
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=fake_redis,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.redis_limiter.redis_client is fake_redis

    def test_default_backend_is_redis(self, monkeypatch: Any) -> None:
        """Without KENE_RATE_LIMIT_BACKEND set, the default is redis → SwitchableRateLimiter."""
        monkeypatch.delenv("KENE_RATE_LIMIT_BACKEND", raising=False)
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="factory_default_test",
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=fake_redis,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"

    def test_memory_backend_preserves_limiter_name(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        limiter = build_rate_limiter(
            name="my_custom_limiter",
            requests_per_minute=5,
            requests_per_hour=50,
        )
        assert limiter.limiter_name == "my_custom_limiter"

    def test_redis_backend_preserves_limiter_name(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="my_redis_limiter",
            requests_per_minute=5,
            requests_per_hour=50,
            redis_client=fake_redis,
        )
        # AH-79: factory returns SwitchableRateLimiter; limiter_name is on the wrapper.
        assert limiter.limiter_name == "my_redis_limiter"

    def test_memory_backend_ignores_audit_logger_kwarg(self, monkeypatch: Any) -> None:
        """Regression guard for B1: memory backend must not forward an
        audit_logger kwarg into LocalRateLimiter.__init__ (which doesn't accept
        it) — previously raised TypeError; now is silently dropped + INFO logged."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        mock_audit = MagicMock()
        # The call must NOT raise TypeError.
        limiter = build_rate_limiter(
            name="memory_with_audit",
            requests_per_minute=10,
            requests_per_hour=100,
            audit_logger=mock_audit,
        )
        assert type(limiter).__name__ == "LocalRateLimiter"


# ---------------------------------------------------------------------------
# 10. Key shape (§4.1)
# ---------------------------------------------------------------------------


class TestKeyShape:
    async def test_minute_key_follows_schema(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Minute key is kene:ratelimit:{name}:minute:{client_key}."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(fake_redis, limiter_name="keyshape_test")
        request = _make_request(forwarded_for="198.51.100.7")

        await limiter.check_rate_limit(request)

        expected_key = "kene:ratelimit:keyshape_test:minute:ip:198.51.100.7"
        cardinality = await fake_redis.zcard(expected_key)
        assert cardinality == 1, f"Expected 1 entry in key {expected_key!r}, got {cardinality}"

    async def test_authenticated_key_uses_uid_prefix(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Authenticated key uses uid:{sha256[:16]} as the client_key segment."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = await _make_limiter(
            fake_redis,
            limiter_name="auth_key_test",
            key_strategy=authenticated_key_strategy,
        )
        request = _make_request()
        ctx = _make_ctx("uid_test_user")

        await limiter.check_rate_limit(request, ctx=ctx)

        uid_hash = hashlib.sha256(b"uid_test_user").hexdigest()[:16]
        expected_key = f"kene:ratelimit:auth_key_test:minute:uid:{uid_hash}"
        cardinality = await fake_redis.zcard(expected_key)
        assert cardinality == 1, f"Expected 1 entry in key {expected_key!r}, got {cardinality}"

    async def test_custom_key_prefix_respected(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """key_prefix constructor param overrides the default 'kene:ratelimit' prefix."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RedisRateLimiter(
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=fake_redis,
            key_strategy=ip_only_key_strategy,
            limiter_name="custom_prefix_test",
            key_prefix="myapp:limits",
        )
        request = _make_request(forwarded_for="198.51.100.8")

        await limiter.check_rate_limit(request)

        expected_key = "myapp:limits:custom_prefix_test:minute:ip:198.51.100.8"
        cardinality = await fake_redis.zcard(expected_key)
        assert cardinality == 1


# ---------------------------------------------------------------------------
# 11. Adversarial UID hashing (AC-18)
# ---------------------------------------------------------------------------


class TestAdversarialUidHashing:
    ADVERSARIAL_UIDS: ClassVar[list[str]] = [
        "oidc:sub:value",  # colons in UID
        "üser_id_тест",  # unicode
        "x" * 1024,  # 1KB-length UID
        "",  # empty string
    ]

    async def test_adversarial_uids_produce_distinct_keys(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """All adversarial UIDs produce distinct, non-colliding ZSET keys."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request()

        for uid in self.ADVERSARIAL_UIDS:
            limiter = await _make_limiter(
                fake_redis,
                limiter_name=f"adv_{hashlib.sha256(uid.encode()).hexdigest()[:8]}",
                key_strategy=authenticated_key_strategy,
            )
            ctx = _make_ctx(uid)
            # Must not raise
            await limiter.check_rate_limit(request, ctx=ctx)

    async def test_adversarial_uids_produce_distinct_redis_keys(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Two adversarial UIDs with the same limiter must land in different ZSET keys."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request()
        limiter = await _make_limiter(
            fake_redis,
            limiter_name="adv_collision_test",
            key_strategy=authenticated_key_strategy,
            requests_per_minute=100,
            requests_per_hour=10000,
        )

        all_minute_keys: list[str] = []
        for uid in self.ADVERSARIAL_UIDS:
            ctx = _make_ctx(uid)
            uid_hash = hashlib.sha256(uid.encode()).hexdigest()[:16]
            minute_key = f"kene:ratelimit:adv_collision_test:minute:uid:{uid_hash}"
            await limiter.check_rate_limit(request, ctx=ctx)
            all_minute_keys.append(minute_key)

        # All keys must be distinct
        assert len(set(all_minute_keys)) == len(self.ADVERSARIAL_UIDS), (
            f"UID hash collision detected: {all_minute_keys}"
        )


# ---------------------------------------------------------------------------
# 12. Lua script structural ordering (N2 — defense against future reordering)
# ---------------------------------------------------------------------------


class TestLuaScript:
    """Regex-based ordering assertions on the Lua script constants.

    These tests guard against future refactors that accidentally reorder Lua
    steps, which would silently break:
    - AC-4: oldest_score must be read BEFORE ZADD (X-RateLimit-Reset accuracy)
    - AC-6: EXPIRE must be the last step per window (orphaned-key prevention)
    """

    def test_sliding_window_lua_step_order(self) -> None:
        """_LUA_SLIDING_WINDOW: ZREMRANGEBYSCORE → ZRANGEBYSCORE → ZCARD → ZADD → EXPIRE."""
        from src.kene_api.rate_limiter import _LUA_SLIDING_WINDOW

        script = _LUA_SLIDING_WINDOW

        # Find positions of each critical operation
        zremrange_pos = script.find("ZREMRANGEBYSCORE")
        zrangebyscore_pos = script.find("ZRANGEBYSCORE")
        zcard_pos = script.find("ZCARD")
        zadd_pos = script.find("ZADD")
        expire_pos = script.rfind("EXPIRE")  # last EXPIRE (the per-window one)

        assert zremrange_pos != -1, "_LUA_SLIDING_WINDOW must contain ZREMRANGEBYSCORE"
        assert zrangebyscore_pos != -1, "_LUA_SLIDING_WINDOW must contain ZRANGEBYSCORE"
        assert zcard_pos != -1, "_LUA_SLIDING_WINDOW must contain ZCARD"
        assert zadd_pos != -1, "_LUA_SLIDING_WINDOW must contain ZADD"
        assert expire_pos != -1, "_LUA_SLIDING_WINDOW must contain EXPIRE"

        # Strict ordering: ZREMRANGEBYSCORE < ZRANGEBYSCORE < ZCARD < ZADD < EXPIRE
        assert zremrange_pos < zrangebyscore_pos, (
            "ZREMRANGEBYSCORE must come before ZRANGEBYSCORE (trim before oldest-read)"
        )
        assert zrangebyscore_pos < zcard_pos, (
            "ZRANGEBYSCORE must come before ZCARD (oldest_score read before count)"
        )
        assert zcard_pos < zadd_pos, (
            "ZCARD must come before ZADD (count before add — AC-4)"
        )
        assert zadd_pos < expire_pos, (
            "ZADD must come before EXPIRE (EXPIRE is last — AC-6)"
        )

    def test_sentinel_lua_step_order(self) -> None:
        """_LUA_SENTINEL_CAP: ZREMRANGEBYSCORE → ZCARD → EXPIRE (on both paths)."""
        from src.kene_api.rate_limiter import _LUA_SENTINEL_CAP

        script = _LUA_SENTINEL_CAP

        zremrange_pos = script.find("ZREMRANGEBYSCORE")
        zcard_pos = script.find("ZCARD")
        # First EXPIRE position (deny path — N4 fix ensures EXPIRE on deny path too)
        expire_pos = script.find("EXPIRE")

        assert zremrange_pos != -1, "_LUA_SENTINEL_CAP must contain ZREMRANGEBYSCORE"
        assert zcard_pos != -1, "_LUA_SENTINEL_CAP must contain ZCARD"
        assert expire_pos != -1, "_LUA_SENTINEL_CAP must contain EXPIRE"

        assert zremrange_pos < zcard_pos, (
            "ZREMRANGEBYSCORE must come before ZCARD (trim before count)"
        )
        assert zcard_pos < expire_pos, (
            "ZCARD must come before EXPIRE"
        )

    def test_sentinel_lua_expire_on_both_paths(self) -> None:
        """_LUA_SENTINEL_CAP must call EXPIRE on BOTH allow and deny paths (N4)."""
        from src.kene_api.rate_limiter import _LUA_SENTINEL_CAP

        # Count the number of EXPIRE calls — must be >= 2 (one per path)
        expire_count = _LUA_SENTINEL_CAP.count("EXPIRE")
        assert expire_count >= 2, (
            f"_LUA_SENTINEL_CAP must call EXPIRE on both allow and deny paths "
            f"(N4 fix) — found {expire_count} EXPIRE call(s)"
        )

    def test_sentinel_lua_allow_path_expire_after_zadd(self) -> None:
        """_LUA_SENTINEL_CAP allow path: EXPIRE must come AFTER ZADD.

        The deny path intentionally has EXPIRE before ZADD (it returns early
        without ZADD), so the first EXPIRE in the script is the deny-path one.
        Verify the LAST EXPIRE (allow path) is after ZADD — preserves the
        EXPIRE-is-last invariant on the path that actually mutates the ZSET.
        """
        from src.kene_api.rate_limiter import _LUA_SENTINEL_CAP

        zadd_pos = _LUA_SENTINEL_CAP.find("ZADD")
        last_expire_pos = _LUA_SENTINEL_CAP.rfind("EXPIRE")
        assert zadd_pos != -1, "_LUA_SENTINEL_CAP must contain ZADD"
        assert last_expire_pos != -1, "_LUA_SENTINEL_CAP must contain EXPIRE"
        assert zadd_pos < last_expire_pos, (
            "Allow-path EXPIRE must come AFTER ZADD — preserves the "
            "EXPIRE-is-last invariant on the mutating path"
        )
