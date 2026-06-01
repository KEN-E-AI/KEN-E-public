"""Rate limiting utilities for API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal

from fastapi import HTTPException, Request, Response, status

try:
    import redis.exceptions as _redis_exceptions
except ImportError:  # pragma: no cover — redis is a required dep
    # If `redis` is missing the entire RedisRateLimiter + SwitchableRateLimiter
    # path silently degrades to "all exceptions treated as bugs" (the isinstance
    # check downstream is always False). Emit a CRITICAL log at import time so
    # operators see this BEFORE traffic hits a misconfigured deploy.
    _redis_exceptions = None  # type: ignore[assignment]
    logging.getLogger(__name__).critical(
        "rate_limiter: `redis` package import failed at module load — "
        "RedisRateLimiter + SwitchableRateLimiter Redis-error discrimination "
        "is disabled. Every Redis transport error will be re-raised as a 500 "
        "without circuit-breaker tripping. Add `redis` to your environment."
    )

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

    from .auth.audit_logger import AuditLogger
    from .auth.models import UserContext
    from .models.feature_flag_models import EvaluationContext

try:
    from shared.structured_logging import log_context as _log_context
except ImportError:  # pragma: no cover — shared package always present in prod
    # Fallback so the module remains importable in minimal test environments.
    def _log_context(**kwargs: Any) -> dict[str, Any]:
        return kwargs

from .metrics.rate_limiter_metrics import (
    ratelimit_429_total,
    ratelimit_circuit_breaker_state,
    ratelimit_local_fallback_total,
    ratelimit_redis_errors_total,
)

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
            "rate_limiter: xff_config_error",
            extra=_log_context(
                component="rate_limiter",
                action="xff_config_error",
                extra={
                    "reason": "KENE_RATE_LIMIT_TRUSTED_HOPS is not an integer",
                    "value": os.environ.get("KENE_RATE_LIMIT_TRUSTED_HOPS"),
                    "coerced_to": 1,
                },
            ),
        )
        trusted_hops = 1
    if trusted_hops < 1:
        # trusted_hops=0 would make `len(entries) < 0` unreachable and return
        # entries[-0] = entries[0] — the LEFTMOST, attacker-controllable XFF
        # entry. Coerce to 1 so the sentinel still guards.
        logger.warning(
            "rate_limiter: xff_config_error",
            extra=_log_context(
                component="rate_limiter",
                action="xff_config_error",
                extra={
                    "reason": "KENE_RATE_LIMIT_TRUSTED_HOPS below safe minimum",
                    "value": trusted_hops,
                    "coerced_to": 1,
                },
            ),
        )
        trusted_hops = 1

    xff_header = request.headers.get("X-Forwarded-For", "") or ""
    entries = [e.strip() for e in xff_header.split(",") if e.strip()]

    if len(entries) < trusted_hops:
        logger.warning(
            "rate_limiter: xff_short_chain",
            extra=_log_context(
                component="rate_limiter",
                action="xff_short_chain",
                extra={
                    "expected_hops": trusted_hops,
                    "actual_hops": len(entries),
                    "path": getattr(request.url, "path", "<unknown>"),
                    "xff_header": xff_header,
                },
            ),
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

    This is the local (non-Redis) backend.  AH-70 introduced
    RedisRateLimiter with the same async interface so call sites can
    `await` either backend uniformly.

    AH-71 adds optional ``audit_logger`` support so the memory backend
    emits ``RATE_LIMIT_EXCEEDED`` audit events symmetrically with
    ``RedisRateLimiter`` (PRD §6.4 Option A — limiter owns the audit call).
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
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.key_strategy = key_strategy
        self.limiter_name = limiter_name
        self.audit_logger = audit_logger
        self.minute_requests: dict[str, list[float]] = defaultdict(list)
        self.hour_requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old_requests(
        self, requests: list[float], window_seconds: int
    ) -> list[float]:
        """Remove requests older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        return [req_time for req_time in requests if req_time > cutoff_time]

    async def _emit_audit_log(
        self,
        request: Request,
        ctx: UserContext | None,
    ) -> None:
        """Emit a RATE_LIMIT_EXCEEDED audit event.

        Wraps the audit call in try/except so a Firestore outage never
        replaces the 429 — identical to the pattern in RedisRateLimiter.
        """
        if self.audit_logger is None:
            return
        ip_key = _validated_ip_key(request)
        ip_addr = ip_key.split(":", 1)[1] if ":" in ip_key else ip_key
        try:
            await self.audit_logger.log_rate_limit_exceeded(
                ip_address=ip_addr,
                endpoint=request.url.path,
                user_id=ctx.user_id if ctx is not None else None,
            )
        except Exception:
            # Audit-sink failure must NOT replace the 429 — log with context
            # and fall through so the rate-limit denial still reaches the client.
            logger.exception(
                "audit_logger failed during 429 emission "
                "(limiter=%s endpoint=%s)",
                self.limiter_name,
                request.url.path,
            )

    async def check_rate_limit(
        self, request: Request, ctx: UserContext | None = None
    ) -> None:
        """Check whether the request exceeds rate limits and raise 429 if so.

        The async signature matches RedisRateLimiter / SwitchableRateLimiter
        so call sites can ``await`` either backend without a conditional.

        Args:
            request: The incoming FastAPI request.
            ctx: Optional authenticated user context.  Passed to key_strategy
                 and included in the audit log's ``user_id`` field when set.

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
            await self._emit_audit_log(request, ctx)
            logger.warning(
                "rate_limiter: 429",
                extra=_log_context(
                    component="rate_limiter",
                    action="rate_limit_exceeded",
                    extra={
                        "limiter_name": self.limiter_name,
                        "client_key": client_id,
                        "window": "minute",
                        "limit": self.requests_per_minute,
                        "path": getattr(request.url, "path", "<unknown>"),
                    },
                ),
            )
            ratelimit_429_total.labels(limiter_name=self.limiter_name).inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                headers={"Retry-After": str(self.MINUTE_WINDOW)},
            )

        if len(hour_requests) >= self.requests_per_hour:
            await self._emit_audit_log(request, ctx)
            logger.warning(
                "rate_limiter: 429",
                extra=_log_context(
                    component="rate_limiter",
                    action="rate_limit_exceeded",
                    extra={
                        "limiter_name": self.limiter_name,
                        "client_key": client_id,
                        "window": "hour",
                        "limit": self.requests_per_hour,
                        "path": getattr(request.url, "path", "<unknown>"),
                    },
                ),
            )
            ratelimit_429_total.labels(limiter_name=self.limiter_name).inc()
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
# RedisRateLimiter — async, ZSET-backed, 2-key atomic Lua sliding window
# ---------------------------------------------------------------------------

# Sentinel cap: requests that fall into the _no_xff_chain_ sentinel bucket are
# capped here across ALL sentinel hits regardless of which per-limiter threshold
# applies.  5/min is deliberately aggressive — prevents an attacker from
# weaponising the sentinel bucket as a DoS lever against legitimate users who
# momentarily land in it (see PRD §4.3 / AC-19).
_SENTINEL_CAP_PER_MINUTE = 5
_SENTINEL_REDIS_KEY = "kene:ratelimit:_sentinel_"

# Atomic Lua script — operates on KEYS[1]=minute_key, KEYS[2]=hour_key.
# Strict order per §4.6:
#   1. ZREMRANGEBYSCORE (trim stale)
#   2. ZRANGEBYSCORE WITHSCORES LIMIT 0 1  (READ oldest_score BEFORE add)
#   3. ZCARD (count existing)
#   4. If count >= limit: return denied
#   5. ZADD (add unique member)
#   6. EXPIRE (bounded lifetime — LAST to guard against orphaned keys)
# Returns a flat list: [min_allowed, min_count, min_oldest, hr_allowed, hr_count, hr_oldest]
_LUA_SLIDING_WINDOW = """
local function check_window(key, limit, now, window, member)
    redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
    local oldest_entries = redis.call('ZRANGEBYSCORE', key, 0, '+inf', 'WITHSCORES', 'LIMIT', 0, 1)
    local oldest_score = oldest_entries[2] or now
    local count = redis.call('ZCARD', key)
    if count >= limit then
        return {0, count, oldest_score}
    end
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window + 60)
    return {1, count + 1, oldest_score}
