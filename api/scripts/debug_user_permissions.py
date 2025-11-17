"""Debug script to inspect user permissions.

Usage:
    python api/scripts/debug_user_permissions.py <user_id>
    python api/scripts/debug_user_permissions.py test-user-123
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

# Get user_id from command line args
if len(sys.argv) < 2:
    print("Usage: python api/scripts/debug_user_permissions.py <user_id>")
    sys.exit(1)

user_id = sys.argv[1]

# Initialize Firestore
fs = FirestoreService()
fs.initialize()
client = fs.get_client()

# Fetch user document
user_doc = client.collection("users").document(user_id).get()

if user_doc.exists:
    user_data = user_doc.to_dict()
    print(f"User ID: {user_id}")
    print(f"Email: {user_data.get('email', 'N/A')}")
    print(f"\nPermissions structure:")
    print(json.dumps(user_data.get("permissions", {}), indent=2))
    print(f"\nFull user data keys: {list(user_data.keys())}")
else:
    print(f"User {user_id} not found")
