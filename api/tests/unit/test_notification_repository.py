"""Unit tests for notification repository."""

from datetime import datetime, timedelta

import pytest

from kene_api.models.kene_models import (
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreferences,
)
from kene_api.repositories import InMemoryNotificationRepository


class TestInMemoryNotificationRepository:
    """Test cases for InMemoryNotificationRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository for each test."""
        return InMemoryNotificationRepository()

    @pytest.fixture
    def sample_notification(self):
        """Create a sample notification."""
        return Notification(
            id="notif_acc_123_1234567890_456",
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Revenue increased by 15%",
            data={"metric": "revenue", "change": 0.15},
            created_at=datetime.now().isoformat(),
            archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
        )

    async def test_create_notification(self, repository, sample_notification):
        """Test creating a notification."""
        notification_id = await repository.create(sample_notification)
        
        assert notification_id == sample_notification.id
        assert sample_notification.id in repository.notifications

    async def test_get_by_id(self, repository, sample_notification):
        """Test getting notification by ID."""
        await repository.create(sample_notification)
        
        # Test existing notification
        notification = await repository.get_by_id(sample_notification.id)
        assert notification is not None
        assert notification.id == sample_notification.id
        assert notification.description == sample_notification.description
        
        # Test non-existent notification
        notification = await repository.get_by_id("non_existent")
        assert notification is None

    async def test_get_by_account(self, repository):
        """Test getting notifications by account."""
        # Create notifications for different accounts
        notifications = [
            Notification(
                id=f"notif_{i}",
                account_id="acc_123" if i < 3 else "acc_456",
                category=NotificationCategory.KPI_PERFORMANCE,
                description=f"Test notification {i}",
                created_at=datetime.now().isoformat(),
                archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
            )
            for i in range(5)
        ]
        
        for notif in notifications:
            await repository.create(notif)
        
        # Test filtering by account
        acc_123_notifications = await repository.get_by_account(["acc_123"])
        assert len(acc_123_notifications) == 3
        assert all(n.account_id == "acc_123" for n in acc_123_notifications)
        
        # Test multiple accounts
        all_notifications = await repository.get_by_account(["acc_123", "acc_456"])
        assert len(all_notifications) == 5

    async def test_get_by_account_with_pagination(self, repository):
        """Test pagination in get_by_account."""
        # Create 10 notifications
        for i in range(10):
            await repository.create(
                Notification(
                    id=f"notif_{i}",
                    account_id="acc_123",
                    category=NotificationCategory.KPI_PERFORMANCE,
                    description=f"Test notification {i}",
                    created_at=(datetime.now() - timedelta(minutes=i)).isoformat(),
                    archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
                )
            )
        
        # Test limit
        limited = await repository.get_by_account(["acc_123"], limit=5)
        assert len(limited) == 5
        
        # Test offset
        offset_results = await repository.get_by_account(["acc_123"], offset=3, limit=5)
        assert len(offset_results) == 5
        assert offset_results[0].id == "notif_3"

    async def test_user_statuses(self, repository):
        """Test user status operations."""
        user_id = "user_123"
        notification_id = "notif_123"
        
        # Initially no status
        statuses = await repository.get_user_statuses(user_id, [notification_id])
        assert statuses[notification_id]["status"] == "unread"
        
        # Update status to read
        await repository.update_user_status(user_id, notification_id, NotificationStatus.READ)
        
        statuses = await repository.get_user_statuses(user_id, [notification_id])
        assert statuses[notification_id]["status"] == NotificationStatus.READ.value
        assert "read_at" in statuses[notification_id]
        
        # Update status to archived
        await repository.update_user_status(user_id, notification_id, NotificationStatus.ARCHIVED)
        
        statuses = await repository.get_user_statuses(user_id, [notification_id])
        assert statuses[notification_id]["status"] == NotificationStatus.ARCHIVED.value
        assert "archived_at" in statuses[notification_id]

    async def test_user_preferences(self, repository):
        """Test user preferences operations."""
        user_id = "user_123"
        
        # Initially no preferences
        prefs = await repository.get_user_preferences(user_id)
        assert prefs is None
        
        # Set preferences
        new_prefs = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE, NotificationCategory.NEW_FEATURES],
            channels=[NotificationChannel.UI, NotificationChannel.EMAIL],
            updated_at=datetime.now().isoformat(),
        )
        
        await repository.set_user_preferences(user_id, new_prefs)
        
        # Get preferences
        saved_prefs = await repository.get_user_preferences(user_id)
        assert saved_prefs is not None
        assert len(saved_prefs.categories) == 2
        assert NotificationCategory.KPI_PERFORMANCE in saved_prefs.categories
        assert NotificationChannel.EMAIL in saved_prefs.channels

    async def test_count_unread(self, repository):
        """Test counting unread notifications."""
        user_id = "user_123"
        
        # Set up test data
        repository.user_accounts[user_id] = ["acc_123"]
        
        # Create notifications
        for i in range(5):
            notif = Notification(
                id=f"notif_{i}",
                account_id="acc_123",
                category=NotificationCategory.KPI_PERFORMANCE,
                description=f"Test {i}",
                created_at=datetime.now().isoformat(),
                archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
            )
            await repository.create(notif)
        
        # Initially all unread
        count = await repository.count_unread(user_id, ["acc_123"])
        assert count == 5
        
        # Mark some as read
        await repository.update_user_status(user_id, "notif_0", NotificationStatus.READ)
        await repository.update_user_status(user_id, "notif_1", NotificationStatus.READ)
        
        count = await repository.count_unread(user_id, ["acc_123"])
        assert count == 3
        
        # Mark one as archived
        await repository.update_user_status(user_id, "notif_2", NotificationStatus.ARCHIVED)
        
        count = await repository.count_unread(user_id, ["acc_123"])
        assert count == 2

    async def test_batch_create_user_statuses(self, repository):
        """Test batch creating user statuses."""
        statuses = [
            {
                "user_id": "user_1",
                "notification_id": "notif_1",
                "status": NotificationStatus.UNREAD.value,
                "updated_at": datetime.now().isoformat(),
            },
            {
                "user_id": "user_1",
                "notification_id": "notif_2",
                "status": NotificationStatus.EXCLUDED.value,
                "updated_at": datetime.now().isoformat(),
            },
            {
                "user_id": "user_2",
                "notification_id": "notif_1",
                "status": NotificationStatus.UNREAD.value,
                "updated_at": datetime.now().isoformat(),
            },
        ]
        
        await repository.batch_create_user_statuses(statuses)
        
        # Verify statuses were created
        user1_statuses = await repository.get_user_statuses("user_1", ["notif_1", "notif_2"])
        assert user1_statuses["notif_1"]["status"] == NotificationStatus.UNREAD.value
        assert user1_statuses["notif_2"]["status"] == NotificationStatus.EXCLUDED.value
        
        user2_statuses = await repository.get_user_statuses("user_2", ["notif_1"])
        assert user2_statuses["notif_1"]["status"] == NotificationStatus.UNREAD.value

    async def test_archive_old_notifications(self, repository):
        """Test archiving old notifications."""
        # Create old and new notifications
        old_date = (datetime.now() - timedelta(days=31)).isoformat()
        new_date = datetime.now().isoformat()
        
        old_notif = Notification(
            id="old_notif",
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="Old notification",
            created_at=old_date,
            archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
        )
        
        new_notif = Notification(
            id="new_notif",
            account_id="acc_123",
            category=NotificationCategory.KPI_PERFORMANCE,
            description="New notification",
            created_at=new_date,
            archived_at=(datetime.now() + timedelta(days=30)).isoformat(),
        )
        
        await repository.create(old_notif)
        await repository.create(new_notif)
        
        # Set up user statuses
        await repository.update_user_status("user_1", "old_notif", NotificationStatus.UNREAD)
        await repository.update_user_status("user_1", "new_notif", NotificationStatus.UNREAD)
        
        # Archive old notifications
        archived_count = await repository.archive_old_notifications(days=30)
        assert archived_count == 1
        
        # Verify old notification is archived
        statuses = await repository.get_user_statuses("user_1", ["old_notif", "new_notif"])
        assert statuses["old_notif"]["status"] == NotificationStatus.ARCHIVED.value
        assert statuses["new_notif"]["status"] == NotificationStatus.UNREAD.value