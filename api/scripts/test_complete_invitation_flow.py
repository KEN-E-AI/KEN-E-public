#!/usr/bin/env python3
"""Test the complete invitation email flow with detailed diagnostics."""

import os
import sys
import logging
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_local_invitation():
    """Test invitation flow locally."""
    
    logger.info("="*60)
    logger.info("Testing Local Invitation Flow")
    logger.info("="*60)
    
    # Load staging environment for testing
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.staging"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"Loaded environment from {env_file}")
    
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"
    
    # Import the email service
    from src.kene_api.email_service import EmailService
    
    # Create a fresh instance
    email_service = EmailService()
    
    # Test sending an invitation
    test_email = input("\nEnter email address to send test invitation (or press Enter to skip): ").strip()
    
    if test_email and '@' in test_email:
        logger.info(f"\nSending test invitation to {test_email}...")
        
        result = email_service.send_invitation_email(
            to_email=test_email,
            inviter_name="Test Admin",
            organization_name="Test Organization",
            access_level="admin",
            invitation_token="test-token-" + str(os.getpid())
        )
        
        if result:
            logger.info(f"✓ Email sent successfully to {test_email}")
            logger.info(f"  Check your inbox for the invitation")
        else:
            logger.error(f"✗ Failed to send email to {test_email}")
            logger.error(f"  Check the logs above for error details")
    
    return email_service


def check_deployed_api():
    """Check if the deployed API can send emails."""
    
    logger.info("\n" + "="*60)
    logger.info("Checking Deployed API Email Capability")
    logger.info("="*60)
    
    import requests
    
    # Test staging API
    staging_url = "https://kene-api-staging-391472102753.us-central1.run.app"
    
    try:
        # Check health
        health_response = requests.get(f"{staging_url}/health", timeout=5)
        if health_response.status_code == 200:
            logger.info(f"✓ Staging API is healthy")
        else:
            logger.warning(f"⚠ Staging API returned status {health_response.status_code}")
            
    except Exception as e:
        logger.error(f"✗ Could not reach staging API: {e}")


def check_environment_in_cloud_run():
    """Check what environment variables are set in Cloud Run."""
    
    logger.info("\n" + "="*60)
    logger.info("Environment Variables in Cloud Run")
    logger.info("="*60)
    
    # This would need to be run from within Cloud Run to be accurate
    # For now, we'll check what should be set based on our deployment config
    
    expected_vars = {
        'SENDGRID_API_KEY': 'projects/391472102753/secrets/sendgrid-api-key/versions/latest',
        'APP_BASE_URL': 'https://staging.app.ken-e.ai',
        'EMAIL_FROM_ADDRESS': 'noreply@ken-e.ai',
        'EMAIL_FROM_NAME': 'KEN-E Team'
    }
    
    logger.info("Expected environment variables in staging:")
    for var, value in expected_vars.items():
        logger.info(f"  {var}: {value}")
    
    logger.info("\nIf emails are not being sent, check that these are actually set in Cloud Run")


def test_sendgrid_api_directly():
    """Test SendGrid API directly with minimal setup."""
    
    logger.info("\n" + "="*60)
    logger.info("Direct SendGrid API Test")
    logger.info("="*60)
    
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.staging"
    load_dotenv(env_file, override=True)
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"

    from src.kene_api.utils.secrets import get_env_or_secret

    # Get the API key
    api_key = get_env_or_secret("SENDGRID_API_KEY")
    
    if not api_key:
        logger.error("Could not retrieve SendGrid API key")
        return
    
    logger.info(f"✓ Retrieved SendGrid API key (length: {len(api_key)})")
    
    # Try to send a test email directly
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    
    test_email = input("\nEnter email for direct SendGrid test (or press Enter to skip): ").strip()
    
    if test_email and '@' in test_email:
        try:
            sg = SendGridAPIClient(api_key)
            
            message = Mail(
                from_email='noreply@ken-e.ai',
                to_emails=test_email,
                subject='Direct SendGrid Test - KEN-E',
                html_content='<p>This is a direct test of SendGrid API.</p>'
            )
            
            response = sg.send(message)
            
            logger.info(f"✓ Email sent directly via SendGrid!")
            logger.info(f"  Status code: {response.status_code}")
            logger.info(f"  Message ID: {response.headers.get('X-Message-Id', 'N/A')}")
            
            if response.body:
                logger.info(f"  Response body: {response.body}")
                
        except Exception as e:
            logger.error(f"✗ Direct SendGrid test failed: {e}")
            if hasattr(e, 'body'):
                logger.error(f"  Error body: {e.body}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Complete Invitation Flow Test")
    print("="*60 + "\n")
    
    # Test different aspects
    check_deployed_api()
    check_environment_in_cloud_run()
    
    # Test SendGrid directly
    test_sendgrid_api_directly()
    
    # Test local invitation flow
    email_service = test_local_invitation()
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print("\nIf emails are not being sent in production/staging:")
    print("1. Check Cloud Run logs for error messages")
    print("2. Verify environment variables are set in Cloud Run")
    print("3. Check SendGrid Activity Feed for any blocks or suppressions")
    print("4. Ensure the sender domain (ken-e.ai) is verified in SendGrid")
    print("5. Check if the recipient email is on SendGrid's suppression list")
    print("\nTo check Cloud Run logs:")
    print("  gcloud logging read 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"kene-api-staging\" AND textPayload:\"SendGrid\"' --limit=50 --project=ken-e-staging")
    print("="*60)