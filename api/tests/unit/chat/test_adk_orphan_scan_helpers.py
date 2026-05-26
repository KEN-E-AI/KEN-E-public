"""Unit tests for pure helpers in kene_api.chat.adk_session_orphan_scan.

Tests cover _classify_session, _normalize_list_sessions_response,
_alert_missing_orphan_ops, and _emit_completion_log.  No Firestore, ADK, or
GCS calls are made.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from kene_api.chat import adk_session_orphan_scan as cli

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_GRACE = timedelta(hours=1)
_ACCOUNT_ID = "acc_unit_test"
_SESSION_ID = "sess_unit_001"


def _meta(deleted_at: datetime | None = None):
    """Return a minimal ChatSessionMetadata-like namespace."""
    return SimpleNamespace(
        session_id=_SESSION_ID,
        user_id="uid_test",
        account_id=_ACCOUNT_ID,
        organization_id="org_test",
        deleted_at=deleted_at,
    )


# ---------------------------------------------------------------------------
# _classify_session
# ---------------------------------------------------------------------------


class TestClassifySession:
    """Tests for _classify_session pure function."""

    def test_no_side_table_row_returns_missing(self):
        result = cli._classify_session(_ACCOUNT_ID, _SESSION_ID, None, _NOW, _GRACE)
        assert result == cli.CLASS_MISSING

    def test_active_session_returns_all_clean(self):
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=None), _NOW, _GRACE
        )
        assert result == cli.CLASS_ALL_CLEAN

    def test_tombstoned_outside_grace_returns_tombstoned(self):
        deleted_at = _NOW - timedelta(hours=2)  # > 1 h ago
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=deleted_at), _NOW, _GRACE
        )
        assert result == cli.CLASS_TOMBSTONED

    def test_tombstoned_inside_grace_returns_in_grace(self):
        deleted_at = _NOW - timedelta(minutes=30)  # < 1 h ago
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=deleted_at), _NOW, _GRACE
        )
        assert result == cli.CLASS_TOMBSTONED_IN_GRACE

    def test_tombstoned_exactly_at_boundary_is_in_grace(self):
        """Strict > comparison: deleted exactly 1 h ago is still in grace."""
        deleted_at = _NOW - timedelta(hours=1)
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=deleted_at), _NOW, _GRACE
        )
        assert result == cli.CLASS_TOMBSTONED_IN_GRACE

    def test_tombstoned_one_second_past_boundary_is_tombstoned(self):
        deleted_at = _NOW - timedelta(hours=1, seconds=1)
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=deleted_at), _NOW, _GRACE
        )
        assert result == cli.CLASS_TOMBSTONED

    def test_naive_deleted_at_treated_as_utc(self):
        """deleted_at without tzinfo is assumed UTC and compared correctly."""
        # 2 h ago as naive datetime
        deleted_at_naive = (_NOW - timedelta(hours=2)).replace(tzinfo=None)
        result = cli._classify_session(
            _ACCOUNT_ID, _SESSION_ID, _meta(deleted_at=deleted_at_naive), _NOW, _GRACE
        )
        assert result == cli.CLASS_TOMBSTONED

    def test_custom_grace_window_respected(self):
        """A non-default grace window is applied correctly."""
        deleted_at = _NOW - timedelta(hours=3)
        # 6-hour grace — should still be in grace.
        result = cli._classify_session(
            _ACCOUNT_ID,
            _SESSION_ID,
            _meta(deleted_at=deleted_at),
            _NOW,
            timedelta(hours=6),
        )
        assert result == cli.CLASS_TOMBSTONED_IN_GRACE


# ---------------------------------------------------------------------------
# _normalize_list_sessions_response
# ---------------------------------------------------------------------------


class TestNormalizeListSessionsResponse:
    """Tests for _normalize_list_sessions_response."""

    def test_plain_list_returned_as_is(self):
        sessions = [SimpleNamespace(id="s1"), SimpleNamespace(id="s2")]
        result = cli._normalize_list_sessions_response(sessions)
        assert result == sessions

    def test_object_with_sessions_attr_unpacked(self):
        s1 = SimpleNamespace(id="s1")
        response = SimpleNamespace(sessions=[s1], next_page_token=None)
        result = cli._normalize_list_sessions_response(response)
        assert result == [s1]

    def test_paginated_response_raises(self):
        response = SimpleNamespace(
            sessions=[SimpleNamespace(id="s1")],
            next_page_token="some-token",
        )
        with pytest.raises(RuntimeError, match="paginated"):
            cli._normalize_list_sessions_response(response)

    def test_empty_list_returns_empty(self):
        assert cli._normalize_list_sessions_response([]) == []

    def test_object_with_empty_sessions_and_no_token(self):
        response = SimpleNamespace(sessions=[], next_page_token=None)
        assert cli._normalize_list_sessions_response(response) == []


# ---------------------------------------------------------------------------
# _alert_missing_orphan_ops
# ---------------------------------------------------------------------------


class TestAlertMissingOrphanOps:
    """Tests for _alert_missing_orphan_ops structured-log alert helper."""

    def test_emits_error_per_orphan(self):
        mock_log = MagicMock(spec=logging.Logger)
        orphans = [
            {"account_id": "acc_a", "session_id": "sess_a"},
            {"account_id": "acc_b", "session_id": "sess_b"},
        ]
        cli._alert_missing_orphan_ops(orphans, log=mock_log)
        assert mock_log.error.call_count == 2

    def test_no_calls_for_empty_list(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._alert_missing_orphan_ops([], log=mock_log)
        mock_log.error.assert_not_called()

    def test_alert_kind_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._alert_missing_orphan_ops(
            [{"account_id": "acc_x", "session_id": "sess_x"}],
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("alert_kind") == "chat.orphan_scan.missing_side_table"

    def test_pageable_flag_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._alert_missing_orphan_ops(
            [{"account_id": "acc_x", "session_id": "sess_x"}],
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("pageable") is True

    def test_account_id_and_session_id_in_extra(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._alert_missing_orphan_ops(
            [{"account_id": "acc_check", "session_id": "sess_check"}],
            log=mock_log,
        )
        _, kwargs = mock_log.error.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("account_id") == "acc_check"
        assert json_fields.get("session_id") == "sess_check"

    def test_uses_module_logger_when_none_provided(self):
        """Falls back to module-level logger without raising."""
        orphans = [{"account_id": "acc_z", "session_id": "sess_z"}]
        # Should not raise; we just verify it runs without error.
        cli._alert_missing_orphan_ops(orphans, log=None)


# ---------------------------------------------------------------------------
# _emit_completion_log
# ---------------------------------------------------------------------------


class TestEmitCompletionLog:
    """Tests for _emit_completion_log structured-log helper."""

    def _summary(self, **overrides) -> dict:
        base = {
            "tombstoned_cleaned": 0,
            "tombstoned_in_grace": 0,
            "missing_orphans": 0,
            "all_clean": 5,
            "errored": 0,
        }
        base.update(overrides)
        return base

    def test_emits_info_level(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(), log=mock_log)
        mock_log.info.assert_called_once()

    def test_success_true_when_no_errors(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(errored=0), log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields.get("success") is True

    def test_success_false_when_errored(self):
        mock_log = MagicMock(spec=logging.Logger)
        cli._emit_completion_log(self._summary(errored=2), log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        # success=False is included because False == 0 passes the to_dict filter.
        assert json_fields.get("success") is False

    def test_all_summary_keys_present(self):
        mock_log = MagicMock(spec=logging.Logger)
        summary = self._summary(
            tombstoned_cleaned=3,
            tombstoned_in_grace=1,
            missing_orphans=2,
            all_clean=10,
            errored=0,
        )
        cli._emit_completion_log(summary, log=mock_log)
        _, kwargs = mock_log.info.call_args
        json_fields = kwargs["extra"]["json_fields"]
        assert json_fields["tombstoned_cleaned"] == 3
        assert json_fields["tombstoned_in_grace"] == 1
        assert json_fields["missing_orphans"] == 2
        assert json_fields["all_clean"] == 10
        assert json_fields["errored"] == 0

    def test_uses_module_logger_when_none_provided(self):
        """Falls back to module-level logger without raising."""
        cli._emit_completion_log(self._summary(), log=None)


# ---------------------------------------------------------------------------
# Orchestrator ID-validation guards (unit-level, no Firestore/ADK)
# ---------------------------------------------------------------------------


class TestFirestoreIdRegex:
    """Boundary tests for the _FIRESTORE_ID_RE constant itself."""

    def test_invalid_account_id_rejected(self):
        """account_id containing '/' fails the regex."""
        assert not cli._FIRESTORE_ID_RE.match("bad/account/id")

    def test_valid_account_id_passes_regex(self):
        """Standard account_id pattern matches the validation regex."""
        assert cli._FIRESTORE_ID_RE.match("acc_abc123")

    def test_session_id_with_slash_fails_regex(self):
        """session_id containing '/' is rejected by _FIRESTORE_ID_RE."""
        assert not cli._FIRESTORE_ID_RE.match("sess/evil")

    def test_session_id_with_double_dot_fails_regex(self):
        """session_id containing '..' is rejected by _FIRESTORE_ID_RE."""
        assert not cli._FIRESTORE_ID_RE.match("..")

    def test_max_length_boundary(self):
        """128-char ID is accepted; 129-char ID is rejected."""
        assert cli._FIRESTORE_ID_RE.match("a" * 128)
        assert not cli._FIRESTORE_ID_RE.match("a" * 129)


# ---------------------------------------------------------------------------
# _FakeAdkSessionService helper (reused across test classes)
# ---------------------------------------------------------------------------


class _FakeAdkSessionService:
    async def list_sessions(self, app_name: str, user_id: str):
        return self._sessions_by_user.get(user_id, [])

    async def delete_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> None:
        # Matches the real VertexAiSessionService signature (user_id required) so
        # dropping it in the script raises TypeError here too.
        self.deleted.append((app_name, session_id))

    def __init__(self):
        self._sessions_by_user: dict = {}
        self.deleted: list = []

    def add_session(self, user_id: str, session) -> None:
        self._sessions_by_user.setdefault(user_id, []).append(session)


# ---------------------------------------------------------------------------
# _FakeFirestoreDb helper (users-collection iteration; no path construction)
# ---------------------------------------------------------------------------


class _FakeUserDoc:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class _FakeUsersCollection:
    def __init__(self, user_docs: list[_FakeUserDoc]):
        self._user_docs = user_docs

    def stream(self):
        return iter(self._user_docs)


class _FakeFirestoreDb:
    """Yields users; records any document() path so tests can assert none built."""

    def __init__(self, user_docs: list[_FakeUserDoc]):
        self._user_docs = user_docs
        self.documents_accessed: list[str] = []

    def collection(self, name: str) -> _FakeUsersCollection:
        assert name == "users"
        return _FakeUsersCollection(self._user_docs)

    def document(self, path: str):
        # The path-traversal guard must reject a session before any Firestore
        # path is built; recording here lets tests assert this list stays empty.
        self.documents_accessed.append(path)
        raise AssertionError(f"unexpected db.document({path!r})")


def _user_with_account(doc_id: str, account_id: str) -> _FakeUserDoc:
    return _FakeUserDoc(
        doc_id,
        {"permissions": {"account_permissions": {account_id: {"role": "member"}}}},
    )


# ---------------------------------------------------------------------------
# --account-id scoping (_iter_users)
# ---------------------------------------------------------------------------


class TestAccountIdScoping:
    """_iter_users filters by account permission when account_id is given."""

    def test_account_id_yields_only_permitted_users(self):
        db = _FakeFirestoreDb(
            [
                _user_with_account("uid_in", "acc_target"),
                _user_with_account("uid_out", "acc_other"),
            ]
        )
        assert [uid for uid, _ in cli._iter_users(db, "acc_target")] == ["uid_in"]

    def test_none_account_id_yields_all_users(self):
        db = _FakeFirestoreDb(
            [
                _user_with_account("uid_a", "acc_a"),
                _user_with_account("uid_b", "acc_b"),
            ]
        )
        assert [uid for uid, _ in cli._iter_users(db, None)] == ["uid_a", "uid_b"]


# ---------------------------------------------------------------------------
# Path-traversal guard — orchestrator-level (proves the regex is wired in)
# ---------------------------------------------------------------------------


class TestOrchestratorPathTraversalGuard:
    """scan_for_adk_session_orphans rejects malicious IDs before any Firestore path."""

    def _run(self, session_account_id: str, session_id: str = "sess_ok"):
        db = _FakeFirestoreDb([_user_with_account("uid_test", "acc_target")])
        svc = _FakeAdkSessionService()
        svc.add_session(
            "uid_test",
            SimpleNamespace(id=session_id, state={"account_id": session_account_id}),
        )
        summary = cli.scan_for_adk_session_orphans(
            db, svc, account_id="acc_target", _now=_NOW
        )
        return db, svc, summary

    def test_account_id_with_slash_errors_without_deleting(self):
        db, svc, summary = self._run("evil/../../etc")
        assert summary["errored"] == 1
        assert summary["tombstoned_cleaned"] == 0
        assert db.documents_accessed == []
        assert svc.deleted == []

    def test_session_id_with_slash_errors_without_deleting(self):
        db, svc, summary = self._run("acc_target", session_id="sess/../evil")
        assert summary["errored"] == 1
        assert summary["tombstoned_cleaned"] == 0
        assert db.documents_accessed == []
        assert svc.deleted == []
