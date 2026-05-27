#!/usr/bin/env python3
"""Test creating an account with regions to verify ActivityLog creation."""

from datetime import datetime

import requests

# API endpoint
url = "http://localhost:8000/api/v1/accounts/"

# Test account data with regions
account_data = {
    "account_name": f"Test Holiday Account {datetime.now().strftime('%Y%m%d_%H%M%S')}",
    "organization_id": "org_841e82cc157443d39465dd1aabbd5356",  # Non-agency org ID
    "industry": "Technology",
    "status": "Active",
    "websites": ["https://example.com"],
    "timezone": "America/New_York",
    "region": ["US", "CA", "AU", "UK"],  # Multiple regions to test holiday creation
}

print("Creating account with regions:", account_data["region"])
print(f"Account name: {account_data['account_name']}")

try:
    response = requests.post(url, json=account_data)

    if response.status_code == 200:
        result = response.json()
        print("\n✓ Account created successfully!")
        print(f"Account ID: {result['account_id']}")
        print(f"Regions: {result.get('region', [])}")

        # Now check the logs
        print("\n📋 Check the API logs for:")
        print(
            "  - 'Account {id} has regions: [...], attempting to create holiday activity logs'"
        )
        print(
            "  - 'Querying BigQuery for holidays in project ken-e-dev for regions [...]'"
        )
        print("  - 'Found X holiday activities from BigQuery'")
        print("  - 'Successfully created X holiday activity logs for account {id}'")

    else:
        print(f"\n✗ Failed to create account: {response.status_code}")
        print(f"Error: {response.text}")

except Exception as e:
    print(f"\n✗ Error: {e}")
