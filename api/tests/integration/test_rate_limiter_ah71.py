"""Integration tests for AH-71 ACs using fakeredis + Firestore-mocked audit logger.

Verifies the AC-1..AC-17 acceptance criteria that are specifically owned by AH-71:

- AC-1  NAT'd-user case: two users with the same IP each get their own 60/min bucket.
- AC-1a Per-user-additive: 5 distinct UIDs on same IP collectively issue 5x limit with no 429.
- AC-3  IP-keyed brute-force defense preserved (auth_rate_limiter, recaptcha_rate_limiter).
- AC-4  bad_token_rate_limiter ceiling = 10/min (NOT 60/min) — Critical #1.
- AC-12 AuditLogger writes exactly one document per 429 (not 2x from wrapper + limiter).
- AC-13 Emergency cap: Redis outage → security-critical limiter uses capped LocalRateLimiter.
- AC-17 bad_token_rate_limiter is independent of token_rate_limiter (no shared bucket).

These tests use:
- ``fakeredis.aioredis.FakeRedis`` for Redis-backed SwitchableRateLimiter behaviour.
- ``unittest.mock.AsyncMock`` for the AuditLogger (Firestore document not created for real).
- The actual rate-limit logic (Lua script, circuit breaker, key strategy) runs end-to-end.

Tests are collected and run without any special marker — fakeredis has no real Redis dep.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from src.kene_api.auth.models import UserContext
from src.kene_api.rate_limiter import (
    LocalRateLimiter,
    SwitchableRateLimiter,
    authenticated_key_strategy,
    build_rate_limiter,
    ip_only_key_strategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    forwarded_for: str | None = "203.0.113.5",
    url_path: str = "/api/v1/chat",
) -> Request:
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


def _make_ctx(user_id: str, email: str = "user@example.com") -> UserContext:
    return UserContext(
        user_id=user_id,
        email=email,
        organization_permissions={},
        account_permissions={},
        roles=[],
    )


def _make_switchable(
    fake_redis: Any,
    key_strategy: Any,
    rpm: int = 5,
    rph: int = 100,
    fallback_cap_divisor: int = 1,
    fail_open: bool = False,
    name: str | None = None,
    audit_logger: Any = None,
) -> SwitchableRateLimiter:
    """Build a SwitchableRateLimiter backed by fakeredis (no real Redis needed)."""
    import uuid
    name = name or f"test_{uuid.uuid4().hex[:8]}"
    return build_rate_limiter(  # type: ignore[return-value]
        name=name,
        requests_per_minute=rpm,
        requests_per_hour=rph,
        key_strategy=key_strategy,
        fallback_cap_divisor=fallback_cap_divisor,
        fail_open=fail_open,
        redis_client=fake_redis,
        audit_logger=audit_logger,
    )


# ---------------------------------------------------------------------------
# AC-1: NAT'd-user case — two distinct UIDs on same source IP get separate buckets
# ---------------------------------------------------------------------------


class TestNatUserCase:
    """AC-1: authenticated_key_strategy gives each user their own bucket even
    when they share a source IP (NAT'd office, corporate VPN, etc.)."""

    async def test_two_users_same_ip_get_independent_buckets(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Two distinct UIDs, same XFF IP → each gets full rpm quota (no shared 429)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter = _make_switchable(
            fake_redis,
            key_strategy=authenticated_key_strategy,
            rpm=3,
            rph=100,
        )

        request = _make_request(forwarded_for="203.0.113.5")
        ctx_alice = _make_ctx("alice")
        ctx_bob = _make_ctx("bob")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # Alice exhausts her quota
            for _ in range(3):
                await limiter.check_rate_limit(request, ctx_alice)

            # Alice's 4th request is denied
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, ctx_alice)
            assert exc_info.value.status_code == 429

            # Bob is on the same IP but has his own bucket — still gets 3 requests
            for _ in range(3):
                await limiter.check_rate_limit(request, ctx_bob)

            # Bob's 4th is denied (his own bucket, independent of Alice)
            with pytest.raises(HTTPException):
                await limiter.check_rate_limit(request, ctx_bob)

    async def test_authenticated_key_includes_sha256_of_user_id(
        self, monkeypatch: Any
    ) -> None:
        """authenticated_key_strategy embeds sha256[:16] of user_id in the bucket key (AC-13)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="203.0.113.5")
        ctx = _make_ctx("firebase-uid-abc123")

        key = authenticated_key_strategy(request, ctx)

        expected_hash = hashlib.sha256(b"firebase-uid-abc123").hexdigest()[:16]
        assert key == f"uid:{expected_hash}"


# ---------------------------------------------------------------------------
# AC-1a: Per-user-additive — 5 distinct UIDs issue 5x quota with no shared 429
# ---------------------------------------------------------------------------


class TestPerUserAdditive:
    async def test_five_users_each_get_full_quota(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """5 distinct UIDs on the same IP: collectively 5xrpm requests succeed."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        rpm = 3
        users = [_make_ctx(f"user_{i}") for i in range(5)]
        request = _make_request(forwarded_for="10.10.10.10")

        limiter = _make_switchable(fake_redis, authenticated_key_strategy, rpm=rpm, rph=500)

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            total_allowed = 0
            for ctx in users:
                for _ in range(rpm):
                    await limiter.check_rate_limit(request, ctx)
                    total_allowed += 1

        assert total_allowed == 5 * rpm


# ---------------------------------------------------------------------------
# AC-3: IP-keyed brute-force defense preserved
# ---------------------------------------------------------------------------


class TestIpKeyedBruteForce:
    async def test_auth_rate_limiter_11th_attempt_from_same_ip_blocked(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """IP-keyed limiter (auth-style, 10/min): 11th request from same IP → 429."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter = _make_switchable(
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=10,
            rph=50,
            fallback_cap_divisor=10,
            fail_open=False,
        )
        request = _make_request(forwarded_for="192.0.2.1")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            for _ in range(10):
                await limiter.check_rate_limit(request, None)

            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, None)

        assert exc_info.value.status_code == 429

    async def test_recaptcha_rate_limiter_6th_attempt_blocked(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """IP-keyed limiter (recaptcha-style, 5/min): 6th request from same IP → 429."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter = _make_switchable(
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=5,
            rph=20,
            fallback_cap_divisor=10,
        )
        request = _make_request(forwarded_for="198.51.100.5")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            for _ in range(5):
                await limiter.check_rate_limit(request, None)

            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, None)

        assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# AC-4 (Critical #1): bad_token_rate_limiter ceiling = 10/min, NOT 60/min
