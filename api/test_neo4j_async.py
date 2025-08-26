#!/usr/bin/env python3
"""Test Neo4j async connection directly."""

import asyncio
import os
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

# Load from .env file manually
with open('.env', 'r') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

uri = os.getenv('NEO4J_URI')
username = os.getenv('NEO4J_USERNAME')
password = os.getenv('NEO4J_PASSWORD')

print(f'Testing async connection to: {uri}')
print(f'Username: {username}')


async def test_connection():
    """Test async Neo4j connection."""
    try:
        driver = AsyncGraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=10.0,
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60.0,
        )
        
        print("Driver created, testing connectivity...")
        await driver.verify_connectivity()
        print("✅ Connectivity verified!")
        
        # Try to run a query
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS test")
            data = await result.single()
            print(f"✅ Query successful! Result: {data['test']}")
        
        await driver.close()
        print("✅ Connection closed successfully!")
        
    except Neo4jError as e:
        print(f"❌ Neo4j error: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error code: {e.code if hasattr(e, 'code') else 'N/A'}")
    except Exception as e:
        print(f"❌ General error: {e}")
        print(f"Error type: {type(e).__name__}")


if __name__ == "__main__":
    asyncio.run(test_connection())