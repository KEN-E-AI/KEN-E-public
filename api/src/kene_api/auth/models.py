"""Authentication models."""

from dataclasses import dataclass, field

# The role string that confers super-admin privileges. Single source of truth
# shared by UserContext.is_super_admin, the admin endpoints, and the bootstrap
# migration — never compare against the literal elsewhere.
SUPER_ADMIN_ROLE = "super_admin"


@dataclass
class UserContext:
    """User context containing authentication and authorization information."""

    user_id: str
    email: str
    organization_permissions: dict[str, str]  # organization_id -> role
    account_permissions: dict[str, str] = field(
        default_factory=dict
    )  # account_id -> edit|view
    # Explicit role grants stored on the users/{uid} Firestore doc. Super-admin
    # status derives solely from membership here (see is_super_admin). Only
    # server-side admin endpoints may write this field — every client write
    # path to users/{uid} must reject a client-supplied `roles`.
    roles: list[str] = field(default_factory=list)

    @property
    def is_super_admin(self) -> bool:
        """Check if user is a super admin (KEN-E support team member).

        Derives solely from an explicit ``super_admin`` role grant on the
        user's Firestore doc, keyed on the immutable Firebase uid. The former
        ``@ken-e.ai`` email-domain check was removed — an email string is not
        an authorization decision, and Firebase signup is open.
        """
        return SUPER_ADMIN_ROLE in self.roles

    @property
    def accessible_accounts(self) -> list[str]:
        """Get list of accessible account IDs.

        Backward compatibility property that returns account IDs from account_permissions.
        This replaces the deprecated accessible_accounts field.

        **IMPORTANT LIMITATION:**
        This property only returns accounts with EXPLICIT permissions in account_permissions.
        It does NOT include accounts accessible via:
        - Super admin status (the super_admin role)
        - Organization admin role (implicit access to all org accounts)

        For org admins and super admins, this will return an empty list even though they
        have access to accounts. Callers should:
        1. Check if user.is_super_admin or has org admin role first
        2. If true, fetch accounts from Neo4j instead of using this property
        3. See notifications_v2.py:147-182 for example implementation

        Returns:
            List of account IDs the user has explicit permissions for.
        """
        return list(self.account_permissions.keys())

    def has_account_access(
        self, account_id: str, required_roles: list[str] | None = None
    ) -> bool:
        """DEPRECATED — Cross-org privilege escalation risk. Do not use.

        This method granted access to any admin of *any* org without verifying
        which org owns ``account_id`` (IN-2). It is retained as a stub that
        raises ``NotImplementedError`` at call time so any surviving call site
        surfaces a loud failure rather than silently bypassing the tenant
        isolation check.

        Use ``auth.account_org.require_account_access_for`` instead.
        See IN-2 for migration context.
        """
        raise NotImplementedError(
            "has_account_access is unsafe — any-org-admin bypass removed in IN-2. "
            "Use auth.account_org.require_account_access_for(user, account_id, level) instead."
        )

    def has_account_permission(
        self, account_id: str, organization_id: str, required_level: str = "view"
    ) -> bool:
        """Check if user has specific permission level for an account.

        This is the preferred method when the account's organization is known.

        Args:
            account_id: The account ID to check
            organization_id: The organization ID that owns the account
            required_level: Required permission level (view or edit)

        Returns:
            True if user has the required permission level, False otherwise
        """
        # Super admins always have edit access
        if self.is_super_admin:
            return True

        # Check if user is admin of the specific organization
        if self.organization_permissions.get(organization_id) == "admin":
            return True

        # Check explicit account permissions
        account_perm = self.account_permissions.get(account_id)
        if not account_perm:
            return False

        # Check permission level
        if required_level == "view":
            return account_perm in ["view", "edit"]
        elif required_level == "edit":
            return account_perm == "edit"

        return False

    def has_organization_access(
        self, organization_id: str, required_roles: list[str] | None = None
    ) -> bool:
        """Check if user has access to an organization with optional role check.

        Super admins always have admin access to all organizations.

        Args:
            organization_id: The organization ID to check
            required_roles: Optional list of required roles

        Returns:
            True if user has access, False otherwise
        """
        # Super admins always have admin access
        if self.is_super_admin:
            return True

        if organization_id not in self.organization_permissions:
            return False

        if required_roles:
            user_role = self.organization_permissions.get(organization_id, "")
            return user_role in required_roles

        return True

    def get_effective_organization_role(self, organization_id: str) -> str | None:
        """Get the effective role for an organization, considering super admin status.

        Args:
            organization_id: The organization ID

        Returns:
            The effective role (admin/view) or None if no access
        """
        if self.is_super_admin:
            return "admin"
        return self.organization_permissions.get(organization_id)

    def has_organization_permission(
        self, organization_id: str | None = None, required_role: str = "view"
    ) -> bool:
        """Check if user has specific permission level for an organization.

        If no organization_id is provided, checks if user has the required role in ANY organization.

        Args:
            organization_id: The organization ID to check (optional)
            required_role: Required permission level (admin or view)

        Returns:
            True if user has the required permission level, False otherwise
        """
        if self.is_super_admin:
            return True

        if organization_id:
            org_role = self.organization_permissions.get(organization_id)
            if not org_role:
                return False
            if required_role == "view":
                return org_role in ["view", "admin"]
            elif required_role == "admin":
                return org_role == "admin"
            return False
        else:
            # Check if user has the required role in ANY organization
            for role in self.organization_permissions.values():
                if required_role == "view" and role in ["view", "admin"]:
                    return True
                elif required_role == "admin" and role == "admin":
                    return True
            return False

    def get_effective_account_role(
        self, account_id: str, organization_id: str | None = None
    ) -> str | None:
        """Get the effective role for an account, considering super admin and org admin status.

        Args:
            account_id: The account ID
            organization_id: The organization ID (if known)

        Returns:
            The effective role (edit/view) or None if no access
        """
        if self.is_super_admin:
            return "edit"

        # Check if user is org admin (simplified check for now)
        if (
            organization_id
            and self.organization_permissions.get(organization_id) == "admin"
        ):
            return "edit"

        # Check explicit account permissions
        return self.account_permissions.get(account_id)
