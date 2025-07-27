#!/usr/bin/env python3
"""
Script to check recent notifications and who has access to them.
"""

import os
import sys
from google.cloud import firestore
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_notifications():
    """Check recent notifications."""
    # Initialize Firestore client
    db = firestore.Client()
    
    # Get all notifications to check the test one
    notifications_ref = db.collection("notifications")
    all_notifications = notifications_ref.stream()
    
    print("All notifications:")
    print("="*80)
    
    count = 0
    for notif_doc in all_notifications:
        count += 1
        if count > 10:  # Limit to first 10 to avoid too much output
            print("\n... (showing first 10 only)")
            break
        notif_data = notif_doc.to_dict()
        print(f"\nNotification ID: {notif_data.get('id', notif_doc.id)}")
        print(f"  Account ID: {notif_data.get('account_id')}")
        print(f"  Category: {notif_data.get('category')}")
        print(f"  Description: {notif_data.get('description')}")
        print(f"  Created at: {notif_data.get('created_at')}")
        
        # Check which users have access to this account
        account_id = notif_data.get('account_id')
        if account_id:
            print(f"\n  Users with access to account {account_id}:")
            
            # Get all users and check their permissions
            users_ref = db.collection("users")
            users = users_ref.stream()
            
            users_with_access = []
            for user_doc in users:
                user_data = user_doc.to_dict()
                permissions = user_data.get("permissions", {})
                account_permissions = permissions.get("accounts", {})
                
                if account_id in account_permissions:
                    user_email = user_data.get("profile", {}).get("email", "unknown")
                    users_with_access.append(f"{user_email} (role: {account_permissions[account_id]})")
            
            if users_with_access:
                for user in users_with_access:
                    print(f"    - {user}")
            else:
                print("    - No users have direct access to this account")


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