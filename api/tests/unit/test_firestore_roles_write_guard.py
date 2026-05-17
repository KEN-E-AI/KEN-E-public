"""Write-path hardening for the generic Firestore documents endpoint.

On a `users/{uid}` doc, `roles` carries super-admin and `permissions` carries
org-admin / account-edit grants — both read straight into `UserContext`. The
generic `/firestore/documents` create/update endpoints (unauthenticated; root
fix tracked in DM-82) must never let a client set either, or the DM-80/DM-81
escalation surface stays open. These tests pin `_reject_protected_user_field_write`.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.kene_api.routers.firestore import _reject_protected_user_field_write


class TestRejectsRolesWritesOnUserDocs:
    """Any write that touches `roles` on a users/{uid} doc is refused."""

    def test_direct_top_level_roles_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write("users", {"roles": ["super_admin"]})

        assert exc.value.status_code == 403

    def test_direct_roles_alongside_other_fields_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users", {"profile": {"email": "a@b.com"}, "roles": ["super_admin"]}
            )

        assert exc.value.status_code == 403

    def test_array_union_on_roles_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {
                    "update": {
                        "operator": "arrayUnion",
                        "field": "roles",
                        "value": "super_admin",
                    }
                },
            )

        assert exc.value.status_code == 403

    def test_set_nested_roles_path_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {
                    "update": {
                        "operator": "set",
                        "field": "roles.0",
                        "value": "super_admin",
                    }
                },
            )

        assert exc.value.status_code == 403

    def test_replace_one_on_roles_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {
                    "update": {
                        "operator": "replaceOne",
                        "field": "roles",
                        "matchField": "x",
                        "matchValue": "y",
                        "value": "z",
                    }
                },
            )

        assert exc.value.status_code == 403


class TestRejectsPermissionsWritesOnUserDocs:
    """`permissions` on a users/{uid} doc confers org-admin / account-edit."""

    def test_direct_top_level_permissions_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {"permissions": {"organizations": {"org1": "admin"}}},
            )

        assert exc.value.status_code == 403

    def test_set_nested_permissions_path_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {
                    "update": {
                        "operator": "set",
                        "field": "permissions.account_permissions.a1",
                        "value": "edit",
                    }
                },
            )

        assert exc.value.status_code == 403

    def test_set_nested_org_admin_path_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _reject_protected_user_field_write(
                "users",
                {
                    "update": {
                        "operator": "set",
                        "field": "permissions.organizations.org1",
                        "value": "admin",
                    }
                },
            )

        assert exc.value.status_code == 403


class TestAllowsLegitimateWrites:
    """The guard is narrow: only `roles` / `permissions` on `users/` is gated."""

    def test_profile_update_on_user_doc_allowed(self):
        _reject_protected_user_field_write("users", {"profile": {"email": "a@b.com"}})

    def test_preferences_and_metadata_on_user_doc_allowed(self):
        # Sign-up writes profile + preferences + metadata — none are gated.
        _reject_protected_user_field_write(
            "users",
            {"profile": {"email": "a@b.com"}, "preferences": {}, "metadata": {}},
        )

    def test_protected_fields_on_non_user_collection_allowed(self):
        # `roles` / `permissions` elsewhere are unrelated to user privileges.
        _reject_protected_user_field_write("accounts", {"roles": ["whatever"]})
        _reject_protected_user_field_write("accounts", {"permissions": {"x": 1}})


def _make_super_admin_mock():
    """Return a super-admin UserContext mock for dependency injection."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.user_id = "admin_uid"
    user.email = "admin@ken-e.ai"
    user.is_super_admin = True
    return user


def test_post_documents_endpoint_rejects_roles_on_users():
    """End-to-end: the field guard is wired into POST /firestore/documents.

    Auth is mocked with a super-admin so the request reaches the field guard
    (super-admin bypasses the scope check but the field guard is always enforced).
    """
    from src.kene_api.auth.dependencies import get_current_user
    from src.kene_api.main import app

    super_admin = _make_super_admin_mock()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/firestore/documents",
            json={
                "account_id": "a000001",
                "collection": "users",
                "document_id": "victim-uid",
                "data": {"roles": ["super_admin"]},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


def test_post_documents_endpoint_rejects_permissions_on_users():
    """End-to-end: the field guard also blocks the org-admin escalation vector.

    Auth is mocked with a super-admin so the request reaches the field guard.
    """
    from src.kene_api.auth.dependencies import get_current_user
    from src.kene_api.main import app

    super_admin = _make_super_admin_mock()
    app.dependency_overrides[get_current_user] = lambda: super_admin
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/firestore/documents",
            json={
                "account_id": "a000001",
                "collection": "users",
                "document_id": "victim-uid",
                "data": {"permissions": {"organizations": {"org1": "admin"}}},
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
