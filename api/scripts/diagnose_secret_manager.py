#!/usr/bin/env python3
"""
Diagnostic script for Google Secret Manager authentication issues.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

try:
    from google.cloud import secretmanager
    from google.api_core import exceptions
    from google.auth import default
    from google.auth.exceptions import RefreshError, DefaultCredentialsError
except ImportError:
    print("❌ Error: google-cloud-secret-manager not installed")
    print("   Run: pip install google-cloud-secret-manager")
    sys.exit(1)


def check_gcloud_auth():
    """Check if gcloud is authenticated."""
    print("\n1️⃣ Checking gcloud authentication...")
    
    try:
        # Check if gcloud is installed
        result = subprocess.run(['gcloud', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install")
            return False
        
        # Check active account
        result = subprocess.run(['gcloud', 'auth', 'list', '--format=json'], capture_output=True, text=True)
        if result.returncode == 0:
            accounts = json.loads(result.stdout)
            active_accounts = [acc for acc in accounts if acc.get('status') == 'ACTIVE']
            if active_accounts:
                print(f"✅ gcloud authenticated as: {active_accounts[0]['account']}")
            else:
                print("❌ No active gcloud account")
                return False
        
        # Check application default credentials
        result = subprocess.run(['gcloud', 'auth', 'application-default', 'print-access-token'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Application Default Credentials (ADC) are configured")
            return True
        else:
            print("❌ Application Default Credentials (ADC) not configured")
            print("   Run: gcloud auth application-default login")
            return False
            
    except Exception as e:
        print(f"❌ Error checking gcloud auth: {e}")
        return False


def check_python_auth():
    """Check Python Google auth."""
    print("\n2️⃣ Checking Python Google authentication...")
    
    try:
        credentials, project = default()
        print(f"✅ Python auth successful")
        print(f"   Project ID: {project or 'Not set (will use from env file)'}")
        
        # Try to refresh the credentials
        try:
            credentials.refresh(None)
            print("✅ Credentials can be refreshed")
        except Exception as e:
            print(f"⚠️  Warning: Cannot refresh credentials: {e}")
            
        return True, project
        
    except DefaultCredentialsError as e:
        print(f"❌ No default credentials found: {e}")
        return False, None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False, None


def check_secret_manager_access(project_id=None):
    """Check access to Secret Manager."""
    print("\n3️⃣ Checking Secret Manager access...")
    
    if not project_id:
        # Try to get project ID from environment
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT_ID', '391472102753')
        print(f"   Using project ID: {project_id}")
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        
        # Try to list secrets (requires secretmanager.secrets.list permission)
        parent = f"projects/{project_id}"
        print(f"   Attempting to list secrets in {parent}...")
        
        secrets = list(client.list_secrets(request={"parent": parent, "page_size": 1}))
        print(f"✅ Can list secrets (found {len(secrets)} secret(s))")
        
        # Try to access a specific secret from .env.staging
        test_secret = f"projects/{project_id}/secrets/neo4j-password/versions/latest"
        print(f"\n   Testing access to: {test_secret}")
        
        try:
            response = client.access_secret_version(request={"name": test_secret})
            print("✅ Can access neo4j-password secret")
            print(f"   Secret value length: {len(response.payload.data)}")
            return True
        except exceptions.PermissionDenied:
            print("❌ Permission denied accessing neo4j-password")
            print("   You need the 'Secret Manager Secret Accessor' role")
            return False
        except exceptions.NotFound:
            print("❌ Secret neo4j-password not found")
            print("   The secret may not exist in this project")
            return False
            
    except exceptions.PermissionDenied as e:
        print(f"❌ Permission denied: {e}")
        print("\n   Required IAM roles:")
        print("   - Secret Manager Secret Accessor (roles/secretmanager.secretAccessor)")
        print("   - OR Secret Manager Viewer (roles/secretmanager.viewer)")
        return False
    except Exception as e:
        print(f"❌ Error accessing Secret Manager: {e}")
        return False


def check_iam_permissions():
    """Check what IAM permissions the current user has."""
    print("\n4️⃣ Checking IAM permissions...")
    
    try:
        # Get current user
        result = subprocess.run(['gcloud', 'config', 'get-value', 'account'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            account = result.stdout.strip()
            print(f"   Current account: {account}")
        else:
            print("   Could not determine current account")
            return
        
        # Get project
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT_ID', '391472102753')
        
        # Check IAM policy
        print(f"   Checking IAM policy for project {project_id}...")
        result = subprocess.run([
            'gcloud', 'projects', 'get-iam-policy', project_id,
            '--flatten=bindings[].members',
            '--format=json',
            f'--filter=bindings.members:{account}'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            bindings = json.loads(result.stdout)
            if bindings:
                print(f"\n   Your IAM roles:")
                for binding in bindings:
                    role = binding.get('bindings', {}).get('role', 'Unknown')
                    print(f"   - {role}")
                    
                # Check for Secret Manager roles
                roles = [b.get('bindings', {}).get('role', '') for b in bindings]
                has_secret_access = any('secretmanager' in role for role in roles)
                
                if has_secret_access:
                    print("\n✅ You have Secret Manager permissions")
                else:
                    print("\n❌ You don't have Secret Manager permissions")
                    print("   Ask your admin to grant you one of these roles:")
                    print("   - roles/secretmanager.secretAccessor (recommended)")
                    print("   - roles/secretmanager.admin")
            else:
                print("   No IAM roles found for your account")
        else:
            print("   Could not retrieve IAM policy")
            print("   You may not have permission to view the IAM policy")
            
    except Exception as e:
        print(f"   Error checking IAM: {e}")


def suggest_fixes():
    """Suggest fixes based on the diagnostics."""
    print("\n🔧 Suggested fixes:")
    print("\n1. Ensure you're authenticated:")
    print("   gcloud auth application-default login")
    
    print("\n2. Set the project explicitly:")
    print("   gcloud config set project 391472102753")
    
    print("\n3. If you don't have Secret Manager access, you have two options:")
    print("\n   Option A: Request access from your admin")
    print("   - Ask for 'Secret Manager Secret Accessor' role")
    print("   - For project: 391472102753")
    
    print("\n   Option B: Use a local .env file without secrets")
    print("   - Create .env.staging.local with actual values (not secret paths)")
    print("   - Copy it to .env when needed")
    print("   - Never commit this file to git")
    
    print("\n4. Test secret access directly:")
    print("   gcloud secrets versions access latest --secret=neo4j-password --project=391472102753")
    
    print("\n5. If you're using a service account:")
    print("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json")


def main():
    """Run all diagnostics."""
    print("=" * 60)
    print("Google Secret Manager Diagnostic Tool")
    print("=" * 60)
    
    # Check various authentication methods
    gcloud_ok = check_gcloud_auth()
    python_ok, project = check_python_auth()
    
    if python_ok:
        # Use detected project or fall back to env/default
        project_id = project or os.environ.get('GOOGLE_CLOUD_PROJECT_ID', '391472102753')
        secret_ok = check_secret_manager_access(project_id)
        
        if gcloud_ok:
            check_iam_permissions()
    else:
        print("\n⚠️  Skipping Secret Manager checks due to auth issues")
        secret_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if gcloud_ok and python_ok and secret_ok:
        print("✅ Everything looks good! You should be able to access secrets.")
        print("\nIf you're still having issues, check:")
        print("- Network connectivity")
        print("- Firewall rules")
        print("- Corporate proxy settings")
    else:
        print("❌ Issues detected. See suggestions below.")
        suggest_fixes()


if __name__ == "__main__":
    main()