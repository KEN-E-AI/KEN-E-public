#!/usr/bin/env python3
"""
Test script for full account creation flow with detailed timing logs.
This script will create an account and monitor the entire process.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime

import httpx

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_USER_TOKEN = os.getenv("TEST_USER_TOKEN", "")  # You'll need to set this

# Test data
TEST_ACCOUNT_DATA = {
    "account_name": f"Test Company {datetime.now().strftime('%Y%m%d_%H%M%S')}",
    "organization_id": "org_36e6691ccde243f1be1bdc9f61f59ec9",  # Use your test org ID
    "industry": "Technology",
    "status": "active",
    "websites": ["https://example.com"],
    "timezone": "America/New_York",
    "data_region": "US",
    "region": ["North America"],
    "marketing_channels": ["social_media", "email"],
    "product_integrations": ["google_ads"],
    "estimated_annual_ad_budget": 100000,
}


class AccountCreationTester:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        self.start_time = None
        self.account_id = None

    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp and duration."""
        timestamp = datetime.now().isoformat()
        if self.start_time:
            duration = time.time() - self.start_time
            print(f"[{timestamp}] [{level}] [+{duration:.1f}s] {message}")
        else:
            print(f"[{timestamp}] [{level}] {message}")

    async def create_account(self) -> str | None:
        """Create an account and return its ID."""
        self.log("Starting account creation...")
        self.start_time = time.time()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(1800.0)
        ) as client:  # 30 min timeout
            try:
                # Generate a unique account ID for tracking
                account_id = f"acc_{uuid.uuid4().hex[:32]}"
                data = {**TEST_ACCOUNT_DATA, "account_id": account_id}

                self.log(f"Creating account with ID: {account_id}")
                self.log(f"Account name: {data['account_name']}")
                self.log(f"Organization ID: {data['organization_id']}")

                response = await client.post(
                    f"{self.base_url}/api/v1/accounts/", json=data, headers=self.headers
                )

                if response.status_code == 200:
                    result = response.json()
                    self.account_id = result.get("account_id", account_id)
                    self.log(
                        f"Account created successfully: {self.account_id}", "SUCCESS"
                    )
                    return self.account_id
                else:
                    self.log(
                        f"Account creation failed: {response.status_code}", "ERROR"
                    )
                    self.log(f"Response: {response.text}", "ERROR")
                    return None

            except httpx.TimeoutException as e:
                duration = time.time() - self.start_time
                self.log(f"Request timed out after {duration:.1f} seconds", "ERROR")
                self.log(f"Timeout error: {e!s}", "ERROR")
                return None
            except Exception as e:
                self.log(f"Unexpected error: {e!s}", "ERROR")
                return None

    async def check_account_status(self, account_id: str) -> dict:
        """Check the status of account creation."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/accounts/{account_id}/creation-status",
                    headers=self.headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    self.log(f"Status check failed: {response.status_code}", "ERROR")
                    return {"status": "error", "message": response.text}

            except Exception as e:
                self.log(f"Status check error: {e!s}", "ERROR")
                return {"status": "error", "message": str(e)}

    async def monitor_account_creation(self, account_id: str, max_duration: int = 1800):
        """Monitor account creation progress for up to max_duration seconds."""
        self.log(
            f"Monitoring account creation for up to {max_duration / 60:.0f} minutes..."
        )

        check_interval = 30  # Check every 30 seconds
        checks_performed = 0

        while (time.time() - self.start_time) < max_duration:
            checks_performed += 1
            self.log(f"Status check #{checks_performed}")

            status = await self.check_account_status(account_id)

            if status.get("status") == "completed":
                self.log("Account creation completed!", "SUCCESS")
                self.log(f"Final status: {json.dumps(status, indent=2)}", "SUCCESS")
                return True
            elif status.get("status") == "failed":
                self.log("Account creation failed!", "ERROR")
                self.log(f"Error details: {json.dumps(status, indent=2)}", "ERROR")
                return False
            else:
                self.log(f"Current status: {status.get('status', 'unknown')}")
                if status.get("message"):
                    self.log(f"Message: {status.get('message')}")

            # Wait before next check
            await asyncio.sleep(check_interval)

        duration = time.time() - self.start_time
        self.log(f"Monitoring stopped after {duration:.1f} seconds", "WARNING")
        return False

    async def list_accounts(self, organization_id: str):
        """List accounts for the organization to trigger the potential timeout."""
        self.log("Fetching account list to test timeout behavior...")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(360.0)
        ) as client:  # 6 min timeout
            try:
                list_start = time.time()
                response = await client.get(
                    f"{self.base_url}/api/v1/accounts/?organization_id={organization_id}",
                    headers=self.headers,
                )

                list_duration = time.time() - list_start

                if response.status_code == 200:
                    accounts = response.json().get("accounts", [])
                    self.log(
                        f"Successfully fetched {len(accounts)} accounts in {list_duration:.1f}s",
                        "SUCCESS",
                    )

                    # Check if our new account is in the list
                    if self.account_id:
                        found = any(
                            acc.get("account_id") == self.account_id for acc in accounts
                        )
                        if found:
                            self.log(
                                f"New account {self.account_id} found in list",
                                "SUCCESS",
                            )
                        else:
                            self.log(
                                f"New account {self.account_id} NOT found in list",
                                "WARNING",
                            )
                else:
                    self.log(
                        f"List accounts failed: {response.status_code} after {list_duration:.1f}s",
                        "ERROR",
                    )

            except httpx.TimeoutException:
                list_duration = time.time() - list_start
                self.log(f"List accounts timed out after {list_duration:.1f}s", "ERROR")
                self.log("This is the 5-minute timeout issue!", "ERROR")
            except Exception as e:
                self.log(f"List accounts error: {e!s}", "ERROR")

    async def run_full_test(self):
        """Run the complete account creation test flow."""
        self.log("=" * 60)
        self.log("ACCOUNT CREATION FLOW TEST")
        self.log("=" * 60)

        # Step 1: Create account
        account_id = await self.create_account()
        if not account_id:
            self.log("Account creation failed, stopping test", "ERROR")
            return

        # Step 2: Monitor creation progress
        await self.monitor_account_creation(account_id)

        # Step 3: Try to list accounts (this might trigger the 5-minute timeout)
        await self.list_accounts(TEST_ACCOUNT_DATA["organization_id"])

        # Final summary
        total_duration = time.time() - self.start_time
        self.log("=" * 60)
        self.log(
            f"TEST COMPLETED - Total duration: {total_duration:.1f}s ({total_duration / 60:.1f} minutes)"
        )
        self.log("=" * 60)


async def main():
    """Main test runner."""
    # Check if we have an auth token
    if not TEST_USER_TOKEN:
        print("ERROR: Please set TEST_USER_TOKEN environment variable")
        print("You can get this from your browser's dev tools after logging in")
        return

    tester = AccountCreationTester(API_BASE_URL, TEST_USER_TOKEN)
    await tester.run_full_test()


if __name__ == "__main__":
    print("Starting Account Creation Flow Test")
    print(f"API URL: {API_BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    print("-" * 60)

    asyncio.run(main())
