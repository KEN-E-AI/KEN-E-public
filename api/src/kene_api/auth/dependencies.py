"""Authentication dependencies for FastAPI."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..firestore import FirestoreService, get_firestore_service
from ..rate_limiter import progress_rate_limiter
from .firebase_admin import verify_id_token
from .models import UserContext
from .user_context import _get_user_context_with_limiter

logger = logging.getLogger(__name__)

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> Optional[UserContext]:
    """
    Get current user from Bearer token (optional).

    Returns None if no token provided or token is invalid.

    Args:
        credentials: HTTP Bearer credentials
        firestore_service: Firestore service instance

    Returns:
        Optional[UserContext]: User context if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        # Verify the token
        decoded_token = verify_id_token(credentials.credentials)

        # Get Firestore client
        firestore_db = firestore_service.get_client()

        # Fetch user document from Firestore
        user_ref = firestore_db.collection("users").document(decoded_token["uid"])
        user_doc = user_ref.get()

        # Build user context
        user_context = UserContext(
            user_id=decoded_token["uid"],
            email=decoded_token.get("email", ""),
            accessible_accounts=[],
            permissions={},
            organization_permissions={},
        )

        # Add permissions from user document if it exists
        if user_doc.exists:
            user_data = user_doc.to_dict()
            permissions = user_data.get("permissions", {})
            user_context.account_permissions = permissions.get("accounts", {})
            user_context.organization_permissions = permissions.get("organizations", {})

        return user_context

    except Exception as e:
        logger.warning(f"Failed to authenticate user: {e}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> UserContext:
    """
    Get current user from Bearer token (required).

    Raises 401 if no token provided or token is invalid.

    Args:
        credentials: HTTP Bearer credentials
        firestore_service: Firestore service instance

    Returns:
        UserContext: Authenticated user context

    Raises:
        HTTPException: 401 if authentication fails
    """
    user = await get_current_user_optional(credentials, firestore_service)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_account_access(
    user: UserContext,
    account_id: str,
    required_roles: Optional[list[str]] = None,
) -> bool:
    """
    Check if user has access to an account.

    Args:
        user: User context
        account_id: Account ID to check
        required_roles: List of acceptable roles (if None, any role is accepted)

    Returns:
        bool: True if user has access

    Raises:
        HTTPException: 403 if user lacks access
    """
    user_role = user.account_permissions.get(account_id)

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to account {account_id}",
        )

    if required_roles and user_role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {', '.join(required_roles)}",
        )

    return True


def require_organization_access(
    user: UserContext,
    organization_id: str,
    required_roles: Optional[list[str]] = None,
) -> bool:
    """
    Check if user has access to an organization.

    Args:
        user: User context
        organization_id: Organization ID to check
        required_roles: List of acceptable roles (if None, any role is accepted)

    Returns:
        bool: True if user has access

    Raises:
        HTTPException: 403 if user lacks access
    """
    user_role = user.organization_permissions.get(organization_id)

    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to organization {organization_id}",
        )

    if required_roles and user_role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required roles: {', '.join(required_roles)}",
        )

    return True


async def get_user_context_for_polling(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> UserContext:
    """Get user context with higher rate limits for polling endpoints.

    This function uses the progress_rate_limiter which allows 120 requests/minute
    instead of the default 60 requests/minute, making it suitable for polling
    endpoints during long-running operations.

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
        request=request,
        credentials=credentials,
        firestore_service=firestore_service,
        rate_limiter=progress_rate_limiter,  # Use progress rate limiter for polling
    )
