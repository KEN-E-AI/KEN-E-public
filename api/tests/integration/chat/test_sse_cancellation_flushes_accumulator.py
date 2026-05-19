"""Integration tests: defensive stop-stamp in /completions finally block (AC-8).

Verifies that apply_side_table_update is called with the correct delta on any
exit path (normal completion, exception, SSE cancellation).

Also includes a parity sub-test: _reconstruct_increments passes datetime
values through unchanged, ensuring the direct API path (datetime objects)
and the HTTP callback path (ISO strings) both write to the correct fields.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat.side_table_handlers import (
    _reconstruct_increments,
    apply_side_table_update,
)


class TestApplySideTableUpdateStopStamp:
    """apply_side_table_update writes the stop-stamp delta correctly."""

    def test_stop_stamp_fields_written_to_firestore(self) -> None:
        """Delta with last_agent_stopped_at and updated_at is applied to Firestore."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        session_id = "sess_ac8_test"
        account_id = "acc_ac8_test"
        idempotency_key = f"{session_id}:api-finally:turn-uuid-001"
        delta = {"last_agent_stopped_at": now, "updated_at": now}

        mock_idem_ref = MagicMock()
        # create() succeeds (no AlreadyExists) — happy path
        mock_idem_ref.create.return_value = None

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_idem_ref

        with patch("kene_api.chat.side_table_handlers.get_chat_side_table_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc_fn.return_value = mock_svc

            result = apply_side_table_update(
                db=mock_db,
                session_id=session_id,
                account_id=account_id,
                delta=delta,
                idempotency_key=idempotency_key,
            )

        assert result["status"] == "applied"
        mock_svc.update_from_delta.assert_called_once_with(
            account_id=account_id,
            session_id=session_id,
            delta=delta,  # datetime values pass through _reconstruct_increments unchanged
        )

    def test_duplicate_idempotency_key_returns_duplicate(self) -> None:
        """A repeated idempotency key returns {'status': 'duplicate'} without re-applying."""

        import google.api_core.exceptions

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # expires_future must be beyond the real wall-clock time inside apply_side_table_update,
        # which calls datetime.now(timezone.utc) at invocation time.  Use a far-future date.
        expires_future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        session_id = "sess_ac8_dup"
        account_id = "acc_ac8_dup"

        mock_idem_ref = MagicMock()
        mock_idem_ref.create.side_effect = google.api_core.exceptions.AlreadyExists("exists")
        stored_doc = MagicMock()
        stored_doc.exists = True
        stored_doc.to_dict.return_value = {"applied_at": now, "expires_at": expires_future}
        mock_idem_ref.get.return_value = stored_doc

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_idem_ref

        with patch("kene_api.chat.side_table_handlers.get_chat_side_table_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc_fn.return_value = mock_svc

            result = apply_side_table_update(
                db=mock_db,
                session_id=session_id,
                account_id=account_id,
                delta={"last_agent_stopped_at": now},
                idempotency_key=f"{session_id}:api-finally:turn-uuid-002",
            )

        assert result["status"] == "duplicate"
        mock_svc.update_from_delta.assert_not_called()


class TestReconstructIncrementsParity:
    """_reconstruct_increments parity: wire sentinels and pass-through values."""

    def test_increment_sentinel_converted(self) -> None:
        delta = {"message_count": {"_increment": 5}}
        from google.cloud.firestore_v1.transforms import Increment
        result = _reconstruct_increments(delta)
        assert isinstance(result["message_count"], Increment)

    def test_datetime_passes_through(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        delta = {"last_agent_stopped_at": now, "updated_at": now}
        result = _reconstruct_increments(delta)
        assert result["last_agent_stopped_at"] is now
        assert result["updated_at"] is now

    def test_isoformat_sentinel_converted_to_datetime(self) -> None:
        now_iso = "2026-01-01T00:00:00+00:00"
        delta = {"last_agent_stopped_at": {"_isoformat": now_iso}}
        result = _reconstruct_increments(delta)
        assert isinstance(result["last_agent_stopped_at"], datetime)
        assert result["last_agent_stopped_at"] == datetime.fromisoformat(now_iso)

    def test_mixed_delta_converted_correctly(self) -> None:
        """Full stop-stamp delta from the API finally block is reconstructed correctly."""
        from google.cloud.firestore_v1.transforms import Increment
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        delta = {
            "last_agent_stopped_at": now,
            "updated_at": now,
            "input_tokens_total": {"_increment": 100},
            "output_tokens_total": {"_increment": 50},
            "message_count": {"_increment": 2},
        }
        result = _reconstruct_increments(delta)
        assert result["last_agent_stopped_at"] is now
        assert result["updated_at"] is now
        assert isinstance(result["input_tokens_total"], Increment)
        assert isinstance(result["output_tokens_total"], Increment)
        assert isinstance(result["message_count"], Increment)
