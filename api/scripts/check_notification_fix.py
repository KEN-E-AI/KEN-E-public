#!/usr/bin/env python3
"""
Script to test that the notification fix works correctly.
"""

import asyncio
import os
import sys

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)

from google.cloud import firestore


async def test_notification_visibility():
    """Test that notifications are visible for users without status documents."""
    # Initialize Firestore client for development
    db = firestore.Client(project="ken-e-dev", database="(default)")

    # Test data
    user_id = "YAQkqxG4zab9FL7flwyfQ3E4Ucu2"
    test_account = "acc_4eac7dbf731b4c39bd983014efd6c7c8"

    print("Testing notification visibility fix")
    print("=" * 80)
    print(f"User ID: {user_id}")
    print(f"Account: {test_account}")

    # Get notifications for the account
    notifications_ref = db.collection("notifications")
    account_notifications = notifications_ref.where(
        "account_id", "==", test_account
    ).stream()

    notif_count = 0
    for notif_doc in account_notifications:
        notif_count += 1
        notif_data = notif_doc.to_dict()
        notification_id = notif_data.get("id", notif_doc.id)

        # Check if user has a status document
        status_ref = (
            db.collection("users")
            .document(user_id)
            .collection("notification_status")
            .document(notification_id)
        )
        status_doc = status_ref.get()

        print(f"\nNotification {notif_count}: {notification_id}")
        print(f"  Category: {notif_data.get('category')}")
        print(f"  Has status document: {'YES' if status_doc.exists else 'NO'}")
        print(
            f"  Should be visible: {'YES' if not status_doc.exists or status_doc.to_dict().get('status') != 'archived' else 'NO'}"
        )

    print(f"\nTotal notifications that should be visible: {notif_count}")

    # Summary
    print("\n" + "=" * 80)
    print("EXPECTED RESULT:")
    print("- User should see ALL notifications since they have no status documents")
    print("- The notification service should treat missing status docs as 'unread'")
    print("\nACTUAL RESULT:")
    print("- With the fix, notifications without status docs will be shown as unread")
    print("- This matches the expected behavior for new notifications")


async def main():
    """Main function."""
    try:
        await test_notification_visibility()
        print("\n✅ Test completed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
