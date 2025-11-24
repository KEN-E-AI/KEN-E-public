"""
Migration script to consolidate user permission structures.

This script migrates from the old permission structure to the new canonical format:
  OLD: permissions.accounts -> NEW: permissions.account_permissions

The script:
1. Reads all user documents from Firestore
2. Merges permissions.accounts into permissions.account_permissions (NEW takes precedence)
3. Deletes the permissions.accounts field
4. Logs detailed migration results

Usage:
    # Dry run (no changes made)
    python api/scripts/migrate_user_permissions.py --dry-run

    # Execute migration
    python api/scripts/migrate_user_permissions.py

    # Specify environment
    GOOGLE_CLOUD_PROJECT_ID=ken-e-dev python api/scripts/migrate_user_permissions.py
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from google.cloud.firestore_v1 import DELETE_FIELD

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"migrate_permissions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class PermissionMigrator:
    """Handles migration of user permissions from old to new structure."""

    def __init__(self, dry_run: bool = False):
        self.firestore = FirestoreService()
        self.dry_run = dry_run
        self.stats = {
            "total_users": 0,
            "migrated": 0,
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

    def _migrate_user_permissions(
        self, user_id: str, user_data: dict[str, Any]
    ) -> bool:
        """Migrate permissions for a single user.

        Args:
            user_id: User ID
            user_data: User data from Firestore

        Returns:
            True if migration was needed and successful, False if skipped
        """
        permissions = user_data.get("permissions", {})
        has_old_field = "accounts" in permissions
        has_new_field = "account_permissions" in permissions
        old_accounts = permissions.get("accounts", {})
        new_account_permissions = permissions.get("account_permissions", {})

        # Skip if no migration needed (no old field AND new field exists)
        if not has_old_field and has_new_field:
            logger.debug(f"User {user_id}: Already migrated")
            return False

        # Need to migrate if:
        # 1. Old field exists (even if empty), OR
        # 2. New field is missing
        needs_migration = has_old_field or not has_new_field

        if not needs_migration:
            logger.debug(f"User {user_id}: No migration needed")
            return False

        # Merge: NEW structure takes precedence
        merged_permissions = {**old_accounts, **new_account_permissions}

        logger.info(
            f"User {user_id}: Migrating {len(old_accounts)} old + "
            f"{len(new_account_permissions)} new = {len(merged_permissions)} total permissions"
        )

        if self.dry_run:
            logger.info(f"[DRY RUN] Would migrate user {user_id}")
            return True

        # Update Firestore with cache invalidation to prevent race conditions
        try:
            # Import cache service
            from src.kene_api.auth.cached_user_context import (
                get_cached_user_context_service,
            )

            cached_user_service = get_cached_user_context_service()

            # Invalidate cache BEFORE update to prevent race condition
            # If user authenticates between update and invalidation, they'd get old structure cached
            cached_user_service.invalidate_user_context(user_id)

            client = self.firestore.get_client()
            update_data = {"permissions.account_permissions": merged_permissions}

            # Only delete old field if it exists
            if has_old_field:
                update_data["permissions.accounts"] = DELETE_FIELD

            client.collection("users").document(user_id).update(update_data)

            # Double invalidation for safety - ensures cache is cleared even if
            # it was populated during the brief window of the update
            cached_user_service.invalidate_user_context(user_id)

            # Post-migration validation: verify the structure is correct
            migrated_user_doc = client.collection("users").document(user_id).get()
            if not migrated_user_doc.exists:
                raise ValueError(f"User {user_id} disappeared after migration")

            migrated_data = migrated_user_doc.to_dict()
            new_perms = migrated_data.get("permissions", {})

            # Validation checks
            if "account_permissions" not in new_perms:
                raise ValueError(
                    f"Migration failed: Missing account_permissions field for user {user_id}"
                )

            if has_old_field and "accounts" in new_perms:
                raise ValueError(
                    f"Migration failed: Old accounts field still present for user {user_id}"
                )

            if not isinstance(new_perms["account_permissions"], dict):
                raise ValueError(
                    f"Migration failed: account_permissions is not a dict for user {user_id}"
                )

            # Verify permissions were preserved
            actual_perms = new_perms["account_permissions"]
            if len(actual_perms) != len(merged_permissions):
                logger.warning(
                    f"Permission count mismatch for user {user_id}: "
                    f"expected {len(merged_permissions)}, got {len(actual_perms)}"
                )

            logger.info(
                f"✓ Successfully migrated and validated user {user_id} "
                f"({len(actual_perms)} permissions)"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Failed to migrate user {user_id}: {e}")
            # Re-raise to be caught by outer handler in migrate_all_users()
            # This ensures error is both logged here (with context) AND counted in error stats
            raise

    async def migrate_all_users(self) -> dict[str, int]:
        """Migrate all users from old to new permission structure.

        Returns:
            Dictionary with migration statistics
        """
        logger.info("=" * 80)
        logger.info("Starting user permissions migration")
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 80)

        try:
            # Get all users
            logger.info("Reading users from Firestore...")
            users = self.firestore.list_documents("users")
            self.stats["total_users"] = len(users)

            logger.info(f"Found {len(users)} total users")

            # Track users without UIDs for detailed reporting
            users_without_uid: list[dict[str, Any]] = []

            # Process each user
            for idx, user_data in enumerate(users, 1):
                # Use uid if available, fallback to document id (added by list_documents)
                user_id = user_data.get("uid") or user_data.get("id")
                if not user_id:
                    # Collect detailed info for reporting
                    users_without_uid.append(
                        {
                            "index": idx,
                            "email": user_data.get("email", "N/A"),
                            "keys": list(user_data.keys()),
                        }
                    )
                    logger.warning(
                        f"Skipping user at index {idx}: Missing both uid and id fields. "
                        f"Email: {user_data.get('email', 'N/A')}, "
                        f"Available keys: {list(user_data.keys())}"
                    )
                    self.stats["skipped"] += 1
                    continue

                # Log progress every 10 users
                if idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{len(users)} users processed")

                try:
                    if self._migrate_user_permissions(user_id, user_data):
                        self.stats["migrated"] += 1
                    else:
                        self.stats["skipped"] += 1

                except Exception as e:
                    self.stats["errors"] += 1
                    logger.error(f"Error processing user {user_id}: {e}")

            # Print summary
            logger.info("=" * 80)
            logger.info("Migration Complete")
            logger.info("=" * 80)
            logger.info(f"Total users:     {self.stats['total_users']}")
            logger.info(f"Migrated:        {self.stats['migrated']}")
            logger.info(f"Skipped:         {self.stats['skipped']}")
            logger.info(f"Errors:          {self.stats['errors']}")
            logger.info("=" * 80)

            # Report users without UIDs if any found
            if users_without_uid:
                logger.warning("=" * 80)
                logger.warning(
                    f"⚠️  Found {len(users_without_uid)} users without UID field:"
                )
                for user_info in users_without_uid[:5]:  # Show first 5
                    logger.warning(
                        f"  Index {user_info['index']}: {user_info['email']} "
                        f"(keys: {user_info['keys']})"
                    )
                if len(users_without_uid) > 5:
                    logger.warning(f"  ... and {len(users_without_uid) - 5} more")
                logger.warning(
                    "These users may be incomplete records, test data, or orphaned documents."
                )
                logger.warning(
                    "Consider investigating with: python api/scripts/debug_user_permissions.py <email>"
                )
                logger.warning("=" * 80)

            return self.stats

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


async def main() -> int:
    """Main entry point for migration script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse command line arguments
    dry_run = "--dry-run" in sys.argv

    # Initialize migrator
    migrator = PermissionMigrator(dry_run=dry_run)

    # Initialize Firestore
    if not migrator.initialize_firestore():
        logger.error("Failed to initialize Firestore")
        return 1

    # Run migration
    try:
        stats = await migrator.migrate_all_users()

        # Return success if no errors
        if stats["errors"] == 0:
            logger.info("✓ Migration completed successfully!")
            return 0
        else:
            logger.error(f"✗ Migration completed with {stats['errors']} errors")
            return 1

    except Exception as e:
        logger.error(f"Migration failed with exception: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
