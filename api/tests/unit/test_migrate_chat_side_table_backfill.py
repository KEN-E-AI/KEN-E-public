"""Unit tests for migrate_chat_side_table_backfill.py (CH-17).

Covers:
- CLI --help exits 0; missing GOOGLE_CLOUD_PROJECT_ID exits 2 (AC-10, AC-11)
- _count_user_model_messages: only user/model authors counted; tool/system excluded
- _last_message_preview: truncation, ORGANIZATION CONTEXT skip, reversed scan
- _resolve_model_id: state.model_id > default fallback
- _parse_timestamp: aware datetime, naive datetime, ISO string, None
- _build_metadata: raises ValueError on missing state.account_id and missing session id
- _normalize_list_sessions_response: ListSessionsResponse object vs. plain list;
  asserts on next_page_token
- run_backfill: dry_run, already_present skip, account_id mismatch skip,
  missing org_id error path, ADK #3154 guard (user_id never from session.user_id)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
API_SRC = SCRIPTS_DIR.parent / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

import migrate_chat_side_table_backfill as cli  # noqa: E402

# ---------------------------------------------------------------------------
# Minimal in-memory Firestore substitute
# ---------------------------------------------------------------------------


class _FakeDocSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self.exists = data is not None
        self._data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeDocRef:
    def __init__(self, store: dict[str, Any], path: str) -> None:
        self._store = store
        self._path = path

    def get(self) -> _FakeDocSnapshot:
        return _FakeDocSnapshot(self._store.get(self._path))

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._path] = data


class _FakeCollectionRef:
    def __init__(self, store: dict[str, Any], col_path: str) -> None:
        self._store = store
        self._col_path = col_path

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, f"{self._col_path}/{doc_id}")

    def stream(self) -> list[Any]:
        prefix = self._col_path + "/"
        docs = []
        seen: set[str] = set()
        for full_path, data in self._store.items():
            if not full_path.startswith(prefix):
                continue
            rel = full_path[len(prefix):]
            doc_id = rel.split("/")[0]
            if doc_id not in seen:
                seen.add(doc_id)
                snap = _FakeDocSnapshot(data)
                snap.id = doc_id  # type: ignore[attr-defined]
                docs.append(snap)
        return docs


class FakeFirestoreClient:
    """Minimal in-memory Firestore for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def seed(self, path: str, data: dict[str, Any]) -> None:
        self._store[path] = data

    def collection(self, col: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self._store, col)

    def document(self, path: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, path)


# ---------------------------------------------------------------------------
# Fake ADK session factory
# ---------------------------------------------------------------------------


def _fake_event(author: str, text: str = "hello") -> Any:
    part = SimpleNamespace(text=text)
    content = SimpleNamespace(parts=[part])
    return SimpleNamespace(author=author, content=content)


def _fake_session(
    session_id: str = "sess_001",
    account_id: str = "acc_A",
    user_id: str = "",  # always empty to simulate ADK Issue #3154
    events: list[Any] | None = None,
    model_id: str | None = None,
    create_time: datetime | None = None,
    update_time: datetime | None = None,
    title: str | None = None,
) -> Any:
    state: dict[str, Any] = {"account_id": account_id}
    if model_id:
        state["model_id"] = model_id
    if title:
        state["conversation_name"] = title
    return SimpleNamespace(
        id=session_id,
        user_id=user_id,
        state=state,
        events=events or [],
        create_time=create_time,
        update_time=update_time,
    )


