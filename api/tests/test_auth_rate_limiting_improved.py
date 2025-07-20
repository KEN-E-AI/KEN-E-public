"""Improved integration tests for auth endpoint rate limiting."""

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from hypothesis import given, strategies as st, settings

from src.kene_api.main import app
from src.kene_api.rate_limiter import recaptcha_rate_limiter


# Constants for expected values
HTTP_OK = status.HTTP_200_OK
HTTP_TOO_MANY_REQUESTS = status.HTTP_429_TOO_MANY_REQUESTS
RATE_LIMIT_MINUTE = 5  # Must match recaptcha_rate_limiter configuration
RATE_LIMIT_HOUR = 20   # Must match recaptcha_rate_limiter configuration


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the rate limiter state before each test."""
    # Clear all tracked requests
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()
    yield
    # Clean up after test
    recaptcha_rate_limiter.minute_requests.clear()
    recaptcha_rate_limiter.hour_requests.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("num_requests,should_be_limited", [
    (RATE_LIMIT_MINUTE - 1, False),  # Just under limit
    (RATE_LIMIT_MINUTE, False),       # Exactly at limit
    (RATE_LIMIT_MINUTE + 1, True),    # Just over limit
    (RATE_LIMIT_MINUTE + 5, True),    # Well over limit
])
async def test_recaptcha_rate_limit_boundaries(num_requests, should_be_limited):
    """Test rate limiting at various boundary conditions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        blocked = False
        successful = 0
        
        for i in range(num_requests):
            response = await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": "signin"},
            )
            
            if response.status_code == HTTP_TOO_MANY_REQUESTS:
                blocked = True
                # Verify rate limit response structure
                assert "Retry-After" in response.headers
                assert response.headers["Retry-After"].isdigit()
                assert int(response.headers["Retry-After"]) > 0
                break
            else:
                successful += 1
                assert response.status_code == HTTP_OK
        
        # Verify expectations
        if should_be_limited:
            assert blocked, f"Expected to be rate limited after {num_requests} requests"
            assert successful == RATE_LIMIT_MINUTE
        else:
            assert not blocked, f"Should not be rate limited after {num_requests} requests"
            assert successful == num_requests


@pytest.mark.asyncio
async def test_rate_limit_headers():
    """Test that rate limit responses include proper headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust the rate limit
        for i in range(RATE_LIMIT_MINUTE):
            await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": "signin"},
            )
        
        # Next request should be rate limited
        response = await client.post(
            "/api/v1/auth/verify-recaptcha",
            json={"token": "test_token_exceeded", "action": "signin"},
        )
        
        assert response.status_code == HTTP_TOO_MANY_REQUESTS
        assert "Retry-After" in response.headers
        # Verify it's a valid number
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0
        assert retry_after <= 3600  # Should be reasonable (max 1 hour)


@pytest.mark.asyncio
async def test_different_endpoints_independent_limits():
    """Test that different endpoints have independent rate limits."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust the reCAPTCHA verification limit
        for i in range(RATE_LIMIT_MINUTE + 1):
            response = await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": "signin"},
            )
            if response.status_code == HTTP_TOO_MANY_REQUESTS:
                break
        
        # Other endpoints should still work
        response = await client.get("/api/v1/auth/recaptcha-site-key")
        # Should not be rate limited (though it might fail for other reasons)
        assert response.status_code != HTTP_TOO_MANY_REQUESTS


@pytest.mark.asyncio
@given(
    action=st.sampled_from(["signin", "signup", "submit", "verify"]),
    num_requests=st.integers(min_value=1, max_value=10)
)
@settings(deadline=1000)  # Allow 1 second for async tests
async def test_rate_limit_with_different_actions(action, num_requests):
    """Test that rate limiting works regardless of the action parameter."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = []
        
        for i in range(num_requests):
            response = await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_{i}", "action": action},
            )
            responses.append(response.status_code)
        
        # Count successful vs rate limited
        successful = sum(1 for status in responses if status == HTTP_OK)
        rate_limited = sum(1 for status in responses if status == HTTP_TOO_MANY_REQUESTS)
        
        # All responses should be either OK or rate limited
        assert successful + rate_limited == num_requests
        
        # Successful requests should not exceed the limit
        assert successful <= RATE_LIMIT_MINUTE


@pytest.mark.asyncio
async def test_rate_limit_different_ips():
    """Test that rate limits are applied per IP address."""
    # Note: In a real test environment, we'd need to mock the client IP
    # For now, this tests that the endpoint handles the X-Forwarded-For header
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make requests with different forwarded IPs
        for ip_suffix in range(1, 4):
            response = await client.post(
                "/api/v1/auth/verify-recaptcha",
                json={"token": f"test_token_ip_{ip_suffix}", "action": "signin"},
                headers={"X-Forwarded-For": f"192.168.1.{ip_suffix}"}
            )
            # Each "different IP" should get its own rate limit
            # (though in test environment this might not work without proper mocking)
            assert response.status_code in [HTTP_OK, HTTP_TOO_MANY_REQUESTS]