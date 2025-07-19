#!/usr/bin/env python3
"""
Verify reCAPTCHA keys are valid by making a direct API call to Google.
"""

import httpx
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def verify_keys(site_key: str, secret_key: str, environment: str):
    """Verify a reCAPTCHA key pair by making a test request to Google."""
    print(f"\n🔍 Testing {environment} reCAPTCHA keys...")
    print(f"   Site Key: {site_key[:20]}...")
    print(f"   Secret Key: {secret_key[:20]}...")
    
    # Test with a dummy token to get the actual error from Google
    test_url = "https://www.google.com/recaptcha/api/siteverify"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # First test: Check if the secret key is valid
            response = await client.post(
                test_url,
                data={
                    "secret": secret_key,
                    "response": "test-token-invalid"
                }
            )
            
            result = response.json()
            print(f"\n   Response from Google:")
            print(f"   Success: {result.get('success', False)}")
            print(f"   Error codes: {result.get('error-codes', [])}")
            
            # Interpret the error codes
            error_codes = result.get('error-codes', [])
            
            if 'invalid-input-secret' in error_codes:
                print("   ❌ Secret key is invalid or not recognized by Google")
                print("   → This key may not exist in Google reCAPTCHA admin")
            elif 'missing-input-secret' in error_codes:
                print("   ❌ Secret key is missing")
            elif 'invalid-input-response' in error_codes:
                print("   ✅ Secret key is valid (expected error for test token)")
            else:
                print(f"   ⚠️  Unexpected response: {error_codes}")
                
    except Exception as e:
        print(f"   ❌ Error connecting to Google: {e}")

async def main():
    """Main verification function."""
    print("🔐 reCAPTCHA Key Verification Tool")
    print("=" * 50)
    
    # Get current environment keys
    current_site_key = os.getenv('RECAPTCHA_SITE_KEY', '')
    current_secret_key = os.getenv('RECAPTCHA_SECRET_KEY', '')
    
    if current_site_key and current_secret_key:
        await verify_keys(current_site_key, current_secret_key, "Current Environment")
    
    # Test all known keys
    print("\n" + "=" * 50)
    print("Testing all configured keys:")
    
    # Development keys
    await verify_keys(
        "6LcpnogrAAAAAN0OUYYKDEWK6YHisl3ZMXVX6mdM",
        "***REMOVED***",
        "Development"
    )
    
    # Staging keys
    await verify_keys(
        "6LexnYgrAAAAANIsI2_FTaIeBvTvUnc8cWg7exTw",
        "***REMOVED***",
        "Staging"
    )
    
    # Production keys
    await verify_keys(
        "6LdOa4grAAAAAKAitE1UXiHDBZ0EW7m83LM_5UJ2",
        "***REMOVED***",
        "Production"
    )
    
    print("\n" + "=" * 50)
    print("\n💡 Next Steps:")
    print("1. If you see 'invalid-input-secret', the keys don't exist in Google reCAPTCHA")
    print("2. Go to https://www.google.com/recaptcha/admin to create/verify keys")
    print("3. Ensure you're using reCAPTCHA v3 (not v2)")
    print("4. Check that the domains are correctly configured for each key")
    print("5. Keys may take a few minutes to activate after creation")

if __name__ == "__main__":
    asyncio.run(main())