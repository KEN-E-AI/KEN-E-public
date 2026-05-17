"""Tests for the super-admin admin endpoints (DM-81 Phase 2).

Covers grant / revoke / list, the last-admin guard, idempotency, cache
invalidation, audit logging, and the require_super_admin gate (403 for
non-super-admins).
"""

from contextlib import contextmanager
from unittest import mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from src.kene_api.auth.audit_logger import SecurityEventType
from src.kene_api.auth.models import SUPER_ADMIN_ROLE, UserContext
from src.kene_api.routers.admin import (
    GrantSuperAdminRequest,
    grant_super_admin,
    list_super_admins,
    revoke_super_admin,
)


def _admin() -> UserContext:
    return UserContext(
        user_id="actor-uid",
        email="actor@example.com",
        organization_permissions={},
        account_permissions={},
        roles=[SUPER_ADMIN_ROLE],
    )


def _request() -> mock.Mock:
    request = mock.Mock()
    request.client = mock.Mock(host="127.0.0.1")
    request.headers = mock.Mock()
    request.headers.get = mock.Mock(return_value="TestAgent/1.0")
    return request


def _firestore(*, doc_exists=False, doc_roles=None, super_admin_docs=None):
    """Build a mock FirestoreService + the users/{uid} doc ref it hands out."""
    snapshot = mock.Mock()
    snapshot.exists = doc_exists
    snapshot.to_dict.return_value = (
        {"roles": list(doc_roles or [])} if doc_exists else None
    )
    user_ref = mock.Mock()
    user_ref.get.return_value = snapshot
    client = mock.Mock()
    client.collection.return_value.document.return_value = user_ref
    service = mock.Mock()
    service.get_client.return_value = client
    service.list_documents.return_value = list(super_admin_docs or [])
    return service, user_ref


@contextmanager
def _patched_side_effects():
    """Patch the audit logger + cache service; yield (audit, cache) mocks."""
    audit = mock.AsyncMock()
    cache = mock.Mock()
    with (
        mock.patch("src.kene_api.routers.admin.get_audit_logger", return_value=audit),
        mock.patch(
            "src.kene_api.routers.admin.get_cached_user_context_service",
            return_value=cache,
        ),
    ):
        yield audit, cache


class TestGrantRequestValidation:
    """GrantSuperAdminRequest requires exactly one identifier."""

    def test_rejects_both_uid_and_email(self):
        with pytest.raises(ValidationError):
            GrantSuperAdminRequest(uid="u1", email="a@b.com")

    def test_rejects_neither_identifier(self):
        with pytest.raises(ValidationError):
            GrantSuperAdminRequest()

    def test_accepts_uid_only(self):
        assert GrantSuperAdminRequest(uid="u1").uid == "u1"

    def test_accepts_email_only(self):
        assert GrantSuperAdminRequest(email="a@b.com").email == "a@b.com"


@pytest.mark.asyncio
class TestListSuperAdmins:
    async def test_lists_role_holders(self):
        service, _ = _firestore(
            super_admin_docs=[
                {"id": "u1", "profile": {"email": "a@ken-e.ai"}},
                {"id": "u2", "email": "b@example.com"},
            ]
        )

        result = await list_super_admins(_admin(), service)

        assert result.total == 2
        assert {e.uid for e in result.super_admins} == {"u1", "u2"}
        assert {e.email for e in result.super_admins} == {"a@ken-e.ai", "b@example.com"}

    async def test_empty_when_no_super_admins(self):
        service, _ = _firestore(super_admin_docs=[])

        result = await list_super_admins(_admin(), service)

        assert result.total == 0


