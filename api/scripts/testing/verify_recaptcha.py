#!/usr/bin/env python3
"""
Test script to verify reCAPTCHA configuration and functionality.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from kene_api.config import settings
from kene_api.recaptcha import recaptcha_service

def check_environment_config():
    """Check if environment variables are properly configured."""
    print("🔍 Checking reCAPTCHA Environment Configuration...")
    print(f"   RECAPTCHA_SITE_KEY: {'✅ Set' if settings.RECAPTCHA_SITE_KEY else '❌ Missing'}")
    print(f"   RECAPTCHA_SECRET_KEY: {'✅ Set' if settings.RECAPTCHA_SECRET_KEY else '❌ Missing'}")
    
    if settings.RECAPTCHA_SITE_KEY:
        print(f"   Site Key: {settings.RECAPTCHA_SITE_KEY[:10]}...")
    if settings.RECAPTCHA_SECRET_KEY:
        print(f"   Secret Key: {settings.RECAPTCHA_SECRET_KEY[:10]}...")
    
    print()
    return bool(settings.RECAPTCHA_SITE_KEY and settings.RECAPTCHA_SECRET_KEY)

async def test_recaptcha_service():
    """Test the reCAPTCHA service with invalid tokens to check error handling."""
    print("🧪 Testing reCAPTCHA Service...")
    
    # Test with empty token
    print("   Testing empty token...")
    result = await recaptcha_service.verify_token("")
    print(f"      Result: {result}")
    
    # Test with invalid token
    print("   Testing invalid token...")
    result = await recaptcha_service.verify_token("invalid-token-12345")
    print(f"      Result: {result}")
    
    # Test with invalid token but valid action
    print("   Testing invalid token with 'signin' action...")
    result = await recaptcha_service.verify_token("invalid-token-12345", expected_action="signin")
    print(f"      Result: {result}")
    
    print()

def print_common_issues():
    """Print common reCAPTCHA issues and solutions."""
    print("🔧 Common reCAPTCHA Issues and Solutions:")
    print("   1. Domain Mismatch:")
    print("      - Check that localhost is added to allowed domains in Google reCAPTCHA admin")
    print("      - Verify the correct domain is configured for staging/production")
    print()
    print("   2. Key Mismatch:")
    print("      - Site key (public) should match between frontend and backend")
    print("      - Secret key (private) should only be in backend")
    print()
    print("   3. Version Mismatch:")
    print("      - Ensure you're using reCAPTCHA v3 keys if implementing v3")
    print("      - Check that the action parameter matches what's expected")
    print()
    print("   4. Rate Limiting:")
    print("      - Check if too many requests are being made from the same IP")
    print()
    print("   5. Network Issues:")
    print("      - Verify the backend can reach www.google.com/recaptcha/api/siteverify")
    print()

async def main():
    """Main test function."""
    print("🔐 reCAPTCHA Configuration Test Tool")
    print("=" * 50)
    print()
    
    # Load environment
    load_dotenv()
    
    # Check configuration
    config_ok = check_environment_config()
    
    if not config_ok:
        print("❌ Configuration incomplete. Please check your environment variables.")
        print_common_issues()
        return
    
    # Test service
    await test_recaptcha_service()
    
    # Print debugging info
    print_common_issues()
    
    print("✅ Test complete. Check the results above for any issues.")
    print()
    print("💡 Next steps:")
    print("   1. Run this script in each environment (dev/staging/prod)")
    print("   2. Check browser console for detailed error messages")
    print("   3. Verify domain configuration in Google reCAPTCHA admin")

if __name__ == "__main__":
    asyncio.run(main())