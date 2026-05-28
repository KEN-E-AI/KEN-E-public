#!/usr/bin/env python3
"""
Script to test organization creation endpoint in staging environment.
"""

import asyncio
import json
import os
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

# Load environment variables based on environment
environment = os.getenv("ENVIRONMENT", "development")
env_file = f".env.{environment}"
if os.path.exists(env_file):
    print(f"Loading environment from {env_file}")
    load_dotenv(env_file, override=True)
else:
    print(f"Warning: {env_file} not found, using default .env")
    load_dotenv()


async def get_auth_token():
    """Get a valid auth token (you'll need to implement this based on your auth)."""
    # This is a placeholder - you need to implement actual authentication
    # For testing, you might want to:
    # 1. Use a test user token
    # 2. Implement Firebase auth flow
    # 3. Use a service account

    # For now, return None and test without auth
    print("⚠️  Warning: No authentication token provided")
    print("   If the API requires authentication, this test will fail")
    return None


async def test_create_organization():
    """Test creating an organization via the API."""
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    if environment == "staging":
        api_base_url = "https://staging.api.ken-e.ai"

    create_url = f"{api_base_url}/api/v1/organizations/"

    print(f"\n🔍 Testing organization creation at {create_url}")

    # Prepare test data
    test_org = {
        "organization_name": f"Test Org {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "plan": "Free",
        "website": "https://test.example.com",
        "company_size": "small",
        "agency": False,
        "child_organizations": [],
        "subscription": {
            "plan_name": "Free Plan",
            "plan_description": "Basic features for getting started",
            "price": 0,
            "currency": "USD",
            "billing_cycle": "monthly",
            "next_billing_date": datetime.now().isoformat(),
            "features": ["Basic Reports", "1 User"],
            "usage": {"reports_generated": 0, "reports_limit": 10},
        },
        "billing": {
            "payment_method": {"last_four": "", "brand": "", "expires": ""},
            "address": "",
            "tax_id": "",
        },
        "team": {"members_used": 1, "members_limit": 1, "pending_invitations": 0},
    }

    print("\n📝 Test organization data:")
    print(json.dumps(test_org, indent=2))

    # Get auth token
    token = await get_auth_token()

    headers = {
        "Content-Type": "application/json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with aiohttp.ClientSession() as session:
            print(f"\n🚀 Sending POST request to {create_url}")
            async with session.post(
                create_url, json=test_org, headers=headers
            ) as response:
                response_text = await response.text()

                print(f"\n📊 Response Status: {response.status}")
                print("📊 Response Headers:")
                for key, value in response.headers.items():
                    print(f"   {key}: {value}")

                if response.status == 200 or response.status == 201:
                    data = json.loads(response_text)
                    print("\n✅ Organization created successfully!")
                    print(f"   Organization ID: {data.get('organization_id')}")
                    print(f"   Organization Name: {data.get('organization_name')}")
                    return True
                else:
                    print("\n❌ Failed to create organization")
                    print(f"   Status: {response.status}")
                    print(f"   Response: {response_text}")

                    if response.status == 503:
                        print("\n💡 503 Service Unavailable - Possible causes:")
                        print("   1. Neo4j database is not accessible")
                        print("   2. API cannot connect to Neo4j")
                        print("   3. Database is overloaded or down")
                        print("   4. Network issues between API and database")

                    return False

    except aiohttp.ClientError as e:
        print(f"\n❌ HTTP Client Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
        return False


async def check_api_logs():
    """Provide instructions for checking API logs."""
    print("\n📋 To check API logs in staging:")
    print("   1. Google Cloud Console:")
    print("      gcloud logs read --project=<staging-project> --limit=50")
    print("   2. Check Cloud Run logs:")
    print("      Go to Cloud Run > kene-api-staging > Logs")
    print("   3. Look for errors around Neo4j connection")


async def main():
    """Run the organization creation test."""
    print("=" * 60)
    print("Organization Creation Test")
    print(f"Environment: {environment}")
    print("=" * 60)

    # Test organization creation
    success = await test_create_organization()

    if not success:
        await check_api_logs()

        print("\n💡 Quick fixes to try:")
        print("   1. Restart the API service in staging")
        print("   2. Check Neo4j connection string in environment variables")
        print("   3. Verify Neo4j is running and accessible from staging")
        print("   4. Check if Neo4j has enough resources (memory/CPU)")


if __name__ == "__main__":
    asyncio.run(main())
