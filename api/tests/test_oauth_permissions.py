"""Tests for OAuth permission checks."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext


@pytest.fixture
def super_admin_user():
    """Create super admin user (granted the super_admin role)."""
    return UserContext(
        user_id="super123",
        email="admin@example.com",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


@pytest.fixture
def org_admin_user():
    """Create organization admin user (non-@ken-e.ai)."""
    return UserContext(
        user_id="orgadmin123",
        email="admin@example.com",
        organization_permissions={"org123": "admin"},
        account_permissions={},
    )


@pytest.fixture
def account_editor_user():
    """Create user with explicit edit permission on account."""
    return UserContext(
        user_id="editor123",
        email="editor@example.com",
        organization_permissions={},
        account_permissions={"acc123": "edit"},
    )


@pytest.fixture
def viewer_user():
    """Create user with only view permission."""
    return UserContext(
        user_id="viewer123",
        email="viewer@example.com",
        organization_permissions={},
        account_permissions={"acc123": "view"},
    )


@pytest.fixture
def no_access_user():
    """Create user with no permissions."""
    return UserContext(
        user_id="noone123",
        email="noone@example.com",
        organization_permissions={},
        account_permissions={},
    )


class TestOAuthAuthorizePermissions:
    """Test permission checks for OAuth authorization endpoint."""

    @pytest.mark.asyncio
    async def test_super_admin_can_authorize(self, super_admin_user):
        """Super admins should be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(
            "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID", "test_id"
        ):
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                "test_secret",
            ):
                with patch(
                    "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                    return_value="http://localhost/callback",
                ):
                    with patch(
                        "src.kene_api.routers.oauth_integrations.get_firestore_service"
                    ) as mock_fs:
                        mock_db = Mock()
                        mock_fs.return_value.get_client.return_value = mock_db

                        # Mock OAuth state service
                        mock_state_service = AsyncMock()
                        with patch(
                            "src.kene_api.routers.oauth_integrations.OAuthStateService",
                            return_value=mock_state_service,
                        ):
                            result = await authorize_google_analytics(
                                account_id="acc123",
                                current_user=super_admin_user,
                            )

                            assert "auth_url" in result
                            assert "accounts.google.com" in result["auth_url"]

    @pytest.mark.asyncio
    async def test_org_admin_can_authorize(self, org_admin_user):
        """Organization admins should be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(
            "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID", "test_id"
        ):
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                "test_secret",
            ):
                with patch(
                    "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                    return_value="http://localhost/callback",
                ):
                    with patch(
                        "src.kene_api.routers.oauth_integrations.get_firestore_service"
                    ) as mock_fs:
                        mock_db = Mock()
                        mock_fs.return_value.get_client.return_value = mock_db

                        mock_state_service = AsyncMock()
                        with patch(
                            "src.kene_api.routers.oauth_integrations.OAuthStateService",
                            return_value=mock_state_service,
                        ):
                            result = await authorize_google_analytics(
                                account_id="acc123",
                                current_user=org_admin_user,
                            )

                            # Should succeed for org admin
                            assert "auth_url" in result

    @pytest.mark.asyncio
    async def test_account_editor_can_authorize(self, account_editor_user):
        """Users with explicit edit permission should be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(
            "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID", "test_id"
        ):
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                "test_secret",
            ):
                with patch(
                    "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                    return_value="http://localhost/callback",
                ):
                    with patch(
                        "src.kene_api.routers.oauth_integrations.get_firestore_service"
                    ) as mock_fs:
                        mock_db = Mock()
                        mock_fs.return_value.get_client.return_value = mock_db

                        mock_state_service = AsyncMock()
                        with patch(
                            "src.kene_api.routers.oauth_integrations.OAuthStateService",
                            return_value=mock_state_service,
                        ):
                            result = await authorize_google_analytics(
                                account_id="acc123",
                                current_user=account_editor_user,
                            )

                            # Should succeed for editor
                            assert "auth_url" in result

    @pytest.mark.asyncio
    async def test_viewer_cannot_authorize(self, viewer_user):
        """Viewers should not be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with pytest.raises(HTTPException) as exc_info:
            await authorize_google_analytics(
                account_id="acc123",
                current_user=viewer_user,
            )

        assert exc_info.value.status_code == 403
        assert "permission" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_no_access_user_cannot_authorize(self, no_access_user):
        """Users with no permissions should not be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with pytest.raises(HTTPException) as exc_info:
            await authorize_google_analytics(
                account_id="acc123",
                current_user=no_access_user,
            )

        assert exc_info.value.status_code == 403


