"""Rate limiting utilities for API endpoints."""

import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    # Time windows in seconds
    MINUTE_WINDOW = 60
    HOUR_WINDOW = 3600

    def __init__(self, requests_per_minute: int = 10, requests_per_hour: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_requests: Dict[str, list[float]] = defaultdict(list)
        self.hour_requests: Dict[str, list[float]] = defaultdict(list)

    def _clean_old_requests(self, requests: list[float], window_seconds: int) -> list[float]:
        """Remove requests older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        return [req_time for req_time in requests if req_time > cutoff_time]

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request (IP address)."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        return client_ip

    def check_rate_limit(self, request: Request) -> None:
        """
        Check if the request exceeds rate limits.
        
        This implementation ensures strict rate limiting by checking if adding
        the current request would exceed limits before actually adding it.
        
        Raises:
            HTTPException: If rate limit is exceeded
        """
        client_id = self._get_client_id(request)
        current_time = time.time()

        # Clean old requests for both windows
        minute_requests = self._clean_old_requests(
            self.minute_requests[client_id], self.MINUTE_WINDOW
        )
        hour_requests = self._clean_old_requests(
            self.hour_requests[client_id], self.HOUR_WINDOW
        )

        # Check if adding this request would exceed minute limit
        if len(minute_requests) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                headers={"Retry-After": str(self.MINUTE_WINDOW)},
            )

        # Check if adding this request would exceed hour limit
        if len(hour_requests) >= self.requests_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour",
                headers={"Retry-After": str(self.HOUR_WINDOW)},
            )

        # All checks passed, now add the current request
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        # Update the stored lists
        self.minute_requests[client_id] = minute_requests
        self.hour_requests[client_id] = hour_requests


# Create a global rate limiter for reCAPTCHA verification
# More restrictive than general API endpoints to prevent abuse
recaptcha_rate_limiter = RateLimiter(
    requests_per_minute=5,  # 5 verification attempts per minute
    requests_per_hour=20,   # 20 verification attempts per hour
)