#!/usr/bin/env python3
"""Test account creation with file upload."""

import json
import requests
import sys

# Get auth token (you'll need to provide this)
if len(sys.argv) > 1:
    token = sys.argv[1]
else:
    print("Usage: python test_account_creation_with_file.py <auth_token>")
    print("Get auth token from browser DevTools > Network tab > Request Headers > Authorization")
    sys.exit(1)

# Create test form data
form_data = {
    "account_name": "Test Account with File",
    "organization_id": "healthway",  # Use an existing org
    "industry": "Technology", 
    "status": "Active",
    "websites": json.dumps(["https://example.com"]),
    "timezone": "America/New_York",
    "data_region": "US"
}

# Create a test PDF file
with open("/tmp/test_strategy.pdf", "wb") as f:
    f.write(b"%PDF-1.4\n")
    f.write(b"1 0 obj\n<< /Type /Catalog >>\nendobj\n")
    f.write(b"%%EOF\n")

files = {
    "files": ("test_strategy.pdf", open("/tmp/test_strategy.pdf", "rb"), "application/pdf")
}

headers = {
    "Authorization": f"Bearer {token}"
}

print("Testing account creation with file upload...")
print(f"Form data: {form_data}")

response = requests.post(
    "http://localhost:8000/api/v1/accounts/",
    data=form_data,
    files=files,
    headers=headers
)

print(f"\nStatus: {response.status_code}")
if response.status_code == 200 or response.status_code == 201:
    print("✅ Success! Account created with file upload")
    result = response.json()
    print(f"Account ID: {result.get('account_id')}")
elif response.status_code == 422:
    print("❌ Validation error:")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Response: {response.text[:500]}")