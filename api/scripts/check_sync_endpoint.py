#!/usr/bin/env python3
"""Test the sync endpoint directly via HTTP."""

import requests
import json
import sys

def test_sync_endpoint(account_id, api_base_url="http://localhost:8000"):
    """Test the sync endpoint and display the results."""
    
    endpoint = f"{api_base_url}/api/v1/activities/logs/sync"
    params = {"account_id": account_id}
    
    print(f"Testing sync for account: {account_id}")
    print(f"Endpoint: {endpoint}")
    print("-" * 50)
    
    try:
        response = requests.post(endpoint, params=params)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()["data"]
            print("\n" + "=" * 50)
            print("SYNC SUMMARY:")
            print(f"  Account ID: {data['account_id']}")
            print(f"  Regions: {data['regions']}")
            print(f"  Total holidays in BigQuery: {data['total_holidays_in_bigquery']}")
            print(f"  Existing logs before sync: {data['existing_logs_before_sync']}")
            print(f"  New logs created: {data['new_logs_created']}")
            print(f"  Logs deleted: {data['logs_deleted']}")
            print(f"  Logs protected from deletion: {data['logs_protected_from_deletion']}")
            print("=" * 50)
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API. Make sure the API is running:")
        print("  cd api && uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_sync_endpoint.py <account_id>")
        print("Example: python check_sync_endpoint.py acc_123456")
        sys.exit(1)
    
    account_id = sys.argv[1]
    test_sync_endpoint(account_id)