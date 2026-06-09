"""User context and authentication utilities."""

import hmac
import logging
import time
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud import firestore

from shared.structured_logging import log_context

from ..config import settings
from ..firestore import FirestoreService, get_firestore_service
from ..rate_limiter import LocalRateLimiter, SwitchableRateLimiter
from .audit_logger import AuditLogger, SecurityEventType, get_audit_logger
from .firebase_admin import initialize_firebase_admin, verify_id_token
from .models import UserContext
from .rate_limiting import bad_token_rate_limiter, token_rate_limiter
from .token_revocation import get_token_revocation_service

logger = logging.getLogger(__name__)

# Initialize Firebase Admin on module load
initialize_firebase_admin()

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)


async def _apply_rate_limiting(
    request: Request,
    rate_limiter: LocalRateLimiter | SwitchableRateLimiter,
    audit_logger: AuditLogger,
    client_ip: str | None,
    ctx: UserContext | None = None,
) -> None:
    """Apply rate limiting.

    The limiter itself logs the RATE_LIMIT_EXCEEDED audit event on 429
    (AH-71 / PRD §6.4 Option A).  This wrapper exists to localise the
    try/except around check_rate_limit for the two call sites in
    _get_user_context_with_limiter (missing-credentials at line ~304,
    post-verify at line ~355).

    Args:
        request:      The FastAPI request object.
        rate_limiter: The rate limiter to use.
        audit_logger: Audit logger instance (retained in signature for future
                      non-429 logging; not used for 429 events — limiter owns those).
        client_ip:    Client IP address (unused for 429 audit; limiter resolves IP
                      from X-Forwarded-For directly).
        ctx:          Optional UserContext for user-keyed limiters.  Pass None on
                      the missing-credentials path (token not yet verified).

    Raises:
        HTTPException: If rate limit is exceeded (re-raised from limiter).
    """
    await rate_limiter.check_rate_limit(request, ctx)


