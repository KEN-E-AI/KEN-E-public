#!/bin/bash

# Quick deployment script for ken-e-staging indexes
# Run this after authenticating with: gcloud auth login

PROJECT="ken-e-staging"

echo "Deploying Firestore indexes to $PROJECT..."
echo ""

# Index 1: Basic query
echo "Creating index 1/4: notifications (account_id + archived_at)..."
gcloud firestore indexes composite create \
  --collection-group=notifications \
  --field-config="field-path=account_id,order=ascending" \
  --field-config="field-path=archived_at,order=ascending" \
  --project=$PROJECT \
  --quiet

# Index 2: Sorted query with archive filter
echo "Creating index 2/4: notifications (account_id + archived_at + created_at DESC)..."
gcloud firestore indexes composite create \
  --collection-group=notifications \
  --field-config="field-path=account_id,order=ascending" \
  --field-config="field-path=archived_at,order=ascending" \
  --field-config="field-path=created_at,order=descending" \
  --project=$PROJECT \
  --quiet

# Index 3: Simple sorted without archive filter
echo "Creating index 3/4: notifications (account_id + created_at DESC)..."
gcloud firestore indexes composite create \
  --collection-group=notifications \
  --field-config="field-path=account_id,order=ascending" \
  --field-config="field-path=created_at,order=descending" \
  --project=$PROJECT \
  --quiet

# Index 4: Status index
echo "Creating index 4/4: notification_status (status)..."
gcloud firestore indexes composite create \
  --collection-group=notification_status \
  --field-config="field-path=status,order=ascending" \
  --project=$PROJECT \
  --quiet

echo ""
echo "✅ Index creation commands sent to $PROJECT"
echo ""
echo "To check index status, run:"
echo "  gcloud firestore indexes composite list --project=$PROJECT"
echo ""
echo "Note: Indexes may take 2-10 minutes to become active."