#!/usr/bin/env python3
"""
Script to resolve Secret Manager secrets for API environment variables.
This runs for local development to fetch secrets and create a resolved .env file.
"""

import os
import sys
from pathlib import Path
from google.cloud import secretmanager
from google.api_core import exceptions


def get_secret(secret_path: str) -> str:
    """
    Get a secret from Google Cloud Secret Manager.
    
    Args:
        secret_path: Full secret path
        
    Returns:
        The secret value
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except exceptions.PermissionDenied:
        print(f"⚠️  Permission denied accessing {secret_path}")
        print("   Make sure you're authenticated with: gcloud auth application-default login")
        return None
    except Exception as e:
        print(f"⚠️  Failed to retrieve secret {secret_path}: {e}")
        return None


def resolve_env_file(env_file: str):
    """Resolve secrets in an environment file."""
    env_path = Path(__file__).parent.parent / env_file
    
    if not env_path.exists():
        print(f"❌ Environment file {env_file} not found")
        sys.exit(1)
    
    print(f"📄 Processing {env_file}...")
    
    lines = []
    secrets_resolved = 0
    secrets_failed = 0
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # Skip empty lines and comments
            if not line or line.strip().startswith('#'):
                lines.append(line)
                continue
            
            # Parse key=value
            if '=' not in line:
                lines.append(line)
                continue
                
            key, value = line.split('=', 1)
            
            # Check if value is a Secret Manager path
            if (value.startswith('projects/') and 
                '/secrets/' in value and 
                '/versions/' in value):
                
                print(f"   🔐 Resolving {key}...")
                secret_value = get_secret(value)
                
                if secret_value:
                    lines.append(f"{key}={secret_value}")
                    secrets_resolved += 1
                else:
                    # Keep the original line if we can't resolve
                    lines.append(line)
                    secrets_failed += 1
            else:
                lines.append(line)
    
    # Write resolved .env file
    resolved_path = Path(__file__).parent.parent / '.env.resolved'
    with open(resolved_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"\n✅ Resolved {secrets_resolved} secrets")
    if secrets_failed > 0:
        print(f"⚠️  Failed to resolve {secrets_failed} secrets")
    print(f"📝 Written to .env.resolved")
    
    # Also update the main .env file
    import shutil
    shutil.copy(resolved_path, Path(__file__).parent.parent / '.env')
    print(f"📝 Updated .env file")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python resolve_secrets.py <env_file>")
        print("Example: python resolve_secrets.py .env.development")
        sys.exit(1)
    
    env_file = sys.argv[1]
    
    # Check if we have default application credentials
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Trying to use gcloud default credentials...")
    
    resolve_env_file(env_file)


if __name__ == "__main__":
    main()