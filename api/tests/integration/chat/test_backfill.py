"""Integration tests for migrate_chat_side_table_backfill.py (CH-17).

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_backfill.py -v

These tests verify the full run_backfill path against a real Firestore emulator,
covering dry-run mode, real writes, idempotency, account-id scoping, and the
ADK Issue #3154 guard.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 "
        "(and GOOGLE_CLOUD_PROJECT_ID=test-project) to enable."
    ),
)

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
API_SRC = SCRIPTS_DIR.parent / "src"
for _p in (str(SCRIPTS_DIR), str(API_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import migrate_chat_side_table_backfill as cli  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
_ACCOUNT_ID = "acc_backfill_integration_test"
_ORG_ID = "org_backfill_test"
_USER_ID = "uid_backfill_test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    return _fs.Client(project=_PROJECT)


def _fake_session(
    session_id: str = "sess_bf_001",
    account_id: str = _ACCOUNT_ID,
    user_id: str = "",
) -> Any:
    return SimpleNamespace(
        id=session_id,
        user_id=user_id,
        state={"account_id": account_id},
        events=[
            SimpleNamespace(
                author="user",
                content=SimpleNamespace(parts=[SimpleNamespace(text="hello")]),
            ),
            SimpleNamespace(
                author="model",
                content=SimpleNamespace(parts=[SimpleNamespace(text="hi there")]),
            ),
        ],
        create_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        update_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_emulator(request: pytest.FixtureRequest) -> Any:  # type: ignore[return]
    """Wipe test documents before each test."""
    db = _emulator_client()

    yield

    # Teardown: clean up all test documents written under the test account
    docs = db.collection(f"accounts/{_ACCOUNT_ID}/chat_sessions").stream()
    for doc in docs:
        doc.reference.delete()
    # Clean up test account and user docs
    db.document(f"accounts/{_ACCOUNT_ID}").delete()
    db.document(f"users/{_USER_ID}").delete()


def _seed_account_and_user(db: Any) -> None:
    db.document(f"accounts/{_ACCOUNT_ID}").set({"organization_id": _ORG_ID})
    db.document(f"users/{_USER_ID}").set(
        {"permissions": {"account_permissions": {_ACCOUNT_ID: {"role": "admin"}}}}
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackfillDryRun:
    def test_dry_run_no_writes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dry-run mode logs the session but writes nothing to Firestore."""
        db = _emulator_client()
        _seed_account_and_user(db)
        session = _fake_session()
        monkeypatch.setattr(cli, "_list_sessions_for_user", lambda svc, uid: [session])

        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=True,
            user_id_filter=_USER_ID,
        )

        assert summary["created"] == 1
        # Verify no document was actually written
        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_bf_001").get()
        assert not doc.exists


class TestBackfillRealWrite:
    def test_writes_document_with_correct_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real run: document is written with expected fields."""
        db = _emulator_client()
        _seed_account_and_user(db)
        session = _fake_session()
        monkeypatch.setattr(cli, "_list_sessions_for_user", lambda svc, uid: [session])

        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            user_id_filter=_USER_ID,
        )

        assert summary["created"] == 1
        assert summary["errored"] == 0

        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_bf_001").get()
        assert doc.exists
        data = doc.to_dict() or {}
        assert data["session_id"] == "sess_bf_001"
        assert data["user_id"] == _USER_ID
        assert data["account_id"] == _ACCOUNT_ID
        assert data["organization_id"] == _ORG_ID
        assert data["message_count"] == 2
        assert data["last_message_preview"] == "hi there"


class TestBackfillIdempotency:
    def test_rerun_skips_existing_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Running backfill twice: second run skips already-present rows."""
        db = _emulator_client()
        _seed_account_and_user(db)
        session = _fake_session()
        monkeypatch.setattr(cli, "_list_sessions_for_user", lambda svc, uid: [session])

        # First run
        summary1 = cli.run_backfill(
            db, MagicMock(), dry_run=False, user_id_filter=_USER_ID
        )
        assert summary1["created"] == 1

        # Second run — idempotent
        summary2 = cli.run_backfill(
            db, MagicMock(), dry_run=False, user_id_filter=_USER_ID
        )
        assert summary2["already_present"] == 1
        assert summary2["created"] == 0


class TestBackfillAccountIdFilter:
    def test_account_filter_skips_unmatched_sessions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--account-id filter: sessions from a different account are skipped."""
        db = _emulator_client()
        _seed_account_and_user(db)
        # Session belongs to a different account
        session = _fake_session(account_id="acc_OTHER")
        monkeypatch.setattr(cli, "_list_sessions_for_user", lambda svc, uid: [session])

        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            account_id=_ACCOUNT_ID,
            user_id_filter=_USER_ID,
        )

        assert summary["skipped_account_mismatch"] == 1
        assert summary["created"] == 0


class TestBackfillAdk3154Guard:
    def test_written_user_id_is_loop_uid_not_session_user_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADK #3154 guard: metadata.user_id must be the iteration-loop uid."""
        db = _emulator_client()
        _seed_account_and_user(db)
        # ADK returns session with empty user_id (the bug)
        session = _fake_session(user_id="SHOULD_NEVER_APPEAR_IN_DB")
        monkeypatch.setattr(cli, "_list_sessions_for_user", lambda svc, uid: [session])

        cli.run_backfill(db, MagicMock(), dry_run=False, user_id_filter=_USER_ID)

        doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/sess_bf_001").get()
        data = doc.to_dict() or {}
        assert data["user_id"] == _USER_ID
        assert data["user_id"] != "SHOULD_NEVER_APPEAR_IN_DB"
