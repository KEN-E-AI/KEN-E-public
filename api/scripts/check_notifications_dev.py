#!/usr/bin/env python3
"""
Script to check notifications in development environment.
"""

import os
import sys
from google.cloud import firestore
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_notifications():
    """Check notifications for the test account."""
    # Initialize Firestore client for development
    db = firestore.Client(project="ken-e-dev", database="(default)")
    
    test_account = "acc_4eac7dbf731b4c39bd983014efd6c7c8"
    
    print(f"Checking notifications for account: {test_account}")
    print(f"Project: ken-e-dev")
    print(f"Database: (default)")
    print("="*80)
    
    # Get all notifications for this account
    notifications_ref = db.collection("notifications")
    account_notifications = notifications_ref.where("account_id", "==", test_account).stream()
    
    notif_count = 0
    notifications = []
    
    for notif_doc in account_notifications:
        notif_count += 1
        notif_data = notif_doc.to_dict()
        notifications.append({
            "id": notif_data.get('id', notif_doc.id),
            "category": notif_data.get('category'),
            "description": notif_data.get('description'),
            "created_at": notif_data.get('created_at'),
            "archived_at": notif_data.get('archived_at'),
            "data": notif_data.get('data', {})
        })
    
    if notif_count == 0:
        print(f"\n❌ No notifications found for account {test_account}")
        
        # Check recent notifications in general
        print("\nChecking recent notifications (any account):")
        recent = notifications_ref.limit(5).stream()
        for doc in recent:
            data = doc.to_dict()
            print(f"  - ID: {doc.id}, Account: {data.get('account_id')}, Category: {data.get('category')}")
    else:
        print(f"\n✅ Found {notif_count} notification(s) for account {test_account}:")
        for i, notif in enumerate(notifications, 1):
            print(f"\nNotification {i}:")
            print(f"  ID: {notif['id']}")
            print(f"  Category: {notif['category']}")
            print(f"  Description: {notif['description']}")
            print(f"  Created: {notif['created_at']}")
            print(f"  Archived at: {notif['archived_at']}")
            if notif['data']:
                print(f"  Data: {notif['data']}")
    
    # Check specific users and their notification visibility
    print(f"\n\nChecking user access and notification visibility:")
    
    users_to_check = [
        {"id": "YAQkqxG4zab9FL7flwyfQ3E4Ucu2", "email": "kennethcwilliams@gmail.com"},
        {"id": "jt0iNgeBFfNN1comkJWtj6wrftK2", "email": "ken@dive.team"}
    ]
    
    for user_info in users_to_check:
        user_ref = db.collection("users").document(user_info['id'])
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            permissions = user_data.get("permissions", {})
            
            # Check all forms of account access
            has_access = False
            access_type = None
            
            # Direct account access
            if test_account in permissions.get("accounts", {}):
                has_access = True
                access_type = f"direct ({permissions['accounts'][test_account]})"
            
            # Account-level permissions
            if test_account in permissions.get("account_permissions", {}):
                has_access = True
                access_type = f"account_permissions ({permissions['account_permissions'][test_account]})"
            
            print(f"\n{user_info['email']}:")
            print(f"  User exists: ✅")
            print(f"  Has access to account: {'✅' if has_access else '❌'}")
            if has_access:
                print(f"  Access type: {access_type}")
            
            # Check notification preferences
            pref_ref = user_ref.collection("preferences").document("notifications")
            pref_doc = pref_ref.get()
            print(f"  Has notification preferences: {'✅' if pref_doc.exists else '❌'}")
            
            # Based on the notification service logic, this user should see notifications if:
            # 1. They have access to the account
            # 2. They have notification preferences
            # 3. The notification is not archived (or archived_at is in the future)
            
            can_see_notifications = has_access and pref_doc.exists
            print(f"  Should see notifications: {'✅' if can_see_notifications else '❌'}")
        else:
            print(f"\n{user_info['email']}:")
            print(f"  User exists: ❌")


def main():
    """Main function."""
    try:
        check_notifications()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()