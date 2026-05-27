#!/usr/bin/env python3
"""Check marketing channels data using API's Neo4j service."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kene_api.database import get_neo4j_service


async def check_accounts():
    """Check accounts and their marketing channels in Neo4j."""

    # Get Neo4j service instance (this is async)
    db = await get_neo4j_service()

    try:
        # Check connectivity
        is_healthy = await db.health_check()
        print(f"Neo4j connection healthy: {is_healthy}")

        if not is_healthy:
            print("Cannot connect to Neo4j")
            return

        # Query to get all accounts with their properties
        query = """
        MATCH (acc:Account)
        RETURN acc
        LIMIT 10
        """

        result = await db.execute_query(query)

        print(f"\nFound {len(result)} accounts (showing up to 10):\n")
        print("-" * 80)

        for record in result:
            acc = record.get("acc", {})
            print(f"Account ID: {acc.get('account_id')}")
            print(f"Account Name: {acc.get('account_name')}")
            print(f"Organization: {acc.get('organization_id')}")
            print(f"Marketing Channels: {acc.get('marketing_channels', 'NOT SET')}")
            print(f"Product Integrations: {acc.get('product_integrations', 'NOT SET')}")

            # Check all properties
            all_props = list(acc.keys()) if isinstance(acc, dict) else []
            print(f"All properties: {', '.join(all_props)}")
            print("-" * 80)

        # Check specifically for accounts with marketing_channels
        query_with_channels = """
        MATCH (acc:Account)
        WHERE acc.marketing_channels IS NOT NULL AND size(acc.marketing_channels) > 0
        RETURN count(acc) as count
        """

        result = await db.execute_query(query_with_channels)
        count_with_channels = result[0]["count"] if result else 0

        print(f"\nAccounts with marketing_channels set: {count_with_channels}")

        # Get total count of accounts
        query_total = """
        MATCH (acc:Account)
        RETURN count(acc) as count
        """

        result = await db.execute_query(query_total)
        total_count = result[0]["count"] if result else 0

        print(f"Total accounts in database: {total_count}")

        # Show an example of an account with marketing channels if any exist
        if count_with_channels > 0:
            print("\nExample account with marketing_channels:")
            query_example = """
            MATCH (acc:Account)
            WHERE acc.marketing_channels IS NOT NULL AND size(acc.marketing_channels) > 0
            RETURN acc
            LIMIT 1
            """
            result = await db.execute_query(query_example)
            if result:
                acc = result[0]["acc"]
                print(f"  Account: {acc.get('account_name')} ({acc.get('account_id')})")
                print(f"  Marketing Channels: {acc.get('marketing_channels')}")

    finally:
        # Close the connection
        await db.close()


if __name__ == "__main__":
    asyncio.run(check_accounts())
