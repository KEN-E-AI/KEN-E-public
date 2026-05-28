"""Session recovery service for returning users.

This module handles session recovery, allowing users to resume
previous conversations and maintain context across visits.

Features:
- List recoverable sessions within 30-day window
- Full state restoration from ADK session store
- Conversation history reloading
- Graceful degradation for corrupted data

Design Reference: Story 1.4.3 - Session Recovery
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from shared.structured_logging import get_structured_logger, log_context

if TYPE_CHECKING:
    from google.adk.sessions import VertexAiSessionService

logger = get_structured_logger(__name__)

# App name constant (matches chat.py)
APP_NAME = "ken_e_chatbot"


@dataclass
class RecoverableSession:
    """A session that can be recovered.

    Attributes:
        session_id: Unique session identifier
        conversation_name: User-friendly name (if set)
        created_at: When session was created
        last_updated: Last activity time
        message_count: Number of messages in session
        preview: Preview text from last message
    """

    session_id: str
    conversation_name: str | None
    created_at: datetime
    last_updated: datetime
    message_count: int
    preview: str | None = None


@dataclass
class SessionRecoveryResult:
    """Result of session recovery attempt.

    Attributes:
        success: Whether recovery succeeded
        session_id: Recovered session ID (or None on failure)
        state: Restored session state
        conversation_history: List of message events
        error: Error message if recovery failed
    """

    success: bool
    session_id: str | None
    state: dict[str, Any] | None
    conversation_history: list[dict[str, Any]] | None
    error: str | None = None


class SessionRecoveryService:
    """Handles session recovery for returning users.

    Builds on Sprint 1's session infrastructure to add:
    - Session listing with 30-day window
    - Full state restoration
    - Conversation history reloading
    - Graceful degradation for corrupted data

    Usage:
        service = SessionRecoveryService(session_service, redis_service)

        # List sessions that can be recovered
        sessions = await service.list_recoverable_sessions("user123")

        # Recover a specific session
        result = await service.recover_session("user123", "session_abc")
        if result.success:
            state = result.state
            history = result.conversation_history
    """

    RECOVERY_WINDOW_DAYS = 30

    def __init__(
        self,
        session_service: VertexAiSessionService,
        redis_service: Any | None = None,
    ):
        """Initialize the recovery service.

        Args:
            session_service: ADK session service for session operations
            redis_service: Optional Redis service for caching
        """
        self._session_service = session_service
        self._redis = redis_service

    async def list_recoverable_sessions(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[RecoverableSession]:
        """List sessions available for recovery.

        Returns sessions from the last 30 days, sorted by last_updated desc.

        Args:
            user_id: User to list sessions for
            limit: Maximum number of sessions to return

        Returns:
            List of recoverable sessions, newest first (30-day window)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.RECOVERY_WINDOW_DAYS)

        try:
            sessions = await self._session_service.list_sessions(
                app_name=APP_NAME,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to list sessions: {e}",
                extra=log_context(
                    component="session_recovery",
                    action="list_error",
                    error_message=str(e),
                    extra={"user_id": user_id},
                ),
            )
            return []

        # Handle ListSessionsResponse - it might have a sessions attribute
        session_list = sessions.sessions if hasattr(sessions, "sessions") else sessions

        recoverable = []
        for session in session_list:
            try:
                session_info = self._parse_session(session, cutoff)
                if session_info:
                    recoverable.append(session_info)
            except Exception as e:
                logger.warning(f"Failed to parse session for recovery: {e}")
                continue

        # Sort by last_updated descending
        recoverable.sort(key=lambda s: s.last_updated, reverse=True)

        return recoverable[:limit]

    def _parse_session(
        self,
        session: Any,
        cutoff: datetime,
    ) -> RecoverableSession | None:
        """Parse a session object into RecoverableSession.

        Args:
            session: Session object from ADK
            cutoff: Cutoff datetime for recovery window

        Returns:
            RecoverableSession or None if not recoverable
        """
        # Extract session ID
        session_id = str(
            getattr(session, "id", None) or getattr(session, "session_id", session)
        )

        # Get timestamps
        create_time = getattr(session, "create_time", None)
        update_time = getattr(session, "update_time", None) or create_time

        if isinstance(create_time, str):
            create_time = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
        if isinstance(update_time, str):
            update_time = datetime.fromisoformat(update_time.replace("Z", "+00:00"))

        if create_time is None:
            create_time = datetime.now(timezone.utc)
        if update_time is None:
            update_time = create_time

        # Ensure timezone awareness
        if create_time.tzinfo is None:
            create_time = create_time.replace(tzinfo=timezone.utc)
        if update_time.tzinfo is None:
            update_time = update_time.replace(tzinfo=timezone.utc)

        # Check if within recovery window
        if update_time < cutoff:
            return None

        # Get state and events
        state = getattr(session, "state", {}) or {}
        events = getattr(session, "events", []) or []

        # Count user messages (check both content.role and event author)
        message_count = 0
        for e in events:
            content_obj = getattr(e, "content", None)
            role = None
            if content_obj and hasattr(content_obj, "role"):
                role = content_obj.role
            if role == "user" or getattr(e, "author", None) == "user":
                message_count += 1

        # Generate preview from last user/model message
        preview = None
        for e in reversed(events):
            content_obj = getattr(e, "content", None)
            if not content_obj:
                continue
            if hasattr(content_obj, "parts") and content_obj.parts:
                for part in content_obj.parts:
                    if hasattr(part, "text") and part.text:
                        text = part.text.strip()
                        if text and not text.startswith("[ORGANIZATION CONTEXT]"):
                            preview = text[:100] + "..." if len(text) > 100 else text
                            break
            if preview:
                break

        # Get conversation name from state
        conversation_name = state.get("conversation_name")

        return RecoverableSession(
            session_id=session_id,
            conversation_name=conversation_name,
            created_at=create_time,
            last_updated=update_time,
            message_count=message_count,
            preview=preview,
        )

    async def recover_session(
        self,
        user_id: str,
        session_id: str,
    ) -> SessionRecoveryResult:
        """Recover a specific session.

        Restores full context including:
        - Session state (account_id, organization_context, etc.)
        - Conversation history
        - Loaded MCP server state (if applicable)

        Args:
            user_id: User ID
            session_id: Session to recover

        Returns:
            SessionRecoveryResult with state and history
        """
        try:
            session = await self._session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

            if session is None:
                return SessionRecoveryResult(
                    success=False,
                    session_id=session_id,
                    state=None,
                    conversation_history=None,
                    error="Session not found",
                )

            # Extract state
            state = getattr(session, "state", {}) or {}

            # Validate state has required fields
            if not self._validate_state(state):
                logger.warning(
                    f"Session {session_id} has incomplete state, attempting partial recovery"
                )
                state = self._repair_state(state)

            # Extract conversation history, matching the format from
            # AgentEngineClient.get_conversation_history so the frontend
            # can parse it the same way.
            events = getattr(session, "events", []) or []
            conversation_history = []
            for e in events:
                content_obj = getattr(e, "content", None)
                if not content_obj:
                    continue

                # Determine role from content.role or event.author
                role = "assistant"
                if hasattr(content_obj, "role"):
                    role = content_obj.role or "assistant"
                elif hasattr(e, "author"):
                    role = getattr(e, "author", "assistant")

                # Map ADK roles to frontend roles
                if role == "model":
                    role = "assistant"
                # Skip system/tool events — only keep user and assistant
                if role not in ("user", "assistant"):
                    continue

                # Extract text from content.parts
                text = ""
                if hasattr(content_obj, "parts") and content_obj.parts:
                    text_parts = []
                    for part in content_obj.parts:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(part.text)
                    text = "\n".join(text_parts)
                elif isinstance(content_obj, str):
                    text = content_obj

                if not text or not text.strip():
                    continue

                # Skip internal context-setting messages
                if text.strip().startswith("[ORGANIZATION CONTEXT]"):
                    continue

                conversation_history.append(
                    {
                        "role": role,
                        "content": text,
                        "timestamp": (
                            ts.isoformat()
                            if (ts := getattr(e, "timestamp", None))
                            else None
                        ),
                    }
                )

            # Update cache for faster subsequent access
            if self._redis:
                try:
                    cache_key = f"chat:session:{user_id}:{session_id}"
                    if hasattr(self._redis, "set_json"):
                        self._redis.set_json(
                            cache_key,
                            {
                                "state": state,
                                "recovered_at": datetime.now(timezone.utc).isoformat(),
                            },
                            ttl_seconds=86400,
                        )
                except Exception as e:
                    logger.warning(f"Failed to cache recovered session: {e}")

            logger.info(
                "Session recovered successfully",
                extra=log_context(
                    component="session_recovery",
                    action="recover_success",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "message_count": len(conversation_history),
                    },
                ),
            )

            return SessionRecoveryResult(
                success=True,
                session_id=session_id,
                state=state,
                conversation_history=conversation_history,
            )

        except Exception as e:
            logger.error(
                f"Session recovery failed: {e}",
                extra=log_context(
                    component="session_recovery",
                    action="recover_error",
                    error_message=str(e),
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                ),
            )
            return SessionRecoveryResult(
                success=False,
                session_id=session_id,
                state=None,
                conversation_history=None,
                error=str(e),
            )

    def _validate_state(self, state: dict[str, Any]) -> bool:
        """Validate session state has minimum required fields.

        Args:
            state: Session state dictionary

        Returns:
            True if state has required fields
        """
        required_fields = ["account_id"]
        return all(field in state for field in required_fields)

    def _repair_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Attempt to repair incomplete session state.

        Adds default values for missing required fields.

        Args:
            state: Original state

        Returns:
            Repaired state with defaults
        """
        repaired = dict(state)

        # Add defaults for missing fields
        if "account_id" not in repaired:
            repaired["account_id"] = None  # Will need to be selected

        if "accessible_accounts" not in repaired:
            repaired["accessible_accounts"] = []

        return repaired


# Singleton instance
_recovery_service: SessionRecoveryService | None = None


def get_recovery_service() -> SessionRecoveryService:
    """Get the singleton recovery service.

    Lazily initializes with the ADK session service.

    Returns:
        Shared SessionRecoveryService instance
    """
    global _recovery_service
    if _recovery_service is None:
        from api.src.kene_api.redis_client import get_redis_service
        from api.src.kene_api.routers.chat import agent_client

        session_service = agent_client.session_service
        redis_service = get_redis_service()

        _recovery_service = SessionRecoveryService(
            session_service=session_service,
            redis_service=redis_service if redis_service.is_available() else None,
        )
    return _recovery_service


def reset_recovery_service() -> None:
    """Reset the singleton (for testing)."""
    global _recovery_service
    _recovery_service = None
