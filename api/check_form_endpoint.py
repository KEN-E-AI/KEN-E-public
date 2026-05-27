#!/usr/bin/env python3
"""Test the accounts endpoint to diagnose 422 error."""

import json

import requests

# Test the endpoint structure
url = "http://localhost:8000/api/v1/accounts/"

# Create test form data
form_data = {
    "account_name": "Test Account",
    "organization_id": "test-org",
    "industry": "Technology",
    "status": "Active",
    "websites": json.dumps(["https://example.com"]),  # JSON string
    "timezone": "America/New_York",
    "data_region": "US",
}

# Create a dummy file
with open("/tmp/test.pdf", "wb") as f:
    f.write(b"%PDF-1.4\nTest\n%%EOF")

files = {"files": ("test.pdf", open("/tmp/test.pdf", "rb"), "application/pdf")}

print("Testing endpoint without auth (expect 401 or 403):")
print(f"URL: {url}")
print(f"Form data: {form_data}")

try:
    response = requests.post(url, data=form_data, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

    if response.status_code == 422:
        print("\n422 Validation Error Details:")
        try:
            error_detail = response.json()
            print(json.dumps(error_detail, indent=2))
        except:
            print(response.text)
except Exception as e:
    print(f"Error: {e}")

# Also test what the OpenAPI schema says
print("\n\nChecking OpenAPI schema for this endpoint:")
try:
    openapi_response = requests.get("http://localhost:8000/openapi.json")
    if openapi_response.status_code == 200:
        openapi = openapi_response.json()
        accounts_post = (
            openapi.get("paths", {}).get("/api/v1/accounts/", {}).get("post", {})
        )
        if accounts_post:
            print("POST /api/v1/accounts/ expects:")
            if "requestBody" in accounts_post:
                print(json.dumps(accounts_post["requestBody"], indent=2))
            else:
                print(
                    "Parameters:",
                    json.dumps(accounts_post.get("parameters", []), indent=2),
                )
except Exception as e:
    print(f"Could not fetch OpenAPI schema: {e}")
