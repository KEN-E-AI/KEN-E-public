"""
Rollback script to restore old permission structure.

This script reverses the migration by copying account_permissions back to accounts.
Use this only if issues are found after migration and you need to restore the old structure.

CAUTION: This should only be used in emergency situations. The old structure is deprecated.

Usage:
    # Dry run (no changes made)
    python api/scripts/rollback_permissions_migration.py --dry-run

    # Execute rollback
    python api/scripts/rollback_permissions_migration.py

    # Specify environment
    GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/rollback_permissions_migration.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"rollback_permissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class PermissionRollback:
    """Handles rollback of user permissions from new to old structure."""

    def __init__(self, dry_run: bool = False):
        self.firestore = FirestoreService()
        self.dry_run = dry_run
        self.stats = {
            "total_users": 0,
            "rolled_back": 0,
            "skipped": 0,
            "errors": 0,
        }

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

    def _rollback_user_permissions(
        self, user_id: str, user_data: dict[str, Any]
    ) -> bool:
        """Rollback permissions for a single user.

        Args:
            user_id: User ID
            user_data: User data from Firestore

        Returns:
            True if rollback was needed and successful, False if skipped
        """
        permissions = user_data.get("permissions", {})
        account_permissions = permissions.get("account_permissions", {})

        # Skip if no permissions to rollback
        if not account_permissions:
            logger.debug(f"User {user_id}: No account_permissions to rollback")
            return False

        logger.info(
            f"User {user_id}: Rolling back {len(account_permissions)} permissions "
            "from account_permissions to accounts"
        )

        if self.dry_run:
            logger.info(f"[DRY RUN] Would rollback user {user_id}")
            return True

        # Update Firestore - copy account_permissions to accounts
        try:
            client = self.firestore.get_client()
            client.collection("users").document(user_id).update(
                {
                    "permissions.accounts": account_permissions,
                }
            )
            logger.info(f"✓ Successfully rolled back user {user_id}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to rollback user {user_id}: {e}")
            raise

    async def rollback_all_users(self) -> dict[str, int]:
        """Rollback all users from new to old permission structure.

        Returns:
            Dictionary with rollback statistics
        """
        logger.info("=" * 80)
        logger.info("⚠️  WARNING: Starting user permissions ROLLBACK")
        logger.info("This will restore the OLD deprecated permission structure")
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 80)

        # Confirmation prompt in non-dry-run mode
        if not self.dry_run:
            logger.warning("This operation will restore the old permission structure.")
            logger.warning("Are you sure you want to continue? (yes/no)")
            response = input().strip().lower()
            if response != "yes":
                logger.info("Rollback cancelled by user")
                return self.stats

        try:
            # Get all users
            logger.info("Reading users from Firestore...")
            users = self.firestore.list_documents("users")
            self.stats["total_users"] = len(users)

            logger.info(f"Found {len(users)} total users")

            # Process each user
            for idx, user_data in enumerate(users, 1):
                user_id = user_data.get("uid")
                if not user_id:
                    logger.warning(f"Skipping user at index {idx}: Missing uid field")
                    self.stats["skipped"] += 1
                    continue

                # Log progress every 10 users
                if idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{len(users)} users processed")

                try:
                    if self._rollback_user_permissions(user_id, user_data):
                        self.stats["rolled_back"] += 1
                    else:
                        self.stats["skipped"] += 1

                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(f"Error processing user {user_id}: {e}")

            # Print summary
            logger.info("=" * 80)
            logger.info("Rollback Complete")
            logger.info("=" * 80)
            logger.info(f"Total users:     {self.stats['total_users']}")
            logger.info(f"Rolled back:     {self.stats['rolled_back']}")
            logger.info(f"Skipped:         {self.stats['skipped']}")
            logger.info(f"Errors:          {self.stats['errors']}")
            logger.info("=" * 80)

            return self.stats

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise


async def main() -> int:
    """Main entry point for rollback script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv

    # Initialize rollback
    rollback = PermissionRollback(dry_run=dry_run)

    # Initialize Firestore
    if not rollback.initialize_firestore():
        logger.error("Failed to initialize Firestore")
        return 1

    # Run rollback
    try:
        stats = await rollback.rollback_all_users()

        # Return success if no errors
        if stats["errors"] == 0:
            logger.info("✓ Rollback completed successfully!")
            return 0
        else:
            logger.error(f"✗ Rollback completed with {stats['errors']} errors")
            return 1

    except Exception as e:
        logger.error(f"Rollback failed with exception: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
