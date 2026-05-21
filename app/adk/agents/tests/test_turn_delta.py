"""Unit tests for shared.turn_delta.TurnDelta (CH-PRD-01 §7 AC-3).

Covers:
  - Wire round-trip: model_dump(mode="json", by_alias=True) produces legacy sentinel dict
  - Firestore-native output: to_firestore_delta() returns datetime + Increment types
  - extra="forbid" rejects unknown keys at parse time (HTTP 422 surface)
  - Optional compaction fields omitted from to_wire_dict() when None
  - Sentinel parsing: {"_increment": n} and {"_isoformat": "..."} round-trip correctly
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from shared.turn_delta import TurnDelta

_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_NOW_ISO = _NOW.isoformat()


def _minimal(**overrides: object) -> TurnDelta:
    """Build a minimal TurnDelta with all required fields."""
    return TurnDelta(
        last_agent_stopped_at=_NOW,
        updated_at=_NOW,
        last_agent_message_at=_NOW,
        **overrides,  # type: ignore[arg-type]
    )


class TestWireRoundTrip:
    def test_default_fields_produce_zero_increments(self) -> None:
        wire = _minimal().to_wire_dict()
        assert wire["input_tokens_total"] == {"_increment": 0}
        assert wire["output_tokens_total"] == {"_increment": 0}
        assert wire["reasoning_tokens_total"] == {"_increment": 0}
        assert wire["tool_call_count"] == {"_increment": 0}
        assert wire["message_count"] == {"_increment": 0}
        assert wire["current_context_tokens"] == {"_increment": 0}

    def test_datetime_fields_emit_isoformat_sentinel(self) -> None:
        wire = _minimal().to_wire_dict()
        for key in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            assert wire[key] == {"_isoformat": _NOW_ISO}, f"{key} wrong sentinel"

    def test_last_message_preview_is_plain_string(self) -> None:
        wire = _minimal(last_message_preview="hello").to_wire_dict()
        assert wire["last_message_preview"] == "hello"

    def test_full_wire_dict_matches_legacy_format(self) -> None:
        """Byte-for-byte identity with the legacy hand-built sentinel dict."""
        delta = TurnDelta(
            last_agent_stopped_at=_NOW,
            updated_at=_NOW,
            last_agent_message_at=_NOW,
            input_tokens_increment=280,
            output_tokens_increment=130,
            reasoning_tokens_increment=30,
            tool_call_count=3,
            message_count=2,
            current_context_tokens=440,
            last_message_preview="hello",
        )
        now_sentinel = {"_isoformat": _NOW_ISO}
        assert delta.to_wire_dict() == {
            "last_agent_stopped_at": now_sentinel,
            "updated_at": now_sentinel,
            "last_agent_message_at": now_sentinel,
            "input_tokens_total": {"_increment": 280},
            "output_tokens_total": {"_increment": 130},
            "reasoning_tokens_total": {"_increment": 30},
            "tool_call_count": {"_increment": 3},
            "message_count": {"_increment": 2},
            "current_context_tokens": {"_increment": 440},
            "last_message_preview": "hello",
        }

    def test_compaction_fields_absent_when_none(self) -> None:
        wire = _minimal().to_wire_dict()
        assert "latest_summary" not in wire
        assert "summary_updated_at" not in wire
        assert "compaction_count" not in wire

    def test_compaction_fields_present_when_set(self) -> None:
        delta = _minimal(
            latest_summary="This turn had a compaction.",
            summary_updated_at=_NOW,
            compaction_count=1,
        )
        wire = delta.to_wire_dict()
        assert wire["latest_summary"] == "This turn had a compaction."
        assert wire["summary_updated_at"] == {"_isoformat": _NOW_ISO}
        assert wire["compaction_count"] == {"_increment": 1}


class TestFirestoreNativeOutput:
    def test_datetime_fields_are_datetime_objects(self) -> None:
        fs = _minimal().to_firestore_delta()
        for key in ("last_agent_stopped_at", "updated_at", "last_agent_message_at"):
            assert isinstance(fs[key], datetime), f"{key} should be datetime"
            assert fs[key] == _NOW

    def test_counter_fields_are_increment_objects(self) -> None:
        from google.cloud import firestore

        delta = TurnDelta(
            last_agent_stopped_at=_NOW,
            updated_at=_NOW,
            last_agent_message_at=_NOW,
            input_tokens_increment=5,
            output_tokens_increment=3,
            tool_call_count=2,
        )
        fs = delta.to_firestore_delta()
        assert isinstance(fs["input_tokens_total"], firestore.Increment)
        assert isinstance(fs["output_tokens_total"], firestore.Increment)
        assert isinstance(fs["tool_call_count"], firestore.Increment)

    def test_compaction_count_is_increment_when_present(self) -> None:
        from google.cloud import firestore

        delta = _minimal(compaction_count=1)
        fs = delta.to_firestore_delta()
        assert isinstance(fs["compaction_count"], firestore.Increment)

    def test_optional_compaction_fields_absent_from_firestore_delta(self) -> None:
        fs = _minimal().to_firestore_delta()
        assert "latest_summary" not in fs
        assert "summary_updated_at" not in fs
        assert "compaction_count" not in fs


class TestExtraForbid:
    def test_unknown_key_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TurnDelta(
                last_agent_stopped_at=_NOW,
                updated_at=_NOW,
                last_agent_message_at=_NOW,
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_protected_ownership_field_rejected(self) -> None:
        """user_id (ownership field) must never be accepted via TurnDelta."""
        with pytest.raises(ValidationError):
            TurnDelta(
                last_agent_stopped_at=_NOW,
                updated_at=_NOW,
                last_agent_message_at=_NOW,
                user_id="some-user",  # type: ignore[call-arg]
            )


class TestSentinelParsing:
    """TurnDelta can be round-tripped through JSON via Pydantic parsing."""

    def test_parse_from_wire_dict(self) -> None:
        """Parsing a wire-format dict (as sent over HTTP) produces correct field values."""
        wire = {
            "last_agent_stopped_at": {"_isoformat": _NOW_ISO},
            "updated_at": {"_isoformat": _NOW_ISO},
            "last_agent_message_at": {"_isoformat": _NOW_ISO},
            "input_tokens_total": {"_increment": 100},
            "output_tokens_total": {"_increment": 50},
            "reasoning_tokens_total": {"_increment": 10},
            "tool_call_count": {"_increment": 3},
            "message_count": {"_increment": 2},
            "current_context_tokens": {"_increment": 160},
            "last_message_preview": "hello",
        }
        delta = TurnDelta.model_validate(wire)
        assert delta.last_agent_stopped_at == _NOW
        assert delta.input_tokens_increment == 100
        assert delta.output_tokens_increment == 50
        assert delta.reasoning_tokens_increment == 10
        assert delta.tool_call_count == 3
        assert delta.message_count == 2
        assert delta.current_context_tokens == 160
        assert delta.last_message_preview == "hello"

    def test_json_serialise_then_parse_is_identity(self) -> None:
        """Full round-trip: construct → to_wire_dict → parse → same values."""
        original = TurnDelta(
            last_agent_stopped_at=_NOW,
            updated_at=_NOW,
            last_agent_message_at=_NOW,
            input_tokens_increment=42,
            tool_call_count=7,
            last_message_preview="test",
        )
        wire = original.to_wire_dict()
        restored = TurnDelta.model_validate(wire)
        assert restored.input_tokens_increment == original.input_tokens_increment
        assert restored.tool_call_count == original.tool_call_count
        assert restored.last_agent_stopped_at == original.last_agent_stopped_at
        assert restored.last_message_preview == original.last_message_preview

    def test_ge_constraint_rejects_negative_increment(self) -> None:
        with pytest.raises(ValidationError):
            _minimal(input_tokens_increment=-1)
