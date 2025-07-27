#!/bin/bash

# Fixed script to switch to staging using service account credentials
# This version properly passes the environment variable to child processes

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
API_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Service account file
SA_FILE="$API_DIR/ken-e-staging.json"

# Check if service account file exists
if [ ! -f "$SA_FILE" ]; then
    echo "❌ Service account file not found: $SA_FILE"
    echo "   Please ensure ken-e-staging.json is in the api directory"
    exit 1
fi

echo "🔐 Using service account for staging environment"
echo "   Service Account: $SA_FILE"

# First, let's verify the service account works
echo ""
echo "🔍 Verifying service account access..."

# Export for all child processes
export GOOGLE_APPLICATION_CREDENTIALS="$SA_FILE"

# Test if we can list secrets (this will validate the service account)
if command -v gcloud &> /dev/null; then
    echo "   Testing with gcloud..."
    if gcloud secrets list --limit=1 --project=391472102753 &>/dev/null; then
        echo "✅ Service account can access Secret Manager"
    else
        echo "❌ Service account cannot access Secret Manager"
        echo ""
        echo "The service account may not have the required permissions."
        echo "You need one of these roles:"
        echo "  - roles/secretmanager.secretAccessor"
        echo "  - roles/secretmanager.viewer"
        echo "  - roles/secretmanager.admin"
        echo ""
        echo "Contact your admin to grant permissions, or use:"
        echo "  python scripts/create_local_staging_env.py"
        exit 1
    fi
else
    echo "   gcloud not available, skipping verification"
fi

# Create a wrapper script that exports the env var before running Python
WRAPPER_SCRIPT=$(mktemp)
cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
export GOOGLE_APPLICATION_CREDENTIALS="$1"
shift
exec "$@"
EOF
chmod +x "$WRAPPER_SCRIPT"

# Backup current .env
if [ -f "$API_DIR/.env" ]; then
    cp "$API_DIR/.env" "$API_DIR/.env.backup.$(date +%s)"
fi

# Copy staging env file
cp "$API_DIR/.env.staging" "$API_DIR/.env"

echo ""
echo "🔐 Resolving secrets from Google Secret Manager..."

# Run resolve_secrets.py with the service account
if command -v uv &> /dev/null; then
    PYTHON_CMD="uv run python"
else
    PYTHON_CMD="python3"
fi

# Use the wrapper to ensure env var is set
if "$WRAPPER_SCRIPT" "$SA_FILE" $PYTHON_CMD "$SCRIPT_DIR/resolve_secrets.py" ".env.staging"; then
    echo ""
    echo "✅ Secrets resolved successfully!"
    
    # Add the service account path to .env
    echo "" >> "$API_DIR/.env"
    echo "# Service Account Configuration (added by use_staging_with_sa_fixed.sh)" >> "$API_DIR/.env"
    echo "GOOGLE_APPLICATION_CREDENTIALS=$SA_FILE" >> "$API_DIR/.env"
    
    echo ""
    echo "✅ Successfully configured staging with service account!"
    echo ""
    echo "The API will now use the service account for all Google Cloud operations."
    echo "You can start the API with: uv run -- uvicorn src.kene_api.main:app --reload"
    
    # Clean up
    rm -f "$WRAPPER_SCRIPT"
    exit 0
else
    echo ""
    echo "❌ Failed to resolve secrets"
    echo ""
    echo "Restoring previous .env file..."
    if [ -f "$API_DIR/.env.backup."* ]; then
        mv "$API_DIR/.env.backup."* "$API_DIR/.env"
    else
        rm -f "$API_DIR/.env"
    fi
    
    # Clean up
    rm -f "$WRAPPER_SCRIPT"
    
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Verify the service account JSON is valid:"
    echo "   cat $SA_FILE | jq '.type'"
    echo ""
    echo "2. Check if the service account has Secret Manager permissions:"
    echo "   gcloud projects get-iam-policy 391472102753 --flatten=\"bindings[].members\" --filter=\"bindings.members:serviceAccount:*\""
    echo ""
    echo "3. Try the local staging environment instead:"
    echo "   python scripts/create_local_staging_env.py"
    echo ""
    echo "4. Check the detailed error by running manually:"
    echo "   export GOOGLE_APPLICATION_CREDENTIALS=\"$SA_FILE\""
    echo "   python scripts/resolve_secrets.py .env.staging"
    
    exit 1
fi