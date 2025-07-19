"""
Neo4j Data Cleanup Script

This script identifies and fixes malformed data in Neo4j that causes 500 errors in the API.
It ensures all required fields have proper non-null values that match the Pydantic model requirements.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path to import API modules
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.database import Neo4jService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Neo4jDataCleanup:
    """Class to handle Neo4j data cleanup operations."""

    def __init__(self):
        self.db = Neo4jService()

    async def connect(self):
        """Connect to Neo4j database."""
        await self.db.connect()
        logger.info("Connected to Neo4j database")

    async def close(self):
        """Close Neo4j connection."""
        await self.db.close()
        logger.info("Closed Neo4j connection")

    async def inspect_organizations(self) -> list[dict[str, Any]]:
        """Inspect organization data and identify issues."""
        query = """
        MATCH (org:Organization)
        RETURN org.organization_id as organization_id,
               org.organization_name as organization_name,
               org.plan as plan,
               org.website as website,
               org.company_size as company_size,
               org.agency as agency,
               org.child_organizations as child_organizations,
               org.subscription as subscription,
               org.billing as billing,
               org.team as team
        """

        result = await self.db.execute_query(query)

        issues = []
        for record in result:
            org_issues = []

            # Check required string fields
            if not record.get("organization_id"):
                org_issues.append("organization_id is null or empty")
            if not record.get("organization_name"):
                org_issues.append("organization_name is null or empty")
            if not record.get("plan"):
                org_issues.append("plan is null or empty")
            if record.get("website") is None:
                org_issues.append("website is null")
            if not record.get("company_size"):
                org_issues.append("company_size is null or empty")

            # Check nested objects
            if not record.get("subscription"):
                org_issues.append("subscription is null or empty")
            if not record.get("billing"):
                org_issues.append("billing is null or empty")
            if not record.get("team"):
                org_issues.append("team is null or empty")

            if org_issues:
                issues.append(
                    {
                        "organization_id": record.get("organization_id"),
                        "issues": org_issues,
                        "data": record,
                    }
                )

        return issues

    async def inspect_accounts(self) -> list[dict[str, Any]]:
        """Inspect account data and identify issues."""
        query = """
        MATCH (acc:Account)
        RETURN acc.account_id as account_id,
               acc.account_name as account_name,
               acc.organization_id as organization_id,
               acc.industry as industry,
               acc.status as status,
               acc.websites as websites,
               acc.timezone as timezone,
               acc.data_region as data_region,
               acc.region as region
        """

        result = await self.db.execute_query(query)

        issues = []
        for record in result:
            acc_issues = []

            # Check required string fields
            if not record.get("account_id"):
                acc_issues.append("account_id is null or empty")
            if not record.get("account_name"):
                acc_issues.append("account_name is null or empty")
            if not record.get("organization_id"):
                acc_issues.append("organization_id is null or empty")
            if not record.get("industry"):
                acc_issues.append("industry is null or empty")
            if not record.get("status"):
                acc_issues.append("status is null or empty")
            if not record.get("timezone"):
                acc_issues.append("timezone is null or empty")

            if acc_issues:
                issues.append(
                    {
                        "account_id": record.get("account_id"),
                        "issues": acc_issues,
                        "data": record,
                    }
                )

        return issues

    async def fix_organizations(self) -> int:
        """Fix malformed organization data."""
        logger.info("Starting organization data cleanup...")

        # Default values for organizations
        default_subscription = {
            "plan_name": "Free Plan",
            "plan_description": "Basic features for getting started",
            "price": 0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": "2024-12-31",
            "features": ["Basic Reports", "1 User"],
            "usage": {"reports_generated": 0, "reports_limit": 10},
        }

        default_billing = {
            "payment_method": {"last_four": "", "brand": "", "expires": ""},
            "address": "",
            "tax_id": "",
        }

        default_team = {"members_used": 1, "members_limit": 1, "pending_invitations": 0}

        # Update query to fix null/empty fields
        update_query = """
        MATCH (org:Organization)
        WHERE org.organization_id IS NULL 
           OR org.organization_name IS NULL 
           OR org.plan IS NULL 
           OR org.website IS NULL 
           OR org.company_size IS NULL
           OR org.subscription IS NULL
           OR org.billing IS NULL
           OR org.team IS NULL
        SET org.organization_id = COALESCE(org.organization_id, 'unknown-org-' + toString(id(org))),
            org.organization_name = COALESCE(org.organization_name, 'Unknown Organization'),
            org.plan = COALESCE(org.plan, 'Free'),
            org.website = COALESCE(org.website, ''),
            org.company_size = COALESCE(org.company_size, 'Unknown'),
            org.agency = COALESCE(org.agency, false),
            org.child_organizations = COALESCE(org.child_organizations, []),
            org.subscription = COALESCE(org.subscription, $default_subscription),
            org.billing = COALESCE(org.billing, $default_billing),
            org.team = COALESCE(org.team, $default_team)
        RETURN count(org) as updated_count
        """

        params = {
            "default_subscription": json.dumps(default_subscription),
            "default_billing": json.dumps(default_billing),
            "default_team": json.dumps(default_team),
        }

        result = await self.db.execute_write_query(update_query, params)
        updated_count = result.get("updated_count", 0)

        logger.info(f"Updated {updated_count} organizations")
        return updated_count

    async def fix_accounts(self) -> int:
        """Fix malformed account data."""
        logger.info("Starting account data cleanup...")

        # Update query to fix null/empty fields
        update_query = """
        MATCH (acc:Account)
        WHERE acc.account_id IS NULL 
           OR acc.account_name IS NULL 
           OR acc.organization_id IS NULL 
           OR acc.industry IS NULL 
           OR acc.status IS NULL 
           OR acc.timezone IS NULL
        SET acc.account_id = COALESCE(acc.account_id, 'unknown-acc-' + toString(id(acc))),
            acc.account_name = COALESCE(acc.account_name, 'Unknown Account'),
            acc.organization_id = COALESCE(acc.organization_id, 'unknown'),
            acc.industry = COALESCE(acc.industry, 'Unknown'),
            acc.status = COALESCE(acc.status, 'Active'),
            acc.websites = COALESCE(acc.websites, []),
            acc.timezone = COALESCE(acc.timezone, 'UTC'),
            acc.data_region = COALESCE(acc.data_region, ''),
            acc.region = COALESCE(acc.region, [])
        RETURN count(acc) as updated_count
        """

        result = await self.db.execute_write_query(update_query)
        updated_count = result.get("updated_count", 0)

        logger.info(f"Updated {updated_count} accounts")
        return updated_count

    async def run_inspection(self):
        """Run data inspection and report issues."""
        logger.info("=" * 60)
        logger.info("STARTING NEO4J DATA INSPECTION")
        logger.info("=" * 60)

        # Inspect organizations
        logger.info("Inspecting organization data...")
        org_issues = await self.inspect_organizations()

        if org_issues:
            logger.error(f"Found {len(org_issues)} organizations with issues:")
            for issue in org_issues:
                logger.error(
                    f"  Organization {issue['organization_id']}: {', '.join(issue['issues'])}"
                )
        else:
            logger.info("All organizations data looks good!")

        # Inspect accounts
        logger.info("Inspecting account data...")
        acc_issues = await self.inspect_accounts()

        if acc_issues:
            logger.error(f"Found {len(acc_issues)} accounts with issues:")
            for issue in acc_issues:
                logger.error(
                    f"  Account {issue['account_id']}: {', '.join(issue['issues'])}"
                )
        else:
            logger.info("All accounts data looks good!")

        return len(org_issues) + len(acc_issues)

    async def run_cleanup(self):
        """Run the complete data cleanup process."""
        logger.info("=" * 60)
        logger.info("STARTING NEO4J DATA CLEANUP")
        logger.info("=" * 60)

        # Run inspection first
        total_issues = await self.run_inspection()

        if total_issues == 0:
            logger.info("No issues found. Data cleanup not needed.")
            return

        # Ask for confirmation before making changes
        logger.info(f"Found {total_issues} data issues. Starting cleanup...")

        # Fix organizations
        org_updated = await self.fix_organizations()

        # Fix accounts
        acc_updated = await self.fix_accounts()

        logger.info("=" * 60)
        logger.info("CLEANUP COMPLETE")
        logger.info(f"Organizations updated: {org_updated}")
        logger.info(f"Accounts updated: {acc_updated}")
        logger.info("=" * 60)

        # Run inspection again to verify fixes
        logger.info("Running post-cleanup inspection...")
        remaining_issues = await self.run_inspection()

        if remaining_issues == 0:
            logger.info("✅ All data issues have been resolved!")
        else:
            logger.warning(
                f"⚠️  {remaining_issues} issues remain. Manual intervention may be required."
            )


async def main():
    """Main execution function."""
    cleanup = Neo4jDataCleanup()

    try:
        await cleanup.connect()

        # Check if user wants to run inspection only or full cleanup
        if len(sys.argv) > 1 and sys.argv[1] == "--inspect-only":
            await cleanup.run_inspection()
        else:
            await cleanup.run_cleanup()

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise
    finally:
        await cleanup.close()


if __name__ == "__main__":
    asyncio.run(main())
