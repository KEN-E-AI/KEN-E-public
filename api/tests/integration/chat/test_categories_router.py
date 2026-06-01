"""Integration tests for category CRUD endpoints (CH-35).

Verifies the four endpoints against a real Firestore emulator:
- GET    /api/v1/chat/categories
- POST   /api/v1/chat/categories
- DELETE /api/v1/chat/categories/{category_id}
- PUT    /api/v1/chat/conversations/{session_id}/category

References: CH-PRD-03 §7 AC-POST/DELETE/GET/PUT, §5.4 (security).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_categories_router.py -v
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Constants — must match what the overridden UserContext returns
# ---------------------------------------------------------------------------

_USER_ID = "cat-router-test-user"
_ACCOUNT_ID = "cat_router_account"
_ORG_ID = "org_cat_router_test"
_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _set_flag(db: Any, key: str, *, default_enabled: bool) -> None:
    db.collection("feature_flags").document(key).set(
        {
            "key": key,
            "description": f"test flag {key}",
            "default_enabled": default_enabled,
            "is_active": True,
            "targeting_rules": {
                "user_emails": [],
                "email_domains": [],
                "organization_ids": [],
                "account_ids": [],
                "rollout_percentage": 0,
            },
            "bucketing_entity": "account",
            "owner": "test@ken-e.ai",
            "created_at": _NOW.isoformat(),
            "updated_at": _NOW.isoformat(),
        }
    )


def _delete_flag(db: Any, key: str) -> None:
    db.collection("feature_flags").document(key).delete()


def _seed_session(db: Any, session_id: str, *, category_id: str | None = None) -> None:
    from src.kene_api.models.chat import ChatSessionMetadata

    metadata = ChatSessionMetadata(
        session_id=session_id,
        user_id=_USER_ID,
        account_id=_ACCOUNT_ID,
        organization_id=_ORG_ID,
        model_id="gemini-2.5-flash",
        category_id=category_id,
        search_text="",
        created_at=_NOW,
        updated_at=_NOW,
        deleted_at=None,
    )
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}").set(
        metadata.model_dump()
    )


def _clear_caches() -> None:
    from src.kene_api.chat.categories import get_chat_category_service
    from src.kene_api.dependencies import get_firestore_client
    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_firestore_client.cache_clear()
    get_chat_category_service.cache_clear()
    get_feature_flag_service.cache_clear()


def _purge_user_categories(db: Any) -> None:
    for doc in db.collection(f"users/{_USER_ID}/chat_categories").stream():
        doc.reference.delete()


def _purge_user_sessions(db: Any) -> None:
    for doc in (
        db.collection_group("chat_sessions").where("user_id", "==", _USER_ID).stream()
    ):
        doc.reference.delete()


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    _clear_caches()

    from src.kene_api.auth.models import UserContext
    from src.kene_api.auth.user_context import get_current_user_context
    from src.kene_api.main import app

    mock_user = UserContext(
        user_id=_USER_ID,
        email="cat-test@example.com",
        organization_permissions={},
        account_permissions={_ACCOUNT_ID: "edit"},
    )
    app.dependency_overrides[get_current_user_context] = lambda: mock_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_current_user_context, None)


@pytest.fixture(autouse=True)
def _reset_emulator_state() -> Generator[None, None, None]:
    db = _emulator_client()
    # Both flags must be on for the category endpoints to respond — the
    # categories flag depends on the master chat_v2_enabled (per api/CLAUDE.md
    # + the _require_categories_enabled enforcement added in this PR).
    _set_flag(db, "chat_v2_enabled", default_enabled=True)
    _set_flag(db, "chat_categories_enabled", default_enabled=True)
    # Reset module-level rate-limiter state per test so cumulative POST/PUT
    # counts across tests don't exhaust the 20/hr POST cap or 60/min PUT cap.
    from src.kene_api.chat.category_assign_limiter import category_assign_limiter
    from src.kene_api.chat.category_user_limiter import category_user_limiter

    category_user_limiter._buckets.clear()
    category_assign_limiter._buckets.clear()
    _clear_caches()

    yield

    _purge_user_categories(db)
    _purge_user_sessions(db)
    _delete_flag(db, "chat_categories_enabled")
    _delete_flag(db, "chat_v2_enabled")
    _clear_caches()


# ---------------------------------------------------------------------------
# TestListCategories — GET /api/v1/chat/categories
# ---------------------------------------------------------------------------


class TestListCategories:
    def test_returns_empty_list_when_no_categories(self, client: TestClient) -> None:
        resp = client.get("/api/v1/chat/categories")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_created_categories_sorted_by_name(self, client: TestClient) -> None:
        client.post("/api/v1/chat/categories", json={"name": "Zebra"})
        client.post("/api/v1/chat/categories", json={"name": "Apple"})
        client.post("/api/v1/chat/categories", json={"name": "Mango"})

        resp = client.get("/api/v1/chat/categories")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert names == ["Apple", "Mango", "Zebra"]

    def test_wire_shape_has_four_fields(self, client: TestClient) -> None:
        client.post("/api/v1/chat/categories", json={"name": "Shape Test"})
        resp = client.get("/api/v1/chat/categories")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        item = items[0]
        assert set(item.keys()) == {"category_id", "name", "created_at", "updated_at"}

    def test_returns_404_when_flag_off(self, client: TestClient) -> None:
        db = _emulator_client()
        _set_flag(db, "chat_categories_enabled", default_enabled=False)
        _clear_caches()

        resp = client.get("/api/v1/chat/categories")
        assert resp.status_code == 404

    def test_returns_404_when_chat_v2_master_flag_off(
        self, client: TestClient
    ) -> None:
        """The master `chat_v2_enabled` kill switch must close every category
        endpoint — even when `chat_categories_enabled` is on. Per api/CLAUDE.md
        the categories flag depends on the master flag, and the runbook for
        killing chat in prod expects this enforcement."""
        db = _emulator_client()
        _set_flag(db, "chat_v2_enabled", default_enabled=False)
        _set_flag(db, "chat_categories_enabled", default_enabled=True)
        _clear_caches()

        resp = client.get("/api/v1/chat/categories")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestCreateCategory — POST /api/v1/chat/categories
# ---------------------------------------------------------------------------


class TestCreateCategory:
    def test_create_returns_201_with_public_shape(self, client: TestClient) -> None:
        resp = client.post("/api/v1/chat/categories", json={"name": "Work"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Work"
        assert set(body.keys()) == {"category_id", "name", "created_at", "updated_at"}

    def test_create_duplicate_casefold_returns_409(self, client: TestClient) -> None:
        client.post("/api/v1/chat/categories", json={"name": "Work"})
        resp = client.post("/api/v1/chat/categories", json={"name": "work"})
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["error"] == "category_exists"
        assert "existing_category_id" in detail

    def test_create_whitespace_only_name_returns_400(self, client: TestClient) -> None:
        # Whitespace-only strings pass Pydantic's min_length=1 but fail the service
        # strip check, which raises ValueError → 400 (not 422).
        resp = client.post("/api/v1/chat/categories", json={"name": "   "})
        assert resp.status_code == 400

    def test_create_returns_404_when_flag_off(self, client: TestClient) -> None:
        db = _emulator_client()
        _set_flag(db, "chat_categories_enabled", default_enabled=False)
        _clear_caches()

        resp = client.post("/api/v1/chat/categories", json={"name": "Test"})
        assert resp.status_code == 404

    def test_category_id_is_stable(self, client: TestClient) -> None:
        """Two creates with the same casefold yield the same category_id (deterministic)."""
        r1 = client.post("/api/v1/chat/categories", json={"name": "Stable"})
        cid = r1.json()["category_id"]
        # Second call with same-casefolded name returns 409 with the same id
        r2 = client.post("/api/v1/chat/categories", json={"name": "STABLE"})
        assert r2.status_code == 409
        assert r2.json()["detail"]["existing_category_id"] == cid


# ---------------------------------------------------------------------------
# TestDeleteCategory — DELETE /api/v1/chat/categories/{category_id}
# ---------------------------------------------------------------------------


class TestDeleteCategory:
    def test_delete_returns_200_with_sessions_reassigned(self, client: TestClient) -> None:
        r = client.post("/api/v1/chat/categories", json={"name": "ToDelete"})
        cid = r.json()["category_id"]

        resp = client.delete(f"/api/v1/chat/categories/{cid}")
        assert resp.status_code == 200
        body = resp.json()
        assert "sessions_reassigned" in body
        assert body["sessions_reassigned"] == 0

    def test_delete_clears_sessions(self, client: TestClient) -> None:
        db = _emulator_client()
        r = client.post("/api/v1/chat/categories", json={"name": "ClearTest"})
        cid = r.json()["category_id"]

        _seed_session(db, "sess_clear_1", category_id=cid)
        _seed_session(db, "sess_clear_2", category_id=cid)

        resp = client.delete(f"/api/v1/chat/categories/{cid}")
        assert resp.status_code == 200
        assert resp.json()["sessions_reassigned"] == 2

        # Category no longer appears in list
        list_resp = client.get("/api/v1/chat/categories")
        ids = [c["category_id"] for c in list_resp.json()]
        assert cid not in ids

    def test_delete_nonexistent_category_returns_403(self, client: TestClient) -> None:
        # Ownership/existence check now raises PermissionError → 403 when the
        # category_id is not found under the caller's collection.
        resp = client.delete("/api/v1/chat/categories/cat_nonexistent000000000000")
        assert resp.status_code == 403

    def test_delete_returns_404_when_flag_off(self, client: TestClient) -> None:
        r = client.post("/api/v1/chat/categories", json={"name": "FlagOff"})
        cid = r.json()["category_id"]

        db = _emulator_client()
        _set_flag(db, "chat_categories_enabled", default_enabled=False)
        _clear_caches()

        resp = client.delete(f"/api/v1/chat/categories/{cid}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestAssignCategory — PUT /api/v1/chat/conversations/{session_id}/category
# ---------------------------------------------------------------------------


class TestAssignCategory:
    def test_assign_returns_200_with_session_and_category_id(
        self, client: TestClient
    ) -> None:
        db = _emulator_client()
        r = client.post("/api/v1/chat/categories", json={"name": "Assigned"})
        cid = r.json()["category_id"]
        _seed_session(db, "sess_assign_1")

        resp = client.put(
            "/api/v1/chat/conversations/sess_assign_1/category",
            json={"category_id": cid},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "sess_assign_1"
        assert body["category_id"] == cid

    def test_assign_none_clears_category(self, client: TestClient) -> None:
        db = _emulator_client()
        r = client.post("/api/v1/chat/categories", json={"name": "ToClear"})
        cid = r.json()["category_id"]
        _seed_session(db, "sess_assign_clear", category_id=cid)

        resp = client.put(
            "/api/v1/chat/conversations/sess_assign_clear/category",
            json={"category_id": None},
        )
        assert resp.status_code == 200
        assert resp.json()["category_id"] is None

    def test_assign_limiter_key_includes_user_id(self, client: TestClient) -> None:
        """Regression guard: the per-session rate-limit key must include the
        authenticated user_id, not just the path-param session_id. Pre-fix, an
        attacker who guessed a victim's session_id could flood the endpoint
        and exhaust the victim's 60/min bucket (cross-user 429 DoS)."""
        from unittest.mock import patch

        db = _emulator_client()
        r = client.post("/api/v1/chat/categories", json={"name": "KeyCheck"})
        cid = r.json()["category_id"]
        _seed_session(db, "sess_key_check")

        with patch(
            "src.kene_api.routers.chat.category_assign_limiter.check"
        ) as mock_check:
            client.put(
                "/api/v1/chat/conversations/sess_key_check/category",
                json={"category_id": cid},
            )

        mock_check.assert_called_once()
        (key,), _ = mock_check.call_args
        assert key == f"{_USER_ID}:sess_key_check", (
            f"limiter key must be '<user_id>:<session_id>', got {key!r}"
        )

    def test_assign_to_unowned_session_returns_403(self, client: TestClient) -> None:
        # Session owned by a different user
        db = _emulator_client()
        from src.kene_api.models.chat import ChatSessionMetadata

        other_meta = ChatSessionMetadata(
            session_id="sess_other_user",
            user_id="other-user-999",
            account_id=_ACCOUNT_ID,
            organization_id=_ORG_ID,
            model_id="gemini-2.5-flash",
            search_text="",
            created_at=_NOW,
            updated_at=_NOW,
            deleted_at=None,
        )
        db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_other_user"
        ).set(other_meta.model_dump())

        r = client.post("/api/v1/chat/categories", json={"name": "OtherUser"})
        cid = r.json()["category_id"]

        resp = client.put(
            "/api/v1/chat/conversations/sess_other_user/category",
            json={"category_id": cid},
        )
        assert resp.status_code == 403

        # Cleanup
        db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_other_user").delete()

    def test_assign_nonexistent_session_returns_403(self, client: TestClient) -> None:
        r = client.post("/api/v1/chat/categories", json={"name": "Ghost"})
        cid = r.json()["category_id"]

        resp = client.put(
            "/api/v1/chat/conversations/sess_does_not_exist/category",
            json={"category_id": cid},
        )
        # 403 not 404 — no existence leak per AC-10 / §5.4
        assert resp.status_code == 403

    def test_assign_returns_404_when_flag_off(self, client: TestClient) -> None:
        db = _emulator_client()
        _set_flag(db, "chat_categories_enabled", default_enabled=False)
        _clear_caches()

        resp = client.put(
            "/api/v1/chat/conversations/sess_flag_off/category",
            json={"category_id": None},
        )
        assert resp.status_code == 404
