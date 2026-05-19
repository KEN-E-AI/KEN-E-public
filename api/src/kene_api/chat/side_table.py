"""ChatSessionSideTableService — single write path to Firestore chat_sessions.

Shape B layout: accounts/{account_id}/chat_sessions/{session_id}
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.chat import ChatSessionMetadata


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _doc_path(account_id: str, session_id: str) -> str:
    return f"accounts/{account_id}/chat_sessions/{session_id}"


class ChatSessionSideTableService:
    """Write/read service for the chat_sessions Firestore side-table."""

    def __init__(self, db: firestore.Client) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        session_id: str,
        user_id: str,
        account_id: str,
        organization_id: str,
        model_id: str,
    ) -> ChatSessionMetadata:
        """Create a new side-table row. Raises if document already exists."""
        from .context_windows import get_model_context_window

        now = _now_utc()
        context_window_max = get_model_context_window(model_id).context_window_max
        metadata = ChatSessionMetadata(
            session_id=session_id,
            user_id=user_id,
            account_id=account_id,
            organization_id=organization_id,
            model_id=model_id,
            context_window_max=context_window_max,
            created_at=now,
            updated_at=now,
        )
        doc_ref = self._db.document(_doc_path(account_id, session_id))
        doc_ref.create(metadata.model_dump())
        return metadata

    def get(self, account_id: str, session_id: str) -> ChatSessionMetadata | None:
        """Return the side-table row or None if not found."""
        doc = self._db.document(_doc_path(account_id, session_id)).get()
        if not doc.exists:
            return None
        return ChatSessionMetadata(**doc.to_dict())

    def list_for_user(
        self,
        user_id: str,
        account_id: str,
        cursor: str | None = None,
        category_id: str | None = None,
        query: str | None = None,
        limit: int = 20,
    ) -> tuple[list[ChatSessionMetadata], str | None]:
        """Cursor-paginated listing for a user. Delegates to search.list_sessions."""
        from .search import list_sessions

        return list_sessions(
            db=self._db,
            user_id=user_id,
            account_id=account_id,
            cursor=cursor,
            category_id=category_id,
            query=query,
            limit=limit,
        )

    def update_from_delta(
        self,
        account_id: str,
        session_id: str,
        delta: dict[str, Any],
    ) -> None:
        """Merge a delta dict onto the document.

        Callers may include firestore.Increment sentinels directly; they are
        passed through to Firestore without conversion here.
        """
        if not delta:
            return
        doc_ref = self._db.document(_doc_path(account_id, session_id))
        doc_ref.update(delta)

    def tombstone(self, account_id: str, session_id: str) -> datetime:
        """Soft-delete: set deleted_at and updated_at to now. Returns deleted_at."""
        now = _now_utc()
        doc_ref = self._db.document(_doc_path(account_id, session_id))
        doc_ref.update({"deleted_at": now, "updated_at": now})
        return now


@lru_cache(maxsize=1)
def get_chat_side_table_service() -> ChatSessionSideTableService:
    """Process-wide singleton for ChatSessionSideTableService."""
    return ChatSessionSideTableService(db=get_firestore_client())
