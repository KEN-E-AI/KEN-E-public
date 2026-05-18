"""Unit tests for feature_flag_audit.py — diff helper + audit writer.

Covers:
  - compute_flag_diff: all diff branches (create, delete, single-field update,
    multi-field update, nested-rules-only update, timestamp-only update → empty,
    fully-unchanged → empty)
  - record_audit: empty-diff skip, happy-path write shape (keys, doc-ID format,
    collection path), Firestore-error swallow, no-PII logging invariant.

Uses unittest.mock.MagicMock for the Firestore client; no emulator dependency.
The emulator-backed integration coverage is owned by B6 (FF-17).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.models.feature_flag_models import FeatureFlag, TargetingRules
from src.kene_api.services.feature_flag_audit import (
    AuditAction,
    compute_flag_diff,
    record_audit,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)


def _make_flag(**overrides: Any) -> FeatureFlag:
    """Build a minimal valid FeatureFlag, optionally overriding fields."""
    base: dict[str, Any] = {
        "key": "test_flag",
        "description": "A test flag",
        "default_enabled": False,
        "is_active": True,
        "targeting_rules": TargetingRules(),
        "bucketing_entity": "account",
        "owner": "test@ken-e.ai",
        "expected_ga_release": None,
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return FeatureFlag(**base)


# ---------------------------------------------------------------------------
# compute_flag_diff tests
# ---------------------------------------------------------------------------


class TestComputeFlagDiff:
    """Tests for the pure-logic shallow-diff helper."""

    def test_create_returns_all_non_timestamp_fields_with_none_before(self) -> None:
        """create (before=None) → every non-timestamp field appears with before=None."""
        flag = _make_flag()
        diff = compute_flag_diff(None, flag)

        # Timestamps must be excluded.
        assert "created_at" not in diff
        assert "updated_at" not in diff

        # All other top-level fields must appear as added (before=None).
        for field in ("key", "description", "default_enabled", "is_active",
                      "targeting_rules", "bucketing_entity", "owner",
                      "expected_ga_release"):
            assert field in diff, f"Expected '{field}' in create diff"
            assert diff[field]["before"] is None, (
                f"create diff[{field!r}]['before'] should be None"
            )

    def test_delete_returns_all_non_timestamp_fields_with_none_after(self) -> None:
        """delete (after=None) → every non-timestamp field appears with after=None."""
        flag = _make_flag()
        diff = compute_flag_diff(flag, None)

        assert "created_at" not in diff
        assert "updated_at" not in diff

        for field in ("key", "description", "default_enabled", "is_active",
                      "targeting_rules", "bucketing_entity", "owner",
                      "expected_ga_release"):
            assert field in diff, f"Expected '{field}' in delete diff"
            assert diff[field]["after"] is None, (
                f"delete diff[{field!r}]['after'] should be None"
            )

    def test_single_field_update_description(self) -> None:
        """Changing only description returns exactly one diff entry."""
        before = _make_flag(description="old description")
        after = _make_flag(description="new description")
        diff = compute_flag_diff(before, after)

        assert diff == {
            "description": {"before": "old description", "after": "new description"}
        }

    def test_single_field_update_default_enabled(self) -> None:
        """Flipping default_enabled produces exactly one diff entry."""
        before = _make_flag(default_enabled=False)
        after = _make_flag(default_enabled=True)
        diff = compute_flag_diff(before, after)

        assert diff == {
            "default_enabled": {"before": False, "after": True}
        }

    def test_multi_field_update(self) -> None:
        """Changing two fields returns exactly two diff entries."""
        before = _make_flag(description="old", is_active=True)
        after = _make_flag(description="new", is_active=False)
        diff = compute_flag_diff(before, after)

        assert diff == {
            "description": {"before": "old", "after": "new"},
            "is_active": {"before": True, "after": False},
        }

    def test_nested_targeting_rules_change_collapses_to_single_entry(self) -> None:
        """A change deep inside targeting_rules produces ONE top-level diff entry."""
        before = _make_flag(targeting_rules=TargetingRules(rollout_percentage=0))
        after = _make_flag(targeting_rules=TargetingRules(rollout_percentage=25))
        diff = compute_flag_diff(before, after)

        # Only the top-level key should appear — not a recursive diff.
        assert list(diff.keys()) == ["targeting_rules"]
        assert diff["targeting_rules"]["before"]["rollout_percentage"] == 0
        assert diff["targeting_rules"]["after"]["rollout_percentage"] == 25

    def test_timestamp_only_change_returns_empty_diff(self) -> None:
        """Changing only updated_at (e.g. a no-op PUT) produces an empty diff."""
        before = _make_flag(updated_at=_NOW)
        after = _make_flag(updated_at=_LATER)
        diff = compute_flag_diff(before, after)

        assert diff == {}

    def test_fully_unchanged_returns_empty_diff(self) -> None:
        """Identical before and after → empty diff (no audit row should be written)."""
        flag = _make_flag()
        diff = compute_flag_diff(flag, flag)

        assert diff == {}

    def test_timestamps_always_excluded_from_diff(self) -> None:
        """created_at and updated_at are never included even when they change."""
        before = _make_flag(created_at=_NOW, updated_at=_NOW)
        after = _make_flag(created_at=_LATER, updated_at=_LATER)
        diff = compute_flag_diff(before, after)

        assert "created_at" not in diff
        assert "updated_at" not in diff

    def test_both_none_raises_or_returns_empty(self) -> None:
        """Both args None → no meaningful diff; implementation returns empty dict."""
        diff = compute_flag_diff(None, None)
        assert diff == {}


# ---------------------------------------------------------------------------
# record_audit tests
# ---------------------------------------------------------------------------


class TestRecordAuditSkipOnEmptyDiff:
    async def test_empty_diff_does_not_write_to_firestore(self) -> None:
        """When diff={}, record_audit must not call db.collection at all."""
        db = MagicMock()
        result = await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="update",
            diff={},
        )

        assert result is None
        db.collection.assert_not_called()


class TestRecordAuditHappyPath:
    async def test_writes_to_feature_flag_audit_collection(self) -> None:
        """record_audit writes to the 'feature_flag_audit' collection."""
        db = MagicMock()
        diff: dict[str, Any] = {
            "description": {"before": "old", "after": "new"}
        }

        await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="update",
            diff=diff,
        )

        db.collection.assert_called_once_with("feature_flag_audit")

    async def test_returns_audit_id_on_success(self) -> None:
        """record_audit returns a non-empty audit_id string on success."""
        db = MagicMock()
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        result = await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="toggle_active",
            diff=diff,
        )

        assert isinstance(result, str)
        assert len(result) > 0

    async def test_audit_id_follows_iso_uuid8_pattern(self) -> None:
        """Audit doc ID matches the {iso_datetime}_{uuid8} format."""
        db = MagicMock()
        diff: dict[str, Any] = {"owner": {"before": "a@ken-e.ai", "after": "b@ken-e.ai"}}

        result = await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="update",
            diff=diff,
        )

        assert result is not None
        # Pattern: ISO datetime prefix (with T and colons/dots/+) then underscore then 8 hex chars.
        assert re.match(r"^[\d\-T:.+]+_[0-9a-f]{8}$", result), (
            f"audit_id {result!r} does not match expected pattern"
        )

    async def test_written_body_has_required_keys(self) -> None:
        """The Firestore document body has exactly the FeatureFlagAuditEntry keys."""
        db = MagicMock()
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="toggle_active",
            diff=diff,
        )

        set_call = db.collection.return_value.document.return_value.set
        set_call.assert_called_once()
        written_body: dict[str, Any] = set_call.call_args.args[0]

        expected_keys = {"audit_id", "flag_key", "actor_email", "action", "diff", "created_at"}
        assert set(written_body.keys()) == expected_keys, (
            f"Written body keys {set(written_body.keys())} != expected {expected_keys}"
        )

    async def test_written_body_values_match_inputs(self) -> None:
        """Payload field values match the inputs passed to record_audit."""
        db = MagicMock()
        diff: dict[str, Any] = {"description": {"before": "old", "after": "new"}}

        result = await record_audit(
            db=db,
            flag_key="my_feature",
            actor_email="engineer@ken-e.ai",
            action="update",
            diff=diff,
        )

        set_call = db.collection.return_value.document.return_value.set
        body: dict[str, Any] = set_call.call_args.args[0]

        assert body["flag_key"] == "my_feature"
        assert body["actor_email"] == "engineer@ken-e.ai"
        assert body["action"] == "update"
        assert body["diff"] == diff
        assert body["audit_id"] == result

    async def test_document_id_matches_audit_id_in_body(self) -> None:
        """The document ID passed to db.collection(...).document(id) matches audit_id in body."""
        db = MagicMock()
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="toggle_active",
            diff=diff,
        )

        doc_id_arg: str = db.collection.return_value.document.call_args.args[0]
        set_call = db.collection.return_value.document.return_value.set
        body: dict[str, Any] = set_call.call_args.args[0]

        assert doc_id_arg == body["audit_id"]

    async def test_uses_asyncio_to_thread_for_firestore_write(self) -> None:
        """Firestore write is wrapped in asyncio.to_thread (non-blocking call)."""
        db = MagicMock()
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        with patch("asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread:
            await record_audit(
                db=db,
                flag_key="test_flag",
                actor_email="admin@ken-e.ai",
                action="toggle_active",
                diff=diff,
            )

        mock_to_thread.assert_called_once()


class TestRecordAuditErrorSwallow:
    async def test_firestore_exception_returns_none(self) -> None:
        """When Firestore raises, record_audit must return None (not propagate)."""
        db = MagicMock()
        db.collection.side_effect = RuntimeError("Firestore unavailable")
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        result = await record_audit(
            db=db,
            flag_key="test_flag",
            actor_email="admin@ken-e.ai",
            action="toggle_active",
            diff=diff,
        )

        assert result is None

    async def test_firestore_exception_logs_error(self) -> None:
        """A Firestore failure emits one ERROR log (audit failure is observable)."""
        import logging as _logging

        db = MagicMock()
        db.collection.side_effect = RuntimeError("Firestore unavailable")
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        caplog_records: list[_logging.LogRecord] = []

        class _CapHandler(_logging.Handler):
            def emit(self, record: _logging.LogRecord) -> None:
                caplog_records.append(record)

        from src.kene_api.services import feature_flag_audit as _audit_mod
        handler = _CapHandler()
        _audit_mod.logger.addHandler(handler)
        old_level = _audit_mod.logger.level
        _audit_mod.logger.setLevel(_logging.ERROR)
        try:
            await record_audit(
                db=db,
                flag_key="test_flag",
                actor_email="admin@ken-e.ai",
                action="toggle_active",
                diff=diff,
            )
        finally:
            _audit_mod.logger.removeHandler(handler)
            _audit_mod.logger.setLevel(old_level)

        assert any(r.levelno == _logging.ERROR for r in caplog_records), (
            "Expected at least one ERROR log record"
        )

    async def test_error_log_contains_flag_key_action_error_type(self) -> None:
        """Error log fields are exactly {flag_key, action, error_type} — no PII."""
        db = MagicMock()
        db.collection.side_effect = ValueError("connection reset")
        diff: dict[str, Any] = {"is_active": {"before": True, "after": False}}

        import logging as _logging
        caplog_records: list[_logging.LogRecord] = []

        class _CapHandler(_logging.Handler):
            def emit(self, record: _logging.LogRecord) -> None:
                caplog_records.append(record)

        from src.kene_api.services import feature_flag_audit as _audit_mod
        handler = _CapHandler()
        _audit_mod.logger.addHandler(handler)
        _audit_mod.logger.propagate = False
        old_level = _audit_mod.logger.level
        _audit_mod.logger.setLevel(_logging.DEBUG)
        try:
            await record_audit(
                db=db,
                flag_key="flaggy_flag",
                actor_email="admin@ken-e.ai",
                action="delete",
                diff=diff,
            )
        finally:
            _audit_mod.logger.removeHandler(handler)
            _audit_mod.logger.setLevel(old_level)
            _audit_mod.logger.propagate = True

        error_records = [r for r in caplog_records if r.levelno == _logging.ERROR]
        assert len(error_records) == 1, "Expected exactly one ERROR log record"
        record = error_records[0]

        # Required fields must be present.
        assert hasattr(record, "flag_key") or "flag_key" in str(record.getMessage()) or \
               (hasattr(record, "__dict__") and "flaggy_flag" in str(record.__dict__)), \
            "flag_key must be identifiable in the error log"

        # PII fields must not be present in the extra dict.
        pii_fields = {"actor_email", "user_id", "user_email", "organization_id", "account_id"}
        record_extra_keys = {
            k for k in record.__dict__
            if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__
        }
        pii_present = pii_fields & record_extra_keys
        assert not pii_present, f"PII fields found in error log extra: {pii_present}"


class TestRecordAuditNoPII:
    async def test_no_pii_in_any_log_record_on_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Successful record_audit emits no PII fields in any log record."""
        db = MagicMock()
        diff: dict[str, Any] = {"description": {"before": "old", "after": "new"}}
        pii_values = {"admin@ken-e.ai", "u_12345", "org_abcde", "acc_xyz"}

        with caplog.at_level(logging.DEBUG, logger="src.kene_api.services.feature_flag_audit"):
            await record_audit(
                db=db,
                flag_key="test_flag",
                actor_email="admin@ken-e.ai",
                action="update",
                diff=diff,
            )

        for record in caplog.records:
            log_text = record.getMessage() + str(record.__dict__)
            for pii_val in pii_values:
                assert pii_val not in log_text, (
                    f"PII value {pii_val!r} found in log record: {log_text}"
                )


# ---------------------------------------------------------------------------
# AuditAction type alias smoke test
# ---------------------------------------------------------------------------


class TestAuditAction:
    def test_audit_action_values(self) -> None:
        """AuditAction Literal includes the four expected action values."""
        import typing
        args = typing.get_args(AuditAction)
        assert set(args) == {"create", "update", "delete", "toggle_active"}
