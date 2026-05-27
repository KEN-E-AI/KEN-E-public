"""Integration tests: category user isolation and assign_category (CH-PRD-03 §7 AC-10, AC-3, AC-4).

Tests the ownership enforcement guarantees: a user can neither read another user's
categories nor assign them to sessions. Also covers the happy-path assign and
unassign flows with real Firestore semantics.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_category_user_isolation.py -v
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
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_ACCOUNT_A = "acc_isolation_a"
_ACCOUNT_B = "acc_isolation_b"
_USER_A = "user_isolation_a"
_USER_B = "user_isolation_b"
_SESSION_A = "sess_isolation_a"
_SESSION_B = "sess_isolation_b"
_ORG_A = "org_isolation_a"
_ORG_B = "org_isolation_b"


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_session(db: Any, *, account_id: str, session_id: str, user_id: str) -> None:
    """Write a minimal chat_sessions side-table row for an isolation test."""
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").set(
        {
            "session_id": session_id,
            "user_id": user_id,
            "account_id": account_id,
            "organization_id": f"org_{user_id}",
            "model_id": "gemini-2.5-flash",
            "adk_app_name": "ken_e_chatbot",
            "context_window_max": 1_000_000,
            "title": "Isolation Test Session",
            "latest_summary": "Summary of test session",
            "category_id": None,
            "search_text": "",
            "created_at": _now(),
            "updated_at": _now(),
            "deleted_at": None,
            "input_tokens_total": 0,
            "output_tokens_total": 0,
            "reasoning_tokens_total": 0,
            "current_context_tokens": 0,
            "tool_call_count": 0,
            "artifact_count": 0,
            "message_count": 0,
        }
    )


@pytest.fixture(scope="module")
def db() -> Any:
    return _emulator_client()


@pytest.fixture(scope="module")
def services(db: Any):
    """Seed both users' sessions and categories; return service instances."""
    from src.kene_api.chat.categories import ChatCategoryService

    _seed_session(db, account_id=_ACCOUNT_A, session_id=_SESSION_A, user_id=_USER_A)
    _seed_session(db, account_id=_ACCOUNT_B, session_id=_SESSION_B, user_id=_USER_B)

    svc_a = ChatCategoryService(db=db)
    svc_b = ChatCategoryService(db=db)
    return svc_a, svc_b


@pytest.fixture(scope="module")
def category_ids(services: tuple, db: Any) -> dict:
    """Create one category per user and return their IDs."""
    svc_a, svc_b = services
    cat_a = svc_a.create_category(_USER_A, "Alpha Category")
    cat_b = svc_b.create_category(_USER_B, "Beta Category")
    return {"a": cat_a.category_id, "b": cat_b.category_id}


class TestListCategoriesIsolation:
    def test_user_b_list_does_not_include_user_a_category(
        self, services: tuple, category_ids: dict
    ) -> None:
        """AC-10: user B's list_categories does not expose user A's category."""
        _, svc_b = services
        categories = svc_b.list_categories(_USER_B)
        ids = {c.category_id for c in categories}
        assert category_ids["a"] not in ids

    def test_user_a_list_does_not_include_user_b_category(
        self, services: tuple, category_ids: dict
    ) -> None:
        _, _svc_b = services
        svc_a = services[0]
        categories = svc_a.list_categories(_USER_A)
        ids = {c.category_id for c in categories}
        assert category_ids["b"] not in ids


class TestAssignCategoryCrossUserBlocked:
    def test_user_b_cannot_assign_user_a_category_to_own_session(
        self, services: tuple, category_ids: dict
    ) -> None:
        """AC-10: assigning another user's category raises PermissionError (collapsed 404→403)."""
        _, svc_b = services
        with pytest.raises(PermissionError):
            svc_b.assign_category(_USER_B, _SESSION_B, category_ids["a"])

    def test_user_b_cannot_assign_to_user_a_session(
        self, services: tuple, category_ids: dict
    ) -> None:
        """AC-10: assigning to another user's session raises PermissionError."""
        _, svc_b = services
        with pytest.raises(PermissionError):
            svc_b.assign_category(_USER_B, _SESSION_A, category_ids["b"])


class TestAssignCategoryHappyPath:
    def test_assign_sets_category_id_on_session(
        self, services: tuple, category_ids: dict, db: Any
    ) -> None:
        """AC-3: valid assign persists category_id."""
        svc_a, _ = services
        svc_a.assign_category(_USER_A, _SESSION_A, category_ids["a"])

        doc = db.document(f"accounts/{_ACCOUNT_A}/chat_sessions/{_SESSION_A}").get()
        assert doc.exists
        data = doc.to_dict()
        assert data["category_id"] == category_ids["a"]

    def test_assign_sets_search_text_containing_casefolded_title(
        self, services: tuple, category_ids: dict, db: Any
    ) -> None:
        """AC-3: search_text includes casefolded session title."""
        svc_a, _ = services
        svc_a.assign_category(_USER_A, _SESSION_A, category_ids["a"])

        doc = db.document(f"accounts/{_ACCOUNT_A}/chat_sessions/{_SESSION_A}").get()
        search_text = doc.to_dict()["search_text"]
        assert "isolation test session" in search_text

    def test_assign_sets_search_text_containing_casefolded_category_name(
        self, services: tuple, category_ids: dict, db: Any
    ) -> None:
        """AC-3: search_text includes casefolded category name."""
        svc_a, _ = services
        svc_a.assign_category(_USER_A, _SESSION_A, category_ids["a"])

        doc = db.document(f"accounts/{_ACCOUNT_A}/chat_sessions/{_SESSION_A}").get()
        search_text = doc.to_dict()["search_text"]
        assert "alpha category" in search_text


class TestAssignCategoryUnassign:
    def test_unassign_clears_category_id(
        self, services: tuple, category_ids: dict, db: Any
    ) -> None:
        """AC-4: category_id=None clears the assignment."""
        svc_a, _ = services
        # Ensure assigned first
        svc_a.assign_category(_USER_A, _SESSION_A, category_ids["a"])
        # Now unassign
        svc_a.assign_category(_USER_A, _SESSION_A, None)

        doc = db.document(f"accounts/{_ACCOUNT_A}/chat_sessions/{_SESSION_A}").get()
        assert doc.to_dict()["category_id"] is None

    def test_unassign_excludes_category_name_from_search_text(
        self, services: tuple, category_ids: dict, db: Any
    ) -> None:
        """AC-4: after unassign, search_text does not include the old category name."""
        svc_a, _ = services
        svc_a.assign_category(_USER_A, _SESSION_A, category_ids["a"])
        svc_a.assign_category(_USER_A, _SESSION_A, None)

        doc = db.document(f"accounts/{_ACCOUNT_A}/chat_sessions/{_SESSION_A}").get()
        search_text = doc.to_dict()["search_text"]
        assert "alpha category" not in search_text
        # title is still in search_text
        assert "isolation test session" in search_text
