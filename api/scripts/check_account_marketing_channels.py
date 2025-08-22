#!/usr/bin/env python3
"""Check marketing channels data in Neo4j for accounts."""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Load environment variables
load_dotenv('.env.development')

async def check_accounts():
    """Check accounts and their marketing channels in Neo4j."""
    
    # Get Neo4j connection details
    neo4j_uri = os.getenv('NEO4J_URI', 'neo4j+s://bd5f0652.databases.neo4j.io')
    neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
    neo4j_password = os.getenv('NEO4J_PASSWORD')
    
    if not neo4j_password:
        print("NEO4J_PASSWORD not found in environment")
        return
    
    print(f"Connecting to Neo4j at {neo4j_uri}...")
    
    # Create driver
    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        async with driver.session() as session:
            # Query to get all accounts with their properties
            query = """
            MATCH (acc:Account)
            RETURN acc.account_id as account_id, 
                   acc.account_name as account_name,
                   acc.marketing_channels as marketing_channels,
                   acc.product_integrations as product_integrations,
                   acc.organization_id as organization_id
            LIMIT 10
            """
            
            result = await session.run(query)
            records = await result.data()
            
            print(f"\nFound {len(records)} accounts (showing up to 10):\n")
            print("-" * 80)
            
            for record in records:
                print(f"Account ID: {record['account_id']}")
                print(f"Account Name: {record['account_name']}")
                print(f"Organization: {record['organization_id']}")
                print(f"Marketing Channels: {record['marketing_channels']}")
                print(f"Product Integrations: {record['product_integrations']}")
                print("-" * 80)
            
            # Check specifically for accounts with marketing_channels
            query_with_channels = """
            MATCH (acc:Account)
            WHERE acc.marketing_channels IS NOT NULL AND size(acc.marketing_channels) > 0
            RETURN count(acc) as count
            """
            
            result = await session.run(query_with_channels)
            records = await result.data()
            count_with_channels = records[0]['count'] if records else 0
            
            print(f"\nAccounts with marketing_channels set: {count_with_channels}")
            
            # Get total count of accounts
            query_total = """
            MATCH (acc:Account)
            RETURN count(acc) as count
            """
            
            result = await session.run(query_total)
            records = await result.data()
            total_count = records[0]['count'] if records else 0
            
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
                result = await session.run(query_example)
                records = await result.data()
                if records:
                    acc = records[0]['acc']
                    print(f"  Account: {acc.get('account_name')} ({acc.get('account_id')})")
                    print(f"  Marketing Channels: {acc.get('marketing_channels')}")
                    
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_accounts())