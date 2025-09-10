"""Unit tests for cached notification repository."""

import time
from datetime import datetime

import pytest

from src.kene_api.models.kene_models import (
    NotificationCategory,
    NotificationChannel,
    NotificationStatus,
    UserNotificationPreferences,
)
from src.kene_api.repositories import (
    CachedNotificationRepository,
    InMemoryNotificationRepository,
)


class TestCachedNotificationRepository:
    """Test cases for CachedNotificationRepository."""

    @pytest.fixture
    def base_repository(self):
        """Create base repository."""
        return InMemoryNotificationRepository()

    @pytest.fixture
    def cached_repository(self, base_repository):
        """Create cached repository with short TTL for testing."""
        return CachedNotificationRepository(
            base_repository, cache_ttl=1
        )  # 1 second TTL

    async def test_preferences_caching(self, cached_repository, base_repository):
        """Test that preferences are cached."""
        user_id = "user_123"
        prefs = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE],
            channels=[NotificationChannel.UI],
            updated_at=datetime.now().isoformat(),
        )

        # Set preferences
        await cached_repository.set_user_preferences(user_id, prefs)

        # First get - hits database
        result1 = await cached_repository.get_user_preferences(user_id)
        assert result1 is not None

        # Clear base repository to prove cache is used
        base_repository.user_preferences.clear()

        # Second get - should hit cache
        result2 = await cached_repository.get_user_preferences(user_id)
        assert result2 is not None
        assert result2.categories == prefs.categories

        # Wait for cache to expire
        time.sleep(1.1)

        # Third get - should hit database (and get None since we cleared it)
        result3 = await cached_repository.get_user_preferences(user_id)
        assert result3 is None

    async def test_preferences_cache_invalidation_on_update(self, cached_repository):
        """Test that cache is updated when preferences are set."""
        user_id = "user_123"

        # Set initial preferences
        prefs1 = UserNotificationPreferences(
            categories=[NotificationCategory.KPI_PERFORMANCE],
            channels=[NotificationChannel.UI],
        )
        await cached_repository.set_user_preferences(user_id, prefs1)

        # Get preferences (cached)
        result1 = await cached_repository.get_user_preferences(user_id)
        assert len(result1.categories) == 1

        # Update preferences
        prefs2 = UserNotificationPreferences(
            categories=[
                NotificationCategory.KPI_PERFORMANCE,
                NotificationCategory.NEW_FEATURES,
            ],
            channels=[NotificationChannel.UI, NotificationChannel.EMAIL],
        )
        await cached_repository.set_user_preferences(user_id, prefs2)

        # Get preferences again - should get updated value from cache
        result2 = await cached_repository.get_user_preferences(user_id)
        assert len(result2.categories) == 2
        assert NotificationChannel.EMAIL in result2.channels

    async def test_unread_count_caching(self, cached_repository, base_repository):
        """Test that unread count is cached."""
        user_id = "user_123"
        account_ids = ["acc_123", "acc_456"]

        # Set up test data
        base_repository._unread_count_cache.clear()  # Clear any existing cache

        # Mock the count method to track calls
        call_count = 0
        original_count_unread = base_repository.count_unread

        async def mock_count_unread(uid, aids):
            nonlocal call_count
            call_count += 1
            return 5

        base_repository.count_unread = mock_count_unread

        # First call - hits database
        count1 = await cached_repository.count_unread(user_id, account_ids)
        assert count1 == 5
        assert call_count == 1

        # Second call - should hit cache
        count2 = await cached_repository.count_unread(user_id, account_ids)
        assert count2 == 5
        assert call_count == 1  # No additional call

        # Wait for cache to expire
        time.sleep(1.1)

        # Third call - should hit database again
        count3 = await cached_repository.count_unread(user_id, account_ids)
        assert count3 == 5
        assert call_count == 2

    async def test_unread_count_cache_invalidation(self, cached_repository):
        """Test that unread count cache is invalidated on status update."""
        user_id = "user_123"
        notification_id = "notif_123"
        account_ids = ["acc_123"]

        # Initial count
        await cached_repository.count_unread(user_id, account_ids)

        # Update notification status
        await cached_repository.update_user_status(
            user_id, notification_id, NotificationStatus.READ
        )

        # Cache should be invalidated - verify by checking internal cache
        cache_key = f"{user_id}:acc_123"
        assert cache_key not in cached_repository._unread_count_cache

    async def test_cache_key_generation(self, cached_repository):
        """Test that cache keys are consistent regardless of account order."""
        user_id = "user_123"

        # Different order of same accounts
        key1 = cached_repository._make_count_cache_key(
            user_id, ["acc_123", "acc_456", "acc_789"]
        )
        key2 = cached_repository._make_count_cache_key(
            user_id, ["acc_789", "acc_123", "acc_456"]
        )

        assert key1 == key2

    async def test_batch_operations_invalidate_cache(self, cached_repository):
        """Test that batch operations invalidate affected caches."""
        # Set up initial cached counts
        await cached_repository.count_unread("user_1", ["acc_123"])
        await cached_repository.count_unread("user_2", ["acc_456"])

        # Batch create statuses
        statuses = [
            {
                "user_id": "user_1",
                "notification_id": "notif_1",
                "status": NotificationStatus.UNREAD.value,
                "updated_at": datetime.now().isoformat(),
            }
        ]

        await cached_repository.batch_create_user_statuses(statuses)

        # user_1's cache should be invalidated
        assert not any(
            k.startswith("user_1:") for k in cached_repository._unread_count_cache
        )

        # user_2's cache should still exist
        assert any(
            k.startswith("user_2:") for k in cached_repository._unread_count_cache
        )
