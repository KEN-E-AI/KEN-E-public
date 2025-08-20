"""Cached notification repository implementation."""

import json
import time
from typing import Any

from ..models.kene_models import (
    Notification,
    NotificationStatus,
    UserNotificationPreferences,
)
from .notification_repository import NotificationRepository


class CachedNotificationRepository(NotificationRepository):
    """Notification repository with in-memory caching.

    This decorator adds caching to any NotificationRepository implementation.
    For production use, consider using Redis instead of in-memory cache.
    """

    def __init__(self, repository: NotificationRepository, cache_ttl: int = 300):
        """Initialize cached repository.

        Args:
            repository: The underlying repository to cache
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.repository = repository
        self.cache_ttl = cache_ttl

        # In-memory caches
        self._preferences_cache: dict[
            str, tuple[UserNotificationPreferences | None, float]
        ] = {}
        self._unread_count_cache: dict[str, tuple[int, float]] = {}

    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if a cache entry is still valid."""
        return time.time() - timestamp < self.cache_ttl

    def _make_count_cache_key(self, user_id: str, account_ids: list[str]) -> str:
        """Create a cache key for unread count."""
        # Sort account IDs for consistent key
        sorted_accounts = sorted(account_ids)
        return f"{user_id}:{','.join(sorted_accounts)}"

    async def create(self, notification: Notification) -> str:
        """Create notification and invalidate relevant caches."""
        result = await self.repository.create(notification)

        # Invalidate unread count cache for all users
        # In production, you'd want to be more selective
        self._unread_count_cache.clear()

        return result

    async def get_by_id(self, notification_id: str) -> Notification | None:
        """Get notification by ID (no caching needed)."""
        return await self.repository.get_by_id(notification_id)

    async def get_by_account(
        self,
        account_ids: list[str],
        include_archived: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications (no caching for lists)."""
        return await self.repository.get_by_account(
            account_ids, include_archived, limit, offset
        )

    async def get_user_statuses(
        self,
        user_id: str,
        notification_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get user statuses (no caching needed)."""
        return await self.repository.get_user_statuses(user_id, notification_ids)

    async def update_user_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        """Update status and invalidate unread count cache."""
        await self.repository.update_user_status(user_id, notification_id, status)

        # Invalidate unread count cache for this user
        keys_to_remove = [
            k for k in self._unread_count_cache if k.startswith(f"{user_id}:")
        ]
        for key in keys_to_remove:
            del self._unread_count_cache[key]

    async def get_user_preferences(
        self, user_id: str
    ) -> UserNotificationPreferences | None:
        """Get user preferences with caching."""
        # Check cache
        if user_id in self._preferences_cache:
            cached_prefs, timestamp = self._preferences_cache[user_id]
            if self._is_cache_valid(timestamp):
                return cached_prefs

        # Cache miss or expired
        preferences = await self.repository.get_user_preferences(user_id)

        # Update cache
        self._preferences_cache[user_id] = (preferences, time.time())

        return preferences

    async def set_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Set preferences and update cache."""
        await self.repository.set_user_preferences(user_id, preferences)

        # Update cache
        self._preferences_cache[user_id] = (preferences, time.time())

    async def count_unread(self, user_id: str, account_ids: list[str]) -> int:
        """Count unread notifications with caching."""
        # Create cache key
        cache_key = self._make_count_cache_key(user_id, account_ids)

        # Check cache
        if cache_key in self._unread_count_cache:
            count, timestamp = self._unread_count_cache[cache_key]
            if self._is_cache_valid(timestamp):
                return count

        # Cache miss or expired
        count = await self.repository.count_unread(user_id, account_ids)

        # Update cache
        self._unread_count_cache[cache_key] = (count, time.time())

        return count

    async def get_users_by_account(
        self, account_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        """Get users by account (no caching for user lists)."""
        return await self.repository.get_users_by_account(account_id)

    async def batch_create_user_statuses(
        self,
        statuses: list[dict[str, Any]],
    ) -> None:
        """Batch create statuses and invalidate caches."""
        await self.repository.batch_create_user_statuses(statuses)

        # Invalidate unread count cache for affected users
        user_ids = {status["user_id"] for status in statuses}
        keys_to_remove = []
        for key in self._unread_count_cache:
            if any(key.startswith(f"{uid}:") for uid in user_ids):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._unread_count_cache[key]

    async def archive_old_notifications(self, days: int = 30) -> int:
        """Archive old notifications and clear caches."""
        result = await self.repository.archive_old_notifications(days)

        # Clear all caches since many notifications may have changed
        self._unread_count_cache.clear()

        return result
