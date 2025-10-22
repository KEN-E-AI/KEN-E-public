# CD Pipeline Fix Plan for Staging and Production Deployment

**Created:** 2025-10-20
**Status:** Ready for implementation
**Estimated Time:** 4-6 hours

---

## Overview

This document details the required changes to deploy the current codebase (including agent config feature) to staging and production environments. The main issues involve missing environment variables, OAuth secrets, and Agent Engine deployments.

---

## Current Deployment Architecture

**Confirmed Deployment Stack:**
- Frontend: Cloud Run (Dockerized React app)
- API: Cloud Run (Dockerized FastAPI)
- Agent Engine: Vertex AI Agent Engine (separate deployment)
- Database: Neo4j Aura, Firestore
- Auth: Firebase Authentication
- Observability: Weights & Biases / Weave (CRITICAL)

**Existing Services:**
- Staging: kene-api-staging, kene-frontend-staging @ us-central1
- Production: kene-api-prod, kene-frontend-prod @ us-central1

---

## PART 1: Create Missing Secrets in Secret Manager

### Staging (ken-e-staging / 391472102753)

**Missing Secrets (3 critical):**

#### 1. ENCRYPTION_KEY
```bash
# Generate unique key for staging
STAGING_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create secret
echo "$STAGING_KEY" | gcloud secrets create ENCRYPTION_KEY \
  --data-file=- \
  --project=ken-e-staging

# IMPORTANT: Back up this key securely!
echo "Staging ENCRYPTION_KEY: $STAGING_KEY" >> ~/ken-e-secrets-backup.txt
```

#### 2. GOOGLE_OAUTH_CLIENT_ID & GOOGLE_OAUTH_CLIENT_SECRET
```bash
# 1. Go to: https://console.cloud.google.com/apis/credentials?project=ken-e-staging
# 2. Click "Create Credentials" → "OAuth 2.0 Client ID"
# 3. Application type: "Web application"
# 4. Name: "KEN-E Staging OAuth Client"
# 5. Authorized redirect URIs:
#    https://kene-api-staging-391472102753.us-central1.run.app/api/oauth/callback/google
# 6. Copy the generated Client ID and Client Secret

# Create secrets (replace YOUR_* with actual values)
echo "YOUR_STAGING_CLIENT_ID" | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID \
  --data-file=- \
  --project=ken-e-staging

echo "YOUR_STAGING_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET \
  --data-file=- \
  --project=ken-e-staging
```

**Existing Secrets (verify they exist):**
- ✅ NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME
- ✅ OPENAI_API_KEY
- ✅ wandb_api_key
- ✅ recaptcha-site-key, recaptcha-secret-key
- ✅ sendgrid-api-key
- ✅ ken-e-engine-id, strategy-supervisor-engine-id

---

### Production (ken-e-production / 395770269870)

**Missing Secrets (3 critical):**

#### 1. ENCRYPTION_KEY (DIFFERENT from staging!)
```bash
# Generate DIFFERENT unique key for production
PROD_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create secret
echo "$PROD_KEY" | gcloud secrets create ENCRYPTION_KEY \
  --data-file=- \
  --project=ken-e-production

# CRITICAL: Back up this key in multiple secure locations!
echo "Production ENCRYPTION_KEY: $PROD_KEY" >> ~/ken-e-secrets-backup.txt
```

#### 2. GOOGLE_OAUTH_CLIENT_ID & GOOGLE_OAUTH_CLIENT_SECRET (DIFFERENT from staging!)
```bash
# 1. Go to: https://console.cloud.google.com/apis/credentials?project=ken-e-production
# 2. Create NEW OAuth 2.0 Client (separate from staging)
# 3. Authorized redirect URIs:
#    https://kene-api-prod-395770269870.us-central1.run.app/api/oauth/callback/google
# 4. Copy Client ID and Secret

# Create secrets
echo "YOUR_PROD_CLIENT_ID" | gcloud secrets create GOOGLE_OAUTH_CLIENT_ID \
  --data-file=- \
  --project=ken-e-production

echo "YOUR_PROD_CLIENT_SECRET" | gcloud secrets create GOOGLE_OAUTH_CLIENT_SECRET \
  --data-file=- \
  --project=ken-e-production
```

