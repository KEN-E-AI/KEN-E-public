#!/bin/bash

# Script to switch between different Neo4j environments

if [ $# -eq 0 ]; then
    echo "Usage: ./set_environment.sh [development|staging|production]"
    echo "Current environment: $([ -f .env ] && grep ENVIRONMENT .env | cut -d'=' -f2 || echo 'not set')"
    exit 1
fi

ENV=$1

case $ENV in
    development|dev)
        cp .env.development .env
        echo "✅ Switched to DEVELOPMENT environment"
        echo "   Neo4j: Development Aura instance"
        echo "   Debug: Enabled"
        ;;
    staging|stage)
        cp .env.staging .env
        echo "✅ Switched to STAGING environment"
        echo "   Neo4j: Staging Aura instance"
        echo "   Debug: Disabled"
        ;;
    production|prod)
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

# Show current Neo4j URI (without password)
echo "   URI: $(grep NEO4J_URI .env | cut -d'=' -f2)"