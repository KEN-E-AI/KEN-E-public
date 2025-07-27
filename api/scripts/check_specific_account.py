#!/usr/bin/env python3
"""
Script to check a specific account and its notifications.
"""

import os
import sys
from google.cloud import firestore

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_account(account_id: str):
    """Check specific account and related data."""
    # Initialize Firestore client
    db = firestore.Client()
    
    print(f"Checking account: {account_id}")
    print("="*80)
    
    # Check if account exists
    account_ref = db.collection("accounts").document(account_id)
    account_doc = account_ref.get()
    
    if account_doc.exists:
        print(f"\n✅ Account exists in Firestore")
        account_data = account_doc.to_dict()
        print(f"  Name: {account_data.get('name', 'N/A')}")
        print(f"  Organization: {account_data.get('organization_id', 'N/A')}")
    else:
        print(f"\n❌ Account NOT found in Firestore")
    
    # Check notifications for this account
    notifications_ref = db.collection("notifications")
    account_notifications = notifications_ref.where("account_id", "==", account_id).stream()
    
    notif_count = 0
    print(f"\nNotifications for account {account_id}:")
    for notif_doc in account_notifications:
        notif_count += 1
        notif_data = notif_doc.to_dict()
        print(f"\n  Notification {notif_count}:")
        print(f"    ID: {notif_data.get('id', notif_doc.id)}")
        print(f"    Category: {notif_data.get('category')}")
        print(f"    Description: {notif_data.get('description')}")
        print(f"    Created: {notif_data.get('created_at', 'N/A')}")
    
    if notif_count == 0:
        print("  No notifications found for this account")
    
    # Check which users have access to this account
    print(f"\n\nUsers with access to account {account_id}:")
    users_ref = db.collection("users")
    users = users_ref.stream()
    
    users_with_access = []
    for user_doc in users:
        user_data = user_doc.to_dict()
        permissions = user_data.get("permissions", {})
        
        # Check accounts permissions
        account_permissions = permissions.get("accounts", {})
        if account_id in account_permissions:
            user_email = user_data.get("profile", {}).get("email", "unknown")
            users_with_access.append({
                "email": user_email,
                "id": user_doc.id,
                "role": account_permissions[account_id],
                "type": "direct"
            })
        
        # Check account_permissions (new structure)
        account_level_permissions = permissions.get("account_permissions", {})
        if account_id in account_level_permissions:
            user_email = user_data.get("profile", {}).get("email", "unknown")
            users_with_access.append({
                "email": user_email,
                "id": user_doc.id,
                "role": account_level_permissions[account_id],
                "type": "account_level"
            })
    
    if users_with_access:
        for user in users_with_access:
            print(f"  - {user['email']} (ID: {user['id']}, role: {user['role']}, type: {user['type']})")
    else:
        print("  - No users have access to this account")
    
    # Check if the account belongs to any organization that users have access to
    if account_doc.exists:
        org_id = account_data.get('organization_id')
        if org_id:
            print(f"\n\nOrganization {org_id} members:")
            for user_doc in users_ref.stream():
                user_data = user_doc.to_dict()
                org_permissions = user_data.get("permissions", {}).get("organizations", {})
                if org_id in org_permissions:
                    user_email = user_data.get("profile", {}).get("email", "unknown")
                    print(f"  - {user_email} (org role: {org_permissions[org_id]})")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        # Default to the test account
        account_id = "acc_4eac7dbf731b4c39bd983014efd6c7c8"
    else:
        account_id = sys.argv[1]
    
    try:
        check_account(account_id)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()