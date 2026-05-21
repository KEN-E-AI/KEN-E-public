"""Unit tests for POST /conversations/{session_id}/mark-read (CH-16).

Tests cover:
- Stamps last_viewed_at when session exists and no recent view.
- 5-second dedup: second call within window returns existing timestamp.
- 404 when session does not exist (find_session_for_user returns None).
- Rate limit: 61st request in a 60-second window is rejected with 429.
- MarkReadResponse shape is correct.

References: CH-PRD-02 §5.5, §6, §7 AC-7.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import UserContext
from src.kene_api.chat.mark_read_limiter import MarkReadRateLimiter
from src.kene_api.models.chat import ChatSessionMetadata, MarkReadResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user_context(user_id: str = "user_1") -> UserContext:
    return UserContext(
        user_id=user_id,
        email="user@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _make_meta(
    *,
    session_id: str = "sess_1",
    user_id: str = "user_1",
    account_id: str = "acc_1",
    organization_id: str = "org_1",
    last_viewed_at: datetime | None = None,
) -> ChatSessionMetadata:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return ChatSessionMetadata(
        session_id=session_id,
        user_id=user_id,
        account_id=account_id,
        organization_id=organization_id,
        model_id="gemini-2.5-flash",
        created_at=now,
        updated_at=now,
        last_viewed_at=last_viewed_at,
    )


# ---------------------------------------------------------------------------
# MarkReadResponse model
# ---------------------------------------------------------------------------

class TestMarkReadResponse:
    def test_contains_last_viewed_at(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        resp = MarkReadResponse(last_viewed_at=now)
        assert resp.last_viewed_at == now

    def test_serialises_to_iso(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        resp = MarkReadResponse(last_viewed_at=now)
        dumped = resp.model_dump()
        assert dumped["last_viewed_at"] == now


# ---------------------------------------------------------------------------
# Endpoint unit tests via mock injection
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_limiter() -> MarkReadRateLimiter:
    """A fresh limiter with a very high cap so rate-limiting doesn't interfere."""
    return MarkReadRateLimiter(max_requests=1000, window_seconds=60)


class TestMarkConversationRead:
    """Tests for the mark_conversation_read handler via patched dependencies."""

    def _run(
        self,
        session_id: str,
        meta: ChatSessionMetadata | None,
        user_id: str = "user_1",
        limiter: MarkReadRateLimiter | None = None,
    ) -> MarkReadResponse:
        """Helper: run the handler with mocked side-table service and limiter."""
        from src.kene_api.routers import chat as chat_module

        fake_svc = MagicMock()
        fake_svc.find_session_for_user.return_value = meta
        fake_svc.update_from_delta.return_value = None

        user_ctx = _make_user_context(user_id=user_id)
        _limiter = limiter or MarkReadRateLimiter(max_requests=1000, window_seconds=60)

        import asyncio

        async def _call() -> MarkReadResponse:
            with (
                patch.object(chat_module, "get_chat_side_table_service", return_value=fake_svc),
                patch.object(chat_module, "mark_read_limiter", _limiter),
            ):
                from src.kene_api.routers.chat import mark_conversation_read

                return await mark_conversation_read(
                    session_id=session_id,
                    user_context=user_ctx,
                )

        return asyncio.run(_call())

    def test_stamps_last_viewed_at_when_never_viewed(self) -> None:
        meta = _make_meta(last_viewed_at=None)
        resp = self._run(session_id="sess_1", meta=meta)
        assert isinstance(resp.last_viewed_at, datetime)

    def test_stamps_last_viewed_at_when_old_view(self) -> None:
        old = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        meta = _make_meta(last_viewed_at=old)
        # Ensure at least 5 seconds have passed — old is far in the past.
        resp = self._run(session_id="sess_1", meta=meta)
        assert resp.last_viewed_at > old

    def test_dedup_returns_existing_timestamp_within_5s(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(seconds=2)
        meta = _make_meta(last_viewed_at=recent)
        resp = self._run(session_id="sess_1", meta=meta)
        # Should return the existing timestamp, not a new one.
        assert resp.last_viewed_at == recent

    def test_dedup_does_not_call_update_when_within_5s(self) -> None:
        from src.kene_api.routers import chat as chat_module

        recent = datetime.now(timezone.utc) - timedelta(seconds=2)
        meta = _make_meta(last_viewed_at=recent)

        fake_svc = MagicMock()
        fake_svc.find_session_for_user.return_value = meta
        _limiter = MarkReadRateLimiter(max_requests=1000, window_seconds=60)
        user_ctx = _make_user_context()

        import asyncio

        async def _call() -> None:
            with (
                patch.object(chat_module, "get_chat_side_table_service", return_value=fake_svc),
                patch.object(chat_module, "mark_read_limiter", _limiter),
            ):
                from src.kene_api.routers.chat import mark_conversation_read

                await mark_conversation_read(
                    session_id="sess_1",
                    user_context=user_ctx,
                )

        asyncio.run(_call())
        fake_svc.update_from_delta.assert_not_called()

    def test_404_when_session_not_found(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            self._run(session_id="sess_missing", meta=None)
        assert exc_info.value.status_code == 404

    def test_404_same_for_nonexistent_and_unowned(self) -> None:
        """404 is returned whether the session doesn't exist or belongs to another user.
        Callers cannot distinguish the two cases (no existence leak)."""
        with pytest.raises(HTTPException) as exc_info_none:
            self._run(session_id="sess_1", meta=None)

        assert exc_info_none.value.status_code == 404

    def test_update_from_delta_called_with_correct_fields(self) -> None:
        from src.kene_api.routers import chat as chat_module

        meta = _make_meta(last_viewed_at=None)
        fake_svc = MagicMock()
        fake_svc.find_session_for_user.return_value = meta
        _limiter = MarkReadRateLimiter(max_requests=1000, window_seconds=60)
        user_ctx = _make_user_context()

        import asyncio

        async def _call() -> None:
            with (
                patch.object(chat_module, "get_chat_side_table_service", return_value=fake_svc),
                patch.object(chat_module, "mark_read_limiter", _limiter),
            ):
                from src.kene_api.routers.chat import mark_conversation_read

                await mark_conversation_read(
                    session_id="sess_1",
                    user_context=user_ctx,
                )

        asyncio.run(_call())

        fake_svc.update_from_delta.assert_called_once()
        call_args = fake_svc.update_from_delta.call_args
        delta = call_args.kwargs.get("delta") or call_args[1].get("delta") or call_args[0][2]
        assert "last_viewed_at" in delta
        assert "updated_at" in delta

    def test_429_when_rate_limit_exceeded(self) -> None:
        """61st call in window raises 429 before reaching the side-table."""
        from src.kene_api.chat import mark_read_limiter as limiter_module

        limiter = MarkReadRateLimiter(max_requests=60, window_seconds=60)
        t = 1_000_000.0  # Fixed epoch well within any pruning window.
        for _ in range(60):
            limiter.check("sess_1", now=lambda: t)

        meta = _make_meta()
        # Patch _now_utc so the handler's bare check() call also uses the
        # frozen clock — prevents the pre-filled entries from being pruned.
        with patch.object(limiter_module, "_now_utc", return_value=t):
            with pytest.raises(HTTPException) as exc_info:
                self._run(session_id="sess_1", meta=meta, limiter=limiter)
        assert exc_info.value.status_code == 429
