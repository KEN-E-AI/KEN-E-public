"""Tests for authentication models."""

from src.kene_api.auth.models import UserContext


class TestUserContext:
    """Test UserContext model."""

    def test_is_super_admin_true(self):
        """Super admin status comes from the super_admin role."""
        user = UserContext(
            user_id="123",
            email="admin@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )
        assert user.is_super_admin is True

    def test_is_super_admin_false(self):
        """A user with no roles is not a super admin."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={},
            account_permissions={},
        )
        assert user.is_super_admin is False

    def test_is_super_admin_ignores_email_domain(self):
        """An @ken-e.ai email without the role does NOT confer super admin.

        Super-admin status derives solely from an explicit role grant keyed on
        the immutable Firebase uid — never from the email string. Firebase
        signup is open, so an email domain is not an authorization decision.
        """
        user = UserContext(
            user_id="123",
            email="anyone@ken-e.ai",
            organization_permissions={},
            account_permissions={},
        )
        assert user.is_super_admin is False

    def test_has_account_permission_super_admin(self):
        """Test super admin has access to any account."""
        user = UserContext(
            user_id="123",
            email="admin@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )
        assert user.has_account_permission("acc123", "org456", "edit") is True
        assert user.has_account_permission("acc123", "org456", "view") is True

    def test_has_account_permission_org_admin(self):
        """Test org admin has edit access to accounts in their org."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org456": "admin"},
            account_permissions={},
        )
        # Admin has access to accounts in their org
        assert user.has_account_permission("acc123", "org456", "edit") is True
        assert user.has_account_permission("acc123", "org456", "view") is True
        # But not to accounts in other orgs
        assert user.has_account_permission("acc123", "org789", "edit") is False

    def test_has_account_permission_view_role_with_permissions(self):
        """Test view-role user with explicit account permissions."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org456": "view"},
            account_permissions={"acc123": "edit", "acc456": "view"},
        )
        # Has edit access to acc123
        assert user.has_account_permission("acc123", "org456", "edit") is True
        assert user.has_account_permission("acc123", "org456", "view") is True
        # Has only view access to acc456
        assert user.has_account_permission("acc456", "org456", "edit") is False
        assert user.has_account_permission("acc456", "org456", "view") is True
        # No access to acc789
        assert user.has_account_permission("acc789", "org456", "view") is False

    def test_has_organization_permission_super_admin(self):
        """Test super admin has admin access to any organization."""
        user = UserContext(
            user_id="123",
            email="admin@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )
        assert user.has_organization_permission("org123", "admin") is True
        assert user.has_organization_permission("org123", "view") is True
        assert user.has_organization_permission(None, "admin") is True

    def test_has_organization_permission_specific_org(self):
        """Test organization permission for specific org."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org123": "admin", "org456": "view"},
            account_permissions={},
        )
        # Admin access to org123
        assert user.has_organization_permission("org123", "admin") is True
        assert user.has_organization_permission("org123", "view") is True
        # View access to org456
        assert user.has_organization_permission("org456", "admin") is False
        assert user.has_organization_permission("org456", "view") is True
        # No access to org789
        assert user.has_organization_permission("org789", "view") is False

    def test_has_organization_permission_any_org(self):
        """Test organization permission for ANY org."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org123": "admin", "org456": "view"},
            account_permissions={},
        )
        # Has admin in at least one org
        assert user.has_organization_permission(None, "admin") is True
        # Has view in at least one org
        assert user.has_organization_permission(None, "view") is True

    def test_has_organization_permission_no_admin(self):
        """Test organization permission when user has no admin role."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org123": "view", "org456": "view"},
            account_permissions={},
        )
        # No admin in any org
        assert user.has_organization_permission(None, "admin") is False
        # Has view in at least one org
        assert user.has_organization_permission(None, "view") is True

    def test_get_effective_organization_role(self):
        """Test getting effective organization role."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org123": "admin", "org456": "view"},
            account_permissions={},
        )
        assert user.get_effective_organization_role("org123") == "admin"
        assert user.get_effective_organization_role("org456") == "view"
        assert user.get_effective_organization_role("org789") is None

    def test_get_effective_organization_role_super_admin(self):
        """Test super admin always gets admin role."""
        user = UserContext(
            user_id="123",
            email="admin@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )
        assert user.get_effective_organization_role("any_org") == "admin"

    def test_get_effective_account_role(self):
        """Test getting effective account role."""
        user = UserContext(
            user_id="123",
            email="user@example.com",
            organization_permissions={"org123": "admin", "org456": "view"},
            account_permissions={"acc789": "edit", "acc012": "view"},
        )
        # Org admin gets edit access
        assert user.get_effective_account_role("acc123", "org123") == "edit"
        # View-role user with explicit permissions
        assert user.get_effective_account_role("acc789", "org456") == "edit"
        assert user.get_effective_account_role("acc012", "org456") == "view"
        # No access
        assert user.get_effective_account_role("acc999", "org456") is None

    def test_get_effective_account_role_super_admin(self):
        """Test super admin always gets edit role."""
        user = UserContext(
            user_id="123",
            email="admin@example.com",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )
        assert user.get_effective_account_role("any_acc", "any_org") == "edit"
