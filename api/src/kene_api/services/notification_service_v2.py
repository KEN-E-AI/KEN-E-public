"""Improved notification service using repository pattern."""

import logging
import random
from datetime import datetime, timedelta
from typing import Any

from ..models.kene_models import (
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    NotificationWithStatus,
    UserNotificationPreferences,
)
from ..repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications using repository pattern."""

    def __init__(self, repository: NotificationRepository):
        """Initialize the notification service.

        Args:
            repository: Notification repository implementation
        """
        self.repository = repository

    async def create_notification(
        self,
        account_id: str,
        category: NotificationCategory,
        description: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Create a new notification for an account.

        Args:
            account_id: The account ID this notification belongs to
            category: The notification category
            description: Short description of the notification
            data: Optional JSON data

        Returns:
            The created notification ID
        """
        # Generate unique notification ID
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        random_num = random.randint(0, 1000)
        notification_id = f"notif_{account_id}_{timestamp_ms}_{random_num}"

        # Calculate auto-archive timestamp (30 days from now)
        archived_at = (datetime.now() + timedelta(days=30)).isoformat()

        # Create notification object
        notification = Notification(
            id=notification_id,
            account_id=account_id,
            category=category,
            description=description,
            data=data or {},
            created_at=datetime.now().isoformat(),
            archived_at=archived_at,
        )

        # Store notification
        await self.repository.create(notification)

        # Note: User statuses are now created lazily when users query notifications
        # or explicitly by the caller for specific users (more scalable approach)

        logger.info(f"Created notification {notification_id} for account {account_id}")
        return notification_id

    async def _initialize_user_statuses(
        self,
        account_id: str,
        notification_id: str,
        category: NotificationCategory,
    ) -> None:
        """Initialize notification status for all users with access to the account.

        Args:
            account_id: The account ID
            notification_id: The notification ID
            category: The notification category
        """
        # Get all users with access to this account
        users_with_access = await self.repository.get_users_by_account(account_id)

        statuses_to_create = []

        for user_id, user_data in users_with_access:
            # Get user's notification preferences
            user_prefs = await self.repository.get_user_preferences(user_id)

            # Determine initial status based on preferences
            if user_prefs and category in user_prefs.categories:
                status = NotificationStatus.UNREAD
            else:
                status = NotificationStatus.EXCLUDED

            # Add to batch
            statuses_to_create.append(
                {
                    "user_id": user_id,
                    "notification_id": notification_id,
                    "status": status.value,
                    "updated_at": datetime.now().isoformat(),
                }
            )

        # Batch create statuses
        if statuses_to_create:
            await self.repository.batch_create_user_statuses(statuses_to_create)

    async def get_user_notifications(
        self,
        user_id: str,
        account_ids: list[str],
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationWithStatus]:
        """Get notifications for a user across their accessible accounts.

        Args:
            user_id: The user ID
            account_ids: List of account IDs the user has access to
            include_archived: Whether to include archived notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip

        Returns:
            List of notifications with user-specific status
        """
        # Get notifications for accessible accounts
        notifications = await self.repository.get_by_account(
            account_ids=account_ids,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

        if not notifications:
            return []

        # Get user statuses for these notifications
        notification_ids = [n.id for n in notifications]
        user_statuses = await self.repository.get_user_statuses(
            user_id, notification_ids
        )

        # Combine notifications with user statuses
        notifications_with_status = []

        for notification in notifications:
            status_data = user_statuses.get(
                notification.id, {"status": NotificationStatus.UNREAD.value}
            )

            # Skip if user archived it (unless include_archived is True)
            if (
                not include_archived
                and status_data.get("status") == NotificationStatus.ARCHIVED.value
            ):
                continue

            # Create NotificationWithStatus
            notification_with_status = NotificationWithStatus(
                **notification.model_dump(),
                status=NotificationStatus(
                    status_data.get("status", NotificationStatus.UNREAD.value)
                ),
                read_at=status_data.get("read_at"),
                user_archived_at=status_data.get("archived_at"),
            )

            notifications_with_status.append(notification_with_status)

        return notifications_with_status

    async def update_user_notification_status(
        self,
        user_id: str,
        notification_id: str,
        status: NotificationStatus,
    ) -> None:
        """Update notification status for a specific user.

        Args:
            user_id: The user ID
            notification_id: The notification ID
            status: The new status
        """
        await self.repository.update_user_status(user_id, notification_id, status)
        logger.info(
            f"Updated notification {notification_id} status to {status.value} for user {user_id}"
        )

    async def get_user_preferences(self, user_id: str) -> UserNotificationPreferences:
        """Get user's notification preferences.

        Args:
            user_id: The user ID

        Returns:
            User's notification preferences
        """
        preferences = await self.repository.get_user_preferences(user_id)

        if preferences:
            return preferences

        # Return default preferences if not set
        default_prefs = UserNotificationPreferences(
            categories=list(NotificationCategory),  # All categories enabled by default
            channels=[NotificationChannel.UI],  # UI only by default
            updated_at=datetime.now().isoformat(),
        )

        # Save default preferences
        await self.repository.set_user_preferences(user_id, default_prefs)

        return default_prefs

    async def update_user_preferences(
        self,
        user_id: str,
        preferences: UserNotificationPreferences,
    ) -> None:
        """Update user's notification preferences.

        Args:
            user_id: The user ID
            preferences: The new preferences
        """
        # Update timestamp
        preferences.updated_at = datetime.now().isoformat()

        await self.repository.set_user_preferences(user_id, preferences)
        logger.info(f"Updated notification preferences for user {user_id}")

    async def get_unread_count(self, user_id: str, account_ids: list[str]) -> int:
        """Get count of unread notifications for a user.

        Args:
            user_id: The user ID
            account_ids: List of account IDs the user has access to

        Returns:
            Count of unread notifications
        """
        return await self.repository.count_unread(user_id, account_ids)

    async def archive_old_notifications(self) -> int:
        """Archive notifications older than 30 days.

        This method should be called by a scheduled job.

        Returns:
            Number of notifications archived
        """
        return await self.repository.archive_old_notifications(days=30)
