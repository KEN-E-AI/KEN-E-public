#!/bin/bash

# Script to start frontend on a fresh port with staging environment

echo "🚀 Starting frontend on port 3000 with staging environment..."

# Kill any existing processes
echo "Stopping any existing processes..."
pkill -f "npm run dev" || true
pkill -f vite || true
lsof -ti:8080 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Clear all caches
echo "Clearing all caches..."
rm -rf node_modules/.vite
rm -rf .vite  
rm -rf node_modules/.cache
rm -rf dist

# Ensure staging environment
echo "Setting staging environment..."
./scripts/set_environment.sh staging

# Verify environment
echo ""
echo "Environment configuration:"
echo "========================="
grep -E "(VITE_ENVIRONMENT|VITE_RECAPTCHA_SITE_KEY|VITE_API_BASE_URL)" .env.local
echo "========================="
echo ""

# Export port to ensure Vite uses it
export PORT=3000

# Start on port 3000
echo "Starting frontend on http://localhost:3000"
npm run dev -- --port 3000 --host