"""Unit tests for _CircuitBreaker, SwitchableRateLimiter, and build_rate_limiter
factory changes (AH-79).

All Redis interactions use ``fakeredis.aioredis.FakeRedis`` — no real Redis
instance required.  pytest-asyncio is configured in ``asyncio_mode = auto``
(see pytest.ini) so async test functions are collected automatically.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis  # type: ignore[import-untyped]
import pytest
import src.kene_api.rate_limiter as rate_limiter_module
from fastapi import HTTPException, Request
from src.kene_api.rate_limiter import (
    _CB_COOLDOWN_SECONDS,
    _CB_K,
    LocalRateLimiter,
    RedisRateLimiter,
    SwitchableRateLimiter,
    _CircuitBreaker,
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


def _make_redis_limiter(
    fake_redis: Any,
    requests_per_minute: int = 10,
    requests_per_hour: int = 100,
    name: str = "test_redis",
) -> RedisRateLimiter:
    return RedisRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        redis_client=fake_redis,
        key_strategy=ip_only_key_strategy,
        limiter_name=name,
    )


def _make_local_limiter(
    requests_per_minute: int = 10,
    requests_per_hour: int = 100,
    name: str = "test_local",
) -> LocalRateLimiter:
    return LocalRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        key_strategy=ip_only_key_strategy,
        limiter_name=name,
    )


def _make_switchable(
    fake_redis: Any,
    requests_per_minute: int = 10,
    requests_per_hour: int = 100,
    fallback_cap_divisor: int = 1,
    fail_open: bool = False,
    name: str = "test_sw",
) -> SwitchableRateLimiter:
    redis_l = _make_redis_limiter(fake_redis, requests_per_minute, requests_per_hour, name)
    fallback_l = _make_local_limiter(
        requests_per_minute=max(1, requests_per_minute // max(1, fallback_cap_divisor)),
        requests_per_hour=max(1, requests_per_hour // max(1, fallback_cap_divisor)),
        name=f"{name}:fallback",
    )
    return SwitchableRateLimiter(
        redis_limiter=redis_l,
        fallback_limiter=fallback_l,
        fallback_cap_divisor=fallback_cap_divisor,
        fail_open=fail_open,
        limiter_name=name,
    )


# ---------------------------------------------------------------------------
# 1. _CircuitBreaker state machine
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    async def test_initial_state_is_closed(self) -> None:
        """Fresh circuit breaker starts in CLOSED state."""
        cb = _CircuitBreaker()
        assert await cb.state() == "closed"

    async def test_closed_state_returns_go(self) -> None:
        """acquire_attempt() returns 'go' when circuit is closed."""
        cb = _CircuitBreaker()
        result = await cb.acquire_attempt()
        assert result == "go"

    async def test_record_failure_increments_counter(self) -> None:
        """Each record_failure() call increments consecutive_errors."""
        cb = _CircuitBreaker()
        for i in range(1, 5):
            await cb.record_failure()
            async with cb._lock:
                assert cb.consecutive_errors == i

    async def test_circuit_opens_at_k_failures(self) -> None:
        """After K=10 consecutive failures, circuit transitions to OPEN."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K - 1):
            await cb.record_failure()
        assert await cb.state() == "closed"

        await cb.record_failure()  # K-th failure
        assert await cb.state() == "open"

    async def test_open_circuit_returns_skip(self) -> None:
        """acquire_attempt() returns 'skip' when circuit is open."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()
        result = await cb.acquire_attempt()
        assert result == "skip"

    async def test_circuit_transitions_to_half_open_after_cooldown(
        self, monkeypatch: Any
    ) -> None:
        """After COOLDOWN_SECONDS, circuit transitions from OPEN to HALF_OPEN."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()
        assert await cb.state() == "open"

        # Advance monotonic clock past cooldown
        original_monotonic = time.monotonic
        t0 = original_monotonic()
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
            assert await cb.state() == "half_open"

    async def test_half_open_admits_exactly_one_probe(
        self, monkeypatch: Any
    ) -> None:
        """In HALF_OPEN state, acquire_attempt() returns 'go' for the first call
        and 'skip' for concurrent subsequent calls."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()

        t0 = time.monotonic()
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
            result1 = await cb.acquire_attempt()
            result2 = await cb.acquire_attempt()

        assert result1 == "go"
        assert result2 == "skip"

    async def test_half_open_success_closes_circuit(
        self, monkeypatch: Any
    ) -> None:
        """A successful probe in HALF_OPEN state closes the circuit."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()

        t0 = time.monotonic()
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
            await cb.acquire_attempt()  # win the probe token

        await cb.record_success()
        assert await cb.state() == "closed"
        async with cb._lock:
            assert cb.consecutive_errors == 0

    async def test_half_open_failure_reopens_with_fresh_cooldown(
        self, monkeypatch: Any
    ) -> None:
        """A failed probe in HALF_OPEN state re-opens the circuit with a reset cooldown."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()

        t0 = time.monotonic()
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
            await cb.acquire_attempt()  # win the probe token
            # record_failure re-opens with monotonic() as opened_at
            await cb.record_failure()
            assert await cb.state() == "open"

    async def test_concurrent_acquire_at_most_one_half_open_probe(
        self, monkeypatch: Any
    ) -> None:
        """Under asyncio.gather, only ONE concurrent caller wins the half-open probe."""
        cb = _CircuitBreaker()
        for _ in range(_CB_K):
            await cb.record_failure()

        t0 = time.monotonic()
        with patch("src.kene_api.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
            results = await asyncio.gather(*[cb.acquire_attempt() for _ in range(20)])

        go_count = sum(1 for r in results if r == "go")
        assert go_count == 1, f"Expected exactly 1 'go' in half-open, got {go_count}"

    async def test_record_success_resets_counter_in_closed_state(self) -> None:
        """record_success() resets consecutive_errors even from closed state."""
        cb = _CircuitBreaker()
        for _ in range(5):
            await cb.record_failure()
        await cb.record_success()
        async with cb._lock:
            assert cb.consecutive_errors == 0
        assert await cb.state() == "closed"


# ---------------------------------------------------------------------------
# 2. SwitchableRateLimiter delegation
# ---------------------------------------------------------------------------


class TestSwitchableDelegation:
    """Verify SwitchableRateLimiter delegates to the correct backend."""

    async def test_flag_false_circuit_closed_uses_redis(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """When flag=False and circuit closed, delegates to Redis."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=5, requests_per_hour=100)

        # Spy on redis_limiter.check_rate_limit
        redis_spy = AsyncMock(return_value=None)
        sw.redis_limiter.check_rate_limit = redis_spy  # type: ignore[method-assign]

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        redis_spy.assert_awaited_once()

    async def test_flag_true_uses_local_fallback(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """When flag=True, delegates to fallback LocalRateLimiter (rollback path)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=5, requests_per_hour=100)

        redis_spy = AsyncMock(return_value=None)
        local_spy = AsyncMock(return_value=None)
        sw.redis_limiter.check_rate_limit = redis_spy  # type: ignore[method-assign]
        sw.fallback_limiter.check_rate_limit = local_spy  # type: ignore[method-assign]

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=True),
        ):
            await sw.check_rate_limit(_make_request())

        redis_spy.assert_not_awaited()
        local_spy.assert_awaited_once()

    async def test_circuit_open_uses_local_fallback(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """When circuit is OPEN, delegates to fallback LocalRateLimiter."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=5, requests_per_hour=100)

        # Open the circuit by forcing K failures
        for _ in range(_CB_K):
            await sw._circuit_breaker.record_failure()

        local_spy = AsyncMock(return_value=None)
        sw.fallback_limiter.check_rate_limit = local_spy  # type: ignore[method-assign]

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        local_spy.assert_awaited_once()

    async def test_redis_429_is_not_a_failure(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """A 429 HTTPException from Redis is re-raised without counting as a Redis error."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=1, requests_per_hour=100)

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # First request OK
            await sw.check_rate_limit(_make_request())
            # Second request → 429
            with pytest.raises(HTTPException) as exc_info:
                await sw.check_rate_limit(_make_request())

        assert exc_info.value.status_code == 429
        # Circuit must still be closed — 429 is not a Redis error
        assert await sw._circuit_breaker.state() == "closed"

    async def test_redis_connection_error_increments_circuit_breaker(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """A ConnectionError from Redis increments the circuit-breaker failure counter."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)

        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("Redis down")
        )

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # fail_open=True so no 429 — just logs and returns
            await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 1

    async def test_redis_timeout_error_increments_circuit_breaker(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """A TimeoutError from Redis increments the circuit-breaker failure counter."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)

        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.TimeoutError("Redis timeout")
        )

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 1


# ---------------------------------------------------------------------------
# 3. Emergency cap (AC-13)
# ---------------------------------------------------------------------------


class TestEmergencyCap:
    """Verify the fallback LocalRateLimiter has limits pre-divided by fallback_cap_divisor."""

    async def test_security_critical_fallback_limits_divided_by_10(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Security-critical limiter (divisor=10): fallback LocalRateLimiter has
        limits=original//10 at construction time (not per-request)."""
        sw = _make_switchable(
            fake_redis,
            requests_per_minute=60,
            requests_per_hour=300,
            fallback_cap_divisor=10,
        )
        assert sw.fallback_limiter.requests_per_minute == 6
        assert sw.fallback_limiter.requests_per_hour == 30

    async def test_throughput_limiter_fallback_limits_unchanged(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Throughput limiter (divisor=1): fallback LocalRateLimiter has unchanged limits."""
        sw = _make_switchable(
            fake_redis,
            requests_per_minute=120,
            requests_per_hour=2000,
            fallback_cap_divisor=1,
        )
        assert sw.fallback_limiter.requests_per_minute == 120
        assert sw.fallback_limiter.requests_per_hour == 2000

    async def test_emergency_cap_enforced_on_fallback_path(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Security-critical limiter: 11th request in the same minute via fallback → 429.

        fallback_rpm = 60 // 10 = 6; 7th request through the local backend raises 429.
        """
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(
            fake_redis,
            requests_per_minute=60,
            requests_per_hour=600,
            fallback_cap_divisor=10,
            fail_open=False,
        )

        # Force Redis errors so the circuit opens and we exercise the local path
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("Redis down")
        )

        request = _make_request()

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # fallback_rpm = 6; 6 requests should succeed
            for _ in range(6):
                await sw.check_rate_limit(request)

            # 7th request should be blocked by the local fallback's 6/min cap
            with pytest.raises(HTTPException) as exc_info:
                await sw.check_rate_limit(request)

        assert exc_info.value.status_code == 429

    async def test_divisor_minimum_is_1(
        self, fake_redis: Any
    ) -> None:
        """Divisor < 1 is coerced to 1 inside build_rate_limiter."""
        # SwitchableRateLimiter accepts divisor=0 but the factory coerces to 1.
        # Test the factory path.
        import os

        with patch.dict(os.environ, {"KENE_RATE_LIMIT_BACKEND": "redis"}):
            sw = build_rate_limiter(
                name="div_test",
                requests_per_minute=10,
                requests_per_hour=100,
                fallback_cap_divisor=0,
                redis_client=fake_redis,
            )
        assert type(sw).__name__ == "SwitchableRateLimiter"
        # max(1, 10 // max(1,0)) = max(1, 10) = 10
        assert sw.fallback_limiter.requests_per_minute == 10

    async def test_feature_flag_read_exception_falls_through_to_redis(
        self, fake_redis: Any, monkeypatch: Any, caplog: Any
    ) -> None:
        """G2 regression guard: if `is_feature_enabled` raises (flag-service
        unavailable), the limiter must fall through to the Redis path rather
        than propagating the exception. Asserts (a) no propagation, (b) Redis
        backend is exercised, (c) the failure is logged at ERROR (control-plane
        incident severity)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=5, requests_per_hour=100)

        redis_spy = AsyncMock(return_value=None)
        sw.redis_limiter.check_rate_limit = redis_spy  # type: ignore[method-assign]

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(side_effect=RuntimeError("flag service down")),
        ):
            request = _make_request()
            with caplog.at_level(logging.ERROR, logger="src.kene_api.rate_limiter"):
                await sw.check_rate_limit(request)

        redis_spy.assert_awaited_once()
        # ERROR-severity log with traceback — pins the I-3 contract so a future
        # refactor that downgrades it back to WARNING fails this test.
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "feature flag read failed" in r.getMessage()
        ]
        assert len(error_records) == 1, (
            f"expected exactly 1 ERROR log; got {len(error_records)}"
        )
        assert error_records[0].exc_info is not None, "exc_info must be attached"


# ---------------------------------------------------------------------------
# 4. Fail-open behavior (AC-17)
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Verify throughput limiters fail-open on Redis errors."""

    async def test_fail_open_on_redis_connection_error(
        self, fake_redis: Any, monkeypatch: Any, caplog: Any
    ) -> None:
        """fail_open=True + Redis ConnectionError → request is allowed (None returned),
        ERROR is logged."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("Redis down")
        )

        import logging

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ), caplog.at_level(logging.ERROR):
            result = await sw.check_rate_limit(_make_request())

        # Returns None — request allowed
        assert result is None
        # At least one ERROR-level log about failing open
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert any("failing open" in m or "fail_open" in m or "throughput" in m for m in error_messages), (
            f"Expected fail-open ERROR log, got: {error_messages}"
        )

    async def test_fail_open_on_circuit_open(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """fail_open=True + circuit OPEN → request is allowed through."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)

        for _ in range(_CB_K):
            await sw._circuit_breaker.record_failure()

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            result = await sw.check_rate_limit(_make_request())

        assert result is None

    async def test_fail_closed_uses_local_on_redis_error(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """fail_open=False + Redis ConnectionError → delegates to LocalRateLimiter (fail-closed)."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=False, requests_per_minute=5)
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("Redis down")
        )

        local_spy = AsyncMock(return_value=None)
        sw.fallback_limiter.check_rate_limit = local_spy  # type: ignore[method-assign]

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        local_spy.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. build_rate_limiter factory return types (AC-11)
# ---------------------------------------------------------------------------


class TestFactoryReturnType:
    def test_redis_backend_returns_switchable_rate_limiter(
        self, monkeypatch: Any
    ) -> None:
        """KENE_RATE_LIMIT_BACKEND=redis → SwitchableRateLimiter."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        fake_r = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="factory_redis_test",
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=fake_r,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.redis_limiter.redis_client is fake_r

    def test_memory_backend_still_returns_local_rate_limiter(
        self, monkeypatch: Any
    ) -> None:
        """KENE_RATE_LIMIT_BACKEND=memory → LocalRateLimiter (unchanged)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        limiter = build_rate_limiter(
            name="factory_memory_test",
            requests_per_minute=10,
            requests_per_hour=100,
        )
        assert type(limiter).__name__ == "LocalRateLimiter"

    def test_redis_backend_default(self, monkeypatch: Any) -> None:
        """Without KENE_RATE_LIMIT_BACKEND set, defaults to redis → SwitchableRateLimiter."""
        monkeypatch.delenv("KENE_RATE_LIMIT_BACKEND", raising=False)
        fake_r = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="factory_default_test",
            requests_per_minute=10,
            requests_per_hour=100,
            redis_client=fake_r,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"

    def test_switchable_wraps_emergency_capped_local(self, monkeypatch: Any) -> None:
        """Redis branch: fallback LocalRateLimiter has limits divided by fallback_cap_divisor."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        fake_r = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="factory_cap_test",
            requests_per_minute=60,
            requests_per_hour=300,
            fallback_cap_divisor=10,
            redis_client=fake_r,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.fallback_limiter.requests_per_minute == 6
        assert limiter.fallback_limiter.requests_per_hour == 30

    def test_limiter_name_preserved(self, monkeypatch: Any) -> None:
        """limiter_name is propagated to SwitchableRateLimiter."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        fake_r = fakeredis.aioredis.FakeRedis(decode_responses=False)
        limiter = build_rate_limiter(
            name="my_custom_limiter",
            requests_per_minute=5,
            requests_per_hour=50,
            redis_client=fake_r,
        )
        assert limiter.limiter_name == "my_custom_limiter"


# ---------------------------------------------------------------------------
# 6. Redis error taxonomy — only ConnectionError / TimeoutError count as failures
# ---------------------------------------------------------------------------


class TestRedisErrorTaxonomy:
    """Only ConnectionError and TimeoutError should increment the circuit breaker.
    Other exceptions (e.g. redis.exceptions.ResponseError) should also record
    failure and re-raise.  HTTPException(429) must NOT count as a failure.
    """

    async def test_connection_error_triggers_record_failure(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """ConnectionError → record_failure() called; fail_open allows request through."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("conn refused")
        )

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 1

    async def test_timeout_error_triggers_record_failure(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """TimeoutError → record_failure() called."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.TimeoutError("timed out")
        )

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 1

    async def test_http_429_does_not_count_as_redis_failure(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """HTTPException(429) from Redis is a legitimate denial — not a Redis error."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, requests_per_minute=1, requests_per_hour=100)

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # First request → OK
            await sw.check_rate_limit(_make_request())
            # Second request → 429
            with pytest.raises(HTTPException):
                await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 0

    async def test_unexpected_redis_exception_reopens_circuit(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """An unexpected non-ConnectionError, non-TimeoutError Redis exception still
        increments the failure counter and is re-raised."""

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis)
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=ValueError("unexpected")
        )

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(ValueError, match="unexpected"):
                await sw.check_rate_limit(_make_request())

        async with sw._circuit_breaker._lock:
            assert sw._circuit_breaker.consecutive_errors == 1


# ---------------------------------------------------------------------------
# 7. Circuit opens at K=10 and remains open for COOLDOWN_SECONDS (AC-14)
# ---------------------------------------------------------------------------


class TestCircuitBreakerFullCycle:
    async def test_circuit_opens_after_10_consecutive_errors_and_closes_after_cooldown(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Full AC-14 cycle: K=10 errors → open → cooldown → half-open probe → closed.

        Side-effect accounting:
          - Redis is called K=10 times (loop below) → 10 ConnectionErrors → circuit opens.
          - When circuit is OPEN, acquire_attempt() returns "skip" → Redis is NOT called.
          - When circuit is HALF_OPEN, one probe is admitted → Redis call #11 = None (success).
        """
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        sw = _make_switchable(fake_redis, fail_open=True)

        # K ConnectionErrors then one successful None (for the half-open probe).
        redis_responses: list[Exception | None] = [
            redis_exc.ConnectionError("down") for _ in range(_CB_K)
        ] + [None]
        sw.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_responses
        )

        t0 = time.monotonic()

        with patch.object(
            rate_limiter_module,
            "is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # K errors → circuit opens
            for _ in range(_CB_K):
                await sw.check_rate_limit(_make_request())

            assert await sw._circuit_breaker.state() == "open"
            # Redis was called exactly K times
            assert sw.redis_limiter.check_rate_limit.await_count == _CB_K

            # One more request — circuit is OPEN → acquire_attempt() returns "skip"
            # → Redis NOT called (fail_open path returns early)
            await sw.check_rate_limit(_make_request())
            assert sw.redis_limiter.check_rate_limit.await_count == _CB_K  # unchanged

            # Advance past cooldown → circuit transitions to HALF_OPEN
            with patch("src.kene_api.rate_limiter.time") as mock_time:
                mock_time.monotonic.return_value = t0 + _CB_COOLDOWN_SECONDS + 1
                assert await sw._circuit_breaker.state() == "half_open"

                # Probe succeeds (side_effect[K] = None) → circuit closes
                await sw.check_rate_limit(_make_request())

            assert await sw._circuit_breaker.state() == "closed"
