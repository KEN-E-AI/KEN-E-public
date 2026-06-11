"""Cross-org isolation tests for accounts.py GET endpoints.

Covers get_account and get_account_creation_status — the two endpoints that
were not migrated in IN-2 and still returned 403 on cross-org denial.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"
_NEO4J = "src.kene_api.routers.accounts.get_neo4j_service"


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
def no_access_user():
    return UserContext(
        user_id="n1",
        email="nobody@example.com",
        organization_permissions={},
        account_permissions={},
    )


_FULL_ACCOUNT = {
    "account_id": "acc_a",
    "account_name": "Test Account A",
    "organization_id": "org_A",
    "industry": "Technology",
    "status": "Active",
    "websites": ["https://example.com"],
    "timezone": "UTC",
}


def _mock_db(account_data: dict | None = None):
    """Return a minimal Neo4jService mock."""
    db = MagicMock()
    db.health_check = AsyncMock(return_value=True)
    if account_data is not None:
        db.execute_query = AsyncMock(return_value=[{"acc": account_data}])
    else:
        db.execute_query = AsyncMock(return_value=[{"acc": _FULL_ACCOUNT}])
    return db


class TestGetAccountCrossOrgIsolation:
    """get_account must return 404 (not 403) on cross-org denial."""

    @pytest.mark.asyncio
    async def test_cross_org_admin_denied_with_404(self, org_a_admin):
        """Org-A admin accessing an org-B account gets 404, not 403."""
        from src.kene_api.routers.accounts import get_account

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await get_account(
                    account_id="acc_b",
                    user=org_a_admin,
                    db=_mock_db(),
                )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Account not found"

    @pytest.mark.asyncio
    async def test_no_access_user_denied_with_404(self, no_access_user):
        """User with no permissions gets 404."""
        from src.kene_api.routers.accounts import get_account

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            with pytest.raises(HTTPException) as exc:
                await get_account(
                    account_id="acc_a",
                    user=no_access_user,
                    db=_mock_db(),
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_resolver_miss_denied_with_404(self, org_a_admin):
        """Resolver returning None (account not in graph) raises 404."""
        from src.kene_api.routers.accounts import get_account

        with patch(_RESOLVER, AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                await get_account(
                    account_id="acc_unknown",
                    user=org_a_admin,
                    db=_mock_db(),
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_owning_org_admin_allowed(self, org_a_admin):
        """Admin of the account's owning org is allowed through."""
        from src.kene_api.routers.accounts import get_account

        db = _mock_db()

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await get_account(
                account_id="acc_a",
                user=org_a_admin,
                db=db,
            )
        assert result.account_id == "acc_a"

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_resolver(self, super_admin):
        """Super-admin short-circuits: resolver is never called."""
        from src.kene_api.routers.accounts import get_account

        db = _mock_db()

        with patch(
            _RESOLVER,
            AsyncMock(side_effect=AssertionError("resolver must not be called")),
        ):
            result = await get_account(
                account_id="acc_a",
                user=super_admin,
                db=db,
            )
        assert result.account_id == "acc_a"

    @pytest.mark.asyncio
    async def test_neo4j_outage_returns_503(self, org_a_admin):
        """Neo4j outage during org resolution returns 503, not 404."""
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.accounts import get_account

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await get_account(
                    account_id="acc_a",
                    user=org_a_admin,
                    db=_mock_db(),
                )
        assert exc.value.status_code == 503


class TestGetAccountCreationStatusCrossOrgIsolation:
    """get_account_creation_status must return 404 (not 403) on cross-org denial."""

    @pytest.mark.asyncio
    async def test_cross_org_admin_denied_with_404(self, org_a_admin):
        """Org-A admin accessing an org-B account's creation status gets 404."""
        from src.kene_api.routers.accounts import get_account_creation_status

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc:
                await get_account_creation_status(
                    account_id="acc_b",
                    user=org_a_admin,
                    db=MagicMock(),
                )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Account not found"

    @pytest.mark.asyncio
    async def test_no_access_user_denied_with_404(self, no_access_user):
        """User with no permissions gets 404."""
        from src.kene_api.routers.accounts import get_account_creation_status

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            with pytest.raises(HTTPException) as exc:
                await get_account_creation_status(
                    account_id="acc_a",
                    user=no_access_user,
                    db=MagicMock(),
                )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_owning_org_admin_allowed(self, org_a_admin):
        """Admin of the account's owning org gets a valid creation status."""
        from src.kene_api.routers.accounts import get_account_creation_status

        db = MagicMock()
        db.execute_query = AsyncMock(
            return_value=[{"setup_status": "completed", "setup_completed_at": "2026-01-01T00:00:00Z"}]
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            result = await get_account_creation_status(
                account_id="acc_a",
                user=org_a_admin,
                db=db,
            )
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_resolver(self, super_admin):
        """Super-admin short-circuits: resolver is never called."""
        from src.kene_api.routers.accounts import get_account_creation_status

        db = MagicMock()
        db.execute_query = AsyncMock(
            return_value=[{"setup_status": "processing", "setup_completed_at": None}]
        )

        with patch(
            _RESOLVER,
            AsyncMock(side_effect=AssertionError("resolver must not be called")),
        ):
            result = await get_account_creation_status(
                account_id="acc_a",
                user=super_admin,
                db=db,
            )
        assert result.status == "processing"

    @pytest.mark.asyncio
    async def test_neo4j_outage_returns_503(self, org_a_admin):
        """Neo4j outage during org resolution returns 503, not 404."""
        from src.kene_api.auth.account_org import AuthBackendUnavailable
        from src.kene_api.routers.accounts import get_account_creation_status

        with patch(_RESOLVER, AsyncMock(side_effect=AuthBackendUnavailable("down"))):
            with pytest.raises(HTTPException) as exc:
                await get_account_creation_status(
                    account_id="acc_a",
                    user=org_a_admin,
                    db=MagicMock(),
                )
        assert exc.value.status_code == 503
