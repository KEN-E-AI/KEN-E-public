#!/usr/bin/env python3
"""
Debug reCAPTCHA by testing the full flow.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from kene_api.config import settings
from kene_api.recaptcha import recaptcha_service


async def test_with_mock_token():
    """Test with various token scenarios to see what errors we get."""
    print("🔍 Testing reCAPTCHA Service with various scenarios...")
    print(f"   Site Key: {settings.RECAPTCHA_SITE_KEY[:20]}...")
    print(f"   Secret Key: {settings.RECAPTCHA_SECRET_KEY[:20]}...")
    print()

    # Test 1: Empty token
    print("Test 1: Empty token")
    result = await recaptcha_service.verify_token("", expected_action="signin")
    print(f"   Result: {result}")
    print()

    # Test 2: Invalid token
    print("Test 2: Invalid token")
    result = await recaptcha_service.verify_token(
        "invalid-token", expected_action="signin"
    )
    print(f"   Result: {result}")
    print()

    # Test 3: Test if the service is initialized properly
    print("Test 3: Service initialization check")
    print(f"   Service has secret key: {bool(recaptcha_service.secret_key)}")
    print(f"   Settings has secret key: {bool(settings.RECAPTCHA_SECRET_KEY)}")
    print()


async def main():
    """Main debug function."""
    # Load environment
    load_dotenv()

    print("🔐 reCAPTCHA Debug Tool")
    print("=" * 50)
    print()

    # Run tests
    await test_with_mock_token()

    print("💡 Debugging Notes:")
    print("1. 'invalid-keys' is not a standard Google reCAPTCHA error")
    print("2. This might be coming from the frontend or a custom error")
    print("3. Check browser console for more details")
    print("4. Try these steps:")
    print("   - Clear browser cache and cookies")
    print("   - Restart both API and frontend servers")
    print("   - Check browser network tab for the actual API response")


if __name__ == "__main__":
    asyncio.run(main())
