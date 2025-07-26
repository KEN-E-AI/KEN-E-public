"""User context and authentication utilities."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud import firestore

from ..firestore import get_firestore_service
from .audit_logger import SecurityEventType, get_audit_logger
from .cached_user_context import get_cached_user_context_service
from .firebase_admin import initialize_firebase_admin, verify_id_token
from .models import UserContext
from .rate_limiting import token_rate_limiter
from .token_revocation import get_token_revocation_service

logger = logging.getLogger(__name__)

# Initialize Firebase Admin on module load
initialize_firebase_admin()

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)


async def get_current_user_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    firestore_service = Depends(get_firestore_service),
) -> UserContext:
    """Get the current user context from Firebase auth token.
    
    Extracts and verifies the Firebase ID token from the Authorization header,
    then loads user permissions from Firestore.
    
    Args:
        request: The FastAPI request object
        credentials: HTTP Bearer credentials containing Firebase ID token
        firestore_service: Firestore service instance
        
    Returns:
        UserContext object with user info and permissions
        
    Raises:
        HTTPException: If authentication fails or rate limit exceeded
    """
    # Get client info for audit logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    audit_logger = get_audit_logger()
    
    # Apply rate limiting
    try:
        token_rate_limiter.check_rate_limit(request)
    except HTTPException as e:
        if e.status_code == 429:
            await audit_logger.log_rate_limit_exceeded(
                ip_address=client_ip or "unknown",
                endpoint=str(request.url),
            )
        raise
    
    if not credentials:
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
        decoded_token = verify_id_token(credentials.credentials)
        user_id = decoded_token["uid"]
        email = decoded_token.get("email", "")
        
        # Check if token is revoked
        token_revocation = get_token_revocation_service()
        token_id = decoded_token.get("jti") or decoded_token.get("sub", "") + str(decoded_token.get("iat", ""))
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
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
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
    
    # Try to get from cache first
    cached_user_service = get_cached_user_context_service()
    cached_context = cached_user_service.get_user_context(user_id)
    if cached_context:
        logger.debug(f"Found cached user context for {user_id}")
        return cached_context
    
    # Get Firestore client
    firestore_db = firestore_service.get_client()
    
    # Load user data from Firestore
    user_doc = firestore_db.collection("users").document(user_id).get()
    
    if not user_doc.exists:
        # Create basic user document if it doesn't exist
        logger.info(f"Creating user document for {user_id}")
        user_data = {
            "uid": user_id,
            "email": email,
            "profile": {
                "email": email,
            },
            "permissions": {
                "accounts": {},
                "organizations": {},
            },
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        firestore_db.collection("users").document(user_id).set(user_data)
        
        # Log user creation
        await audit_logger.log_event(
            event_type=SecurityEventType.USER_CREATED,
            user_id=user_id,
            email=email,
            ip_address=client_ip,
            user_agent=user_agent,
            severity="INFO",
        )
    else:
        user_data = user_doc.to_dict()
    
    # Extract permissions
    permissions = user_data.get("permissions", {})
    account_permissions = permissions.get("accounts", {})
    organization_permissions = permissions.get("organizations", {})
    
    # Extract account permissions (new structure)
    # accounts field contains specific permissions for view-role users
    account_level_permissions = permissions.get("account_permissions", {})
    
    # Combine all accessible accounts from both old and new permission structures
    all_accessible_accounts = set(account_permissions.keys())
    all_accessible_accounts.update(account_level_permissions.keys())
    
    # Build user context
    user_context = UserContext(
        user_id=user_id,
        email=email,
        accessible_accounts=list(all_accessible_accounts),
        permissions=account_permissions,  # Keep for backward compatibility
        organization_permissions=organization_permissions,
        account_permissions=account_level_permissions,  # New field for view-role users
    )
    
    # Cache the user context
    cached_user_service.set_user_context(user_context)
    
    # Log successful authentication
    await audit_logger.log_login_success(
        user_id=user_id,
        email=email,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    
    return user_context


async def get_optional_user_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    firestore_service = Depends(get_firestore_service),
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
) -> None:
    """Verify user has access to an account.
    
    To be used within route handlers after getting user context.
    
    Args:
        account_id: The account ID to check
        required_roles: Optional list of required roles
        
    Raises:
        HTTPException: If access is denied
    """
    def check_access(user: UserContext):
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
) -> None:
    """Verify user has access to an organization.
    
    To be used within route handlers after getting user context.
    
    Args:
        organization_id: The organization ID to check
        required_roles: Optional list of required roles
        
    Raises:
        HTTPException: If access is denied
    """
    def check_access(user: UserContext):
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