@pytest.mark.asyncio
class TestGrantSuperAdmin:
    async def test_creates_skeleton_when_user_doc_missing(self):
        service, user_ref = _firestore(doc_exists=False)
        record = mock.Mock(uid="new-uid", email="new@example.com")

        with (
            mock.patch("src.kene_api.routers.admin.get_user", return_value=record),
            _patched_side_effects() as (audit, cache),
        ):
            result = await grant_super_admin(
                _request(), GrantSuperAdminRequest(uid="new-uid"), _admin(), service
            )

        assert result.uid == "new-uid"
        user_ref.set.assert_called_once()
        assert user_ref.set.call_args[0][0]["roles"] == [SUPER_ADMIN_ROLE]
        user_ref.update.assert_not_called()
        cache.invalidate_user_context.assert_called_once_with("new-uid")
        audit.log_event.assert_awaited_once()
        assert (
            audit.log_event.call_args.kwargs["event_type"]
            == SecurityEventType.SUPER_ADMIN_GRANTED
        )

    async def test_adds_role_when_doc_exists_without_it(self):
        service, user_ref = _firestore(doc_exists=True, doc_roles=[])
        record = mock.Mock(uid="u1", email="u1@example.com")

        with (
            mock.patch("src.kene_api.routers.admin.get_user", return_value=record),
            _patched_side_effects(),
        ):
            await grant_super_admin(
                _request(), GrantSuperAdminRequest(uid="u1"), _admin(), service
            )

        user_ref.update.assert_called_once()
        user_ref.set.assert_not_called()

    async def test_is_idempotent_when_already_super_admin(self):
        service, user_ref = _firestore(doc_exists=True, doc_roles=[SUPER_ADMIN_ROLE])
        record = mock.Mock(uid="u1", email="u1@example.com")

        with (
            mock.patch("src.kene_api.routers.admin.get_user", return_value=record),
            _patched_side_effects(),
        ):
            result = await grant_super_admin(
                _request(), GrantSuperAdminRequest(uid="u1"), _admin(), service
            )

        assert result.uid == "u1"
        user_ref.update.assert_not_called()
        user_ref.set.assert_not_called()

    async def test_by_email_resolves_uid_via_firebase(self):
        service, _ = _firestore(doc_exists=True, doc_roles=[])
        record = mock.Mock(uid="resolved-uid", email="staff@example.com")

        with (
            mock.patch(
                "src.kene_api.routers.admin.get_user_by_email", return_value=record
            ) as mock_by_email,
            _patched_side_effects(),
        ):
            result = await grant_super_admin(
                _request(),
                GrantSuperAdminRequest(email="staff@example.com"),
                _admin(),
                service,
            )

        mock_by_email.assert_called_once_with("staff@example.com")
        assert result.uid == "resolved-uid"

    async def test_unknown_uid_returns_404(self):
        service, _ = _firestore(doc_exists=False)

        with (
            mock.patch(
                "src.kene_api.routers.admin.get_user",
                side_effect=ValueError("User not found"),
            ),
            _patched_side_effects(),
        ):
            with pytest.raises(HTTPException) as exc:
                await grant_super_admin(
                    _request(), GrantSuperAdminRequest(uid="ghost"), _admin(), service
                )

        assert exc.value.status_code == 404


@pytest.mark.asyncio
class TestRevokeSuperAdmin:
    async def test_removes_role_when_not_the_last_admin(self):
        service, user_ref = _firestore(
            doc_exists=True,
            doc_roles=[SUPER_ADMIN_ROLE],
            super_admin_docs=[{"id": "u1"}, {"id": "u2"}],
        )

        with _patched_side_effects() as (audit, cache):
            result = await revoke_super_admin("u1", _request(), _admin(), service)

        assert result.success is True
        user_ref.update.assert_called_once()
        cache.invalidate_user_context.assert_called_once_with("u1")
        audit.log_event.assert_awaited_once()
        assert (
            audit.log_event.call_args.kwargs["event_type"]
            == SecurityEventType.SUPER_ADMIN_REVOKED
        )

    async def test_refuses_to_revoke_the_last_super_admin(self):
        service, user_ref = _firestore(super_admin_docs=[{"id": "u1"}])

        with _patched_side_effects():
            with pytest.raises(HTTPException) as exc:
                await revoke_super_admin("u1", _request(), _admin(), service)

        assert exc.value.status_code == 409
        user_ref.update.assert_not_called()

    async def test_revoking_a_non_super_admin_returns_404(self):
        service, user_ref = _firestore(super_admin_docs=[{"id": "u1"}, {"id": "u2"}])

        with _patched_side_effects():
            with pytest.raises(HTTPException) as exc:
                await revoke_super_admin("u99", _request(), _admin(), service)

        assert exc.value.status_code == 404
        user_ref.update.assert_not_called()


def test_endpoints_reject_non_super_admin_callers():
    """The require_super_admin gate returns 403 for an authenticated non-admin."""
    from src.kene_api.auth.dependencies import get_current_user
    from src.kene_api.main import app

    non_admin = UserContext(
        user_id="x",
        email="x@example.com",
        organization_permissions={},
        account_permissions={},
        roles=[],
    )
    app.dependency_overrides[get_current_user] = lambda: non_admin
    try:
        client = TestClient(app)
        assert client.get("/api/v1/admin/super-admins").status_code == 403
        assert (
            client.post("/api/v1/admin/super-admins", json={"uid": "u1"}).status_code
            == 403
        )
        assert client.delete("/api/v1/admin/super-admins/u1").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
