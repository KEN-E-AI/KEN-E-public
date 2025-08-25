#!/usr/bin/env python3
"""Debug script to test sending invitation emails and identify issues."""

import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from src.kene_api.email_service import EmailService


def main():
    # Load staging environment
    env_file = Path(__file__).parent.parent / ".env.staging"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"Loaded environment from {env_file}")
    
    # Set project ID
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"
    
    # Check critical environment variables
    logger.info("=" * 60)
    logger.info("Environment Variables:")
    logger.info("=" * 60)
    
    sendgrid_key = os.getenv("SENDGRID_API_KEY", "NOT SET")
    app_base_url = os.getenv("APP_BASE_URL", "NOT SET")
    email_from = os.getenv("EMAIL_FROM_ADDRESS", "NOT SET")
    email_from_name = os.getenv("EMAIL_FROM_NAME", "NOT SET")
    
    logger.info(f"SENDGRID_API_KEY: {'SET (Secret Manager path)' if sendgrid_key.startswith('projects/') else sendgrid_key[:20] if sendgrid_key != 'NOT SET' else 'NOT SET'}")
    logger.info(f"APP_BASE_URL: {app_base_url}")
    logger.info(f"EMAIL_FROM_ADDRESS: {email_from}")
    logger.info(f"EMAIL_FROM_NAME: {email_from_name}")
    
    # Check defaults used by EmailService
    logger.info("\n" + "=" * 60)
    logger.info("EmailService Default Values:")
    logger.info("=" * 60)
    
    # Initialize email service
    email_service = EmailService()
    
    logger.info(f"from_email (actual): {email_service.from_email}")
    logger.info(f"from_name (actual): {email_service.from_name}")
    logger.info(f"app_base_url (actual): {email_service.app_base_url}")
    logger.info(f"SendGrid client initialized: {email_service.client is not None}")
    
    if email_service.client:
        logger.info("✓ SendGrid client is ready")
    else:
        logger.error("✗ SendGrid client is NOT initialized - emails cannot be sent!")
        return
    
    # Generate a test invitation URL
    test_token = "test-token-123456"
    invitation_url = f"{email_service.app_base_url}/auth/signin?invitation={test_token}"
    
    logger.info("\n" + "=" * 60)
    logger.info("Test Invitation Details:")
    logger.info("=" * 60)
    logger.info(f"Invitation URL that would be sent: {invitation_url}")
    
    # Check if we should use staging URL
    if email_service.app_base_url == "http://localhost:8080":
        logger.warning("⚠ APP_BASE_URL is using localhost - recipients will get a localhost link!")
        logger.info("  For staging, should be: https://staging.app.ken-e.ai")
    
    # Try to send a test email
    logger.info("\n" + "=" * 60)
    logger.info("Test Email Sending:")
    logger.info("=" * 60)
    
    test_email = input("Enter email address to send test invitation (or press Enter to skip): ").strip()
    
    if test_email and '@' in test_email:
        logger.info(f"Attempting to send invitation to {test_email}...")
        
        try:
            result = email_service.send_invitation_email(
                to_email=test_email,
                inviter_name="Test Admin",
                organization_name="Test Organization",
                access_level="admin",
                invitation_token=test_token
            )
            
            if result:
                logger.info(f"✓ Email sent successfully to {test_email}!")
                logger.info(f"  Check inbox for email with subject: You've been invited to join Test Organization on KEN-E")
                logger.info(f"  Invitation URL in email: {invitation_url}")
            else:
                logger.error("✗ Email sending failed (returned False)")
                logger.error("  This usually means SendGrid rejected the request")
                
        except Exception as e:
            logger.error(f"✗ Exception during email sending: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.info("Skipping email test")
    
    logger.info("\n" + "=" * 60)
    logger.info("Debugging complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()