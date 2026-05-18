#!/usr/bin/env python3
"""
Script to test marking notifications as read.
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import firestore


async def test_mark_as_read():
    """Test marking a notification as read."""
    # Initialize Firestore client for development
    db = firestore.Client(project="ken-e-dev", database="(default)")
    
    # Test data
    user_id = "YAQkqxG4zab9FL7flwyfQ3E4Ucu2"
    test_notification_id = "notif_acc_4eac7dbf731b4c39bd983014efd6c7c8_1753450652205_51"
    
    print("Testing mark notification as read")
    print("="*80)
    print(f"User ID: {user_id}")
    print(f"Notification ID: {test_notification_id}")
    
    # Check if status document exists before
    status_ref = (
        db.collection("users")
        .document(user_id)
        .collection("notification_status")
        .document(test_notification_id)
    )
    
    status_doc_before = status_ref.get()
    print(f"\nStatus document exists before: {'YES' if status_doc_before.exists else 'NO'}")
    if status_doc_before.exists:
        print(f"Current status: {status_doc_before.to_dict()}")
    
    # Simulate marking as read (what the service will do)
    print("\nSimulating mark as read...")
    update_data = {
        "status": "read",
        "updated_at": datetime.now().isoformat(),
        "read_at": datetime.now().isoformat(),
    }
    
    try:
        # This is what the fixed service will do
        status_ref.set(update_data, merge=True)
        print("✅ Successfully marked as read using set(merge=True)")
    except Exception as e:
        print(f"❌ Error with set(merge=True): {e}")
        
        # Show what would happen with update()
        try:
            status_ref.update(update_data)
            print("✅ update() worked (document already existed)")
        except Exception as e2:
            print(f"❌ update() failed (as expected for non-existent doc): {e2}")
    
    # Check status after
    status_doc_after = status_ref.get()
    print(f"\nStatus document exists after: {'YES' if status_doc_after.exists else 'NO'}")
    if status_doc_after.exists:
        print(f"New status: {status_doc_after.to_dict()}")
    
    # Clean up - delete the test status document
    if status_doc_after.exists:
        print("\nCleaning up test data...")
        status_ref.delete()
        print("✅ Test status document deleted")


async def main():
    """Main function."""
    try:
        await test_mark_as_read()
        print("\n✅ Test completed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())