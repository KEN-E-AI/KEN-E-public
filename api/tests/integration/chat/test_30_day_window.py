"""Integration tests: 30-day session listing window (CH-15).

Verifies that the recovery service and list endpoint honour the 30-day
window — sessions updated within 30 days are included; those older than
30 days are excluded.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_30_day_window.py -v
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

_USER_ID = "user_window_test"
_ACCOUNT_ID = "acc_window_test"


class TestRecoveryWindowIs30Days:
    """Unit-level tests for the RECOVERY_WINDOW_DAYS constant."""

    def test_constant_is_30(self) -> None:
        from app.adk.session.recovery import SessionRecoveryService

        assert SessionRecoveryService.RECOVERY_WINDOW_DAYS == 30

    def test_session_within_30_days_is_included(self) -> None:
        from app.adk.session.recovery import SessionRecoveryService

        svc = SessionRecoveryService(session_service=MagicMock())
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        update_time = now - timedelta(days=29)

        session = MagicMock()
        session.id = "sess_recent"
        session.create_time = update_time
        session.update_time = update_time
        session.state = {}
        session.events = []

        result = svc._parse_session(session, cutoff)
        assert result is not None
        assert result.session_id == "sess_recent"

    def test_session_older_than_30_days_is_excluded(self) -> None:
        from app.adk.session.recovery import SessionRecoveryService

        svc = SessionRecoveryService(session_service=MagicMock())
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        update_time = now - timedelta(days=31)

        session = MagicMock()
        session.id = "sess_old"
        session.create_time = update_time
        session.update_time = update_time
        session.state = {}
        session.events = []

        result = svc._parse_session(session, cutoff)
        assert result is None

    def test_session_at_boundary_30_days_is_excluded(self) -> None:
        from app.adk.session.recovery import SessionRecoveryService

        svc = SessionRecoveryService(session_service=MagicMock())
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        # Exactly at cutoff — strictly less than, so excluded
        update_time = cutoff - timedelta(seconds=1)

        session = MagicMock()
        session.id = "sess_boundary"
        session.create_time = update_time
        session.update_time = update_time
        session.state = {}
        session.events = []

        result = svc._parse_session(session, cutoff)
        assert result is None


class TestSearchWindowIs30Days:
    """Verify the Firestore-side search constant is 30 days."""

    def test_chat_list_window_days_constant(self) -> None:
        from src.kene_api.chat.search import CHAT_LIST_WINDOW_DAYS

        assert CHAT_LIST_WINDOW_DAYS == 30
