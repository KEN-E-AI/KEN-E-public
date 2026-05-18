#!/usr/bin/env python3
"""Test script to verify account creation progress tracking."""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set up environment
os.environ["ENVIRONMENT"] = "development"
os.environ["SUPPRESS_REDIS_WARNING"] = "true"

from kene_api.cache import InMemoryCache
from kene_api.routers.accounts import AccountCreationProgress, ProgressStep

async def test_progress_storage():
    """Test storing and retrieving progress from cache."""
    
    print("Testing progress tracking storage...")
    
    # Initialize cache service
    cache_service = InMemoryCache()
    
    # Create test account ID
    account_id = f"test_acc_{int(time.time())}"
    print(f"\nTest account ID: {account_id}")
    
    # Test storing progress at different stages
    stages = [
        (0, "Initializing account creation"),
        (20, "Setting up organization structure"),
        (40, "Creating Neo4j nodes and relationships"),
        (60, "Initializing agent workspace"),
        (80, "Configuring account settings"),
        (100, "Account creation complete")
    ]
    
    for percentage, message in stages:
        # Create progress update
        progress = AccountCreationProgress(
            status="processing" if percentage < 100 else "completed",
            percentage=percentage,
            current_step=stages.index((percentage, message)) + 1,
            total_steps=len(stages),
            message=message,
            steps=[
                ProgressStep(
                    name=msg,
                    status="completed" if stages.index((pct, msg)) < stages.index((percentage, message)) 
                           else "processing" if stages.index((pct, msg)) == stages.index((percentage, message))
                           else "pending"
                )
                for pct, msg in stages
            ]
        )
        
        # Store in cache
        key = f"account_progress:{account_id}"
        cache_service.set(key, progress.model_dump(), ttl_seconds=300)
        
        print(f"\n✓ Stored progress: {percentage}% - {message}")
        
        # Retrieve and verify
        retrieved = cache_service.get(key)
        if retrieved:
            print(f"  Retrieved: {retrieved.get('percentage')}% - {retrieved.get('message')}")
        else:
            print(f"  ❌ Failed to retrieve progress!")
        
        # Small delay to simulate work
        await asyncio.sleep(0.5)
    
    # Test retrieval after completion
    print("\n\nFinal retrieval test...")
    final_progress = cache_service.get(f"account_progress:{account_id}")
    if final_progress:
        print(f"✓ Final progress retrieved successfully:")
        print(f"  Status: {final_progress.get('status')}")
        print(f"  Percentage: {final_progress.get('percentage')}%")
        print(f"  Message: {final_progress.get('message')}")
    else:
        print("❌ Could not retrieve final progress")
    
    # Clean up
    cache_service.delete(f"account_progress:{account_id}")
    print(f"\n✓ Cleaned up test data")

async def test_progress_endpoint():
    """Test the actual API endpoint for progress tracking."""
    import httpx
    
    print("\n\nTesting API endpoint...")
    
    # You would need a valid token for this to work
    # This is just to show the endpoint structure
    base_url = "http://localhost:8000"
    test_account_id = "acc_test123"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/api/v1/accounts/{test_account_id}/creation-status",
                timeout=5.0
            )
            
            if response.status_code == 401:
                print("❌ Authentication required (expected for this test)")
            elif response.status_code == 404:
                print("❌ Account not found or no progress data")
            elif response.status_code == 200:
                data = response.json()
                print(f"✓ Progress data retrieved:")
                print(json.dumps(data, indent=2))
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                
        except httpx.ConnectError:
            print("❌ Could not connect to API server. Make sure it's running on port 8000")
        except Exception as e:
            print(f"❌ Error testing endpoint: {e}")

async def main():
    """Run all tests."""
    print("=" * 60)
    print("Account Creation Progress Tracking Test")
    print("=" * 60)
    
    # Test cache storage
    await test_progress_storage()
    
    # Test API endpoint (will fail without auth, but shows structure)
    await test_progress_endpoint()
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())