end

local min_limit = tonumber(ARGV[1])
local hr_limit  = tonumber(ARGV[2])
local now       = tonumber(ARGV[3])
local member    = ARGV[4]

local min_result = check_window(KEYS[1], min_limit, now, 60,   member)
local hr_result  = check_window(KEYS[2], hr_limit,  now, 3600, member)

return {min_result[1], min_result[2], min_result[3],
        hr_result[1],  hr_result[2],  hr_result[3]}
"""

# Sentinel cap Lua: same single-window check for the shared sentinel bucket.
_LUA_SENTINEL_CAP = """
local key    = KEYS[1]
local limit  = tonumber(ARGV[1])
local now    = tonumber(ARGV[2])
local member = ARGV[3]

redis.call('ZREMRANGEBYSCORE', key, 0, now - 60)
local count = redis.call('ZCARD', key)
if count >= limit then
    redis.call('EXPIRE', key, 120)
    return 0
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, 120)
return 1
"""


class RedisRateLimiter:
    """Async Redis-backed sliding-window rate limiter (ZSET, 2-key atomic Lua).

    Uses ``redis.asyncio.Redis`` — NOT the sync ``redis.Redis`` from
    ``redis_client.py``.  Calling a sync Redis client from an async FastAPI
    dependency chain would block the event loop.

    The 2-key Lua script is atomic across both the per-minute and per-hour
    windows in a single Redis round-trip, satisfying AC-3 and AC-4.

    ``fallback_on_redis_error`` is intentionally defined here for AH-B2 parity
    but the circuit-breaker / SwitchableRateLimiter logic is NOT implemented in
    AH-B1 — that ships in AH-79.  Passing a non-False value raises
    ``NotImplementedError`` so callers are not silently no-op'd.
    """

    MINUTE_WINDOW = 60
    HOUR_WINDOW = 3600

    def __init__(
        self,
        requests_per_minute: int,
        requests_per_hour: int,
        redis_client: AsyncRedis,
        key_strategy: KeyStrategy,
        limiter_name: str,
        key_prefix: str = "kene:ratelimit",
        audit_logger: AuditLogger | None = None,
        emit_remaining_on_success: bool = True,
        fallback_on_redis_error: bool | LocalRateLimiter = False,
    ) -> None:
        if fallback_on_redis_error is not False:
            # This parameter is now vestigial — fallback logic is handled by
            # SwitchableRateLimiter (AH-79).  Accept any value with an INFO log
            # so existing callers are not broken.  Deletion is deferred to a
            # follow-up to keep this PR small.
            logger.info(
                "RedisRateLimiter: fallback_on_redis_error is no longer used "
                "(AH-79 moved fallback logic to SwitchableRateLimiter). "
                "Remove this kwarg from the call site."
            )
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.redis_client = redis_client
        self.key_strategy = key_strategy
        self.limiter_name = limiter_name
        self.key_prefix = key_prefix
        self.audit_logger = audit_logger
        self.emit_remaining_on_success = emit_remaining_on_success

    def _build_key(self, window: str, client_key: str) -> str:
        """Build the Redis ZSET key for a given window and client key."""
        return f"{self.key_prefix}:{self.limiter_name}:{window}:{client_key}"

    async def _check_sentinel_cap(self, now: float) -> bool:
        """Return True if the sentinel cap allows the request, False if it's blocked."""
        member = f"{now}:{uuid.uuid4().hex[:16]}"
        result: int = await self.redis_client.eval(
            _LUA_SENTINEL_CAP,
            1,
            _SENTINEL_REDIS_KEY,
            str(_SENTINEL_CAP_PER_MINUTE),
            str(now),
            member,
        )
        return bool(result)

    async def check_rate_limit(
        self,
        request: Request,
        ctx: UserContext | None = None,
        response: Response | None = None,
    ) -> None:
        """Check whether the request exceeds rate limits and raise 429 if so.

        Sets ``X-RateLimit-*`` headers on the supplied ``response`` object when
        provided (200 OK path).  Headers are also set on the ``HTTPException``
        headers dict on 429 responses.

        Args:
            request: The incoming FastAPI request.
            ctx: Optional authenticated user context passed to key_strategy.
            response: Optional FastAPI Response object for header injection on
                successful requests.  If not supplied, headers are silently
                omitted on the 200 path (Retry-After is always set on 429).

        Raises:
            HTTPException: 429 if a rate limit is exceeded.
        """
        client_key = self.key_strategy(request, ctx)
        now = time.time()

        # Sentinel cap — checked before the per-limiter window (§4.3 / AC-19).
        if client_key == _SENTINEL_KEY:
            allowed = await self._check_sentinel_cap(now)
            if not allowed:
                # Forensic: the sentinel client_key is the literal
                # "ip:_no_xff_chain_". Splitting yields the bare suffix which is
                # not an IP address; record an explicit sentinel marker so SIEM
                # searches for an IP don't match this row.
                if self.audit_logger is not None:
                    try:
                        await self.audit_logger.log_rate_limit_exceeded(
                            ip_address="sentinel:no_xff_chain",
                            endpoint=request.url.path,
                            user_id=ctx.user_id if ctx is not None else None,
                        )
                    except Exception:
                        # Audit-sink failure must NOT replace the 429. Log with
                        # context for the on-call (the traceback is auto-attached
                        # by .exception()) and intentionally fall through to the
                        # raise below so the rate-limit denial still surfaces to
                        # the client. Don't propagate — that's B2's whole point.
                        logger.exception(
                            "audit_logger failed during 429 emission "
                            "(limiter=%s window=sentinel endpoint=%s)",
                            self.limiter_name,
                            request.url.path,
                        )
                # Same X-RateLimit-* header shape as the per-window 429 paths
                # so CDN/observability sees a consistent set across all 429s.
                logger.warning(
                    "rate_limiter: 429",
                    extra=_log_context(
                        component="rate_limiter",
                        action="rate_limit_exceeded",
                        extra={
                            "limiter_name": self.limiter_name,
                            "client_key": client_key,
                            "window": "sentinel",
                            "limit": _SENTINEL_CAP_PER_MINUTE,
                            "path": getattr(request.url, "path", "<unknown>"),
                        },
                    ),
                )
                ratelimit_429_total.labels(limiter_name=self.limiter_name).inc()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded: sentinel cap (5 requests per minute)",
                    headers={
                        "X-RateLimit-Limit": str(_SENTINEL_CAP_PER_MINUTE),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(self.MINUTE_WINDOW),
                    },
                )

        minute_key = self._build_key("minute", client_key)
        hour_key = self._build_key("hour", client_key)
        member = f"{now}:{uuid.uuid4().hex[:16]}"

        results: list[Any] = await self.redis_client.eval(
            _LUA_SLIDING_WINDOW,
            2,
            minute_key,
            hour_key,
            str(self.requests_per_minute),
            str(self.requests_per_hour),
            str(now),
            member,
        )

        # Unpack Lua return: [min_allowed, min_count, min_oldest,
        #                      hr_allowed,  hr_count,  hr_oldest]
        min_allowed = bool(int(results[0]))
        min_count = int(results[1])
        min_oldest = float(results[2])
        hr_allowed = bool(int(results[3]))
        hr_count = int(results[4])
        hr_oldest = float(results[5])

        if not min_allowed:
            retry_after = max(1, math.ceil(min_oldest + self.MINUTE_WINDOW - now))
            reset_at = math.ceil(min_oldest + self.MINUTE_WINDOW)
            remaining = 0
            exc_headers: dict[str, str] = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_at),
            }
            if self.audit_logger is not None:
                ip_key = _validated_ip_key(request)
                ip_addr = ip_key.split(":", 1)[1] if ":" in ip_key else ip_key
                try:
                    await self.audit_logger.log_rate_limit_exceeded(
                        ip_address=ip_addr,
                        endpoint=request.url.path,
                        user_id=ctx.user_id if ctx is not None else None,
                    )
                except Exception:
                    # Audit failure must NOT replace the 429 — log with context
                    # and fall through. .exception() auto-attaches the traceback.
                    logger.exception(
                        "audit_logger failed during 429 emission "
                        "(limiter=%s window=minute endpoint=%s)",
                        self.limiter_name,
                        request.url.path,
                    )
            logger.warning(
                "rate_limiter: 429",
                extra=_log_context(
                    component="rate_limiter",
                    action="rate_limit_exceeded",
                    extra={
                        "limiter_name": self.limiter_name,
                        "client_key": client_key,
                        "window": "minute",
                        "limit": self.requests_per_minute,
                        "path": getattr(request.url, "path", "<unknown>"),
                    },
                ),
            )
            ratelimit_429_total.labels(limiter_name=self.limiter_name).inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                headers=exc_headers,
            )

        if not hr_allowed:
            retry_after = max(1, math.ceil(hr_oldest + self.HOUR_WINDOW - now))
            reset_at = math.ceil(hr_oldest + self.HOUR_WINDOW)
            remaining = 0
            exc_headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(self.requests_per_hour),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_at),
            }
            if self.audit_logger is not None:
                ip_key = _validated_ip_key(request)
                ip_addr = ip_key.split(":", 1)[1] if ":" in ip_key else ip_key
                try:
                    await self.audit_logger.log_rate_limit_exceeded(
                        ip_address=ip_addr,
                        endpoint=request.url.path,
                        user_id=ctx.user_id if ctx is not None else None,
                    )
                except Exception:
                    # Audit failure must NOT replace the 429 — log with context
                    # and fall through. .exception() auto-attaches the traceback.
                    logger.exception(
                        "audit_logger failed during 429 emission "
                        "(limiter=%s window=hour endpoint=%s)",
                        self.limiter_name,
                        request.url.path,
                    )
            logger.warning(
                "rate_limiter: 429",
                extra=_log_context(
                    component="rate_limiter",
                    action="rate_limit_exceeded",
                    extra={
                        "limiter_name": self.limiter_name,
                        "client_key": client_key,
                        "window": "hour",
                        "limit": self.requests_per_hour,
                        "path": getattr(request.url, "path", "<unknown>"),
                    },
                ),
            )
            ratelimit_429_total.labels(limiter_name=self.limiter_name).inc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_hour} requests per hour",
                headers=exc_headers,
            )

        # Request allowed — compute headers for the most-restrictive window.
        # Per-minute is almost always the binding window; per-hour can bind for
        # burst-then-quiet traffic patterns.
        min_remaining = self.requests_per_minute - min_count
        hr_remaining = self.requests_per_hour - hr_count

        if min_remaining <= hr_remaining:
            # Minute window is more restrictive
            binding_limit = self.requests_per_minute
            binding_remaining = min_remaining
            binding_reset = math.ceil(min_oldest + self.MINUTE_WINDOW)
        else:
            # Hour window is more restrictive
            binding_limit = self.requests_per_hour
            binding_remaining = hr_remaining
            binding_reset = math.ceil(hr_oldest + self.HOUR_WINDOW)

        if response is not None:
            response.headers["X-RateLimit-Limit"] = str(binding_limit)
            response.headers["X-RateLimit-Reset"] = str(binding_reset)
            if self.emit_remaining_on_success:
                response.headers["X-RateLimit-Remaining"] = str(binding_remaining)


