"""Cross-org isolation tests for routers/agent_configs.py.

Tests use the shared guard directly to avoid fighting with Firestore mock wiring
in the router functions (the auth check fires before any DB call, so testing the
guard is sufficient to verify the cross-org isolation).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"


@pytest.fixture
def super_admin():
    return UserContext(
        user_id="sa1", email="sa@ken-e.ai",
        organization_permissions={}, account_permissions={}, roles=["super_admin"],
    )


@pytest.fixture
def org_a_admin():
    return UserContext(
        user_id="oa1", email="admin@org-a.com",
        organization_permissions={"org_A": "admin"}, account_permissions={},
    )


class TestAgentConfigsCrossOrgIsolation:
    """Org-A admin must be denied on org-B accounts for all agent_configs endpoints."""

    @pytest.mark.asyncio
    async def test_list_configs_cross_org_denied_via_router(self, org_a_admin):
        """list_account_agent_configs endpoint cross-org → 404 (tests actual wiring)."""
        from unittest.mock import MagicMock

        from src.kene_api.routers.agent_configs import list_account_agent_configs

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = []

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await list_account_agent_configs(
                    account_id="acc_org_b_xyz",
                    visible_in_frontend=False,
                    user=org_a_admin,
                    db=mock_db,
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_view_cross_org_denied(self, org_a_admin):
        """list / get endpoints use view level → org-B account → 404."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await require_account_access_for(org_a_admin, "acc_org_b", "view")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_cross_org_denied(self, org_a_admin):
        """create / upsert / delete use edit level (admin-mapped) → org-B account → 404."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await require_account_access_for(org_a_admin, "acc_org_b", "edit")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_resolver(self, super_admin):
        """Super-admin bypasses resolver for both view and edit levels."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            assert await require_account_access_for(super_admin, "acc_org_b", "view") is None
            assert await require_account_access_for(super_admin, "acc_org_b", "edit") is None

    @pytest.mark.asyncio
    async def test_own_org_account_allowed(self, org_a_admin):
        """Org-A admin can access org-A account."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await require_account_access_for(org_a_admin, "acc_org_a", "edit")
        assert result is None
