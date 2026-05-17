"""Tests for GET /api/v1/users/me — verifies is_super_admin propagation.

Covers the two cases introduced by DM-81 Phase 5:
  1. A super-admin (roles=[super_admin]) receives is_super_admin=true.
  2. A regular user (roles=[]) receives is_super_admin=false.
  3. A newly auto-created user (no doc) receives is_super_admin=false.
"""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.kene_api.auth.models import SUPER_ADMIN_ROLE, UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app


def _user_context(*, is_super: bool) -> UserContext:
    return UserContext(
        user_id="test-uid",
        email="test@example.com",
        organization_permissions={},
        account_permissions={},
        roles=[SUPER_ADMIN_ROLE] if is_super else [],
    )


def _make_firestore(*, doc_exists: bool, roles: list[str] | None = None):
    """Return a mock FirestoreService."""
    user_doc = mock.Mock()
    user_doc.exists = doc_exists
    user_doc.to_dict.return_value = {
        "uid": "test-uid",
        "email": "test@example.com",
        "profile": {"email": "test@example.com"},
        "permissions": {"accounts": {}, "organizations": {}},
        "roles": roles or [],
    }
    ref = mock.Mock()
    ref.get.return_value = user_doc
    # Support nested .collection().document().set() calls for new-user creation
    sub_ref = mock.Mock()
    sub_ref.document.return_value.set = mock.Mock()
    ref.collection.return_value = sub_ref

    firestore_client = mock.Mock()
    firestore_client.collection.return_value.document.return_value = ref

    service = mock.Mock()
    service.get_client.return_value = firestore_client
    return service


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Reset dependency overrides between tests."""
    yield
    app.dependency_overrides.pop(get_current_user_context, None)
    app.dependency_overrides.pop(get_firestore_service, None)


class TestGetCurrentUserIsSuperAdmin:
    """GET /api/v1/users/me — is_super_admin field tests."""

    def test_super_admin_user_returns_is_super_admin_true(self):
        ctx = _user_context(is_super=True)
        fs = _make_firestore(doc_exists=True, roles=[SUPER_ADMIN_ROLE])
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        app.dependency_overrides[get_firestore_service] = lambda: fs

        resp = TestClient(app).get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer test-token"},
        )

        assert resp.status_code == 200
        assert resp.json()["is_super_admin"] is True

    def test_regular_user_returns_is_super_admin_false(self):
        ctx = _user_context(is_super=False)
        fs = _make_firestore(doc_exists=True, roles=[])
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        app.dependency_overrides[get_firestore_service] = lambda: fs

        resp = TestClient(app).get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer test-token"},
        )

        assert resp.status_code == 200
        assert resp.json()["is_super_admin"] is False

    def test_new_user_creation_branch_returns_is_super_admin_false(self):
        """A newly auto-created user has no roles, so is_super_admin=false."""
        ctx = _user_context(is_super=False)
        fs = _make_firestore(doc_exists=False)
        app.dependency_overrides[get_current_user_context] = lambda: ctx
        app.dependency_overrides[get_firestore_service] = lambda: fs

        resp = TestClient(app).get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer test-token"},
        )

        assert resp.status_code == 200
        assert resp.json()["is_super_admin"] is False
