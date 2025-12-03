#!/usr/bin/env python3
"""Test SendGrid configuration in production/staging environment."""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_sendgrid_directly():
    """Test SendGrid API key directly without going through the service."""
    
    from dotenv import load_dotenv
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    
    # Try different environments
    environments = ['staging', 'production']
    
    for env in environments:
        env_file = Path(__file__).parent.parent / f".env.{env}"
        if not env_file.exists():
            logger.warning(f"Environment file not found: {env_file}")
            continue
            
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {env.upper()} environment")
        logger.info(f"{'='*60}")
        
        # Load environment
        load_dotenv(env_file, override=True)
        
        # Set project ID based on environment
        if env == 'staging':
            os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-staging"
        else:
            os.environ["GOOGLE_CLOUD_PROJECT_ID"] = "ken-e-production"
        
        # Get SendGrid API key
        sendgrid_key_path = os.getenv("SENDGRID_API_KEY")
        logger.info(f"SENDGRID_API_KEY env var: {sendgrid_key_path}")
        
        if not sendgrid_key_path:
            logger.error("SENDGRID_API_KEY not set in environment")
            continue
        
        # Try to retrieve the actual key
        from src.kene_api.utils.secrets import get_env_or_secret

        try:
            api_key = get_env_or_secret("SENDGRID_API_KEY")
            if not api_key:
                logger.error("Failed to retrieve SendGrid API key from Secret Manager")
                continue
                
            logger.info(f"✓ Retrieved API key (length: {len(api_key)})")
            
            # Validate key format
            if not api_key.startswith("SG."):
                logger.warning(f"API key doesn't start with 'SG.' - might be invalid")
            
            # Try to initialize SendGrid client
            sg = SendGridAPIClient(api_key)
            logger.info("✓ SendGrid client initialized")
            
            # Test sending a simple email
            test_email = input(f"\nEnter email to test {env} SendGrid (or press Enter to skip): ").strip()
            
            if test_email and '@' in test_email:
                message = Mail(
                    from_email='noreply@ken-e.ai',
                    to_emails=test_email,
                    subject=f'SendGrid Test - {env.upper()} Environment',
                    html_content=f'<p>This is a test email from KEN-E {env} environment.</p>'
                )
                
                try:
                    response = sg.send(message)
                    logger.info(f"✓ Email sent! Status code: {response.status_code}")
                    logger.info(f"  Response headers: {response.headers}")
                    
                    # Check response body for any messages
                    if response.body:
                        logger.info(f"  Response body: {response.body}")
                        
                except Exception as e:
                    logger.error(f"✗ Failed to send email: {e}")
                    if hasattr(e, 'body'):
                        logger.error(f"  Error body: {e.body}")
            
        except Exception as e:
            logger.error(f"Error retrieving/testing SendGrid: {e}")
            import traceback
            traceback.print_exc()


def check_cloud_run_environment():
    """Check what environment variables are actually set in Cloud Run."""
    
    logger.info("\n" + "="*60)
    logger.info("Checking deployed environment variables")
    logger.info("="*60)
    
    # Check if we can access the deployed API
    import requests
    
    urls = {
        'staging': 'https://kene-api-staging-391472102753.us-central1.run.app',
        'production': 'https://kene-api-prod-395770269870.us-central1.run.app'
    }
    
    for env, url in urls.items():
        try:
            logger.info(f"\nChecking {env} API at {url}/health")
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ {env} API is healthy")
            else:
                logger.warning(f"⚠ {env} API returned status {response.status_code}")
        except Exception as e:
            logger.error(f"✗ Could not reach {env} API: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SendGrid Production/Staging Test")
    print("="*60 + "\n")
    
    # Check deployed environments
    check_cloud_run_environment()
    
    # Test SendGrid configuration
    print("\nTesting SendGrid configuration...")
    test_sendgrid_directly()
    
    print("\n" + "="*60)
    print("Test completed")
    print("="*60)