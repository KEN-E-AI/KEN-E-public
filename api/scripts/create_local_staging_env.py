#!/usr/bin/env python3
"""
Create a local staging environment file without Secret Manager dependencies.
This allows developers to work with staging locally without needing Secret Manager access.
"""

import os
import sys
from pathlib import Path


def create_local_staging_env():
    """Create a local staging env file template."""
    
    staging_env_path = Path(__file__).parent.parent / '.env.staging'
    local_env_path = Path(__file__).parent.parent / '.env.staging.local'
    
    if not staging_env_path.exists():
        print("❌ .env.staging not found")
        return False
    
    print("📝 Creating .env.staging.local template...")
    
    # Read the staging env file
    with open(staging_env_path, 'r') as f:
        lines = f.readlines()
    
    # Process each line
    new_lines = []
    secrets_found = []
    
    for line in lines:
        line = line.rstrip('\n')
        
        # Skip empty lines and comments
        if not line or line.strip().startswith('#'):
            new_lines.append(line)
            continue
        
        # Parse key=value
        if '=' not in line:
            new_lines.append(line)
            continue
        
        key, value = line.split('=', 1)
        
        # Check if value is a Secret Manager path
        if (value.startswith('projects/') and 
            '/secrets/' in value and 
            '/versions/' in value):
            
            # Extract secret name
            secret_name = value.split('/secrets/')[1].split('/')[0]
            secrets_found.append((key, secret_name))
            
            # Add placeholder
            if key == 'NEO4J_PASSWORD':
                new_lines.append(f"{key}=<YOUR_NEO4J_PASSWORD_HERE>")
            elif key == 'SUPERSET_PASSWORD':
                new_lines.append(f"{key}=<YOUR_SUPERSET_PASSWORD_HERE>")
            elif key == 'SENDGRID_API_KEY':
                new_lines.append(f"{key}=<YOUR_SENDGRID_API_KEY_HERE>")
            elif key == 'RECAPTCHA_SITE_KEY':
                new_lines.append(f"{key}=<YOUR_RECAPTCHA_SITE_KEY_HERE>")
            elif key == 'RECAPTCHA_SECRET_KEY':
                new_lines.append(f"{key}=<YOUR_RECAPTCHA_SECRET_KEY_HERE>")
            else:
                new_lines.append(f"{key}=<YOUR_{key}_HERE>")
        else:
            new_lines.append(line)
    
    # Write the local env file
    with open(local_env_path, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print(f"✅ Created {local_env_path}")
    
    # Add to .gitignore if not already there
    gitignore_path = Path(__file__).parent.parent / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
        
        if '.env.staging.local' not in gitignore_content:
            with open(gitignore_path, 'a') as f:
                f.write('\n# Local staging environment (never commit!)\n')
                f.write('.env.staging.local\n')
            print("✅ Added .env.staging.local to .gitignore")
    
    # Print instructions
    print("\n📋 Next steps:")
    print("\n1. Edit .env.staging.local and replace the placeholders:")
    for key, secret in secrets_found:
        print(f"   - {key}: Get value for '{secret}' from your team")
    
    print("\n2. Use the local staging environment:")
    print("   cp .env.staging.local .env")
    
    print("\n3. IMPORTANT: Never commit .env.staging.local to git!")
    print("   It contains sensitive credentials.")
    
    return True


def create_switch_script():
    """Create a script to switch to local staging."""
    script_content = '''#!/bin/bash
# Switch to local staging environment

if [ ! -f .env.staging.local ]; then
    echo "❌ .env.staging.local not found"
    echo "   Run: python scripts/create_local_staging_env.py"
    exit 1
fi

# Backup current .env
if [ -f .env ]; then
    cp .env .env.backup
    echo "📦 Backed up current .env to .env.backup"
fi

# Switch to local staging
cp .env.staging.local .env
echo "✅ Switched to local staging environment"
echo "   Neo4j and other services will use your local credentials"
echo ""
echo "⚠️  Remember: Don't commit .env or .env.staging.local!"
'''
    
    script_path = Path(__file__).parent / 'use_local_staging.sh'
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(script_path, 0o755)
    print(f"\n✅ Created helper script: {script_path}")
    print("   Use it to quickly switch to local staging: ./scripts/use_local_staging.sh")


def main():
    """Main function."""
    print("=" * 60)
    print("Local Staging Environment Setup")
    print("=" * 60)
    
    print("\nThis tool creates a local staging environment file that doesn't")
    print("require Google Secret Manager access.\n")
    
    if create_local_staging_env():
        create_switch_script()
        
        print("\n" + "=" * 60)
        print("✅ Setup complete!")
        print("=" * 60)
        
        print("\nYou can now work with staging locally without Secret Manager access.")
        print("Ask your team for the actual credential values to fill in.")
    else:
        print("\n❌ Setup failed")


if __name__ == "__main__":
    main()