#!/bin/bash

# Script to properly restart frontend with fresh environment

echo "🔄 Restarting frontend with fresh environment..."

# Kill any existing frontend processes
echo "Stopping existing processes..."
pkill -f "npm run dev" || true
pkill -f "vite" || true

# Clear all caches
echo "Clearing caches..."
rm -rf node_modules/.vite
rm -rf .vite
rm -rf node_modules/.cache

# Verify environment
echo "Current environment:"
grep -E "(VITE_ENVIRONMENT|VITE_RECAPTCHA_SITE_KEY)" .env.local

# Start fresh
echo "Starting frontend..."
npm run dev