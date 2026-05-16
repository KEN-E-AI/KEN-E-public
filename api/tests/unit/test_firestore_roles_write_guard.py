"""Write-path hardening for the generic Firestore documents endpoint.

`roles` on `users/{uid}` carries super-admin. The generic
`/firestore/documents` create/update endpoints must never let a client set it
— doing so would rebuild the DM-80 privilege-escalation hole. These tests pin
`_reject_protected_user_field_write` (DM-81 Phase 2).
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


class TestAllowsLegitimateWrites:
    """The guard is narrow: only `roles` on `users/` is gated."""

    def test_profile_update_on_user_doc_allowed(self):
        _reject_protected_user_field_write("users", {"profile": {"email": "a@b.com"}})

    def test_permissions_set_on_user_doc_allowed(self):
        # Only `roles` is gated; the existing permissions structure is untouched.
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

    def test_roles_on_non_user_collection_allowed(self):
        # `roles` on another collection is unrelated to super-admin — not gated.
        _reject_protected_user_field_write("accounts", {"roles": ["whatever"]})


def test_post_documents_endpoint_rejects_roles_on_users():
    """End-to-end: the guard is wired into POST /firestore/documents."""
    from src.kene_api.main import app

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

    assert response.status_code == 403
