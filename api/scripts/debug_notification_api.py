#!/usr/bin/env python3
"""
Script to debug notification API endpoint behavior.
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import firestore
from kene_api.services.notification_service import NotificationService
from kene_api.models.notifications import NotificationStatus


async def debug_notifications():
    """Debug notification retrieval for a specific user."""
    # Initialize services
    db = firestore.Client(project="ken-e-dev", database="(default)")
    notification_service = NotificationService(db)
    
    # User to test
    user_id = "YAQkqxG4zab9FL7flwyfQ3E4Ucu2"
    user_email = "kennethcwilliams@gmail.com"
    account_ids = ["acc_4eac7dbf731b4c39bd983014efd6c7c8"]
    
    print(f"Debugging notifications for user: {user_email} ({user_id})")
    print(f"Account IDs: {account_ids}")
    print("="*80)
    
    # Test 1: Check user preferences
    print("\n1. Checking user preferences:")
    try:
        prefs = await notification_service.get_user_preferences(user_id)
        print(f"   ✅ Preferences found:")
        print(f"      Categories: {prefs.categories[:3]}... ({len(prefs.categories)} total)")
        print(f"      Channels: {prefs.channels}")
    except Exception as e:
        print(f"   ❌ Error getting preferences: {e}")
    
    # Test 2: Get notifications without archived
    print("\n2. Getting notifications (excluding archived):")
    try:
        notifications = await notification_service.get_user_notifications(
            user_id=user_id,
            account_ids=account_ids,
            include_archived=False
        )
        print(f"   Found {len(notifications)} notifications")
        
        now = datetime.now()
        for notif in notifications[:3]:  # Show first 3
            archived_at = datetime.fromisoformat(notif.notification.archived_at.replace('Z', '+00:00')) if notif.notification.archived_at else None
            is_archived = archived_at and archived_at < now if archived_at else False
            
            print(f"\n   Notification: {notif.notification.id}")
            print(f"      Category: {notif.notification.category}")
            print(f"      Description: {notif.notification.description}")
            print(f"      Created: {notif.notification.created_at}")
            print(f"      Archived at: {notif.notification.archived_at}")
            print(f"      Is archived: {is_archived}")
            print(f"      User status: {notif.status}")
    except Exception as e:
        print(f"   ❌ Error getting notifications: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Get notifications including archived
    print("\n\n3. Getting notifications (including archived):")
    try:
        all_notifications = await notification_service.get_user_notifications(
            user_id=user_id,
            account_ids=account_ids,
            include_archived=True
        )
        print(f"   Found {len(all_notifications)} total notifications (including archived)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 4: Check notification filtering logic
    print("\n\n4. Checking notification filtering:")
    notifications_ref = db.collection("notifications")
    raw_notifications = notifications_ref.where("account_id", "in", account_ids).stream()
    
    count = 0
    for doc in raw_notifications:
        count += 1
        data = doc.to_dict()
        print(f"\n   Raw notification {count}: {data.get('id')}")
        print(f"      Archived at: {data.get('archived_at')}")
        
        # Check if it should be visible
        archived_at = data.get('archived_at')
        if archived_at:
            try:
                archived_datetime = datetime.fromisoformat(archived_at.replace('Z', '+00:00'))
                is_future = archived_datetime > datetime.now()
                print(f"      Archive date is in future: {is_future}")
            except:
                print(f"      Could not parse archive date")


async def main():
    """Main function."""
    try:
        await debug_notifications()
        print("\n✅ Debug completed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())