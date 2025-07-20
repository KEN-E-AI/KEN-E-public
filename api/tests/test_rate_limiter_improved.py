"""Improved tests for rate limiting functionality using property-based testing."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request, status
from hypothesis import given, strategies as st, assume

from src.kene_api.rate_limiter import RateLimiter


# Constants for expected values
HTTP_TOO_MANY_REQUESTS = status.HTTP_429_TOO_MANY_REQUESTS
RETRY_AFTER_MINUTE = "60"
RETRY_AFTER_HOUR = "3600"


class TestRateLimiterProperties:
    """Property-based tests for rate limiting functionality."""

    def create_mock_request(self, client_ip: str = "127.0.0.1") -> Request:
        """Create a mock request object with the given IP."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = client_ip
        request.headers = {}
        return request

    @given(
        requests_per_minute=st.integers(min_value=1, max_value=100),
        requests_to_make=st.integers(min_value=0, max_value=150)
    )
    def test_minute_rate_limit_property(self, requests_per_minute, requests_to_make):
        """Test that rate limiter blocks requests after the minute limit is reached."""
        limiter = RateLimiter(requests_per_minute=requests_per_minute, requests_per_hour=1000)
        request = self.create_mock_request()
        
        successful_requests = 0
        blocked = False
        
        for _ in range(requests_to_make):
            try:
                limiter.check_rate_limit(request)
                successful_requests += 1
            except HTTPException as e:
                blocked = True
                # Verify exception properties
                assert e.status_code == HTTP_TOO_MANY_REQUESTS
                assert e.headers["Retry-After"] == RETRY_AFTER_MINUTE
                break
        
        # Property: successful requests should never exceed the limit
        assert successful_requests <= requests_per_minute
        
        # Property: if we tried to make more requests than allowed, we should be blocked
        if requests_to_make > requests_per_minute:
            assert blocked
            assert successful_requests == requests_per_minute

    @given(
        requests_per_hour=st.integers(min_value=1, max_value=100),
        requests_to_make=st.integers(min_value=0, max_value=150)
    )
    def test_hour_rate_limit_property(self, requests_per_hour, requests_to_make):
        """Test that rate limiter blocks requests after the hour limit is reached."""
        limiter = RateLimiter(requests_per_minute=1000, requests_per_hour=requests_per_hour)
        request = self.create_mock_request()
        
        successful_requests = 0
        blocked = False
        
        for _ in range(requests_to_make):
            try:
                limiter.check_rate_limit(request)
                successful_requests += 1
            except HTTPException as e:
                blocked = True
                assert e.status_code == HTTP_TOO_MANY_REQUESTS
                assert e.headers["Retry-After"] == RETRY_AFTER_HOUR
                break
        
        # Property: successful requests should never exceed the limit
        assert successful_requests <= requests_per_hour
        
        # Property: if we tried to make more requests than allowed, we should be blocked
        if requests_to_make > requests_per_hour:
            assert blocked
            assert successful_requests == requests_per_hour

    @given(
        num_clients=st.integers(min_value=1, max_value=5),
        requests_per_client=st.integers(min_value=1, max_value=10),
        requests_per_minute=st.integers(min_value=1, max_value=20)
    )
    def test_independent_client_limits(self, num_clients, requests_per_client, requests_per_minute):
        """Test that different clients have independent rate limits."""
        limiter = RateLimiter(requests_per_minute=requests_per_minute, requests_per_hour=1000)
        
        # Create different clients
        clients = [self.create_mock_request(f"192.168.1.{i}") for i in range(num_clients)]
        
        # Track successful requests per client
        successful_per_client = {}
        
        for i, client_request in enumerate(clients):
            successful = 0
            for _ in range(requests_per_client):
                try:
                    limiter.check_rate_limit(client_request)
                    successful += 1
                except HTTPException:
                    break
            successful_per_client[i] = successful
        
        # Property: each client should be limited independently
        for client_id, successful in successful_per_client.items():
            assert successful <= requests_per_minute
            if requests_per_client > requests_per_minute:
                assert successful == requests_per_minute

    @given(
        forwarded_ips=st.lists(
            st.text(alphabet="0123456789.", min_size=7, max_size=15),
            min_size=1,
            max_size=3
        )
    )
    def test_x_forwarded_for_handling(self, forwarded_ips):
        """Test that X-Forwarded-For header is properly handled."""
        assume(all("." in ip for ip in forwarded_ips))  # Ensure IPs have dots
        
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=100)
        
        # Create request with X-Forwarded-For header
        request = self.create_mock_request("127.0.0.1")
        request.headers = {"X-Forwarded-For": ", ".join(forwarded_ips)}
        
        # Make two requests (the limit)
        limiter.check_rate_limit(request)
        limiter.check_rate_limit(request)
        
        # Third request should fail
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(request)
        
        assert exc_info.value.status_code == HTTP_TOO_MANY_REQUESTS
        
        # Different forwarded IP should have its own limit
        request.headers = {"X-Forwarded-For": "10.0.0.1"}
        limiter.check_rate_limit(request)  # Should not raise


class TestRateLimiterEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def create_mock_request(self, client_ip: str = "127.0.0.1") -> Request:
        """Create a mock request object with the given IP."""
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = client_ip
        request.headers = {}
        return request

    @pytest.mark.parametrize("requests_per_minute,requests_per_hour", [
        (1, 1),  # Minimum limits
        (1, 100),  # Minute limit more restrictive
        (100, 1),  # Hour limit more restrictive
        (0, 100),  # Zero minute limit (should block all)
        (100, 0),  # Zero hour limit (should block all)
    ])
    def test_boundary_limits(self, requests_per_minute, requests_per_hour):
        """Test rate limiter with boundary limit values."""
        limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour
        )
        request = self.create_mock_request()
        
        if requests_per_minute == 0 or requests_per_hour == 0:
            # Should block immediately
            with pytest.raises(HTTPException) as exc_info:
                limiter.check_rate_limit(request)
            assert exc_info.value.status_code == HTTP_TOO_MANY_REQUESTS
        else:
            # Should allow at least one request
            limiter.check_rate_limit(request)
            
            # Check which limit is more restrictive
            min_limit = min(requests_per_minute, requests_per_hour)
            
            # Try to exceed the limit
            for _ in range(min_limit - 1):
                limiter.check_rate_limit(request)
            
            # Next request should fail
            with pytest.raises(HTTPException) as exc_info:
                limiter.check_rate_limit(request)
            assert exc_info.value.status_code == HTTP_TOO_MANY_REQUESTS

    def test_request_without_client(self):
        """Test handling of requests without client information."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=100)
        
        request = MagicMock(spec=Request)
        request.client = None
        request.headers = {}
        
        # Should track as "unknown" but still work
        limiter.check_rate_limit(request)
        limiter.check_rate_limit(request)
        
        # Third request should fail
        with pytest.raises(HTTPException) as exc_info:
            limiter.check_rate_limit(request)
        
        assert exc_info.value.status_code == HTTP_TOO_MANY_REQUESTS

    def test_malformed_x_forwarded_for(self):
        """Test handling of malformed X-Forwarded-For headers."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=100)
        
        test_cases = [
            "",  # Empty
            "   ",  # Whitespace only
            "not-an-ip",  # Invalid format
            "192.168.1.1,,,",  # Multiple commas
            "  192.168.1.1  ",  # Whitespace around IP
        ]
        
        for forwarded_value in test_cases:
            request = self.create_mock_request()
            request.headers = {"X-Forwarded-For": forwarded_value}
            
            # Should still work without crashing
            limiter.check_rate_limit(request)

    def test_concurrent_request_timing(self):
        """Test that rate limiting works correctly with rapid concurrent requests."""
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=100)
        request = self.create_mock_request()
        
        # Make requests as fast as possible
        start_time = time.time()
        successful = 0
        
        while time.time() - start_time < 0.1:  # Run for 100ms
            try:
                limiter.check_rate_limit(request)
                successful += 1
            except HTTPException:
                break
        
        # Should have allowed exactly the limit
        assert successful == 3