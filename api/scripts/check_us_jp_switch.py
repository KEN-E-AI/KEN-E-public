#!/usr/bin/env python3
"""Test switching between US and JP regions."""

import requests


def test_region_switch():
    """Test switching between US and JP regions."""
    api_url = "http://localhost:8000"
    account_id = "acc_adf3a803fe294ae4af0f8bc3ad3218fa"

    print("TESTING US <-> JP REGION SWITCH")
    print("=" * 50)

    # Get current state
    print("\n0. Getting current state...")
    account_resp = requests.get(f"{api_url}/api/v1/accounts/{account_id}")
    if account_resp.status_code == 200:
        current_region = account_resp.json().get("region", [])
        print(f"Current region: {current_region}")

    # Step 1: Set region to US
    print("\n1. Setting region to US...")
    update_resp = requests.put(
        f"{api_url}/api/v1/accounts/{account_id}",
        json={
            "account_id": account_id,
            "account_name": "japan test",
            "organization_id": "org_ken_e",
            "user_id": "user123",
            "region": ["US"],
        },
    )
    if update_resp.status_code == 200:
        print("✓ Region set to US")
    else:
        print(f"✗ Failed to set region: {update_resp.text}")
        return

    # Step 2: Sync holidays for US
    print("\n2. Syncing holidays for US...")
    sync_resp = requests.post(
        f"{api_url}/api/v1/activities/logs/sync", params={"account_id": account_id}
    )
    if sync_resp.status_code == 200:
        data = sync_resp.json()["data"]
        print("Results:")
        print(f"  - Regions: {data['regions']}")
        print(f"  - Total holidays in BigQuery: {data['total_holidays_in_bigquery']}")
        print(f"  - Existing logs before sync: {data['existing_logs_before_sync']}")
        print(f"  - New logs created: {data['new_logs_created']}")
        print(f"  - Logs deleted: {data['logs_deleted']}")
        print(f"  - Logs protected: {data['logs_protected_from_deletion']}")
    else:
        print(f"✗ Sync failed: {sync_resp.text}")
        return

    # Step 3: Check logs for US
    print("\n3. Checking logs for US...")
    activities_resp = requests.get(
        f"{api_url}/api/v1/activities/", params={"account_id": account_id}
    )
    if activities_resp.status_code == 200:
        activities = activities_resp.json()["activities"]
        act00 = [a for a in activities if a["id"] == "act_00"][0]
        us_logs = act00["logs"]
        print(f"✓ Found {len(us_logs)} logs for act_00")
        if len(us_logs) > 0:
            print("Sample US logs:")
            for log in us_logs[:5]:
                print(f"  - {log['description']} ({log['start_date']})")
    else:
        print(f"✗ Failed to get activities: {activities_resp.text}")

    # Step 4: Switch to JP
    print("\n4. Switching region to JP...")
    update_resp = requests.put(
        f"{api_url}/api/v1/accounts/{account_id}",
        json={
            "account_id": account_id,
            "account_name": "japan test",
            "organization_id": "org_ken_e",
            "user_id": "user123",
            "region": ["JP"],
        },
    )
    if update_resp.status_code == 200:
        print("✓ Region set to JP")
    else:
        print(f"✗ Failed to set region: {update_resp.text}")
        return

    # Step 5: Sync holidays for JP
    print("\n5. Syncing holidays for JP...")
    sync_resp = requests.post(
        f"{api_url}/api/v1/activities/logs/sync", params={"account_id": account_id}
    )
    if sync_resp.status_code == 200:
        data = sync_resp.json()["data"]
        print("Results:")
        print(f"  - Regions: {data['regions']}")
        print(f"  - Total holidays in BigQuery: {data['total_holidays_in_bigquery']}")
        print(f"  - Existing logs before sync: {data['existing_logs_before_sync']}")
        print(f"  - New logs created: {data['new_logs_created']}")
        print(f"  - Logs deleted: {data['logs_deleted']}")
        print(f"  - Logs protected: {data['logs_protected_from_deletion']}")
    else:
        print(f"✗ Sync failed: {sync_resp.text}")
        return

    # Step 6: Check logs for JP
    print("\n6. Checking logs for JP...")
    activities_resp = requests.get(
        f"{api_url}/api/v1/activities/", params={"account_id": account_id}
    )
    if activities_resp.status_code == 200:
        activities = activities_resp.json()["activities"]
        act00 = [a for a in activities if a["id"] == "act_00"][0]
        jp_logs = act00["logs"]
        print(f"✓ Found {len(jp_logs)} logs for act_00")
        if len(jp_logs) > 0:
            print("Sample JP logs:")
            for log in jp_logs[:5]:
                print(f"  - {log['description']} ({log['start_date']})")
    else:
        print(f"✗ Failed to get activities: {activities_resp.text}")

    # Step 7: Switch back to US
    print("\n7. Switching back to US...")
    update_resp = requests.put(
        f"{api_url}/api/v1/accounts/{account_id}",
        json={
            "account_id": account_id,
            "account_name": "japan test",
            "organization_id": "org_ken_e",
            "user_id": "user123",
            "region": ["US"],
        },
    )
    if update_resp.status_code == 200:
        print("✓ Region set back to US")
    else:
        print(f"✗ Failed to set region: {update_resp.text}")
        return

    # Step 8: Sync again for US
    print("\n8. Syncing holidays for US again...")
    sync_resp = requests.post(
        f"{api_url}/api/v1/activities/logs/sync", params={"account_id": account_id}
    )
    if sync_resp.status_code == 200:
        data = sync_resp.json()["data"]
        print("Results:")
        print(f"  - Regions: {data['regions']}")
        print(f"  - Total holidays in BigQuery: {data['total_holidays_in_bigquery']}")
        print(f"  - Existing logs before sync: {data['existing_logs_before_sync']}")
        print(f"  - New logs created: {data['new_logs_created']}")
        print(f"  - Logs deleted: {data['logs_deleted']}")
        print(f"  - Logs protected: {data['logs_protected_from_deletion']}")
    else:
        print(f"✗ Sync failed: {sync_resp.text}")

    # Final check
    print("\n9. Final check...")
    activities_resp = requests.get(
        f"{api_url}/api/v1/activities/", params={"account_id": account_id}
    )
    if activities_resp.status_code == 200:
        activities = activities_resp.json()["activities"]
        act00 = [a for a in activities if a["id"] == "act_00"][0]
        final_logs = act00["logs"]
        print(f"✓ Final log count: {len(final_logs)}")


if __name__ == "__main__":
    test_region_switch()
