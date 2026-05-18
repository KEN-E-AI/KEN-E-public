#!/usr/bin/env python3
"""
Test service account permissions for Secret Manager access.
"""

import json
import os
import sys
from pathlib import Path

try:
    from google.cloud import secretmanager
    from google.oauth2 import service_account
    from google.api_core import exceptions
except ImportError:
    print("❌ Error: google-cloud-secret-manager not installed")
    print("   Run: pip install google-cloud-secret-manager")
    sys.exit(1)


def test_service_account(sa_file_path: str):
    """Test if a service account can access Secret Manager."""
    
    print(f"🔍 Testing service account: {sa_file_path}")
    
    # Check if file exists
    if not os.path.exists(sa_file_path):
        print(f"❌ Service account file not found: {sa_file_path}")
        return False
    
    # Load and validate the service account
    try:
        with open(sa_file_path, 'r') as f:
            sa_data = json.load(f)
        
        print(f"✅ Valid JSON file")
        print(f"   Type: {sa_data.get('type', 'unknown')}")
        print(f"   Project ID: {sa_data.get('project_id', 'unknown')}")
        print(f"   Client Email: {sa_data.get('client_email', 'unknown')}")
        
        if sa_data.get('type') != 'service_account':
            print(f"❌ Not a service account file (type: {sa_data.get('type')})")
            return False
            
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    # Create credentials from the service account
    try:
        credentials = service_account.Credentials.from_service_account_file(
            sa_file_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        print("✅ Created credentials from service account")
    except Exception as e:
        print(f"❌ Failed to create credentials: {e}")
        return False
    
    # Test Secret Manager access
    print("\n📋 Testing Secret Manager access...")
    
    try:
        # Create client with explicit credentials
        client = secretmanager.SecretManagerServiceClient(credentials=credentials)
        
        # Try to list secrets
        project_id = sa_data.get('project_id', '391472102753')
        parent = f"projects/{project_id}"
        
        print(f"   Attempting to list secrets in project {project_id}...")
        
        try:
            # List with page_size=1 to minimize data transfer
            secrets = list(client.list_secrets(request={"parent": parent, "page_size": 1}))
            print(f"✅ Can list secrets (found at least {len(secrets)})")
            
            # Try to access a specific secret
            test_secret_name = f"projects/{project_id}/secrets/neo4j-password/versions/latest"
            print(f"\n   Testing access to: neo4j-password")
            
            try:
                response = client.access_secret_version(request={"name": test_secret_name})
                print(f"✅ Can access neo4j-password secret")
                print(f"   Secret value length: {len(response.payload.data)}")
                return True
                
            except exceptions.PermissionDenied:
                print("❌ Permission denied accessing neo4j-password")
                print("   The service account can list secrets but cannot access their values")
                print("   Need: roles/secretmanager.secretAccessor")
                return False
            except exceptions.NotFound:
                print("❌ Secret neo4j-password not found")
                print("   The secret may not exist in this project")
                return False
                
        except exceptions.PermissionDenied as e:
            print(f"❌ Permission denied listing secrets: {e}")
            print("\n   The service account needs one of these roles:")
            print("   - roles/secretmanager.secretAccessor (recommended)")
            print("   - roles/secretmanager.viewer")
            print("   - roles/secretmanager.admin")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main function."""
    if len(sys.argv) < 2:
        # Try to find service account files automatically
        script_dir = Path(__file__).parent
        api_dir = script_dir.parent
        
        sa_files = [
            api_dir / "ken-e-staging.json",
            api_dir / "ken-e-dev.json",
            api_dir / "ken-e-production.json",
        ]
        
        print("No service account file specified. Looking for files...")
        print()
        
        found = False
        for sa_file in sa_files:
            if sa_file.exists():
                print(f"Found: {sa_file}")
                if test_service_account(str(sa_file)):
                    found = True
                print("-" * 60)
                
        if not found:
            print("\n❌ No working service accounts found")
            print("\nUsage: python check_service_account.py <path_to_service_account.json>")
            sys.exit(1)
    else:
        sa_file = sys.argv[1]
        if not test_service_account(sa_file):
            print("\n❌ Service account test failed")
            
            print("\n💡 Solutions:")
            print("\n1. Ask your admin to grant Secret Manager permissions:")
            print(f"   gcloud projects add-iam-policy-binding 391472102753 \\")
            print(f"     --member='serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL' \\")
            print(f"     --role='roles/secretmanager.secretAccessor'")
            
            print("\n2. Use a local environment file instead:")
            print("   python scripts/create_local_staging_env.py")
            print("   cp .env.staging.local .env")
            
            sys.exit(1)
        else:
            print("\n✅ Service account is properly configured!")
            print("   You can use this service account for the staging environment.")


if __name__ == "__main__":
    main()