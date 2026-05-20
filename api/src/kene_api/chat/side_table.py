"""ChatSessionSideTableService — single write path to Firestore chat_sessions.

Shape B layout: accounts/{account_id}/chat_sessions/{session_id}
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.chat import ChatSessionMetadata

STUCK_THRESHOLD = timedelta(minutes=10)


def derive_is_agent_running(
    started_at: datetime | None,
    stopped_at: datetime | None,
    *,
    now: datetime | None = None,
    threshold: timedelta = STUCK_THRESHOLD,
) -> bool:
    """Derive whether the agent is currently running from timestamps.

    No persistent boolean field; no in-process sweeper. Three-state logic:
    - never-started: started_at is None → False
    - running-stuck: running more than threshold → False
    - stopped: stopped_at >= started_at → False
    - running-fresh: started_at set, stopped_at None or started_at > stopped_at,
      and elapsed < threshold → True

    Args:
        started_at: Timestamp from before_agent_callback. None if never started.
        stopped_at: Timestamp from after_agent_callback/finally. None if not stopped.
        now: Override for the current time (test injection). Defaults to utcnow.
        threshold: Max duration before treating an in-flight turn as stuck.
                   Default 10 minutes per PRD §7.7.

    Returns:
        True only when the agent turn is live and within threshold.
    """
    if started_at is None:
        return False
    _now = now if now is not None else datetime.now(timezone.utc)
    # Normalise naive datetimes that may arrive as strings coerced by Pydantic.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if stopped_at is not None and stopped_at.tzinfo is None:
        stopped_at = stopped_at.replace(tzinfo=timezone.utc)
    # Stopped-after-start: agent completed normally
    if stopped_at is not None and stopped_at >= started_at:
        return False
    # Running-stuck: elapsed exceeds threshold (crash/hang safety)
    if (_now - started_at) >= threshold:
        return False
    return True


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

    def find_session_for_user(
        self,
        user_id: str,
        session_id: str,
    ) -> ChatSessionMetadata | None:
        """Locate a session by (user_id, session_id) without knowing account_id.

        Issues a collection-group query filtered by both equality conditions.
        Returns the row only when it exists, belongs to user_id, and is not
        tombstoned (deleted_at is None).

        This is the canonical lookup for endpoints whose URL carries only
        session_id — callers resolve account_id from the returned metadata.

        Args:
            user_id: The authenticated user's ID.
            session_id: The ADK session ID.

        Returns:
            ChatSessionMetadata if found and owned by user_id, else None.
        """
        query = (
            self._db.collection_group("chat_sessions")
            .where("user_id", "==", user_id)
            .where("session_id", "==", session_id)
            .limit(1)
        )
        docs = list(query.get())
        if not docs:
            return None
        doc = docs[0]
        if not doc.exists:
            return None
        meta = ChatSessionMetadata(**doc.to_dict())
        if meta.deleted_at is not None:
            return None
        return meta

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
