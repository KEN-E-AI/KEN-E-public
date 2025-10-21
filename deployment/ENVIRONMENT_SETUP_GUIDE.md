# Environment Setup Guide

This guide explains how to set up staging and production environments with proper Secret Manager integration.

## Overview

The KEN-E application uses Google Secret Manager to securely store sensitive credentials. Each environment (dev, staging, production) has its own isolated secrets.

---

## Prerequisites

- Access to GCP projects: `ken-e-dev`, `ken-e-staging`, `ken-e-production`
- `gcloud` CLI authenticated with appropriate permissions
- Secret Manager Admin role on all three projects

---

## Secrets Requiring Manual Setup Per Environment

The following secrets need environment-specific values and cannot be copied between environments:

### 1. Google OAuth 2.0 Credentials

**Purpose:** Enable Google Analytics integration via OAuth

**Why environment-specific:** Each environment has different redirect URIs

**Setup Steps:**

#### For Staging (ken-e-staging):

```bash
# 1. Create OAuth 2.0 Client in GCP Console
# Go to: https://console.cloud.google.com/apis/credentials?project=ken-e-staging
# Click: "Create Credentials" → "OAuth 2.0 Client ID"
# Application type: "Web application"
# Name: "KEN-E Staging OAuth Client"
# Authorized redirect URIs: https://staging-api.ken-e.ai/api/oauth/callback/google

# 2. Copy the generated Client ID and Client Secret

# 3. Create secrets in Secret Manager:
echo "YOUR_STAGING_CLIENT_ID" | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID \
  --data-file=- --project=ken-e-staging

echo "YOUR_STAGING_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET \
  --data-file=- --project=ken-e-staging
```

#### For Production (ken-e-production):

```bash
# 1. Create OAuth 2.0 Client in GCP Console
# Go to: https://console.cloud.google.com/apis/credentials?project=ken-e-production
# Click: "Create Credentials" → "OAuth 2.0 Client ID"
# Application type: "Web application"
# Name: "KEN-E Production OAuth Client"
# Authorized redirect URIs: https://api.ken-e.ai/api/oauth/callback/google

# 2. Copy the generated Client ID and Client Secret

# 3. Create secrets in Secret Manager:
echo "YOUR_PRODUCTION_CLIENT_ID" | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID \
  --data-file=- --project=ken-e-production

echo "YOUR_PRODUCTION_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET \
  --data-file=- --project=ken-e-production
```

---

### 2. Encryption Key

**Purpose:** Encrypt OAuth tokens and sensitive credentials in database

**Why environment-specific:** Security isolation between environments

**Setup Steps:**

#### For Staging:

```bash
# 1. Generate a unique encryption key
STAGING_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Create secret in Secret Manager
echo "$STAGING_KEY" | gcloud secrets create ENCRYPTION_KEY \
  --data-file=- --project=ken-e-staging

# 3. IMPORTANT: Back up this key securely!
# Store it in your password manager or secure documentation
```

#### For Production:

```bash
# 1. Generate a DIFFERENT unique encryption key
PRODUCTION_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 2. Create secret in Secret Manager
echo "$PRODUCTION_KEY" | gcloud secrets create ENCRYPTION_KEY \
  --data-file=- --project=ken-e-production

# 3. CRITICAL: Back up this key in multiple secure locations!
# Production key loss = permanent data loss for encrypted credentials
```

---

## Secrets Already Standardized

These secrets have been created/standardized across all environments and are ready to use:

| Secret Name | Purpose | Dev | Staging | Production |
|-------------|---------|-----|---------|------------|
| NEO4J_URI | Neo4j connection string | ✅ | ✅ | ✅ |
| NEO4J_USERNAME | Neo4j username | ✅ | ✅ | ✅ |
| NEO4J_PASSWORD | Neo4j password | ✅ | ✅ | ✅ |
| OPENAI_API_KEY | OpenAI API key | ✅ | ✅ | ✅ |
| wandb_api_key | W&B observability | ✅ | ✅ | ✅ |
| recaptcha-site-key | reCAPTCHA public key | ✅ | ✅ | ✅ |
| recaptcha-secret-key | reCAPTCHA private key | ✅ | ✅ | ✅ |
| sendgrid-api-key | Email service | ✅ | ✅ | ✅ |
| superset-password | Superset dashboard | ✅ | ✅ | ✅ |
| ken-e-engine-id | KEN-E chat agent | ✅ | ✅ | ✅ |
| strategy-supervisor-engine-id | Strategy agent | ✅ | ✅ | ✅ |

---

## Environment Configuration Files

After creating secrets, update your environment-specific .env files:

### Staging (.env.staging)

