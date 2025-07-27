#!/usr/bin/env python3
"""
Script to check a specific user by their document ID.
"""

import os
import sys
from google.cloud import firestore

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_user_by_id(user_id: str):
    """Check user by document ID."""
    # Initialize Firestore client
    db = firestore.Client(project="ken-e-dev", database="(default)")
    
    print(f"Checking user document: {user_id}")
    print(f"Project: ken-e-dev")
    print(f"Database: (default)")
    print("="*80)
    
    # Get user document directly by ID
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        print(f"\n❌ User document {user_id} not found!")
        return False
    
    user_data = user_doc.to_dict()
    user_profile = user_data.get("profile", {})
    
    print(f"\n✅ Found user: {user_id}")
    print(f"Email: {user_profile.get('email', 'N/A')}")
    print(f"Name: {user_profile.get('first_name', '')} {user_profile.get('last_name', '')}")
    
    # Check permissions
    permissions = user_data.get("permissions", {})
    print(f"\nPermissions structure:")
    print(f"  - accounts: {permissions.get('accounts', {})}")
    print(f"  - organizations: {permissions.get('organizations', {})}")
    print(f"  - account_permissions: {permissions.get('account_permissions', {})}")
    
    # Extract all accessible accounts
    account_permissions = permissions.get("accounts", {})
    account_level_permissions = permissions.get("account_permissions", {})
    
    all_accessible_accounts = set(account_permissions.keys())
    all_accessible_accounts.update(account_level_permissions.keys())
    
    print(f"\nAccessible accounts: {list(all_accessible_accounts)}")
    
    # Check if user has access to the test account
    test_account = "acc_4eac7dbf731b4c39bd983014efd6c7c8"
    if test_account in all_accessible_accounts:
        print(f"\n✅ User has access to test account {test_account}")
        print(f"   Role: {account_permissions.get(test_account) or account_level_permissions.get(test_account)}")
    else:
        print(f"\n❌ User does NOT have access to test account {test_account}")
    
    # Check notification preferences
    pref_ref = user_ref.collection("preferences").document("notifications")
    pref_doc = pref_ref.get()
    
    if pref_doc.exists:
        print(f"\n✅ User has notification preferences")
        pref_data = pref_doc.to_dict()
        print(f"  Categories: {pref_data.get('categories', [])}")
        print(f"  Channels: {pref_data.get('channels', [])}")
    else:
        print(f"\n❌ User missing notification preferences")
    
    # Check recent notification status
    status_collection = user_ref.collection("notification_status")
    status_docs = list(status_collection.limit(5).stream())
    
    print(f"\nNotification status documents: {len(status_docs)} (showing up to 5)")
    if status_docs:
        for doc in status_docs:
            data = doc.to_dict()
            print(f"  - {doc.id}: status={data.get('status', 'unknown')}, updated={data.get('updated_at', 'N/A')}")
    
    return True


def main():
    """Main function."""
    if len(sys.argv) < 2:
        # Default to the user ID mentioned
        user_id = "YAQkqxG4zab9FL7flwyfQ3E4Ucu2"
    else:
        user_id = sys.argv[1]
    
    try:
        if check_user_by_id(user_id):
            print("\n✅ Check completed!")
        else:
            print("\n❌ Check failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()