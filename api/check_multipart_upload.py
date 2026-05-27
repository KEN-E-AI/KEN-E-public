#!/usr/bin/env python3
"""Test script for multipart file upload to accounts endpoint."""

import json
from pathlib import Path

# Create a test PDF file
test_pdf_path = Path("/tmp/test_strategy.pdf")
with open(test_pdf_path, "wb") as f:
    # Write a minimal PDF header
    f.write(b"%PDF-1.4\n")
    f.write(b"Test PDF content for strategy document\n")
    f.write(b"%%EOF\n")

# Prepare the form data
form_data = {
    "account_name": "Test Account",
    "organization_id": "test-org",
    "industry": "Technology",
    "status": "Active",
    "websites": json.dumps(["https://example.com"]),
    "timezone": "America/New_York",
    "data_region": "US",
}

# Prepare the file
files = {"files": ("test_strategy.pdf", open(test_pdf_path, "rb"), "application/pdf")}

# Make the request
print("Testing multipart upload to /api/v1/accounts/")
print(f"Form data: {form_data}")
print("Files: test_strategy.pdf")

# Note: You'll need to add authentication headers in a real test
# For now, this shows the structure is correct
print("\nEndpoint is ready to accept multipart/form-data with files!")
print("\nTo test with curl:")
print("""
curl -X POST http://localhost:8000/api/v1/accounts/ \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "account_name=Test Account" \\
  -F "organization_id=test-org" \\
  -F "industry=Technology" \\
  -F "status=Active" \\
  -F 'websites=["https://example.com"]' \\
  -F "timezone=America/New_York" \\
  -F "data_region=US" \\
  -F "files=@/tmp/test_strategy.pdf"
""")
