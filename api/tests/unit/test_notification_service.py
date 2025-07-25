"""Unit tests for notification service."""

from datetime import datetime

import pytest

from kene_api.models.kene_models import (
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreferences,
)
from kene_api.repositories import InMemoryNotificationRepository
from kene_api.services.notification_service_v2 import NotificationService


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
        
        assert notification_id.startswith("notif_acc_123_")
        
        # Verify notification was created
        notification = await repository.get_by_id(notification_id)
        assert notification is not None
        assert notification.description == "Test notification"
        
        # Verify user statuses were initialized correctly
        user1_statuses = await repository.get_user_statuses("user_1", [notification_id])
        assert user1_statuses[notification_id]["status"] == NotificationStatus.UNREAD.value
        
        user2_statuses = await repository.get_user_statuses("user_2", [notification_id])
        assert user2_statuses[notification_id]["status"] == NotificationStatus.EXCLUDED.value

    async def test_get_user_notifications(self, service, repository):
        """Test getting user notifications with status."""
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
        await repository.update_user_status("user_1", notif1_id, NotificationStatus.READ)
        
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
        await repository.update_user_status("user_1", notif2_id, NotificationStatus.ARCHIVED)
        
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

    async def test_get_user_notifications_pagination(self, service, repository):
        """Test pagination in get_user_notifications."""
        # Create multiple notifications
        for i in range(10):
            await service.create_notification(
                account_id="acc_123",
                category=NotificationCategory.KPI_PERFORMANCE,
                description=f"Notification {i}",
            )
        
        # Test limit
        notifications = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            limit=5,
        )
        assert len(notifications) == 5
        
        # Test offset
        page2 = await service.get_user_notifications(
            user_id="user_1",
            account_ids=["acc_123"],
            limit=5,
            offset=5,
        )
        assert len(page2) == 5
        
        # Ensure no overlap
        page1_ids = {n.id for n in notifications}
        page2_ids = {n.id for n in page2}
        assert len(page1_ids & page2_ids) == 0

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

    async def test_get_user_preferences_with_defaults(self, service, repository):
        """Test getting user preferences returns defaults if not set."""
        # Get preferences for user without saved preferences
        prefs = await service.get_user_preferences("new_user")
        
        assert prefs is not None
        assert len(prefs.categories) == len(NotificationCategory)  # All enabled by default
        assert prefs.channels == [NotificationChannel.UI]
        
        # Verify defaults were saved
        saved_prefs = await repository.get_user_preferences("new_user")
        assert saved_prefs is not None

    async def test_update_user_preferences(self, service, repository):
        """Test updating user preferences."""
        new_prefs = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE, NotificationCategory.DATA_QUALITY_ALERT],
            channels=[NotificationChannel.UI, NotificationChannel.EMAIL],
        )
        
        await service.update_user_preferences("user_1", new_prefs)
        
        # Verify preferences were updated
        saved_prefs = await repository.get_user_preferences("user_1")
        assert len(saved_prefs.categories) == 2
        assert NotificationCategory.KPI_PERFORMANCE in saved_prefs.categories
        assert NotificationChannel.EMAIL in saved_prefs.channels
        assert saved_prefs.updated_at is not None

    async def test_get_unread_count(self, service, repository):
        """Test getting unread notification count."""
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

    async def test_archive_old_notifications(self, service, repository):
        """Test archiving old notifications."""
        # This would require mocking datetime or modifying the service
        # For now, just test that the method runs
        archived_count = await service.archive_old_notifications()
        assert archived_count == 0  # No old notifications in test data