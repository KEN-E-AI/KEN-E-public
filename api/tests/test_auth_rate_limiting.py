"""Integration tests for auth endpoint rate limiting."""

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from src.kene_api.main import app


@pytest.fixture(autouse=True)
def reset_rate_limiter(monkeypatch) -> None:
    """Inject a fresh in-memory rate limiter at the configured limit (5/min).

    The global recaptcha_rate_limiter is now a SwitchableRateLimiter; without
    Redis in CI the emergency-capped fallback (1/min) breaks tests that rely
    on the 5/min configured rate.  A LocalRateLimiter is the correct test
    double for these endpoint integration tests — they verify endpoint behaviour,
    not the Redis fallback mechanism.
    """
    import src.kene_api.rate_limiter as rl_mod
    import src.kene_api.routers.auth as auth_mod
    from src.kene_api.rate_limiter import LocalRateLimiter, ip_only_key_strategy

    fresh = LocalRateLimiter(
        requests_per_minute=5,
        requests_per_hour=20,
        key_strategy=ip_only_key_strategy,
        limiter_name="recaptcha",
    )
    monkeypatch.setattr(rl_mod, "recaptcha_rate_limiter", fresh)
    monkeypatch.setattr(auth_mod, "recaptcha_rate_limiter", fresh)
    yield


@pytest.mark.asyncio
async def test_recaptcha_verification_rate_limit():
    """Test that reCAPTCHA verification endpoint has rate limiting."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make requests up to the limit (5 per minute)
        for i in range(5):
            response = await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": "signin"},
            )
            # These will fail due to invalid token, but that's OK - we're testing rate limiting
            assert response.status_code == status.HTTP_200_OK

        # 6th request should be rate limited
        response = await client.post(
            "/api/v1/auth/verify-recaptcha",
            json={"token": "test_token_6", "action": "signin"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Rate limit exceeded" in response.json()["detail"]
        assert response.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_different_endpoints_have_separate_limits():
    """Test that different endpoints don't share rate limits."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Use up the reCAPTCHA verification limit
        for i in range(5):
            await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": "signin"},
            )

        # Other endpoints should still work
        response = await client.get("/api/v1/auth/recaptcha-site-key")
        # This will fail if site key not configured, but won't be rate limited
        assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS
