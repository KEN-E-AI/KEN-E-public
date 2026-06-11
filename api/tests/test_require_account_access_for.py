"""Tests for require_account_access_for — the cross-org-safe account gate."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_MODULE = "src.kene_api.auth.account_org"


@pytest.fixture
def super_admin():
    return UserContext(
        user_id="sa1",
        email="sa@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


@pytest.fixture
def org_a_admin():
    return UserContext(
        user_id="oa1",
        email="admin@org-a.com",
        organization_permissions={"org_A": "admin"},
        account_permissions={},
    )


@pytest.fixture
def account_viewer():
    return UserContext(
        user_id="v1",
        email="viewer@org-a.com",
        organization_permissions={},
        account_permissions={"acc_a": "view"},
    )


@pytest.fixture
def account_editor():
    return UserContext(
        user_id="e1",
        email="editor@org-a.com",
        organization_permissions={},
        account_permissions={"acc_a": "edit"},
    )


@pytest.fixture
def no_access_user():
    return UserContext(
        user_id="n1",
        email="nobody@example.com",
        organization_permissions={},
        account_permissions={},
    )


class TestRequireAccountAccessFor:
    """Unit tests for require_account_access_for."""

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_resolver(self, super_admin):
        """Super-admin short-circuits before the resolver is called."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(
            f"{_MODULE}.resolve_owning_organization_id",
            AsyncMock(side_effect=AssertionError("resolver must not be called")),
        ):
            result = await require_account_access_for(super_admin, "any_account", "edit")

        assert result is None

    @pytest.mark.asyncio
    async def test_org_admin_of_owning_org_granted(self, org_a_admin):
        """Admin of the account's owning org is allowed."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_A")):
            result = await require_account_access_for(org_a_admin, "acc_a", "edit")

        assert result is None

    @pytest.mark.asyncio
    async def test_org_admin_of_different_org_denied(self, org_a_admin):
        """Admin of org_A is denied when account belongs to org_B (cross-org IDOR)."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await require_account_access_for(org_a_admin, "acc_b", "view")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Account not found"

    @pytest.mark.asyncio
    async def test_resolver_miss_raises_404(self, org_a_admin):
        """Resolver returning None (account not found) raises 404."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await require_account_access_for(org_a_admin, "acc_unknown", "view")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_view_level_granted_for_viewer(self, account_viewer):
        """Explicit view permission grants view-level access."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_A")):
            # viewer has explicit account permission; org resolution not needed for account_permissions path
            # but resolver still runs (not super-admin); org must match or account_perm must exist
            result = await require_account_access_for(account_viewer, "acc_a", "view")

        assert result is None

    @pytest.mark.asyncio
    async def test_view_level_denied_for_viewer_on_edit(self, account_viewer):
        """View-only permission is denied when edit level is required."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_X")):
            with pytest.raises(HTTPException) as exc_info:
                await require_account_access_for(account_viewer, "acc_a", "edit")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_level_granted_for_editor(self, account_editor):
        """Explicit edit permission grants edit-level access."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_X")):
            result = await require_account_access_for(account_editor, "acc_a", "edit")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_access_user_denied(self, no_access_user):
        """User with no permissions is denied."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_A")):
            with pytest.raises(HTTPException) as exc_info:
                await require_account_access_for(no_access_user, "acc_a", "view")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_default_required_level_is_view(self, org_a_admin):
        """Default required_level is 'view'."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(f"{_MODULE}.resolve_owning_organization_id", AsyncMock(return_value="org_A")):
            result = await require_account_access_for(org_a_admin, "acc_a")

        assert result is None
