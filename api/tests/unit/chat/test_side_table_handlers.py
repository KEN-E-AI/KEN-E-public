"""Unit tests for side_table_handlers.apply_side_table_update (CH-PRD-01 §7 AC-5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.kene_api.chat.side_table_handlers import (
    _reconstruct_increments,
    _sha256_hex,
    apply_side_table_update,
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


class TestReconstructIncrements:
    def test_converts_increment_wire_sentinel(self) -> None:
        from google.cloud import firestore

        delta = {"message_count": {"_increment": 1}}
        result = _reconstruct_increments(delta)

        assert isinstance(result["message_count"], firestore.Increment)

    def test_passes_through_non_increment_values(self) -> None:
        delta = {"title": "My session", "updated_at": "2025-01-01T00:00:00Z"}
        result = _reconstruct_increments(delta)

        assert result["title"] == "My session"
        assert result["updated_at"] == "2025-01-01T00:00:00Z"

    def test_mixed_delta(self) -> None:
        from google.cloud import firestore

        delta = {
            "message_count": {"_increment": 3},
            "title": "Hello",
        }
        result = _reconstruct_increments(delta)

        assert isinstance(result["message_count"], firestore.Increment)
        assert result["title"] == "Hello"

    def test_dict_without_increment_key_not_converted(self) -> None:
        from google.cloud import firestore

        delta = {"meta": {"key": "value"}}
        result = _reconstruct_increments(delta)

        assert result["meta"] == {"key": "value"}
        assert not isinstance(result["meta"], firestore.Increment)


class TestApplySideTableUpdate:
    def _make_db(self, idem_doc_exists: bool = False, expires_at_future: bool = False):
        db = MagicMock()

        idem_snap = MagicMock()
        idem_snap.exists = idem_doc_exists
        now = datetime.now(timezone.utc)
        idem_snap.to_dict.return_value = {
            "applied_at": now - timedelta(hours=1),
            "expires_at": now + timedelta(hours=1) if expires_at_future else now - timedelta(hours=1),
        }

        idem_ref = MagicMock()
        idem_ref.get.return_value = idem_snap

        db.collection.return_value.document.return_value = idem_ref
        return db

    def _patch_svc(self):
        svc = MagicMock()
        return patch(
            "src.kene_api.chat.side_table_handlers.get_chat_side_table_service",
            return_value=svc,
        ), svc

    def test_applies_delta_when_new_key(self) -> None:
        db = self._make_db(idem_doc_exists=False)
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

    def test_returns_duplicate_when_key_exists_and_not_expired(self) -> None:
        db = self._make_db(idem_doc_exists=True, expires_at_future=True)
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
        db = self._make_db(idem_doc_exists=True, expires_at_future=False)
        ctx, svc = self._patch_svc()

        with ctx:
            result = apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={"title": "New title"},
                idempotency_key="expired-key",
            )

        assert result["status"] == "applied"
        svc.update_from_delta.assert_called_once()

    def test_writes_idempotency_doc_on_apply(self) -> None:
        db = self._make_db(idem_doc_exists=False)
        idem_ref = db.collection.return_value.document.return_value
        ctx, svc = self._patch_svc()

        with ctx:
            apply_side_table_update(
                db=db,
                session_id="sess_1",
                account_id="acc_1",
                delta={},
                idempotency_key="new-key",
            )

        idem_ref.set.assert_called_once()
        written = idem_ref.set.call_args[0][0]
        assert "expires_at" in written
        assert "applied_at" in written
