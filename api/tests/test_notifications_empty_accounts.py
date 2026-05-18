"""Test notification service with empty account lists."""

import pytest
from src.kene_api.models.kene_models import NotificationCategory
from src.kene_api.repositories.notification_repository import (
    InMemoryNotificationRepository,
)
from src.kene_api.services.notification_service_v2 import NotificationService


@pytest.mark.asyncio
async def test_get_user_notifications_with_empty_account_list():
    """get_user_notifications returns empty list when user has no accessible accounts."""
    repository = InMemoryNotificationRepository()
    service = NotificationService(repository)

    # Call with empty account list
    result = await service.get_user_notifications(
        user_id="test_user",
        account_ids=[],  # Empty list
        include_archived=False,
    )

    # No accounts means no notifications
    assert result == []


@pytest.mark.asyncio
async def test_get_unread_count_with_empty_account_list():
    """get_unread_count returns 0 when user has no accessible accounts."""
    repository = InMemoryNotificationRepository()
    service = NotificationService(repository)

    # Call with empty account list
    result = await service.get_unread_count(
        user_id="test_user",
        account_ids=[],  # Empty list
    )

    # No accounts means no unread notifications
    assert result == 0


@pytest.mark.asyncio
async def test_get_user_notifications_with_accounts():
    """get_user_notifications returns notifications scoped to accessible accounts."""
    repository = InMemoryNotificationRepository()
    service = NotificationService(repository)

    # Seed notifications across three accounts
    await service.create_notification(
        account_id="account1",
        category=NotificationCategory.KPI_PERFORMANCE,
        description="Automation finished for account1",
    )
    await service.create_notification(
        account_id="account2",
        category=NotificationCategory.KPI_PERFORMANCE,
        description="Automation finished for account2",
    )
    await service.create_notification(
        account_id="account3",
        category=NotificationCategory.KPI_PERFORMANCE,
        description="Automation finished for account3",
    )

    # Call with a subset of accounts the user can access
    result = await service.get_user_notifications(
        user_id="test_user",
        account_ids=["account1", "account2"],
        include_archived=False,
    )

    # Only notifications for the accessible accounts are returned
    assert {n.account_id for n in result} == {"account1", "account2"}
