#!/usr/bin/env python3
"""
Script to clean up orphaned organizations from Firestore permissions.

This script:
1. Connects to Neo4j and Firestore
2. Gets all valid organization IDs from Neo4j
3. Scans all users in Firestore for organization permissions
4. Removes permissions for organizations that don't exist in Neo4j
5. Optionally clears browser storage via a flag

Usage:
    python scripts/cleanup_orphaned_organizations.py [--dry-run]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import API modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService
from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def get_all_organizations_from_neo4j(db: Neo4jService) -> set[str]:
    """Get all organization IDs from Neo4j."""
    query = """
    MATCH (org:Organization)
    RETURN org.organization_id as org_id
    """

    try:
        result = await db.execute_query(query)
        org_ids = {record["org_id"] for record in result if record.get("org_id")}
        logger.info(f"Found {len(org_ids)} organizations in Neo4j")
        return org_ids
    except Exception as e:
        logger.error(f"Failed to get organizations from Neo4j: {e}")
        raise


def cleanup_orphaned_organizations_from_firestore(
    firestore_service: FirestoreService, valid_org_ids: set[str], dry_run: bool = True
) -> dict:
    """
    Remove orphaned organization permissions from all users in Firestore.

    Returns:
        dict: Statistics about the cleanup operation
    """
    stats = {
        "users_scanned": 0,
        "users_with_orphaned_orgs": 0,
        "orphaned_orgs_found": set(),
        "permissions_removed": 0,
        "errors": [],
    }

    try:
        firestore_client = firestore_service.get_client()
        users_collection = firestore_client.collection("users")

        # Scan all users
        for user_doc in users_collection.stream():
            stats["users_scanned"] += 1
            user_id = user_doc.id
            user_data = user_doc.to_dict()

            permissions = user_data.get("permissions", {})
            org_permissions = permissions.get("organizations", {})

            if not org_permissions:
                continue

            # Find orphaned organizations
            orphaned_orgs = set(org_permissions.keys()) - valid_org_ids

            if orphaned_orgs:
                stats["users_with_orphaned_orgs"] += 1
                stats["orphaned_orgs_found"].update(orphaned_orgs)

                logger.info(
                    f"User {user_id} has permissions for orphaned organizations: {orphaned_orgs}"
                )

                if not dry_run:
                    # Remove orphaned organizations
                    updated_permissions = {
                        org_id: role
                        for org_id, role in org_permissions.items()
                        if org_id in valid_org_ids
                    }

                    try:
                        user_doc.reference.update(
                            {"permissions.organizations": updated_permissions}
                        )
                        stats["permissions_removed"] += len(orphaned_orgs)
                        logger.info(
                            f"Removed {len(orphaned_orgs)} orphaned organization permissions from user {user_id}"
                        )
                    except Exception as e:
                        error_msg = f"Failed to update user {user_id}: {e}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

    except Exception as e:
        logger.error(f"Error during Firestore cleanup: {e}")
        raise

    return stats


async def main(dry_run: bool = True):
    """Main cleanup function."""
    logger.info(f"Starting orphaned organization cleanup (dry_run={dry_run})")

    # Initialize services
    neo4j_service = Neo4jService()
    await neo4j_service.connect()

    firestore_service = FirestoreService()

    try:
        # Check Neo4j connectivity
        is_healthy = await neo4j_service.health_check()
        if not is_healthy:
            logger.error("Neo4j is not healthy")
            return

        # Get all valid organizations from Neo4j
        valid_org_ids = await get_all_organizations_from_neo4j(neo4j_service)

        # Clean up Firestore
        stats = cleanup_orphaned_organizations_from_firestore(
            firestore_service, valid_org_ids, dry_run=dry_run
        )

        # Print summary
        logger.info("\n=== Cleanup Summary ===")
        logger.info(f"Users scanned: {stats['users_scanned']}")
        logger.info(
            f"Users with orphaned organizations: {stats['users_with_orphaned_orgs']}"
        )
        logger.info(
            f"Unique orphaned organizations found: {len(stats['orphaned_orgs_found'])}"
        )

        if stats["orphaned_orgs_found"]:
            logger.info(
                f"Orphaned organization IDs: {sorted(stats['orphaned_orgs_found'])}"
            )

        if not dry_run:
            logger.info(f"Permissions removed: {stats['permissions_removed']}")
            if stats["errors"]:
                logger.error(f"Errors encountered: {len(stats['errors'])}")
                for error in stats["errors"]:
                    logger.error(f"  - {error}")
        else:
            logger.info("\nThis was a DRY RUN. No changes were made.")
            logger.info("To perform the cleanup, run with --no-dry-run flag")

    finally:
        # Close Neo4j connection
        await neo4j_service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean up orphaned organizations from Firestore permissions"
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually perform the cleanup (default is dry-run mode)",
    )

    args = parser.parse_args()

    # Run the cleanup
    asyncio.run(main(dry_run=not args.no_dry_run))