# ---------------------------------------------------------------------------
# TestCLIContract — subprocess-level tests
# ---------------------------------------------------------------------------


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    script = str(SCRIPTS_DIR / "migrate_chat_side_table_backfill.py")
    return subprocess.run(
        [sys.executable, script, *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestCLIContract:
    def test_help_exits_zero(self) -> None:
        result = _run_cli("--help", env={})
        assert result.returncode == 0
        assert "--dry-run" in result.stdout

    def test_missing_project_id_exits_two(self) -> None:
        result = _run_cli("--dry-run", env={})
        assert result.returncode == 2
        assert "GOOGLE_CLOUD_PROJECT_ID" in result.stderr


# ---------------------------------------------------------------------------
# TestCountUserModelMessages
# ---------------------------------------------------------------------------


class TestCountUserModelMessages:
    def test_empty_events(self) -> None:
        session = SimpleNamespace(events=[])
        assert cli._count_user_model_messages(session) == 0

    def test_no_events_attr(self) -> None:
        session = SimpleNamespace()
        assert cli._count_user_model_messages(session) == 0

    def test_counts_user_and_model(self) -> None:
        events = [
            _fake_event("user"),
            _fake_event("model"),
            _fake_event("user"),
        ]
        session = SimpleNamespace(events=events)
        assert cli._count_user_model_messages(session) == 3

    def test_excludes_tool_and_system(self) -> None:
        events = [
            _fake_event("user"),
            _fake_event("tool"),
            _fake_event("system"),
            _fake_event("model"),
        ]
        session = SimpleNamespace(events=events)
        assert cli._count_user_model_messages(session) == 2

    def test_events_none(self) -> None:
        session = SimpleNamespace(events=None)
        assert cli._count_user_model_messages(session) == 0


# ---------------------------------------------------------------------------
# TestLastMessagePreview
# ---------------------------------------------------------------------------


class TestLastMessagePreview:
    def test_none_when_no_events(self) -> None:
        session = SimpleNamespace(events=[])
        assert cli._last_message_preview(session) is None

    def test_truncates_to_limit(self) -> None:
        text = "x" * 200
        session = SimpleNamespace(events=[_fake_event("user", text)])
        result = cli._last_message_preview(session, limit=10)
        assert result == "x" * 10

    def test_skips_organization_context_prefix(self) -> None:
        org_event = _fake_event("system", "[ORGANIZATION CONTEXT] big blob")
        real_event = _fake_event("user", "what's my budget?")
        session = SimpleNamespace(events=[real_event, org_event])
        # reversed scan hits org_event first → should skip it → return real_event text
        result = cli._last_message_preview(session)
        assert result == "what's my budget?"

    def test_returns_last_non_internal_event(self) -> None:
        events = [
            _fake_event("user", "first message"),
            _fake_event("model", "response"),
        ]
        session = SimpleNamespace(events=events)
        result = cli._last_message_preview(session)
        assert result == "response"

    def test_skips_empty_text(self) -> None:
        events = [
            _fake_event("user", "real text"),
            _fake_event("model", ""),  # empty — should be skipped
        ]
        session = SimpleNamespace(events=events)
        result = cli._last_message_preview(session)
        assert result == "real text"


# ---------------------------------------------------------------------------
# TestResolveModelId
# ---------------------------------------------------------------------------


class TestResolveModelId:
    def test_default_when_no_state(self) -> None:
        session = SimpleNamespace(state={})
        assert cli._resolve_model_id(session) == cli._DEFAULT_MODEL_ID

    def test_uses_state_model_id(self) -> None:
        session = SimpleNamespace(state={"model_id": "gemini-2.5-flash"})
        assert cli._resolve_model_id(session) == "gemini-2.5-flash"

    def test_default_when_state_is_none(self) -> None:
        session = SimpleNamespace(state=None)
        assert cli._resolve_model_id(session) == cli._DEFAULT_MODEL_ID


# ---------------------------------------------------------------------------
# TestParseTimestamp
# ---------------------------------------------------------------------------


class TestParseTimestamp:
    def test_none_returns_none(self) -> None:
        assert cli._parse_timestamp(None) is None

    def test_aware_datetime_passthrough(self) -> None:
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = cli._parse_timestamp(dt)
        assert result == dt
        assert result.tzinfo is not None

    def test_naive_datetime_gets_utc(self) -> None:
        dt = datetime(2025, 1, 1)
        result = cli._parse_timestamp(dt)
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_iso_string_with_z(self) -> None:
        result = cli._parse_timestamp("2025-06-01T12:00:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.tzinfo is not None

    def test_iso_string_with_offset(self) -> None:
        result = cli._parse_timestamp("2025-06-01T12:00:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_invalid_string_returns_none(self) -> None:
        assert cli._parse_timestamp("not-a-date") is None

    def test_unknown_type_returns_none(self) -> None:
        assert cli._parse_timestamp(12345) is None


# ---------------------------------------------------------------------------
# TestBuildMetadata
# ---------------------------------------------------------------------------


class TestBuildMetadata:
    def test_raises_on_missing_state_account_id(self) -> None:
        session = SimpleNamespace(
            id="sess_001",
            state={},  # no account_id
            events=[],
            create_time=None,
            update_time=None,
        )
        with pytest.raises(ValueError, match=r"state\.account_id"):
            cli._build_metadata(
                session,
                account_id="acc_A",
                user_id="uid_1",
                organization_id="org_1",
                context_window_max=1_000_000,
                model_id="gemini-2.5-pro",
            )

    def test_raises_on_missing_session_id(self) -> None:
        session = SimpleNamespace(
            id="",
            state={"account_id": "acc_A"},
            events=[],
            create_time=None,
            update_time=None,
        )
        with pytest.raises(ValueError, match="no id field"):
            cli._build_metadata(
                session,
                account_id="acc_A",
                user_id="uid_1",
                organization_id="org_1",
                context_window_max=1_000_000,
                model_id="gemini-2.5-pro",
            )

    def test_user_id_comes_from_argument_not_session(self) -> None:
        """ADK Issue #3154 guard: user_id in metadata = iteration-loop uid, not session.user_id."""
        session = SimpleNamespace(
            id="sess_001",
            user_id="WRONG_USER_FROM_ADK",  # ADK bug: this should never be used
            state={"account_id": "acc_A"},
            events=[],
            create_time=None,
            update_time=None,
        )
        metadata = cli._build_metadata(
            session,
            account_id="acc_A",
            user_id="correct_uid",
            organization_id="org_1",
            context_window_max=1_000_000,
            model_id="gemini-2.5-pro",
        )
        assert metadata.user_id == "correct_uid"

    def test_populated_metadata_fields(self) -> None:
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        events = [
            _fake_event("user", "hello"),
            _fake_event("model", "hi there"),
        ]
        session = SimpleNamespace(
            id="sess_xyz",
            state={"account_id": "acc_B", "conversation_name": "My Chat"},
            events=events,
            create_time=now,
            update_time=now,
        )
        metadata = cli._build_metadata(
            session,
            account_id="acc_B",
            user_id="uid_2",
            organization_id="org_2",
            context_window_max=2_000_000,
            model_id="gemini-2.5-flash",
        )
        assert metadata.session_id == "sess_xyz"
        assert metadata.account_id == "acc_B"
        assert metadata.organization_id == "org_2"
        assert metadata.model_id == "gemini-2.5-flash"
        assert metadata.context_window_max == 2_000_000
        assert metadata.title == "My Chat"
        assert metadata.message_count == 2
        assert metadata.last_message_preview == "hi there"
        assert metadata.created_at == now
        assert metadata.updated_at == now


# ---------------------------------------------------------------------------
# TestNormalizeListSessionsResponse
# ---------------------------------------------------------------------------


class TestNormalizeListSessionsResponse:
    def test_plain_list(self) -> None:
        sessions = [_fake_session("s1"), _fake_session("s2")]
        result = cli._normalize_list_sessions_response(sessions)
        assert len(result) == 2
        assert result[0].id == "s1"

    def test_response_object_with_sessions_attr(self) -> None:
        inner = [_fake_session("s1"), _fake_session("s2")]
        response = SimpleNamespace(sessions=inner)
        result = cli._normalize_list_sessions_response(response)
        assert len(result) == 2

    def test_response_with_next_page_token_raises(self) -> None:
        inner = [_fake_session("s1")]
        response = SimpleNamespace(sessions=inner, next_page_token="tok_abc")
        with pytest.raises(AssertionError, match="paginated"):
            cli._normalize_list_sessions_response(response)

    def test_empty_list(self) -> None:
        result = cli._normalize_list_sessions_response([])
        assert result == []


# ---------------------------------------------------------------------------
# TestRunBackfill — functional tests with FakeFirestoreClient
# ---------------------------------------------------------------------------


class TestRunBackfill:
    def _make_db(self) -> FakeFirestoreClient:
        db = FakeFirestoreClient()
        # Seed account doc so org_id resolves
        db.seed("accounts/acc_A", {"organization_id": "org_A"})
        # Seed a user that has access to acc_A
        db.seed(
            "users/uid_1",
            {"permissions": {"account_permissions": {"acc_A": {"role": "admin"}}}},
        )
        return db

    def _make_session_service(self, sessions: list[Any]) -> Any:
        """Stub session service that returns a fixed list for any user."""
        service = MagicMock()
        # _list_sessions_for_user is called in a thread; we patch it at module level instead
        return service

    def test_dry_run_logs_but_does_not_write(self, monkeypatch: pytest.MonkeyPatch) -> None:
        db = self._make_db()
        session = _fake_session("sess_001", account_id="acc_A")
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=True,
            account_id=None,
            user_id_filter="uid_1",
        )
        assert summary["created"] == 1
        assert summary["errored"] == 0
        # No writes in dry-run
        assert "accounts/acc_A/chat_sessions/sess_001" not in db._store

    def test_real_run_writes_document(self, monkeypatch: pytest.MonkeyPatch) -> None:
        db = self._make_db()
        session = _fake_session("sess_001", account_id="acc_A")
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            account_id=None,
            user_id_filter="uid_1",
        )
        assert summary["created"] == 1
        assert "accounts/acc_A/chat_sessions/sess_001" in db._store

    def test_idempotency_skips_existing_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        db = self._make_db()
        # Pre-seed the side-table row
        db.seed("accounts/acc_A/chat_sessions/sess_001", {"session_id": "sess_001"})
        session = _fake_session("sess_001", account_id="acc_A")
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            account_id=None,
            user_id_filter="uid_1",
        )
        assert summary["already_present"] == 1
        assert summary["created"] == 0

    def test_account_mismatch_skips_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Session whose state.account_id != --account-id filter is skipped."""
        db = self._make_db()
        db.seed("accounts/acc_B", {"organization_id": "org_B"})
        session = _fake_session("sess_002", account_id="acc_B")  # different account
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            account_id="acc_A",  # filter to acc_A
            user_id_filter="uid_1",
        )
        assert summary["skipped_account_mismatch"] == 1
        assert summary["created"] == 0

    def test_missing_org_id_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Account doc missing organization_id increments errored counter."""
        db = FakeFirestoreClient()
        db.seed("accounts/acc_X", {})  # no organization_id field
        session = _fake_session("sess_003", account_id="acc_X")
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            user_id_filter="uid_x",
        )
        assert summary["errored"] == 1
        assert summary["created"] == 0

    def test_adk_3154_guard_written_user_id_is_loop_uid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Metadata written to Firestore uses the iteration-loop uid, not session.user_id."""
        db = self._make_db()
        # Simulate ADK Issue #3154: session.user_id is empty
        session = _fake_session("sess_001", account_id="acc_A", user_id="")
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            user_id_filter="uid_1",
        )
        doc = db._store.get("accounts/acc_A/chat_sessions/sess_001", {})
        assert doc.get("user_id") == "uid_1"  # must be the loop uid

    def test_missing_state_account_id_skips_with_warning(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session without state.account_id is counted as skipped_account_mismatch."""
        db = FakeFirestoreClient()
        session = SimpleNamespace(
            id="sess_no_acct",
            user_id="",
            state={},  # no account_id
            events=[],
            create_time=None,
            update_time=None,
        )
        monkeypatch.setattr(
            cli,
            "_list_sessions_for_user",
            lambda svc, uid: [session],
        )
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            user_id_filter="uid_1",
        )
        assert summary["skipped_account_mismatch"] == 1

    def test_list_sessions_error_increments_errored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If _list_sessions_for_user raises, the user's batch is counted as errored."""
        db = self._make_db()

        def _raise(svc: Any, uid: str) -> list[Any]:
            raise RuntimeError("ADK timeout")

        monkeypatch.setattr(cli, "_list_sessions_for_user", _raise)
        summary = cli.run_backfill(
            db,
            MagicMock(),
            dry_run=False,
            user_id_filter="uid_1",
        )
        # A list_sessions error increments errored (not per-session, but per-user)
        assert summary["errored"] == 1
