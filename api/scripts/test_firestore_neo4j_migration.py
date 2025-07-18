"""
Test script to verify Firestore to Neo4j migration functionality.

This script tests individual components of the migration process.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService
from src.kene_api.firestore import FirestoreService
from src.kene_api.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_firestore_connection():
    """Test Firestore connection and read capabilities."""
    logger.info("Testing Firestore connection...")

    firestore = FirestoreService()

    try:
        # Initialize Firestore
        if not firestore.initialize():
            logger.error("Failed to initialize Firestore")
            return False

        # Test health check
        if not firestore.health_check():
            logger.error("Firestore health check failed")
            return False

        logger.info("Firestore connection successful")

        # Try to list organizations
        orgs = firestore.list_documents("organizations", limit=5)
        logger.info(f"Found {len(orgs)} organizations (limited to 5)")

        for org in orgs:
            logger.info(
                f"  - {org.get('organization_name', 'Unknown')} (ID: {org.get('id', 'No ID')})"
            )

        return True

    except Exception as e:
        logger.error(f"Firestore test failed: {e}")
        return False


async def test_neo4j_connection():
    """Test Neo4j connection and query capabilities."""
    logger.info("Testing Neo4j connection...")

    neo4j = Neo4jService()

    try:
        # Connect to Neo4j
        await neo4j.connect()

        # Test health check
        if not await neo4j.health_check():
            logger.error("Neo4j health check failed")
            return False

        logger.info("Neo4j connection successful")

        # Try to count organizations
        count_query = "MATCH (org:Organization) RETURN count(org) as count"
        result = await neo4j.execute_query(count_query)
        count = result[0]["count"] if result else 0

        logger.info(f"Current organizations in Neo4j: {count}")

        await neo4j.close()
        return True

    except Exception as e:
        logger.error(f"Neo4j test failed: {e}")
        await neo4j.close()
        return False


async def test_sample_migration():
    """Test migrating a single sample organization."""
    logger.info("Testing sample organization migration...")

    firestore = FirestoreService()
    neo4j = Neo4jService()

    try:
        # Initialize services
        if not firestore.initialize():
            logger.error("Failed to initialize Firestore")
            return False

        await neo4j.connect()

        # Create a test organization in Firestore
        test_org = {
            "organization_name": "Test Migration Org",
            "plan": "Professional",
            "website": "https://test-migration.com",
            "company_size": "medium",
            "agency": False,
            "child_organizations": [],
            "subscription": {
                "plan_name": "Professional Plan",
                "plan_description": "Test subscription",
                "price": 99.0,
                "currency": "USD",
                "billing_cycle": "monthly",
                "next_billing_date": "2024-03-01",
                "features": ["Feature 1", "Feature 2"],
                "usage": {"reports_generated": 10, "reports_limit": 100},
            },
            "billing": {
                "payment_method": {
                    "last_four": "4242",
                    "brand": "Visa",
                    "expires": "12/25",
                },
                "address": "123 Test St",
                "tax_id": "TEST123",
            },
            "team": {"members_used": 2, "members_limit": 10, "pending_invitations": 0},
        }

        # Create in Firestore
        logger.info("Creating test organization in Firestore...")
        test_org_id = firestore.create_document(
            "organizations", "test-migration-org", test_org
        )
        logger.info(f"Created test organization with ID: {test_org_id}")

        # Read it back
        read_org = firestore.get_document("organizations", test_org_id)
        if not read_org:
            logger.error("Failed to read test organization from Firestore")
            return False

        logger.info("Successfully read test organization from Firestore")

        # Migrate to Neo4j
        logger.info("Migrating test organization to Neo4j...")

        # Add organization_id for Neo4j
        read_org["organization_id"] = test_org_id

        # Convert nested objects to JSON strings
        create_query = """
        MERGE (org:Organization {organization_id: $organization_id})
        SET org.organization_name = $organization_name,
            org.plan = $plan,
            org.website = $website,
            org.company_size = $company_size,
            org.agency = $agency,
            org.child_organizations = $child_organizations,
            org.subscription = $subscription,
            org.billing = $billing,
            org.team = $team,
            org.test_migration = true
        RETURN org
        """

        params = {
            "organization_id": test_org_id,
            "organization_name": read_org.get("organization_name", ""),
            "plan": read_org.get("plan", ""),
            "website": read_org.get("website", ""),
            "company_size": read_org.get("company_size", ""),
            "agency": read_org.get("agency", False),
            "child_organizations": read_org.get("child_organizations", []),
            "subscription": json.dumps(read_org.get("subscription", {})),
            "billing": json.dumps(read_org.get("billing", {})),
            "team": json.dumps(read_org.get("team", {})),
        }

        await neo4j.execute_write_query(create_query, params)
        logger.info("Successfully migrated test organization to Neo4j")

        # Verify in Neo4j
        verify_query = """
        MATCH (org:Organization {organization_id: $organization_id})
        RETURN org
        """
        result = await neo4j.execute_query(
            verify_query, {"organization_id": test_org_id}
        )

        if result:
            logger.info("Verified test organization in Neo4j")
            org_data = result[0]["org"]
            logger.info(f"  Name: {org_data.get('organization_name')}")
            logger.info(f"  Plan: {org_data.get('plan')}")
            logger.info(f"  Website: {org_data.get('website')}")
        else:
            logger.error("Failed to verify test organization in Neo4j")
            return False

        # Clean up - delete test organization from both databases
        logger.info("Cleaning up test data...")

        # Delete from Firestore
        firestore.delete_document("organizations", test_org_id)

        # Delete from Neo4j
        delete_query = """
        MATCH (org:Organization {organization_id: $organization_id})
        DELETE org
        """
        await neo4j.execute_write_query(delete_query, {"organization_id": test_org_id})

        logger.info("Test migration completed successfully and cleaned up")

        await neo4j.close()
        return True

    except Exception as e:
        logger.error(f"Sample migration test failed: {e}")
        await neo4j.close()
        return False


async def main():
    """Run all tests."""
    logger.info("Starting migration tests...")

    tests = [
        ("Firestore Connection", test_firestore_connection),
        ("Neo4j Connection", test_neo4j_connection),
        ("Sample Migration", test_sample_migration),
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'=' * 60}")

        try:
            if asyncio.iscoroutinefunction(test_func):
                success = await test_func()
            else:
                success = test_func()

            results.append((test_name, success))

            if success:
                logger.info(f"✓ {test_name} passed")
            else:
                logger.error(f"✗ {test_name} failed")

        except Exception as e:
            logger.error(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info("Test Summary")
    logger.info(f"{'=' * 60}")

    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)

    for test_name, success in results:
        status = "PASSED" if success else "FAILED"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    return passed_tests == total_tests


if __name__ == "__main__":
    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
