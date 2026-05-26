"""Rate limiting for authentication endpoints."""

import os

from ..rate_limiter import RateLimiter

# Authentication rate limiters
# More restrictive for login/signup to prevent brute force attacks
auth_rate_limiter = RateLimiter(
    requests_per_minute=10,  # 10 login attempts per minute
    requests_per_hour=50,  # 50 login attempts per hour
)

# Token verification rate limiter
# Used for all authenticated requests. The rate limiter is currently IP-keyed
# (see rate_limiter._get_client_id), so environments with many authenticated
# requests from a single source IP — e2e tests, multi-user NAT — need higher
# thresholds. Override via env vars; defaults preserve previous behaviour.
token_rate_limiter = RateLimiter(
    requests_per_minute=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_HOUR", "1000")),
)

# Password reset rate limiter
# Very restrictive to prevent abuse
password_reset_rate_limiter = RateLimiter(
    requests_per_minute=3,  # 3 reset requests per minute
    requests_per_hour=10,  # 10 reset requests per hour
)
