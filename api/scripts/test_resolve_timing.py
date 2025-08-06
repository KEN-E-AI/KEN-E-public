#!/usr/bin/env python3
"""Test script to identify timing bottleneck in resolve_secrets.py"""

import time
import sys
import os
from pathlib import Path

overall_start = time.time()

print("Starting secret resolution timing test...")

# Time the import
import_start = time.time()
from google.cloud import secretmanager
from google.api_core import exceptions
print(f"Import time: {time.time() - import_start:.2f}s")

# Time client creation
client_start = time.time()
client = secretmanager.SecretManagerServiceClient()
print(f"Client creation time: {time.time() - client_start:.2f}s")

# Test accessing secrets
secrets_to_test = [
    "projects/391472102753/secrets/neo4j-password/versions/latest",
    "projects/391472102753/secrets/superset-password/versions/latest",
    "projects/391472102753/secrets/sendgrid-api-key/versions/latest",
    "projects/391472102753/secrets/recaptcha-site-key/versions/latest",
    "projects/391472102753/secrets/recaptcha-secret-key/versions/latest",
]

total_secret_time = 0
for i, secret_path in enumerate(secrets_to_test, 1):
    secret_start = time.time()
    try:
        response = client.access_secret_version(request={"name": secret_path})
        secret_value = response.payload.data.decode("UTF-8")
        secret_time = time.time() - secret_start
        total_secret_time += secret_time
        print(f"Secret {i}: {secret_time:.2f}s")
    except Exception as e:
        print(f"Secret {i} failed: {e}")

print(f"\nTotal time for {len(secrets_to_test)} secrets: {total_secret_time:.2f}s")
print(f"Overall script time: {time.time() - overall_start:.2f}s")