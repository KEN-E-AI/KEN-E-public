#!/usr/bin/env python3
"""
Script to fix missing notification collections for existing users.

This script will:
1. Find all users in Firestore
2. Check if they have the required notification preferences collection
3. Create the missing collections with default values
"""

import os
import sys
from datetime import datetime

from google.cloud import firestore

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fix_user_notification_collections():
    """Fix missing notification collections for all users."""
    # Initialize Firestore client
    db = firestore.Client()

    # Get all users
    users_ref = db.collection("users")
    users = users_ref.stream()

    fixed_count = 0
    total_count = 0

    for user_doc in users:
        total_count += 1
        user_id = user_doc.id
        user_data = user_doc.to_dict()

        print(
            f"\nChecking user: {user_id} ({user_data.get('profile', {}).get('email', 'No email')})"
        )

        # Check if preferences/notifications exists
        pref_ref = (
            users_ref.document(user_id)
            .collection("preferences")
            .document("notifications")
        )
        pref_doc = pref_ref.get()

        if not pref_doc.exists:
            print("  ❌ Missing preferences/notifications - Creating...")

            # Create default notification preferences
            default_preferences = {
                "categories": [
                    "Data Quality Alert",
                    "News & Press",
                    "Industry News",
                    "Competitor Activities",
                    "Scheduled Report Status",
                    "KPI Performance",
                    "New Features",
                ],
                "channels": ["ui"],
                "updated_at": datetime.now(),
            }

            pref_ref.set(default_preferences)
            fixed_count += 1
            print("  ✅ Created preferences/notifications")
        else:
            print("  ✅ Already has preferences/notifications")

        # Note: notification_status collection is created dynamically when notifications are sent
        # So we don't need to pre-create it

    print(f"\n{'=' * 50}")
    print(f"Total users processed: {total_count}")
    print(f"Users fixed: {fixed_count}")
    print(f"Users already correct: {total_count - fixed_count}")


def main():
    """Main function."""
    print("Fixing user notification collections...")
    print("=" * 50)

    try:
        fix_user_notification_collections()
        print("\n✅ Script completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
