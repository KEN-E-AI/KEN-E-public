#!/bin/bash
# Quick fix script to add VPC connector to running Cloud Run services

echo "🔧 Fixing Redis connectivity with VPC Connectors"
echo "================================================"

# Production
echo -e "\n📦 Updating PRODUCTION service with VPC connector..."
gcloud run services update kene-api-prod \
  --project=ken-e-production \
  --region=us-central1 \
  --vpc-connector=ken-e-production-connector

if [ $? -eq 0 ]; then
  echo "✅ Production service updated successfully"
else
  echo "❌ Failed to update production service"
fi

# Staging
echo -e "\n📦 Updating STAGING service with VPC connector..."
gcloud run services update kene-api-staging \
  --project=ken-e-staging \
  --region=us-central1 \
  --vpc-connector=ken-e-staging-connector

if [ $? -eq 0 ]; then
  echo "✅ Staging service updated successfully"
else
  echo "❌ Failed to update staging service"
fi

echo -e "\n✨ VPC Connector fix applied!"
echo "Wait 1-2 minutes for changes to propagate, then test again."