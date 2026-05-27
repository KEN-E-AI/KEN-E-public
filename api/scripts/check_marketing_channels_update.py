#!/usr/bin/env python3
"""Test script to verify marketing channels are properly updated in accounts."""

import asyncio
from pathlib import Path

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account


async def test_marketing_channels_update():
    """Test updating marketing channels for an account."""

    # Get service account credentials for authentication
    sa_path = Path(__file__).parent.parent / "ken-e-dev-sa.json"
    if not sa_path.exists():
        print(f"Service account file not found at {sa_path}")
        return

    credentials = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())

    # API configuration
    api_base_url = "http://localhost:8000"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # 1. First, get all accounts to find one to test with
        print("\n1. Fetching accounts...")
        response = await client.get(f"{api_base_url}/api/v1/accounts/", headers=headers)

        if response.status_code != 200:
            print(f"Failed to get accounts: {response.status_code}")
            print(response.text)
            return

        accounts_data = response.json()
        accounts = accounts_data.get("accounts", [])

        if not accounts:
            print("No accounts found")
            return

        # Use the first account for testing
        test_account = accounts[0]
        account_id = test_account["account_id"]
        print(f"Testing with account: {account_id} ({test_account['account_name']})")
        print(
            f"Current marketing channels: {test_account.get('marketing_channels', [])}"
        )

        # 2. Update the account with marketing channels
        print("\n2. Updating account with marketing channels...")
        update_data = {
            "marketing_channels": ["Email", "Social Media", "SEO", "Paid Search"],
            "product_integrations": ["Google Analytics", "Slack"],
        }

        response = await client.put(
            f"{api_base_url}/api/v1/accounts/{account_id}",
            headers=headers,
            json=update_data,
        )

        if response.status_code != 200:
            print(f"Failed to update account: {response.status_code}")
            print(response.text)
            return

        updated_account = response.json()
        print(
            f"Updated marketing channels: {updated_account.get('marketing_channels', [])}"
        )
        print(
            f"Updated product integrations: {updated_account.get('product_integrations', [])}"
        )

        # 3. Fetch the account again to verify the changes persisted
        print("\n3. Fetching account again to verify...")
        response = await client.get(
            f"{api_base_url}/api/v1/accounts/{account_id}", headers=headers
        )

        if response.status_code != 200:
            print(f"Failed to get account: {response.status_code}")
            print(response.text)
            return

        verified_account = response.json()
        print(
            f"Verified marketing channels: {verified_account.get('marketing_channels', [])}"
        )
        print(
            f"Verified product integrations: {verified_account.get('product_integrations', [])}"
        )

        # Check if the update was successful
        if (
            verified_account.get("marketing_channels")
            == update_data["marketing_channels"]
        ):
            print(
                "\n✅ SUCCESS: Marketing channels were properly updated and persisted!"
            )
        else:
            print("\n❌ FAILED: Marketing channels were not properly updated")
            print(f"Expected: {update_data['marketing_channels']}")
            print(f"Got: {verified_account.get('marketing_channels', [])}")


if __name__ == "__main__":
    asyncio.run(test_marketing_channels_update())
