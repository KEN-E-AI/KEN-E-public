"""
Unit tests for strategy document access control.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from api.src.kene_api.auth.models import UserContext
from api.src.kene_api.routers.strategy import check_strategy_access


class TestStrategyAccessControl:
    """Test access control for strategy documents."""
    
    @pytest.fixture
    def super_admin_user(self):
        """Create a super admin user context."""
        return UserContext(
            user_id="admin_001",
            email="admin@ken-e.ai",
            accessible_accounts=["all"],
            permissions={},
            organization_permissions={"ken-e": "admin"},
            account_permissions={}
        )
    
    @pytest.fixture
    def org_admin_user(self):
        """Create an organization admin user context."""
        return UserContext(
            user_id="org_admin_001",
            email="admin@company.com",
            accessible_accounts=["account_001", "account_002"],
            permissions={},
            organization_permissions={"org_001": "admin"},
            account_permissions={}
        )
    
    @pytest.fixture
    def regular_user_with_edit(self):
        """Create a regular user with edit permissions."""
        return UserContext(
            user_id="user_001",
            email="user@company.com",
            accessible_accounts=["account_001"],
            permissions={"account_001": "editor"},
            organization_permissions={"org_001": "view"},
            account_permissions={"account_001": "edit"}
        )
    
    @pytest.fixture
    def regular_user_view_only(self):
        """Create a regular user with view-only permissions."""
        return UserContext(
            user_id="user_002",
            email="viewer@company.com",
            accessible_accounts=["account_001"],
            permissions={},
            organization_permissions={"org_001": "view"},
            account_permissions={"account_001": "view"}
        )
    
    @pytest.fixture
    def unauthorized_user(self):
        """Create a user with no access."""
        return UserContext(
            user_id="user_003",
            email="unauthorized@other.com",
            accessible_accounts=[],
            permissions={},
            organization_permissions={},
            account_permissions={}
        )
    
    @pytest.mark.asyncio
    async def test_super_admin_has_full_access(self, super_admin_user):
        """Test that super admins have full access to all accounts."""
        # Should have view access
        result = await check_strategy_access("any_account", super_admin_user, "view")
        assert result == super_admin_user
        
        # Should have edit access
        result = await check_strategy_access("any_account", super_admin_user, "edit")
        assert result == super_admin_user
    
    @pytest.mark.asyncio
    async def test_org_admin_has_account_access(self, org_admin_user):
        """Test that org admins have access to their accounts."""
        # Should have view access to org accounts
        result = await check_strategy_access("account_001", org_admin_user, "view")
        assert result == org_admin_user
        
        # Should have edit access to org accounts
        result = await check_strategy_access("account_001", org_admin_user, "edit")
        assert result == org_admin_user
    
    @pytest.mark.asyncio
    async def test_user_with_edit_permissions(self, regular_user_with_edit):
        """Test user with edit permissions."""
        # Should have view access
        result = await check_strategy_access("account_001", regular_user_with_edit, "view")
        assert result == regular_user_with_edit
        
        # Should have edit access
        result = await check_strategy_access("account_001", regular_user_with_edit, "edit")
        assert result == regular_user_with_edit
    
    @pytest.mark.asyncio
    async def test_user_with_view_only_permissions(self, regular_user_view_only):
        """Test user with view-only permissions."""
        from fastapi import HTTPException
        
        # Should have view access
        result = await check_strategy_access("account_001", regular_user_view_only, "view")
        assert result == regular_user_view_only
        
        # Should NOT have edit access
        with pytest.raises(HTTPException) as exc_info:
            await check_strategy_access("account_001", regular_user_view_only, "edit")
        assert exc_info.value.status_code == 403
    
    @pytest.mark.asyncio
    async def test_unauthorized_user_denied(self, unauthorized_user):
        """Test that unauthorized users are denied access."""
        from fastapi import HTTPException
        
        # Should NOT have view access
        with pytest.raises(HTTPException) as exc_info:
            await check_strategy_access("account_001", unauthorized_user, "view")
        assert exc_info.value.status_code == 403
        
        # Should NOT have edit access
        with pytest.raises(HTTPException) as exc_info:
            await check_strategy_access("account_001", unauthorized_user, "edit")
        assert exc_info.value.status_code == 403
    
    def test_user_context_is_super_admin(self, super_admin_user, regular_user_with_edit):
        """Test is_super_admin property."""
        assert super_admin_user.is_super_admin is True
        assert regular_user_with_edit.is_super_admin is False
    
    def test_user_context_has_account_access(
        self, 
        super_admin_user,
        org_admin_user,
        regular_user_with_edit,
        unauthorized_user
    ):
        """Test has_account_access method."""
        # Super admin has access to everything
        assert super_admin_user.has_account_access("any_account") is True
        assert super_admin_user.has_account_access("any_account", ["edit"]) is True
        
        # Org admin has access to org accounts
        assert org_admin_user.has_account_access("account_001") is True
        assert org_admin_user.has_account_access("account_003") is True  # Has admin in some org
        
        # Regular user with edit has specific access
        assert regular_user_with_edit.has_account_access("account_001") is True
        assert regular_user_with_edit.has_account_access("account_001", ["edit"]) is True
        assert regular_user_with_edit.has_account_access("account_002") is False
        
        # Unauthorized user has no access
        assert unauthorized_user.has_account_access("account_001") is False