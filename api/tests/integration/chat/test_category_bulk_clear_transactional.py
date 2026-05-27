"""Integration tests for ChatCategoryService.delete_category (CH-32).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_category_bulk_clear_transactional.py -v

Three scenarios:
  1. >400 sessions (401) → two transactions; category doc deleted; sessions cleared (AC-13).
  2. 800 sessions (2x400) → two equal batches; all sessions cleared.
  3. Idempotency — calling delete_category twice on the same category is safe and
     returns 0 sessions_reassigned on the second call.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 "
        "(and GOOGLE_CLOUD_PROJECT_ID=test-project) to enable."
    ),
)

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
_USER_ID = "uid_cat_bulk_clear_test"
_ACCOUNT_ID = "acc_cat_bulk_clear_test"
_ORG_ID = "org_cat_bulk_clear_test"
_CATEGORY_ID = "cat_bulk_clear_integration"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    return _fs.Client(project=_PROJECT)


def _make_service(db: Any) -> Any:
    from src.kene_api.chat.categories import ChatCategoryService

    return ChatCategoryService(db=db)


def _seed_sessions(db: Any, count: int, *, category_id: str = _CATEGORY_ID) -> None:
    """Write `count` chat_session docs under `_ACCOUNT_ID` belonging to `_USER_ID`."""
    now = datetime.now(timezone.utc)
    batch = db.batch()
    for i in range(count):
        ref = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_bulk_{i:04d}")
        batch.set(
            ref,
            {
                "session_id": f"sess_bulk_{i:04d}",
                "user_id": _USER_ID,
                "account_id": _ACCOUNT_ID,
                "organization_id": _ORG_ID,
                "category_id": category_id,
                "title": f"Session {i}",
                "latest_summary": None,
                "search_text": f"session {i}",
                "created_at": now,
                "updated_at": now,
            },
        )
        # Firestore batch write limit is 500; flush every 400 to stay well below.
        if (i + 1) % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()


def _seed_category_doc(db: Any, *, category_id: str = _CATEGORY_ID) -> None:
    now = datetime.now(timezone.utc)
    db.document(f"users/{_USER_ID}/chat_categories/{category_id}").set(
        {
            "category_id": category_id,
            "user_id": _USER_ID,
            "name": "Bulk Clear Test",
            "name_casefold": "bulk clear test",
            "created_at": now,
            "updated_at": now,
        }
    )


def _count_sessions_with_category(db: Any, *, category_id: str = _CATEGORY_ID) -> int:
    docs = list(
        db.collection_group("chat_sessions")
        .where("user_id", "==", _USER_ID)
        .where("category_id", "==", category_id)
        .get()
    )
    return len(docs)


def _count_all_sessions(db: Any) -> int:
    return len(list(db.collection(f"accounts/{_ACCOUNT_ID}/chat_sessions").get()))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_emulator() -> Any:  # type: ignore[return]
    db = _emulator_client()
    yield
    # Teardown: delete all session docs under the test account
    docs = list(db.collection(f"accounts/{_ACCOUNT_ID}/chat_sessions").stream())
    batch = db.batch()
    for i, doc in enumerate(docs):
        batch.delete(doc.reference)
        if (i + 1) % 400 == 0:
            batch.commit()
            batch = db.batch()
    batch.commit()
    # Delete the category doc (may already be deleted by the service)
    db.document(f"users/{_USER_ID}/chat_categories/{_CATEGORY_ID}").delete()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteCategory401Sessions:
    """AC-13: 401 sessions → 2 transactions; all sessions cleared; category doc gone."""

    def test_all_sessions_cleared(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 401)

        svc = _make_service(db)
        result = svc.delete_category(_USER_ID, _CATEGORY_ID)

        assert result.sessions_reassigned == 401
        assert _count_sessions_with_category(db) == 0

    def test_category_doc_deleted(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 401)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)

        cat_snap = db.document(f"users/{_USER_ID}/chat_categories/{_CATEGORY_ID}").get()
        assert not cat_snap.exists

    def test_session_docs_still_exist_with_null_category(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 401)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)

        # All 401 session documents must still exist — only category_id is cleared
        assert _count_all_sessions(db) == 401

    def test_search_text_recomputed_on_cleared_sessions(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 5)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)

        docs = list(db.collection(f"accounts/{_ACCOUNT_ID}/chat_sessions").get())
        for doc in docs:
            row = doc.to_dict()
            # search_text must not contain a stale category reference; title-only expected
            title_casefold = (row.get("title") or "").casefold()
            assert row["search_text"] == title_casefold


class TestDeleteCategory800Sessions:
    """800 sessions → exactly 2 batches of 400; all sessions cleared."""

    def test_all_sessions_cleared(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 800)

        svc = _make_service(db)
        result = svc.delete_category(_USER_ID, _CATEGORY_ID)

        assert result.sessions_reassigned == 800
        assert _count_sessions_with_category(db) == 0

    def test_category_doc_deleted(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 800)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)

        cat_snap = db.document(f"users/{_USER_ID}/chat_categories/{_CATEGORY_ID}").get()
        assert not cat_snap.exists


class TestDeleteCategoryIdempotency:
    """Calling delete_category twice on the same category is safe."""

    def test_second_call_returns_zero_sessions_reassigned(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 3)

        svc = _make_service(db)
        first = svc.delete_category(_USER_ID, _CATEGORY_ID)
        second = svc.delete_category(_USER_ID, _CATEGORY_ID)

        assert first.sessions_reassigned == 3
        assert second.sessions_reassigned == 0

    def test_second_call_does_not_raise(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 2)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)
        # Must not raise even though category doc is already gone
        svc.delete_category(_USER_ID, _CATEGORY_ID)

    def test_sessions_remain_cleared_after_second_call(self) -> None:
        db = _emulator_client()
        _seed_category_doc(db)
        _seed_sessions(db, 2)

        svc = _make_service(db)
        svc.delete_category(_USER_ID, _CATEGORY_ID)
        svc.delete_category(_USER_ID, _CATEGORY_ID)

        assert _count_sessions_with_category(db) == 0
