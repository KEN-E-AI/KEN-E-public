"""
Migration script to move organization data from frontend to Neo4j.

This script reads the organization data from the frontend TypeScript file
and creates corresponding nodes in Neo4j with proper relationships.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService
from src.kene_api.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Organization data copied from frontend/src/data/organizationData.ts
ORGANIZATION_DATA = [
    {
        "organization_id": "healthway",
        "organization_name": "Healthway",
        "plan": "Professional",
        "website": "https://healthway.com",
        "company_size": "medium",
        "agency": False,
        "child_organizations": [],
        "accounts": [
            {
                "account_id": "intellipure-b2c",
                "account_name": "Intellipure (B2C)",
                "organization_id": "healthway",
                "industry": "Retail",
                "status": "Active",
                "websites": ["https://intellipure.com", "https://shop.intellipure.com"],
                "timezone": "America/Los_Angeles",
            },
            {
                "account_id": "intellipure-b2b",
                "account_name": "Intellipure (B2B)",
                "organization_id": "healthway",
                "industry": "Retail",
                "status": "Active",
                "websites": ["https://b2b.intellipure.com"],
                "timezone": "America/Los_Angeles",
            },
        ],
        "subscription": {
            "plan_name": "Professional Plan",
            "plan_description": "Advanced analytics and reporting for growing teams",
            "price": 99,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "February 15, 2024",
            "features": ["Unlimited Reports", "Advanced Analytics", "API Access"],
            "usage": {
                "reports_generated": 847,
                "reports_limit": 1000,
            },
        },
        "billing": {
            "payment_method": {
                "last_four": "4242",
                "brand": "Visa",
                "expires": "12/26",
            },
            "address": "123 Business St, San Francisco, CA 94105",
            "tax_id": "US123456789",
        },
        "team": {
            "members_used": 5,
            "members_limit": 10,
            "pending_invitations": 2,
        },
    },
    {
        "organization_id": "open-lines",
        "organization_name": "Open Lines",
        "plan": "Enterprise",
        "website": "https://open-lines.com",
        "company_size": "large",
        "agency": True,
        "child_organizations": ["healthway", "equity-trust"],
        "accounts": [
            {
                "account_id": "master-open-lines",
                "account_name": "Master Open Lines Account",
                "organization_id": "open-lines",
                "industry": "Healthcare Services",
                "status": "Active",
                "websites": [
                    "https://openlines.com",
                    "https://portal.openlines.com",
                    "https://support.openlines.com",
                ],
                "timezone": "America/New_York",
            },
        ],
        "subscription": {
            "plan_name": "Enterprise Plan",
            "plan_description": "Full-featured solution for large organizations",
            "price": 299,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "March 1, 2024",
            "features": [
                "Unlimited Everything",
                "Premium Support",
                "Custom Integrations",
            ],
            "usage": {
                "reports_generated": 2156,
                "reports_limit": 5000,
            },
        },
        "billing": {
            "payment_method": {
                "last_four": "8888",
                "brand": "Mastercard",
                "expires": "08/27",
            },
            "address": "456 Healthcare Ave, Boston, MA 02101",
            "tax_id": "US987654321",
        },
        "team": {
            "members_used": 25,
            "members_limit": 50,
            "pending_invitations": 3,
        },
    },
    {
        "organization_id": "equity-trust",
        "organization_name": "Equity Trust",
        "plan": "Starter",
        "website": "https://equity-trust.com",
        "company_size": "small",
        "agency": False,
        "child_organizations": [],
        "accounts": [
            {
                "account_id": "etc-consumer",
                "account_name": "ETC Consumer",
                "organization_id": "equity-trust",
                "industry": "Financial Services",
                "status": "Active",
                "websites": ["https://equitytrust.com"],
                "timezone": "America/Chicago",
            },
            {
                "account_id": "etc-business",
                "account_name": "ETC Business",
                "organization_id": "equity-trust",
                "industry": "Financial Services",
                "status": "Active",
                "websites": [
                    "https://business.equitytrust.com",
                    "https://portal.equitytrust.com",
                ],
                "timezone": "America/Chicago",
            },
        ],
        "subscription": {
            "plan_name": "Starter Plan",
            "plan_description": "Essential features for small teams getting started",
            "price": 29,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "February 20, 2024",
            "features": ["Basic Reports", "Standard Analytics", "Email Support"],
            "usage": {
                "reports_generated": 45,
                "reports_limit": 100,
            },
        },
        "billing": {
            "payment_method": {
                "last_four": "1234",
                "brand": "American Express",
                "expires": "06/25",
            },
            "address": "789 Finance Blvd, New York, NY 10001",
            "tax_id": "US555666777",
        },
        "team": {
            "members_used": 3,
            "members_limit": 5,
            "pending_invitations": 1,
        },
    },
]


async def clear_existing_data(db: Neo4jService):
    """Clear existing organization and account data."""
    logger.info("Clearing existing organization and account data...")

    # Delete all accounts and their relationships
    delete_accounts_query = """
    MATCH (a:Account)
    DETACH DELETE a
    """
    await db.execute_write_query(delete_accounts_query)

    # Delete all organizations and their relationships
    delete_orgs_query = """
    MATCH (o:Organization)
    DETACH DELETE o
    """
    await db.execute_write_query(delete_orgs_query)

    logger.info("Existing data cleared")


async def create_organization(db: Neo4jService, org_data: dict):
    """Create an organization node in Neo4j."""
    logger.info(f"Creating organization: {org_data['organization_name']}")

    # Extract accounts before creating org
    accounts = org_data.pop("accounts", [])

    # Create organization node
    create_org_query = """
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
        team: $team
    })
    RETURN org
    """

    params = {
        "organization_id": org_data["organization_id"],
        "organization_name": org_data["organization_name"],
        "plan": org_data["plan"],
        "website": org_data["website"],
        "company_size": org_data["company_size"],
        "agency": org_data["agency"],
        "child_organizations": org_data["child_organizations"],
        "subscription": json.dumps(org_data["subscription"]),
        "billing": json.dumps(org_data["billing"]),
        "team": json.dumps(org_data["team"]),
    }

    await db.execute_write_query(create_org_query, params)
    logger.info(f"Created organization: {org_data['organization_name']}")

    # Create accounts for this organization
    for account_data in accounts:
        await create_account(db, account_data)


async def create_account(db: Neo4jService, account_data: dict):
    """Create an account node and its BELONGS_TO relationship."""
    logger.info(f"Creating account: {account_data['account_name']}")

    create_account_query = """
    MATCH (org:Organization {organization_id: $organization_id})
    CREATE (acc:Account {
        account_id: $account_id,
        account_name: $account_name,
        organization_id: $organization_id,
        industry: $industry,
        status: $status,
        websites: $websites,
        timezone: $timezone
    })
    CREATE (acc)-[:BELONGS_TO]->(org)
    RETURN acc
    """

    params = {
        "account_id": account_data["account_id"],
        "account_name": account_data["account_name"],
        "organization_id": account_data["organization_id"],
        "industry": account_data["industry"],
        "status": account_data["status"],
        "websites": account_data["websites"],
        "timezone": account_data["timezone"],
    }

    await db.execute_write_query(create_account_query, params)
    logger.info(f"Created account: {account_data['account_name']}")


async def create_parent_relationships(db: Neo4jService):
    """Create PARENT_OF relationships between organizations."""
    logger.info("Creating parent-child relationships between organizations...")

    # For each organization with child_organizations
    for org_data in ORGANIZATION_DATA:
        if org_data["agency"] and org_data["child_organizations"]:
            parent_id = org_data["organization_id"]

            for child_id in org_data["child_organizations"]:
                create_relationship_query = """
                MATCH (parent:Organization {organization_id: $parent_id})
                MATCH (child:Organization {organization_id: $child_id})
                CREATE (parent)-[:PARENT_OF]->(child)
                """

                params = {
                    "parent_id": parent_id,
                    "child_id": child_id,
                }

                await db.execute_write_query(create_relationship_query, params)
                logger.info(
                    f"Created PARENT_OF relationship: {parent_id} -> {child_id}"
                )


async def verify_migration(db: Neo4jService):
    """Verify the migration was successful."""
    logger.info("Verifying migration...")

    # Count organizations
    org_count_query = "MATCH (o:Organization) RETURN count(o) as count"
    org_result = await db.execute_query(org_count_query)
    org_count = org_result[0]["count"] if org_result else 0
    logger.info(f"Organizations created: {org_count}")

    # Count accounts
    acc_count_query = "MATCH (a:Account) RETURN count(a) as count"
    acc_result = await db.execute_query(acc_count_query)
    acc_count = acc_result[0]["count"] if acc_result else 0
    logger.info(f"Accounts created: {acc_count}")

    # Count relationships
    rel_count_query = "MATCH ()-[r:BELONGS_TO|PARENT_OF]->() RETURN count(r) as count"
    rel_result = await db.execute_query(rel_count_query)
    rel_count = rel_result[0]["count"] if rel_result else 0
    logger.info(f"Relationships created: {rel_count}")

    # List all organizations with their accounts
    list_query = """
    MATCH (org:Organization)
    OPTIONAL MATCH (org)<-[:BELONGS_TO]-(acc:Account)
    RETURN org.organization_name as org_name, collect(acc.account_name) as accounts
    ORDER BY org_name
    """
    list_result = await db.execute_query(list_query)

    logger.info("\nOrganizations and their accounts:")
    for record in list_result:
        logger.info(
            f"  {record['org_name']}: {', '.join(record['accounts']) if record['accounts'][0] else 'No accounts'}"
        )


async def main():
    """Main migration function."""
    logger.info("Starting organization data migration to Neo4j...")

    # Initialize Neo4j service
    db = Neo4jService()

    try:
        # Connect to Neo4j
        await db.connect()
        logger.info("Connected to Neo4j")

        # Clear existing data (optional - comment out if you want to preserve existing data)
        await clear_existing_data(db)

        # Create organizations and accounts
        for org_data in ORGANIZATION_DATA:
            await create_organization(
                db, org_data.copy()
            )  # Use copy to avoid modifying original

        # Create parent-child relationships
        await create_parent_relationships(db)

        # Verify migration
        await verify_migration(db)

        logger.info("Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        # Close connection
        await db.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    asyncio.run(main())
