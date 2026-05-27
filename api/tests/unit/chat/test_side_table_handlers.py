"""Unit tests for side_table_handlers.apply_side_table_update (CH-PRD-01 §7 AC-5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import google.api_core.exceptions
from src.kene_api.chat.side_table_handlers import (
    _sha256_hex,
    apply_side_table_update,
)

from shared.turn_delta import TurnDelta

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_turn_delta(**overrides: object) -> TurnDelta:
    return TurnDelta(
        last_agent_stopped_at=_NOW,
        updated_at=_NOW,
        last_agent_message_at=_NOW,
        **overrides,  # type: ignore[arg-type]
    )


class TestSha256Hex:
    def test_deterministic(self) -> None:
        assert _sha256_hex("key") == _sha256_hex("key")

    def test_different_inputs_different_outputs(self) -> None:
        assert _sha256_hex("key_a") != _sha256_hex("key_b")

    def test_returns_64_char_hex(self) -> None:
        result = _sha256_hex("hello")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestApplySideTableUpdate:
    def _make_db(
        self, create_raises: bool = False, expire_at_future: bool = True
    ) -> MagicMock:
        """Build a mock Firestore client.

        create_raises=True simulates AlreadyExists (duplicate key).
        expire_at_future controls whether the stored idempotency doc is still valid.
        """
        db = MagicMock()
        idem_ref = MagicMock()

        if create_raises:
            idem_ref.create.side_effect = google.api_core.exceptions.AlreadyExists(
                "duplicate"
            )
            now = datetime.now(timezone.utc)
            stored_snap = MagicMock()
            stored_snap.exists = True
            stored_snap.to_dict.return_value = {
                "applied_at": now - timedelta(hours=1),
                "expires_at": (
                    now + timedelta(hours=1)
                    if expire_at_future
                    else now - timedelta(hours=1)
                ),
            }
            idem_ref.get.return_value = stored_snap
        else:
            idem_ref.create.return_value = None

        db.collection.return_value.document.return_value = idem_ref
        return db

    def _patch_svc(self) -> tuple[object, MagicMock]:
        svc = MagicMock()
        return patch(
            "src.kene_api.chat.side_table_handlers.get_chat_side_table_service",
            return_value=svc,
        ), svc

    def test_applies_delta_when_new_key(self) -> None:
        db = self._make_db(create_raises=False)
        ctx, svc = self._patch_svc()

        with ctx:
            result = apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={"message_count": {"_increment": 1}},
                idempotency_key="unique-key-1",
            )

        assert result["status"] == "applied"
        svc.update_from_delta.assert_called_once()

    def test_turn_delta_instance_applies_via_to_firestore_delta(self) -> None:
        from google.cloud import firestore

        db = self._make_db(create_raises=False)
        ctx, svc = self._patch_svc()
        delta = _make_turn_delta(input_tokens_increment=100, message_count=2)

        with ctx:
            result = apply_side_table_update(
                db=db,
                session_id="sess_td",
                account_id="acc_td",
                delta=delta,
                idempotency_key="turn-delta-key-1",
            )

        assert result["status"] == "applied"
        svc.update_from_delta.assert_called_once()
        _, call_kwargs = svc.update_from_delta.call_args
        fs_delta = call_kwargs["delta"]
        assert isinstance(fs_delta["input_tokens_total"], firestore.Increment)
        assert isinstance(fs_delta["message_count"], firestore.Increment)
        assert isinstance(fs_delta["last_agent_stopped_at"], datetime)

    def test_returns_duplicate_when_key_exists_and_not_expired(self) -> None:
        db = self._make_db(create_raises=True, expire_at_future=True)
        ctx, svc = self._patch_svc()

        with ctx:
            result = apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={"message_count": {"_increment": 1}},
                idempotency_key="existing-key",
            )

        assert result["status"] == "duplicate"
        svc.update_from_delta.assert_not_called()

    def test_applies_when_key_exists_but_expired(self) -> None:
        db = self._make_db(create_raises=True, expire_at_future=False)
        ctx, svc = self._patch_svc()

        with ctx:
            result = apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={"message_count": {"_increment": 1}},
                idempotency_key="expired-key",
            )

        assert result["status"] == "applied"
        svc.update_from_delta.assert_called_once()

    def test_writes_idempotency_doc_on_apply(self) -> None:
        db = self._make_db(create_raises=False)
        idem_ref = db.collection.return_value.document.return_value
        ctx, _svc = self._patch_svc()

        with ctx:
            apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={"message_count": {"_increment": 1}},
                idempotency_key="new-key",
            )

        idem_ref.create.assert_called_once()
        written = idem_ref.create.call_args[0][0]
        assert "expires_at" in written
        assert "applied_at" in written


# ---------------------------------------------------------------------------
# AC-8 stop-stamp coverage. Relocated from api/tests/integration/chat/ — these
# are pure unit tests (mocked Firestore client), not emulator-backed
# integration tests. They cover the stop-stamp delta written by the
# /completions finally block and the inline sentinel reconstruction it relies on.
# ---------------------------------------------------------------------------


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

        with patch(
            "src.kene_api.chat.side_table_handlers.get_chat_side_table_service"
        ) as mock_svc_fn:
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
            delta=delta,  # datetime values pass through the inline sentinel reconstruction unchanged
        )

    def test_duplicate_idempotency_key_returns_duplicate(self) -> None:
        """A repeated idempotency key returns {'status': 'duplicate'} without re-applying."""
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # expires_future must be beyond the real wall-clock time inside apply_side_table_update,
        # which calls datetime.now(timezone.utc) at invocation time.  Use a far-future date.
        expires_future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        session_id = "sess_ac8_dup"
        account_id = "acc_ac8_dup"

        mock_idem_ref = MagicMock()
        mock_idem_ref.create.side_effect = google.api_core.exceptions.AlreadyExists(
            "exists"
        )
        stored_doc = MagicMock()
        stored_doc.exists = True
        stored_doc.to_dict.return_value = {
            "applied_at": now,
            "expires_at": expires_future,
        }
        mock_idem_ref.get.return_value = stored_doc

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_idem_ref

        with patch(
            "src.kene_api.chat.side_table_handlers.get_chat_side_table_service"
        ) as mock_svc_fn:
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


class TestInlineSentinelReconstruction:
    """apply_side_table_update's dict path reconstructs wire sentinels correctly."""

    def _patch_svc(self) -> tuple[object, MagicMock]:
        svc = MagicMock()
        return patch(
            "src.kene_api.chat.side_table_handlers.get_chat_side_table_service",
            return_value=svc,
        ), svc

    def _make_db(self) -> MagicMock:
        db = MagicMock()
        db.collection.return_value.document.return_value.create.return_value = None
        return db

    def test_increment_sentinel_converted(self) -> None:
        from google.cloud import firestore

        ctx, svc = self._patch_svc()
        with ctx:
            apply_side_table_update(
                db=self._make_db(),
                session_id="sess_incr",
                account_id="acc_incr",
                delta={"message_count": {"_increment": 5}},
                idempotency_key="incr-key-1",
            )
        _, kw = svc.update_from_delta.call_args
        assert isinstance(kw["delta"]["message_count"], firestore.Increment)

    def test_isoformat_sentinel_converted_to_datetime(self) -> None:
        now_iso = "2026-01-01T00:00:00+00:00"
        ctx, svc = self._patch_svc()
        with ctx:
            apply_side_table_update(
                db=self._make_db(),
                session_id="sess_iso",
                account_id="acc_iso",
                delta={"last_agent_started_at": {"_isoformat": now_iso}},
                idempotency_key="iso-key-1",
            )
        _, kw = svc.update_from_delta.call_args
        val = kw["delta"]["last_agent_started_at"]
        assert isinstance(val, datetime)
        assert val == datetime.fromisoformat(now_iso)

    def test_native_datetime_passes_through_unchanged(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ctx, svc = self._patch_svc()
        with ctx:
            apply_side_table_update(
                db=self._make_db(),
                session_id="sess_native",
                account_id="acc_native",
                delta={"last_agent_stopped_at": now, "updated_at": now},
                idempotency_key="native-dt-key-1",
            )
        _, kw = svc.update_from_delta.call_args
        assert kw["delta"]["last_agent_stopped_at"] is now
        assert kw["delta"]["updated_at"] is now
