#!/usr/bin/env python3
"""Verify sync functionality works as expected."""

import sys

import requests


def verify_sync():
    """Verify the complete sync workflow."""
    api_url = "http://localhost:8000"
    account_id = "acc_adf3a803fe294ae4af0f8bc3ad3218fa"

    print("SYNC FUNCTIONALITY VERIFICATION")
    print("=" * 50)

    # Step 1: Set region to JP
    print("\n1. Setting region to JP...")
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
        return False

    # Step 2: Sync holidays
    print("\n2. Syncing holidays for JP...")
    sync_resp = requests.post(
        f"{api_url}/api/v1/activities/logs/sync", params={"account_id": account_id}
    )
    if sync_resp.status_code == 200:
        data = sync_resp.json()["data"]
        print(f"✓ Created {data['new_logs_created']} logs")
        jp_logs_count = data["new_logs_created"]
    else:
        print(f"✗ Sync failed: {sync_resp.text}")
        return False

    # Step 3: Verify logs exist
    print("\n3. Verifying logs exist...")
    activities_resp = requests.get(
        f"{api_url}/api/v1/activities/", params={"account_id": account_id}
    )
    if activities_resp.status_code == 200:
        activities = activities_resp.json()["activities"]
        act00 = [a for a in activities if a["id"] == "act_00"][0]
        print(f"✓ Found {len(act00['logs'])} logs for act_00")
    else:
        print(f"✗ Failed to get activities: {activities_resp.text}")
        return False

    # Step 4: Change region to AE
    print("\n4. Changing region to AE...")
    update_resp = requests.put(
        f"{api_url}/api/v1/accounts/{account_id}",
        json={
            "account_id": account_id,
            "account_name": "japan test",
            "organization_id": "org_ken_e",
            "user_id": "user123",
            "region": ["AE"],
        },
    )
    if update_resp.status_code == 200:
        print("✓ Region set to AE")
    else:
        print(f"✗ Failed to set region: {update_resp.text}")
        return False

    # Step 5: Sync to delete logs
    print("\n5. Syncing holidays for AE (should delete JP logs)...")
    sync_resp = requests.post(
        f"{api_url}/api/v1/activities/logs/sync", params={"account_id": account_id}
    )
    if sync_resp.status_code == 200:
        data = sync_resp.json()["data"]
        print(f"✓ Deleted {data['logs_deleted']} logs")
        print(f"✓ Protected {data['logs_protected_from_deletion']} logs")
    else:
        print(f"✗ Sync failed: {sync_resp.text}")
        return False

    # Step 6: Verify logs are gone
    print("\n6. Verifying logs are deleted...")
    activities_resp = requests.get(
        f"{api_url}/api/v1/activities/", params={"account_id": account_id}
    )
    if activities_resp.status_code == 200:
        activities = activities_resp.json()["activities"]
        act00 = [a for a in activities if a["id"] == "act_00"][0]
        print(f"✓ Found {len(act00['logs'])} logs for act_00 (should be 0)")

        if len(act00["logs"]) == 0:
            print("\n✅ SYNC FUNCTIONALITY VERIFIED SUCCESSFULLY!")
            return True
        else:
            print("\n❌ VERIFICATION FAILED: Logs were not deleted")
            return False
    else:
        print(f"✗ Failed to get activities: {activities_resp.text}")
        return False


if __name__ == "__main__":
    try:
        success = verify_sync()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
