#!/bin/bash

# Script to check and update authorized domains for Firebase/Identity Platform

echo "=== Checking Authorization Domains ==="
echo ""

# Function to check which domain the user is testing from
check_current_domain() {
    echo "Which domain are you testing from?"
    echo "1. localhost:8080 (local development)"
    echo "2. Staging domain"
    echo "3. Production domain (ken-e.ai or app.ken-e.ai)"
    echo "4. Other domain"
    read -p "Enter your choice (1-4): " choice
    
    case $choice in
        1)
            DOMAIN="localhost"
            PORT="8080"
            ;;
        2)
            read -p "Enter your staging domain: " DOMAIN
            ;;
        3)
            DOMAIN="ken-e.ai"
            ;;
        4)
            read -p "Enter the domain: " DOMAIN
            ;;
    esac
}

# Function to add authorized domain using Firebase CLI
add_authorized_domain() {
    PROJECT=$1
    DOMAIN=$2
    
    echo "Adding $DOMAIN to authorized domains for $PROJECT..."
    
    # Using firebase CLI if available
    if command -v firebase &> /dev/null; then
        firebase auth:import --project $PROJECT <<EOF
{
  "authorizedDomains": ["$DOMAIN"]
}
EOF
    else
        echo "Firebase CLI not found. Please install it with: npm install -g firebase-tools"
        echo ""
        echo "Alternative: Add the domain manually in the console:"
        echo "https://console.firebase.google.com/project/$PROJECT/authentication/settings"
    fi
}

# Main execution
check_current_domain

echo ""
echo "=== Current Setup ==="
echo "Testing from: $DOMAIN${PORT:+:$PORT}"
echo ""

# Check staging
echo "For staging (ken-e-staging):"
echo "1. Go to: https://console.firebase.google.com/project/ken-e-staging/authentication/settings"
echo "2. OR: https://console.cloud.google.com/customer-identity/settings?project=ken-e-staging"
echo "3. Add these authorized domains:"
echo "   - localhost"
echo "   - $DOMAIN${PORT:+:$PORT}"
echo "   - ken-e-staging.firebaseapp.com"
echo "   - ken-e-staging.web.app"
echo ""

# Check production
echo "For production (ken-e-production):"
echo "1. Go to: https://console.firebase.google.com/project/ken-e-production/authentication/settings"
echo "2. OR: https://console.cloud.google.com/customer-identity/settings?project=ken-e-production"
echo "3. Add these authorized domains:"
echo "   - ken-e.ai"
echo "   - app.ken-e.ai"
echo "   - $DOMAIN${PORT:+:$PORT}"
echo "   - ken-e-production.firebaseapp.com"
echo "   - ken-e-production.web.app"
echo ""

# Try to use gcloud to check current settings
echo "=== Checking with gcloud ==="
for PROJECT in ken-e-staging ken-e-production; do
    echo ""
    echo "Project: $PROJECT"
    echo "Checking Identity Platform providers..."
    gcloud alpha identity-toolkit providers list --project=$PROJECT 2>/dev/null || echo "Identity Platform CLI not available"
done

echo ""
echo "=== Quick Fix Steps ==="
echo "1. The 'auth/unauthorized-domain' error means your domain isn't authorized"
echo "2. You need to add your domain to the authorized domains list in Firebase/Identity Platform"
echo "3. This is done in the Firebase Console or Google Cloud Console (links above)"
echo "4. After adding the domain, wait 1-2 minutes for changes to propagate"
echo "5. Clear your browser cache and try again"