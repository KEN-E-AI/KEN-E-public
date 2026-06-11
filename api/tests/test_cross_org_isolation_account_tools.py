"""Cross-org isolation tests for routers/account_tools.py."""

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


class TestAccountToolsCrossOrgIsolation:
    """Org-A admin must be denied on org-B accounts for account_tools endpoints."""

    @pytest.mark.asyncio
    async def test_cross_org_denied_via_router(self, org_a_admin):
        """list_account_tools endpoint cross-org → 404 (tests actual wiring)."""
        from unittest.mock import MagicMock

        from src.kene_api.routers.account_tools import list_account_tools

        mock_db = MagicMock()
        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await list_account_tools(
                    account_id="acc_org_b_long_enough",
                    user=org_a_admin,
                    db=mock_db,
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_org_denied(self, org_a_admin):
        """Tool inventory endpoint (view level) on org-B account → 404."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await require_account_access_for(org_a_admin, "acc_org_b", "view")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_resolver(self, super_admin):
        """Super-admin bypasses resolver."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await require_account_access_for(super_admin, "acc_org_b", "view")
        assert result is None

    @pytest.mark.asyncio
    async def test_own_org_account_allowed(self, org_a_admin):
        """Org-A admin can access org-A account."""
        from src.kene_api.auth.account_org import require_account_access_for

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await require_account_access_for(org_a_admin, "acc_org_a", "view")
        assert result is None