# ---------------------------------------------------------------------------
# _CircuitBreaker — per-instance Redis-error circuit breaker (AH-79)
# ---------------------------------------------------------------------------

# Circuit breaker constants per AH-PRD-10 §7 AC-14.
_CB_K: int = 10  # consecutive Redis errors before circuit opens
_CB_COOLDOWN_SECONDS: float = 60.0  # seconds the circuit stays open before half-open


class _CircuitBreaker:
    """Process-local consecutive-error circuit breaker for Redis calls.

    State machine:
      CLOSED      → normal operation; Redis calls allowed.
      OPEN        → circuit tripped after K consecutive errors; Redis calls
                    skipped for COOLDOWN_SECONDS.
      HALF_OPEN   → cooldown elapsed; exactly ONE probe request is admitted.
                    Success → CLOSED. Failure → OPEN (cooldown resets).

    All state mutations are serialised behind a single ``asyncio.Lock`` so
    concurrent coroutines cannot race the half-open probe gate.  Uses
    ``time.monotonic()`` (immune to wall-clock jumps) for cooldown timing.

    ``limiter_name`` is used to label the ``ratelimit_circuit_breaker_state``
    Prometheus gauge, which tracks state transitions with encoding:
    0=closed, 1=open, 2=half_open.
    """

    def __init__(self, limiter_name: str = "rate_limiter") -> None:
        self.limiter_name: str = limiter_name
        self.consecutive_errors: int = 0
        self.opened_at: float | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._half_open_probe_in_flight: bool = False

    async def state(self) -> Literal["closed", "open", "half_open"]:
        """Return current circuit-breaker state.

        OPEN transitions to HALF_OPEN once the cooldown elapses; the caller
        must still call ``acquire_attempt()`` to obtain the probe token.
        """
        async with self._lock:
            return self._state_unlocked()

    def _state_unlocked(self) -> Literal["closed", "open", "half_open"]:
        """Return state without acquiring the lock (caller must hold it)."""
        if self.opened_at is None:
            return "closed"
        elapsed = time.monotonic() - self.opened_at
        if elapsed >= _CB_COOLDOWN_SECONDS:
            return "half_open"
        return "open"

    async def acquire_attempt(self) -> Literal["go", "skip"]:
        """Return whether the caller should attempt the Redis call.

        - ``"go"`` : circuit is closed, or is half-open AND the caller wins the
                     probe token.  Caller MUST call ``record_success()`` or
                     ``record_failure()`` when done.
        - ``"skip"``: circuit is open, or another half-open probe is already
                      in flight.  Caller should branch to the Local fallback.
        """
        async with self._lock:
            state = self._state_unlocked()
            if state == "closed":
                return "go"
            if state == "open":
                return "skip"
            # half_open — only one probe token at a time
            if self._half_open_probe_in_flight:
                return "skip"
            self._half_open_probe_in_flight = True
            # Transition from open → half_open; update gauge so dashboards reflect
            # the probe window without waiting for the next record_success/failure.
            ratelimit_circuit_breaker_state.labels(
                limiter_name=self.limiter_name
            ).set(2)
            return "go"

    async def record_success(self) -> None:
        """Record a successful Redis call — resets error counter and closes circuit."""
        async with self._lock:
            was_open = self.opened_at is not None
            self.consecutive_errors = 0
            self.opened_at = None
            self._half_open_probe_in_flight = False
            if was_open:
                # Transitioned from open/half_open → closed.
                ratelimit_circuit_breaker_state.labels(
                    limiter_name=self.limiter_name
                ).set(0)

    async def record_failure(self) -> None:
        """Record a failed Redis call.

        Increments the consecutive-error counter.  If the counter reaches K,
        opens the circuit.  If in half-open state, re-opens with a fresh cooldown.
        """
        async with self._lock:
            self._half_open_probe_in_flight = False
            self.consecutive_errors += 1
            if self.consecutive_errors >= _CB_K:
                self.opened_at = time.monotonic()
                logger.warning(
                    "rate_limiter: circuit_breaker_opened",
                    extra=_log_context(
                        component="rate_limiter",
                        action="circuit_breaker_opened",
                        extra={
                            "limiter_name": self.limiter_name,
                            "consecutive_errors": self.consecutive_errors,
                            "cooldown_seconds": _CB_COOLDOWN_SECONDS,
                        },
                    ),
                )
                ratelimit_circuit_breaker_state.labels(
                    limiter_name=self.limiter_name
                ).set(1)


