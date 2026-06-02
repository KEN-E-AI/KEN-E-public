"""Notification repository interface and implementations."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from ..models.kene_models import (
    Notification,
    NotificationStatus,
    UserNotificationPreferences,
)


class NotificationRepository(ABC):
    """Abstract base class for notification data access."""

    @abstractmethod
    async def create(self, notification: Notification) -> str:
        """Create a new notification.

        Args:
            notification: The notification to create

        Returns:
            The created notification ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, notification_id: str) -> Notification | None:
        """Get a notification by ID.

        Args:
            notification_id: The notification ID

        Returns:
            The notification or None if not found
        """
        pass

    @abstractmethod
    async def get_by_account(
        self,
        account_ids: list[str],
        include_archived: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for specified accounts.

        Args:
            account_ids: List of account IDs
            include_archived: Whether to include archived notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip

        Returns:
            List of notifications
        """
        pass

    @abstractmethod
    async def get_user_statuses(
        self,
        user_id: str,
        notification_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get user's statuses for specific notifications.

        Args:
            user_id: The user ID
            notification_ids: List of notification IDs

        Returns:
            Dict mapping notification_id to status data
        """
        pass

    @abstractmethod
    async def update_user_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        """Update a user's notification status.

        Args:
            user_id: The user ID
            notification_id: The notification ID
            status: The new status
        """
        pass

    @abstractmethod
    async def get_user_preferences(
        self, user_id: str
    ) -> UserNotificationPreferences | None:
        """Get user's notification preferences.

        Args:
            user_id: The user ID

        Returns:
            User preferences or None if not set
        """
        pass

    @abstractmethod
    async def set_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Set user's notification preferences.

        Args:
            user_id: The user ID
            preferences: The preferences to set
        """
        pass

    @abstractmethod
    async def count_unread(self, user_id: str, account_ids: list[str]) -> int:
        """Count unread notifications for a user.

        Args:
            user_id: The user ID
            account_ids: List of accessible account IDs

        Returns:
            Count of unread notifications
        """
        pass

    @abstractmethod
    async def get_users_by_account(
        self, account_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        """Get all users with access to an account.

        Args:
            account_id: The account ID

        Returns:
            List of tuples (user_id, user_data)
        """
        pass

    @abstractmethod
    async def batch_create_user_statuses(
        self,
        statuses: list[dict[str, Any]],
    ) -> None:
        """Create multiple user notification statuses in batch.

        Args:
            statuses: List of status records to create
        """
        pass

    @abstractmethod
    async def archive_old_notifications(self, days: int = 30) -> int:
        """Archive notifications older than specified days.

        Args:
            days: Number of days after which to archive

        Returns:
            Number of notifications archived
        """
        pass


class InMemoryNotificationRepository(NotificationRepository):
    """In-memory implementation for testing."""

    def __init__(self):
        self.notifications: dict[str, Notification] = {}
        self.user_statuses: dict[
            str, dict[str, dict[str, Any]]
        ] = {}  # user_id -> notification_id -> status
        self.user_preferences: dict[str, UserNotificationPreferences] = {}
        self.user_accounts: dict[str, list[str]] = {}  # user_id -> account_ids

    async def create(self, notification: Notification) -> str:
        self.notifications[notification.id] = notification
        return notification.id

    async def get_by_id(self, notification_id: str) -> Notification | None:
        return self.notifications.get(notification_id)

    async def get_by_account(
        self,
        account_ids: list[str],
        include_archived: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Notification]:
        notifications = [
            n for n in self.notifications.values() if n.account_id in account_ids
        ]

        if not include_archived:
            now = datetime.now().isoformat()
            notifications = [n for n in notifications if n.archived_at > now]

        # Sort by created_at descending, with notification id as a deterministic
        # tiebreaker. Without the tiebreaker, two notifications with identical
        # created_at (which Firestore can produce on bulk writes within the
        # same millisecond) would sort in arbitrary order, making pagination
        # return the same item on adjacent pages or skip items.
        notifications.sort(key=lambda x: (x.created_at, x.id), reverse=True)

        # Apply pagination
        if offset:
            notifications = notifications[offset:]
        if limit:
            notifications = notifications[:limit]

        return notifications

    async def get_user_statuses(
        self,
        user_id: str,
        notification_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        user_statuses = self.user_statuses.get(user_id, {})
        return {
            nid: user_statuses.get(nid, {"status": "unread"})
            for nid in notification_ids
        }

    async def update_user_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        if user_id not in self.user_statuses:
            self.user_statuses[user_id] = {}

        status_data = {
            "status": status.value,
            "updated_at": datetime.now().isoformat(),
        }

        if status == NotificationStatus.READ:
            status_data["read_at"] = datetime.now().isoformat()
        elif status == NotificationStatus.ARCHIVED:
            status_data["archived_at"] = datetime.now().isoformat()

        self.user_statuses[user_id][notification_id] = status_data

    async def get_user_preferences(
        self, user_id: str
    ) -> UserNotificationPreferences | None:
        return self.user_preferences.get(user_id)

    async def set_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        self.user_preferences[user_id] = preferences

    async def count_unread(self, user_id: str, account_ids: list[str]) -> int:
        notifications = await self.get_by_account(account_ids, include_archived=False)
        user_statuses = self.user_statuses.get(user_id, {})

        count = 0
        for notification in notifications:
            status_data = user_statuses.get(notification.id, {"status": "unread"})
            if status_data.get("status") == "unread":
                count += 1

        return count

    async def get_users_by_account(
        self, account_id: str
    ) -> list[tuple[str, dict[str, Any]]]:
        users = []
        for user_id, accounts in self.user_accounts.items():
            if account_id in accounts:
                users.append(
                    (user_id, {"permissions": {"accounts": {account_id: "user"}}})
                )
        return users

    async def batch_create_user_statuses(
        self,
        statuses: list[dict[str, Any]],
    ) -> None:
        for status in statuses:
            user_id = status["user_id"]
            notification_id = status["notification_id"]

            if user_id not in self.user_statuses:
                self.user_statuses[user_id] = {}

            self.user_statuses[user_id][notification_id] = {
                "status": status["status"],
                "updated_at": status["updated_at"],
            }

    async def archive_old_notifications(self, days: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        archived_count = 0

        for user_id, user_statuses in self.user_statuses.items():
            for notification_id, status_data in user_statuses.items():
                notification = self.notifications.get(notification_id)
                if notification and notification.created_at < cutoff:
                    if status_data.get("status") != NotificationStatus.ARCHIVED.value:
                        status_data["status"] = NotificationStatus.ARCHIVED.value
                        status_data["archived_at"] = datetime.now().isoformat()
                        archived_count += 1

        return archived_count