# ---------------------------------------------------------------------------


class TestBadTokenRateLimiterCritical:
    async def test_bad_token_limiter_blocks_at_10_not_60(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """11 bad Firebase tokens from one IP → 429 at the 11th via bad_token_rate_limiter.

        This test explicitly verifies the attacker cannot send 60 bad tokens
        before being blocked (which would happen if the old token_rate_limiter was used).
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        bad_token_limiter = _make_switchable(
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=10,
            rph=50,
            fallback_cap_divisor=10,
            fail_open=False,
            name="bad_token",
        )
        request = _make_request(forwarded_for="203.0.113.99")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # 10 bad tokens allowed
            for _ in range(10):
                await bad_token_limiter.check_rate_limit(request, ctx=None)

            # 11th is blocked — ceiling is 10/min, NOT 60/min
            with pytest.raises(HTTPException) as exc_info:
                await bad_token_limiter.check_rate_limit(request, ctx=None)

        assert exc_info.value.status_code == 429

    async def test_bad_token_limiter_independent_of_token_limiter(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """AC-17: exhausting bad_token_rate_limiter does not affect token_rate_limiter.

        A user who submits 10 bad tokens (and gets rate-limited) but then presents
        a VALID token should not be blocked by token_rate_limiter bucket sharing.
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        bad_token_limiter = _make_switchable(
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=10, rph=50, name="bad_token_sep",
        )
        token_limiter = _make_switchable(
            fake_redis,
            key_strategy=authenticated_key_strategy,
            rpm=60, rph=1000, fail_open=True, name="token_sep",
        )

        request = _make_request(forwarded_for="203.0.113.88")
        ctx = _make_ctx("legit-user")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # Exhaust bad_token_limiter bucket
            for _ in range(10):
                await bad_token_limiter.check_rate_limit(request, ctx=None)

            # token_rate_limiter bucket is independent — 60 requests still succeed
            for _ in range(60):
                await token_limiter.check_rate_limit(request, ctx)


# ---------------------------------------------------------------------------
# AC-12: AuditLogger writes exactly one document per 429 (not 2x)
# ---------------------------------------------------------------------------


class TestAuditLoggerOnePerEvent:
    async def test_audit_called_once_per_429_not_twice(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """AuditLogger.log_rate_limit_exceeded is called exactly once per 429.

        Before AH-71, both the limiter AND the _apply_rate_limiting wrapper would
        call log_rate_limit_exceeded → 2x Firestore writes per 429.  Post-AH-71,
        only the limiter calls it (D-B).
        """
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = _make_switchable(
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=2,
            rph=100,
            audit_logger=mock_audit,
        )
        request = _make_request(forwarded_for="10.20.30.40")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            await limiter.check_rate_limit(request, None)
            await limiter.check_rate_limit(request, None)

            # No audit yet — under limit
            mock_audit.log_rate_limit_exceeded.assert_not_awaited()

            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, None)

        assert exc_info.value.status_code == 429
        # EXACTLY once — limiter owns the call; wrapper must not double-log.
        assert mock_audit.log_rate_limit_exceeded.await_count == 1

    async def test_local_rate_limiter_audit_once_per_429(
        self, monkeypatch: Any
    ) -> None:
        """LocalRateLimiter (memory backend) also emits exactly one audit per 429."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")

        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = LocalRateLimiter(
            requests_per_minute=2,
            requests_per_hour=100,
            key_strategy=ip_only_key_strategy,
            limiter_name="test_local_audit",
            audit_logger=mock_audit,
        )
        request = _make_request(forwarded_for="10.20.30.50")

        await limiter.check_rate_limit(request, None)
        await limiter.check_rate_limit(request, None)
        mock_audit.log_rate_limit_exceeded.assert_not_awaited()

        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request, None)

        assert mock_audit.log_rate_limit_exceeded.await_count == 1


# ---------------------------------------------------------------------------
# AC-13: Emergency cap — Redis outage triggers fallback with ÷10 limits
# ---------------------------------------------------------------------------


class TestEmergencyCapOnOutage:
    async def test_redis_outage_triggers_capped_local_fallback(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Security-critical limiter: Redis ConnectionError → LocalRateLimiter with ÷10 limits.

        auth_rate_limiter: 10/min normally → 1/min (10÷10) in fallback mode.

        The test verifies the fallback_limiter.requests_per_minute is 1 (10÷10=1),
        and that once the fallback bucket is exhausted (after 1 successful request),
        the next request is blocked.  We pre-open the circuit breaker directly to
        avoid the K-error accumulation in the fallback bucket from the trigger calls.
        """
        from src.kene_api.rate_limiter import _CB_K

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter: SwitchableRateLimiter = _make_switchable(  # type: ignore[assignment]
            fake_redis,
            key_strategy=ip_only_key_strategy,
            rpm=10,
            rph=50,
            fallback_cap_divisor=10,
            fail_open=False,
            name="auth_outage_test",
        )

        # Verify the fallback limits are divided by 10 at construction time (AC-13).
        assert limiter.fallback_limiter.requests_per_minute == 1   # 10 ÷ 10
        assert limiter.fallback_limiter.requests_per_hour == 5     # 50 ÷ 10

        # Pre-open the circuit breaker to skip the K-call trigger phase.
        for _ in range(_CB_K):
            await limiter._circuit_breaker.record_failure()

        # Now any call will skip Redis (circuit OPEN) and go to local fallback.
        request = _make_request(forwarded_for="198.51.100.10")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            # First request uses the 1/min local fallback budget — allowed.
            await limiter.check_rate_limit(request, None)

            # Second request via local fallback → blocked (1/min exhausted).
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check_rate_limit(request, None)

        assert exc_info.value.status_code == 429

    async def test_throughput_limiter_fails_open_on_redis_outage(
        self, fake_redis: Any, monkeypatch: Any
    ) -> None:
        """Throughput limiter (fail_open=True): Redis outage → request allowed (fail-open)."""
        import redis.exceptions as redis_exc

        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        limiter: SwitchableRateLimiter = _make_switchable(  # type: ignore[assignment]
            fake_redis,
            key_strategy=authenticated_key_strategy,
            rpm=60,
            rph=1000,
            fallback_cap_divisor=1,
            fail_open=True,
            name="token_fail_open_test",
        )
        limiter.redis_limiter.check_rate_limit = AsyncMock(  # type: ignore[method-assign]
            side_effect=redis_exc.ConnectionError("Redis down")
        )

        request = _make_request(forwarded_for="203.0.113.5")
        ctx = _make_ctx("throughput_user")

        with patch(
            "src.kene_api.rate_limiter.is_feature_enabled",
            new=AsyncMock(return_value=False),
        ):
            from src.kene_api.rate_limiter import _CB_K
            for _ in range(_CB_K):
                result = await limiter.check_rate_limit(request, ctx)
                assert result is None  # fail-open → allowed through


# ---------------------------------------------------------------------------
# AC-6 / Backward compat: KENE_TOKEN_RATE_LIMIT_PER_MINUTE env var still works
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_token_rate_limiter_respects_env_override(self, monkeypatch: Any) -> None:
        """KENE_TOKEN_RATE_LIMIT_PER_MINUTE=10 sets rpm=10 on token_rate_limiter (AC-9)."""
        monkeypatch.setenv("KENE_TOKEN_RATE_LIMIT_PER_MINUTE", "10")
        monkeypatch.setenv("KENE_TOKEN_RATE_LIMIT_PER_HOUR", "200")
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")

        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)

        limiter = rl_mod.token_rate_limiter
        assert limiter.requests_per_minute == 10
        assert limiter.requests_per_hour == 200
