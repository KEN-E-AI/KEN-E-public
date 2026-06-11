"""Tests for check_graph_access in crud_factory.py."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"


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
def account_editor():
    return UserContext(
        user_id="e1",
        email="editor@org-a.com",
        organization_permissions={},
        account_permissions={"acc_a": "edit"},
    )


class TestCheckGraphAccess:
    """Tests for check_graph_access."""

    @pytest.mark.asyncio
    async def test_super_admin_always_allowed(self, super_admin):
        """Super-admin is granted without consulting the resolver."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("resolver must not be called"))):
            result = await check_graph_access("any_acc", super_admin, "edit")

        assert result is super_admin

    @pytest.mark.asyncio
    async def test_org_admin_of_owning_org_allowed(self, org_a_admin):
        """Admin of the account's owning org is granted."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await check_graph_access("acc_a", org_a_admin, "edit")

        assert result is org_a_admin

    @pytest.mark.asyncio
    async def test_cross_org_denied(self, org_a_admin):
        """Org-A admin cannot access org-B account — no more any-org-admin bypass."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await check_graph_access("acc_b", org_a_admin, "view")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_account_editor_granted_edit(self, account_editor):
        """Explicit edit permission is granted for edit level."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        with patch(_RESOLVER, AsyncMock(return_value="org_X")):
            result = await check_graph_access("acc_a", account_editor, "edit")

        assert result is account_editor

    @pytest.mark.asyncio
    async def test_resolver_miss_raises_404(self, org_a_admin):
        """Account not found (resolver returns None) → 404."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        with patch(_RESOLVER, AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc_info:
                await check_graph_access("acc_unknown", org_a_admin, "view")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_access_user_denied(self):
        """User with no permissions is denied."""
        from src.kene_api.routers.knowledge_graph.crud_factory import check_graph_access

        no_access = UserContext(
            user_id="n1",
            email="nobody@example.com",
            organization_permissions={},
            account_permissions={},
        )
        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            with pytest.raises(HTTPException) as exc_info:
                await check_graph_access("acc_a", no_access, "view")

        assert exc_info.value.status_code == 404
