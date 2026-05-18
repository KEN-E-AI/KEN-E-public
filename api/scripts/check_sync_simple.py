#!/usr/bin/env python3
"""Simple test of the sync endpoint."""

import requests
import sys

def test_sync(account_id):
    """Test the sync endpoint."""
    # Make sure API is running
    api_url = "http://localhost:8000"
    
    print(f"Testing sync for account: {account_id}")
    print("-" * 50)
    
    # First, get account info
    try:
        account_resp = requests.get(f"{api_url}/api/v1/accounts/{account_id}")
        if account_resp.status_code == 200:
            account_data = account_resp.json()
            print(f"Account Name: {account_data.get('account_name', 'Unknown')}")
            print(f"Regions: {account_data.get('region', [])}")
        else:
            print(f"Could not fetch account info: {account_resp.status_code}")
    except Exception as e:
        print(f"Error fetching account: {e}")
    
    # Call sync endpoint
    print("\nCalling sync endpoint...")
    try:
        sync_resp = requests.post(
            f"{api_url}/api/v1/activities/logs/sync",
            params={"account_id": account_id}
        )
        
        print(f"Status Code: {sync_resp.status_code}")
        
        if sync_resp.status_code == 200:
            data = sync_resp.json()
            if data["success"]:
                sync_data = data["data"]
                print("\nSync Results:")
                print(f"  Regions: {sync_data['regions']}")
                print(f"  Total holidays in BigQuery: {sync_data['total_holidays_in_bigquery']}")
                print(f"  Existing logs before sync: {sync_data['existing_logs_before_sync']}")
                print(f"  New logs created: {sync_data['new_logs_created']}")
                print(f"  Logs deleted: {sync_data['logs_deleted']}")
                print(f"  Logs protected from deletion: {sync_data['logs_protected_from_deletion']}")
                
                # Get activities to see current state
                print("\nFetching current activities...")
                activities_resp = requests.get(
                    f"{api_url}/api/v1/activities/",
                    params={"account_id": account_id}
                )
                
                if activities_resp.status_code == 200:
                    activities = activities_resp.json()["activities"]
                    # Find act_00
                    for activity in activities:
                        if activity["id"] == "act_00":
                            logs = activity.get("logs", [])
                            print(f"\nCurrent holiday logs ({len(logs)} total):")
                            for log in sorted(logs, key=lambda x: x.get("description", "")):
                                print(f"  - {log.get('description', 'Unknown')} ({log.get('start_date', 'Unknown')})")
                            break
                    else:
                        print("\nact_00 not found in activities list")
                        
            else:
                print(f"Sync failed: {data.get('message', 'Unknown error')}")
        else:
            print(f"Error response: {sync_resp.text}")
            
    except requests.exceptions.ConnectionError:
        print("\nERROR: Cannot connect to API. Make sure it's running:")
        print("  cd api")
        print("  uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000")
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_sync_simple.py <account_id>")
        sys.exit(1)
    
    test_sync(sys.argv[1])