"""Cleanup script to remove the old 'permissions.accounts' field from users.

This script removes the deprecated 'accounts' field that may have been created
by account_service.py before it was updated to use the new structure.

Usage:
    # Dry run (show what would be changed)
    python api/scripts/cleanup_old_accounts_field.py --dry-run

    # Clean up specific user
    python api/scripts/cleanup_old_accounts_field.py --user-id <user-id>

    # Clean up all users with old field
    python api/scripts/cleanup_old_accounts_field.py --all
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

# Load .env file
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from google.cloud.firestore_v1 import DELETE_FIELD

from src.kene_api.firestore import FirestoreService


def cleanup_user(user_id: str, fs: FirestoreService, dry_run: bool = False):
    """Clean up old accounts field for a specific user."""
    client = fs.get_client()
    user_doc = client.collection("users").document(user_id).get()

    if not user_doc.exists:
        print(f"✗ User {user_id} not found")
        return False

    user_data = user_doc.to_dict()
    permissions = user_data.get("permissions", {})

    if "accounts" not in permissions:
        print(f"✓ User {user_id} - No old 'accounts' field found, nothing to clean up")
        return False

    old_accounts = permissions.get("accounts", {})
    account_permissions = permissions.get("account_permissions", {})

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning up user {user_id}:")
    print(f"  Email: {user_data.get('email')}")
    print(f"  Old 'accounts' field: {old_accounts}")
    print(f"  New 'account_permissions' field: {account_permissions}")

    if dry_run:
        print(f"  Would delete 'permissions.accounts' field")
        return True

    # Delete the old field
    try:
        client.collection("users").document(user_id).update(
            {"permissions.accounts": DELETE_FIELD}
        )
        print(f"  ✓ Deleted 'permissions.accounts' field")

        # Invalidate cache
        from src.kene_api.auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user_id)
        print(f"  ✓ Invalidated user cache")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def cleanup_all_users(fs: FirestoreService, dry_run: bool = False):
    """Clean up old accounts field for all users."""
    print("=" * 80)
    print(f"Cleaning up old 'accounts' field from all users")
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    print("=" * 80)
    print()

    users = fs.list_documents("users")
    print(f"Found {len(users)} total users")
    print()

    cleaned = 0
    skipped = 0
    errors = 0

    for user_data in users:
        user_id = user_data.get("uid")
        if not user_id:
            skipped += 1
            continue

        permissions = user_data.get("permissions", {})
        if "accounts" not in permissions:
            skipped += 1
            continue

        try:
            if cleanup_user(user_id, fs, dry_run):
                cleaned += 1
        except Exception as e:
            print(f"  ✗ Error processing user {user_id}: {e}")
            errors += 1

    print()
    print("=" * 80)
    print("Cleanup Summary")
    print("=" * 80)
    print(f"Total users: {len(users)}")
    print(f"Cleaned up: {cleaned}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python api/scripts/cleanup_old_accounts_field.py --dry-run")
        print("  python api/scripts/cleanup_old_accounts_field.py --user-id <user-id>")
        print("  python api/scripts/cleanup_old_accounts_field.py --all")
        sys.exit(1)

    arg = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    # Initialize Firestore
    print("Initializing Firestore...")
    fs = FirestoreService()
    fs.initialize()
    print("✓ Connected to Firestore")
    print()

    if arg == "--all" or arg == "--dry-run":
        cleanup_all_users(fs, dry_run=dry_run or arg == "--dry-run")
    elif arg == "--user-id" and len(sys.argv) > 2:
        user_id = sys.argv[2]
        cleanup_user(user_id, fs, dry_run=dry_run)
    else:
        print(f"Unknown argument: {arg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
