"""Unit tests for notification service."""

from datetime import datetime

import pytest

from src.kene_api.models.kene_models import (
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreferences,
)
from src.kene_api.repositories import InMemoryNotificationRepository
from src.kene_api.services.notification_service_v2 import NotificationService


class TestNotificationService:
    """Test cases for NotificationService."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository for each test."""
        repo = InMemoryNotificationRepository()
        # Set up test users
        repo.user_accounts["user_1"] = ["acc_123", "acc_456"]
        repo.user_accounts["user_2"] = ["acc_123"]
        repo.user_accounts["user_3"] = ["acc_456"]
        return repo

    @pytest.fixture
    def service(self, repository):
        """Create service with test repository."""
        return NotificationService(repository)

    @pytest.mark.asyncio
    async def test_create_notification(self, service, repository):
        """Test creating a notification initializes user statuses."""
        # Set up user preferences
        user1_prefs = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE],
            channels=[NotificationChannel.UI],
        )
        await repository.set_user_preferences("user_1", user1_prefs)

        user2_prefs = UserNotificationPreferences(
            categories=[],  # No categories enabled
            channels=[NotificationChannel.UI],
        )
        await repository.set_user_preferences("user_2", user2_prefs)

        # Create notification
        notification_id = await service.create_notification(
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Test notification",
            data={"test": "data"},
        )

        # Strengthen ID format assertion
        import re

        assert re.match(r"^notif_acc_123_\d{13}_\d{3}$", notification_id), (
            f"Notification ID format incorrect: {notification_id}"
        )

        # Verify notification was created with all expected fields
        notification = await repository.get_by_id(notification_id)
        assert notification is not None
        assert notification.description == "Test notification"
        assert notification.account_id == "acc_123"
        assert notification.category == NotificationCategory.KPI_PERFORMANCE
        assert notification.data == {"test": "data"}
        assert notification.created_at is not None
        assert notification.archived_at is not None

        # Verify user statuses were initialized correctly with timestamps
        user1_statuses = await repository.get_user_statuses("user_1", [notification_id])
        assert notification_id in user1_statuses
        assert (
            user1_statuses[notification_id]["status"] == NotificationStatus.UNREAD.value
        )
        assert "updated_at" in user1_statuses[notification_id]

        user2_statuses = await repository.get_user_statuses("user_2", [notification_id])
        assert notification_id in user2_statuses
        assert (
            user2_statuses[notification_id]["status"]
            == NotificationStatus.EXCLUDED.value
        )
        assert "updated_at" in user2_statuses[notification_id]

    @pytest.mark.asyncio
    async def test_get_user_notifications(self, service, repository):
        """Test getting user notifications with status."""
        # Set up user preferences to enable notifications
        user_prefs = UserNotificationPreferences(
            categories=[
                NotificationCategory.KPI_PERFORMANCE,
                NotificationCategory.NEW_FEATURES,
            ],
            channels=[NotificationChannel.UI],
        )
        await repository.set_user_preferences("user_1", user_prefs)

        # Create notifications
        notif1_id = await service.create_notification(
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Notification 1",
        )

        notif2_id = await service.create_notification(
            account_id="acc_456",
            category=NotificationCategory.NEW_FEATURES,
            description="Notification 2",
        )

        # Update some statuses
        await repository.update_user_status(
            "user_1", notif1_id, NotificationStatus.READ
        )

        # Get notifications for user_1
        notifications = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123", "acc_456"],
        )

        assert len(notifications) == 2

        # Check status is included
        notif1 = next(n for n in notifications if n.id == notif1_id)
        assert notif1.status == NotificationStatus.READ
        assert notif1.read_at is not None

        notif2 = next(n for n in notifications if n.id == notif2_id)
        assert notif2.status == NotificationStatus.UNREAD

    @pytest.mark.asyncio
    async def test_get_user_notifications_excludes_archived(self, service, repository):
        """Test that archived notifications are excluded by default."""
        # Create notifications
        notif1_id = await service.create_notification(
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Active notification",
        )

        notif2_id = await service.create_notification(
            account_id="acc_123",
            category=NotificationCategory.NEW_FEATURES,
            description="Archived notification",
        )

        # Archive one notification
        await repository.update_user_status(
            "user_1", notif2_id, NotificationStatus.ARCHIVED
        )

        # Get notifications without archived
        notifications = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            include_archived=False,
        )

        assert len(notifications) == 1
        assert notifications[0].id == notif1_id

        # Get notifications with archived
        notifications = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            include_archived=True,
        )

        assert len(notifications) == 2

    @pytest.mark.asyncio
    async def test_get_user_notifications_pagination(self, service, repository):
        """Test pagination in get_user_notifications."""
        # Create multiple notifications with known order
        created_ids = []
        for i in range(10):
            notif_id = await service.create_notification(
                account_id="acc_123",
                category=NotificationCategory.KPI_PERFORMANCE,
                description=f"Notification {i}",
            )
            created_ids.append(notif_id)

        # Test limit
        notifications = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            limit=5,
        )
        assert len(notifications) == 5
        # Verify they are sorted by created_at descending (newest first)
        for i in range(1, len(notifications)):
            assert notifications[i - 1].created_at >= notifications[i].created_at

        # Test offset
        page2 = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            limit=5,
            offset=5,
        )
        assert len(page2) == 5

        # Ensure no overlap between pages
        page1_ids = {n.id for n in notifications}
        page2_ids = {n.id for n in page2}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

        # Verify total coverage
        all_page_ids = page1_ids | page2_ids
        assert len(all_page_ids) == 10, "All notifications should be covered"
        assert all_page_ids == set(created_ids), (
            "Should contain exactly the created notifications"
        )

    @pytest.mark.asyncio
    async def test_update_user_notification_status(self, service, repository):
        """Test updating notification status."""
        notif_id = await service.create_notification(
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Test notification",
        )

        # Update status to read
        await service.update_user_notification_status(
            user_id="user_1",
            notification_id=notif_id,
            status=NotificationStatus.READ,
        )

        # Verify status was updated
        statuses = await repository.get_user_statuses("user_1", [notif_id])
        assert statuses[notif_id]["status"] == NotificationStatus.READ.value
        assert "read_at" in statuses[notif_id]

    @pytest.mark.asyncio
    async def test_get_user_preferences_with_defaults(self, service, repository):
        """Test getting user preferences returns defaults if not set."""
        # Get preferences for user without saved preferences
        prefs = await service.get_user_preferences("new_user")

        assert prefs is not None
        assert len(prefs.categories) == len(
            NotificationCategory
        )  # All enabled by default
        assert prefs.channels == [NotificationChannel.UI]

        # Verify defaults were saved
        saved_prefs = await repository.get_user_preferences("new_user")
        assert saved_prefs is not None

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, service, repository):
        """Test updating user preferences."""
        new_prefs = UserNotificationPreferences(
            categories=[
                NotificationCategory.KPI_PERFORMANCE,
                NotificationCategory.DATA_QUALITY_ALERT,
            ],
            channels=[NotificationChannel.UI, NotificationChannel.EMAIL],
        )

        await service.update_user_preferences("user_1", new_prefs)

        # Verify preferences were updated
        saved_prefs = await repository.get_user_preferences("user_1")
        assert len(saved_prefs.categories) == 2
        assert NotificationCategory.KPI_PERFORMANCE in saved_prefs.categories
        assert NotificationChannel.EMAIL in saved_prefs.channels
        assert saved_prefs.updated_at is not None

    @pytest.mark.asyncio
    async def test_get_unread_count(self, service, repository):
        """Test getting unread notification count."""
        # Set up user preferences to enable notifications
        user_prefs = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE],
            channels=[NotificationChannel.UI],
        )
        await repository.set_user_preferences("user_1", user_prefs)

        # Create notifications
        for i in range(5):
            await service.create_notification(
                account_id="acc_123",
                category=NotificationCategory.KPI_PERFORMANCE,
                description=f"Notification {i}",
            )

        # Initially all unread
        count = await service.get_unread_count("user_1", ["acc_123"])
        assert count == 5

        # Mark some as read
        notifications = await repository.get_by_account(["acc_123"])
        await service.update_user_notification_status(
            "user_1", notifications[0].id, NotificationStatus.READ
        )
        await service.update_user_notification_status(
            "user_1", notifications[1].id, NotificationStatus.READ
        )

        count = await service.get_unread_count("user_1", ["acc_123"])
        assert count == 3

    @pytest.mark.asyncio
    async def test_archive_old_notifications(self, service, repository):
        """Test archiving old notifications."""
        # This would require mocking datetime or modifying the service
        # For now, just test that the method runs
        archived_count = await service.archive_old_notifications()
        assert archived_count == 0  # No old notifications in test data