async def _verify_and_decode_token(
    credentials: HTTPAuthorizationCredentials,
    audit_logger: AuditLogger,
    client_ip: str | None,
    user_agent: str | None,
    request: Request,
) -> tuple[dict[str, Any], str, str]:
    """Verify and decode Firebase ID token.

    On token-verification failure the request is charged against
    ``bad_token_rate_limiter`` (10/min IP-keyed, AH-71 / AC-4 Critical #1).
    Using a dedicated limiter — rather than the 60/min throughput
    ``token_rate_limiter`` — ensures a brute-force attacker is blocked at
    10 bad tokens/min, not 60.  The limiter owns the 429 audit event.

    Args:
        credentials: HTTP Bearer credentials.
        audit_logger: Audit logger instance (for TOKEN_VERIFICATION_FAILURE events).
        client_ip:    Client IP address.
        user_agent:   User agent string.
        request:      FastAPI request object.

    Returns:
        Tuple of (decoded_token, user_id, email).

    Raises:
        HTTPException: 401 if token verification fails; 429 if bad-token
                       rate limit is exceeded.
    """
    try:
        decoded_token = verify_id_token(credentials.credentials)
        user_id = decoded_token["uid"]
        email = decoded_token.get("email", "")
        return decoded_token, user_id, email
    except Exception as e:
        # Rate-limit bad-token attempts via the dedicated IP-keyed limiter.
        # ctx=None: token verification failed, no identity established.
        # The limiter emits the RATE_LIMIT_EXCEEDED audit log on 429.
        try:
            await bad_token_rate_limiter.check_rate_limit(request, ctx=None)
        except HTTPException as rate_error:
            logger.error("Failed to verify token: %s", e)
            raise rate_error

        logger.error("Failed to verify token: %s", e)
        await audit_logger.log_event(
            event_type=SecurityEventType.TOKEN_VERIFICATION_FAILURE,
            ip_address=client_ip,
            user_agent=user_agent,
            details={"error": str(e)},
            severity="WARNING",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def _check_token_revocation(
    decoded_token: dict[str, Any],
    user_id: str,
    audit_logger: AuditLogger,
    client_ip: str | None,
    user_agent: str | None,
) -> None:
    """Check if token has been revoked.

    Args:
        decoded_token: Decoded JWT token
        user_id: User ID from token
        audit_logger: Audit logger instance
        client_ip: Client IP address
        user_agent: User agent string

    Raises:
        HTTPException: If token has been revoked
    """
    token_revocation = get_token_revocation_service()
    token_id = decoded_token.get("jti") or decoded_token.get("sub", "") + str(
        decoded_token.get("iat", "")
    )
    issued_at = decoded_token.get("iat")

    # Defense-in-depth: a real Firebase ID token always carries `sub` and `iat`,
    # so an empty token_id means the JWT is missing all three of jti / sub /
    # iat — a malformed or spoofed token. Reject up-front rather than relying
    # on downstream revocation-check guards; a JWT with no identity claims
    # should not authenticate at all.
    if not token_id:
        await audit_logger.log_event(
            event_type=SecurityEventType.TOKEN_VERIFICATION_FAILURE,
            user_id=user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "Token missing required identity claims (jti/sub/iat)"},
            severity="WARNING",
        )
        raise HTTPException(
            status_code=401,
            detail="Token missing required identity claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if await token_revocation.is_token_revoked(token_id, user_id, issued_at):
        await audit_logger.log_event(
            event_type=SecurityEventType.TOKEN_VERIFICATION_FAILURE,
            user_id=user_id,
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "Token has been revoked"},
            severity="WARNING",
        )
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _get_or_create_user_document(
    firestore_db: firestore.Client,
    user_id: str,
    email: str,
    audit_logger: AuditLogger,
    client_ip: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    """Get or create user document in Firestore.

    Args:
        firestore_db: Firestore client instance
        user_id: User ID
        email: User email
        audit_logger: Audit logger instance
        client_ip: Client IP address
        user_agent: User agent string

    Returns:
        User data dictionary
    """
    user_doc = firestore_db.collection("users").document(user_id).get()

    if not user_doc.exists:
        logger.info(f"Creating user document for {user_id}")
        user_data = {
            "uid": user_id,
            "email": email,
            "profile": {
                "email": email,
            },
            "permissions": {
                "organizations": {},
                "account_permissions": {},
            },
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        firestore_db.collection("users").document(user_id).set(user_data)

        await audit_logger.log_event(
            event_type=SecurityEventType.USER_CREATED,
            user_id=user_id,
            email=email,
            ip_address=client_ip,
            user_agent=user_agent,
            severity="INFO",
        )
        return user_data
    else:
        return user_doc.to_dict()


def _build_user_context_from_data(
    user_id: str,
    email: str,
    user_data: dict[str, Any],
) -> UserContext:
    """Build UserContext from user data.

    Args:
        user_id: User ID
        email: User email
        user_data: User data from Firestore

    Returns:
        UserContext object
    """
    permissions = user_data.get("permissions", {})
    organization_permissions = permissions.get("organizations", {})
    account_permissions = permissions.get("account_permissions", {})
    roles = user_data.get("roles", [])

    return UserContext(
        user_id=user_id,
        email=email,
        organization_permissions=organization_permissions,
        account_permissions=account_permissions,
        roles=roles,
    )


async def _get_user_context_with_limiter(
    request: Request,
    credentials: HTTPAuthorizationCredentials,
    firestore_service: FirestoreService,
    rate_limiter: LocalRateLimiter | SwitchableRateLimiter | None = None,
) -> UserContext:
    """Internal function to get user context with custom rate limiter.

    This is the actual implementation that accepts a custom rate limiter.
    """
    t_start = time.time()

    # E2E test bypass — only active when API_TEST_BYPASS_TOKEN is non-empty.
    # Exact match → non-member; "{token}:{account_id}" → member of that account.
    # hmac.compare_digest is used for both comparisons to avoid byte-level
    # timing side-channels on the token value itself. The length check on the
    # prefix branch is *not* constant-time, so an attacker can distinguish
    # "right-length-as-prefix" from "different-length" by timing — acceptable
    # for a non-secret CI-only token, but do not extend this pattern to any
    # production secret.
    # This path must never be reachable in production or staging — startup
    # guard in main.py (_assert_bypass_token_safe) refuses to boot unless
    # ENVIRONMENT is explicitly in {development, test, ci}.
    # NOTE: this short-circuits past rate-limiting (_apply_rate_limiting),
    # token revocation (_check_token_revocation), and audit logging — so
    # E2E tests cannot catch regressions in those pipelines. Validate
    # changes to those code paths with dedicated integration tests, not
    # by relying on E2E coverage.
    # NOTE: get_optional_user_context relies on its own `not credentials` guard
    # running before this function; the bypass here only fires when credentials
    # are present, so optional-auth callers without a token are unaffected.
    bypass_token = settings.api_test_bypass_token
    if bypass_token and credentials:
        bearer = credentials.credentials
        if hmac.compare_digest(bearer, bypass_token):
            return UserContext(
                user_id="test-bypass-no-member",
                email="no-member@test.internal",
                organization_permissions={},
                account_permissions={},
                roles=[],
            )
        prefix = f"{bypass_token}:"
        if len(bearer) > len(prefix) and hmac.compare_digest(
            bearer[: len(prefix)], prefix
        ):
            account_id_part = bearer[len(prefix) :]
            return UserContext(
                user_id=f"test-bypass-{account_id_part}",
                email=f"member-{account_id_part}@test.internal",
                organization_permissions={},
                account_permissions={account_id_part: "edit"},
                roles=[],
            )

    # Choose which rate limiter to use
    active_limiter = rate_limiter if rate_limiter is not None else token_rate_limiter
    # Get client info for audit logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    audit_logger = get_audit_logger()

    if not credentials:
        # Apply rate limiting for missing credentials (ctx=None — no identity established).
        await _apply_rate_limiting(
            request, active_limiter, audit_logger, client_ip, ctx=None
        )

        await audit_logger.log_login_failure(
            ip_address=client_ip,
            user_agent=user_agent,
            reason="Missing authentication credentials",
        )
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # Verify the Firebase ID token
        t0 = time.time()
        decoded_token, user_id, email = await _verify_and_decode_token(
            credentials, audit_logger, client_ip, user_agent, request
        )
        logger.info(
            "Firebase token verification completed",
            extra=log_context(
                component="auth",
                action="verify_token",
                duration_ms=(time.time() - t0) * 1000,
            ),
        )

        # Apply rate limiting to every authenticated request. Super admins are
        # NOT exempt — exempting them removed the brute-force ceiling on the
        # most privileged tier.
        #
        # The chat-sidebar load-test UID *is* exempt: 1000 VUs polling from a
        # single Cloud Build egress IP would otherwise saturate the 60-req/min
        # per-IP bucket on the very first volley and prevent the test from
        # measuring conversation-endpoint latency.  Bypass is empty in prod —
        # configured via the LOAD_TEST_BYPASS_UID env var on staging only.
        bypass_uid = settings.load_test_bypass_uid
        if bypass_uid and user_id == bypass_uid:
            # `user_id` goes through `extra` (a free-form dict on LogContext)
            # rather than as a positional/keyword arg, since LogContext is a
            # fixed-schema dataclass and rejects unknown fields.
            logger.info(
                "Skipping rate limit for load-test UID",
                extra=log_context(
                    component="auth",
                    action="rate_limit_bypass",
                    extra={"user_id": user_id},
                ),
            )
        else:
            # Pass a minimal UserContext so authenticated_key_strategy can derive a
            # per-user bucket key.  The full UserContext (with permissions) is built
            # after the cache/Firestore lookup below — user_id + email are sufficient
            # because authenticated_key_strategy only reads ctx.user_id (D-10).
            minimal_ctx = UserContext(
                user_id=user_id,
                email=email,
                organization_permissions={},
                account_permissions={},
                roles=[],
            )
            await _apply_rate_limiting(
                request, active_limiter, audit_logger, client_ip, ctx=minimal_ctx
            )

        # Check if token is revoked
        await _check_token_revocation(
            decoded_token, user_id, audit_logger, client_ip, user_agent
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    logger.debug(f"Checking cache for user {user_id}")
    # Try to get from cache first (lazy import to avoid Redis initialization at module load)
    from .cached_user_context import get_cached_user_context_service

    cached_user_service = get_cached_user_context_service()
    logger.debug("Got cached service, calling get_user_context")
    cached_context = cached_user_service.get_user_context(user_id)
    if cached_context:
        logger.info(
            "Auth completed (cache hit)",
            extra=log_context(
                component="auth",
                action="get_user_context",
                duration_ms=(time.time() - t_start) * 1000,
                extra={"cache_hit": True},
            ),
        )
        return cached_context

    logger.debug(f"No cache, fetching from Firestore for {user_id}")

    # Get Firestore client
    firestore_db = firestore_service.get_client()

    # Get or create user document
    t_fs = time.time()
    user_data = await _get_or_create_user_document(
        firestore_db, user_id, email, audit_logger, client_ip, user_agent
    )
    logger.info(
        "Firestore user document lookup completed",
        extra=log_context(
            component="auth",
            action="get_user_document",
            duration_ms=(time.time() - t_fs) * 1000,
        ),
    )

    # Build user context from data
    user_context = _build_user_context_from_data(user_id, email, user_data)

    # Cache the user context
    cached_user_service.set_user_context(user_context)

    # Log successful authentication
    await audit_logger.log_login_success(
        user_id=user_id,
        email=email,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    logger.info(
        "Auth completed (cache miss)",
        extra=log_context(
            component="auth",
            action="get_user_context",
            duration_ms=(time.time() - t_start) * 1000,
            extra={"cache_hit": False},
        ),
    )
    return user_context


async def get_current_user_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> UserContext:
    """Get the current user context from Firebase auth token.

    FastAPI-compatible wrapper that uses the default token_rate_limiter.

    Args:
        request: The FastAPI request object
        credentials: HTTP Bearer credentials containing Firebase ID token
        firestore_service: Firestore service instance

    Returns:
        UserContext object with user info and permissions

    Raises:
        HTTPException: If authentication fails or rate limit exceeded
    """
    return await _get_user_context_with_limiter(
        request, credentials, firestore_service, rate_limiter=None
    )


async def get_optional_user_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> UserContext | None:
    """Get optional user context from Firebase auth token.

    Returns None ONLY when no credentials are presented. If credentials ARE
    presented but invalid (malformed JWT, revoked token, missing identity
    claims), the underlying HTTPException is re-raised so the caller fails
    closed at 401 rather than silently downgrading to an anonymous request.
    """
    if not credentials:
        return None

    return await get_current_user_context(request, credentials, firestore_service)


async def check_account_access(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
) -> UserContext:
    """FastAPI dependency gating every account-scoped route on membership.

    Non-members receive 403. Returns UserContext so downstream handlers that
    need it can declare it as a dependency without a second auth round-trip.
    """
    if not user.has_account_access(account_id):
        audit_logger = get_audit_logger()
        await audit_logger.log_access_denied(
            user_id=user.user_id,
            resource_type="account",
            resource_id=account_id,
            required_permission=None,
        )
        raise HTTPException(status_code=403, detail="forbidden")
    return user
