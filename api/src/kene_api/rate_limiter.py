"""Rate limiting utilities for API endpoints."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from .auth.models import UserContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KeyStrategy type alias
# ---------------------------------------------------------------------------

# A callable that maps (request, optional user context) → a rate-limit bucket key.
# The returned string is used verbatim as the key in the limiter's sliding-window
# dictionaries, so it must be stable and deterministic for a given (request, ctx) pair.
KeyStrategy = Callable[["Request", "UserContext | None"], str]


# ---------------------------------------------------------------------------
# Internal helper: trusted-hops-aware X-Forwarded-For parsing
# ---------------------------------------------------------------------------

_SENTINEL_KEY = "ip:_no_xff_chain_"


def _validated_ip_key(request: Request) -> str:
    """Return a rate-limit bucket key derived from X-Forwarded-For with trusted-hops validation.

    Reads KENE_RATE_LIMIT_TRUSTED_HOPS (default 1) to determine how many
    trailing entries in the X-Forwarded-For chain are controlled by trusted
    proxies.  Returns chain[-trusted_hops] when the chain is long enough.

    On Cloud Run, request.client.host is the load-balancer IP — NOT the client.
    We deliberately do NOT fall back to it; instead we return a sentinel key and
    emit a WARNING so chain-configuration drift is visible to operators.
    """
    try:
        trusted_hops = int(os.environ.get("KENE_RATE_LIMIT_TRUSTED_HOPS", "1"))
    except ValueError:
        logger.warning(
            "Rate limiter: KENE_RATE_LIMIT_TRUSTED_HOPS is not an integer "
            "(value=%r); coercing to 1.",
            os.environ.get("KENE_RATE_LIMIT_TRUSTED_HOPS"),
        )
        trusted_hops = 1
    if trusted_hops < 1:
        # trusted_hops=0 would make `len(entries) < 0` unreachable and return
        # entries[-0] = entries[0] — the LEFTMOST, attacker-controllable XFF
        # entry. Coerce to 1 so the sentinel still guards.
        logger.warning(
            "Rate limiter: KENE_RATE_LIMIT_TRUSTED_HOPS=%d is below the safe "
            "minimum (1); coercing to 1 to preserve XFF-spoofing defence.",
            trusted_hops,
        )
        trusted_hops = 1

    xff_header = request.headers.get("X-Forwarded-For", "") or ""
    entries = [e.strip() for e in xff_header.split(",") if e.strip()]

    if len(entries) < trusted_hops:
        logger.warning(
            "Rate limiter: X-Forwarded-For chain is shorter than trusted_hops "
            "(%d entries, need %d). Returning sentinel key. "
            "Check proxy configuration at path %s.",
            len(entries),
            trusted_hops,
            getattr(request.url, "path", "<unknown>"),
        )
        return _SENTINEL_KEY

    return f"ip:{entries[-trusted_hops]}"


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------


def ip_only_key_strategy(request: Request, ctx: UserContext | None) -> str:
    """Rate-limit bucket key derived from the trusted source IP.

    Ignores ctx entirely — suitable for unauthenticated endpoints or as the
    default before UserContext is wired in (AH-71).
    """
    return _validated_ip_key(request)


def authenticated_key_strategy(request: Request, ctx: UserContext | None) -> str:
    """Rate-limit bucket key derived from the authenticated user's UID.

    When ctx is None (request arrived before auth resolution), falls back to
    the validated IP and emits a WARNING — a user-keyed limiter receiving
    ctx=None is a code bug (limiter applied before context resolution).

    The UID is hashed via sha256[:16] to:
    - prevent key injection from OIDC sub claims containing ':'
    - bound key length regardless of UID size
    - avoid leaking raw UIDs into the limiter's in-memory dicts (defense-in-depth)
    """
    if ctx is None:
        logger.warning(
            "authenticated_key_strategy: ctx is None — falling back to IP key. "
            "Investigate: rate limiter is being applied before UserContext resolution "
            "at path %s.",
            getattr(request.url, "path", "<unknown>"),
        )
        return _validated_ip_key(request)

    uid_hash = hashlib.sha256(ctx.user_id.encode("utf-8")).hexdigest()[:16]
    return f"uid:{uid_hash}"


# ---------------------------------------------------------------------------
# LocalRateLimiter (renamed from RateLimiter)
# ---------------------------------------------------------------------------


class LocalRateLimiter:
    """In-memory sliding-window rate limiter with pluggable KeyStrategy.

    This is the local (non-Redis) backend.  AH-70 will introduce
    RedisRateLimiter with the same async interface so call sites can
    `await` either backend uniformly.
    """

    # Time windows in seconds
    MINUTE_WINDOW = 60
    HOUR_WINDOW = 3600

    def __init__(
        self,
        requests_per_minute: int = 10,
        requests_per_hour: int = 100,
        key_strategy: KeyStrategy = ip_only_key_strategy,
        limiter_name: str = "default",
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.key_strategy = key_strategy
        self.limiter_name = limiter_name
        self.minute_requests: dict[str, list[float]] = defaultdict(list)
        self.hour_requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old_requests(
        self, requests: list[float], window_seconds: int
    ) -> list[float]:
        """Remove requests older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        return [req_time for req_time in requests if req_time > cutoff_time]

    async def check_rate_limit(
        self, request: Request, ctx: UserContext | None = None
    ) -> None:
        """Check whether the request exceeds rate limits and raise 429 if so.

        The async signature is interface-only for this local backend (no awaits
        in the body).  It matches the upcoming RedisRateLimiter (AH-70) so call
        sites can `await` either backend without a conditional.

        Args:
            request: The incoming FastAPI request.
            ctx: Optional authenticated user context.  Passed to key_strategy;
                 defaults to None so existing call sites (which do not yet pass
                 ctx) continue to work until AH-71 wires UserContext through.

        Raises:
            HTTPException: 429 if a rate limit is exceeded.
        """
        client_id = self.key_strategy(request, ctx)
        current_time = time.time()

        minute_requests = self._clean_old_requests(
            self.minute_requests[client_id], self.MINUTE_WINDOW
        )
        hour_requests = self._clean_old_requests(
            self.hour_requests[client_id], self.HOUR_WINDOW
        )

        if len(minute_requests) >= self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                headers={"Retry-After": str(self.MINUTE_WINDOW)},
            )

        if len(hour_requests) >= self.requests_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour",
                headers={"Retry-After": str(self.HOUR_WINDOW)},
            )

        minute_requests.append(current_time)
        hour_requests.append(current_time)

        self.minute_requests[client_id] = minute_requests
        self.hour_requests[client_id] = hour_requests


# Backward-compat alias — survives one release cycle while AH-71 migrates call
# sites from `from ..rate_limiter import RateLimiter` to `LocalRateLimiter`.
RateLimiter = LocalRateLimiter

# ---------------------------------------------------------------------------
# Global limiter instances
# ---------------------------------------------------------------------------

# reCAPTCHA verification — restrictive to prevent abuse
recaptcha_rate_limiter = LocalRateLimiter(
    requests_per_minute=5,
    requests_per_hour=20,
    limiter_name="recaptcha",
)

# Progress-polling endpoints — permissive (polled frequently during long ops)
progress_rate_limiter = LocalRateLimiter(
    requests_per_minute=120,
    requests_per_hour=2000,
    limiter_name="progress",
)
