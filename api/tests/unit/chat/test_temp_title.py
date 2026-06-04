"""Unit tests for the temporary first-prompt session title (Q3 stopgap).

Covers ``_maybe_set_temp_title`` — the interim auto-title that derives a title
from the first 30 characters of the user's first prompt until CH-PRD-04's LLM
generator ships. The helper must be idempotent, bounded to early turns, and must
never raise.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from src.kene_api.models.chat import ChatSessionMetadata
from src.kene_api.routers import chat as chat_module
from src.kene_api.routers.chat import ChatMessage


def _meta(title: str | None = None) -> ChatSessionMetadata:
    now = datetime(2026, 6, 4, tzinfo=timezone.utc)
    return ChatSessionMetadata(
        session_id="sess-1",
        user_id="u1",
        account_id="acc-1",
        organization_id="org-1",
        model_id="gemini-2.0-flash",
        context_window_max=128_000,
        created_at=now,
        updated_at=now,
        title=title,
    )


def _msgs(*pairs: tuple[str, str]) -> list[ChatMessage]:
    return [ChatMessage(role=r, content=c) for r, c in pairs]


@pytest.mark.asyncio
async def test_sets_title_from_first_user_message() -> None:
    prompt = "Build me a Q3 marketing calendar for LinkedIn ads"
    expected = " ".join(prompt.split())[:30]

    svc = MagicMock()
    svc.get.return_value = _meta(title=None)
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("user", prompt)),
        )

    svc.update_from_delta.assert_called_once()
    account_id, session_id, delta = svc.update_from_delta.call_args.args
    assert (account_id, session_id) == ("acc-1", "sess-1")
    assert delta["title"] == expected
    assert len(delta["title"]) == 30
    assert delta["search_text"] == expected.casefold()
    # Must NOT stamp auto_title_attempted_at — CH-PRD-04 can still upgrade later.
    assert "auto_title_attempted_at" not in delta


@pytest.mark.asyncio
async def test_collapses_whitespace_in_title() -> None:
    svc = MagicMock()
    svc.get.return_value = _meta(title=None)
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("user", "  hello   \n\n  world  ")),
        )

    delta = svc.update_from_delta.call_args.args[2]
    assert delta["title"] == "hello world"


@pytest.mark.asyncio
async def test_noop_when_already_titled() -> None:
    svc = MagicMock()
    svc.get.return_value = _meta(title="A title the user set")
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("user", "a new prompt")),
        )

    svc.update_from_delta.assert_not_called()


@pytest.mark.asyncio
async def test_noop_when_row_missing() -> None:
    svc = MagicMock()
    svc.get.return_value = None
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("user", "prompt")),
        )

    svc.update_from_delta.assert_not_called()


@pytest.mark.asyncio
async def test_skips_pending_session() -> None:
    svc = MagicMock()
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="pending_abc",
            account_id="acc-1",
            messages=_msgs(("user", "prompt")),
        )

    svc.get.assert_not_called()


@pytest.mark.asyncio
async def test_skips_missing_account() -> None:
    svc = MagicMock()
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id=None,
            messages=_msgs(("user", "prompt")),
        )

    svc.get.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_user_message() -> None:
    svc = MagicMock()
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("assistant", "hi there")),
        )

    svc.get.assert_not_called()


@pytest.mark.asyncio
async def test_skips_once_conversation_has_progressed() -> None:
    """More than two user messages → not an early turn; avoid a per-turn read."""
    svc = MagicMock()
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(
                ("user", "one"),
                ("assistant", "x"),
                ("user", "two"),
                ("assistant", "y"),
                ("user", "three"),
            ),
        )

    svc.get.assert_not_called()


@pytest.mark.asyncio
async def test_never_raises_on_service_error() -> None:
    svc = MagicMock()
    svc.get.side_effect = RuntimeError("firestore down")
    with patch.object(chat_module, "get_chat_side_table_service", lambda: svc):
        # Must not surface to the chat client.
        await chat_module._maybe_set_temp_title(
            session_id="sess-1",
            account_id="acc-1",
            messages=_msgs(("user", "prompt")),
        )

    svc.update_from_delta.assert_not_called()
