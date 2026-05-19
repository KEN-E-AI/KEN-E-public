"""Unit tests for GET /conversations cursor signature extension (CH-15)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.kene_api.routers.chat import ConversationInfo, ConversationListResponse


def _make_info() -> ConversationInfo:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ConversationInfo(
        session_id="sess_1",
        conversation_name="Test",
        created_at=now,
        last_updated=now,
        message_count=2,
    )


class TestConversationListResponse:
    def test_items_mirrors_conversations(self) -> None:
        info = _make_info()
        resp = ConversationListResponse(conversations=[info], total_count=1)
        assert resp.items is resp.conversations

    def test_next_cursor_defaults_to_none(self) -> None:
        resp = ConversationListResponse(conversations=[], total_count=0)
        assert resp.next_cursor is None

    def test_explicit_next_cursor_is_preserved(self) -> None:
        resp = ConversationListResponse(
            conversations=[], total_count=0, next_cursor="abc123"
        )
        assert resp.next_cursor == "abc123"

    def test_legacy_conversations_field_still_present(self) -> None:
        info = _make_info()
        resp = ConversationListResponse(conversations=[info], total_count=1)
        assert len(resp.conversations) == 1
        assert resp.conversations[0].session_id == "sess_1"


class TestConversationInfo:
    def test_optional_timestamp_fields_default_none(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        info = ConversationInfo(
            session_id="s",
            conversation_name=None,
            created_at=now,
            last_updated=now,
            message_count=0,
        )
        assert info.last_agent_started_at is None
        assert info.last_agent_stopped_at is None
        assert info.last_viewed_at is None
