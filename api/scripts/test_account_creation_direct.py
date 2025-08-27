#!/usr/bin/env python3
"""
Test script to directly test account creation endpoint via HTTP.
Simulates what the frontend does to check for timeout issues.
"""

import asyncio
import httpx
import time
import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_account_creation():
    """Test account creation via HTTP request."""
    
    # Get a valid Firebase token (you'll need to provide this)
    # For testing, you can get this from the browser's network tab when logged in
    AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")
    
    if not AUTH_TOKEN:
        logger.warning("No TEST_AUTH_TOKEN provided. Test will likely fail with 401.")
        logger.info("To get a token: Login to the app, open browser dev tools, ")
        logger.info("go to Network tab, and look for Authorization header in API calls.")
        logger.info("Set it as: export TEST_AUTH_TOKEN='Bearer YOUR_TOKEN_HERE'")
        return False
    
    # API endpoint
    api_url = "http://localhost:8000/api/v1/accounts/"
    
    # Test data
    account_data = {
        "account_name": f"Test Company {int(time.time())}",
        "organization_id": "healthway",  # Use a known test organization
        "industry": "Technology",
        "status": "Active", 
        "websites": ["https://example.com"],
        "timezone": "America/New_York",
        "region": ["North America"],
        "estimated_annual_ad_budget": 100000,
        "marketing_channels": ["SEO", "Social Media"],
        "product_integrations": ["Google Analytics"]
    }
    
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    
    logger.info(f"Testing account creation at {api_url}")
    logger.info(f"Account name: {account_data['account_name']}")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(api_url, json=account_data, headers=headers)
            elapsed = time.time() - start_time
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response time: {elapsed:.2f} seconds")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Account created successfully!")
                logger.info(f"Account ID: {data.get('account_id')}")
                
                if elapsed < 5:
                    logger.info(f"✅ EXCELLENT: Response time under 5 seconds ({elapsed:.2f}s)")
                elif elapsed < 30:
                    logger.info(f"✅ GOOD: Response time under 30 seconds ({elapsed:.2f}s)")
                else:
                    logger.warning(f"⚠️ SLOW: Response time over 30 seconds ({elapsed:.2f}s)")
                    
                return True
                
            else:
                logger.error(f"❌ Account creation failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            logger.error(f"❌ Request timed out after {elapsed:.2f} seconds")
            return False
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ Request failed after {elapsed:.2f} seconds: {e}")
            return False


async def main():
    """Main test function."""
    logger.info("=" * 60)
    logger.info("Testing Account Creation Timeout Fix")
    logger.info("=" * 60)
    
    # Check if API is running
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                logger.error("API health check failed. Is the API running on port 8000?")
                return
    except Exception as e:
        logger.error(f"Cannot connect to API on localhost:8000: {e}")
        logger.info("Please start the API with: cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000")
        return
    
    # Run the test
    success = await test_account_creation()
    
    logger.info("=" * 60)
    if success:
        logger.info("✅ TEST PASSED: Account creation works without timeout")
    else:
        logger.info("❌ TEST FAILED: See errors above")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())