"""Tests for rate limiting functionality."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request
from src.kene_api.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test the rate limiting functionality."""

    def create_mock_request(self, client_ip: str = "127.0.0.1") -> Request:
        """Create a mock request object with the given IP."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = client_ip
        request.headers = {}
        return request

    async def test_allows_requests_under_limit(self, monkeypatch):
        """Test that requests under the limit are allowed."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "0")
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=20)
        request = self.create_mock_request()
        request.headers = {"X-Forwarded-For": "127.0.0.1"}

        # Should allow 5 requests
        for _ in range(5):
            await limiter.check_rate_limit(request)  # Should not raise

    async def test_blocks_requests_over_minute_limit(self, monkeypatch):
        """Test that requests exceeding minute limit are blocked."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=20)
        request = self.create_mock_request()
        request.headers = {"X-Forwarded-For": "192.168.1.1"}

        # Allow first 3 requests
        for _ in range(3):
            await limiter.check_rate_limit(request)

        # 4th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "3 requests per minute" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    async def test_blocks_requests_over_hour_limit(self, monkeypatch):
        """Test that requests exceeding hour limit are blocked."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=100, requests_per_hour=5)
        request = self.create_mock_request()
        request.headers = {"X-Forwarded-For": "192.168.1.1"}

        # Allow first 5 requests
        for _ in range(5):
            await limiter.check_rate_limit(request)

        # 6th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "5 requests per hour" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "3600"

    async def test_different_clients_have_separate_limits(self, monkeypatch):
        """Test that different clients have independent rate limits."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)

        request1 = self.create_mock_request("192.168.1.1")
        request1.headers = {"X-Forwarded-For": "192.168.1.1"}
        request2 = self.create_mock_request("192.168.1.2")
        request2.headers = {"X-Forwarded-For": "192.168.1.2"}

        # Client 1 uses up their limit
        await limiter.check_rate_limit(request1)
        await limiter.check_rate_limit(request1)

        # Client 1 should be blocked
        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request1)

        # Client 2 should still be allowed
        await limiter.check_rate_limit(request2)  # Should not raise
        await limiter.check_rate_limit(request2)  # Should not raise

    async def test_respects_x_forwarded_for_header(self, monkeypatch):
        """Test that X-Forwarded-For header is used when present."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)

        request = self.create_mock_request("127.0.0.1")
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}

        # trusted_hops=1 → chain[-1] = "192.168.1.1"
        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        # 3rd request should be blocked
        with pytest.raises(HTTPException):
            await limiter.check_rate_limit(request)

        # Request with different forwarded chain ending should have separate limit
        request_other = self.create_mock_request("127.0.0.1")
        request_other.headers = {"X-Forwarded-For": "10.0.0.1"}
        await limiter.check_rate_limit(request_other)  # Should not raise

    async def test_old_requests_are_cleaned_up(self, monkeypatch):
        """Test that old requests are cleaned up and don't count against limits."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)
        request = self.create_mock_request()
        request.headers = {"X-Forwarded-For": "127.0.0.1"}

        # Use up the minute limit
        await limiter.check_rate_limit(request)
        await limiter.check_rate_limit(request)

        # Manually advance time in the internal storage
        client_id = "ip:127.0.0.1"
        old_time = time.time() - 61  # 61 seconds ago
        limiter.minute_requests[client_id] = [old_time, old_time]

        # Should now allow new requests since old ones expired
        await limiter.check_rate_limit(request)  # Should not raise

    async def test_strict_rate_limiting_enforcement(self, monkeypatch):
        """Test that rate limiting is strictly enforced without edge cases."""
        monkeypatch.setenv("KENE_RATE_LIMIT_TRUSTED_HOPS", "1")
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=20)
        request = self.create_mock_request()
        request.headers = {"X-Forwarded-For": "10.0.0.1"}

        # Make exactly the limit of requests
        for _ in range(3):
            await limiter.check_rate_limit(request)

        # The next request should immediately fail
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429

        # Try one more request to ensure it's consistently blocked
        with pytest.raises(HTTPException) as exc_info2:
            await limiter.check_rate_limit(request)

        assert exc_info2.value.status_code == 429
