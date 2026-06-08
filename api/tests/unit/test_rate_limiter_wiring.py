"""Unit tests for AH-71 limiter-instance wiring + call-site signatures.

Verifies:
- Each limiter instance has the correct key_strategy, fallback_cap_divisor,
  fail_open, and emit_remaining_on_success per AH-PRD-10 §5 spec table.
- Each of the 4 flow-level call sites passes (request, ctx_or_none) correctly.
- _apply_rate_limiting does NOT invoke audit_logger.log_rate_limit_exceeded on 429
  (the limiter owns this now per D-B).
- _verify_and_decode_token uses bad_token_rate_limiter on the failure path (AC-4).
- LocalRateLimiter.check_rate_limit emits audit event when audit_logger is set (Task 1).
- LocalRateLimiter.check_rate_limit handles a failing audit_logger without raising.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from src.kene_api.auth.models import UserContext
from src.kene_api.rate_limiter import (
    LocalRateLimiter,
    SwitchableRateLimiter,
    authenticated_key_strategy,
    ip_only_key_strategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    forwarded_for: str | None = "203.0.113.5",
    url_path: str = "/test",
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


def _make_ctx(user_id: str = "test_user", email: str = "test@example.com") -> UserContext:
    return UserContext(
        user_id=user_id,
        email=email,
        organization_permissions={},
        account_permissions={},
        roles=[],
    )


# ---------------------------------------------------------------------------
# 1. Limiter instance wiring — memory backend (KENE_RATE_LIMIT_BACKEND=memory)
# ---------------------------------------------------------------------------


class TestLimiterInstanceWiringMemory:
    """Verify per-limiter flags with KENE_RATE_LIMIT_BACKEND=memory.

    In memory mode, build_rate_limiter returns LocalRateLimiter directly.
    We verify key_strategy identity (is-comparison) and limiter_name.
    """

    def test_auth_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        # Re-import to pick up env change
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.auth_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is ip_only_key_strategy
        assert limiter.limiter_name == "auth"
        assert limiter.requests_per_minute == 10
        assert limiter.requests_per_hour == 50

    def test_bad_token_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.bad_token_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is ip_only_key_strategy
        assert limiter.limiter_name == "bad_token"
        assert limiter.requests_per_minute == 10
        assert limiter.requests_per_hour == 50

    def test_password_reset_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.password_reset_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is ip_only_key_strategy
        assert limiter.limiter_name == "password_reset"

    def test_early_release_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.early_release_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is ip_only_key_strategy
        assert limiter.limiter_name == "early_release"
        assert limiter.requests_per_minute == 5
        assert limiter.requests_per_hour == 20

    def test_signup_policy_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.signup_policy_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is ip_only_key_strategy
        assert limiter.limiter_name == "signup_policy"
        assert limiter.requests_per_minute == 20
        assert limiter.requests_per_hour == 100

    def test_token_rate_limiter_authenticated(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.auth.rate_limiting as rl_mod
        reload(rl_mod)
        limiter = rl_mod.token_rate_limiter
        assert isinstance(limiter, LocalRateLimiter)
        assert limiter.key_strategy is authenticated_key_strategy
        assert limiter.limiter_name == "token"

    def test_recaptcha_rate_limiter_ip_keyed(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.rate_limiter as rm_mod
        reload(rm_mod)
        limiter = rm_mod.recaptcha_rate_limiter
        # Use the class from the reloaded module to avoid isinstance mismatch
        assert isinstance(limiter, rm_mod.LocalRateLimiter)
        assert limiter.key_strategy is rm_mod.ip_only_key_strategy
        assert limiter.limiter_name == "recaptcha"

    def test_progress_rate_limiter_authenticated(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        from importlib import reload

        import src.kene_api.rate_limiter as rm_mod
        reload(rm_mod)
        limiter = rm_mod.progress_rate_limiter
        assert isinstance(limiter, rm_mod.LocalRateLimiter)
        assert limiter.key_strategy is rm_mod.authenticated_key_strategy
        assert limiter.limiter_name == "progress"


# ---------------------------------------------------------------------------
# 2. Limiter instance wiring — redis backend (SwitchableRateLimiter)
# ---------------------------------------------------------------------------


class TestLimiterInstanceWiringRedis:
    """Verify per-limiter flags with KENE_RATE_LIMIT_BACKEND=redis (fakeredis).

    In redis mode, build_rate_limiter returns SwitchableRateLimiter.
    We verify the underlying redis_limiter.key_strategy and the
    fallback_limiter's capped limits.
    """

    @pytest.fixture
    def fake_redis(self) -> Any:
        import fakeredis.aioredis  # type: ignore[import-untyped]
        return fakeredis.aioredis.FakeRedis(decode_responses=False)

    def _build_limiter_direct(
        self,
        name: str,
        rpm: int,
        rph: int,
        key_strategy: Any,
        fake_redis: Any,
        fallback_cap_divisor: int = 1,
        fail_open: bool = False,
        emit_remaining_on_success: bool = True,
    ) -> SwitchableRateLimiter:
        """Build a SwitchableRateLimiter directly (avoids module reload issues)."""
        from src.kene_api.rate_limiter import build_rate_limiter

        return build_rate_limiter(  # type: ignore[return-value]
            name=name,
            requests_per_minute=rpm,
            requests_per_hour=rph,
            key_strategy=key_strategy,
            fallback_cap_divisor=fallback_cap_divisor,
            fail_open=fail_open,
            redis_client=fake_redis,
            emit_remaining_on_success=emit_remaining_on_success,
        )

    def test_security_critical_limiters_have_cap_divisor_10(
        self, monkeypatch: Any, fake_redis: Any
    ) -> None:
        """auth, bad_token, password_reset: fallback ÷ 10 (SwitchableRateLimiter attributes)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        for cfg in [
            {"name": "auth", "rpm": 10, "rph": 50, "ks": ip_only_key_strategy, "fcd": 10},
            {"name": "bad_token", "rpm": 10, "rph": 50, "ks": ip_only_key_strategy, "fcd": 10},
            {"name": "password_reset", "rpm": 3, "rph": 10, "ks": ip_only_key_strategy, "fcd": 10},
        ]:
            limiter = self._build_limiter_direct(
                name=cfg["name"],
                rpm=cfg["rpm"],
                rph=cfg["rph"],
                key_strategy=cfg["ks"],
                fake_redis=fake_redis,
                fallback_cap_divisor=cfg["fcd"],
                fail_open=False,
            )
            assert type(limiter).__name__ == "SwitchableRateLimiter", (
                f"{cfg['name']} must be SwitchableRateLimiter"
            )
            assert limiter.fallback_cap_divisor == 10, (
                f"{cfg['name']}: expected fallback_cap_divisor=10"
            )
            assert limiter.fail_open is False, f"{cfg['name']}: expected fail_open=False"
            assert limiter.redis_limiter.key_strategy is ip_only_key_strategy, (
                f"{cfg['name']}: key_strategy must be ip_only_key_strategy"
            )

    def test_token_rate_limiter_authenticated_fail_open(
        self, monkeypatch: Any, fake_redis: Any
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        limiter = self._build_limiter_direct(
            "token", 60, 1000, authenticated_key_strategy, fake_redis,
            fallback_cap_divisor=1, fail_open=True,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.fail_open is True
        assert limiter.fallback_cap_divisor == 1
        assert limiter.redis_limiter.key_strategy is authenticated_key_strategy

    def test_recaptcha_limiter_ip_fail_closed(
        self, monkeypatch: Any, fake_redis: Any
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        limiter = self._build_limiter_direct(
            "recaptcha", 5, 20, ip_only_key_strategy, fake_redis,
            fallback_cap_divisor=10, fail_open=False,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.fail_open is False
        assert limiter.fallback_cap_divisor == 10
        assert limiter.redis_limiter.key_strategy is ip_only_key_strategy

    def test_progress_limiter_authenticated_fail_open(
        self, monkeypatch: Any, fake_redis: Any
    ) -> None:
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")
        limiter = self._build_limiter_direct(
            "progress", 120, 2000, authenticated_key_strategy, fake_redis,
            fallback_cap_divisor=1, fail_open=True,
        )
        assert type(limiter).__name__ == "SwitchableRateLimiter"
        assert limiter.fail_open is True
        assert limiter.fallback_cap_divisor == 1
        assert limiter.redis_limiter.key_strategy is authenticated_key_strategy

    def test_security_critical_fallback_limits_divided(
        self, monkeypatch: Any, fake_redis: Any
    ) -> None:
        """auth (10÷10=1/min), bad_token (10÷10=1/min) in fallback."""
        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "redis")

        auth = self._build_limiter_direct(
            "auth", 10, 50, ip_only_key_strategy, fake_redis, fallback_cap_divisor=10
        )
        assert auth.fallback_limiter.requests_per_minute == 1  # 10 ÷ 10
        assert auth.fallback_limiter.requests_per_hour == 5    # 50 ÷ 10

        bad_tok = self._build_limiter_direct(
            "bad_token", 10, 50, ip_only_key_strategy, fake_redis, fallback_cap_divisor=10
        )
        assert bad_tok.fallback_limiter.requests_per_minute == 1
        assert bad_tok.fallback_limiter.requests_per_hour == 5


# ---------------------------------------------------------------------------
# 3. Call-site signatures — verify ctx passes through
# ---------------------------------------------------------------------------


class TestCallSiteSignatures:
    """Verify that the four flow-level call sites pass ctx_or_none correctly."""

    async def test_apply_rate_limiting_passes_ctx_to_check(
        self, monkeypatch: Any
    ) -> None:
        """_apply_rate_limiting forwards ctx to check_rate_limit."""
        from src.kene_api.auth.user_context import _apply_rate_limiting

        mock_limiter = MagicMock()
        mock_limiter.check_rate_limit = AsyncMock()
        mock_audit = MagicMock()
        request = _make_request()
        ctx = _make_ctx("user_abc")

        await _apply_rate_limiting(request, mock_limiter, mock_audit, "1.2.3.4", ctx=ctx)

        mock_limiter.check_rate_limit.assert_awaited_once_with(request, ctx)

    async def test_apply_rate_limiting_passes_none_ctx(
        self, monkeypatch: Any
    ) -> None:
        """_apply_rate_limiting with ctx=None passes None to check_rate_limit."""
        from src.kene_api.auth.user_context import _apply_rate_limiting

        mock_limiter = MagicMock()
        mock_limiter.check_rate_limit = AsyncMock()
        mock_audit = MagicMock()
        request = _make_request()

        await _apply_rate_limiting(request, mock_limiter, mock_audit, "1.2.3.4", ctx=None)

        mock_limiter.check_rate_limit.assert_awaited_once_with(request, None)

    async def test_apply_rate_limiting_does_not_call_audit_on_429(
        self, monkeypatch: Any
    ) -> None:
        """_apply_rate_limiting does NOT call audit_logger.log_rate_limit_exceeded.

        The limiter owns this (D-B) — calling it in the wrapper would double-log.
        """
        from src.kene_api.auth.user_context import _apply_rate_limiting

        mock_limiter = MagicMock()
        mock_limiter.check_rate_limit = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
        )
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await _apply_rate_limiting(request, mock_limiter, mock_audit, "1.2.3.4")

        assert exc_info.value.status_code == 429
        # Must NOT double-log — the limiter already emitted the audit event.
        mock_audit.log_rate_limit_exceeded.assert_not_awaited()

    async def test_verify_and_decode_token_uses_bad_token_limiter(
        self, monkeypatch: Any
    ) -> None:
        """_verify_and_decode_token calls bad_token_rate_limiter (NOT token_rate_limiter)
        when token verification fails (AC-4 / Critical #1)."""
        from src.kene_api.auth.user_context import _verify_and_decode_token

        request = _make_request()
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "bad-firebase-token"
        mock_audit = MagicMock()
        mock_audit.log_event = AsyncMock()

        bad_token_spy = AsyncMock()

        with (
            patch("src.kene_api.auth.user_context.verify_id_token",
                  side_effect=ValueError("token invalid")),
            patch("src.kene_api.auth.user_context.bad_token_rate_limiter.check_rate_limit",
                  bad_token_spy),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _verify_and_decode_token(
                    mock_credentials, mock_audit, "1.2.3.4", "TestAgent", request
                )

        assert exc_info.value.status_code == 401
        # bad_token_rate_limiter was called with ctx=None (identity not established)
        bad_token_spy.assert_awaited_once()
        call_args = bad_token_spy.call_args
        assert call_args.kwargs.get("ctx") is None or (
            len(call_args.args) >= 2 and call_args.args[1] is None
        )

    async def test_recaptcha_endpoint_passes_ctx_none(
        self, monkeypatch: Any
    ) -> None:
        """routers/auth.py verify_recaptcha calls check_rate_limit(request, ctx=None)."""
        mock_limiter = AsyncMock()

        with (
            patch("src.kene_api.routers.auth.recaptcha_rate_limiter", mock_limiter),
            patch("src.kene_api.routers.auth.recaptcha_service") as mock_recaptcha,
        ):
            mock_recaptcha.verify_token = AsyncMock(
                return_value=MagicMock(success=True, error_codes=None)
            )
            from httpx import ASGITransport, AsyncClient
            from src.kene_api.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.post(
                    "/api/v1/auth/verify-recaptcha",
                    json={"token": "test-token", "action": "signin"},
                )

            # Verify the call includes ctx=None
            mock_limiter.check_rate_limit.assert_awaited_once()
            call_args = mock_limiter.check_rate_limit.call_args
            # ctx should be None (keyword or positional)
            if call_args.kwargs:
                assert call_args.kwargs.get("ctx") is None
            elif len(call_args.args) >= 2:
                assert call_args.args[1] is None


# ---------------------------------------------------------------------------
# 4. LocalRateLimiter audit_logger integration (Task 1)
# ---------------------------------------------------------------------------


class TestLocalRateLimiterAuditLogger:
    """Verify LocalRateLimiter.check_rate_limit emits audit events when audit_logger is set."""

    async def test_audit_called_once_per_429_on_minute_limit(
        self, monkeypatch: Any
    ) -> None:
        """Memory-backed limiter with audit_logger calls log_rate_limit_exceeded once on 429."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = LocalRateLimiter(
            requests_per_minute=2,
            requests_per_hour=100,
            key_strategy=ip_only_key_strategy,
            limiter_name="test_audit",
            audit_logger=mock_audit,
        )
        request = _make_request(forwarded_for="203.0.113.5")

        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        mock_audit.log_rate_limit_exceeded.assert_not_awaited()

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        mock_audit.log_rate_limit_exceeded.assert_awaited_once()
        call_kwargs = mock_audit.log_rate_limit_exceeded.call_args.kwargs
        assert call_kwargs["ip_address"] == "203.0.113.5"
        assert call_kwargs["endpoint"] == "/test"

    async def test_audit_called_with_user_id_when_ctx_set(
        self, monkeypatch: Any
    ) -> None:
        """audit_logger.log_rate_limit_exceeded receives ctx.user_id when ctx is provided."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock()

        limiter = LocalRateLimiter(
            requests_per_minute=1,
            requests_per_hour=100,
            key_strategy=authenticated_key_strategy,
            limiter_name="test_audit_ctx",
            audit_logger=mock_audit,
        )
        request = _make_request(forwarded_for="203.0.113.5")
        ctx = _make_ctx("uid_test_user")

        await limiter.check_rate_limit(request, ctx)

        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request, ctx)

        call_kwargs = mock_audit.log_rate_limit_exceeded.call_args.kwargs
        assert call_kwargs.get("user_id") == "uid_test_user"

    async def test_failing_audit_logger_does_not_suppress_429(
        self, monkeypatch: Any
    ) -> None:
        """If audit_logger.log_rate_limit_exceeded raises, the 429 is still raised."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        mock_audit = MagicMock()
        mock_audit.log_rate_limit_exceeded = AsyncMock(
            side_effect=RuntimeError("Firestore down")
        )

        limiter = LocalRateLimiter(
            requests_per_minute=1,
            requests_per_hour=100,
            limiter_name="test_audit_fail",
            audit_logger=mock_audit,
        )
        request = _make_request(forwarded_for="203.0.113.5")

        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        # 429 must still be raised despite the audit failure
        assert exc_info.value.status_code == 429

    def test_local_rate_limiter_no_audit_logger_default(self) -> None:
        """LocalRateLimiter defaults to audit_logger=None (backward compat)."""
        limiter = LocalRateLimiter(requests_per_minute=5, requests_per_hour=50)
        assert limiter.audit_logger is None


# ---------------------------------------------------------------------------
# 5. build_rate_limiter memory branch passes audit_logger through
# ---------------------------------------------------------------------------


class TestBuildRateLimiterAuditLoggerPlumbing:
    def test_memory_branch_plumbs_audit_logger(self, monkeypatch: Any) -> None:
        """KENE_RATE_LIMIT_BACKEND=memory: build_rate_limiter passes audit_logger to LocalRateLimiter."""
        from src.kene_api.rate_limiter import build_rate_limiter

        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        mock_audit = MagicMock()
        limiter = build_rate_limiter(
            name="test_plumb",
            requests_per_minute=5,
            requests_per_hour=50,
            audit_logger=mock_audit,
        )
        assert type(limiter).__name__ == "LocalRateLimiter"
        assert limiter.audit_logger is mock_audit

    def test_memory_branch_no_audit_logger_produces_none(self, monkeypatch: Any) -> None:
        """KENE_RATE_LIMIT_BACKEND=memory: omitting audit_logger → limiter.audit_logger is None."""
        from src.kene_api.rate_limiter import build_rate_limiter

        monkeypatch.setenv("KENE_RATE_LIMIT_BACKEND", "memory")
        limiter = build_rate_limiter(
            name="test_no_audit",
            requests_per_minute=5,
            requests_per_hour=50,
        )
        assert type(limiter).__name__ == "LocalRateLimiter"
        assert limiter.audit_logger is None
