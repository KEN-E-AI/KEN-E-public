"""User context and authentication utilities."""

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Header
from google.cloud import firestore

from ..database import get_firestore_service


@dataclass
class UserContext:
    """User context containing authentication and authorization information."""
    
    user_id: str
    email: str
    accessible_accounts: list[str]
    permissions: dict[str, str]  # account_id -> role
    organization_permissions: dict[str, str]  # organization_id -> role
    
    def has_account_access(self, account_id: str, required_roles: list[str] | None = None) -> bool:
        """Check if user has access to an account with optional role check.
        
        Args:
            account_id: The account ID to check
            required_roles: Optional list of required roles
            
        Returns:
            True if user has access, False otherwise
        """
        if account_id not in self.permissions:
            return False
        
        if required_roles:
            user_role = self.permissions.get(account_id, "")
            return user_role in required_roles
        
        return True
    
    def has_organization_access(self, organization_id: str, required_roles: list[str] | None = None) -> bool:
        """Check if user has access to an organization with optional role check.
        
        Args:
            organization_id: The organization ID to check
            required_roles: Optional list of required roles
            
        Returns:
            True if user has access, False otherwise
        """
        if organization_id not in self.organization_permissions:
            return False
        
        if required_roles:
            user_role = self.organization_permissions.get(organization_id, "")
            return user_role in required_roles
        
        return True


async def get_current_user_context(
    x_user_id: str | None = Header(None, description="User ID header for authentication"),
    firestore_db: firestore.Client = Depends(get_firestore_service),
) -> UserContext:
    """Get the current user context from headers.
    
    This is a simplified implementation. In production, you would:
    1. Extract and verify a JWT token from Authorization header
    2. Load user data from cache/database
    3. Check for token expiry and revocation
    
    Args:
        x_user_id: User ID from header (temporary implementation)
        firestore_db: Firestore client
        
    Returns:
        UserContext object
        
    Raises:
        HTTPException: If authentication fails
    """
    # Temporary implementation using header
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Load user data from Firestore
    user_doc = firestore_db.collection("users").document(x_user_id).get()
    
    if not user_doc.exists:
        raise HTTPException(
            status_code=401,
            detail="Invalid user credentials",
        )
    
    user_data = user_doc.to_dict()
    
    # Extract permissions
    permissions = user_data.get("permissions", {})
    account_permissions = permissions.get("accounts", {})
    organization_permissions = permissions.get("organizations", {})
    
    # Build user context
    return UserContext(
        user_id=x_user_id,
        email=user_data.get("profile", {}).get("email", ""),
        accessible_accounts=list(account_permissions.keys()),
        permissions=account_permissions,
        organization_permissions=organization_permissions,
    )


async def get_optional_user_context(
    x_user_id: str | None = Header(None, description="Optional user ID header"),
    firestore_db: firestore.Client = Depends(get_firestore_service),
) -> UserContext | None:
    """Get optional user context from headers.
    
    Returns None if no authentication header is present.
    
    Args:
        x_user_id: Optional user ID from header
        firestore_db: Firestore client
        
    Returns:
        UserContext object or None
    """
    if not x_user_id:
        return None
    
    try:
        return await get_current_user_context(x_user_id, firestore_db)
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
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to organization {organization_id}{role_msg}",
            )
    
    return check_access