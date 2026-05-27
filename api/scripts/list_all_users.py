#!/usr/bin/env python3
"""
Script to list all users and their emails.
"""

import os
import sys

from google.cloud import firestore

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def list_all_users():
    """List all users in Firestore."""
    # Initialize Firestore client
    db = firestore.Client()

    # Get all users
    users_ref = db.collection("users")
    users = users_ref.stream()

    print("All users in Firestore:")
    print("=" * 80)

    count = 0
    for user_doc in users:
        count += 1
        user_data = user_doc.to_dict()
        user_profile = user_data.get("profile", {})
        user_email = user_profile.get("email", "")

        print(f"\nUser {count}:")
        print(f"  ID: {user_doc.id}")
        print(f"  Email: {user_email}")
        print(
            f"  Name: {user_profile.get('first_name', '')} {user_profile.get('last_name', '')}"
        )

        # Check permissions
        permissions = user_data.get("permissions", {})
        account_permissions = permissions.get("accounts", {})
        org_permissions = permissions.get("organizations", {})

        print(f"  Organizations: {list(org_permissions.keys())}")
        print(f"  Accounts: {list(account_permissions.keys())}")

        # Check if email contains 'kenneth' to find our user
        if "kenneth" in user_email.lower():
            print("  >>> This might be the user we're looking for!")

    print(f"\nTotal users: {count}")


def main():
    """Main function."""
    try:
        list_all_users()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