**Existing Secrets:**
- ✅ Same as staging (NEO4J, OPENAI, wandb, etc.)

---

## PART 2: Update CD Pipeline - Staging

**File:** `/Users/dvalia/Code/python/KEN-E/deployment/cd/staging.yaml`

### Change 1: Add Missing Environment Variables to API Deployment

**Location:** Line 190 (inside the long `--set-env-vars` string)

**Add these variables (append to existing string):**
```yaml
,KEN_E_ENGINE_ID=${_KEN_E_ENGINE_ID_STAGING},STRATEGY_SUPERVISOR_ENGINE_ID=${_STRATEGY_SUPERVISOR_ENGINE_ID_STAGING},ENCRYPTION_KEY=${_ENCRYPTION_KEY_STAGING},GOOGLE_OAUTH_CLIENT_ID=${_GOOGLE_OAUTH_CLIENT_ID_STAGING},GOOGLE_OAUTH_CLIENT_SECRET=${_GOOGLE_OAUTH_CLIENT_SECRET_STAGING},GOOGLE_OAUTH_REDIRECT_URI=https://kene-api-staging-391472102753.us-central1.run.app/api/oauth/callback/google,FRONTEND_URL=https://kene-frontend-staging-391472102753.us-central1.run.app,OPENAI_API_KEY=${_OPENAI_API_KEY_STAGING},WANDB_API_KEY=${_WANDB_API_KEY_STAGING},WANDB_PROJECT=ken-e-strategy-agent-staging,WANDB_ENTITY=ken-e,WEAVE_PROJECT_NAME=ken-e-strategy-agent-staging
```

### Change 2: Add Substitutions for New Secrets

**Location:** After line 221 (in substitutions section)

**Add these substitutions:**
```yaml
  # Agent Engine IDs
  _KEN_E_ENGINE_ID_STAGING: projects/391472102753/secrets/ken-e-engine-id/versions/latest
  _STRATEGY_SUPERVISOR_ENGINE_ID_STAGING: projects/391472102753/secrets/strategy-supervisor-engine-id/versions/latest

  # OAuth Configuration
  _ENCRYPTION_KEY_STAGING: projects/391472102753/secrets/ENCRYPTION_KEY/versions/latest
  _GOOGLE_OAUTH_CLIENT_ID_STAGING: projects/391472102753/secrets/GOOGLE_OAUTH_CLIENT_ID/versions/latest
  _GOOGLE_OAUTH_CLIENT_SECRET_STAGING: projects/391472102753/secrets/GOOGLE_OAUTH_CLIENT_SECRET/versions/latest

  # OpenAI
  _OPENAI_API_KEY_STAGING: projects/391472102753/secrets/OPENAI_API_KEY/versions/latest

  # Weights & Biases / Weave (CRITICAL for agent tracing)
  _WANDB_API_KEY_STAGING: projects/391472102753/secrets/wandb_api_key/versions/latest
```

### Change 3: Fix Self-Referencing reCAPTCHA Variables

**Location:** Lines 213-214

**Replace:**
```yaml
# BEFORE:
  _RECAPTCHA_SITE_KEY_STAGING: ${_RECAPTCHA_SITE_KEY_STAGING}
  _RECAPTCHA_SECRET_KEY_STAGING: ${_RECAPTCHA_SECRET_KEY_STAGING}

# AFTER:
  _RECAPTCHA_SITE_KEY_STAGING: projects/391472102753/secrets/recaptcha-site-key/versions/latest
  _RECAPTCHA_SECRET_KEY_STAGING: projects/391472102753/secrets/recaptcha-secret-key/versions/latest
```

### Change 4: Add Missing Firebase Environment Variables to Frontend Build

**Location:** Lines 123-130 (frontend Docker build args)

