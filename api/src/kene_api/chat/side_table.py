"""ChatSessionSideTableService — single write path to Firestore chat_sessions.

Shape B layout: accounts/{account_id}/chat_sessions/{session_id}
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from google.adk.sessions.base_session_service import GetSessionConfig
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from ..dependencies import get_firestore_client
from ..models.chat import ChatSessionMetadata

logger = logging.getLogger(__name__)

# Fire-and-forget heal tasks are stored here so they are not garbage-collected
# before they complete (satisfies RUF006).  The done-callback discards each
# reference on completion, keeping the set bounded.
_heal_tasks: set[asyncio.Task[Any]] = set()

STUCK_THRESHOLD = timedelta(minutes=10)

# Maximum characters (Unicode code points) of latest_summary included in
# search_text. A 2048-char ASCII summary is 2 KB; even 3-byte CJK at this
# cap is ~6 KB — well under the 1 MB Firestore field-size limit (CH-PRD-01 §9).
_SUMMARY_SEARCH_TEXT_CAP = 2048


def recompute_search_text(
    doc: ChatSessionMetadata | Mapping[str, Any],
    category_name: str | None,
) -> str:
    """Compute the denormalised search_text field for a chat session.

    Accepts either a ChatSessionMetadata instance (used by assign_category,
    which already holds the metadata) or a raw Firestore document dict (used
    by the transactional bulk-clear path in delete_category, which has only a
    DocumentSnapshot).

    Formula per CH-PRD-01 §2 step 9:
        search_text = casefold(title + " " + category_name + " " + latest_summary)

    None-safe: missing/None components are omitted. Summary is capped at
    _SUMMARY_SEARCH_TEXT_CAP characters to bound Firestore field size.
    Uses str.casefold() (not str.lower()) for correct Unicode handling
    (Turkish dotted-i, German ß, etc.).

    Args:
        doc: Either a ChatSessionMetadata instance or a Firestore document dict
             (DocumentSnapshot.to_dict()). Both provide 'title' and 'latest_summary'.
        category_name: Resolved display name of the assigned category, or None
                       when the session is uncategorized / being unassigned.

    Returns:
        Casefolded, space-joined string. Empty string when all parts are absent.
        Never raises.
    """
    if isinstance(doc, ChatSessionMetadata):
        title = doc.title or ""
        summary = (doc.latest_summary or "")[:_SUMMARY_SEARCH_TEXT_CAP]
    else:
        title = str(doc.get("title") or "")
        summary = str(doc.get("latest_summary") or "")[:_SUMMARY_SEARCH_TEXT_CAP]
    parts = [p for p in [title, str(category_name or ""), summary] if p]
    return " ".join(parts).casefold()


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
        *,
        include_tombstoned: bool = False,
    ) -> ChatSessionMetadata | None:
        """Locate a session by (user_id, session_id) without knowing account_id.

        Issues a collection-group query filtered by both equality conditions.

        This is the canonical lookup for endpoints whose URL carries only
        session_id — callers resolve account_id from the returned metadata.

        Args:
            user_id: The authenticated user's ID.
            session_id: The ADK session ID.
            include_tombstoned: When ``False`` (default), a tombstoned row
                (``deleted_at`` set) is treated as not-found and ``None`` is
                returned — collapsing "no row" and "deleted row" into one
                result. When ``True``, the row is returned even if tombstoned,
                so the caller can distinguish the two states (used by
                ``resolve_session_for_user`` to deny deleted sessions without
                falling back to ADK).

        Returns:
            ChatSessionMetadata if found and owned by user_id (and, unless
            ``include_tombstoned``, not tombstoned), else None.
        """
        query = (
            self._db.collection_group("chat_sessions")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("session_id", "==", session_id))
            .limit(1)
        )
        docs = list(query.get())
        if not docs:
            return None
        doc = docs[0]
        if not doc.exists:
            return None
        meta = ChatSessionMetadata(**doc.to_dict())
        if meta.deleted_at is not None and not include_tombstoned:
            return None
        return meta

    async def resolve_session_for_user(
        self,
        user_id: str,
        session_id: str,
        session_service: Any,
        app_name: str,
        *,
        org_id_resolver: Callable[[str], Awaitable[str | None]] | None = None,
        model_id: str = "",
    ) -> ChatSessionMetadata | None:
        """Resolve session ownership, falling back to ADK when the side-table row is missing.

        Fast path: finds the side-table row via ``find_session_for_user``.  A
        tombstoned (soft-deleted) row short-circuits to ``None`` *without*
        consulting ADK, so a deleted session is never re-exposed during the ADK
        orphan-scan grace window (the ADK session outlives the side-table
        tombstone).

        Slow path (side-table miss): calls
        ``session_service.get_session(app_name, user_id, session_id)``.  ADK
        scopes sessions by ``user_id`` at the platform layer — google-adk 2.0.0
        ``VertexAiSessionService.get_session`` *raises* ``ValueError`` when the
        session belongs to another user (it does NOT return ``None``).  That
        raise is caught by the broad ``except`` below and converted to ``None``
        (→ 404), so a successful return is itself proof of ownership.  On ADK
        hit, synthesises a ``ChatSessionMetadata`` in memory from
        ``session.state["account_id"]`` and schedules a best-effort self-heal
        write via ``asyncio.create_task``.

        Only ``account_id`` (and ``last_viewed_at=None``) are guaranteed accurate
        on the synthesised path.  Callers must not rely on other fields.

        Args:
            user_id: Authenticated user ID.
            session_id: ADK session ID.
            session_service: ADK ``VertexAiSessionService`` instance.
            app_name: ADK app name (``"ken_e_chatbot"``).
            org_id_resolver: Optional async callable
                ``(account_id: str) -> str | None``.  Used inside the heal task
                to persist a complete side-table row.  When ``None``, the heal
                is skipped with a WARN log.
            model_id: Model ID stored in the synthesised row (callers do not
                read this field on the fallback path; defaults to ``""``).

        Returns:
            ``ChatSessionMetadata`` if the session is owned by ``user_id``,
            ``None`` otherwise.
        """
        loop = asyncio.get_running_loop()

        # ------------------------------------------------------------------
        # Fast path — side-table row exists (zero extra latency for live rows)
        # ------------------------------------------------------------------
        meta = await loop.run_in_executor(
            None,
            lambda: self.find_session_for_user(
                user_id=user_id, session_id=session_id, include_tombstoned=True
            ),
        )
        if meta is not None:
            if meta.deleted_at is not None:
                # Tombstoned row — deny and do NOT fall back to ADK. The ADK
                # session outlives the side-table tombstone (orphan-scan grace
                # window), so falling back here would re-expose a deleted session.
                return None
            return meta

        # ------------------------------------------------------------------
        # Slow path — side-table miss; try ADK as the authoritative source
        # ------------------------------------------------------------------
        try:
            adk_session = await session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                # Ownership only needs the session resource (user_id +
                # state["account_id"]); num_recent_events=0 skips the events.list
                # network round-trip (google-adk 2.0.0 — re-verify on ADK bumps).
                config=GetSessionConfig(num_recent_events=0),
            )
        except Exception as exc:
            # SECURITY BOUNDARY — do NOT narrow this except to specific types.
            # google-adk 2.0.0 get_session RAISES ValueError on cross-user
            # access; that raise MUST be caught here and converted to None (→ 404)
            # so a caller cannot tell "someone else's session" from "no session".
            # Fail closed on any error — a misconfigured IAM policy then surfaces
            # via error_type rather than silently 404-ing all users.
            logger.warning(
                "chat.side_table: ADK get_session failed (treating as not-found)",
                extra={
                    "action": "side_table_adk_fallback_error",
                    "session_id": session_id,
                    "user_id": user_id,
                    "error_type": type(exc).__name__,
                },
            )
            return None

        if adk_session is None:
            return None

        state: dict[str, Any] = getattr(adk_session, "state", {}) or {}
        account_id = state.get("account_id", "")
        # ADK session state is untyped; reject non-str, empty, or path-traversal
        # values — account_id is used as a Firestore document-path segment, so a
        # crafted "/" or ".." would escape the intended sub-path.
        if (
            not isinstance(account_id, str)
            or not account_id
            or "/" in account_id
            or ".." in account_id
        ):
            return None

        # Emit the observability signal — distinct from the heal-failure log.
        logger.warning(
            "chat.side_table: side-table miss — ADK fallback used for ownership check",
            extra={
                "action": "side_table_self_heal_triggered",
                "session_id": session_id,
                "user_id": user_id,
                "account_id": account_id,
            },
        )

        # Synthesise in-memory metadata (only account_id is guaranteed accurate).
        synthesized = ChatSessionMetadata(
            session_id=session_id,
            user_id=user_id,
            account_id=account_id,
            organization_id="",
            model_id=model_id,
        )

        # ------------------------------------------------------------------
        # Best-effort heal — schedule via create_task so it never blocks the
        # read response.  All exceptions are swallowed and logged at WARN.
        # ------------------------------------------------------------------
        _svc_ref = self
        _session_id = session_id
        _user_id = user_id
        _account_id = account_id
        _model_id = model_id or "gemini-2.5-flash"
        _resolver = org_id_resolver

        async def _heal_task() -> None:
            try:
                if _resolver is None:
                    logger.warning(
                        "chat.side_table: self-heal skipped — no org_id_resolver",
                        extra={
                            "action": "side_table_self_heal_failed",
                            "session_id": _session_id,
                            "account_id": _account_id,
                            "error_type": "NoResolver",
                        },
                    )
                    return
                org_id = await _resolver(_account_id)
                if org_id is None:
                    logger.warning(
                        "chat.side_table: self-heal skipped — org_id unresolvable",
                        extra={
                            "action": "side_table_self_heal_failed",
                            "session_id": _session_id,
                            "account_id": _account_id,
                            "error_type": "NoOrgId",
                        },
                    )
                    return
                _loop = asyncio.get_running_loop()
                try:
                    await _loop.run_in_executor(
                        None,
                        lambda: _svc_ref.create(
                            session_id=_session_id,
                            user_id=_user_id,
                            account_id=_account_id,
                            organization_id=org_id,
                            model_id=_model_id,
                        ),
                    )
                except Exception as create_exc:
                    from google.api_core.exceptions import AlreadyExists

                    if isinstance(create_exc, AlreadyExists):
                        # A concurrent request already healed the row — not an error.
                        logger.debug(
                            "chat.side_table: self-heal skipped — row already exists",
                            extra={
                                "action": "side_table_self_heal_duplicate",
                                "session_id": _session_id,
                                "account_id": _account_id,
                            },
                        )
                    else:
                        raise
            except Exception as exc:
                logger.warning(
                    "chat.side_table: self-heal write failed (non-fatal)",
                    extra={
                        "action": "side_table_self_heal_failed",
                        "session_id": _session_id,
                        "account_id": _account_id,
                        "error_type": type(exc).__name__,
                    },
                )

        task = asyncio.create_task(_heal_task())
        _heal_tasks.add(task)
        task.add_done_callback(_heal_tasks.discard)

        return synthesized

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
