#!/bin/bash

# Quick script to switch to staging using service account credentials

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

# Export the service account path
export GOOGLE_APPLICATION_CREDENTIALS="$SA_FILE"

# Now run the regular set_environment script
# The resolve_secrets.py script will automatically use GOOGLE_APPLICATION_CREDENTIALS
"$SCRIPT_DIR/set_environment.sh" staging

# Check if it succeeded
if [ $? -eq 0 ]; then
    # Add the service account path to .env so the API can use it
    echo "" >> "$API_DIR/.env"
    echo "# Service Account Configuration (added by use_staging_with_sa.sh)" >> "$API_DIR/.env"
    echo "GOOGLE_APPLICATION_CREDENTIALS=$SA_FILE" >> "$API_DIR/.env"
    
    echo ""
    echo "✅ Successfully configured staging with service account!"
    echo ""
    echo "The API will now use the service account for all Google Cloud operations."
    echo "You can start the API with: uv run -- uvicorn src.kene_api.main:app --reload"
else
    echo ""
    echo "❌ Failed to configure staging environment"
    echo ""
    echo "If you're still getting Secret Manager errors, try:"
    echo "1. Verify the service account has Secret Manager permissions"
    echo "2. Use the create_local_staging_env.py script instead"
fi