#!/bin/bash

# Script to switch between different frontend environments

if [ $# -eq 0 ]; then
    echo "Usage: ./set_environment.sh [development|staging|production]"
    echo "Current environment: $([ -f .env.local ] && grep VITE_ENVIRONMENT .env.local | cut -d'=' -f2 || echo 'not set')"
    exit 1
fi

ENV=$1

case $ENV in
    development|dev)
        if [ ! -f .env.development ]; then
            echo "❌ ERROR: .env.development file not found"
            exit 1
        fi
        cp .env.development .env.local
        echo "✅ Switched to DEVELOPMENT environment"
        echo "   API: http://localhost:8000"
        echo "   Firebase: ken-e-dev"
        echo ""
        echo "   Run the dev server with: npm run dev:development"
        ;;
    staging|stage)
        if [ ! -f .env.staging ]; then
            echo "❌ ERROR: .env.staging file not found"
            exit 1
        fi
        cp .env.staging .env.local
        echo "✅ Switched to STAGING environment"
        echo "   API: http://localhost:8000"
        echo "   Firebase: ken-e-staging"
        echo ""
        echo "   Run the dev server with: npm run dev:staging"
        ;;
    production|prod)
        if [ ! -f .env.production ]; then
            echo "❌ ERROR: .env.production file not found"
            exit 1
        fi
        cp .env.production .env.local
        echo "⚠️  Switched to PRODUCTION environment"
        echo "   API: https://api.ken-e.ai"
        echo "   Firebase: ken-e-production"
        echo "   WARNING: You are now connected to PRODUCTION!"
        echo ""
        echo "   Run the dev server with: npm run dev:production"
        ;;
    *)
        echo "❌ Invalid environment: $ENV"
        echo "   Valid options: development, staging, production"
        exit 1
        ;;
esac

# Show current API URL, Firebase project, and reCAPTCHA status
echo "   API URL: $(grep VITE_API_BASE_URL .env.local | cut -d'=' -f2)"
echo "   Firebase Project: $(grep VITE_FIREBASE_PROJECT_ID .env.local | cut -d'=' -f2)"
echo "   reCAPTCHA: $([ -n "$(grep VITE_RECAPTCHA_SITE_KEY .env.local | cut -d'=' -f2)" ] && echo 'Configured' || echo 'Not configured')"