"""User context and authentication utilities."""

import logging
import time
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud import firestore

from shared.structured_logging import log_context

from ..config import settings
from ..firestore import FirestoreService, get_firestore_service
from ..rate_limiter import RateLimiter
from .audit_logger import AuditLogger, SecurityEventType, get_audit_logger
from .firebase_admin import initialize_firebase_admin, verify_id_token
from .models import UserContext
from .rate_limiting import token_rate_limiter
from .token_revocation import get_token_revocation_service

logger = logging.getLogger(__name__)

# Initialize Firebase Admin on module load
initialize_firebase_admin()

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)


async def _apply_rate_limiting(
    request: Request,
    rate_limiter: RateLimiter,
    audit_logger: AuditLogger,
    client_ip: Optional[str],
) -> None:
    """Apply rate limiting and log if exceeded.

    Args:
        request: The FastAPI request object
        rate_limiter: The rate limiter to use
        audit_logger: Audit logger instance
        client_ip: Client IP address for logging

    Raises:
        HTTPException: If rate limit is exceeded
    """
    try:
        rate_limiter.check_rate_limit(request)
    except HTTPException as e:
        if e.status_code == 429:
            await audit_logger.log_rate_limit_exceeded(
                ip_address=client_ip or "unknown",
                endpoint=str(request.url),
            )
        raise


async def _verify_and_decode_token(
    credentials: HTTPAuthorizationCredentials,
    audit_logger: AuditLogger,
    client_ip: Optional[str],
    user_agent: Optional[str],
    rate_limiter: RateLimiter,
    request: Request,
) -> tuple[dict[str, Any], str, str]:
    """Verify and decode Firebase ID token.

    Args:
        credentials: HTTP Bearer credentials
        audit_logger: Audit logger instance
        client_ip: Client IP address
        user_agent: User agent string
        rate_limiter: Rate limiter to use for failed attempts
        request: FastAPI request object

    Returns:
        Tuple of (decoded_token, user_id, email)

    Raises:
        HTTPException: If token verification fails
    """
    try:
        decoded_token = verify_id_token(credentials.credentials)
        user_id = decoded_token["uid"]
        email = decoded_token.get("email", "")
        return decoded_token, user_id, email
    except Exception as e:
        # Apply rate limiting for failed authentication attempts
        try:
            rate_limiter.check_rate_limit(request)
        except HTTPException as rate_error:
            if rate_error.status_code == 429:
                await audit_logger.log_rate_limit_exceeded(
                    ip_address=client_ip or "unknown",
                    endpoint=str(request.url),
                )
            logger.error(f"Failed to verify token: {e}")
            raise rate_error

        logger.error(f"Failed to verify token: {e}")
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
        )


async def _check_token_revocation(
    decoded_token: dict[str, Any],
    user_id: str,
    audit_logger: AuditLogger,
    client_ip: Optional[str],
    user_agent: Optional[str],
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
    client_ip: Optional[str],
    user_agent: Optional[str],
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
    rate_limiter: Optional[RateLimiter] = None,
) -> UserContext:
    """Internal function to get user context with custom rate limiter.

    This is the actual implementation that accepts a custom rate limiter.
    """
    t_start = time.time()

    # Choose which rate limiter to use
    active_limiter = rate_limiter if rate_limiter is not None else token_rate_limiter
    # Get client info for audit logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    audit_logger = get_audit_logger()

    if not credentials:
        # Apply rate limiting for missing credentials
        await _apply_rate_limiting(request, active_limiter, audit_logger, client_ip)

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
            credentials, audit_logger, client_ip, user_agent, active_limiter, request
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
            logger.info(
                "Skipping rate limit for load-test UID",
                extra=log_context(
                    component="auth",
                    action="rate_limit_bypass",
                    user_id=user_id,
                ),
            )
        else:
            await _apply_rate_limiting(
                request, active_limiter, audit_logger, client_ip
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
    logger.debug(f"Got cached service, calling get_user_context")
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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> UserContext | None:
    """Get optional user context from Firebase auth token.

    Returns None if no authentication token is present or if token is invalid.

    Args:
        request: The FastAPI request object
        credentials: Optional HTTP Bearer credentials
        firestore_service: Firestore service instance

    Returns:
        UserContext object or None
    """
    if not credentials:
        return None

    try:
        return await get_current_user_context(request, credentials, firestore_service)
    except HTTPException:
        return None


def require_account_access(
    account_id: str,
    required_roles: list[str] | None = None,
) -> Any:
    """Verify user has access to an account.

    To be used within route handlers after getting user context.

    Args:
        account_id: The account ID to check
        required_roles: Optional list of required roles

    Raises:
        HTTPException: If access is denied
    """

    def check_access(user: UserContext) -> None:
        if not user.has_account_access(account_id, required_roles):
            role_msg = f" with role in {required_roles}" if required_roles else ""

            # Log access denied - this is synchronous but we'll log it anyway
            import asyncio

            audit_logger = get_audit_logger()
            asyncio.create_task(
                audit_logger.log_access_denied(
                    user_id=user.user_id,
                    resource_type="account",
                    resource_id=account_id,
                    required_permission=str(required_roles) if required_roles else None,
                )
            )

            raise HTTPException(
                status_code=403,
                detail=f"Access denied to account {account_id}{role_msg}",
            )

    return check_access


def require_organization_access(
    organization_id: str,
    required_roles: list[str] | None = None,
) -> Any:
    """Verify user has access to an organization.

    To be used within route handlers after getting user context.

    Args:
        organization_id: The organization ID to check
        required_roles: Optional list of required roles

    Raises:
        HTTPException: If access is denied
    """

    def check_access(user: UserContext) -> None:
        if not user.has_organization_access(organization_id, required_roles):
            role_msg = f" with role in {required_roles}" if required_roles else ""

            # Log access denied - this is synchronous but we'll log it anyway
            import asyncio

            audit_logger = get_audit_logger()
            asyncio.create_task(
                audit_logger.log_access_denied(
                    user_id=user.user_id,
                    resource_type="organization",
                    resource_id=organization_id,
                    required_permission=str(required_roles) if required_roles else None,
                )
            )

            raise HTTPException(
                status_code=403,
                detail=f"Access denied to organization {organization_id}{role_msg}",
            )

    return check_access
