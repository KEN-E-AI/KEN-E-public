"""Rate limiting for authentication endpoints.

AH-71: All limiter instances migrated to build_rate_limiter with per-limiter
KeyStrategy, fallback_cap_divisor, fail_open, and emit_remaining_on_success flags
per AH-PRD-10 §5 specification table.
"""

from __future__ import annotations

import os

from ..rate_limiter import (
    LocalRateLimiter,
    SwitchableRateLimiter,
    authenticated_key_strategy,
    build_rate_limiter,
    ip_only_key_strategy,
)


def _get_audit_logger_lazy() -> object | None:
    """Lazy-import audit logger to avoid circular imports at module load."""
    try:
        from .audit_logger import get_audit_logger as _get

        return _get()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Security-critical, IP-keyed limiters (pre-auth; brute-force defense)
# fallback_cap_divisor=10: Redis outage → effective limit ÷10 per instance.
# emit_remaining_on_success=False: don't leak bucket headroom to unauthenticated callers.
# ---------------------------------------------------------------------------

# Authentication endpoints (login + signup) — 10/min, 50/hour
auth_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="auth",
    requests_per_minute=10,
    requests_per_hour=50,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=False,
)

# Bad-token exception path (NEW — AH-71).  Dedicated 10/min ceiling so a single
# attacker submitting bad Firebase tokens hits this limiter's 10/min budget
# instead of the 60/min throughput budget of token_rate_limiter (AC-4 / Critical #1).
bad_token_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="bad_token",
    requests_per_minute=10,
    requests_per_hour=50,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=False,
)

# Password reset — very restrictive to prevent abuse
password_reset_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="password_reset",
    requests_per_minute=3,
    requests_per_hour=10,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=False,
)

# Early Release code validation — 5/min, 20/hr (mirrors recaptcha caps)
# fail_open=False: a Redis outage must not silently disable brute-force protection.
early_release_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="early_release",
    requests_per_minute=5,
    requests_per_hour=20,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=False,
)

# Signup-policy lookup — 20/min, 100/hr.  Dedicated bucket (kept off the
# recaptcha and early_release limiters) so a page-load GET cannot contend with
# the recaptcha verification or code-validation paths on the same signup flow.
# Caps are generous because this guards a read-only flag check the signup page
# fires on load, but it stays IP-keyed + fail-closed to resist polling abuse.
signup_policy_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="signup_policy",
    requests_per_minute=20,
    requests_per_hour=100,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=False,
)

# ---------------------------------------------------------------------------
# Authenticated throughput limiter — per-user-keyed, fail-open.
# Override thresholds via env vars to preserve backward compat (AC-6 / CH-54).
# emit_remaining_on_success=True: clients may use remaining count for backoff.
# ---------------------------------------------------------------------------

token_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="token",
    requests_per_minute=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.environ.get("KENE_TOKEN_RATE_LIMIT_PER_HOUR", "1000")),
    key_strategy=authenticated_key_strategy,
    fallback_cap_divisor=1,
    fail_open=True,
    audit_logger=_get_audit_logger_lazy(),
    emit_remaining_on_success=True,
)