**Add these build arguments:**
```yaml
  - name: "gcr.io/cloud-builders/docker"
    id: build-react-image
    args:
      - build
      - "-t"
      - "gcr.io/${PROJECT_ID}/kene-frontend-staging:${COMMIT_SHA}"
      - "-f"
      - "frontend/Dockerfile"
      - "--build-arg"
      - "VITE_FIREBASE_API_KEY=${_VITE_FIREBASE_API_KEY}"
      - "--build-arg"
      - "VITE_FIREBASE_AUTH_DOMAIN=${_VITE_FIREBASE_AUTH_DOMAIN}"
      - "--build-arg"
      - "VITE_FIREBASE_PROJECT_ID=${_VITE_FIREBASE_PROJECT_ID_STAGING}"
      - "--build-arg"
      - "VITE_FIREBASE_STORAGE_BUCKET=${_VITE_FIREBASE_STORAGE_BUCKET_STAGING}"
      - "--build-arg"
      - "VITE_FIREBASE_MESSAGING_SENDER_ID=${_VITE_FIREBASE_MESSAGING_SENDER_ID_STAGING}"
      - "--build-arg"
      - "VITE_FIREBASE_APP_ID=${_VITE_FIREBASE_APP_ID_STAGING}"
      - "--build-arg"
      - "VITE_API_BASE_URL=${_VITE_API_BASE_URL}"
      - "--build-arg"
      - "VITE_RECAPTCHA_SITE_KEY=${_RECAPTCHA_SITE_KEY_STAGING}"
      - "--build-arg"
      - "VITE_ENVIRONMENT=staging"
      - "./frontend"
```

**Add to substitutions:**
```yaml
  _VITE_FIREBASE_PROJECT_ID_STAGING: ken-e-staging
  _VITE_FIREBASE_STORAGE_BUCKET_STAGING: ken-e-staging.firebasestorage.app
  _VITE_FIREBASE_MESSAGING_SENDER_ID_STAGING: 391472102753
  _VITE_FIREBASE_APP_ID_STAGING: 1:391472102753:web:YOUR_APP_ID_HERE
```

---

## PART 3: Update CD Pipeline - Production

**File:** `/Users/dvalia/Code/python/KEN-E/deployment/cd/deploy-to-prod.yaml`

### Apply Same Changes as Staging:

#### Change 1: Add Missing Environment Variables
**Location:** Line 122 (API deployment --set-env-vars)

Same additions as staging, but with prod substitution variables.

#### Change 2: Add Substitutions
**Location:** After line 150

```yaml
  # Agent Engine IDs
  _KEN_E_ENGINE_ID_PROD: projects/395770269870/secrets/ken-e-engine-id/versions/latest
  _STRATEGY_SUPERVISOR_ENGINE_ID_PROD: projects/395770269870/secrets/strategy-supervisor-engine-id/versions/latest

  # OAuth Configuration
  _ENCRYPTION_KEY_PROD: projects/395770269870/secrets/ENCRYPTION_KEY/versions/latest
  _GOOGLE_OAUTH_CLIENT_ID_PROD: projects/395770269870/secrets/GOOGLE_OAUTH_CLIENT_ID/versions/latest
  _GOOGLE_OAUTH_CLIENT_SECRET_PROD: projects/395770269870/secrets/GOOGLE_OAUTH_CLIENT_SECRET/versions/latest

  # OpenAI
  _OPENAI_API_KEY_PROD: projects/395770269870/secrets/OPENAI_API_KEY/versions/latest

  # Weights & Biases / Weave
  _WANDB_API_KEY_PROD: projects/395770269870/secrets/wandb_api_key/versions/latest
```

#### Change 3: Fix Self-Referencing reCAPTCHA Variables
**Location:** Lines 142-143

```yaml
# BEFORE:
  _RECAPTCHA_SITE_KEY_PROD: ${_RECAPTCHA_SITE_KEY_PROD}

# AFTER:
  _RECAPTCHA_SITE_KEY_PROD: projects/395770269870/secrets/recaptcha-site-key/versions/latest
  _RECAPTCHA_SECRET_KEY_PROD: projects/395770269870/secrets/recaptcha-secret-key/versions/latest
```

#### Change 4: Fix Agent Engine ID (Line 145)
```yaml
# BEFORE:
  _VERTEX_AI_AGENT_ENGINE_ID_PROD: projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232  # TODO

# AFTER (use Secret Manager reference):
  _VERTEX_AI_AGENT_ENGINE_ID_PROD: projects/395770269870/secrets/ken-e-engine-id/versions/latest
```

