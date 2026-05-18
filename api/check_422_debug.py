#!/usr/bin/env python3
"""Debug the 422 error by making a test request."""

import requests
import json

# Test what the actual validation error is
url = "http://localhost:8000/api/v1/accounts/"

# Simulate what the frontend is sending (likely still with Content-Type: application/json)
headers = {
    "Content-Type": "application/json",  # This is what the old frontend code sends
    "Authorization": "Bearer dummy"  # Dummy token to get past auth
}

data = {
    "account_name": "Test",
    "organization_id": "test",
    "industry": "Tech",
    "status": "Active",
    "websites": ["https://example.com"],
    "timezone": "UTC"
}

print("Testing with JSON content type (old frontend behavior):")
response = requests.post(url, json=data, headers=headers)
print(f"Status: {response.status_code}")
if response.status_code == 422:
    print("Validation error details:")
    print(json.dumps(response.json(), indent=2))
    
print("\n" + "="*50 + "\n")

# Now test with form data (what it should be)
print("Testing with multipart/form-data (new expected behavior):")
form_data = {
    "account_name": "Test",
    "organization_id": "test", 
    "industry": "Tech",
    "status": "Active",
    "websites": json.dumps(["https://example.com"]),
    "timezone": "UTC"
}

response2 = requests.post(url, data=form_data)
print(f"Status: {response2.status_code}")
if response2.status_code != 200 and response2.status_code != 201:
    print(f"Response: {response2.text[:200]}")