# ---------------------------------------------------------------------------
# SwitchableRateLimiter — runtime-switchable wrapper with circuit breaker (AH-79)
# ---------------------------------------------------------------------------

# Synthetic EvaluationContext kwargs for the per-request feature-flag read.
# Same pattern as routers/chat.py:3211-3216 for kill-switch reads.
_SYSTEM_RATE_LIMITER_CTX_KWARGS: dict[str, str | None] = {
    "user_id": "_system_rate_limiter",
    "user_email": "system@ken-e.ai",
    "organization_id": None,
    "account_id": None,
}


def _get_system_eval_ctx() -> EvaluationContext:
    """Return the synthetic EvaluationContext for the rate-limiter feature-flag read.

    Lazy import avoids circular imports at module load time; the instance is
    constructed per-call (lightweight Pydantic model).
    """
    from .models.feature_flag_models import (
        EvaluationContext as _EvalCtx,
    )

    return _EvalCtx(**_SYSTEM_RATE_LIMITER_CTX_KWARGS)


async def is_feature_enabled(
    flag_key: str,
    ctx: EvaluationContext,
    default: bool = False,
) -> bool:
    """Module-level wrapper around ``feature_flag_service.is_feature_enabled``.

    Exposed at module level so tests can patch
    ``src.kene_api.rate_limiter.is_feature_enabled`` without depending on
    the lazy-import path inside ``check_rate_limit``.
    """
    from .services.feature_flag_service import (
        is_feature_enabled as _is_feature_enabled,
    )

    return await _is_feature_enabled(flag_key, ctx, default)


