"""Focused integration test: delete_user_data purges chat_categories (CH-PRD-03 §7 AC-12).

Verifies that ``delete_user_data(user_id, actor=...)`` (DM-PRD-05 §4.2) sweeps
``users/{user_id}/chat_categories/*`` to empty, satisfying the USER_SUBCOLLECTIONS
registration at ``user_deletion_service.py``.

Shape B session-scoping rule: chat sessions live at
``accounts/{account_id}/chat_sessions/*`` (account-scoped, not user-scoped).
``delete_user_data`` does NOT delete sessions — that is ``delete_account_data``'s
job. This test seeds 10 sessions and explicitly asserts they survive user deletion,
documenting this boundary rather than accidentally testing the wrong scope.

PRD reference:   CH-PRD-03 §7 AC-12
Data model ref:  DM-PRD-05 §4.2 Step 4 (recursive_delete on users/{user_id})
                 CLAUDE.md §Shape B Multi-Tenant Data Model Convention

Enable by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_chat_categories_user_deletion_sweep.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import src.kene_api.services.user_deletion_service as _svc_module
from src.kene_api.auth.models import UserContext
from src.kene_api.services.user_deletion_service import delete_user_data

# ---------------------------------------------------------------------------
# Skip gate
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _super_admin_user() -> UserContext:
    return UserContext(
        user_id="super-uid",
        email="ops@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _recursive_delete_emulator(db: Any, collection: str, doc_id: str) -> None:
    """Best-effort two-level recursive delete for emulator cleanup."""
    root_ref = db.collection(collection).document(doc_id)
    for sub_col in root_ref.collections():
        for doc_ref in list(sub_col.list_documents()):
            for nested in doc_ref.collections():
                for nested_doc in list(nested.list_documents()):
                    nested_doc.delete()
            doc_ref.delete()
    root_ref.delete()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def emulator_db() -> Any:
    return _emulator_client()


@pytest.fixture
def run_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def user_id(run_id: str) -> str:
    return f"u_alpha_{run_id}"


@pytest.fixture
def account_id(run_id: str) -> str:
    return f"acc_alpha_{run_id}"


@pytest.fixture(autouse=True)
def cleanup_emulator(
    emulator_db: Any,
    user_id: str,
    account_id: str,
) -> Generator[None, None, None]:
    """Wipe test-owned Firestore data before and after each test."""
    _cleanup_docs = [
        ("users", user_id),
        ("accounts", account_id),
    ]
    for col, doc_id in _cleanup_docs:
        try:
            _recursive_delete_emulator(emulator_db, col, doc_id)
        except Exception:
            pass

    yield

    for col, doc_id in _cleanup_docs:
        try:
            _recursive_delete_emulator(emulator_db, col, doc_id)
        except Exception as exc:
            import warnings

            warnings.warn(
                f"cleanup_emulator failed for {col}/{doc_id}: {exc}", stacklevel=2
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatCategoriesUserDeletionSweep:
    """Focused regression: delete_user_data sweeps chat_categories, preserves sessions.

    CH-PRD-03 §7 AC-12 — Verifies the USER_SUBCOLLECTIONS registration is
    honoured end-to-end against a real Firestore emulator.
    """

    async def test_categories_purged_sessions_preserved(
        self,
        emulator_db: Any,
        run_id: str,
        user_id: str,
        account_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Happy path: 5 categories and 10 sessions seeded.

        After delete_user_data():
          (a) chat_categories collection is empty.
          (b) users/{user_id} root document does not exist.
          (c) accounts/{account_id}/members/{user_id} row is deleted.
          (d) All 10 chat_sessions docs still exist (Shape B — user-deletion
              does not touch account-scoped sessions; that is
              delete_account_data's responsibility).
        """
        # --- Arrange: seed user doc ---
        emulator_db.collection("users").document(user_id).set(
            {"email": f"{user_id}@test.com", "seeded_for": "CH-34"}
        )

        # --- Arrange: seed 5 categories ---
        cats_col = (
            emulator_db.collection("users").document(user_id).collection("chat_categories")
        )
        category_ids = [f"cat_{i:02d}_{run_id}" for i in range(5)]
        for i, cat_id in enumerate(category_ids):
            cats_col.document(cat_id).set(
                {
                    "category_id": cat_id,
                    "user_id": user_id,
                    "name": f"Category {i}",
                    "name_casefold": f"category {i}",
                }
            )

        # --- Arrange: seed account + member row ---
        # parent_kind is required by _resolve_member_rows which queries
        # where("parent_kind", "==", "account") to discover member rows.
        emulator_db.collection("accounts").document(account_id).collection(
            "members"
        ).document(user_id).set({"user_id": user_id, "role": "editor", "parent_kind": "account"})

        # --- Arrange: seed 10 sessions at Shape B path (account-scoped) ---
        sessions_col = (
            emulator_db.collection("accounts")
            .document(account_id)
            .collection("chat_sessions")
        )
        session_ids = [f"sess_{i:02d}_{run_id}" for i in range(10)]
        for i, sess_id in enumerate(session_ids):
            sessions_col.document(sess_id).set(
                {
                    "session_id": sess_id,
                    "user_id": user_id,
                    "account_id": account_id,
                    "category_id": category_ids[i % 5],
                    "title": f"Session {i}",
                    "deleted_at": None,
                }
            )

        # --- Arrange: patch orchestrator seams ---
        monkeypatch.setattr(_svc_module, "_on_user_removed", AsyncMock(return_value=None))
        monkeypatch.setattr(_svc_module, "_write_audit", AsyncMock(return_value=None))
        monkeypatch.setattr(_svc_module, "get_firestore_client", lambda: emulator_db)

        # --- Act ---
        result = await delete_user_data(user_id, actor=_super_admin_user())

        # --- Assert: no errors ---
        assert result.errors == [], f"delete_user_data reported errors: {result.errors}"

        # --- Assert (a): chat_categories collection is empty ---
        remaining_cats = list(cats_col.list_documents())
        assert remaining_cats == [], (
            f"Expected chat_categories to be empty after user deletion, "
            f"but found: {[d.id for d in remaining_cats]}"
        )

        # --- Assert (b): users/{user_id} root document is gone ---
        user_doc = emulator_db.collection("users").document(user_id).get()
        assert not user_doc.exists, (
            f"Root users/{user_id} document still exists after delete_user_data"
        )

        # --- Assert (c): account member row is deleted ---
        member_doc = (
            emulator_db.collection("accounts")
            .document(account_id)
            .collection("members")
            .document(user_id)
            .get()
        )
        assert not member_doc.exists, (
            f"accounts/{account_id}/members/{user_id} still exists after delete_user_data"
        )

        # --- Assert (d): sessions still exist (Shape B — not user-scoped) ---
        # delete_user_data only purges users/{user_id}/* and member rows.
        # Chat sessions at accounts/{account_id}/chat_sessions/* are account-scoped
        # (Shape B); deleting them is delete_account_data's responsibility, not
        # delete_user_data's. Asserting their presence here documents this boundary.
        missing_sessions = []
        for sess_id in session_ids:
            sess_doc = sessions_col.document(sess_id).get()
            if not sess_doc.exists:
                missing_sessions.append(sess_id)
        assert missing_sessions == [], (
            f"Sessions unexpectedly deleted by delete_user_data (Shape B violation): "
            f"{missing_sessions}"
        )
