"""Rate limiting for authentication endpoints."""

import os

from ..rate_limiter import RateLimiter

# Authentication rate limiters
# More restrictive for login/signup to prevent brute force attacks
auth_rate_limiter = RateLimiter(
    requests_per_minute=10,  # 10 login attempts per minute
    requests_per_hour=50,  # 50 login attempts per hour
    limiter_name="auth",
)

# Token verification rate limiter
# Used for all authenticated requests.  Key strategy is IP-only for now;
# AH-PRD-10 (AH-71) will wire UserContext so authenticated requests use a
# per-user bucket, fixing NAT'd-user bucket sharing and cross-instance divergence.
# Override thresholds via env vars; defaults preserve previous behaviour.
token_rate_limiter = RateLimiter(
    requests_per_minute=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_HOUR", "1000")),
    limiter_name="token",
)

# Password reset rate limiter
# Very restrictive to prevent abuse
password_reset_rate_limiter = RateLimiter(
    requests_per_minute=3,  # 3 reset requests per minute
    requests_per_hour=10,  # 10 reset requests per hour
    limiter_name="password_reset",
)
