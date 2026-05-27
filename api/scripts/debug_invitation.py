"""Debug script to inspect invitation and user data.

Usage:
    # By invitation token:
    python api/scripts/debug_invitation.py --token <invitation-token>

    # By user email:
    python api/scripts/debug_invitation.py --email <user-email>

    # By user ID:
    python api/scripts/debug_invitation.py --user-id <user-id>
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

# Load .env file
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from src.kene_api.firestore import FirestoreService


def debug_by_token(token: str, fs: FirestoreService):
    """Debug invitation by token."""
    print("=" * 80)
    print(f"Searching for invitation with token: {token}")
    print("=" * 80)
    print()

    invitations = fs.query_documents(
        collection="invitations", field="invitation_token", operator="==", value=token
    )

    if not invitations:
        print("✗ No invitation found with this token")
        return

    invitation = invitations[0]
    print("✓ Found invitation:")
    print(json.dumps(invitation, indent=2, default=str))
    print()

    # Check if user exists
    email = invitation.get("email")
    if email:
        print(f"Checking if user with email '{email}' exists...")
        users = fs.query_documents(
            collection="users", field="email", operator="==", value=email
        )
        if users:
            user = users[0]
            print(f"✓ User found: {user.get('uid')}")
            print("\nUser permissions:")
            print(json.dumps(user.get("permissions", {}), indent=2))
        else:
            print("✗ User not found (hasn't signed up yet)")


def debug_by_email(email: str, fs: FirestoreService):
    """Debug by user email."""
    print("=" * 80)
    print(f"Searching for user with email: {email}")
    print("=" * 80)
    print()

    users = fs.query_documents(
        collection="users", field="email", operator="==", value=email
    )

    if not users:
        print("✗ No user found with this email")
        print("\nSearching for invitations...")
        invitations = fs.query_documents(
            collection="invitations", field="email", operator="==", value=email
        )
        if invitations:
            print(f"✓ Found {len(invitations)} invitation(s):")
            for inv in invitations:
                print(f"\n  Invitation ID: {inv.get('id')}")
                print(
                    f"  Organization: {inv.get('organization_name')} ({inv.get('organization_id')})"
                )
                print(f"  Access Level: {inv.get('access_level')}")
                print(f"  Status: {inv.get('status')}")
                print(
                    f"  Account Permissions: {inv.get('account_permissions', 'None')}"
                )
        else:
            print("✗ No invitations found either")
        return

    user = users[0]
    user_id = user.get("uid")

    print(f"✓ User found: {user_id}")
    print(f"Email: {user.get('email')}")
    print()
    print("Permissions structure:")
    permissions = user.get("permissions", {})
    print(json.dumps(permissions, indent=2))
    print()

    # Analyze permissions
    print("Analysis:")
    print("-" * 80)

    account_perms = permissions.get("account_permissions", {})
    org_perms = permissions.get("organizations", {})

    print(f"Organization permissions: {len(org_perms)}")
    for org_id, role in org_perms.items():
        print(f"  - {org_id}: {role}")

    print(f"\nExplicit account permissions: {len(account_perms)}")
    for acc_id, role in account_perms.items():
        print(f"  - {acc_id}: {role}")

    # Check for old structure
    if "accounts" in permissions:
        print("\n⚠️  WARNING: User still has old 'permissions.accounts' field!")
        print(f"Old accounts: {permissions['accounts']}")

    print()
    print("Accessible accounts property would return:")
    print(f"  {list(account_perms.keys())}")

    if not account_perms and org_perms:
        print(
            "\n⚠️  ISSUE: User has org permissions but no explicit account permissions"
        )
        print(
            "This means accessible_accounts returns [] even though user has access via org role"
        )


def debug_by_user_id(user_id: str, fs: FirestoreService):
    """Debug by user ID."""
    print("=" * 80)
    print(f"Fetching user: {user_id}")
    print("=" * 80)
    print()

    client = fs.get_client()
    user_doc = client.collection("users").document(user_id).get()

    if not user_doc.exists:
        print(f"✗ User {user_id} not found")
        return

    user_data = user_doc.to_dict()
    print("✓ User found")
    print(f"Email: {user_data.get('email')}")
    print()
    print("Permissions structure:")
    print(json.dumps(user_data.get("permissions", {}), indent=2))


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python api/scripts/debug_invitation.py --token <invitation-token>")
        print("  python api/scripts/debug_invitation.py --email <user-email>")
        print("  python api/scripts/debug_invitation.py --user-id <user-id>")
        sys.exit(1)

    arg_type = sys.argv[1]
    arg_value = sys.argv[2]

    # Initialize Firestore
    print("Initializing Firestore...")
    fs = FirestoreService()
    fs.initialize()
    print("✓ Connected to Firestore")
    print()

    if arg_type == "--token":
        debug_by_token(arg_value, fs)
    elif arg_type == "--email":
        debug_by_email(arg_value, fs)
    elif arg_type == "--user-id":
        debug_by_user_id(arg_value, fs)
    else:
        print(f"Unknown argument: {arg_type}")
        print("Use --token, --email, or --user-id")
        sys.exit(1)


if __name__ == "__main__":
    main()
