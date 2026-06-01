"""Integration tests for auth endpoint rate limiting."""

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from src.kene_api.main import app
from src.kene_api.rate_limiter import recaptcha_rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()
    yield
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()


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
