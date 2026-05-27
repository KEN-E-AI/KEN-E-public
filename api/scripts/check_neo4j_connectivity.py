#!/usr/bin/env python3
"""
Script to check Neo4j connectivity and diagnose issues in staging environment.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

# Load environment variables based on environment
environment = os.getenv("ENVIRONMENT", "development")
env_file = f".env.{environment}"
if os.path.exists(env_file):
    print(f"Loading environment from {env_file}")
    load_dotenv(env_file, override=True)
else:
    print(f"Warning: {env_file} not found, using default .env")
    load_dotenv()


async def test_neo4j_connection():
    """Test Neo4j connection and basic operations."""
    # Get Neo4j configuration
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

    print(f"\n🔍 Testing Neo4j connectivity in {environment} environment")
    print(f"   URI: {neo4j_uri}")
    print(f"   Username: {neo4j_username}")
    print(f"   Database: {neo4j_database}")
    print(f"   Password: {'*' * len(neo4j_password) if neo4j_password else 'Not set'}")

    driver = None
    try:
        # Create driver
        print("\n📡 Creating Neo4j driver...")
        driver = AsyncGraphDatabase.driver(
            neo4j_uri, auth=(neo4j_username, neo4j_password)
        )

        # Verify connectivity
        print("🔗 Verifying connectivity...")
        await driver.verify_connectivity()
        print("✅ Successfully connected to Neo4j!")

        # Test a simple query
        print("\n🔍 Testing database access...")
        async with driver.session(database=neo4j_database) as session:
            result = await session.run("RETURN 'Hello Neo4j' as message")
            record = await result.single()
            print(f"✅ Query successful: {record['message']}")

        # Check if Organization node label exists
        print("\n🔍 Checking Organization nodes...")
        async with driver.session(database=neo4j_database) as session:
            result = await session.run("""
                MATCH (org:Organization)
                RETURN count(org) as count
                LIMIT 1
            """)
            record = await result.single()
            org_count = record["count"]
            print(f"✅ Found {org_count} Organization nodes")

        # Test create query (without actually creating)
        print("\n🔍 Testing CREATE query syntax...")
        test_query = """
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

        # Just validate the query syntax without executing
        async with driver.session(database=neo4j_database) as session:
            try:
                # Use EXPLAIN to validate query without executing
                explain_query = f"EXPLAIN {test_query}"
                await session.run(
                    explain_query,
                    {
                        "organization_id": "test_id",
                        "organization_name": "Test Org",
                        "plan": "Free",
                        "website": "",
                        "company_size": "",
                        "agency": False,
                        "child_organizations": [],
                        "subscription": "{}",
                        "billing": "{}",
                        "team": "{}",
                    },
                )
                print("✅ CREATE query syntax is valid")
            except Exception as e:
                print(f"❌ CREATE query validation failed: {e}")

        return True

    except Neo4jError as e:
        print(f"\n❌ Neo4j Error: {e}")
        print(f"   Error code: {e.code}")
        print(f"   Error message: {e.message}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
        return False
    finally:
        if driver:
            await driver.close()
            print("\n🔒 Connection closed")


async def check_api_health():
    """Check the API health endpoint."""
    import aiohttp

    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    health_url = f"{api_base_url}/health"

    print(f"\n🔍 Checking API health at {health_url}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(health_url) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ API Status: {data.get('status', 'unknown')}")
                    print(
                        f"   Neo4j: {data.get('services', {}).get('neo4j', 'unknown')}"
                    )
                    print(
                        f"   Firestore: {data.get('services', {}).get('firestore', 'unknown')}"
                    )
                else:
                    print(f"❌ API returned status {response.status}")
                    text = await response.text()
                    print(f"   Response: {text}")
    except Exception as e:
        print(f"❌ Failed to reach API: {e}")


async def main():
    """Run all diagnostics."""
    print("=" * 60)
    print("Neo4j Connectivity Diagnostic Tool")
    print("=" * 60)

    # Test Neo4j connection
    neo4j_ok = await test_neo4j_connection()

    # Check API health
    await check_api_health()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if neo4j_ok:
        print("✅ Neo4j connection is working properly")
        print("\n💡 If you're still getting 503 errors, check:")
        print("   1. The API service has the correct environment variables")
        print("   2. Network connectivity between API and Neo4j")
        print("   3. Neo4j memory/resource usage")
        print("   4. API logs for more detailed error messages")
    else:
        print("❌ Neo4j connection failed")
        print("\n💡 Troubleshooting steps:")
        print("   1. Verify Neo4j is running and accessible")
        print("   2. Check NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars")
        print("   3. Ensure Neo4j allows connections from the API host")
        print("   4. Check Neo4j logs for authentication or connection errors")


if __name__ == "__main__":
    asyncio.run(main())
