"""Authentication models."""

from dataclasses import dataclass


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