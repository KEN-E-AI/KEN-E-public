#!/usr/bin/env python3
"""Test Neo4j service as used by the API."""

import asyncio
import sys
import os

# Add API source to path
sys.path.insert(0, 'src')

# Set up environment
os.environ['NEO4J_URI'] = 'neo4j+s://c6e91588.databases.neo4j.io'
os.environ['NEO4J_USERNAME'] = 'neo4j'

# Load password from .env
with open('.env', 'r') as f:
    for line in f:
        if 'NEO4J_PASSWORD' in line and not line.startswith('#'):
            _, value = line.strip().split('=', 1)
            os.environ['NEO4J_PASSWORD'] = value
            break

from kene_api.database import neo4j_service


async def test_api_connection():
    """Test Neo4j connection as the API would use it."""
    print("Testing Neo4j service as used by API...")
    print(f"Driver before connect: {neo4j_service.driver}")
    
    # Connect (as the API does on startup)
    try:
        await neo4j_service.connect()
        print("✅ Connected successfully!")
        print(f"Driver after connect: {neo4j_service.driver}")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    # Test health check (as API routes do)
    try:
        is_healthy = await neo4j_service.health_check()
        print(f"Health check result: {is_healthy}")
        
        if is_healthy:
            print("✅ Health check passed!")
        else:
            print("❌ Health check failed!")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Try a query
    try:
        async with neo4j_service.get_session() as session:
            result = await session.run("RETURN 1 AS test")
            data = await result.single()
            print(f"✅ Query successful! Result: {data['test']}")
    except Exception as e:
        print(f"❌ Query failed: {e}")
    
    # Close
    await neo4j_service.close()
    print("Connection closed.")


if __name__ == "__main__":
    asyncio.run(test_api_connection())