class TestOAuthDisconnectPermissions:
    """Test permission checks for OAuth disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_org_admin_can_disconnect(self, org_admin_user):
        """Organization admins should be able to disconnect OAuth."""
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_db = Mock()
            mock_fs.return_value.get_client.return_value = mock_db

            mock_creds_service = AsyncMock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                result = await disconnect_google_analytics(
                    account_id="acc123",
                    current_user=org_admin_user,
                )

                assert result["message"] == "Google Analytics disconnected successfully"
                mock_creds_service.delete_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_viewer_cannot_disconnect(self, viewer_user):
        """Viewers should not be able to disconnect OAuth."""
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with pytest.raises(HTTPException) as exc_info:
            await disconnect_google_analytics(
                account_id="acc123",
                current_user=viewer_user,
            )

        assert exc_info.value.status_code == 403


class TestOAuthPropertiesPermissions:
    """Test permission checks for properties endpoint."""

    @pytest.mark.asyncio
    async def test_org_admin_can_view_properties(self, org_admin_user):
        """Organization admins should be able to view properties."""
        from src.kene_api.routers.oauth_integrations import (
            get_google_analytics_properties,
        )

        # Should not raise 403 - will fail later due to no credentials, but that's expected
        with patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_db = Mock()
            mock_fs.return_value.get_client.return_value = mock_db

            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None

            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_google_analytics_properties(
                        account_id="acc123",
                        current_user=org_admin_user,
                    )

                # Should fail with 404 (no credentials), not 403 (no permission)
                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_viewer_can_view_properties(self, viewer_user):
        """Viewers should be able to view (read-only) properties."""
        from src.kene_api.routers.oauth_integrations import (
            get_google_analytics_properties,
        )

        with patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_db = Mock()
            mock_fs.return_value.get_client.return_value = mock_db

            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None

            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_google_analytics_properties(
                        account_id="acc123",
                        current_user=viewer_user,
                    )

                # Should fail with 404 (no credentials), not 403 (no permission)
                assert exc_info.value.status_code == 404


class TestUserContextPermissionLogic:
    """Test UserContext.has_account_access() logic."""

    def test_super_admin_has_access_to_any_account(self, super_admin_user):
        """Super admins should have access to any account."""
        assert super_admin_user.has_account_access("any_account_id")
        assert super_admin_user.has_account_access(
            "any_account_id", required_roles=["edit"]
        )

    def test_org_admin_has_access_to_any_account(self, org_admin_user):
        """Organization admins should have access to any account."""
        # Org admin has admin role in org123
        assert org_admin_user.has_account_access("any_account_id")
        assert org_admin_user.has_account_access("different_account")

    def test_account_editor_has_access_to_their_account(self, account_editor_user):
        """Users with edit permission should have access to their account."""
        assert account_editor_user.has_account_access("acc123")
        assert account_editor_user.has_account_access("acc123", required_roles=["edit"])

    def test_account_editor_no_access_to_other_accounts(self, account_editor_user):
        """Users should not have access to accounts they don't have permissions for."""
        assert not account_editor_user.has_account_access("other_account")

    def test_viewer_has_view_access_only(self, viewer_user):
        """Viewers should have view access but not edit."""
        assert viewer_user.has_account_access("acc123")
        assert viewer_user.has_account_access("acc123", required_roles=["view"])
        # Should not have edit access
        assert not viewer_user.has_account_access("acc123", required_roles=["edit"])

    def test_no_access_user_cannot_access(self, no_access_user):
        """Users with no permissions should not have access."""
        assert not no_access_user.has_account_access("acc123")
