# Firestore Indexes Deployment Guide

## Overview

This guide explains how to deploy Firestore indexes for the improved notification system across all KEN-E environments.

## Required Indexes

The notification system requires the following composite indexes to function efficiently:

### 1. **Basic Query Index** (existing)
- Collection: `notifications`
- Fields:
  - `account_id` (ASCENDING)
  - `archived_at` (ASCENDING)
- Purpose: Filter notifications by account and archive status

### 2. **Sorted Query Index** (new)
- Collection: `notifications`
- Fields:
  - `account_id` (ASCENDING)
  - `archived_at` (ASCENDING)
  - `created_at` (DESCENDING)
- Purpose: Filter and sort notifications for paginated results

### 3. **Simple Sorted Index** (new)
- Collection: `notifications`
- Fields:
  - `account_id` (ASCENDING)
  - `created_at` (DESCENDING)
- Purpose: Sort all notifications (including archived) by creation date

### 4. **Status Index** (existing)
- Collection: `notification_status`
- Fields:
  - `status` (ASCENDING)
- Purpose: Query notification statuses

## Deployment Methods

### Method 1: Using Firebase CLI (Recommended)

1. **Install Firebase CLI** (if not already installed):
   ```bash
   npm install -g firebase-tools
   ```

2. **Login to Firebase**:
   ```bash
   firebase login
   ```

3. **Deploy to each environment**:

   **Development:**
   ```bash
   firebase use ken-e-dev
   firebase firestore:indexes:deploy deployment/firestore.indexes.json
   ```

   **Staging:**
   ```bash
   firebase use ken-e-staging
   firebase firestore:indexes:deploy deployment/firestore.indexes.json
   ```

   **Production:**
   ```bash
   firebase use ken-e-production
   firebase firestore:indexes:deploy deployment/firestore.indexes.json
   ```

### Method 2: Using gcloud CLI

1. **Authenticate with gcloud**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Deploy indexes individually to each environment**:

   **Note**: gcloud requires creating each index individually. Run these commands for each environment (replace `PROJECT_ID` with `ken-e-dev`, `ken-e-staging`, or `ken-e-production`):

   ```bash
   # Index 1: Basic query (account_id + archived_at)
   gcloud firestore indexes composite create \
     --collection-group=notifications \
     --field-config field-path=account_id,order=ascending \
     --field-config field-path=archived_at,order=ascending \
     --project=PROJECT_ID

   # Index 2: Sorted query (account_id + archived_at + created_at DESC)
   gcloud firestore indexes composite create \
     --collection-group=notifications \
     --field-config field-path=account_id,order=ascending \
     --field-config field-path=archived_at,order=ascending \
     --field-config field-path=created_at,order=descending \
     --project=PROJECT_ID

   # Index 3: Simple sorted (account_id + created_at DESC)
   gcloud firestore indexes composite create \
     --collection-group=notifications \
     --field-config field-path=account_id,order=ascending \
     --field-config field-path=created_at,order=descending \
     --project=PROJECT_ID

   # Index 4: Status index
   gcloud firestore indexes composite create \
     --collection-group=notification_status \
     --field-config field-path=status,order=ascending \
     --project=PROJECT_ID
   ```

   **Full example for ken-e-staging:**
   ```bash
   # Create all indexes for staging
   gcloud firestore indexes composite create --collection-group=notifications --field-config field-path=account_id,order=ascending --field-config field-path=archived_at,order=ascending --project=ken-e-staging

   gcloud firestore indexes composite create --collection-group=notifications --field-config field-path=account_id,order=ascending --field-config field-path=archived_at,order=ascending --field-config field-path=created_at,order=descending --project=ken-e-staging

   gcloud firestore indexes composite create --collection-group=notifications --field-config field-path=account_id,order=ascending --field-config field-path=created_at,order=descending --project=ken-e-staging

   gcloud firestore indexes composite create --collection-group=notification_status --field-config field-path=status,order=ascending --project=ken-e-staging
   ```

### Method 3: Using the Deployment Script

We've provided a script that automates the deployment:

```bash
cd deployment
./deploy-firestore-indexes.sh
```

The script will:
1. Check for proper authentication
2. Deploy indexes to all three environments
3. Provide status updates
4. Report any failures

### Method 4: Manual Creation via Console

If CLI access is not available, indexes can be created manually:

1. Go to the [Firebase Console](https://console.firebase.google.com)
2. Select your project (ken-e-dev, ken-e-staging, or ken-e-production)
3. Navigate to **Firestore Database** → **Indexes**
4. Click **Create Index**
5. Add each index with the specifications above

## Verification

After deployment, verify that indexes are active:

### Using CLI:
```bash
# List indexes for each project
gcloud firestore indexes composite list --project=ken-e-dev
gcloud firestore indexes composite list --project=ken-e-staging
gcloud firestore indexes composite list --project=ken-e-production
```

### Using Console:
1. Go to [Firestore Indexes Console](https://console.cloud.google.com/firestore/indexes)
2. Select your project
3. Verify all indexes show status: **Enabled**

## Index Build Time

- New indexes typically take 2-10 minutes to build
- Large collections may take longer
- The system will use fallback queries (without sorting) until indexes are ready

## Troubleshooting

### Error: "The query requires an index"
- The index is still building or missing
- Check index status in the console
- Redeploy if necessary

### Error: "Permission denied"
- Ensure you have `Firebase Admin` or `Editor` role in the project
- Re-authenticate: `gcloud auth login`

### Error: "Index already exists"
- This is safe to ignore - existing indexes won't be duplicated
- The deployment will update any changed indexes

## Testing After Deployment

Once indexes are deployed and active, test the notification system:

1. **Check API logs** for any Firestore index warnings:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND \
     textPayload:'Firestore query failed'" \
     --project=ken-e-staging --limit=10
   ```

2. **Test notification endpoints**:
   ```bash
   # Get notifications (should use the new indexes)
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.ken-e.ai/api/v1/notifications?limit=10
   ```

3. **Monitor performance** in the Firestore console to ensure indexes are being used

## Important Notes

1. **Backward Compatibility**: The new indexes are backward compatible with existing queries
2. **No Downtime**: Index deployment doesn't cause any service interruption
3. **Automatic Fallback**: If an index is missing, the code falls back to simpler queries
4. **Cost**: Composite indexes have minimal storage cost but significantly improve query performance

## Support

If you encounter issues during deployment:
1. Check the Firestore console for index status
2. Review API logs for any warnings
3. Ensure you have proper IAM permissions
4. Contact the platform team for assistance