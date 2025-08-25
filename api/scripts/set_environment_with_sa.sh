#!/bin/bash

# Modified environment switching script that uses service account credentials
# This avoids the need for Application Default Credentials (ADC)

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
API_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Service account files
DEVELOPMENT_SA="$API_DIR/ken-e-dev-sa.json"
STAGING_SA="$API_DIR/ken-e-staging-sa.json"
PRODUCTION_SA="$API_DIR/ken-e-production-sa.json"

# Helper function to set service account
set_service_account() {
    local sa_file=$1
    local env_name=$2
    
    if [ -f "$sa_file" ]; then
        export GOOGLE_APPLICATION_CREDENTIALS="$sa_file"
        echo "✅ Using service account: $sa_file"
        return 0
    else
        echo "⚠️  Service account file not found: $sa_file"
        echo "   Falling back to Application Default Credentials"
        unset GOOGLE_APPLICATION_CREDENTIALS
        return 1
    fi
}

# Helper function to run resolve_secrets.py with service account
resolve_secrets_with_sa() {
    local env_file=$1
    local sa_file=$2
    
    # Export the service account path for the Python script
    export GOOGLE_APPLICATION_CREDENTIALS="$sa_file"
    
    # Run the resolve secrets script
    if command -v uv &> /dev/null; then
        uv run python "$SCRIPT_DIR/resolve_secrets.py" "$env_file"
    else
        python3 "$SCRIPT_DIR/resolve_secrets.py" "$env_file"
    fi
    
    return $?
}

if [ $# -eq 0 ]; then
    echo "Usage: ./set_environment_with_sa.sh [development|staging|production]"
    echo ""
    echo "This script uses service account files instead of ADC when available:"
    echo "  - Development: $DEVELOPMENT_SA"
    echo "  - Staging: $STAGING_SA"
    echo "  - Production: $PRODUCTION_SA"
    echo ""
    if [ -f .env ]; then
        current_env=$(grep ENVIRONMENT .env 2>/dev/null | cut -d'=' -f2)
        echo "Current environment: ${current_env:-'not set'}"
    fi
    exit 1
fi

ENV=$1

case $ENV in
    development|dev)
        if [ ! -f .env.development ]; then
            echo "❌ ERROR: .env.development file not found"
            exit 1
        fi
        
        # Check for development service account
        if [ -f "$DEVELOPMENT_SA" ]; then
            echo "🔐 Found development service account file"
            
            # Copy development env
            cp .env.development .env
            
            # Resolve secrets using service account if needed
            echo "🔐 Setting up development environment..."
            
            # Add service account path to .env
            echo "" >> .env
            echo "# Service Account Configuration" >> .env
            echo "GOOGLE_APPLICATION_CREDENTIALS=$DEVELOPMENT_SA" >> .env
            
            echo "✅ Switched to DEVELOPMENT environment with service account"
            echo "   Service Account: $DEVELOPMENT_SA"
        else
            # Development doesn't typically need secrets from Secret Manager
            cp .env.development .env
            echo "✅ Switched to DEVELOPMENT environment"
            echo "   Using local development credentials"
        fi
        ;;
        
    staging|stage)
        if [ ! -f .env.staging ]; then
            echo "❌ ERROR: .env.staging file not found"
            exit 1
        fi
        
        # Check for staging service account
        if [ -f "$STAGING_SA" ]; then
            echo "🔐 Found staging service account file"
            
            # Copy staging env
            cp .env.staging .env
            
            # Resolve secrets using service account
            echo "🔐 Resolving secrets using service account..."
            if resolve_secrets_with_sa .env.staging "$STAGING_SA"; then
                echo "✅ Switched to STAGING environment with service account"
                echo "   Service Account: $STAGING_SA"
                echo "   Secrets resolved successfully"
                
                # Add service account path to .env
                echo "" >> .env
                echo "# Service Account Configuration" >> .env
                echo "GOOGLE_APPLICATION_CREDENTIALS=$STAGING_SA" >> .env
            else
                echo "❌ Failed to resolve secrets"
                rm -f .env
                exit 1
            fi
        else
            echo "⚠️  No service account file found at: $STAGING_SA"
            echo "   You'll need to use ADC or create a local env file"
            exit 1
        fi
        ;;
        
    production|prod)
        if [ ! -f .env.production ]; then
            echo "❌ ERROR: .env.production file not found"
            exit 1
        fi
        
        # Check for production service account
        if [ -f "$PRODUCTION_SA" ]; then
            echo "🔐 Found production service account file"
            
            # Copy production env
            cp .env.production .env
            
            # Resolve secrets using service account
            echo "🔐 Resolving secrets using service account..."
            if resolve_secrets_with_sa .env.production "$PRODUCTION_SA"; then
                echo "✅ Switched to PRODUCTION environment with service account"
                echo "   Service Account: $PRODUCTION_SA"
                echo "   ⚠️  WARNING: You are now connected to PRODUCTION!"
                
                # Add service account path to .env
                echo "" >> .env
                echo "# Service Account Configuration" >> .env
                echo "GOOGLE_APPLICATION_CREDENTIALS=$PRODUCTION_SA" >> .env
            else
                echo "❌ Failed to resolve secrets"
                rm -f .env
                exit 1
            fi
        else
            echo "⚠️  No service account file found at: $PRODUCTION_SA"
            echo "   Using original script behavior..."
            # Fall back to original script
            exec "$SCRIPT_DIR/set_environment.sh" "$ENV"
        fi
        ;;
        
    *)
        echo "❌ Invalid environment: $ENV"
        echo "   Valid options: development, staging, production"
        exit 1
        ;;
esac

# Show current configuration
echo ""
echo "Configuration:"
echo "   Environment: $(grep ENVIRONMENT .env | cut -d'=' -f2)"
echo "   Neo4j URI: $(grep NEO4J_URI .env | cut -d'=' -f2)"
echo "   GCP Project: $(grep GOOGLE_CLOUD_PROJECT_ID .env | cut -d'=' -f2)"
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "   Service Account: $GOOGLE_APPLICATION_CREDENTIALS"
fi