"""Cross-org isolation tests for routers/usage.py (check_cost_access helper)."""

from unittest.mock import AsyncMock, patch

import pytest
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


class TestUsageCrossOrgIsolation:
    """check_cost_access must deny org-A admin on org-B accounts."""

    @pytest.mark.asyncio
    async def test_account_costs_cross_org_denied_via_router(self, org_a_admin):
        """get_account_costs endpoint cross-org → 404 (tests actual wiring)."""
        from fastapi import HTTPException

        from src.kene_api.routers.usage import get_account_costs

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await get_account_costs(
                    account_id="acc_org_b_xyz",
                    date_from=None,
                    date_to=None,
                    limit=10,
                    user=org_a_admin,
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_org_returns_false(self, org_a_admin):
        """check_cost_access returns False for org-A admin on org-B account."""
        from src.kene_api.routers.usage import check_cost_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            result = await check_cost_access(org_a_admin, account_id="acc_org_b")

        assert result is False

    @pytest.mark.asyncio
    async def test_own_org_returns_true(self, org_a_admin):
        """check_cost_access returns True for org-A admin on org-A account."""
        from src.kene_api.routers.usage import check_cost_access

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await check_cost_access(org_a_admin, account_id="acc_org_a")

        assert result is True

    @pytest.mark.asyncio
    async def test_super_admin_always_true(self, super_admin):
        """Super-admin always returns True (short-circuits)."""
        from src.kene_api.routers.usage import check_cost_access

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await check_cost_access(super_admin, account_id="any_acc")

        assert result is True

    @pytest.mark.asyncio
    async def test_own_user_costs_always_accessible(self, org_a_admin):
        """User can always view their own costs regardless of account."""
        from src.kene_api.routers.usage import check_cost_access

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await check_cost_access(org_a_admin, target_user_id=org_a_admin.user_id)

        assert result is True