**Note:** This assumes you're using ken-e-engine-id for both chat and strategy. If separate:
- Chat: ken-e-engine-id
- Strategy: strategy-supervisor-engine-id

#### Change 5: Add Firebase Build Args to Frontend
**Location:** Lines 56-64

Same additions as staging, but with prod Firebase config.

---

## PART 4: Deploy Agent Engines to Staging and Production

### Current Situation:
- `/Users/dvalia/Code/python/KEN-E/app/adk/deploy_with_sys_version.py` is hardcoded to ken-e-dev
- No separate deployment for staging/production agents

### Option A: Quick Fix - Manual Deployment

#### Deploy to Staging:
```bash
cd /Users/dvalia/Code/python/KEN-E/app/adk

# Edit deploy_with_sys_version.py temporarily:
# Change PROJECT_ID = "ken-e-dev" to PROJECT_ID = "ken-e-staging"
# Change PROJECT_NUMBER = "525657242938" to PROJECT_NUMBER = "391472102753"

# Deploy
uv run python deploy_with_sys_version.py

# Copy the deployed engine ID and store in Secret Manager
# ENGINE_ID will be: projects/391472102753/locations/us-central1/reasoningEngines/XXXXXXXXXX

# Update Secret Manager with new engine ID
gcloud secrets versions add strategy-supervisor-engine-id \
  --data-file=- \
  --project=ken-e-staging <<< "ENGINE_ID_HERE"

# Revert changes to deploy_with_sys_version.py
```

#### Deploy to Production:
```bash
# Same process but for ken-e-production (395770269870)
```

### Option B: Better Fix - Parameterize Deployment Script

Create a new file: `/Users/dvalia/Code/python/KEN-E/app/adk/deploy_agent.py`

```python
#!/usr/bin/env python3
"""
Deploy strategy agent to specified environment.

Usage:
    python deploy_agent.py staging
    python deploy_agent.py production
"""

import sys
# ... [rest of deployment code with environment parameter]

ENVIRONMENTS = {
    "development": {
        "project_id": "ken-e-dev",
        "project_number": "525657242938",
    },
    "staging": {
        "project_id": "ken-e-staging",
        "project_number": "391472102753",
    },
    "production": {
        "project_id": "ken-e-production",
        "project_number": "395770269870",
    }
}

if __name__ == "__main__":
    env = sys.argv[1] if len(sys.argv) > 1 else "development"
    if env not in ENVIRONMENTS:
        print(f"Error: Invalid environment. Must be: {', '.join(ENVIRONMENTS.keys())}")
        sys.exit(1)

    config = ENVIRONMENTS[env]
    # Use config to deploy...
```

**Recommendation:** Use Option A for now (quick), implement Option B later.

---

## PART 5: Update Cloud Build Pipelines

### File 1: deployment/cd/staging.yaml

**Complete list of changes:**

1. **Line 190:** Append to --set-env-vars string:
```
,KEN_E_ENGINE_ID=${_KEN_E_ENGINE_ID_STAGING},STRATEGY_SUPERVISOR_ENGINE_ID=${_STRATEGY_SUPERVISOR_ENGINE_ID_STAGING},ENCRYPTION_KEY=${_ENCRYPTION_KEY_STAGING},GOOGLE_OAUTH_CLIENT_ID=${_GOOGLE_OAUTH_CLIENT_ID_STAGING},GOOGLE_OAUTH_CLIENT_SECRET=${_GOOGLE_OAUTH_CLIENT_SECRET_STAGING},GOOGLE_OAUTH_REDIRECT_URI=https://kene-api-staging-391472102753.us-central1.run.app/api/oauth/callback/google,FRONTEND_URL=https://kene-frontend-staging-391472102753.us-central1.run.app,OPENAI_API_KEY=${_OPENAI_API_KEY_STAGING},WANDB_API_KEY=${_WANDB_API_KEY_STAGING},WANDB_PROJECT=ken-e-strategy-agent-staging,WANDB_ENTITY=ken-e,WEAVE_PROJECT_NAME=ken-e-strategy-agent-staging,VERTEX_AI_PROJECT_ID=${_STAGING_PROJECT_ID}
```

