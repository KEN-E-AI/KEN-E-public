#!/usr/bin/env python3
"""Debug SendGrid issues in Cloud Run deployment."""

import os
import sys
import logging
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_secret_manager_access():
    """Test if we can access SendGrid secret from Secret Manager."""
    
    logger.info("="*60)
    logger.info("Testing Secret Manager Access")
    logger.info("="*60)
    
    environments = {
        'staging': {
            'project_id': 'ken-e-staging',
            'project_number': '391472102753',
            'secret_path': 'projects/391472102753/secrets/sendgrid-api-key/versions/latest'
        },
        'production': {
            'project_id': 'ken-e-production', 
            'project_number': '395770269870',
            'secret_path': 'projects/395770269870/secrets/sendgrid-api-key/versions/latest'
        }
    }
    
    for env_name, config in environments.items():
        logger.info(f"\n{env_name.upper()} Environment:")
        logger.info(f"  Project: {config['project_id']}")
        logger.info(f"  Secret path: {config['secret_path']}")
        
        # Set environment for this test
        os.environ["GOOGLE_CLOUD_PROJECT_ID"] = config['project_id']
        
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            
            # Try to access the secret
            response = client.access_secret_version(request={"name": config['secret_path']})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.info(f"  ✓ Successfully retrieved secret (length: {len(secret_value)})")
            
            # Validate it looks like a SendGrid key
            if secret_value.startswith("SG."):
                logger.info(f"  ✓ Secret has valid SendGrid format")
            else:
                logger.warning(f"  ⚠ Secret doesn't start with 'SG.' - might be invalid")
                
        except Exception as e:
            logger.error(f"  ✗ Failed to retrieve secret: {e}")


def check_environment_variables():
    """Check what environment variables would be set in Cloud Run."""
    
    logger.info("\n" + "="*60)
    logger.info("Environment Variables Check")
    logger.info("="*60)
    
    # Check current environment
    important_vars = [
        'SENDGRID_API_KEY',
        'APP_BASE_URL',
        'EMAIL_FROM_ADDRESS',
        'EMAIL_FROM_NAME',
        'GOOGLE_CLOUD_PROJECT_ID',
        'ENVIRONMENT'
    ]
    
    logger.info("\nCurrent environment variables:")
    for var in important_vars:
        value = os.getenv(var, "NOT SET")
        if var == 'SENDGRID_API_KEY' and value != "NOT SET":
            # Don't log the actual key
            if value.startswith("projects/"):
                logger.info(f"  {var}: {value[:50]}... (Secret Manager path)")
            else:
                logger.info(f"  {var}: ***HIDDEN*** (length: {len(value)})")
        else:
            logger.info(f"  {var}: {value}")


def test_email_service_initialization():
    """Test how the email service gets initialized."""
    
    logger.info("\n" + "="*60)
    logger.info("Testing Email Service Initialization")
    logger.info("="*60)
    
    # Load staging environment
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env.staging"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info(f"Loaded environment from {env_file}")
    
    os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"
    
    # Now import and test the email service
    from src.kene_api.email_service import EmailService
    
    # Create a new instance (not using the global one)
    email_service = EmailService()
    
    logger.info(f"Email service initialized:")
    logger.info(f"  Client exists: {email_service.client is not None}")
    logger.info(f"  From email: {email_service.from_email}")
    logger.info(f"  From name: {email_service.from_name}")
    logger.info(f"  App base URL: {email_service.app_base_url}")
    
    if email_service.client:
        logger.info("  ✓ SendGrid client is initialized")
    else:
        logger.error("  ✗ SendGrid client is NOT initialized!")
        logger.error("    This means emails cannot be sent")
    
    return email_service


def simulate_invitation_email(email_service=None):
    """Simulate sending an invitation email."""
    
    logger.info("\n" + "="*60)
    logger.info("Simulating Invitation Email")
    logger.info("="*60)
    
    if not email_service:
        from src.kene_api.email_service import EmailService
        email_service = EmailService()
    
    test_data = {
        'to_email': 'test@example.com',
        'inviter_name': 'Test Admin',
        'organization_name': 'Test Organization',
        'access_level': 'admin',
        'invitation_token': 'test-token-123'
    }
    
    logger.info(f"Attempting to send invitation with:")
    for key, value in test_data.items():
        logger.info(f"  {key}: {value}")
    
    # Don't actually send, just check if it would work
    if not email_service.client:
        logger.error("✗ Cannot send - SendGrid client not initialized")
        return False
    
    logger.info("✓ SendGrid client is ready - email would be sent")
    
    # Check what URL would be in the email
    invitation_url = f"{email_service.app_base_url}/auth/signin?invitation={test_data['invitation_token']}"
    logger.info(f"  Invitation URL: {invitation_url}")
    
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SendGrid Cloud Run Debugging")
    print("="*60 + "\n")
    
    # Check environment variables
    check_environment_variables()
    
    # Test Secret Manager access
    test_secret_manager_access()
    
    # Test email service initialization
    email_service = test_email_service_initialization()
    
    # Simulate sending an invitation
    simulate_invitation_email(email_service)
    
    print("\n" + "="*60)
    print("Debugging complete")
    print("="*60)