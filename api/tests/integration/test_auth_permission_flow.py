"""Integration tests for authentication flow with new permission structure."""

from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.auth.dependencies import get_current_user_optional


class TestAuthPermissionFlow:
    """Integration tests for auth with new permission structure."""

    @pytest.mark.asyncio
    async def test_user_authentication_with_account_permissions(self):
        """Test user can authenticate and access account with new permission structure."""
        # Setup: Mock Firebase token verification
        mock_token = {
            "uid": "test_user_123",
            "email": "test@example.com",
        }

        # Setup: Mock Firestore with NEW permission structure
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "test_user_123",
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {"account_456": "edit", "account_789": "view"},
                "organizations": {"org_123": "admin"},
            },
        }

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        # Setup: Mock credentials
        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate user
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: User context created with new structure
        assert user_context is not None
        assert user_context.user_id == "test_user_123"
        assert user_context.email == "test@example.com"

        # Verify: Account permissions loaded correctly
        assert user_context.account_permissions == {
            "account_456": "edit",
            "account_789": "view",
        }
        assert user_context.organization_permissions == {"org_123": "admin"}

        # Verify: Permission checks work
        # Users with org admin access will have access to all accounts
        # So we need to test without org admin permissions
        user_context.organization_permissions = {}  # Remove org admin for this test

        # has_account_access deprecated (IN-2); verify via has_account_permission with a placeholder org
        assert user_context.has_account_permission("account_456", "org_123", "edit") is True
        assert user_context.has_account_permission("account_789", "org_123", "view") is True
        assert user_context.has_account_permission("account_999", "org_123", "view") is False

    @pytest.mark.asyncio
    async def test_super_admin_detection(self):
        """Test that a super admin is identified from the super_admin role."""
        # Setup: token for a user whose Firestore doc carries the role grant.
        # Super-admin status derives from the `roles` array, not the email.
        mock_token = {
            "uid": "admin_user_123",
            "email": "admin@example.com",
        }

        # Setup: Mock Firestore with the super_admin role grant on the doc.
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "admin_user_123",
            "email": "admin@example.com",
            "permissions": {"account_permissions": {}, "organizations": {}},
            "roles": ["super_admin"],
        }

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate super admin
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: Super admin status detected
        assert user_context is not None
        assert user_context.is_super_admin is True

        # Verify: Super admin bypass is captured by is_super_admin flag
        assert user_context.is_super_admin is True

    @pytest.mark.asyncio
    async def test_old_structure_detected_logs_warning(self, caplog):
        """Test that old permission structure triggers warning but doesn't break auth."""
        # Setup: User still has old 'accounts' field (migration not complete)
        mock_token = {"uid": "old_user_789", "email": "old@example.com"}

        # Setup: Mock Firestore with BOTH old and new structures
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "old_user_789",
            "email": "old@example.com",
            "permissions": {
                "accounts": {
                    "account_123": "edit"
                },  # Old structure (should be ignored)
                "account_permissions": {
                    "account_456": "view"
                },  # New structure (should be used)
                "organizations": {},
            },
        }

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate user with old structure
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: Auth succeeded (doesn't break)
        assert user_context is not None
        assert user_context.user_id == "old_user_789"

        # Verify: Only NEW structure used (old structure ignored)
        assert user_context.account_permissions == {"account_456": "view"}
        assert "account_123" not in user_context.account_permissions

        # Verify: Warning logged about old structure
        assert any(
            "deprecated 'permissions.accounts' field" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_user_without_permissions_in_firestore(self):
        """Test user authentication when user doc exists but has no permissions."""
        # Setup: User with no permissions in Firestore
        mock_token = {"uid": "new_user_999", "email": "newuser@example.com"}

        # Setup: Mock Firestore with empty permissions
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "new_user_999",
            "email": "newuser@example.com",
            "permissions": {},  # No permissions set
        }

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate user
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: User context created with empty permissions
        assert user_context is not None
        assert user_context.user_id == "new_user_999"
        assert user_context.account_permissions == {}
        assert user_context.organization_permissions == {}
        assert user_context.has_account_permission("any_account", "any_org", "view") is False

    @pytest.mark.asyncio
    async def test_user_not_in_firestore(self):
        """Test user authentication when user doc doesn't exist in Firestore."""
        # Setup: Valid token but user not in Firestore yet
        mock_token = {"uid": "brand_new_user", "email": "brandnew@example.com"}

        # Setup: Mock Firestore with non-existent user
        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate user
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: User context created with default empty permissions
        assert user_context is not None
        assert user_context.user_id == "brand_new_user"
        assert user_context.email == "brandnew@example.com"
        assert user_context.account_permissions == {}
        assert user_context.organization_permissions == {}

    @pytest.mark.asyncio
    async def test_permission_check_edit_vs_view(self):
        """Test account permission checking distinguishes between edit and view roles."""
        # Setup: User with mixed edit/view permissions
        mock_token = {"uid": "test_user", "email": "test@example.com"}

        mock_firestore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "test_user",
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {
                    "account_edit": "edit",
                    "account_view": "view",
                },
                "organizations": {},
            },
        }

        mock_firestore_client = MagicMock()
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc
        mock_firestore.get_client.return_value = mock_firestore_client

        mock_credentials = MagicMock()
        mock_credentials.credentials = "fake_token"

        # Execute: Authenticate user
        with patch(
            "src.kene_api.auth.dependencies.verify_id_token", return_value=mock_token
        ):
            user_context = await get_current_user_optional(
                mock_credentials, mock_firestore
            )

        # Verify: Permission checks work correctly
        assert user_context is not None

        # Check access via has_account_permission (has_account_access deprecated IN-2)
        assert user_context.has_account_permission("account_edit", "test_org", "edit") is True
        assert user_context.has_account_permission("account_view", "test_org", "view") is True

        # Check specific permissions (requires organization_id parameter)
        test_org_id = "test_org"
        assert (
            user_context.has_account_permission("account_edit", test_org_id, "edit")
            is True
        )
        assert (
            user_context.has_account_permission("account_edit", test_org_id, "view")
            is True
        )  # Edit permission includes view
        assert (
            user_context.has_account_permission("account_view", test_org_id, "view")
            is True
        )
        assert (
            user_context.has_account_permission("account_view", test_org_id, "edit")
            is False
        )  # View permission doesn't include edit
