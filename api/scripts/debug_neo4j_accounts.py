#!/usr/bin/env python3
"""Debug script to check Neo4j account data structure directly."""

import asyncio
import os

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
load_dotenv(".env.development")


async def debug_accounts():
    """Check the actual structure of account data in Neo4j."""

    # Get Neo4j connection details
    uri = os.getenv("NEO4J_URI", "neo4j+s://bd5f0652.databases.neo4j.io")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        print("NEO4J_PASSWORD not found in .env.development")
        return

    print(f"Connecting to Neo4j at {uri}...")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    try:
        async with driver.session() as session:
            # Get one account with all its properties
            query = """
            MATCH (acc:Account)
            RETURN acc
            LIMIT 1
            """

            result = await session.run(query)
            records = await result.data()

            if not records:
                print("No accounts found in database")
                return

            account = records[0]["acc"]
            print("\n=== ACCOUNT DATA STRUCTURE ===")
            print(f"Account ID: {account.get('account_id')}")
            print(f"Account Name: {account.get('account_name')}")
            print("\nAll properties:")
            for key, value in account.items():
                print(f"  {key}: {value} (type: {type(value).__name__})")

            # Check specifically for marketing_channels
            print("\n=== MARKETING CHANNELS CHECK ===")
            if "marketing_channels" in account:
                mc = account["marketing_channels"]
                print(f"marketing_channels exists: {mc}")
                print(f"Type: {type(mc)}")
                print(f"Is None: {mc is None}")
                print(f"Is empty list: {mc == []}")
            else:
                print("marketing_channels property does NOT exist on this account")

            # Try a different query to get marketing channels
            print("\n=== ALTERNATIVE QUERY ===")
            query2 = """
            MATCH (acc:Account)
            WHERE acc.marketing_channels IS NOT NULL
            RETURN acc.account_id as id, 
                   acc.account_name as name,
                   acc.marketing_channels as marketing_channels
            LIMIT 5
            """

            result2 = await session.run(query2)
            records2 = await result2.data()

            if records2:
                print(f"Found {len(records2)} accounts with marketing_channels:")
                for rec in records2:
                    print(f"  - {rec['name']}: {rec['marketing_channels']}")
            else:
                print("No accounts found with marketing_channels property set")

            # Check if any account has the property at all
            query3 = """
            MATCH (acc:Account)
            WHERE EXISTS(acc.marketing_channels)
            RETURN count(acc) as count
            """

            result3 = await session.run(query3)
            records3 = await result3.data()
            count = records3[0]["count"] if records3 else 0

            print(f"\nTotal accounts with marketing_channels property: {count}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(debug_accounts())
