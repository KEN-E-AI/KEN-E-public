#!/usr/bin/env python3
"""Test script to diagnose SendGrid email invitation issues."""

import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from src.kene_api.email_service import EmailService

from shared.secrets import get_env_or_secret


def test_sendgrid_configuration():
    """Test SendGrid configuration and connection."""

    # Load staging environment
    env_file = Path(__file__).parent.parent / ".env.staging"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"Loaded environment from {env_file}")
    else:
        logger.error(f"Environment file not found: {env_file}")
        return False

    # Set the project ID for secret manager
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"

    # Test 1: Check if SendGrid API key is configured
    sendgrid_api_key_env = os.getenv("SENDGRID_API_KEY")
    logger.info(
        f"SENDGRID_API_KEY env var: {sendgrid_api_key_env[:50]}..."
        if sendgrid_api_key_env
        else "NOT SET"
    )

    # Test 2: Try to fetch the actual API key
    try:
        api_key = get_env_or_secret("SENDGRID_API_KEY")
        if api_key:
            logger.info(
                f"Successfully retrieved SendGrid API key (length: {len(api_key)})"
            )
            # Check if it looks like a valid SendGrid API key
            if api_key.startswith("SG."):
                logger.info("✓ API key has correct SendGrid format (starts with 'SG.')")
            else:
                logger.warning("⚠ API key doesn't have expected SendGrid format")
        else:
            logger.error("✗ Failed to retrieve SendGrid API key")
            return False
    except Exception as e:
        logger.error(f"✗ Error retrieving SendGrid API key: {e}")
        return False

    # Test 3: Check other email configuration
    from_email = os.getenv("EMAIL_FROM_ADDRESS", "noreply@ken-e.ai")
    from_name = os.getenv("EMAIL_FROM_NAME", "KEN-E Team")
    app_base_url = os.getenv("APP_BASE_URL", "http://localhost:8080")

    logger.info(f"FROM_EMAIL: {from_email}")
    logger.info(f"FROM_NAME: {from_name}")
    logger.info(f"APP_BASE_URL: {app_base_url}")

    # Test 4: Initialize EmailService
    try:
        email_service = EmailService()
        if email_service.client:
            logger.info("✓ SendGrid client successfully initialized")
        else:
            logger.error("✗ SendGrid client not initialized (API key might be missing)")
            return False
    except Exception as e:
        logger.error(f"✗ Error initializing EmailService: {e}")
        return False

    return True


def test_send_invitation():
    """Test sending an actual invitation email."""

    # Load staging environment
    env_file = Path(__file__).parent.parent / ".env.staging"
    load_dotenv(env_file, override=True)
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"

    # Initialize email service
    email_service = EmailService()

    if not email_service.client:
        logger.error("Cannot test sending - SendGrid client not initialized")
        return False

    # Test sending to a test email (you can change this to your email)
    test_email = "test@example.com"  # Change this to a real email for testing

    logger.info(f"Attempting to send test invitation to {test_email}")

    try:
        result = email_service.send_invitation_email(
            to_email=test_email,
            inviter_name="Test User",
            organization_name="Test Organization",
            access_level="admin",
            invitation_token="test-token-12345",
        )

        if result:
            logger.info("✓ Email sent successfully!")
        else:
            logger.error("✗ Email sending failed (returned False)")

        return result

    except Exception as e:
        logger.error(f"✗ Exception while sending email: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_google_cloud_auth():
    """Check Google Cloud authentication."""
    try:
        from google.auth import default

        credentials, project = default()
        logger.info(f"✓ Google Cloud authentication successful. Project: {project}")
        return True
    except Exception as e:
        logger.error(f"✗ Google Cloud authentication failed: {e}")
        logger.info("Run 'gcloud auth application-default login' to authenticate")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SendGrid Email Invitation Diagnostic Test")
    print("=" * 60 + "\n")

    # Check Google Cloud auth first
    print("1. Checking Google Cloud authentication...")
    if not check_google_cloud_auth():
        print("\nPlease authenticate with Google Cloud first.")
        sys.exit(1)

    print("\n2. Testing SendGrid configuration...")
    if not test_sendgrid_configuration():
        print("\nSendGrid configuration test failed.")
        sys.exit(1)

    print("\n3. Test sending an email? (y/n): ", end="")
    response = input().strip().lower()

    if response == "y":
        print("Enter test email address: ", end="")
        test_email = input().strip()

        if test_email and "@" in test_email:
            # Override the test email in the function
            import src.kene_api.email_service

            original_send = (
                src.kene_api.email_service.EmailService.send_invitation_email
            )

            def send_with_test_email(self, to_email, *args, **kwargs):
                return original_send(self, test_email, *args, **kwargs)

            src.kene_api.email_service.EmailService.send_invitation_email = (
                send_with_test_email
            )

            print(f"\nSending test invitation to {test_email}...")
            if test_send_invitation():
                print(
                    f"\n✓ Test completed successfully! Check {test_email} for the invitation."
                )
            else:
                print("\n✗ Test failed. Check the logs above for details.")
        else:
            print("Invalid email address.")

    print("\n" + "=" * 60)
    print("Diagnostic test completed")
    print("=" * 60 + "\n")
