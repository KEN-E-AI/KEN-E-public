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
    """Create organization admin user for org123."""
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


# Patch where the resolver is used (imported name in the router module)
_RESOLVER = "src.kene_api.routers.oauth_integrations.resolve_owning_organization_id"


class TestOAuthAuthorizePermissions:
    """Test permission checks for OAuth authorization endpoint."""

    @pytest.mark.asyncio
    async def test_super_admin_can_authorize(self, super_admin_user):
        """Super admins should be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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
                                    current_user=super_admin_user,
                                )

                                assert "auth_url" in result
                                assert "accounts.google.com" in result["auth_url"]

    @pytest.mark.asyncio
    async def test_org_admin_can_authorize(self, org_admin_user):
        """Organization admins should be able to authorize OAuth for their own org's account."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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

                                assert "auth_url" in result

    @pytest.mark.asyncio
    async def test_account_editor_can_authorize(self, account_editor_user):
        """Users with explicit edit permission should be able to authorize OAuth."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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

                                assert "auth_url" in result

    @pytest.mark.asyncio
    async def test_viewer_cannot_authorize(self, viewer_user):
        """Viewers should not be able to authorize OAuth (returns 404 to prevent account enumeration)."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
            with pytest.raises(HTTPException) as exc_info:
                await authorize_google_analytics(
                    account_id="acc123",
                    current_user=viewer_user,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_access_user_cannot_authorize(self, no_access_user):
        """Users with no permissions should not be able to authorize OAuth (returns 404 to prevent account enumeration)."""
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
            with pytest.raises(HTTPException) as exc_info:
                await authorize_google_analytics(
                    account_id="acc123",
                    current_user=no_access_user,
                )

        assert exc_info.value.status_code == 404


class TestOAuthDisconnectPermissions:
    """Test permission checks for OAuth disconnect endpoint."""

    @pytest.mark.asyncio
    async def test_org_admin_can_disconnect(self, org_admin_user):
        """Organization admins should be able to disconnect OAuth for their own org's account."""
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
            with pytest.raises(HTTPException) as exc_info:
                await disconnect_google_analytics(
                    account_id="acc123",
                    current_user=viewer_user,
                )

        assert exc_info.value.status_code == 404


class TestOAuthPropertiesPermissions:
    """Test permission checks for properties endpoint."""

    @pytest.mark.asyncio
    async def test_org_admin_can_view_properties(self, org_admin_user):
        """Organization admins should be able to view properties for their own org's account."""
        from src.kene_api.routers.oauth_integrations import (
            get_google_analytics_properties,
        )

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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

        with patch(_RESOLVER, AsyncMock(return_value="org123")):
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
    """Test UserContext permission logic.

    has_account_access() is deprecated (IN-2); these tests verify it raises.
    Cross-org isolation is now tested in test_require_account_access_for.py.
    """

    def test_has_account_access_is_deprecated(self, org_admin_user):
        """has_account_access() raises NotImplementedError — it is unsafe (IN-2)."""
        with pytest.raises(NotImplementedError, match="has_account_access is unsafe"):
            org_admin_user.has_account_access("acc123")

    def test_org_admin_has_no_implicit_cross_account_access(self, org_admin_user):
        """Org admin of org123 must not have access to an account owned by a different org."""
        # Admin of org123 → access to org123-owned account
        assert org_admin_user.has_account_permission(
            "acc123", organization_id="org123", required_level="edit"
        )
        # Admin of org123 → NO access to account owned by org_other
        assert not org_admin_user.has_account_permission(
            "acc123", organization_id="org_other", required_level="edit"
        )

    def test_account_editor_permission(self, account_editor_user):
        """Users with edit permission have edit + view via has_account_permission."""
        assert account_editor_user.has_account_permission("acc123", "any_org", "edit")
        assert account_editor_user.has_account_permission("acc123", "any_org", "view")
        assert not account_editor_user.has_account_permission("other_account", "any_org", "view")

    def test_viewer_permission(self, viewer_user):
        """Viewers have view but not edit via has_account_permission."""
        assert viewer_user.has_account_permission("acc123", "any_org", "view")
        assert not viewer_user.has_account_permission("acc123", "any_org", "edit")

    def test_no_access_user(self, no_access_user):
        """Users with no permissions denied."""
        assert not no_access_user.has_account_permission("acc123", "any_org", "view")


class TestOAuthCrossOrgIsolation:
    """Verify that org admins are denied on accounts belonging to a different org.

    For every GA OAuth endpoint: an admin of org_A must receive 403 when the
    account belongs to org_B. Super-admins must NOT be blocked (bypass preserved).
    """

    @pytest.fixture
    def org_a_admin(self):
        return UserContext(
            user_id="orgA_admin",
            email="admin@org-a.com",
            organization_permissions={"org_A": "admin"},
            account_permissions={},
        )

    @pytest.mark.asyncio
    async def test_authorize_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await authorize_google_analytics(
                    account_id="acc_org_b",
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_authorize_cross_org_super_admin_allowed(self, super_admin_user):
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_ID", "test_id"
            ), patch(
                "src.kene_api.routers.oauth_integrations.GOOGLE_CLIENT_SECRET",
                "test_secret",
            ), patch(
                "src.kene_api.routers.oauth_integrations.get_google_redirect_uri",
                return_value="http://localhost/callback",
            ), patch(
                "src.kene_api.routers.oauth_integrations.get_firestore_service"
            ) as mock_fs, patch(
                "src.kene_api.routers.oauth_integrations.OAuthStateService",
                return_value=AsyncMock(),
            ):
                mock_fs.return_value.get_client.return_value = Mock()
                result = await authorize_google_analytics(
                    account_id="acc_org_b",
                    current_user=super_admin_user,
                )
            assert "auth_url" in result

    @pytest.mark.asyncio
    async def test_refresh_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.oauth_integrations import (
            refresh_google_analytics_token,
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await refresh_google_analytics_token(
                    account_id="acc_org_b",
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_refresh_cross_org_super_admin_allowed(self, super_admin_user):
        from src.kene_api.routers.oauth_integrations import (
            refresh_google_analytics_token,
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")), patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None
            mock_fs.return_value.get_client.return_value = Mock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await refresh_google_analytics_token(
                        account_id="acc_org_b",
                        current_user=super_admin_user,
                    )
            # Fails with 404 (no refresh token), not from the auth check
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disconnect_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await disconnect_google_analytics(
                    account_id="acc_org_b",
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_disconnect_cross_org_super_admin_allowed(self, super_admin_user):
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with patch(_RESOLVER, AsyncMock(return_value="org_B")), patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_creds_service = AsyncMock()
            mock_fs.return_value.get_client.return_value = Mock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                result = await disconnect_google_analytics(
                    account_id="acc_org_b",
                    current_user=super_admin_user,
                )
            assert result["message"] == "Google Analytics disconnected successfully"

    @pytest.mark.asyncio
    async def test_get_properties_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.oauth_integrations import (
            get_google_analytics_properties,
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await get_google_analytics_properties(
                    account_id="acc_org_b",
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_properties_cross_org_super_admin_allowed(self, super_admin_user):
        from src.kene_api.routers.oauth_integrations import (
            get_google_analytics_properties,
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")), patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None
            mock_fs.return_value.get_client.return_value = Mock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await get_google_analytics_properties(
                        account_id="acc_org_b",
                        current_user=super_admin_user,
                    )
            # Fails with 404 (no credentials), not from the auth check
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_properties_cross_org_denied(self, org_a_admin):
        from src.kene_api.models.oauth_models import UpdateSelectedPropertiesRequest
        from src.kene_api.routers.oauth_integrations import update_selected_properties

        req = UpdateSelectedPropertiesRequest(property_ids=[], properties=[])

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await update_selected_properties(
                    account_id="acc_org_b",
                    request=req,
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_properties_cross_org_super_admin_allowed(
        self, super_admin_user
    ):
        from src.kene_api.models.oauth_models import UpdateSelectedPropertiesRequest
        from src.kene_api.routers.oauth_integrations import update_selected_properties

        req = UpdateSelectedPropertiesRequest(property_ids=[], properties=[])

        with patch(_RESOLVER, AsyncMock(return_value="org_B")), patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None
            mock_fs.return_value.get_client.return_value = Mock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                with pytest.raises(HTTPException) as exc_info:
                    await update_selected_properties(
                        account_id="acc_org_b",
                        request=req,
                        current_user=super_admin_user,
                    )
            # Fails with 404 (no GA connected), not from the auth check
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_status_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.oauth_integrations import get_google_analytics_status

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await get_google_analytics_status(
                    account_id="acc_org_b",
                    current_user=org_a_admin,
                )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_status_cross_org_super_admin_allowed(self, super_admin_user):
        from src.kene_api.routers.oauth_integrations import get_google_analytics_status

        with patch(_RESOLVER, AsyncMock(return_value="org_B")), patch(
            "src.kene_api.routers.oauth_integrations.get_firestore_service"
        ) as mock_fs:
            mock_creds_service = AsyncMock()
            mock_creds_service.get_credentials.return_value = None
            mock_fs.return_value.get_client.return_value = Mock()
            with patch(
                "src.kene_api.routers.oauth_integrations.IntegrationCredentialsService",
                return_value=mock_creds_service,
            ):
                result = await get_google_analytics_status(
                    account_id="acc_org_b",
                    current_user=super_admin_user,
                )
        # Super-admin bypasses auth → reaches business logic → not-configured response
        assert result.status.value == "not_configured"


class TestOAuthNeo4jOutage503:
    """Verify that all six OAuth GA endpoints return 503 when Neo4j is unavailable."""

    @pytest.fixture
    def any_user(self):
        return UserContext(
            user_id="u1",
            email="user@org-a.com",
            organization_permissions={"org_A": "admin"},
            account_permissions={},
        )

    @pytest.mark.asyncio
    async def test_authorize_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import authorize_google_analytics

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await authorize_google_analytics(account_id="acc_a", current_user=any_user)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_refresh_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import refresh_google_analytics_token

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await refresh_google_analytics_token(account_id="acc_a", current_user=any_user)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_disconnect_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import disconnect_google_analytics

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await disconnect_google_analytics(account_id="acc_a", current_user=any_user)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_properties_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import get_google_analytics_properties

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await get_google_analytics_properties(account_id="acc_a", current_user=any_user)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_update_properties_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import update_selected_properties

        update_req = Mock()
        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await update_selected_properties(
                    account_id="acc_a", request=update_req, current_user=any_user
                )
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_get_status_neo4j_outage_503(self, any_user):
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.oauth_integrations import get_google_analytics_status

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await get_google_analytics_status(account_id="acc_a", current_user=any_user)
        assert exc.value.status_code == 503
