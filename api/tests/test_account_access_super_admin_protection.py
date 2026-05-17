"""DM-81 Phase 3: super admins are shielded from account-permission edits.

The grant/revoke account-access handlers refuse to touch a target who holds
the `super_admin` role. The shield is keyed on the role on the target's user
doc — not, as before, on an `@ken-e.ai` email string.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import SUPER_ADMIN_ROLE, UserContext
from src.kene_api.routers.accounts import (
    GrantAccountAccessRequest,
    grant_account_access,
    revoke_account_access,
)

ORG_ID = "org456"
ACCOUNT_ID = "acc789"


def _caller() -> UserContext:
    """An org admin — passes the grant/revoke authorization gate."""
    return UserContext(
        user_id="caller",
        email="admin@example.com",
        organization_permissions={ORG_ID: "admin"},
        account_permissions={},
    )


def _db() -> AsyncMock:
    db = AsyncMock()
    db.health_check = AsyncMock(return_value=True)
    db.execute_query = AsyncMock(return_value=[{"organization_id": ORG_ID}])
    return db


def _firestore(target_doc: dict) -> MagicMock:
    firestore = MagicMock()
    firestore.get_document = MagicMock(return_value=target_doc)
    firestore.set_nested_field = MagicMock(return_value=True)
    firestore.get_client = MagicMock()
    return firestore


@pytest.mark.asyncio
class TestGrantAccessSuperAdminProtection:
    async def test_super_admin_target_is_protected(self):
        target = {
            "profile": {"email": "staff@example.com"},
            "permissions": {"organizations": {ORG_ID: "view"}},
            "roles": [SUPER_ADMIN_ROLE],
        }

        with pytest.raises(HTTPException) as exc:
            await grant_account_access(
                ACCOUNT_ID,
                GrantAccountAccessRequest(user_id="target", access_level="view"),
                _caller(),
                _db(),
                _firestore(target),
            )

        assert exc.value.status_code == 403
        assert "KEN-E support team" in exc.value.detail

    async def test_non_super_admin_target_is_grantable(self):
        target = {
            "profile": {"email": "user@example.com"},
            "permissions": {"organizations": {ORG_ID: "view"}},
            "roles": [],
        }

        result = await grant_account_access(
            ACCOUNT_ID,
            GrantAccountAccessRequest(user_id="target", access_level="view"),
            _caller(),
            _db(),
            _firestore(target),
        )

        assert result.success is True


@pytest.mark.asyncio
class TestRevokeAccessSuperAdminProtection:
    async def test_super_admin_target_is_protected(self):
        target = {
            "profile": {"email": "staff@example.com"},
            "permissions": {"organizations": {}},
            "roles": [SUPER_ADMIN_ROLE],
        }

        with pytest.raises(HTTPException) as exc:
            await revoke_account_access(
                ACCOUNT_ID, "target", _caller(), _db(), _firestore(target)
            )

        assert exc.value.status_code == 403
        assert "KEN-E support team" in exc.value.detail

    async def test_non_super_admin_target_is_revocable(self):
        target = {
            "profile": {"email": "user@example.com"},
            "permissions": {"organizations": {}},
            "roles": [],
        }

        result = await revoke_account_access(
            ACCOUNT_ID, "target", _caller(), _db(), _firestore(target)
        )

        assert result.success is True