2. **Lines 213-214:** Replace self-referencing variables:
```yaml
  _RECAPTCHA_SITE_KEY_STAGING: projects/391472102753/secrets/recaptcha-site-key/versions/latest
  _RECAPTCHA_SECRET_KEY_STAGING: projects/391472102753/secrets/recaptcha-secret-key/versions/latest
```

3. **After line 221:** Add new substitutions:
```yaml
  # Agent Engine IDs (deployed separately to staging project)
  _KEN_E_ENGINE_ID_STAGING: projects/391472102753/secrets/ken-e-engine-id/versions/latest
  _STRATEGY_SUPERVISOR_ENGINE_ID_STAGING: projects/391472102753/secrets/strategy-supervisor-engine-id/versions/latest

  # OAuth Configuration (environment-specific)
  _ENCRYPTION_KEY_STAGING: projects/391472102753/secrets/ENCRYPTION_KEY/versions/latest
  _GOOGLE_OAUTH_CLIENT_ID_STAGING: projects/391472102753/secrets/GOOGLE_OAUTH_CLIENT_ID/versions/latest
  _GOOGLE_OAUTH_CLIENT_SECRET_STAGING: projects/391472102753/secrets/GOOGLE_OAUTH_CLIENT_SECRET/versions/latest

  # OpenAI (for strategy formatters)
  _OPENAI_API_KEY_STAGING: projects/391472102753/secrets/OPENAI_API_KEY/versions/latest

  # Weights & Biases / Weave (CRITICAL for agent observability)
  _WANDB_API_KEY_STAGING: projects/391472102753/secrets/wandb_api_key/versions/latest
```

4. **Lines 123-130:** Add Firebase variables to frontend build:
```yaml
      - "--build-arg"
      - "VITE_FIREBASE_PROJECT_ID=ken-e-staging"
      - "--build-arg"
      - "VITE_FIREBASE_STORAGE_BUCKET=ken-e-staging.firebasestorage.app"
      - "--build-arg"
      - "VITE_FIREBASE_MESSAGING_SENDER_ID=391472102753"
      - "--build-arg"
      - "VITE_FIREBASE_APP_ID=${_VITE_FIREBASE_APP_ID_STAGING}"
      - "--build-arg"
      - "VITE_ENVIRONMENT=staging"
```

Add to substitutions:
```yaml
  _VITE_FIREBASE_APP_ID_STAGING: "1:391472102753:web:YOUR_STAGING_APP_ID"
```

### File 2: deployment/cd/deploy-to-prod.yaml

**Apply same changes as staging, but with production values:**

1. **Line 122:** Add environment variables (use prod substitutions)

2. **Lines 142-143:** Fix reCAPTCHA self-references:
```yaml
  _RECAPTCHA_SITE_KEY_PROD: projects/395770269870/secrets/recaptcha-site-key/versions/latest
  _RECAPTCHA_SECRET_KEY_PROD: projects/395770269870/secrets/recaptcha-secret-key/versions/latest
```

3. **After line 150:** Add prod substitutions (same as staging but with project 395770269870)

4. **Line 145:** Fix agent engine ID:
```yaml
  _VERTEX_AI_AGENT_ENGINE_ID_PROD: projects/395770269870/secrets/strategy-supervisor-engine-id/versions/latest
```

5. **Lines 56-64:** Add Firebase build args for frontend

---

## PART 6: Verification Checklist

### After Secrets Created:

```bash
# Verify staging secrets
gcloud secrets list --project=ken-e-staging --filter="name:(ENCRYPTION_KEY OR GOOGLE_OAUTH)" --format="value(name)"

# Verify production secrets
gcloud secrets list --project=ken-e-production --filter="name:(ENCRYPTION_KEY OR GOOGLE_OAUTH)" --format="value(name)"

# Test accessing a secret
gcloud secrets versions access latest --secret="ENCRYPTION_KEY" --project=ken-e-staging
```

### After Agent Engine Deployment:

```bash
# Verify engine ID is stored
gcloud secrets versions access latest --secret="strategy-supervisor-engine-id" --project=ken-e-staging

# Should output something like:
# projects/391472102753/locations/us-central1/reasoningEngines/1234567890
```

