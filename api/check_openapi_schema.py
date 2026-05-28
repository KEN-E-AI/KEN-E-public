#!/usr/bin/env python3
"""Check the OpenAPI schema for the accounts endpoint."""

import json

import requests

try:
    response = requests.get("http://localhost:8000/openapi.json")
    if response.status_code == 200:
        openapi = response.json()

        # Find the schema reference
        schema_ref = "Body_create_account_api_v1_accounts__post"
        schemas = openapi.get("components", {}).get("schemas", {})

        if schema_ref in schemas:
            print(f"Schema for {schema_ref}:")
            print(json.dumps(schemas[schema_ref], indent=2))
        else:
            print(f"Schema {schema_ref} not found")
            print("\nAvailable schemas:")
            for key in schemas.keys():
                if "account" in key.lower() or "body" in key.lower():
                    print(f"  - {key}")
except Exception as e:
    print(f"Error: {e}")