class SwitchableRateLimiter:
    """Runtime-switchable rate limiter that wraps a RedisRateLimiter and a fallback
    LocalRateLimiter.

    Per-request, it:
      (a) reads the ``rate_limit_backend_override`` feature flag via
          ``is_feature_enabled`` with a synthetic ``_system_rate_limiter``
          EvaluationContext.  Flag=True → delegate to Local (rollback path).
      (b) if flag is False, consults the process-local ``_CircuitBreaker``:
          - "skip" → fallback to Local (or fail-open for throughput limiters).
          - "go"  → delegate to Redis, recording success/failure.

    For security-critical limiters (``fallback_cap_divisor=10, fail_open=False``),
    the fallback ``LocalRateLimiter`` has its limits pre-divided by 10 so a Redis
    outage does not silently disable brute-force protection.

    For throughput limiters (``fail_open=True``), a Redis error logs ERROR and
    returns without rate-limiting (request is allowed through).
    """

    def __init__(
        self,
        redis_limiter: RedisRateLimiter,
        fallback_limiter: LocalRateLimiter,
        fallback_cap_divisor: int = 1,
        fail_open: bool = False,
        limiter_name: str = "default",
    ) -> None:
        self.redis_limiter = redis_limiter
        self.fallback_limiter = fallback_limiter
        self.fallback_cap_divisor = fallback_cap_divisor
        self.fail_open = fail_open
        self.limiter_name = limiter_name
        self._circuit_breaker = _CircuitBreaker(limiter_name=limiter_name)

    # ---------------------------------------------------------------------------
    # Backward-compat proxy properties (AH-71 PO fix)
    # ---------------------------------------------------------------------------
    # Tests that were written against LocalRateLimiter access these attributes
    # directly.  Rather than rewriting every test (Option B), we expose them as
    # delegation properties that forward to the appropriate underlying limiter:
    #   - minute_requests / hour_requests  → fallback_limiter  (mutable dicts that
    #     tests can .clear(); the fallback limiter is what's active when Redis is
    #     unavailable, which is the common CI/test scenario)
    #   - requests_per_minute / requests_per_hour → redis_limiter  (the configured
    #     "canonical" limits, not the emergency-capped fallback values)

    @property
    def minute_requests(self) -> dict:
        """Proxy to fallback_limiter.minute_requests for test backward-compat."""
        return self.fallback_limiter.minute_requests

    @property
    def hour_requests(self) -> dict:
        """Proxy to fallback_limiter.hour_requests for test backward-compat."""
        return self.fallback_limiter.hour_requests

    @property
    def requests_per_minute(self) -> int:
        """Proxy to redis_limiter.requests_per_minute for test backward-compat."""
        return self.redis_limiter.requests_per_minute

    @property
    def requests_per_hour(self) -> int:
        """Proxy to redis_limiter.requests_per_hour for test backward-compat."""
        return self.redis_limiter.requests_per_hour

    async def check_rate_limit(
        self,
        request: Request,
        ctx: UserContext | None = None,
        response: Response | None = None,
    ) -> None:
        """Check whether the request exceeds rate limits and raise 429 if so.

        Reads ``rate_limit_backend_override`` feature flag PER-REQUEST (not at
        startup) so the backend can be toggled at runtime without a redeploy.

        Args:
            request:  The incoming FastAPI request.
            ctx:      Optional authenticated user context; passed to key_strategy.
            response: Optional FastAPI Response for header injection on success.

        Raises:
            HTTPException: 429 if a rate limit is exceeded.
        """
        eval_ctx = _get_system_eval_ctx()

        use_local: bool = False
        try:
            flag_enabled = await is_feature_enabled(
                "rate_limit_backend_override", eval_ctx, default=False
            )
        except Exception:
            # Feature-flag read failure must NOT block the limiter path.
            # Fall through to Redis (the circuit breaker guards that path).
            # ERROR (not WARNING) — flag-service unavailability is a
            # control-plane incident operators need to see; exc_info=True
            # so the traceback lands in Cloud Logging for debugging.
            logger.error(
                "SwitchableRateLimiter: feature flag read failed for "
                "rate_limit_backend_override (limiter=%s). Falling back to "
                "Redis path. Flag-service backend (Firestore) may be down.",
                self.limiter_name,
                exc_info=True,
            )
            flag_enabled = False

        if flag_enabled:
            use_local = True
        else:
            attempt = await self._circuit_breaker.acquire_attempt()
            if attempt == "skip":
                use_local = True

        if use_local:
            if self.fail_open:
                logger.error(
                    "SwitchableRateLimiter: Redis unavailable for throughput limiter "
                    "'%s'; failing open (request allowed).",
                    self.limiter_name,
                )
                return
            ratelimit_local_fallback_total.labels(limiter_name=self.limiter_name).inc()
            await self.fallback_limiter.check_rate_limit(request, ctx)
            return

        # Redis path
        try:
            await self.redis_limiter.check_rate_limit(request, ctx, response)
            await self._circuit_breaker.record_success()
        except HTTPException:
            # A 429 from Redis is a legitimate rate-limit decision — NOT a Redis error.
            # Do not count it as a failure; re-raise so the client sees the 429.
            await self._circuit_breaker.record_success()
            raise
        except Exception as exc:
            if _redis_exceptions is not None and isinstance(
                exc, (_redis_exceptions.ConnectionError, _redis_exceptions.TimeoutError)
            ):
                await self._circuit_breaker.record_failure()
                cb_state = await self._circuit_breaker.state()
                logger.error(
                    "rate_limiter: redis_error",
                    extra=_log_context(
                        component="rate_limiter",
                        action="redis_error",
                        extra={
                            "limiter_name": self.limiter_name,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "fallback_active": True,
                            "circuit_breaker_state": cb_state,
                        },
                    ),
                    exc_info=True,
                )
                ratelimit_redis_errors_total.labels(
                    limiter_name=self.limiter_name,
                    error_type=type(exc).__name__,
                ).inc()
                if self.fail_open:
                    logger.error(
                        "SwitchableRateLimiter: throughput limiter '%s' failing open.",
                        self.limiter_name,
                    )
                    return
                ratelimit_local_fallback_total.labels(
                    limiter_name=self.limiter_name
                ).inc()
                await self.fallback_limiter.check_rate_limit(request, ctx)
            else:
                # Unexpected Redis exception — treat as failure, re-raise.
                await self._circuit_breaker.record_failure()
                raise


