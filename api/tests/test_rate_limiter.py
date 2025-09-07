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

    def test_allows_requests_under_limit(self):
        """Test that requests under the limit are allowed."""
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=20)
        request = self.create_mock_request()

        # Should allow 5 requests
        for _ in range(5):
            limiter.check_rate_limit(request)  # Should not raise

    def test_blocks_requests_over_minute_limit(self):
        """Test that requests exceeding minute limit are blocked."""
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=20)
        request = self.create_mock_request()

        # Allow first 3 requests
        for _ in range(3):
            limiter.check_rate_limit(request)

        # 4th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "3 requests per minute" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "60"

    def test_blocks_requests_over_hour_limit(self):
        """Test that requests exceeding hour limit are blocked."""
        limiter = RateLimiter(requests_per_minute=100, requests_per_hour=5)
        request = self.create_mock_request()

        # Allow first 5 requests
        for _ in range(5):
            limiter.check_rate_limit(request)

        # 6th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "5 requests per hour" in exc_info.value.detail
        assert exc_info.value.headers["Retry-After"] == "3600"

    def test_different_clients_have_separate_limits(self):
        """Test that different clients have independent rate limits."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)

        request1 = self.create_mock_request("192.168.1.1")
        request2 = self.create_mock_request("192.168.1.2")

        # Client 1 uses up their limit
        limiter.check_rate_limit(request1)
        limiter.check_rate_limit(request1)

        # Client 1 should be blocked
        with pytest.raises(HTTPException):
            limiter.check_rate_limit(request1)

        # Client 2 should still be allowed
        limiter.check_rate_limit(request2)  # Should not raise
        limiter.check_rate_limit(request2)  # Should not raise

    def test_respects_x_forwarded_for_header(self):
        """Test that X-Forwarded-For header is used when present."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)

        request = self.create_mock_request("127.0.0.1")
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}

        # Should track by forwarded IP (10.0.0.1)
        limiter.check_rate_limit(request)
        limiter.check_rate_limit(request)

        # 3rd request should be blocked
        with pytest.raises(HTTPException):
            limiter.check_rate_limit(request)

        # Request without X-Forwarded-For should have separate limit
        request_no_forward = self.create_mock_request("127.0.0.1")
        limiter.check_rate_limit(request_no_forward)  # Should not raise

    def test_old_requests_are_cleaned_up(self):
        """Test that old requests are cleaned up and don't count against limits."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=20)
        request = self.create_mock_request()

        # Use up the minute limit
        limiter.check_rate_limit(request)
        limiter.check_rate_limit(request)

        # Manually advance time in the internal storage
        # This simulates old requests expiring
        client_id = "127.0.0.1"
        old_time = time.time() - 61  # 61 seconds ago
        limiter.minute_requests[client_id] = [old_time, old_time]

        # Should now allow new requests since old ones expired
        limiter.check_rate_limit(request)  # Should not raise

    def test_strict_rate_limiting_enforcement(self):
        """Test that rate limiting is strictly enforced without edge cases."""
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=20)
        request = self.create_mock_request()

        # Make exactly the limit of requests
        for _ in range(3):
            limiter.check_rate_limit(request)

        # The next request should immediately fail
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(request)

        assert exc_info.value.status_code == 429

        # Try one more request to ensure it's consistently blocked
        with pytest.raises(HTTPException) as exc_info2:
            limiter.check_rate_limit(request)

        assert exc_info2.value.status_code == 429
