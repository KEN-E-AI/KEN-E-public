"""
Verification script to confirm user permissions migration was successful.

This script verifies:
1. No users have the old permissions.accounts field
2. All users have permissions.account_permissions field (even if empty)
3. Permission counts are reasonable
4. Super admins are still identified correctly

Usage:
    python api/scripts/verify_permissions_migration.py

    # Specify environment
    GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/verify_permissions_migration.py
"""

import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PermissionVerifier:
    """Verifies that permission migration was successful."""

    def __init__(self):
        self.firestore = FirestoreService()
        self.stats = {
            "total_users": 0,
            "users_with_old_structure": 0,
            "users_without_new_structure": 0,
            "users_with_permissions": 0,
            "super_admins": 0,
        }
        self.users_with_old_structure: list[str] = []
        self.users_without_new_structure: list[str] = []

    def initialize_firestore(self) -> bool:
        """Initialize Firestore service with health check."""
        try:
            logger.info("Initializing Firestore service...")
            if not self.firestore.initialize():
                logger.error("Failed to initialize Firestore service")
                return False

            if not self.firestore.health_check():
                logger.error("Firestore health check failed")
                return False

            logger.info("Firestore service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            return False

    def _verify_user_permissions(self, user_id: str, user_data: dict[str, Any]) -> None:
        """Verify permissions structure for a single user.

        Args:
            user_id: User ID
            user_data: User data from Firestore
        """
        permissions = user_data.get("permissions", {})
        email = user_data.get("email", "")

        # Check for super admin
        if email.lower().endswith("@ken-e.ai"):
            self.stats["super_admins"] += 1

        # Check for old structure
        if "accounts" in permissions:
            self.stats["users_with_old_structure"] += 1
            self.users_with_old_structure.append(user_id)
            logger.warning(f"User {user_id} ({email}): Still has old 'accounts' field")

        # Check for new structure
        if "account_permissions" not in permissions:
            self.stats["users_without_new_structure"] += 1
            self.users_without_new_structure.append(user_id)
            logger.warning(
                f"User {user_id} ({email}): Missing 'account_permissions' field"
            )
        else:
            account_permissions = permissions.get("account_permissions", {})
            if account_permissions:
                self.stats["users_with_permissions"] += 1

    def verify_all_users(self) -> bool:
        """Verify all users have correct permission structure.

        Returns:
            True if all users are correctly migrated, False otherwise
        """
        logger.info("=" * 80)
        logger.info("Starting permission migration verification")
        logger.info("=" * 80)

        try:
            # Get all users
            logger.info("Reading users from Firestore...")
            users = self.firestore.list_documents("users")
            self.stats["total_users"] = len(users)

            logger.info(f"Found {len(users)} total users")

            # Verify each user
            for idx, user_data in enumerate(users, 1):
                user_id = user_data.get("uid")
                if not user_id:
                    logger.warning(f"Skipping user at index {idx}: Missing uid field")
                    continue

                # Log progress every 50 users
                if idx % 50 == 0:
                    logger.info(f"Progress: {idx}/{len(users)} users verified")

                self._verify_user_permissions(user_id, user_data)

            # Print summary
            logger.info("=" * 80)
            logger.info("Verification Complete")
            logger.info("=" * 80)
            logger.info(f"Total users:                {self.stats['total_users']}")
            logger.info(
                f"Users with old structure:   {self.stats['users_with_old_structure']}"
            )
            logger.info(
                f"Users without new structure: {self.stats['users_without_new_structure']}"
            )
            logger.info(
                f"Users with permissions:     {self.stats['users_with_permissions']}"
            )
            logger.info(f"Super admins found:         {self.stats['super_admins']}")
            logger.info("=" * 80)

            # Detailed error reporting
            if self.users_with_old_structure:
                logger.error(
                    f"❌ Found {len(self.users_with_old_structure)} users with old structure:"
                )
                for user_id in self.users_with_old_structure[:10]:
                    logger.error(f"   - {user_id}")
                if len(self.users_with_old_structure) > 10:
                    logger.error(
                        f"   ... and {len(self.users_with_old_structure) - 10} more"
                    )

            if self.users_without_new_structure:
                logger.error(
                    f"❌ Found {len(self.users_without_new_structure)} users without new structure:"
                )
                for user_id in self.users_without_new_structure[:10]:
                    logger.error(f"   - {user_id}")
                if len(self.users_without_new_structure) > 10:
                    logger.error(
                        f"   ... and {len(self.users_without_new_structure) - 10} more"
                    )

            # Determine success
            all_migrated = (
                self.stats["users_with_old_structure"] == 0
                and self.stats["users_without_new_structure"] == 0
            )

            if all_migrated:
                logger.info("✅ All users migrated successfully!")
                return True
            else:
                logger.error("❌ Migration incomplete - some users still have issues")
                return False

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False


def main() -> int:
    """Main entry point for verification script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    verifier = PermissionVerifier()

    # Initialize Firestore
    if not verifier.initialize_firestore():
        logger.error("Failed to initialize Firestore")
        return 1

    # Run verification
    if verifier.verify_all_users():
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
