#!/usr/bin/env python3
"""Debug script to test notification creation and retrieval for new accounts."""

import asyncio
import logging
from datetime import datetime

from src.kene_api.auth.models import UserContext
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.models.kene_models import NotificationCategory, NotificationStatus
from src.kene_api.repositories import FirestoreNotificationRepository
from src.kene_api.services.notification_service_v2 import NotificationService

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def simulate_account_creation_and_notification():
    """Simulate what happens when an org admin creates an account."""
    
    # Initialize services
    firestore = get_firestore_service()
    # neo4j = get_neo4j_service()  # Skip Neo4j for this test
    # await neo4j.connect()
    
    # Test data
    test_org_id = "test_org_123"
    test_account_id = "acc_test_" + str(int(datetime.now().timestamp()))
    test_user_id = "org_admin_user_123"
    
    logger.info(f"\n=== SIMULATING ACCOUNT CREATION ===")
    logger.info(f"Organization: {test_org_id}")
    logger.info(f"Account: {test_account_id}")
    logger.info(f"User (org admin): {test_user_id}")
    
    # Create a mock org admin user context
    user_context = UserContext(
        user_id=test_user_id,
        email="admin@test.org",
        accessible_accounts=[],  # Org admins don't have explicit account permissions
        permissions={},
        organization_permissions={test_org_id: "admin"},  # Org admin
        account_permissions={}
    )
    
    logger.info(f"\n1. USER CONTEXT:")
    logger.info(f"   - Is org admin: {user_context.organization_permissions.get(test_org_id) == 'admin'}")
    logger.info(f"   - Accessible accounts (explicit): {user_context.accessible_accounts}")
    logger.info(f"   - Has account access (should be True for org admin): {user_context.has_account_access(test_account_id)}")
    
    # Create notification repository and service
    notification_repository = FirestoreNotificationRepository(firestore.get_client())
    notification_service = NotificationService(notification_repository)
    
    # Step 1: Create notification (as done in account creation)
    logger.info(f"\n2. CREATING NOTIFICATION:")
    try:
        notification_id = await notification_service.create_notification(
            account_id=test_account_id,
            category=NotificationCategory.NEW_FEATURES,
            description="Configure your new account",
            data={
                "account_name": "Test Account",
                "created_by": test_user_id,
                "created_at": datetime.now().isoformat(),
            },
        )
        logger.info(f"   ✓ Created notification: {notification_id}")
    except Exception as e:
        logger.error(f"   ✗ Failed to create notification: {e}")
        return
    
    # Step 2: Create user status (as done in account creation after our fix)
    logger.info(f"\n3. CREATING USER STATUS:")
    try:
        await notification_repository.batch_create_user_statuses([
            {
                "user_id": test_user_id,
                "notification_id": notification_id,
                "status": NotificationStatus.UNREAD.value,
                "updated_at": datetime.now().isoformat(),
            }
        ])
        logger.info(f"   ✓ Created notification status for user")
    except Exception as e:
        logger.error(f"   ✗ Failed to create user status: {e}")
    
    # Step 3: Simulate what the notifications endpoint does
    logger.info(f"\n4. SIMULATING NOTIFICATION QUERY (as org admin):")
    
    # Check if accessible_accounts is empty (it should be for org admin)
    if not user_context.accessible_accounts:
        logger.info("   - User has no explicit account permissions (expected for org admin)")
        
        # Check if user is org admin
        if any(role == "admin" for role in user_context.organization_permissions.values()):
            logger.info("   - User is org admin, need to fetch organization accounts")
            
            # For this simulation, we'll use our test account
            account_ids = [test_account_id]
            logger.info(f"   - Would query Neo4j for all accounts in org {test_org_id}")
            logger.info(f"   - Using test account: {account_ids}")
    else:
        account_ids = user_context.accessible_accounts
    
    # Step 4: Get notifications
    logger.info(f"\n5. FETCHING NOTIFICATIONS:")
    try:
        notifications = await notification_service.get_user_notifications(
            user_id=test_user_id,
            account_ids=account_ids,
            include_archived=False,
            limit=10,
            offset=0,
        )
        
        if notifications:
            logger.info(f"   ✓ Found {len(notifications)} notification(s)")
            for notif in notifications:
                logger.info(f"      - ID: {notif.id}")
                logger.info(f"      - Description: {notif.description}")
                logger.info(f"      - Status: {notif.status}")
                logger.info(f"      - Account: {notif.account_id}")
        else:
            logger.error(f"   ✗ No notifications found")
    except Exception as e:
        logger.error(f"   ✗ Failed to fetch notifications: {e}")
    
    # Step 5: Check what's actually in Firestore
    logger.info(f"\n6. CHECKING FIRESTORE DIRECTLY:")
    
    # Check if notification exists
    notif_doc = firestore.get_client().collection("notifications").document(notification_id).get()
    if notif_doc.exists:
        logger.info(f"   ✓ Notification exists in Firestore")
        notif_data = notif_doc.to_dict()
        logger.info(f"      - Account ID: {notif_data.get('account_id')}")
        logger.info(f"      - Category: {notif_data.get('category')}")
    else:
        logger.error(f"   ✗ Notification NOT found in Firestore")
    
    # Check if user status exists
    status_doc = (
        firestore.get_client()
        .collection("users")
        .document(test_user_id)
        .collection("notification_status")
        .document(notification_id)
        .get()
    )
    if status_doc.exists:
        logger.info(f"   ✓ User status exists in Firestore")
        status_data = status_doc.to_dict()
        logger.info(f"      - Status: {status_data.get('status')}")
        logger.info(f"      - Updated at: {status_data.get('updated_at')}")
    else:
        logger.error(f"   ✗ User status NOT found in Firestore")
    
    logger.info(f"\n=== SIMULATION COMPLETE ===")
    
    # Cleanup
    try:
        firestore.get_client().collection("notifications").document(notification_id).delete()
        firestore.get_client().collection("users").document(test_user_id).collection(
            "notification_status"
        ).document(notification_id).delete()
        logger.info("Cleaned up test data")
    except:
        pass
    
    # await neo4j.close()


if __name__ == "__main__":
    asyncio.run(simulate_account_creation_and_notification())