```bash
# Use Secret Manager for all sensitive values
NEO4J_URI=sm://NEO4J_URI
NEO4J_USERNAME=sm://NEO4J_USERNAME
NEO4J_PASSWORD=sm://NEO4J_PASSWORD
OPENAI_API_KEY=sm://OPENAI_API_KEY
GOOGLE_OAUTH_CLIENT_SECRET=sm://GOOGLE_OAUTH_CLIENT_SECRET
ENCRYPTION_KEY=sm://ENCRYPTION_KEY
RECAPTCHA_SECRET_KEY=sm://recaptcha-secret-key
SUPERSET_PASSWORD=sm://superset-password
SENDGRID_API_KEY=sm://sendgrid-api-key
WANDB_API_KEY=sm://wandb_api_key

# Environment-specific non-sensitive values
ENVIRONMENT=staging
GOOGLE_OAUTH_REDIRECT_URI=https://staging-api.ken-e.ai/api/oauth/callback/google
FRONTEND_URL=https://staging.ken-e.ai
```

### Production (.env.production)

```bash
# Use Secret Manager for all sensitive values
NEO4J_URI=sm://NEO4J_URI
NEO4J_USERNAME=sm://NEO4J_USERNAME
NEO4J_PASSWORD=sm://NEO4J_PASSWORD
OPENAI_API_KEY=sm://OPENAI_API_KEY
GOOGLE_OAUTH_CLIENT_SECRET=sm://GOOGLE_OAUTH_CLIENT_SECRET
ENCRYPTION_KEY=sm://ENCRYPTION_KEY
RECAPTCHA_SECRET_KEY=sm://recaptcha-secret-key
SUPERSET_PASSWORD=sm://superset-password
SENDGRID_API_KEY=sm://sendgrid-api-key
WANDB_API_KEY=sm://wandb_api_key

# Environment-specific non-sensitive values
ENVIRONMENT=production
GOOGLE_OAUTH_REDIRECT_URI=https://api.ken-e.ai/api/oauth/callback/google
FRONTEND_URL=https://ken-e.ai
```

---

## Verification Checklist

After setup, verify each environment:

### Check Secret Manager Secrets

```bash
# List all secrets
gcloud secrets list --project=ken-e-staging --format="value(name)" | sort

# Test accessing a secret
gcloud secrets versions access latest --secret="ENCRYPTION_KEY" --project=ken-e-staging
```

### Test Application Startup

```bash
# Deploy to Cloud Run or Agent Engine
# Check logs for:
# - ✅ "Loaded environment variables"
# - ✅ "Firestore service initialized"
# - ✅ "Neo4j connection established"
# - ❌ NO errors about missing secrets or failed authentication
```

### Test OAuth Flow

1. Navigate to settings page
2. Click "Connect Google Analytics"
3. Verify redirect to Google OAuth consent screen
4. Verify successful callback and property selection

---

## Cleanup: Old/Duplicate Secrets

After verification, these old secrets can be deleted:

### Staging:
```bash
# Delete old kebab-case Neo4j password (replaced by NEO4J_PASSWORD)
gcloud secrets delete neo4j-password --project=ken-e-staging --quiet
```

### Production:
```bash
# Delete old Neo4j password
gcloud secrets delete neo4j-password --project=ken-e-production --quiet

# Delete old PascalCase OpenAI key (replaced by OPENAI_API_KEY)
gcloud secrets delete Open-AI-API-Key --project=ken-e-production --quiet
```

---

## Troubleshooting

### "Secret not found" errors

**Check:**
1. Secret exists: `gcloud secrets list --project=PROJECT_ID | grep SECRET_NAME`
2. Application has permissions: Check service account IAM roles
3. Correct project ID in `GOOGLE_CLOUD_PROJECT_ID` env var

### "Failed to decrypt credentials" errors

**Possible causes:**
1. ENCRYPTION_KEY changed (credentials encrypted with old key)
2. Different ENCRYPTION_KEY used between app instances
3. ENCRYPTION_KEY not in Secret Manager

**Solution:**
- Use same ENCRYPTION_KEY across all instances in same environment
- Re-connect OAuth integrations to re-encrypt with current key

### OAuth redirect mismatch errors

**Check:**
1. GOOGLE_OAUTH_REDIRECT_URI in .env matches OAuth client configuration
2. OAuth client has the redirect URI in authorized list
3. Correct OAuth client ID for this environment

---

## Security Best Practices

1. ✅ **Use Secret Manager for all sensitive values** (passwords, API keys, secrets)
2. ✅ **Generate unique credentials per environment** (OAuth clients, encryption keys)
3. ✅ **Never copy secrets between environments**
4. ✅ **Back up encryption keys securely** (password manager, encrypted storage)
5. ✅ **Rotate secrets periodically** (every 90 days recommended)
6. ✅ **Audit secret access** (Cloud Audit Logs)
7. ✅ **Use least-privilege IAM** (grant only necessary permissions)

---

## Contact

For questions about environment setup, contact the platform team or refer to:
- Main documentation: `/CLAUDE.md`
- API documentation: `/api/README.md`
- Deployment guide: `/deployment/README.md`
