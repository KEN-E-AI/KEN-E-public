"""Tests for account permission endpoints."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.kene_api.auth.models import UserContext
from src.kene_api.routers.accounts import (
    grant_account_access,
    revoke_account_access,
    get_account_permissions,
    GrantAccountAccessRequest,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.fixture
def admin_user():
    """Create an admin user context."""
    return UserContext(
        user_id="admin123",
        email="admin@example.com",
        organization_permissions={"org456": "admin"},
        account_permissions={},
    )


@pytest.fixture
def view_user():
    """Create a view-role user context."""
    return UserContext(
        user_id="user123",
        email="user@example.com",
        organization_permissions={"org456": "view"},
        account_permissions={},
    )


@pytest.fixture
def super_admin_user():
    """Create a super admin user context."""
    return UserContext(
        user_id="super123",
        email="support@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


@pytest.fixture
def mock_db():
    """Create a mock database service."""
    db = AsyncMock()
    db.health_check = AsyncMock(return_value=True)
    return db


@pytest.fixture
def mock_firestore():
    """Create a mock Firestore service."""
    firestore = MagicMock()
    firestore.get_document = MagicMock()
    firestore.set_nested_field = MagicMock(return_value=True)
    firestore.get_client = MagicMock()
    return firestore


class TestGrantAccountAccess:
    """Test grant_account_access endpoint."""

    @pytest.mark.asyncio
    async def test_grant_access_as_admin(self, admin_user, mock_db, mock_firestore):
        """Test admin can grant account access."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "target@example.com"},
            "permissions": {"organizations": {"org456": "view"}},
        }

        request = GrantAccountAccessRequest(user_id="target123", access_level="edit")

        # Execute
        with patch("src.kene_api.routers.accounts.get_cached_user_context_service"):
            result = await grant_account_access(
                "acc123", request, admin_user, mock_db, mock_firestore
            )

        # Verify
        assert result.success is True
        mock_firestore.set_nested_field.assert_called_once_with(
            collection="users",
            document_id="target123",
            field_path="permissions.account_permissions.acc123",
            value="edit",
        )

    @pytest.mark.asyncio
    async def test_grant_access_as_view_user(self, view_user, mock_db, mock_firestore):
        """Test view-role user cannot grant account access."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        request = GrantAccountAccessRequest(user_id="target123", access_level="edit")

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await grant_account_access(
                "acc123", request, view_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 403
        assert "Only organization admins can grant account access" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_grant_access_to_non_member(
        self, admin_user, mock_db, mock_firestore
    ):
        """Test cannot grant access to non-organization member."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "target@example.com"},
            "permissions": {"organizations": {"org789": "view"}},  # Different org
        }

        request = GrantAccountAccessRequest(user_id="target123", access_level="edit")

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await grant_account_access(
                "acc123", request, admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 400
        assert "does not have access to the organization" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_grant_access_to_super_admin(
        self, admin_user, mock_db, mock_firestore
    ):
        """Test cannot grant access to super admin."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "support@ken-e.ai"},
            "permissions": {"organizations": {"org456": "view"}},
        }

        request = GrantAccountAccessRequest(user_id="super123", access_level="edit")

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await grant_account_access(
                "acc123", request, admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 403
        assert "Cannot modify permissions for KEN-E support team members" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_grant_access_to_org_admin(self, admin_user, mock_db, mock_firestore):
        """Test cannot grant explicit access to org admin."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "otheradmin@example.com"},
            "permissions": {"organizations": {"org456": "admin"}},
        }

        request = GrantAccountAccessRequest(user_id="admin456", access_level="edit")

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await grant_account_access(
                "acc123", request, admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 400
        assert "Organization admins already have access to all accounts" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_grant_access_invalid_level(
        self, admin_user, mock_db, mock_firestore
    ):
        """Test invalid access level."""
        request = GrantAccountAccessRequest(user_id="target123", access_level="invalid")

        with pytest.raises(HTTPException) as exc_info:
            await grant_account_access(
                "acc123", request, admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 400
        assert "Invalid access_level" in str(exc_info.value.detail)


class TestRevokeAccountAccess:
    """Test revoke_account_access endpoint."""

    @pytest.mark.asyncio
    async def test_revoke_access_as_admin(self, admin_user, mock_db, mock_firestore):
        """Test admin can revoke account access."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "target@example.com"},
            "permissions": {"organizations": {"org456": "view"}},
        }

        firestore_client = MagicMock()
        user_ref = MagicMock()
        firestore_client.collection.return_value.document.return_value = user_ref
        mock_firestore.get_client.return_value = firestore_client

        # Execute
        with patch("src.kene_api.routers.accounts.get_cached_user_context_service"):
            result = await revoke_account_access(
                "acc123", "target123", admin_user, mock_db, mock_firestore
            )

        # Verify
        assert result.success is True
        user_ref.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_access_from_super_admin(
        self, admin_user, mock_db, mock_firestore
    ):
        """Test cannot revoke access from super admin."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "support@ken-e.ai"},
            "permissions": {"organizations": {"org456": "view"}},
        }

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await revoke_account_access(
                "acc123", "super123", admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 403
        assert "Cannot modify permissions for KEN-E support team members" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_revoke_access_from_org_admin(
        self, admin_user, mock_db, mock_firestore
    ):
        """Test cannot revoke access from org admin."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])
        mock_firestore.get_document.return_value = {
            "profile": {"email": "otheradmin@example.com"},
            "permissions": {"organizations": {"org456": "admin"}},
        }

        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await revoke_account_access(
                "acc123", "admin456", admin_user, mock_db, mock_firestore
            )

        assert exc_info.value.status_code == 400
        assert "Cannot revoke access from organization admins" in str(
            exc_info.value.detail
        )


class TestGetAccountPermissions:
    """Test get_account_permissions endpoint."""

    @pytest.mark.asyncio
    async def test_get_permissions_as_admin(self, admin_user, mock_db, mock_firestore):
        """Test admin can view account permissions."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org456"}])

        firestore_client = MagicMock()
        user_doc1 = MagicMock()
        user_doc1.id = "user1"
        user_doc1.to_dict.return_value = {
            "profile": {
                "email": "user1@example.com",
                "firstName": "User",
                "lastName": "One",
            },
            "permissions": {"account_permissions": {"acc123": "edit"}},
        }
        user_doc2 = MagicMock()
        user_doc2.id = "user2"
        user_doc2.to_dict.return_value = {
            "profile": {"email": "user2@example.com"},
            "permissions": {
                "account_permissions": {"acc123": "view", "acc456": "edit"}
            },
        }

        firestore_client.collection.return_value.stream.return_value = [
            user_doc1,
            user_doc2,
        ]
        mock_firestore.get_client.return_value = firestore_client

        # Execute
        result = await get_account_permissions(
            "acc123", admin_user, mock_db, mock_firestore
        )

        # Verify
        assert result.account_id == "acc123"
        assert result.total == 2
        assert len(result.permissions) == 2
        assert result.permissions[0]["user_id"] == "user1"
        assert result.permissions[0]["access_level"] == "edit"
        assert result.permissions[1]["user_id"] == "user2"
        assert result.permissions[1]["access_level"] == "view"

    @pytest.mark.asyncio
    async def test_get_permissions_as_super_admin(
        self, super_admin_user, mock_db, mock_firestore
    ):
        """Test super admin can view any account permissions."""
        # Setup
        mock_db.execute_query = AsyncMock(return_value=[{"organization_id": "org999"}])

        firestore_client = MagicMock()
        firestore_client.collection.return_value.stream.return_value = []
        mock_firestore.get_client.return_value = firestore_client

        # Execute
        result = await get_account_permissions(
            "acc123", super_admin_user, mock_db, mock_firestore
        )

        # Verify - should succeed even though super admin has no org access
        assert result.account_id == "acc123"
        assert result.total == 0
