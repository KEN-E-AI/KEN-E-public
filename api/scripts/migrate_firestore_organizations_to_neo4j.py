"""
Migration script to sync organization data from Firestore to Neo4j.

This script:
1. Reads all organizations from Firestore
2. Creates corresponding nodes in Neo4j with all their data
3. Preserves all organization properties and relationships
4. Handles organizations that might already exist in Neo4j
5. Logs progress and any issues encountered
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService
from src.kene_api.firestore import FirestoreService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class FirestoreToNeo4jMigrator:
    """Handles migration of organizations from Firestore to Neo4j."""

    def __init__(self):
        self.firestore = FirestoreService()
        self.neo4j = Neo4jService()
        self.stats = {
            "organizations_read": 0,
            "organizations_created": 0,
            "organizations_updated": 0,
            "organizations_skipped": 0,
            "errors": [],
        }

    async def initialize_services(self) -> bool:
        """Initialize both Firestore and Neo4j services."""
        try:
            # Initialize Firestore
            logger.info("Initializing Firestore service...")
            if not self.firestore.initialize():
                logger.error("Failed to initialize Firestore service")
                return False

            # Test Firestore connection
            if not self.firestore.health_check():
                logger.error("Firestore health check failed")
                return False

            logger.info("Firestore service initialized successfully")

            # Initialize Neo4j
            logger.info("Initializing Neo4j service...")
            await self.neo4j.connect()

            # Test Neo4j connection
            if not await self.neo4j.health_check():
                logger.error("Neo4j health check failed")
                return False

            logger.info("Neo4j service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            return False

    async def read_organizations_from_firestore(self) -> list[dict[str, Any]]:
        """Read all organizations from Firestore."""
        logger.info("Reading organizations from Firestore...")

        try:
            # List all documents in the organizations collection
            organizations = self.firestore.list_documents("organizations")
            self.stats["organizations_read"] = len(organizations)

            logger.info(f"Found {len(organizations)} organizations in Firestore")

            # Process each organization
            processed_orgs = []
            for org in organizations:
                try:
                    # Ensure we have the organization_id
                    if "id" in org and not org.get("organization_id"):
                        org["organization_id"] = org["id"]

                    processed_orgs.append(org)
                    logger.debug(
                        f"Read organization: {org.get('organization_name', 'Unknown')} ({org.get('organization_id', 'No ID')})"
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing organization {org.get('id', 'Unknown')}: {e}"
                    )
                    self.stats["errors"].append(
                        {
                            "organization_id": org.get("id", "Unknown"),
                            "error": str(e),
                            "phase": "read",
                        }
                    )

            return processed_orgs

        except Exception as e:
            logger.error(f"Failed to read organizations from Firestore: {e}")
            raise

    async def check_organization_exists_in_neo4j(self, organization_id: str) -> bool:
        """Check if an organization already exists in Neo4j."""
        query = """
        MATCH (org:Organization {organization_id: $organization_id})
        RETURN count(org) > 0 as exists
        """
        result = await self.neo4j.execute_query(
            query, {"organization_id": organization_id}
        )
        return result[0]["exists"] if result else False

    async def create_organization_in_neo4j(self, org_data: dict[str, Any]) -> bool:
        """Create a new organization in Neo4j."""
        try:
            # Prepare data for Neo4j
            organization_id = org_data.get("organization_id")
            if not organization_id:
                logger.error(f"Organization missing organization_id: {org_data}")
                return False

            # Convert nested objects to JSON strings for storage
            subscription = org_data.get("subscription", {})
            billing = org_data.get("billing", {})
            team = org_data.get("team", {})

            # Create the organization node
            create_query = """
            CREATE (org:Organization {
                organization_id: $organization_id,
                organization_name: $organization_name,
                plan: $plan,
                website: $website,
                company_size: $company_size,
                agency: $agency,
                child_organizations: $child_organizations,
                subscription: $subscription,
                billing: $billing,
                team: $team,
                created_from_firestore: true,
                migration_timestamp: datetime()
            })
            RETURN org
            """

            params = {
                "organization_id": organization_id,
                "organization_name": org_data.get("organization_name", ""),
                "plan": org_data.get("plan", ""),
                "website": org_data.get("website", ""),
                "company_size": org_data.get("company_size", ""),
                "agency": org_data.get("agency", False),
                "child_organizations": org_data.get("child_organizations", []),
                "subscription": json.dumps(subscription)
                if isinstance(subscription, dict)
                else subscription,
                "billing": json.dumps(billing)
                if isinstance(billing, dict)
                else billing,
                "team": json.dumps(team) if isinstance(team, dict) else team,
            }

            await self.neo4j.execute_write_query(create_query, params)
            logger.info(
                f"Created organization in Neo4j: {org_data.get('organization_name')} ({organization_id})"
            )
            self.stats["organizations_created"] += 1
            return True

        except Exception as e:
            logger.error(
                f"Failed to create organization {org_data.get('organization_id', 'Unknown')}: {e}"
            )
            self.stats["errors"].append(
                {
                    "organization_id": org_data.get("organization_id", "Unknown"),
                    "error": str(e),
                    "phase": "create",
                }
            )
            return False

    async def update_organization_in_neo4j(self, org_data: dict[str, Any]) -> bool:
        """Update an existing organization in Neo4j."""
        try:
            organization_id = org_data.get("organization_id")
            if not organization_id:
                logger.error(f"Organization missing organization_id: {org_data}")
                return False

            # Convert nested objects to JSON strings for storage
            subscription = org_data.get("subscription", {})
            billing = org_data.get("billing", {})
            team = org_data.get("team", {})

            # Update the organization node
            update_query = """
            MATCH (org:Organization {organization_id: $organization_id})
            SET org.organization_name = $organization_name,
                org.plan = $plan,
                org.website = $website,
                org.company_size = $company_size,
                org.agency = $agency,
                org.child_organizations = $child_organizations,
                org.subscription = $subscription,
                org.billing = $billing,
                org.team = $team,
                org.updated_from_firestore = true,
                org.last_migration_timestamp = datetime()
            RETURN org
            """

            params = {
                "organization_id": organization_id,
                "organization_name": org_data.get("organization_name", ""),
                "plan": org_data.get("plan", ""),
                "website": org_data.get("website", ""),
                "company_size": org_data.get("company_size", ""),
                "agency": org_data.get("agency", False),
                "child_organizations": org_data.get("child_organizations", []),
                "subscription": json.dumps(subscription)
                if isinstance(subscription, dict)
                else subscription,
                "billing": json.dumps(billing)
                if isinstance(billing, dict)
                else billing,
                "team": json.dumps(team) if isinstance(team, dict) else team,
            }

            result = await self.neo4j.execute_write_query(update_query, params)

            if result.get("properties_set", 0) > 0:
                logger.info(
                    f"Updated organization in Neo4j: {org_data.get('organization_name')} ({organization_id})"
                )
                self.stats["organizations_updated"] += 1
                return True
            else:
                logger.warning(f"No changes made to organization: {organization_id}")
                return False

        except Exception as e:
            logger.error(
                f"Failed to update organization {org_data.get('organization_id', 'Unknown')}: {e}"
            )
            self.stats["errors"].append(
                {
                    "organization_id": org_data.get("organization_id", "Unknown"),
                    "error": str(e),
                    "phase": "update",
                }
            )
            return False

    async def create_parent_relationships(self) -> None:
        """Create PARENT_OF relationships based on child_organizations arrays."""
        logger.info("Creating parent-child relationships...")

        try:
            # Get all organizations with child_organizations
            query = """
            MATCH (parent:Organization)
            WHERE size(parent.child_organizations) > 0
            RETURN parent.organization_id as parent_id, parent.child_organizations as children
            """

            results = await self.neo4j.execute_query(query)

            for record in results:
                parent_id = record["parent_id"]
                children = record["children"]

                for child_id in children:
                    try:
                        # Create relationship if both organizations exist
                        rel_query = """
                        MATCH (parent:Organization {organization_id: $parent_id})
                        MATCH (child:Organization {organization_id: $child_id})
                        MERGE (parent)-[r:PARENT_OF]->(child)
                        RETURN r
                        """

                        await self.neo4j.execute_write_query(
                            rel_query, {"parent_id": parent_id, "child_id": child_id}
                        )
                        logger.debug(
                            f"Created PARENT_OF relationship: {parent_id} -> {child_id}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to create relationship {parent_id} -> {child_id}: {e}"
                        )
                        self.stats["errors"].append(
                            {
                                "parent_id": parent_id,
                                "child_id": child_id,
                                "error": str(e),
                                "phase": "relationship",
                            }
                        )

            logger.info("Completed creating parent-child relationships")

        except Exception as e:
            logger.error(f"Failed to create parent relationships: {e}")

    async def migrate_organization(self, org_data: dict[str, Any]) -> None:
        """Migrate a single organization to Neo4j."""
        organization_id = org_data.get("organization_id", org_data.get("id"))
        organization_name = org_data.get("organization_name", "Unknown")

        try:
            # Check if organization already exists
            exists = await self.check_organization_exists_in_neo4j(organization_id)

            if exists:
                # Update existing organization
                logger.info(
                    f"Organization already exists, updating: {organization_name} ({organization_id})"
                )
                await self.update_organization_in_neo4j(org_data)
            else:
                # Create new organization
                logger.info(
                    f"Creating new organization: {organization_name} ({organization_id})"
                )
                await self.create_organization_in_neo4j(org_data)

        except Exception as e:
            logger.error(f"Failed to migrate organization {organization_id}: {e}")
            self.stats["errors"].append(
                {
                    "organization_id": organization_id,
                    "error": str(e),
                    "phase": "migrate",
                }
            )

    async def verify_migration(self) -> None:
        """Verify the migration results."""
        logger.info("Verifying migration results...")

        try:
            # Count total organizations in Neo4j
            count_query = """
            MATCH (org:Organization)
            RETURN count(org) as total,
                   count(CASE WHEN org.created_from_firestore THEN 1 END) as created_from_firestore,
                   count(CASE WHEN org.updated_from_firestore THEN 1 END) as updated_from_firestore
            """

            result = await self.neo4j.execute_query(count_query)
            if result:
                counts = result[0]
                logger.info(f"Total organizations in Neo4j: {counts['total']}")
                logger.info(
                    f"Created from Firestore: {counts['created_from_firestore']}"
                )
                logger.info(
                    f"Updated from Firestore: {counts['updated_from_firestore']}"
                )

            # List organizations with their details
            list_query = """
            MATCH (org:Organization)
            OPTIONAL MATCH (org)-[:PARENT_OF]->(child:Organization)
            RETURN org.organization_id as id,
                   org.organization_name as name,
                   org.plan as plan,
                   org.agency as agency,
                   collect(child.organization_id) as children
            ORDER BY org.organization_name
            """

            organizations = await self.neo4j.execute_query(list_query)

            logger.info("\nOrganizations in Neo4j:")
            for org in organizations:
                children = [c for c in org["children"] if c is not None]
                children_str = f" (children: {', '.join(children)})" if children else ""
                agency_str = " [AGENCY]" if org["agency"] else ""
                logger.info(
                    f"  - {org['name']} ({org['id']}) - Plan: {org['plan']}{agency_str}{children_str}"
                )

        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")

    async def run_migration(self) -> None:
        """Run the complete migration process."""
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("Starting Firestore to Neo4j organization migration")
        logger.info("=" * 60)

        try:
            # Initialize services
            if not await self.initialize_services():
                logger.error("Failed to initialize services, aborting migration")
                return

            # Read organizations from Firestore
            organizations = await self.read_organizations_from_firestore()

            if not organizations:
                logger.warning("No organizations found in Firestore")
                return

            # Migrate each organization
            logger.info(f"Migrating {len(organizations)} organizations...")
            for org in organizations:
                await self.migrate_organization(org)

            # Create parent-child relationships
            await self.create_parent_relationships()

            # Verify migration
            await self.verify_migration()

            # Print summary
            elapsed_time = datetime.now() - start_time
            logger.info("\n" + "=" * 60)
            logger.info("Migration Summary")
            logger.info("=" * 60)
            logger.info(f"Total time: {elapsed_time}")
            logger.info(
                f"Organizations read from Firestore: {self.stats['organizations_read']}"
            )
            logger.info(
                f"Organizations created in Neo4j: {self.stats['organizations_created']}"
            )
            logger.info(
                f"Organizations updated in Neo4j: {self.stats['organizations_updated']}"
            )
            logger.info(f"Organizations skipped: {self.stats['organizations_skipped']}")
            logger.info(f"Errors encountered: {len(self.stats['errors'])}")

            if self.stats["errors"]:
                logger.error("\nErrors:")
                for error in self.stats["errors"]:
                    logger.error(f"  - {error}")

            logger.info("\nMigration completed!")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            # Clean up connections
            await self.neo4j.close()
            logger.info("Closed database connections")


async def main():
    """Main entry point for the migration script."""
    migrator = FirestoreToNeo4jMigrator()
    await migrator.run_migration()


if __name__ == "__main__":
    # Run the migration
    asyncio.run(main())
