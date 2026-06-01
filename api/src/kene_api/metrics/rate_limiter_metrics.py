"""Prometheus metrics for the rate-limiter subsystem (AH-79 / AH-73).

Exposes:
- ``ratelimit_backend_override_flips_total`` — every write to the
  ``rate_limit_backend_override`` feature flag (AH-79).  Cloud Monitoring
  alert policy in Terraform (AH-73) fires when this counter increments.
- ``ratelimit_429_total`` — every 429 response emitted by any rate-limiter
  instance (AH-73).
- ``ratelimit_redis_errors_total`` — every Redis ConnectionError / TimeoutError
  caught by SwitchableRateLimiter (AH-73).
- ``ratelimit_local_fallback_total`` — every time the LocalRateLimiter fallback
  is consulted: flag-driven override branch or Redis-error circuit-skip (AH-73).
- ``ratelimit_circuit_breaker_state`` (Gauge) — current circuit state per limiter:
  0=closed (normal), 1=open (tripped), 2=half_open (probe) (AH-73).

Follows the ``oauth_metrics.py`` pattern: uses ``_get_or_create_counter`` /
``_get_or_create_gauge`` to survive the ``pytest_configure`` REGISTRY clear and
avoid duplicate-registration errors across test-session import cycles.
"""

from .oauth_metrics import _get_or_create_counter, _get_or_create_gauge

ratelimit_backend_override_flips_total = _get_or_create_counter(
    "ratelimit_backend_override_flips_total",
    "Total writes to rate_limit_backend_override feature flag "
    "(create / update / delete). Labels carry the before/after default_enabled "
    "state so Cloud Monitoring alert policies can discriminate direction.",
    ["previous_enabled", "new_enabled"],
)

ratelimit_429_total = _get_or_create_counter(
    "ratelimit_429_total",
    "Total 429 responses emitted by any rate-limiter instance. "
    "Incremented at every HTTPException(429) raise site in LocalRateLimiter, "
    "RedisRateLimiter (minute/hour/sentinel windows), and SwitchableRateLimiter.",
    ["limiter_name"],
)

ratelimit_redis_errors_total = _get_or_create_counter(
    "ratelimit_redis_errors_total",
    "Total Redis ConnectionError / TimeoutError exceptions caught by "
    "SwitchableRateLimiter.check_rate_limit. Each increment triggers the "
    "circuit-breaker failure counter; K=10 consecutive errors opens the circuit.",
    ["limiter_name", "error_type"],
)

ratelimit_local_fallback_total = _get_or_create_counter(
    "ratelimit_local_fallback_total",
    "Total times the LocalRateLimiter fallback was consulted: either the "
    "rate_limit_backend_override feature flag is enabled (operator rollback) "
    "or the circuit breaker returned 'skip' (Redis unavailable).",
    ["limiter_name"],
)

ratelimit_circuit_breaker_state = _get_or_create_gauge(
    "ratelimit_circuit_breaker_state",
    "Current circuit-breaker state per limiter instance. "
    "Value encoding: 0=closed (normal operation), 1=open (tripped — Redis calls "
    "skipped for cooldown period), 2=half_open (probe request admitted).",
    ["limiter_name"],
)
