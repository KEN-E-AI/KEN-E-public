"""Rate limiting for authentication endpoints."""

from ..rate_limiter import RateLimiter

# Authentication rate limiters
# More restrictive for login/signup to prevent brute force attacks
auth_rate_limiter = RateLimiter(
    requests_per_minute=10,  # 10 login attempts per minute
    requests_per_hour=50,  # 50 login attempts per hour
)

# Token verification rate limiter
# Less restrictive since it's used for all authenticated requests
token_rate_limiter = RateLimiter(
    requests_per_minute=60,  # 60 requests per minute
    requests_per_hour=1000,  # 1000 requests per hour
)

# Password reset rate limiter
# Very restrictive to prevent abuse
password_reset_rate_limiter = RateLimiter(
    requests_per_minute=3,  # 3 reset requests per minute
    requests_per_hour=10,  # 10 reset requests per hour
)
