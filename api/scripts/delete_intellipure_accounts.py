#!/usr/bin/env python
"""
Script to delete Intellipure accounts following the same process as the DELETE /api/v1/accounts/{account_id} endpoint.

This script recreates the cascade deletion process:
1. Delete Google Cloud Storage documents
2. Recursive-delete the Firestore account subtree at accounts/{account_id} (sweeps every Shape B subcollection)
3. Delete all ActivityLog nodes
4. Delete all entities with BELONGS_TO relationship
5. Delete the account node itself

"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService
from src.kene_api.firestore import FirestoreService
from src.kene_api.services.storage_service import StorageService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def delete_account_cascade(
    account_id: str, account_name: str, data_region: str
) -> bool:
    """Delete an account and all its related data following the API endpoint logic."""
    logger.info(f"Starting deletion of account: {account_id} ({account_name})")

    # Initialize services
    db = Neo4jService()
    firestore = FirestoreService()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    storage = StorageService(project_id=project_id)

    await db.connect()

    cleanup_results = {
        "gcs_documents_deleted": 0,
        "firestore_account_deleted": False,
        "cleanup_errors": [],
    }

    try:
        # 1. Delete GCS documents for this account
        logger.info(
            f"Deleting GCS documents for account {account_id} in region {data_region}..."
        )
        try:
            deleted_documents = await storage.delete_account_documents(
                account_id, data_region
            )
            cleanup_results["gcs_documents_deleted"] = 1 if deleted_documents else 0
            logger.info(
                f"  ✅ Deleted GCS documents: {cleanup_results['gcs_documents_deleted']}"
            )
        except Exception as e:
            logger.error(f"  ❌ Failed to delete GCS documents: {e}")
            cleanup_results["cleanup_errors"].append(f"GCS cleanup failed: {e}")

        # 2. Recursive-delete the Firestore account subtree (sweeps every Shape B subcollection)
        logger.info(
            f"Recursive-deleting Firestore account subtree accounts/{account_id}..."
        )
        try:
            firestore_db = firestore.get_client()
            account_doc_ref = firestore_db.collection("accounts").document(account_id)
            # recursive_delete is synchronous (CLI context only, not request path).
            # Returns None; no-ops silently if the doc doesn't exist — treated as success.
            firestore_db.recursive_delete(account_doc_ref)
            cleanup_results["firestore_account_deleted"] = True
            logger.info(
                f"  ✅ Recursive-deleted accounts/{account_id} and all subcollections"
            )
        except Exception as e:
            logger.error(
                f"  ❌ Failed to recursive-delete Firestore account subtree: {e}"
            )
            cleanup_results["cleanup_errors"].append(f"Firestore cleanup failed: {e}")

        # 3. Delete Neo4j entities
        total_nodes_deleted = 0
        total_relationships_deleted = 0

        # First, delete all ActivityLog nodes
        logger.info("Deleting ActivityLog nodes...")
        delete_logs_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)<-[:LOGGED]-(log:ActivityLog)
        DETACH DELETE log
        """
        logs_summary = await db.execute_write_operation(
            delete_logs_query, {"account_id": account_id}
        )
        logs_deleted = logs_summary.get("nodes_deleted", 0)
        total_nodes_deleted += logs_deleted
        total_relationships_deleted += logs_summary.get("relationships_deleted", 0)
        logger.info(f"  ✅ Deleted {logs_deleted} ActivityLog nodes")

        # Then delete all entities with BELONGS_TO relationship
        logger.info("Deleting entities with BELONGS_TO relationship...")
        delete_entities_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(entity)
        DETACH DELETE entity
        """
        entities_summary = await db.execute_write_operation(
            delete_entities_query, {"account_id": account_id}
        )
        entities_deleted = entities_summary.get("nodes_deleted", 0)
        total_nodes_deleted += entities_deleted
        total_relationships_deleted += entities_summary.get("relationships_deleted", 0)
        logger.info(f"  ✅ Deleted {entities_deleted} related entities")

        # Finally delete the account itself
        logger.info("Deleting account node...")
        delete_account_query = """
        MATCH (acc:Account {account_id: $account_id})
        DETACH DELETE acc
        """
        account_summary = await db.execute_write_operation(
            delete_account_query, {"account_id": account_id}
        )
        account_deleted = account_summary.get("nodes_deleted", 0)
        total_nodes_deleted += account_deleted
        total_relationships_deleted += account_summary.get("relationships_deleted", 0)
        logger.info("  ✅ Deleted account node")

        # Summary
        logger.info(f"""
========================================
✅ Successfully deleted account: {account_id} ({account_name})
========================================
  - Neo4j nodes deleted: {total_nodes_deleted}
  - Neo4j relationships deleted: {total_relationships_deleted}
  - GCS documents deleted: {cleanup_results["gcs_documents_deleted"]}
  - Firestore account subtree deleted: {cleanup_results["firestore_account_deleted"]}
  - Errors: {len(cleanup_results["cleanup_errors"])}
""")

        if cleanup_results["cleanup_errors"]:
            logger.warning("Cleanup errors encountered:")
            for error in cleanup_results["cleanup_errors"]:
                logger.warning(f"  - {error}")

        return len(cleanup_results["cleanup_errors"]) == 0

    except Exception as e:
        logger.error(f"Failed to delete account {account_id}: {e}")
        return False
    finally:
        await db.close()


async def main():
    """Main function to delete all Intellipure accounts."""
    logger.info("Starting Intellipure account deletion process...")

    # Initialize Neo4j to find Intellipure accounts
    db = Neo4jService()
    await db.connect()

    try:
        # Find all Intellipure accounts
        query = """
        MATCH (acc:Account)
        WHERE toLower(acc.account_id) CONTAINS 'intellipure' OR
              toLower(acc.account_name) CONTAINS 'intellipure'
        RETURN acc.account_id as account_id,
               acc.account_name as account_name,
               acc.data_region as data_region
        """
        result = await db.execute_query(query, {})

        if not result:
            logger.info("No Intellipure accounts found in the database.")
            return

        logger.info(f"Found {len(result)} Intellipure account(s) to delete:")
        for acc in result:
            logger.info(
                f"  - {acc['account_id']}: {acc['account_name']} (Region: {acc['data_region']})"
            )

        # Ask for confirmation
        print(
            "\n⚠️  WARNING: This will permanently delete the above accounts and all their data!"
        )
        confirmation = input("Type 'DELETE' to confirm: ")

        if confirmation != "DELETE":
            logger.info("Deletion cancelled by user.")
            return

        # Close the initial connection as delete_account_cascade will create its own
        await db.close()

        # Delete each account
        success_count = 0
        for acc in result:
            success = await delete_account_cascade(
                acc["account_id"], acc["account_name"], acc["data_region"] or "US"
            )
            if success:
                success_count += 1

        logger.info(f"""
========================================
FINAL SUMMARY
========================================
Total accounts processed: {len(result)}
Successfully deleted: {success_count}
Failed: {len(result) - success_count}
========================================
""")

    except Exception as e:
        logger.error(f"Error in main process: {e}")
        await db.close()
        raise


if __name__ == "__main__":
    asyncio.run(main())
