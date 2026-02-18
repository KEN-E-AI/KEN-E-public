"""Session timeout handling for security.

This module manages session timeouts to protect user data when
sessions are left inactive.

Features:
- Configurable warning and timeout thresholds
- Activity tracking per session
- Callback support for UI notifications
- Graceful session cleanup

Design Reference: Story 1.4.4 - Session Timeout
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from shared.structured_logging import get_structured_logger, log_context

logger = get_structured_logger(__name__)


@dataclass
class TimeoutConfig:
    """Session timeout configuration.

    Attributes:
        warning_minutes: Minutes of inactivity before warning
        timeout_minutes: Minutes of inactivity before timeout
        check_interval_seconds: How often to check for timeouts
    """

    warning_minutes: int = 25
    timeout_minutes: int = 30
    check_interval_seconds: int = 30


class SessionTimeoutManager:
    """Manages session timeouts for security.

    Features:
    - 25-minute warning before timeout
    - 30-minute inactivity timeout
    - Activity resets timer
    - Graceful session cleanup

    Usage:
        # Create manager with callbacks
        manager = SessionTimeoutManager(
            on_warning=async_warning_callback,
            on_timeout=async_timeout_callback,
        )

        # Start monitoring
        await manager.start_monitor()

        # Record activity on API requests
        manager.record_activity(user_id, session_id)

        # Stop when done
        await manager.stop_monitor()

    Callbacks:
        on_warning(user_id, session_id, remaining_minutes) - Called when warning threshold reached
        on_timeout(user_id, session_id) - Called when session times out
    """

    def __init__(
        self,
        config: TimeoutConfig | None = None,
        on_warning: Callable[[str, str, int], Awaitable[None]] | None = None,
        on_timeout: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        """Initialize the timeout manager.

        Args:
            config: Timeout configuration
            on_warning: Async callback for timeout warnings
            on_timeout: Async callback when session times out
        """
        self.config = config or TimeoutConfig()
        self._on_warning = on_warning
        self._on_timeout = on_timeout

        # Track session activity: {"user_id:session_id": last_activity_time}
        self._activity: dict[str, datetime] = {}
        self._warned: set[str] = set()  # Sessions that have been warned

        self._monitor_task: asyncio.Task[None] | None = None

    def record_activity(self, user_id: str, session_id: str) -> None:
        """Record user activity, resetting the timeout timer.

        Should be called on any API request for a session.

        Args:
            user_id: User ID
            session_id: Session ID
        """
        key = f"{user_id}:{session_id}"
        self._activity[key] = datetime.now(timezone.utc)

        # Clear warning flag if previously warned
        if key in self._warned:
            self._warned.discard(key)
            logger.debug(
                "Timeout warning cleared for session",
                extra=log_context(
                    component="session_timeout",
                    action="warning_cleared",
                    extra={"user_id": user_id, "session_id": session_id},
                ),
            )

    def untrack_session(self, user_id: str, session_id: str) -> None:
        """Stop tracking a session (e.g., on logout).

        Args:
            user_id: User ID
            session_id: Session ID
        """
        key = f"{user_id}:{session_id}"
        self._activity.pop(key, None)
        self._warned.discard(key)

    async def start_monitor(self) -> None:
        """Start the timeout monitoring background task."""
        if self._monitor_task is not None:
            return

        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Session timeout monitor started")

    async def stop_monitor(self) -> None:
        """Stop the timeout monitor."""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info("Session timeout monitor stopped")

    async def _monitor_loop(self) -> None:
        """Background loop to check for timeouts."""
        while True:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                await self._check_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Timeout monitor error: {e}")

    async def _check_sessions(self) -> None:
        """Check all sessions for timeout conditions."""
        now = datetime.now(timezone.utc)
        warning_threshold = timedelta(minutes=self.config.warning_minutes)
        timeout_threshold = timedelta(minutes=self.config.timeout_minutes)

        sessions_to_timeout: list[tuple[str, str]] = []

        for key, last_activity in list(self._activity.items()):
            idle_duration = now - last_activity
            user_id, session_id = key.split(":", 1)

            if idle_duration >= timeout_threshold:
                # Session should timeout
                sessions_to_timeout.append((user_id, session_id))

            elif idle_duration >= warning_threshold and key not in self._warned:
                # Send warning
                remaining_seconds = (timeout_threshold - idle_duration).total_seconds()
                remaining_minutes = max(1, int(remaining_seconds / 60))
                self._warned.add(key)

                if self._on_warning:
                    try:
                        await self._on_warning(user_id, session_id, remaining_minutes)
                    except Exception as e:
                        logger.error(f"Warning callback failed: {e}")

                logger.info(
                    "Session timeout warning sent",
                    extra=log_context(
                        component="session_timeout",
                        action="warning",
                        extra={
                            "user_id": user_id,
                            "session_id": session_id,
                            "remaining_minutes": remaining_minutes,
                        },
                    ),
                )

        # Process timeouts
        for user_id, session_id in sessions_to_timeout:
            key = f"{user_id}:{session_id}"

            # Clean up tracking
            self._activity.pop(key, None)
            self._warned.discard(key)

            # Call timeout handler
            if self._on_timeout:
                try:
                    await self._on_timeout(user_id, session_id)
                except Exception as e:
                    logger.error(f"Timeout callback failed: {e}")

            logger.info(
                "Session timed out",
                extra=log_context(
                    component="session_timeout",
                    action="timeout",
                    extra={"user_id": user_id, "session_id": session_id},
                ),
            )

    def get_remaining_time(self, user_id: str, session_id: str) -> int | None:
        """Get remaining time before timeout in seconds.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Seconds remaining before timeout, or None if not tracked
        """
        key = f"{user_id}:{session_id}"
        last_activity = self._activity.get(key)

        if last_activity is None:
            return None

        idle = datetime.now(timezone.utc) - last_activity
        timeout = timedelta(minutes=self.config.timeout_minutes)
        remaining = timeout - idle

        return max(0, int(remaining.total_seconds()))

    def is_warned(self, user_id: str, session_id: str) -> bool:
        """Check if a session has been warned.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            True if session has received timeout warning
        """
        key = f"{user_id}:{session_id}"
        return key in self._warned

    def get_active_session_count(self) -> int:
        """Get number of tracked sessions.

        Returns:
            Number of active sessions being monitored
        """
        return len(self._activity)

    def get_warned_session_count(self) -> int:
        """Get number of warned sessions.

        Returns:
            Number of sessions that have received warnings
        """
        return len(self._warned)


# Singleton instance
_timeout_manager: SessionTimeoutManager | None = None


def configure_timeout_manager(
    on_warning: Callable[[str, str, int], Awaitable[None]] | None = None,
    on_timeout: Callable[[str, str], Awaitable[None]] | None = None,
    config: TimeoutConfig | None = None,
) -> SessionTimeoutManager:
    """Configure and return the singleton timeout manager.

    Creates the singleton with the given callbacks if it doesn't exist yet.
    If already created, returns the existing instance (callbacks are not updated).

    Args:
        on_warning: Async callback for timeout warnings
        on_timeout: Async callback when session times out
        config: Optional timeout configuration

    Returns:
        Configured SessionTimeoutManager instance
    """
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = SessionTimeoutManager(
            config=config,
            on_warning=on_warning,
            on_timeout=on_timeout,
        )
    return _timeout_manager


def get_timeout_manager() -> SessionTimeoutManager:
    """Get the singleton timeout manager.

    Returns:
        Shared SessionTimeoutManager instance
    """
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = SessionTimeoutManager()
    return _timeout_manager


async def reset_timeout_manager() -> None:
    """Reset the singleton (for testing)."""
    global _timeout_manager
    if _timeout_manager is not None:
        await _timeout_manager.stop_monitor()
        _timeout_manager = None
