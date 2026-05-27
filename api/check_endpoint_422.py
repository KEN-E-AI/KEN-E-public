#!/usr/bin/env python3
"""Test to diagnose the 422 error."""

import json

import requests

# Test without auth to see the endpoint structure
url = "http://localhost:8000/api/v1/accounts/"

# Test 1: Check what the endpoint expects
print("=== Checking OpenAPI Schema ===")
openapi_response = requests.get("http://localhost:8000/openapi.json")
if openapi_response.status_code == 200:
    openapi = openapi_response.json()
    accounts_post = (
        openapi.get("paths", {}).get("/api/v1/accounts/", {}).get("post", {})
    )
    if accounts_post:
        print("POST /api/v1/accounts/ request body:")
        request_body = accounts_post.get("requestBody", {})
        print(json.dumps(request_body, indent=2))

        # Get the schema details
        if "content" in request_body:
            for content_type, content in request_body["content"].items():
                print(f"\nContent-Type: {content_type}")
                if "schema" in content and "$ref" in content["schema"]:
                    ref = content["schema"]["$ref"].split("/")[-1]
                    schema = openapi["components"]["schemas"].get(ref, {})
                    print(f"Required fields: {schema.get('required', [])}")
                    for field, details in schema.get("properties", {}).items():
                        print(f"  - {field}: {details.get('type', details)}")

print("\n=== Testing with curl command ===")
print("""
Try this curl command to test directly:

curl -X POST http://localhost:8000/api/v1/accounts/ \\
  -F "account_name=Test Account" \\
  -F "organization_id=test-org" \\
  -F "industry=Technology" \\
  -F "status=Active" \\
  -F 'websites=["https://example.com"]' \\
  -F "timezone=America/New_York" \\
  -v
  
This should return 401 (unauthorized) if the endpoint is working correctly.
If it returns 422, there's a validation issue.
""")
