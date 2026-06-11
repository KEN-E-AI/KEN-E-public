"""Cross-org isolation tests for routers/strategy.py."""

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


class TestStrategyCrossOrgIsolation:
    """check_strategy_access must deny org-A admin on org-B accounts."""

    @pytest.mark.asyncio
    async def test_view_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await check_strategy_access("acc_org_b", org_a_admin, "view")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_edit_cross_org_denied(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await check_strategy_access("acc_org_b", org_a_admin, "edit")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_always_allowed(self, super_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await check_strategy_access("any_acc", super_admin, "edit")
        assert result is super_admin

    @pytest.mark.asyncio
    async def test_own_org_account_allowed(self, org_a_admin):
        from src.kene_api.routers.strategy import check_strategy_access

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await check_strategy_access("acc_org_a", org_a_admin, "view")
        assert result is org_a_admin
