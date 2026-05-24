"""Unit tests for ``routers.skills`` cursor codec helpers.

AC coverage: Decision 5 (cursor round-trip identity + malformed-input handling).

PRD reference:
  docs/design/components/skills/projects/SK-PRD-01-skills-backend.md §8 Unit tests
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from src.kene_api.routers.skills import _decode_cursor, _encode_cursor


class TestCursorRoundTrip:
    def test_round_trip(self) -> None:
        updated_at = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        skill_id = "abc123def456"
        token = _encode_cursor(updated_at, skill_id)
        decoded = _decode_cursor(token)
        assert decoded is not None
        decoded_dt, decoded_id = decoded
        assert decoded_dt == updated_at
        assert decoded_id == skill_id

    def test_round_trip_preserves_microseconds(self) -> None:
        updated_at = datetime(2026, 3, 22, 8, 0, 0, 123456, tzinfo=timezone.utc)
        token = _encode_cursor(updated_at, "skill_xyz")
        decoded = _decode_cursor(token)
        assert decoded is not None
        assert decoded[0] == updated_at


class TestDecodeRejectsInvalidInput:
    def test_empty_string_returns_none(self) -> None:
        assert _decode_cursor("") is None

    def test_not_base64_returns_none(self) -> None:
        assert _decode_cursor("not-valid-base64!!!") is None

    def test_valid_base64_invalid_json_returns_none(self) -> None:
        garbage = base64.urlsafe_b64encode(b"not json").decode()
        assert _decode_cursor(garbage) is None

    def test_missing_updated_at_returns_none(self) -> None:
        payload = json.dumps({"skill_id": "abc"})
        token = base64.urlsafe_b64encode(payload.encode()).decode()
        assert _decode_cursor(token) is None

    def test_missing_skill_id_returns_none(self) -> None:
        payload = json.dumps({"updated_at": "2026-01-01T00:00:00+00:00"})
        token = base64.urlsafe_b64encode(payload.encode()).decode()
        assert _decode_cursor(token) is None

    def test_invalid_datetime_format_returns_none(self) -> None:
        payload = json.dumps({"updated_at": "not-a-date", "skill_id": "abc"})
        token = base64.urlsafe_b64encode(payload.encode()).decode()
        assert _decode_cursor(token) is None

    def test_null_cursor_input(self) -> None:
        # _decode_cursor is only called when cursor is not None, but guard anyway.
        assert _decode_cursor("null") is None
