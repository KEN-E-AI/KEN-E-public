#!/usr/bin/env python3
"""Test the complete invitation flow through the API."""

import json

import requests

# API configuration
API_BASE_URL = "http://localhost:8000"


def test_invitation_api():
    """Test sending an invitation through the API endpoint."""

    # First, we need to get an auth token
    # For testing, we'll use a test account or you can provide a real token

    print("Testing Invitation API Endpoint")
    print("=" * 60)

    # Check if API is running
    try:
        health_response = requests.get(f"{API_BASE_URL}/health")
        if health_response.status_code == 200:
            print("✓ API is running and healthy")
        else:
            print("✗ API health check failed")
            return
    except Exception as e:
        print(f"✗ Cannot connect to API at {API_BASE_URL}: {e}")
        return

    print("\nTo test the invitation flow, we need:")
    print("1. A valid Firebase auth token")
    print("2. An account ID where you have admin access")
    print("\nYou can get these from the browser developer tools while logged in:")
    print("- Auth token: Look in Network tab for 'Authorization' header")
    print("- Account ID: Look in the URL or API calls for account_id parameter")

    auth_token = input("\nEnter Firebase auth token (or 'skip' to exit): ").strip()
    if auth_token.lower() == "skip":
        print("Skipping API test")
        return

    account_id = input("Enter account ID: ").strip()
    test_email = input("Enter email to invite: ").strip()

    if not all([auth_token, account_id, test_email]):
        print("Missing required information")
        return

    # Prepare the invitation request
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    invitation_data = {
        "email": test_email,
        "access_level": "view",  # or "admin"
    }

    print(f"\nSending invitation to {test_email}...")
    print(f"Account ID: {account_id}")
    print(f"Access Level: {invitation_data['access_level']}")

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/firestore/invitations/{account_id}",
            headers=headers,
            json=invitation_data,
        )

        print(f"\nResponse Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✓ Invitation created successfully!")
            print(f"Response: {json.dumps(result, indent=2)}")

            if result.get("email_sent"):
                print(f"\n✓ Email was sent to {test_email}")
            else:
                print("\n⚠ Invitation created but email was NOT sent")
                print("  This is the issue - SendGrid is failing to send")
        else:
            print("✗ Failed to create invitation")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"✗ Error calling API: {e}")


if __name__ == "__main__":
    test_invitation_api()
