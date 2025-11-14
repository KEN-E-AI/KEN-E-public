"""Debug script to inspect user permissions."""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

fs = FirestoreService()
fs.initialize()
client = fs.get_client()

user_id = "test-user-123"
user_doc = client.collection("users").document(user_id).get()

if user_doc.exists:
    user_data = user_doc.to_dict()
    print(f"User: {user_id}")
    print(f"Email: {user_data.get('email', 'N/A')}")
    print(f"\nPermissions structure:")
    print(json.dumps(user_data.get("permissions", {}), indent=2))
else:
    print(f"User {user_id} not found")
