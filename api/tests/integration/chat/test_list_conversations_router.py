"""Integration tests: GET /api/v1/chat/conversations router layer (CH-14).

Verifies that the list_conversations endpoint honours:
- AC-10: 30-day window (row at 31d excluded, row at 29d included)
- AC-11: deleted_at=non-null sessions never appear
- AC-5 : category filter narrows to matching rows
- AC-4 : case-insensitive substring search via search_text

These tests exercise the full HTTP stack against a real Firestore emulator.
Firebase token verification is intercepted by the session-scoped
``mock_firebase_auth`` fixture in ``tests/conftest.py``, which returns
``user_id="test-user-123"`` and ``account_permissions={"test_account": "edit"}``.
All sessions in this file therefore use ``account_id="test_account"``.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_list_conversations_router.py -v
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
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
# Constants — must match what mock_firebase_auth returns
# ---------------------------------------------------------------------------

_USER_ID = "test-user-123"
_ACCOUNT_ID = "test_account"
_ORG_ID = "org_list_router_test"
_NOW = datetime.now(timezone.utc)

# Unique prefix to isolate this test module's docs from other integration tests
_PREFIX = "ch14_list_router"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _seed_session(
    db: Any,
    session_id: str,
    *,
    updated_at: datetime,
    deleted_at: datetime | None = None,
    category_id: str | None = None,
    search_text: str = "",
    title: str | None = None,
) -> None:
    """Write a minimal ChatSessionMetadata doc to the emulator."""
    from src.kene_api.models.chat import ChatSessionMetadata

    metadata = ChatSessionMetadata(
        session_id=session_id,
        user_id=_USER_ID,
        account_id=_ACCOUNT_ID,
        organization_id=_ORG_ID,
        model_id="gemini-2.5-flash",
        title=title,
        category_id=category_id,
        search_text=search_text,
        created_at=updated_at,
        updated_at=updated_at,
        deleted_at=deleted_at,
    )
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{session_id}").set(
        metadata.model_dump()
    )


def _purge_sessions(db: Any, *session_ids: str) -> None:
    for sid in session_ids:
        db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{sid}").delete()


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


def _clear_caches() -> None:
    from src.kene_api.chat.side_table import get_chat_side_table_service
    from src.kene_api.dependencies import get_firestore_client
    from src.kene_api.services.feature_flag_service import get_feature_flag_service

    get_firestore_client.cache_clear()
    get_chat_side_table_service.cache_clear()
    get_feature_flag_service.cache_clear()


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """TestClient wired to the real Firestore emulator.

    conftest.py patches ``src.kene_api.auth.firebase_admin.verify_id_token`` at
    the module attribute, but ``user_context.py`` uses ``from .firebase_admin
    import verify_id_token`` (a local binding) so that patch is ineffective
    here. FastAPI's ``app.dependency_overrides`` is the correct mechanism —
    same workaround used by ``test_substrate_only_invisible_with_flags_off.py``.
    """
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    _clear_caches()

    from src.kene_api.auth.models import UserContext
    from src.kene_api.auth.user_context import get_current_user_context
    from src.kene_api.main import app

    mock_user = UserContext(
        user_id=_USER_ID,
        email="test@example.com",
        organization_permissions={},
        account_permissions={_ACCOUNT_ID: "edit"},
    )
    app.dependency_overrides[get_current_user_context] = lambda: mock_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_current_user_context, None)


@pytest.fixture(autouse=True)
def _reset_emulator_state() -> Generator[None, None, None]:
    """Enable the flag; purge all test sessions before and after each test."""
    db = _emulator_client()
    # Enable chat_v2_enabled so the side-table branch runs
    _set_flag(db, "chat_v2_enabled", default_enabled=True)
    _clear_caches()

    yield

    # Purge all docs seeded by this module
    for doc in db.collection_group("chat_sessions").where(
        "user_id", "==", _USER_ID
    ).stream():
        doc.reference.delete()
    _delete_flag(db, "chat_v2_enabled")
    _clear_caches()


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def _get_conversations(client: TestClient, **params: Any) -> Any:
    params.setdefault("account_id", _ACCOUNT_ID)
    return client.get(
        "/api/v1/chat/conversations",
        params=params,
        headers={"Authorization": "Bearer dummy-firebase-token"},
    )


# ---------------------------------------------------------------------------
# AC-10: 30-day window
# ---------------------------------------------------------------------------


class TestThirtyDayWindow:
    def test_session_29_days_old_is_included(self, client: TestClient) -> None:
        db = _emulator_client()
        recent_id = f"{_PREFIX}_w_recent"
        _seed_session(db, recent_id, updated_at=_NOW - timedelta(days=29))

        resp = _get_conversations(client)
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert recent_id in ids

    def test_session_31_days_old_is_excluded(self, client: TestClient) -> None:
        db = _emulator_client()
        stale_id = f"{_PREFIX}_w_stale"
        _seed_session(db, stale_id, updated_at=_NOW - timedelta(days=31))

        resp = _get_conversations(client)
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert stale_id not in ids

    def test_recent_included_stale_excluded_together(
        self, client: TestClient
    ) -> None:
        db = _emulator_client()
        recent_id = f"{_PREFIX}_w_mix_recent"
        stale_id = f"{_PREFIX}_w_mix_stale"
        _seed_session(db, recent_id, updated_at=_NOW - timedelta(days=10))
        _seed_session(db, stale_id, updated_at=_NOW - timedelta(days=35))

        resp = _get_conversations(client)
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert recent_id in ids
        assert stale_id not in ids


# ---------------------------------------------------------------------------
# AC-11: deleted sessions excluded
# ---------------------------------------------------------------------------


class TestDeletedExclusion:
    def test_deleted_session_never_appears(self, client: TestClient) -> None:
        db = _emulator_client()
        deleted_id = f"{_PREFIX}_del_gone"
        live_id = f"{_PREFIX}_del_live"
        _seed_session(db, deleted_id, updated_at=_NOW, deleted_at=_NOW)
        _seed_session(db, live_id, updated_at=_NOW)

        resp = _get_conversations(client)
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert deleted_id not in ids
        assert live_id in ids


# ---------------------------------------------------------------------------
# AC-5: category filter
# ---------------------------------------------------------------------------


class TestCategoryFilter:
    def test_category_filter_narrows_to_matching_rows(
        self, client: TestClient
    ) -> None:
        db = _emulator_client()
        cat_x_id = f"{_PREFIX}_cat_x"
        cat_y_id = f"{_PREFIX}_cat_y"
        _seed_session(db, cat_x_id, updated_at=_NOW, category_id="cat_x_abc")
        _seed_session(db, cat_y_id, updated_at=_NOW, category_id="cat_y_xyz")

        resp = _get_conversations(client, category_id="cat_x_abc")
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert cat_x_id in ids
        assert cat_y_id not in ids

    def test_no_category_filter_returns_all_categories(
        self, client: TestClient
    ) -> None:
        db = _emulator_client()
        cat_x_id = f"{_PREFIX}_ncat_x"
        cat_y_id = f"{_PREFIX}_ncat_y"
        _seed_session(db, cat_x_id, updated_at=_NOW, category_id="cat_x_abc")
        _seed_session(db, cat_y_id, updated_at=_NOW, category_id="cat_y_xyz")

        resp = _get_conversations(client)
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert cat_x_id in ids
        assert cat_y_id in ids


# ---------------------------------------------------------------------------
# AC-4: case-insensitive substring search
# ---------------------------------------------------------------------------


class TestCaseInsensitiveSearch:
    def test_search_text_case_insensitive_match(self, client: TestClient) -> None:
        db = _emulator_client()
        match_id = f"{_PREFIX}_srch_match"
        no_match_id = f"{_PREFIX}_srch_nomatch"
        _seed_session(db, match_id, updated_at=_NOW, search_text="revenue forecast q4")
        _seed_session(db, no_match_id, updated_at=_NOW, search_text="brand strategy")

        resp = _get_conversations(client, query="REVENUE")
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert match_id in ids
        assert no_match_id not in ids

    def test_search_text_partial_substring_matches(
        self, client: TestClient
    ) -> None:
        db = _emulator_client()
        match_id = f"{_PREFIX}_srch_partial"
        _seed_session(
            db, match_id, updated_at=_NOW, search_text="competitive analysis"
        )

        resp = _get_conversations(client, query="petitive")
        assert resp.status_code == 200
        ids = [c["session_id"] for c in resp.json()["conversations"]]
        assert match_id in ids
