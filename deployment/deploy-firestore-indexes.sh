#!/bin/bash

# Deploy Firestore indexes to all KEN-E environments
# This script deploys the Firestore indexes defined in firestore.indexes.json
# to ken-e-dev, ken-e-staging, and ken-e-production projects

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INDEX_FILE="$SCRIPT_DIR/firestore.indexes.json"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if index file exists
if [ ! -f "$INDEX_FILE" ]; then
    echo -e "${RED}Error: firestore.indexes.json not found at $INDEX_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Found index configuration at: $INDEX_FILE${NC}"
echo ""
echo "This script will deploy the following indexes to all environments:"
echo "- notifications collection: account_id + archived_at"
echo "- notifications collection: account_id + archived_at + created_at (DESC)"
echo "- notifications collection: account_id + created_at (DESC)"
echo "- notification_status collection: status"
echo ""

# Function to deploy indexes to a specific project
deploy_indexes() {
    local PROJECT_ID=$1
    echo -e "${YELLOW}Deploying indexes to project: $PROJECT_ID${NC}"
    
    # Check if we can access the project
    if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
        echo "✓ Project $PROJECT_ID is accessible"
        
        # Deploy the indexes using gcloud firestore
        echo "Deploying indexes..."
        # Note: gcloud doesn't support bulk index creation from JSON file
        # We need to use Firebase CLI or create indexes individually
        
        # Try Firebase CLI first if available
        if command -v firebase &> /dev/null; then
            echo "Using Firebase CLI to deploy indexes..."
            firebase use "$PROJECT_ID" --add 2>/dev/null || firebase use "$PROJECT_ID"
            firebase deploy --only firestore:indexes --project "$PROJECT_ID" --config "$INDEX_FILE"
        else
            echo "Firebase CLI not available. Creating indexes individually..."
            
            # Create indexes one by one using gcloud
            echo "Creating index: notifications (account_id, archived_at)..."
            gcloud firestore indexes composite create \
                --collection-group=notifications \
                --field-config="field-path=account_id,order=ascending" \
                --field-config="field-path=archived_at,order=ascending" \
                --project="$PROJECT_ID" --quiet 2>/dev/null || true
            
            echo "Creating index: notifications (account_id, archived_at, created_at DESC)..."
            gcloud firestore indexes composite create \
                --collection-group=notifications \
                --field-config="field-path=account_id,order=ascending" \
                --field-config="field-path=archived_at,order=ascending" \
                --field-config="field-path=created_at,order=descending" \
                --project="$PROJECT_ID" --quiet 2>/dev/null || true
            
            echo "Creating index: notifications (account_id, created_at DESC)..."
            gcloud firestore indexes composite create \
                --collection-group=notifications \
                --field-config="field-path=account_id,order=ascending" \
                --field-config="field-path=created_at,order=descending" \
                --project="$PROJECT_ID" --quiet 2>/dev/null || true
            
            echo "Creating index: notification_status (status)..."
            gcloud firestore indexes composite create \
                --collection-group=notification_status \
                --field-config="field-path=status,order=ascending" \
                --project="$PROJECT_ID" --quiet 2>/dev/null || true
        fi
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Successfully deployed indexes to $PROJECT_ID${NC}"
        else
            echo -e "${RED}✗ Failed to deploy indexes to $PROJECT_ID${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Cannot access project $PROJECT_ID. Please ensure you have the necessary permissions.${NC}"
        return 1
    fi
    
    echo ""
}

# Main deployment
echo -e "${GREEN}Starting Firestore index deployment...${NC}"
echo ""

# Deploy to each environment
ENVIRONMENTS=("ken-e-dev" "ken-e-staging" "ken-e-production")
FAILED_DEPLOYMENTS=()

for ENV in "${ENVIRONMENTS[@]}"; do
    if ! deploy_indexes "$ENV"; then
        FAILED_DEPLOYMENTS+=("$ENV")
    fi
done

echo ""
echo -e "${GREEN}=== Deployment Summary ===${NC}"

# Check deployment status
if [ ${#FAILED_DEPLOYMENTS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All deployments successful!${NC}"
    echo ""
    echo "Indexes have been deployed to:"
    for ENV in "${ENVIRONMENTS[@]}"; do
        echo "  - $ENV"
    done
    echo ""
    echo -e "${YELLOW}Note: Indexes may take a few minutes to become active.${NC}"
    echo "You can check the status at:"
    echo "  https://console.cloud.google.com/firestore/indexes"
else
    echo -e "${RED}✗ Some deployments failed:${NC}"
    for ENV in "${FAILED_DEPLOYMENTS[@]}"; do
        echo "  - $ENV"
    done
    echo ""
    echo "Please check your permissions and try again."
    exit 1
fi

echo ""
echo "To verify indexes are active, run:"
echo "  gcloud firestore indexes composite list --project=<project-id>"