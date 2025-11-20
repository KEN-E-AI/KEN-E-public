#!/bin/bash
# Start the development API server with proper environment configuration
# This script ensures GOOGLE_CLOUD_PROJECT is set for Secret Manager access

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Starting KEN-E API Development Server"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$API_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Run: ./api/scripts/setup_local_dev.sh"
    exit 1
fi

# Set GOOGLE_CLOUD_PROJECT for Secret Manager
# This is needed for sm:// secret references to work
export GOOGLE_CLOUD_PROJECT=ken-e-dev

echo -e "${GREEN}✓${NC} Environment: ken-e-dev"
echo -e "${GREEN}✓${NC} Working directory: $API_DIR"
echo ""

# Check if authenticated
if ! gcloud auth application-default print-access-token &> /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Not authenticated with gcloud${NC}"
    echo "Run: gcloud auth application-default login"
    echo "Or use direct API key in .env instead of sm:// reference"
    echo ""
fi

echo "Starting uvicorn server..."
echo "Server will be available at: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$API_DIR"
uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
