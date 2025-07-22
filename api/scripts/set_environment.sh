#!/bin/bash

# Script to switch between different Neo4j environments

if [ $# -eq 0 ]; then
    echo "Usage: ./set_environment.sh [development|staging|production]"
    if [ -f .env ]; then
        current_env=$(grep ENVIRONMENT .env 2>/dev/null | cut -d'=' -f2)
        echo "Current environment: ${current_env:-'not set'}"
    else
        echo "Current environment: not set"
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
        cp .env.development .env
        echo "✅ Switched to DEVELOPMENT environment"
        echo "   Neo4j: Development Aura instance"
        echo "   Debug: Enabled"
        
        # Try to resolve secrets from Google Secret Manager
        if command -v python3 &> /dev/null; then
            echo "🔐 Resolving secrets from Google Secret Manager..."
            python3 scripts/resolve_secrets.py .env.development
        else
            echo "⚠️  Python not found, skipping secret resolution"
        fi
        ;;
    staging|stage)
        if [ ! -f .env.staging ]; then
            echo "❌ ERROR: .env.staging file not found"
            exit 1
        fi
        cp .env.staging .env
        echo "✅ Switched to STAGING environment"
        echo "   Neo4j: Staging Aura instance"
        echo "   Debug: Disabled"
        ;;
    production|prod)
        if [ ! -f .env.production ]; then
            echo "❌ ERROR: .env.production file not found"
            exit 1
        fi
        cp .env.production .env
        echo "⚠️  Switched to PRODUCTION environment"
        echo "   Neo4j: Production Aura instance"
        echo "   Debug: Disabled"
        echo "   WARNING: You are now connected to PRODUCTION!"
        ;;
    *)
        echo "❌ Invalid environment: $ENV"
        echo "   Valid options: development, staging, production"
        exit 1
        ;;
esac

# Show current Neo4j URI, Google Cloud Project, and reCAPTCHA status
echo "   Neo4j URI: $(grep NEO4J_URI .env | cut -d'=' -f2)"
echo "   GCP Project: $(grep GOOGLE_CLOUD_PROJECT_ID .env | cut -d'=' -f2)"
echo "   reCAPTCHA: $([ -n "$(grep RECAPTCHA_SITE_KEY .env | cut -d'=' -f2)" ] && echo 'Configured' || echo 'Not configured')"