### After CD Pipeline Updates:

**Staging Deployment Test:**
```bash
# Trigger staging pipeline manually or push to main
# Monitor: https://console.cloud.google.com/cloud-build/builds?project=ken-e-staging

# After deployment, verify:
curl https://kene-api-staging-391472102753.us-central1.run.app/health
# Should return: {"status": "healthy", ...}

# Check frontend
open https://kene-frontend-staging-391472102753.us-central1.run.app

# Test OAuth flow in staging UI
# Test strategy generation
# Check Weave traces
```

**Production Deployment Test:**
- Same verification steps for production URLs

---

## PART 7: Post-Deployment Configuration

### Update .env Files Locally (DO NOT COMMIT)

After deployment succeeds, update local .env files to match deployed environment for testing:

**`api/.env.staging` (create if needed):**
```bash
ENVIRONMENT=staging
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging
# ... all other vars using sm:// references
```

**`api/.env.production` (create if needed):**
```bash
ENVIRONMENT=production
GOOGLE_CLOUD_PROJECT_ID=ken-e-production
# ... all other vars using sm:// references
```

---

## Timeline and Ownership

### Phase 1: Secret Creation (Day 1 - 2 hours)
**Owner:** DevOps/Platform team

- [ ] Generate encryption keys (staging & production)
- [ ] Create OAuth 2.0 Clients in GCP Console (staging & production)
- [ ] Store all secrets in Secret Manager
- [ ] Back up encryption keys securely
- [ ] Document OAuth client IDs

### Phase 2: Agent Engine Deployment (Day 1 - 2 hours)
**Owner:** AI/ML team

- [ ] Deploy Strategy Supervisor to staging
- [ ] Deploy Strategy Supervisor to production
- [ ] Store engine IDs in Secret Manager
- [ ] Verify engines are callable

### Phase 3: CD Pipeline Updates (Day 1 - 1 hour)
**Owner:** DevOps team

- [ ] Update staging.yaml with all changes
- [ ] Update deploy-to-prod.yaml with all changes
- [ ] Commit and push changes
- [ ] Review diff carefully

### Phase 4: Staging Deployment & Testing (Day 2 - 3 hours)
**Owner:** QA + Engineering team

- [ ] Trigger staging deployment
- [ ] Monitor Cloud Build logs
- [ ] Verify all services healthy
- [ ] Test complete user flows
- [ ] Test OAuth integration
- [ ] Test strategy generation
- [ ] Verify Weave tracing works
- [ ] Check for errors in logs

### Phase 5: Production Deployment (Day 2 - 1 hour)
**Owner:** Platform team

- [ ] Manual approval in Cloud Build
- [ ] Monitor deployment
- [ ] Smoke test production
- [ ] Verify no regressions
- [ ] Monitor for 24 hours

---

## Rollback Plan

If deployment fails:

### Staging:
```bash
# Redeploy previous working image
gcloud run deploy kene-api-staging \
  --image=gcr.io/ken-e-staging/kene-api-staging:PREVIOUS_COMMIT_SHA \
  --project=ken-e-staging \
  --region=us-central1
```

### Production:
- Trigger previous successful build from Cloud Build history
- Or manually deploy last known good image

---

## Critical Reminders

1. ✅ **WANDB_API_KEY is MANDATORY** - Not optional, critical for agent tracing
2. ✅ **Firebase vars are MANDATORY** - Full config needed for auth
3. ✅ **Each environment needs unique OAuth clients** - DO NOT copy between environments
4. ✅ **Each environment needs unique ENCRYPTION_KEY** - DO NOT copy between environments
5. ✅ **Back up encryption keys** - Losing them = permanent data loss
6. ✅ **Test in staging first** - Never push directly to production
7. ✅ **Monitor Weave after deployment** - Ensure traces are appearing

---

## Contact

For questions or issues during deployment:
- Deployment guide: `/deployment/ENVIRONMENT_SETUP_GUIDE.md`
- This plan: `/deployment/CD_PIPELINE_FIX_PLAN.md`
- Main docs: `/CLAUDE.md`
- Platform team: #ken-e-platform (Slack)
