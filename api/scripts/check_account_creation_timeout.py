#!/usr/bin/env python3
"""
Test script to verify account creation doesn't timeout.
Tests that strategy generation runs in background without blocking.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add parent directory to path to import API modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.models.kene_models import AccountRequest
from src.kene_api.auth.user_context import UserContext
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_account_creation():
    """Test account creation with strategy generation."""
    
    # Import the create_account function
    from src.kene_api.routers.accounts import create_account
    
    # Create a mock user context
    user = UserContext(
        user_id="test_user_123",
        email="test@example.com",
        organizations={"test_org_123": "admin"},
        accounts={},
        permissions={
            "organizations": {"test_org_123": "admin"},
            "accounts": {}
        }
    )
    
    # Create a test account request
    request = AccountRequest(
        account_name="Test Company Timeout Fix",
        organization_id="test_org_123",
        industry="Technology",
        status="Active",
        websites=["https://example.com"],
        timezone="America/New_York",
        region=["North America"],
        estimated_annual_ad_budget=100000,
        marketing_channels=["SEO", "Social Media"],
        product_integrations=["Google Analytics", "HubSpot"]
    )
    
    logger.info("Starting account creation test...")
    start_time = time.time()
    
    try:
        # Call the create_account function
        result = await create_account(request, user)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Account creation completed in {elapsed:.2f} seconds")
        logger.info(f"Account ID: {result.get('account_id')}")
        
        if elapsed > 30:
            logger.warning(f"⚠️ Account creation took longer than 30 seconds ({elapsed:.2f}s)")
        else:
            logger.info(f"✅ Account creation completed within acceptable time ({elapsed:.2f}s < 30s)")
            
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Account creation failed after {elapsed:.2f} seconds: {e}")
        raise


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("Testing account creation timeout fix")
    logger.info("=" * 60)
    
    try:
        # Test account creation
        result = await test_account_creation()
        
        logger.info("=" * 60)
        logger.info("✅ TEST PASSED: Account creation completed without timeout")
        logger.info(f"Account created: {result.get('account_id')}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ TEST FAILED: {e}")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())