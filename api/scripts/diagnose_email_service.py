"""Diagnostic script to check email service configuration.

Usage:
    python api/scripts/diagnose_email_service.py

    Or from project root:
    cd api && python scripts/diagnose_email_service.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Load .env file before importing any modules
from dotenv import load_dotenv

# Load from api/.env (works whether running from api/ or scripts/)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from src.kene_api.email_service import EmailService

print("=" * 80)
print("Email Service Diagnostic")
print("=" * 80)
print()
print(f".env file location: {env_path}")
print(f".env file exists: {env_path.exists()}")
print()

# Check environment variables
print("1. Environment Variables")
print("-" * 80)
gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
print(f"GOOGLE_CLOUD_PROJECT: {gcp_project if gcp_project else '✗ NOT SET'}")
if gcp_project:
    print("  - Will be used for Secret Manager lookups")
else:
    print("  ⚠️  WARNING: Required for Secret Manager (sm://) resolution")
print()
api_key = os.getenv("SENDGRID_API_KEY", "")
from_email = os.getenv("EMAIL_FROM_ADDRESS", "noreply@ken-e.ai")
from_name = os.getenv("EMAIL_FROM_NAME", "KEN-E Team")
app_base_url = os.getenv("APP_BASE_URL", "http://localhost:8080")

print(f"SENDGRID_API_KEY: {'✓ Set' if api_key else '✗ NOT SET'}")
if api_key:
    if api_key.startswith("sm://"):
        print("  - Format: Secret Manager reference")
        print(f"  - Secret path: {api_key}")
        print(
            f"  - Will attempt to fetch from Secret Manager using project: {gcp_project or 'ken-e-dev (default)'}"
        )
        # Try to fetch the actual secret
        try:
            from shared.secrets import get_env_or_secret

            actual_key = get_env_or_secret("SENDGRID_API_KEY")
            if actual_key and actual_key.startswith("SG."):
                print("  - ✓ Successfully fetched secret from Secret Manager")
                print(f"  - Actual key starts with: {actual_key[:10]}...")
            elif actual_key:
                print("  - ⚠️  Fetched value but doesn't start with 'SG.'")
                print(
                    f"  - Starts with: {actual_key[:10] if len(actual_key) > 10 else actual_key}"
                )
            else:
                print("  - ✗ Failed to fetch secret from Secret Manager")
        except Exception as e:
            print(f"  - ✗ Error fetching secret: {e}")
    else:
        print("  - Format: Direct API key")
        print(f"  - Length: {len(api_key)} characters")
        print(f"  - Starts with 'SG.': {api_key.startswith('SG.')}")
        print(
            f"  - Preview: {api_key[:10]}..."
            if len(api_key) > 10
            else f"  - Value: {api_key}"
        )
else:
    print("  ⚠️  WARNING: SendGrid API key is not set!")
    print("  Set it with: export SENDGRID_API_KEY='your-key-here'")

print(f"EMAIL_FROM_ADDRESS: {from_email}")
print(f"EMAIL_FROM_NAME: {from_name}")
print(f"APP_BASE_URL: {app_base_url}")
print()

# Initialize email service
print("2. Email Service Initialization")
print("-" * 80)
try:
    email_service = EmailService()
    email_service._ensure_initialized()

    if email_service.client:
        print("✓ Email service initialized successfully")
        print(f"  - Client type: {type(email_service.client).__name__}")
        print(f"  - From email: {email_service.from_email}")
        print(f"  - From name: {email_service.from_name}")
        print(f"  - App base URL: {email_service.app_base_url}")
    else:
        print("✗ Email service client is None")
        if not api_key:
            print("  ⚠️  Reason: SendGrid API key not configured")
        else:
            print("  ⚠️  Reason: Failed to initialize SendGrid client (check API key)")
except Exception as e:
    print(f"✗ Error initializing email service: {e}")
    import traceback

    traceback.print_exc()

print()
print("=" * 80)
print("Diagnostic Summary")
print("=" * 80)

if not api_key:
    print("❌ ISSUE FOUND: SendGrid API key is not configured")
    print()
    print("To fix:")
    print(
        "1. Get your SendGrid API key from https://app.sendgrid.com/settings/api_keys"
    )
    print("2. Set it as an environment variable:")
    print("   export SENDGRID_API_KEY='SG.your-key-here'")
    print("3. Or add it to your .env file")
    print("4. Restart the API server")
elif not api_key.startswith("SG.") and not api_key.startswith("sm://"):
    print("⚠️  WARNING: SendGrid API key doesn't have expected format")
    print("SendGrid API keys should start with 'SG.' or 'sm://' for Secret Manager")
    print("Double-check your API key is correct")
elif not email_service.client:
    print("❌ ISSUE FOUND: SendGrid client failed to initialize")
    print("Check the logs above for error details")
else:
    print("✅ Email service appears to be configured correctly")
    print()
    print("If invitations still aren't being sent, check:")
    print("1. SendGrid account status (not suspended)")
    print("2. API key has 'Mail Send' permission")
    print("3. API logs for email send attempts")
    print()
    print("Check logs with: grep -i 'invitation email' <your-api-log-file>")

print("=" * 80)
