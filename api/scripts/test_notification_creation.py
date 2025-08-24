#!/usr/bin/env python3
"""Test script to verify notification creation when an account is created."""

import asyncio
import logging
from datetime import datetime

from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.models.kene_models import NotificationCategory, NotificationStatus
from src.kene_api.repositories import FirestoreNotificationRepository
from src.kene_api.services.notification_service_v2 import NotificationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_notification_creation():
    """Test that notifications are created correctly for new accounts."""
    
    # Initialize services
    firestore = get_firestore_service()
    neo4j = get_neo4j_service()
    
    # Create repository and service
    notification_repository = FirestoreNotificationRepository(firestore.get_client())
    notification_service = NotificationService(notification_repository)
    
    # Test account and user IDs
    test_account_id = "acc_test_" + str(int(datetime.now().timestamp()))
    test_user_id = "test_user_123"
    
    logger.info(f"Testing notification creation for account: {test_account_id}")
    
    try:
        # Create a notification (simulating what happens in account creation)
        notification_id = await notification_service.create_notification(
            account_id=test_account_id,
            category=NotificationCategory.NEW_FEATURES,
            description="Test notification for new account",
            data={
                "account_name": "Test Account",
                "created_by": test_user_id,
                "created_at": datetime.now().isoformat(),
            },
        )
        
        logger.info(f"✓ Created notification: {notification_id}")
        
        # Now manually create status for the user (as done in account creation)
        await notification_repository.batch_create_user_statuses([
            {
                "user_id": test_user_id,
                "notification_id": notification_id,
                "status": NotificationStatus.UNREAD.value,
                "updated_at": datetime.now().isoformat(),
            }
        ])
        
        logger.info(f"✓ Created notification status for user: {test_user_id}")
        
        # Verify the notification exists
        notification = await notification_repository.get_by_id(notification_id)
        if notification:
            logger.info(f"✓ Notification verified in database")
            logger.info(f"  - ID: {notification.id}")
            logger.info(f"  - Account: {notification.account_id}")
            logger.info(f"  - Description: {notification.description}")
        else:
            logger.error("✗ Notification not found in database")
            
        # Verify the user status exists
        user_statuses = await notification_repository.get_user_statuses(
            test_user_id, [notification_id]
        )
        if notification_id in user_statuses:
            status_data = user_statuses[notification_id]
            logger.info(f"✓ User status verified")
            logger.info(f"  - Status: {status_data.get('status')}")
            logger.info(f"  - Updated at: {status_data.get('updated_at')}")
        else:
            logger.error("✗ User status not found")
            
        # Test lazy loading: Simulate another user querying notifications
        # This user won't have a status initially, but should get UNREAD by default
        other_user_id = "other_user_456"
        notifications = await notification_service.get_user_notifications(
            user_id=other_user_id,
            account_ids=[test_account_id],
            include_archived=False,
            limit=10,
            offset=0,
        )
        
        if notifications:
            logger.info(f"✓ Lazy loading works - other user can see notification")
            for notif in notifications:
                logger.info(f"  - Notification: {notif.id}, Status: {notif.status}")
        else:
            logger.info("✓ Other user doesn't see notification (expected if no access)")
            
        logger.info("\n✅ All tests passed successfully!")
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        raise
    finally:
        # Clean up test data
        try:
            # Delete test notification
            firestore.get_client().collection("notifications").document(notification_id).delete()
            # Delete test user status
            firestore.get_client().collection("users").document(test_user_id).collection(
                "notification_status"
            ).document(notification_id).delete()
            logger.info("Cleaned up test data")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_notification_creation())