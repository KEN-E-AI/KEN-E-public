#!/usr/bin/env python3
"""
Script to check user permissions and accessible accounts.
"""

import os
import sys
from google.cloud import firestore

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_user_permissions(email: str):
    """Check user permissions and accessible accounts."""
    # Initialize Firestore client
    db = firestore.Client()
    
    # Find user by email
    users_ref = db.collection("users")
    users = users_ref.stream()
    
    user_found = False
    
    for user_doc in users:
        user_data = user_doc.to_dict()
        user_profile = user_data.get("profile", {})
        user_email = user_profile.get("email", "")
        
        if user_email.lower() == email.lower():
            user_found = True
            user_id = user_doc.id
            
            print(f"Found user: {user_id}")
            print(f"Email: {user_email}")
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
            else:
                print(f"\n❌ User does NOT have access to test account {test_account}")
            
            # Check notification preferences
            pref_ref = users_ref.document(user_id).collection("preferences").document("notifications")
            pref_doc = pref_ref.get()
            
            if pref_doc.exists:
                print(f"\n✅ User has notification preferences")
                pref_data = pref_doc.to_dict()
                print(f"  Categories: {pref_data.get('categories', [])}")
                print(f"  Channels: {pref_data.get('channels', [])}")
            else:
                print(f"\n❌ User missing notification preferences")
            
            break
    
    if not user_found:
        print(f"❌ User with email '{email}' not found!")
        return False
    
    return True


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python check_user_permissions.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    print(f"Checking permissions for user: {email}")
    print("="*50)
    
    try:
        if check_user_permissions(email):
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