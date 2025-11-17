#!/bin/bash
# Setup script for local development environment
# This script helps configure the necessary credentials and dependencies

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "KEN-E API Local Development Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f "$API_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp "$API_DIR/.env.example" "$API_DIR/.env"
    echo -e "${GREEN}✓${NC} Created .env file"
    echo "Please edit $API_DIR/.env with your configuration"
    echo ""
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}✗ gcloud CLI not found${NC}"
    echo "Please install gcloud CLI: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo -e "${GREEN}✓${NC} gcloud CLI found"
echo ""

# Check current gcloud auth
echo "Checking gcloud authentication..."
if ! gcloud auth application-default print-access-token &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not authenticated with gcloud${NC}"
    echo "Running: gcloud auth application-default login"
    echo ""
    gcloud auth application-default login
    echo ""
    echo -e "${GREEN}✓${NC} Authentication complete"
else
    echo -e "${GREEN}✓${NC} Already authenticated with gcloud"
fi

echo ""

# Get current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$CURRENT_PROJECT" ]; then
    echo -e "${YELLOW}⚠️  No default GCP project set${NC}"
    echo "Setting project to ken-e-dev..."
    gcloud config set project ken-e-dev
    CURRENT_PROJECT="ken-e-dev"
fi

echo "Current GCP project: ${GREEN}$CURRENT_PROJECT${NC}"
echo ""

# Test Secret Manager access
echo "Testing Secret Manager access..."
if gcloud secrets versions access latest --secret="sendgrid-api-key" --project="$CURRENT_PROJECT" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Successfully accessed sendgrid-api-key from Secret Manager"
else
    echo -e "${RED}✗ Failed to access Secret Manager${NC}"
    echo ""
    echo "Possible issues:"
    echo "  1. Secret 'sendgrid-api-key' doesn't exist in project $CURRENT_PROJECT"
    echo "  2. You don't have 'Secret Manager Secret Accessor' role"
    echo "  3. Secret Manager API is not enabled"
    echo ""
    echo "To check secrets: gcloud secrets list --project=$CURRENT_PROJECT"
    echo "To grant access: gcloud secrets add-iam-policy-binding sendgrid-api-key \\"
    echo "    --member=\"user:your-email@example.com\" \\"
    echo "    --role=\"roles/secretmanager.secretAccessor\" \\"
    echo "    --project=$CURRENT_PROJECT"
    echo ""
    exit 1
fi

echo ""

# Check Python environment
echo "Checking Python environment..."
if command -v uv &> /dev/null; then
    echo -e "${GREEN}✓${NC} uv found"
else
    echo -e "${YELLOW}⚠️  uv not found${NC}"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo ""

# Test email service configuration
echo "Testing email service configuration..."
cd "$API_DIR"
if python scripts/diagnose_email_service.py 2>&1 | grep -q "Email service appears to be configured correctly"; then
    echo -e "${GREEN}✓${NC} Email service configured correctly"
else
    echo -e "${YELLOW}⚠️  Email service may have issues${NC}"
    echo "Run: python api/scripts/diagnose_email_service.py"
    echo "to see detailed diagnostic information"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start the API server:"
echo "     cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "  2. Verify email service:"
echo "     python api/scripts/diagnose_email_service.py"
echo ""
echo "  3. Test invitation feature by inviting a user from the frontend"
echo ""
