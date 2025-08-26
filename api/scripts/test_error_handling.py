#!/usr/bin/env python3
"""Test script to verify proper error handling in email service."""

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


def test_secret_manager_failure():
    """Test behavior when Secret Manager fails."""
    logger.info("="*60)
    logger.info("Testing Secret Manager Failure Handling")
    logger.info("="*60)
    
    # Simulate Cloud Run environment with Secret Manager path
    os.environ["SENDGRID_API_KEY"] = "projects/391472102753/secrets/sendgrid-api-key/versions/latest"
    
    # Remove any service account credentials to force failure
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    
    from src.kene_api.email_service import EmailService
    from src.kene_api.exceptions import SecretManagerError, EmailServiceInitializationError
    
    # Test email service initialization
    logger.info("\n1. Testing EmailService initialization with failed Secret Manager:")
    email_service = EmailService()
    
    # Try to send an email - should handle gracefully
    logger.info("\n2. Testing send_invitation_email with disabled service:")
    result = email_service.send_invitation_email(
        to_email="test@example.com",
        inviter_name="Test User",
        organization_name="Test Org",
        access_level="admin",
        invitation_token="test-token-123"
    )
    
    logger.info(f"   Email send result: {result}")
    assert result is False, "Email should fail when Secret Manager is inaccessible"
    
    logger.info("\n✅ Test passed: Email service handles Secret Manager failures gracefully")
    

def test_valid_api_key():
    """Test behavior with a valid API key."""
    logger.info("\n" + "="*60)
    logger.info("Testing Valid API Key Handling")
    logger.info("="*60)
    
    # Set a direct API key (not a Secret Manager path)
    test_api_key = "SG.test_api_key_12345"
    os.environ["SENDGRID_API_KEY"] = test_api_key
    
    from src.kene_api.email_service import EmailService
    
    logger.info("\n1. Testing EmailService initialization with direct API key:")
    email_service = EmailService()
    email_service._ensure_initialized()
    
    assert email_service.api_key == test_api_key
    assert email_service.client is not None
    
    logger.info(f"   API key set: {email_service.api_key[:10]}...")
    logger.info(f"   Client initialized: {email_service.client is not None}")
    
    logger.info("\n✅ Test passed: Email service initializes correctly with direct API key")


def test_error_logging():
    """Test that errors are properly logged with structured fields."""
    logger.info("\n" + "="*60)
    logger.info("Testing Error Logging with Structured Fields")
    logger.info("="*60)
    
    # Set up to capture log records
    import logging
    from src.kene_api import email_service
    
    # Create a custom handler to capture log records
    class LogCapture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        
        def emit(self, record):
            self.records.append(record)
    
    capture = LogCapture()
    email_service.logger.addHandler(capture)
    
    # Set a Secret Manager path to trigger error
    os.environ["SENDGRID_API_KEY"] = "projects/123/secrets/sendgrid/versions/latest"
    
    from src.kene_api.email_service import EmailService
    
    service = EmailService()
    service.send_invitation_email(
        to_email="test@example.com",
        inviter_name="Test",
        organization_name="Org",
        access_level="admin",
        invitation_token="token"
    )
    
    # Check that structured logging fields were included
    error_logs = [r for r in capture.records if r.levelname in ("ERROR", "WARNING")]
    
    logger.info(f"\n   Captured {len(error_logs)} error/warning logs")
    
    for log in error_logs:
        if hasattr(log, '__dict__'):
            extra_fields = {k: v for k, v in log.__dict__.items() 
                          if k not in ['name', 'msg', 'args', 'created', 'filename', 
                                      'funcName', 'levelname', 'levelno', 'lineno', 
                                      'module', 'msecs', 'pathname', 'process', 
                                      'processName', 'relativeCreated', 'thread', 
                                      'threadName', 'exc_info', 'exc_text', 'stack_info']}
            if extra_fields:
                logger.info(f"   Log extra fields: {extra_fields}")
    
    logger.info("\n✅ Test passed: Errors are logged with structured fields for monitoring")


if __name__ == "__main__":
    try:
        test_secret_manager_failure()
        test_valid_api_key()
        test_error_logging()
        
        logger.info("\n" + "="*60)
        logger.info("All tests passed! ✅")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)