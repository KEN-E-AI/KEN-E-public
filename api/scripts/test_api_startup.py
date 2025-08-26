#!/usr/bin/env python3
"""Test that API can start even when Secret Manager fails."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment to simulate Cloud Run with Secret Manager path
os.environ["SENDGRID_API_KEY"] = "projects/391472102753/secrets/sendgrid-api-key/versions/latest"

# Remove any service account credentials to force failure
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

print("Testing API module imports with simulated Secret Manager failure...")

try:
    # Try to import the main API module
    from src.kene_api import main
    print("✅ Successfully imported main API module")
    
    # Try to import the email service
    from src.kene_api.email_service import EmailService, get_email_service
    print("✅ Successfully imported email service")
    
    # Try to get the email service instance
    email_service = get_email_service()
    print(f"✅ Got email service instance: {email_service}")
    
    # Check that it's in a degraded state (no client)
    email_service._ensure_initialized()
    if email_service.client is None:
        print("✅ Email service correctly in degraded mode (client is None)")
    else:
        print("❌ Email service unexpectedly has a client")
    
    # Try to import the firestore router that uses email service
    from src.kene_api.routers import firestore
    print("✅ Successfully imported firestore router")
    
    print("\n🎉 All imports successful! API should be able to start even with Secret Manager failures.")
    
except Exception as e:
    print(f"❌ Failed to import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)