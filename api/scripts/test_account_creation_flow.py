"""
Quick integration test for account creation with progress tracking.
"""
import asyncio
import time
from datetime import datetime
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kene_api.cache import InMemoryCache

def test_account_creation_flow():
    print("🧪 Testing account creation progress tracking flow...")
    
    # Initialize cache
    cache = InMemoryCache()
    
    # Simulate account creation progress updates
    account_id = f"test-account-{int(time.time())}"
    
    # Step 1: Initial progress
    progress1 = {
        "status": "processing",
        "percentage": 0,
        "currentStep": 1,
        "totalSteps": 6,
        "message": "Creating account",
        "steps": [
            {"step": 1, "name": "Create account", "status": "processing"},
            {"step": 2, "name": "Initialize Neo4j", "status": "pending"},
            {"step": 3, "name": "Create Firestore document", "status": "pending"},
            {"step": 4, "name": "Create BigQuery dataset", "status": "pending"},
            {"step": 5, "name": "Create GCS bucket", "status": "pending"},
            {"step": 6, "name": "Finalize account setup", "status": "pending"},
        ]
    }
    
    cache.set(f"account_creation_progress:{account_id}", progress1, ttl_seconds=300)
    retrieved1 = cache.get(f"account_creation_progress:{account_id}")
    assert retrieved1 is not None, "Progress should be cached"
    assert retrieved1["status"] == "processing"
    assert retrieved1["currentStep"] == 1
    print("✅ Step 1: Account creation started")
    
    # Step 2: Neo4j initialized
    progress2 = progress1.copy()
    progress2["percentage"] = 30
    progress2["currentStep"] = 2
    progress2["message"] = "Initializing Neo4j graph"
    progress2["steps"][0]["status"] = "completed"
    progress2["steps"][1]["status"] = "processing"
    
    cache.set(f"account_creation_progress:{account_id}", progress2, ttl_seconds=300)
    retrieved2 = cache.get(f"account_creation_progress:{account_id}")
    assert retrieved2["currentStep"] == 2
    print("✅ Step 2: Neo4j initialized")
    
    # Step 3: Complete
    progress3 = progress2.copy()
    progress3["status"] = "completed"
    progress3["percentage"] = 100
    progress3["currentStep"] = 6
    progress3["message"] = "Account created successfully"
    for step in progress3["steps"]:
        step["status"] = "completed"
    
    cache.set(f"account_creation_progress:{account_id}", progress3, ttl_seconds=300)
    retrieved3 = cache.get(f"account_creation_progress:{account_id}")
    assert retrieved3["status"] == "completed"
    assert retrieved3["percentage"] == 100
    print("✅ Step 3: Account creation completed")
    
    # Verify cache still has the data
    final_check = cache.get(f"account_creation_progress:{account_id}")
    assert final_check is not None
    assert final_check["status"] == "completed"
    print(f"✅ Cache contains completed progress for {account_id}")
    
    print("\n🎉 All integration tests passed!")
    return True

if __name__ == "__main__":
    test_account_creation_flow()
