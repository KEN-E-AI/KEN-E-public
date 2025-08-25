#!/usr/bin/env python3
"""
Test Redis integration in production environment.
This script tests the Redis/Memorystore connection and operations.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any

import httpx
from dotenv import load_dotenv

# Load production environment
load_dotenv(".env.production")

PRODUCTION_API_URL = "https://kene-api-prod-4quwenkusq-uc.a.run.app"
STAGING_API_URL = "https://kene-api-staging-d3wm5f7uba-uc.a.run.app"

# Choose which environment to test
TEST_ENV = os.getenv("TEST_ENV", "production")
API_URL = PRODUCTION_API_URL if TEST_ENV == "production" else STAGING_API_URL

print(f"\n🔍 Testing Redis in {TEST_ENV.upper()} environment")
print(f"📍 API URL: {API_URL}")
print("=" * 60)


async def test_health_endpoint():
    """Test if health endpoint reports Redis status."""
    print("\n1️⃣  Testing Health Endpoint...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_URL}/health", timeout=10.0)
            data = response.json()
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {json.dumps(data, indent=2)}")
            
            # Check for Redis status in health response
            if "redis" in data:
                redis_status = data["redis"]
                print(f"\n   ✅ Redis Status: {redis_status}")
                
                if redis_status.get("available"):
                    print(f"   ✅ Redis is CONNECTED")
                    print(f"   📊 Stats:")
                    if "connected_clients" in redis_status:
                        print(f"      - Connected clients: {redis_status['connected_clients']}")
                    if "used_memory_human" in redis_status:
                        print(f"      - Memory usage: {redis_status['used_memory_human']}")
                    if "total_connections_received" in redis_status:
                        print(f"      - Total connections: {redis_status['total_connections_received']}")
                else:
                    print(f"   ⚠️  Redis is NOT available")
            else:
                print(f"   ⚠️  Redis status not found in health response")
                
            return response.status_code == 200
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False


async def test_cache_operations():
    """Test cache operations through the API."""
    print("\n2️⃣  Testing Cache Operations...")
    
    # This would require authentication and actual API calls
    # For now, we'll check if the API is responding correctly
    
    test_endpoints = [
        ("/api/v1/metrics", "GET"),
        ("/api/v1/activities", "GET"),
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint, method in test_endpoints:
            try:
                print(f"\n   Testing {method} {endpoint}...")
                
                if method == "GET":
                    response = await client.get(f"{API_URL}{endpoint}", timeout=10.0)
                
                # 401 is expected without auth, but it means the endpoint exists
                if response.status_code in [200, 401, 403]:
                    print(f"   ✅ Endpoint responding (status: {response.status_code})")
                else:
                    print(f"   ⚠️  Unexpected status: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ Error testing {endpoint}: {e}")


async def check_cloud_run_logs():
    """Check Cloud Run logs for Redis-related messages."""
    print("\n3️⃣  Checking Cloud Run Logs...")
    
    project_id = "ken-e-production" if TEST_ENV == "production" else "ken-e-staging"
    service_name = "kene-api-prod" if TEST_ENV == "production" else "kene-api-staging"
    
    print(f"\n   To view Redis logs, run:")
    print(f"   gcloud run services logs read {service_name} \\")
    print(f"     --project={project_id} \\")
    print(f"     --region=us-central1 \\")
    print(f"     --limit=50 | grep -i redis")
    
    print(f"\n   Or check in Cloud Console:")
    print(f"   https://console.cloud.google.com/run/detail/us-central1/{service_name}/logs?project={project_id}")


async def test_redis_metrics():
    """Test Redis metrics endpoint if available."""
    print("\n4️⃣  Testing Redis Metrics...")
    
    async with httpx.AsyncClient() as client:
        try:
            # Try to get metrics from the health endpoint
            response = await client.get(f"{API_URL}/health", timeout=10.0)
            
            if response.status_code == 200:
                data = response.json()
                
                if "redis" in data and data["redis"].get("available"):
                    print("   ✅ Redis metrics available in health endpoint")
                    
                    # Display connection info
                    redis_info = data.get("redis", {})
                    print("\n   📊 Redis Connection Info:")
                    print(f"      - Available: {redis_info.get('available', False)}")
                    
                    if "error" in redis_info:
                        print(f"      - Error: {redis_info['error']}")
                    
                    return True
                else:
                    print("   ⚠️  Redis not available or no metrics")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Error getting metrics: {e}")
            return False


async def main():
    """Run all tests."""
    print("\n🚀 Starting Redis Production Tests")
    print("=" * 60)
    
    # Track test results
    results = {}
    
    # Run tests
    results["health"] = await test_health_endpoint()
    results["metrics"] = await test_redis_metrics()
    await test_cache_operations()
    await check_cloud_run_logs()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print(f"\n✅ Passed: {passed_tests}/{total_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Redis is working in production!")
    elif results.get("health"):
        print("\n⚠️  Some tests failed, but health check passed. Redis may be partially working.")
    else:
        print("\n❌ Redis integration needs attention.")
    
    print("\n📝 Next Steps:")
    print("1. Check Cloud Run logs for detailed Redis connection info")
    print("2. Verify Memorystore instance is accessible from Cloud Run")
    print("3. Ensure VPC connector is properly configured if needed")
    print("4. Check IAM permissions for the service account")


if __name__ == "__main__":
    asyncio.run(main())