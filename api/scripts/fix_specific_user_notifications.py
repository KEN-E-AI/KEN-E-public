#!/usr/bin/env python3
"""
Script to fix notification collections for a specific user.
"""

import os
import sys
from google.cloud import firestore
from datetime import datetime

# Add the parent directory to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fix_user_by_email(email: str):
    """Fix notification collections for a specific user by email."""
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
            
            # Check and fix preferences/notifications
            pref_ref = users_ref.document(user_id).collection("preferences").document("notifications")
            pref_doc = pref_ref.get()
            
            if not pref_doc.exists:
                print(f"\n❌ Missing preferences/notifications - Creating...")
                
                # Create default notification preferences
                default_preferences = {
                    "categories": [
                        "Data Quality Alert",
                        "News & Press", 
                        "Industry News",
                        "Competitor Activities",
                        "Scheduled Report Status",
                        "KPI Performance",
                        "New Features"
                    ],
                    "channels": ["ui"],
                    "updated_at": datetime.now()
                }
                
                pref_ref.set(default_preferences)
                print(f"✅ Created preferences/notifications")
            else:
                print(f"\n✅ User already has preferences/notifications")
                pref_data = pref_doc.to_dict()
                print(f"Current preferences: {pref_data}")
            
            # Check notification_status collection
            status_collection = users_ref.document(user_id).collection("notification_status")
            status_docs = list(status_collection.stream())
            
            print(f"\nNotification status documents: {len(status_docs)}")
            if status_docs:
                print("Recent notification statuses:")
                for i, doc in enumerate(status_docs[:5]):  # Show first 5
                    data = doc.to_dict()
                    print(f"  - {doc.id}: {data.get('status', 'unknown')}")
            
            break
    
    if not user_found:
        print(f"❌ User with email '{email}' not found!")
        return False
    
    return True


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python fix_specific_user_notifications.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    print(f"Fixing notification collections for user: {email}")
    print("="*50)
    
    try:
        if fix_user_by_email(email):
            print("\n✅ User fixed successfully!")
        else:
            print("\n❌ Failed to fix user!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()