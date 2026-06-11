"""Tests for the check_account_access FastAPI dependency (user_context.py)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_GUARD = "src.kene_api.auth.account_org.require_account_access_for"
_AUDIT = "src.kene_api.auth.user_context.get_audit_logger"


@pytest.fixture
def org_a_admin():
    return UserContext(
        user_id="oa1",
        email="admin@org-a.com",
        organization_permissions={"org_A": "admin"},
        account_permissions={},
    )


@pytest.fixture
def super_admin():
    return UserContext(
        user_id="sa1",
        email="sa@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


class TestCheckAccountAccess:
    """Tests for check_account_access dependency."""

    @pytest.mark.asyncio
    async def test_allowed_returns_user(self, org_a_admin):
        """When the guard passes, check_account_access returns the user."""
        from src.kene_api.auth.user_context import check_account_access

        with patch(_GUARD, AsyncMock(return_value=None)):
            result = await check_account_access(account_id="acc_a", user=org_a_admin)

        assert result is org_a_admin

    @pytest.mark.asyncio
    async def test_denied_raises_404_and_audits(self, org_a_admin):
        """When the guard raises 404, check_account_access re-raises and logs."""
        from src.kene_api.auth.user_context import check_account_access

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_access_denied = AsyncMock()

        with patch(_GUARD, AsyncMock(side_effect=HTTPException(status_code=404, detail="Account not found"))):
            with patch(_AUDIT, return_value=mock_audit_logger):
                with pytest.raises(HTTPException) as exc_info:
                    await check_account_access(account_id="acc_b", user=org_a_admin)

        assert exc_info.value.status_code == 404
        mock_audit_logger.log_access_denied.assert_called_once()

    @pytest.mark.asyncio
    async def test_cross_org_denied(self, org_a_admin):
        """Org-A admin cannot access org-B account — integration through real guard."""
        from src.kene_api.auth.user_context import check_account_access

        _RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"
        mock_audit_logger = MagicMock()
        mock_audit_logger.log_access_denied = AsyncMock()

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with patch(_AUDIT, return_value=mock_audit_logger):
                with pytest.raises(HTTPException) as exc_info:
                    await check_account_access(account_id="acc_b", user=org_a_admin)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_allowed(self, super_admin):
        """Super-admin bypasses the guard."""
        from src.kene_api.auth.user_context import check_account_access

        _RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"
        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("resolver must not be called"))):
            result = await check_account_access(account_id="any_acc", user=super_admin)

        assert result is super_admin

    @pytest.mark.asyncio
    async def test_backend_unavailable_raises_503_without_audit(self, org_a_admin):
        """503 (backend unavailable) re-raises without writing an access-denied audit."""
        from src.kene_api.auth.user_context import check_account_access

        mock_audit_logger = MagicMock()
        mock_audit_logger.log_access_denied = AsyncMock()

        with patch(_GUARD, AsyncMock(side_effect=HTTPException(status_code=503, detail="Authorization backend unavailable"))):
            with patch(_AUDIT, return_value=mock_audit_logger):
                with pytest.raises(HTTPException) as exc_info:
                    await check_account_access(account_id="acc_a", user=org_a_admin)

        assert exc_info.value.status_code == 503
        mock_audit_logger.log_access_denied.assert_not_called()
