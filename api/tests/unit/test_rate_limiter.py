"""Unit tests for KeyStrategy, LocalRateLimiter, and related rate-limiting utilities."""

import hashlib
import inspect
import logging
import re
from typing import ClassVar
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.rate_limiting import (
    auth_rate_limiter,
    password_reset_rate_limiter,
    token_rate_limiter,
)
from src.kene_api.rate_limiter import (
    LocalRateLimiter,
    RateLimiter,
    _validated_ip_key,
    authenticated_key_strategy,
    ip_only_key_strategy,
    progress_rate_limiter,
    recaptcha_rate_limiter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    client_host: str = "127.0.0.1",
    forwarded_for: str | None = None,
    url_path: str = "/test",
) -> Request:
    """Create a minimal mock Request."""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = client_host
    headers: dict[str, str] = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    request.headers = headers
    request.url = MagicMock()
    request.url.path = url_path
    return request


def _make_ctx(user_id: str = "test_user") -> UserContext:
    """Create a minimal UserContext."""
    return UserContext(
        user_id=user_id,
        email="test@example.com",
        organization_permissions={},
    )


def _sha256_16(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 1. _validated_ip_key — table-driven (trusted_hops scenarios)
# ---------------------------------------------------------------------------


class TestValidatedIpKey:
    def test_no_xff_header_returns_sentinel(self, monkeypatch, caplog):
        """No X-Forwarded-For → sentinel + WARNING log."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for=None)
        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = _validated_ip_key(request)
        assert result == "ip:_no_xff_chain_"
        assert any("no_xff_chain" in r.message.lower() or "short" in r.message.lower() for r in caplog.records)

    def test_single_entry_trusted_hops_1(self, monkeypatch):
        """1-entry XFF with trusted_hops=1 returns that entry."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="203.0.113.5")
        result = _validated_ip_key(request)
        assert result == "ip:203.0.113.5"

    def test_two_entries_trusted_hops_1_uses_last(self, monkeypatch):
        """2-entry XFF, trusted_hops=1: use chain[-1] (the trusted-proxy-visible source)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1, 203.0.113.5")
        result = _validated_ip_key(request)
        assert result == "ip:203.0.113.5"

    def test_two_entries_trusted_hops_2_uses_correct_position(self, monkeypatch):
        """2-entry XFF, trusted_hops=2: chain[-2] = the real client."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "2")
        request = _make_request(forwarded_for="10.0.0.1, 203.0.113.5")
        result = _validated_ip_key(request)
        assert result == "ip:10.0.0.1"

    def test_spoofed_prefix_trusted_hops_1_ignores_attacker(self, monkeypatch):
        """3-entry XFF (attacker-supplied prefix), trusted_hops=1: keyed off chain[-1]."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="1.2.3.4, 5.6.7.8, 203.0.113.5")
        result = _validated_ip_key(request)
        assert result == "ip:203.0.113.5"

    def test_short_chain_returns_sentinel_and_warns(self, monkeypatch, caplog):
        """Chain shorter than trusted_hops → sentinel + WARNING."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "3")
        request = _make_request(forwarded_for="10.0.0.1")  # only 1 entry, need 3
        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = _validated_ip_key(request)
        assert result == "ip:_no_xff_chain_"
        assert any(r.levelname == "WARNING" for r in caplog.records)

    def test_empty_xff_header_returns_sentinel(self, monkeypatch, caplog):
        """Empty X-Forwarded-For string → sentinel."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="")
        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = _validated_ip_key(request)
        assert result == "ip:_no_xff_chain_"

    def test_no_request_client_host_fallback(self, monkeypatch):
        """Even if request.client.host is set, no-XFF case returns sentinel (no host fallback)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(client_host="192.168.1.1", forwarded_for=None)
        result = _validated_ip_key(request)
        # Must NOT return "ip:192.168.1.1"
        assert result == "ip:_no_xff_chain_"


# ---------------------------------------------------------------------------
# 2. ip_only_key_strategy — default-strategy regression guard
# ---------------------------------------------------------------------------


class TestIpOnlyKeyStrategy:
    def test_returns_validated_ip(self, monkeypatch):
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.5")
        result = ip_only_key_strategy(request, None)
        assert result == "ip:10.0.0.5"

    def test_ctx_is_ignored(self, monkeypatch):
        """ip_only_key_strategy ignores ctx regardless of value."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.5")
        ctx = _make_ctx("some_user")
        result_with_ctx = ip_only_key_strategy(request, ctx)
        result_without_ctx = ip_only_key_strategy(request, None)
        assert result_with_ctx == result_without_ctx


# ---------------------------------------------------------------------------
# 3. authenticated_key_strategy
# ---------------------------------------------------------------------------


class TestAuthenticatedKeyStrategy:
    def test_uses_hashed_user_id(self, monkeypatch):
        """ctx.user_id is hashed via sha256[:16], key starts with uid:."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1")
        ctx = _make_ctx("abc")
        result = authenticated_key_strategy(request, ctx)
        expected_hash = _sha256_16("abc")
        assert result == f"uid:{expected_hash}"

    def test_ctx_none_falls_back_to_ip_and_warns(self, monkeypatch, caplog):
        """When ctx is None, falls back to _validated_ip_key + emits WARNING."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="203.0.113.9")
        with caplog.at_level(logging.WARNING, logger="src.kene_api.rate_limiter"):
            result = authenticated_key_strategy(request, None)
        assert result == "ip:203.0.113.9"
        assert any(r.levelname == "WARNING" for r in caplog.records)

    def test_different_user_ids_produce_different_keys(self, monkeypatch):
        """Two distinct user IDs must produce distinct keys (no collision)."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1")
        key_a = authenticated_key_strategy(request, _make_ctx("alice"))
        key_b = authenticated_key_strategy(request, _make_ctx("bob"))
        assert key_a != key_b

    def test_key_format(self, monkeypatch):
        """Key must match uid:[0-9a-f]{16}."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1")
        ctx = _make_ctx("some_user_123")
        result = authenticated_key_strategy(request, ctx)
        assert re.match(r"^uid:[0-9a-f]{16}$", result), f"Key format wrong: {result}"


# ---------------------------------------------------------------------------
# 4. Adversarial UID hashing
# ---------------------------------------------------------------------------


class TestAdversarialUids:
    ADVERSARIAL_UIDS: ClassVar[list[str]] = [
        "oidc:sub:value",  # contains colons
        "üser_id_тест",  # unicode
        "x" * 1024,  # 1KB length
        "",  # empty string
    ]

    def test_adversarial_uids_produce_distinct_keys(self, monkeypatch):
        """All 4 adversarial UIDs produce distinct, non-colliding hashed keys."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1")
        keys = [
            authenticated_key_strategy(request, _make_ctx(uid))
            for uid in self.ADVERSARIAL_UIDS
        ]
        # All succeed (no exception)
        assert len(keys) == 4
        # All distinct
        assert len(set(keys)) == 4, f"Collision detected in keys: {keys}"

    def test_adversarial_uids_match_format(self, monkeypatch):
        """Every adversarial UID result matches uid:[0-9a-f]{16}."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        request = _make_request(forwarded_for="10.0.0.1")
        for uid in self.ADVERSARIAL_UIDS:
            result = authenticated_key_strategy(request, _make_ctx(uid))
            assert re.match(r"^uid:[0-9a-f]{16}$", result), (
                f"Format wrong for uid={uid!r}: {result}"
            )


# ---------------------------------------------------------------------------
# 5. LocalRateLimiter — async interface + backward compat
# ---------------------------------------------------------------------------


class TestLocalRateLimiterAsync:
    def test_check_rate_limit_is_coroutine_function(self):
        """LocalRateLimiter.check_rate_limit must be a coroutine function."""
        limiter = LocalRateLimiter(requests_per_minute=10, requests_per_hour=100)
        assert inspect.iscoroutinefunction(limiter.check_rate_limit)

    async def test_check_rate_limit_returns_none_on_happy_path(self, monkeypatch):
        """await check_rate_limit() returns None when under the limit."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = LocalRateLimiter(requests_per_minute=10, requests_per_hour=100)
        request = _make_request(forwarded_for="10.0.0.1")
        result = await limiter.check_rate_limit(request)
        assert result is None

    async def test_default_strategy_enforces_minute_limit(self, monkeypatch):
        """Default ip_only_key_strategy: 3rd request raises 429 after 2-req limit."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = LocalRateLimiter(requests_per_minute=2, requests_per_hour=20)
        request = _make_request(forwarded_for="192.168.1.1")

        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "2 requests per minute" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    async def test_default_strategy_enforces_hour_limit(self, monkeypatch):
        """Default ip_only_key_strategy: hour limit is enforced."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = LocalRateLimiter(requests_per_minute=100, requests_per_hour=2)
        request = _make_request(forwarded_for="192.168.1.1")

        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "2 requests per hour" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "3600"

    async def test_ctx_param_accepted(self, monkeypatch):
        """check_rate_limit accepts optional ctx without error."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = LocalRateLimiter(requests_per_minute=10, requests_per_hour=100)
        request = _make_request(forwarded_for="10.0.0.1")
        ctx = _make_ctx("user_abc")
        result = await limiter.check_rate_limit(request, ctx)
        assert result is None


# ---------------------------------------------------------------------------
# 6. LocalRateLimiter constructor — limiter_name + key_strategy params
# ---------------------------------------------------------------------------


class TestLocalRateLimiterConstructor:
    def test_default_key_strategy_is_ip_only(self):
        limiter = LocalRateLimiter(requests_per_minute=5, requests_per_hour=50)
        assert limiter.key_strategy is ip_only_key_strategy

    def test_custom_key_strategy_stored(self):
        limiter = LocalRateLimiter(
            requests_per_minute=5,
            requests_per_hour=50,
            key_strategy=authenticated_key_strategy,
        )
        assert limiter.key_strategy is authenticated_key_strategy

    def test_default_limiter_name_is_default(self):
        limiter = LocalRateLimiter(requests_per_minute=5, requests_per_hour=50)
        assert limiter.limiter_name == "default"

    def test_custom_limiter_name_stored(self):
        limiter = LocalRateLimiter(
            requests_per_minute=5, requests_per_hour=50, limiter_name="recaptcha"
        )
        assert limiter.limiter_name == "recaptcha"


# ---------------------------------------------------------------------------
# 7. RateLimiter alias backward compat
# ---------------------------------------------------------------------------


class TestRateLimiterAlias:
    def test_rate_limiter_is_local_rate_limiter(self):
        """RateLimiter = LocalRateLimiter module-level alias."""
        assert RateLimiter is LocalRateLimiter

    def test_isinstance_check_works(self):
        instance = LocalRateLimiter(requests_per_minute=5, requests_per_hour=50)
        assert isinstance(instance, RateLimiter)


# ---------------------------------------------------------------------------
# 8. Global instances exported correctly
# ---------------------------------------------------------------------------


class TestGlobalInstances:
    def test_global_instances_have_limiter_names(self):
        assert recaptcha_rate_limiter.limiter_name == "recaptcha"
        assert progress_rate_limiter.limiter_name == "progress"

    def test_auth_limiter_instances_have_limiter_names(self):
        assert auth_rate_limiter.limiter_name == "auth"
        assert token_rate_limiter.limiter_name == "token"
        assert password_reset_rate_limiter.limiter_name == "password_reset"
