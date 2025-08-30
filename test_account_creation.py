#!/usr/bin/env python3
"""
Test account creation with strategy generation
"""

import requests
import json
import time
import uuid

# API endpoint
BASE_URL = "http://localhost:8000"

# Generate a unique email for testing
test_id = str(uuid.uuid4())[:8]
test_email = f"test_{test_id}@example.com"

# Create account payload
payload = {
    "email": test_email,
    "password": "TestPassword123!",
    "company_name": f"TestCompany_{test_id}",
    "industry": "Technology",
    "websites": ["https://testcompany.com", "https://blog.testcompany.com"],
    "customer_regions": ["North America", "Europe"],
    "annual_ad_budget": 50000.0
}

print(f"Creating account for: {payload['company_name']}")
print(f"Email: {test_email}")
print("-" * 50)

# Create the account
response = requests.post(
    f"{BASE_URL}/api/v1/accounts/",
    json=payload
)

if response.status_code == 200:
    result = response.json()
    account_id = result.get("account", {}).get("account_id")
    print(f"✅ Account created successfully!")
    print(f"Account ID: {account_id}")
    
    # Poll for progress
    print("\nChecking strategy generation progress...")
    for i in range(30):  # Check for up to 5 minutes
        time.sleep(10)
        
        progress_response = requests.get(
            f"{BASE_URL}/api/v1/accounts/{account_id}/creation-progress"
        )
        
        if progress_response.status_code == 200:
            progress = progress_response.json()
            status = progress.get("status")
            percentage = progress.get("percentage", 0)
            message = progress.get("message", "")
            
            print(f"[{i*10}s] Status: {status} ({percentage}%) - {message}")
            
            if status == "completed":
                print("\n✅ Account setup completed!")
                break
            elif status == "failed":
                print(f"\n❌ Account setup failed: {message}")
                break
        else:
            print(f"Failed to get progress: {progress_response.status_code}")
    
    # Check if strategy documents were created
    print("\n" + "=" * 50)
    print("Checking for strategy documents in Firestore...")
    
    # Note: In a real test, you would check Firestore directly
    # For now, we'll just check the logs
    print("Check the API logs for strategy document creation status")
    
else:
    print(f"❌ Failed to create account: {response.status_code}")
    print(response.text)