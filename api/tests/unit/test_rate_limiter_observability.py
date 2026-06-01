"""Unit tests for AH-73 observability: structured logs + Prometheus counter wiring.

Covers:
1. XFF short-chain WARNING log (action="xff_short_chain") with documented fields.
2. 429 WARNING log (action="rate_limit_exceeded") from LocalRateLimiter + counter increment.
3. Redis-error ERROR log (action="redis_error") from SwitchableRateLimiter + counter increments.
4. Circuit-breaker state gauge transitions (closed=0, open=1, half_open=2).
5. Regression guard: ratelimit_backend_override_flips_total labels unchanged from AH-79.

All Redis interactions use fakeredis.aioredis.FakeRedis.
pytest-asyncio is configured in asyncio_mode=auto (see pytest.ini).
"""

from __future__ import annotations

import logging
import time
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
import src.kene_api.rate_limiter as rate_limiter_module
from fastapi import Request
from src.kene_api.metrics.rate_limiter_metrics import (
    ratelimit_429_total,
    ratelimit_backend_override_flips_total,
    ratelimit_circuit_breaker_state,
    ratelimit_local_fallback_total,
    ratelimit_redis_errors_total,
)
from src.kene_api.rate_limiter import (
    _CB_K,
    LocalRateLimiter,
    RedisRateLimiter,
    SwitchableRateLimiter,
    _CircuitBreaker,
    _validated_ip_key,
    ip_only_key_strategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    xff: str = "",
    path: str = "/test",
) -> Request:
    """Build a minimal Request with the given X-Forwarded-For header."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": b"",
        "headers": [
            (b"x-forwarded-for", xff.encode()),
        ],
    }
    return Request(scope)


def _counter_value(counter, **labels: str) -> float:
    """Return the current value of a labeled Prometheus Counter."""
    return counter.labels(**labels)._value.get()


def _gauge_value(gauge, **labels: str) -> float:
    """Return the current value of a labeled Prometheus Gauge."""
    return gauge.labels(**labels)._value.get()


# ---------------------------------------------------------------------------
# 1. XFF short-chain structured WARNING log
# ---------------------------------------------------------------------------


class TestXffShortChainLog:
    def test_short_chain_emits_warning_with_documented_fields(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "2")
        request = _make_request(xff="203.0.113.1", path="/api/test")

        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = _validated_ip_key(request)

        assert result == "ip:_no_xff_chain_"
        # Find the xff_short_chain record — message is "rate_limiter: xff_short_chain"
        records = [r for r in caplog.records if "rate_limiter: xff_short_chain" in r.getMessage()]
        assert len(records) >= 1, "Expected at least one xff_short_chain WARNING"

        # The extra fields are placed on the LogRecord directly via extra=
        record = records[0]
        # log_context embeds fields — check via record.__dict__
        record_dict = record.__dict__
        # The structured fields land either under json_fields or directly
        # depending on whether StructuredFormatter is installed. In tests,
        # they appear as attributes on the record dict from extra=log_context(...)
        # which returns {"json_fields": {...}} or similar.
        # Search for the action field in all string representations.
        record_str = str(record_dict)
        assert "xff_short_chain" in record_str
        assert "expected_hops" in record_str
        assert "actual_hops" in record_str
        assert "path" in record_str
        assert "xff_header" in record_str

    def test_short_chain_sentinel_returned(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "3")
        request = _make_request(xff="10.0.0.1, 10.0.0.2", path="/api/test")
        result = _validated_ip_key(request)
        assert result == "ip:_no_xff_chain_"

    def test_sufficient_chain_no_warning(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(xff="203.0.113.5", path="/api/test")

        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = _validated_ip_key(request)

        assert result == "ip:203.0.113.5"
        short_chain_records = [
            r for r in caplog.records if "rate_limiter: xff_short_chain" in r.getMessage()
        ]
        assert len(short_chain_records) == 0


# ---------------------------------------------------------------------------
# 2. 429 WARNING log + counter — LocalRateLimiter
# ---------------------------------------------------------------------------


class TestLocalRateLimiter429Log:
    @pytest.fixture
    def limiter(self) -> LocalRateLimiter:
        return LocalRateLimiter(
            requests_per_minute=1,
            requests_per_hour=100,
            key_strategy=ip_only_key_strategy,
            limiter_name="test_local",
        )

    async def test_minute_429_emits_warning_and_increments_counter(
        self,
        limiter: LocalRateLimiter,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(xff="1.2.3.4", path="/api/v1/test")

        before = _counter_value(ratelimit_429_total, limiter_name="test_local")

        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            await limiter.check_rate_limit(request)
            with pytest.raises(Exception):  # noqa: B017
                await limiter.check_rate_limit(request)

        after = _counter_value(ratelimit_429_total, limiter_name="test_local")
        assert after - before >= 1, "ratelimit_429_total should have incremented"

        # Find the 429 log record — message is "rate_limiter: 429",
        # action="rate_limit_exceeded" is in the extra dict on the record.
        records_429 = [
            r for r in caplog.records if "rate_limiter: 429" in r.getMessage()
        ]
        assert len(records_429) >= 1, "Expected a 429 WARNING log"
        record_str = str(records_429[0].__dict__)
        assert "limiter_name" in record_str
        assert "client_key" in record_str
        assert "window" in record_str
        assert "limit" in record_str
        assert "path" in record_str

    async def test_hour_429_increments_counter(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = LocalRateLimiter(
            requests_per_minute=100,
            requests_per_hour=1,
            key_strategy=ip_only_key_strategy,
            limiter_name="test_local_hour",
        )
        request = _make_request(xff="1.2.3.4", path="/api/hour")

        before = _counter_value(ratelimit_429_total, limiter_name="test_local_hour")
        await limiter.check_rate_limit(request)
        with pytest.raises(Exception):  # noqa: B017
            await limiter.check_rate_limit(request)

        after = _counter_value(ratelimit_429_total, limiter_name="test_local_hour")
        assert after - before >= 1


# ---------------------------------------------------------------------------
# 3. Redis-error ERROR log + counters — SwitchableRateLimiter
# ---------------------------------------------------------------------------


class TestSwitchableRedisErrorLog:
    def _make_switchable(self, limiter_name: str = "test_switch") -> SwitchableRateLimiter:

        fake_redis = fakeredis.aioredis.FakeRedis()
        redis_limiter = RedisRateLimiter(
            requests_per_minute=60,
            requests_per_hour=1000,
            redis_client=fake_redis,
            key_strategy=ip_only_key_strategy,
            limiter_name=limiter_name,
        )
        fallback_limiter = LocalRateLimiter(
            requests_per_minute=6,
            requests_per_hour=100,
            key_strategy=ip_only_key_strategy,
            limiter_name=f"{limiter_name}:fallback",
        )
        return SwitchableRateLimiter(
            redis_limiter=redis_limiter,
            fallback_limiter=fallback_limiter,
            fallback_cap_divisor=10,
            fail_open=False,
            limiter_name=limiter_name,
        )

    async def test_redis_connection_error_emits_structured_error_log(
        self,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import redis.exceptions

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = self._make_switchable("test_redis_err")
        request = _make_request(xff="5.6.7.8", path="/api/chat")

        # Patch feature flag to avoid Redis calls; then patch redis eval to raise ConnectionError
        with patch.object(
            rate_limiter_module, "is_feature_enabled", new=AsyncMock(return_value=False)
        ):
            limiter.redis_limiter.redis_client = AsyncMock()
            limiter.redis_limiter.redis_client.eval = AsyncMock(
                side_effect=redis.exceptions.ConnectionError("Connection refused")
            )

            err_before = _counter_value(
                ratelimit_redis_errors_total,
                limiter_name="test_redis_err",
                error_type="ConnectionError",
            )
            fallback_before = _counter_value(
                ratelimit_local_fallback_total, limiter_name="test_redis_err"
            )

            with caplog.at_level(logging.ERROR, logger="src.kene_api.rate_limiter"):
                await limiter.check_rate_limit(request)

        err_after = _counter_value(
            ratelimit_redis_errors_total,
            limiter_name="test_redis_err",
            error_type="ConnectionError",
        )
        fallback_after = _counter_value(
            ratelimit_local_fallback_total, limiter_name="test_redis_err"
        )

        assert err_after - err_before == 1, "ratelimit_redis_errors_total should increment"
        assert fallback_after - fallback_before == 1, "ratelimit_local_fallback_total should increment"

        # Verify structured ERROR log emitted — message is "rate_limiter: redis_error"
        error_records = [r for r in caplog.records if "rate_limiter: redis_error" in r.getMessage()]
        assert len(error_records) >= 1, "Expected a redis_error ERROR log"
        record_str = str(error_records[0].__dict__)
        assert "error_type" in record_str
        assert "fallback_active" in record_str
        assert "circuit_breaker_state" in record_str

    async def test_flag_driven_fallback_increments_local_fallback_counter(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = self._make_switchable("test_flag_fallback")
        request = _make_request(xff="9.10.11.12", path="/api/test")

        with patch.object(
            rate_limiter_module, "is_feature_enabled", new=AsyncMock(return_value=True)
        ):
            before = _counter_value(
                ratelimit_local_fallback_total, limiter_name="test_flag_fallback"
            )
            await limiter.check_rate_limit(request)
            after = _counter_value(
                ratelimit_local_fallback_total, limiter_name="test_flag_fallback"
            )

        assert after - before == 1, "Flag-driven fallback should increment local_fallback_total"


# ---------------------------------------------------------------------------
# 4. Circuit-breaker state gauge transitions
# ---------------------------------------------------------------------------


class TestCircuitBreakerGauge:
    async def test_gauge_open_on_k_failures(self) -> None:
        cb = _CircuitBreaker(limiter_name="test_cb_gauge")

        gauge_before = _gauge_value(ratelimit_circuit_breaker_state, limiter_name="test_cb_gauge")
        # Trigger K failures to open the circuit
        for _ in range(_CB_K):
            await cb.record_failure()

        gauge_after = _gauge_value(ratelimit_circuit_breaker_state, limiter_name="test_cb_gauge")
        assert gauge_after == 1.0, "Gauge should be 1 (open) after K failures"
        assert gauge_before != 1.0 or gauge_after == 1.0  # open is 1

    async def test_gauge_closed_after_success(self) -> None:
        cb = _CircuitBreaker(limiter_name="test_cb_closed")
        for _ in range(_CB_K):
            await cb.record_failure()
        assert _gauge_value(ratelimit_circuit_breaker_state, limiter_name="test_cb_closed") == 1.0

        await cb.record_success()
        assert _gauge_value(ratelimit_circuit_breaker_state, limiter_name="test_cb_closed") == 0.0

    async def test_gauge_half_open_on_cooldown_elapsed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.kene_api.rate_limiter import _CB_COOLDOWN_SECONDS

        cb = _CircuitBreaker(limiter_name="test_cb_halfopen")
        for _ in range(_CB_K):
            await cb.record_failure()

        # Advance monotonic time past cooldown
        original_monotonic = time.monotonic
        monkeypatch.setattr(
            "src.kene_api.rate_limiter.time.monotonic",
            lambda: original_monotonic() + _CB_COOLDOWN_SECONDS + 1,
        )

        result = await cb.acquire_attempt()
        assert result == "go"
        assert _gauge_value(ratelimit_circuit_breaker_state, limiter_name="test_cb_halfopen") == 2.0


# ---------------------------------------------------------------------------
# 5. Regression guard: ratelimit_backend_override_flips_total labels unchanged
# ---------------------------------------------------------------------------


class TestBackendOverrideFlipLabelRegression:
    def test_existing_counter_has_previous_and_new_enabled_labels(self) -> None:
        # Verify the label set from AH-79 is unchanged — relabeling would break
        # security_critical.py:106-109 and the existing test snapshot.
        metric = ratelimit_backend_override_flips_total
        # Access via .labels() — raises TypeError if label names differ
        child = metric.labels(previous_enabled="false", new_enabled="true")
        assert child is not None

    def test_backend_override_counter_importable_and_is_counter(self) -> None:
        from prometheus_client import Counter

        assert isinstance(ratelimit_backend_override_flips_total, Counter)