# ---------------------------------------------------------------------------
# Factory helper — reads KENE_RATE_LIMIT_BACKEND and returns the right backend
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_async_redis_client() -> AsyncRedis:
    """Construct an async Redis client from the standard KENE_* env vars.

    Reuses the same 4 connection vars as ``redis_client.py`` for consistency.
    Returns a ``redis.asyncio.Redis`` — NOT the sync ``redis.Redis``.

    ``@lru_cache(maxsize=1)`` ensures a single connection pool is reused across
    all callers within a process lifetime (singleton pattern per api/CLAUDE.md).
    """
    import redis.asyncio as aioredis

    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None
    db = int(os.environ.get("REDIS_DB", "0"))

    pool = aioredis.BlockingConnectionPool(
        host=host,
        port=port,
        password=password,
        db=db,
        max_connections=50,
        socket_timeout=2,
        socket_connect_timeout=1,
        health_check_interval=30,
        decode_responses=False,
    )
    return aioredis.Redis(connection_pool=pool)


def build_rate_limiter(
    name: str,
    requests_per_minute: int,
    requests_per_hour: int,
    key_strategy: KeyStrategy = ip_only_key_strategy,
    fallback_cap_divisor: int = 1,
    fail_open: bool = False,
    **kwargs: Any,
) -> LocalRateLimiter | SwitchableRateLimiter:
    """Return the correct concrete limiter based on ``KENE_RATE_LIMIT_BACKEND``.

    ``"redis"`` (default in prod/staging) → ``SwitchableRateLimiter`` wrapping
    both a ``RedisRateLimiter`` (primary) and an emergency-capped sibling
    ``LocalRateLimiter`` (fallback).

    ``"memory"`` (default in dev/test; no Redis dep) → ``LocalRateLimiter``
    directly.  No switching needed when memory IS the only backend.

    Args:
        name:                 Logical limiter name (used in Redis keys + logs).
        requests_per_minute:  Per-minute window limit for the primary backend.
        requests_per_hour:    Per-hour window limit for the primary backend.
        key_strategy:         Bucket-key derivation callable.
        fallback_cap_divisor: Emergency-cap divisor applied to the fallback
                              ``LocalRateLimiter``'s limits.  ``1`` = no cap
                              (default, safe for throughput limiters).  ``10`` =
                              divide limits by 10 (security-critical limiters per
                              AH-PRD-10 §7 AC-13).
        fail_open:            If ``True``, a Redis error or open circuit-breaker
                              causes the limiter to allow the request through
                              (fail-open).  ``False`` (default) falls back to the
                              emergency-capped ``LocalRateLimiter`` (fail-closed
                              via local fallback).
        **kwargs:             Forwarded to ``RedisRateLimiter`` constructor.  A
                              ``redis_client`` kwarg is required for the Redis
                              branch unless the env var selects ``"memory"``.
                              Inject ``fakeredis.aioredis.FakeRedis`` in tests.
    """
    backend = os.environ.get("KENE_RATE_LIMIT_BACKEND", "redis").lower()

    # Pop audit_logger BEFORE the backend branch — both the memory backend
    # AND the Redis branch's fallback LocalRateLimiter need it so AC-16's
    # "AuditLogger called from EVERY 429 site" holds during a Redis outage
    # or rate_limit_backend_override flag flip (closes the AH-71 audit-
    # symmetry gap that was scoped to AH-73).
    audit_logger_kwarg = kwargs.pop("audit_logger", None)

    if backend == "memory":
        return LocalRateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            key_strategy=key_strategy,
            limiter_name=name,
            audit_logger=audit_logger_kwarg,
        )

    # Redis backend (default) — wrap in SwitchableRateLimiter.
    redis_client = kwargs.pop("redis_client", None) or _build_async_redis_client()

    redis_limiter = RedisRateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        redis_client=redis_client,
        key_strategy=key_strategy,
        limiter_name=name,
        audit_logger=audit_logger_kwarg,
        **kwargs,
    )

    # Construct the emergency-capped sibling LocalRateLimiter.
    # When fallback_cap_divisor=1, limits are unchanged (no cap for throughput
    # limiters). When fallback_cap_divisor=10, limits are divided by 10 for
    # security-critical limiters (AC-13 — enforced at construction time, not
    # per-request, so the cap is visible in the limiter's repr for diagnostics).
    divisor = max(1, fallback_cap_divisor)
    fallback_rpm = max(1, requests_per_minute // divisor)
    fallback_rph = max(1, requests_per_hour // divisor)

    fallback_limiter = LocalRateLimiter(
        requests_per_minute=fallback_rpm,
        requests_per_hour=fallback_rph,
        key_strategy=key_strategy,
        limiter_name=f"{name}:fallback",
        audit_logger=audit_logger_kwarg,
    )

    return SwitchableRateLimiter(
        redis_limiter=redis_limiter,
        fallback_limiter=fallback_limiter,
        fallback_cap_divisor=divisor,
        fail_open=fail_open,
        limiter_name=name,
    )


# ---------------------------------------------------------------------------
# Global limiter instances (AH-71: migrated to build_rate_limiter)
# ---------------------------------------------------------------------------

# reCAPTCHA verification — IP-keyed, security-critical (pre-auth endpoint).
# fallback_cap_divisor=10: Redis outage reduces effective limit to 1 req/min/instance.
# emit_remaining_on_success=False: don't leak headroom to unauthenticated callers.
def _get_auth_audit_logger() -> AuditLogger | None:
    """Lazy-import the audit logger to avoid circular imports at module load."""
    try:
        from .auth.audit_logger import get_audit_logger as _get_audit_logger

        return _get_audit_logger()
    except Exception:
        return None


recaptcha_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="recaptcha",
    requests_per_minute=5,
    requests_per_hour=20,
    key_strategy=ip_only_key_strategy,
    fallback_cap_divisor=10,
    fail_open=False,
    audit_logger=_get_auth_audit_logger(),
    emit_remaining_on_success=False,
)

# Progress-polling endpoints — authenticated, throughput path.
# fail_open=True: Redis outage must not cascade to a service outage.
# emit_remaining_on_success=True: clients may use remaining count for backoff.
progress_rate_limiter: LocalRateLimiter | SwitchableRateLimiter = build_rate_limiter(
    name="progress",
    requests_per_minute=120,
    requests_per_hour=2000,
    key_strategy=authenticated_key_strategy,
    fallback_cap_divisor=1,
    fail_open=True,
    audit_logger=_get_auth_audit_logger(),
    emit_remaining_on_success=True,
)
