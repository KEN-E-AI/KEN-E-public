"""Tests for the require_super_admin FastAPI dependency (DM-81 Phase 2)."""

import pytest
from fastapi import HTTPException
from src.kene_api.auth.dependencies import require_super_admin
from src.kene_api.auth.models import SUPER_ADMIN_ROLE, UserContext


def _user(roles: list[str]) -> UserContext:
    return UserContext(
        user_id="u1",
        email="staff@example.com",
        organization_permissions={},
        account_permissions={},
        roles=roles,
    )


@pytest.mark.asyncio
async def test_super_admin_passes_through():
    user = _user([SUPER_ADMIN_ROLE])

    assert await require_super_admin(user) is user


@pytest.mark.asyncio
async def test_user_without_role_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await require_super_admin(_user([]))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_unrelated_role_does_not_satisfy_the_gate():
    with pytest.raises(HTTPException) as exc:
        await require_super_admin(_user(["billing_admin"]))

    assert exc.value.status_code == 403
