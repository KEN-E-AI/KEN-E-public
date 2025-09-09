# Agent Engine Deployment Guide

## Overview

This guide documents the deployment process for the separated KEN-E agents to Google Cloud Agent Engine (Vertex AI Reasoning Engines).

## Agent Architecture

### Two Separate Agents

After the separation, we have two distinct agents:

1. **KEN-E Agent** (`ken_e_agent`)
   - Frontend-facing chat agent
   - Handles company news and Google Analytics queries
   - Deployed for `/api/v1/chat/completions` endpoint

2. **Strategy Documents Supervisor** (`create_strategy_docs_supervisor`)
   - Backend-only agent for account creation
   - Generates all 5 strategy documents
   - Called programmatically during account creation

### Architecture Flow

```
Frontend Chat → API → KEN-E Agent → Returns Response
                         ↓
                Routes to either:
                • Company News Agent
                • Google Analytics Agent

Account Creation → API → Strategy Supervisor → Strategy Agent → 5 Documents
```

## Deployment Scripts

### Deploy KEN-E Agent (Frontend Chat)

```bash
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_ken_e.py
```

This deploys the chat agent that handles:

- Company news queries
- Google Analytics data requests
- Frontend chat interactions

### Deploy Strategy Supervisor (Account Creation)

```bash
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_strategy_supervisor.py
```

This deploys the strategy generation agent for:

- Account creation workflow
- Generating 5 strategy documents
- Backend-only operations

## Pre-Deployment Checklist

### 1. Verify Agent Configurations

```bash
# Check KEN-E agent has correct tools
grep "search_company_news\|query_google_analytics" agents/ken_e_agent.py

# Check Strategy Supervisor has strategy tool
grep "create_strategy" agents/create_strategy_docs_supervisor.py

# Verify imports are correct
grep "from .ken_e_agent import ken_e_agent" agents/__init__.py
```

### 2. Clean Environment

```bash
# Remove any old deployment artifacts
rm -f agent.py agent_engine_app.py

# Check for deprecated files
ls agents/*_broken.py agents/*.old
```

### 3. Verify Dependencies

```bash
# Ensure requirements.txt is up to date
cat requirements.txt | grep -E "google-cloud|vertexai"
```

## Deployment Process

### Step 1: Deploy KEN-E Agent

```bash
# Deploy the frontend chat agent
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_ken_e.py

# Optional: specify project and location
uv run python deploy_ken_e.py --project ken-e-dev --location us-central1
```

The script will:

1. Create temporary deployment directory
2. Copy all necessary agent files
3. Create deployment wrappers
4. Deploy to Agent Engine
5. Output the Engine ID

**Save the Engine ID immediately!**
Example: `projects/525657242938/locations/us-central1/reasoningEngines/1234567890`

### Step 2: Deploy Strategy Supervisor

```bash
# Deploy the strategy generation agent
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_strategy_supervisor.py

# Optional: specify project and location
uv run python deploy_strategy_supervisor.py --project ken-e-dev --location us-central1
```

Similar process, but deploys the strategy generation agent.

**Save this Engine ID separately!**

### Step 3: Update Engine IDs Using Secret Manager

After successful deployments, we now use Google Secret Manager to store Engine IDs. This eliminates the need to manually update environment files or Cloud Run configurations.

#### Why Use Secret Manager?

- ✅ **Automatic Updates**: All developers get the latest engine IDs without manual updates
- ✅ **Version Control**: Easy rollback to previous engine versions
- ✅ **Audit Trail**: Track all engine ID changes
- ✅ **No Code Changes**: Applications automatically fetch the latest values
- ✅ **Simplified Deployment**: Update once in Secret Manager, all services use it

#### 3A. Update Secret Manager with New Engine IDs

When you deploy a new agent engine, update the corresponding secret:

```bash
# For Development Environment (ken-e-dev)
PROJECT_ID=525657242938

# For Staging Environment (ken-e-staging)  
PROJECT_ID=391472102753

# For Production Environment (ken-e-production)
PROJECT_ID=395770269870

# Update KEN-E Agent Engine ID
echo "projects/$PROJECT_ID/locations/us-central1/reasoningEngines/NEW_KEN_E_ENGINE_ID" | \
  gcloud secrets versions add ken-e-engine-id \
    --data-file=- \
    --project=$PROJECT_ID

# Update Strategy Supervisor Engine ID
echo "projects/$PROJECT_ID/locations/us-central1/reasoningEngines/NEW_STRATEGY_ENGINE_ID" | \
  gcloud secrets versions add strategy-supervisor-engine-id \
    --data-file=- \
    --project=$PROJECT_ID
```

#### 3B. First-Time Secret Creation

If the secrets don't exist yet (first deployment), create them:

```bash
# Choose your environment
PROJECT_ID=525657242938  # development
# PROJECT_ID=391472102753  # staging
# PROJECT_ID=395770269870  # production

# Create the secrets
gcloud secrets create ken-e-engine-id \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

gcloud secrets create strategy-supervisor-engine-id \
  --replication-policy="automatic" \
  --project=$PROJECT_ID

# Add initial values
echo "projects/$PROJECT_ID/locations/us-central1/reasoningEngines/INITIAL_KEN_E_ID" | \
  gcloud secrets versions add ken-e-engine-id --data-file=- --project=$PROJECT_ID

echo "projects/$PROJECT_ID/locations/us-central1/reasoningEngines/INITIAL_STRATEGY_ID" | \
  gcloud secrets versions add strategy-supervisor-engine-id --data-file=- --project=$PROJECT_ID
```

#### 3C. Environment File Configuration

The environment files now use Secret Manager references instead of hardcoded IDs:

```bash
# .env.development
KEN_E_ENGINE_ID=projects/525657242938/secrets/ken-e-engine-id
STRATEGY_SUPERVISOR_ENGINE_ID=projects/525657242938/secrets/strategy-supervisor-engine-id

# .env.staging
KEN_E_ENGINE_ID=projects/391472102753/secrets/ken-e-engine-id
STRATEGY_SUPERVISOR_ENGINE_ID=projects/391472102753/secrets/strategy-supervisor-engine-id

# .env.production
KEN_E_ENGINE_ID=projects/395770269870/secrets/ken-e-engine-id
STRATEGY_SUPERVISOR_ENGINE_ID=projects/395770269870/secrets/strategy-supervisor-engine-id
```

#### 3D. How Applications Use the Secrets

The application code automatically:
1. Detects the secret path format (`projects/*/secrets/*`)
2. Fetches the latest value from Secret Manager
3. Uses the actual engine ID for API calls

No code changes needed when deploying new engines!

#### 3E. Verify Secret Values

To check current secret values:

```bash
# View the latest version
gcloud secrets versions access latest \
  --secret=ken-e-engine-id \
  --project=$PROJECT_ID

# List all versions (for rollback if needed)
gcloud secrets versions list \
  --secret=ken-e-engine-id \
  --project=$PROJECT_ID
```

#### 3F. Rollback to Previous Engine

If needed, you can quickly rollback:

```bash
# Disable the current version
gcloud secrets versions disable VERSION_NUMBER \
  --secret=ken-e-engine-id \
  --project=$PROJECT_ID

# Or promote an older version to latest
gcloud secrets versions add ken-e-engine-id \
  --data-file=<(gcloud secrets versions access VERSION_NUMBER \
    --secret=ken-e-engine-id --project=$PROJECT_ID) \
  --project=$PROJECT_ID
```

#### 3G. Update Local Environment Files (Legacy Method)

**Files to update:**

- `/api/.env`
- `/api/.env.development`
- `/api/.env.staging`
- `/api/.env.production`

**Environment variables:**

```bash
# KEN-E Agent for chat interactions
KEN_E_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[KEN-E-ID]

# Strategy Supervisor for account creation
STRATEGY_SUPERVISOR_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[STRATEGY-ID]

# Keep for backward compatibility (point to KEN-E)
VERTEX_AI_AGENT_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[KEN-E-ID]
```

#### 3B. Update Cloud Run Services (CRITICAL!)

**⚠️ IMPORTANT:** Local environment file changes are NOT automatically reflected in deployed Cloud Run services. You MUST update the Cloud Run environment variables separately.

**For Staging:**

```bash
# Update KEN-E Engine ID (if changed)
gcloud run services update kene-api-staging \
  --region us-central1 \
  --project ken-e-staging \
  --update-env-vars KEN_E_ENGINE_ID=projects/391472102753/locations/us-central1/reasoningEngines/[NEW-KEN-E-ID]

# Update Strategy Supervisor Engine ID (if changed)
gcloud run services update kene-api-staging \
  --region us-central1 \
  --project ken-e-staging \
  --update-env-vars STRATEGY_SUPERVISOR_ENGINE_ID=projects/391472102753/locations/us-central1/reasoningEngines/[NEW-STRATEGY-ID]
```

**For Production:**

```bash
# Update KEN-E Engine ID (if changed)
gcloud run services update kene-api-production \
  --region us-central1 \
  --project ken-e-production \
  --update-env-vars KEN_E_ENGINE_ID=projects/395770269870/locations/us-central1/reasoningEngines/[NEW-KEN-E-ID]

# Update Strategy Supervisor Engine ID (if changed)
gcloud run services update kene-api-production \
  --region us-central1 \
  --project ken-e-production \
  --update-env-vars STRATEGY_SUPERVISOR_ENGINE_ID=projects/395770269870/locations/us-central1/reasoningEngines/[NEW-STRATEGY-ID]
```

**Verify the update:**

```bash
# Check current Engine IDs in Cloud Run
gcloud run services describe kene-api-[staging|production] \
  --region us-central1 \
  --project ken-e-[staging|production] \
  --format="yaml(spec.template.spec.containers[0].env)" | grep ENGINE_ID
```

#### 3C. Troubleshooting Cloud Run Updates

If the Cloud Run update fails:

1. **Check if the service name is correct:**
   ```bash
   gcloud run services list --project ken-e-[staging|production]
   ```

2. **Update multiple environment variables at once:**
   ```bash
   gcloud run services update kene-api-staging \
     --region us-central1 \
     --project ken-e-staging \
     --update-env-vars \
       KEN_E_ENGINE_ID=projects/391472102753/locations/us-central1/reasoningEngines/[KEN-E-ID],\
       STRATEGY_SUPERVISOR_ENGINE_ID=projects/391472102753/locations/us-central1/reasoningEngines/[STRATEGY-ID]
   ```

3. **Force a new revision with all changes:**
   ```bash
   gcloud run deploy kene-api-staging \
     --region us-central1 \
     --project ken-e-staging \
     --image [current-image] \
     --update-env-vars STRATEGY_SUPERVISOR_ENGINE_ID=projects/391472102753/locations/us-central1/reasoningEngines/[NEW-ID]
   ```

### Step 4: API Routing (Automatic)

The API automatically routes to the correct agent based on the use case:

**Chat Endpoint** (`/api/v1/chat/completions`):

- Uses `KEN_E_ENGINE_ID` if set
- Falls back to `VERTEX_AI_AGENT_ENGINE_ID` for backward compatibility
- Implementation in `src/kene_api/routers/chat.py`

**Strategy Generation** (Account Creation):

- Uses `STRATEGY_SUPERVISOR_ENGINE_ID` if set
- Falls back to `VERTEX_AI_AGENT_ENGINE_ID` for backward compatibility
- Implementation in `src/kene_api/tasks/strategy_tasks.py`

No code changes needed - just set the environment variables!

### Step 5: Restart API Server

```bash
# Kill existing server
ps aux | grep uvicorn
kill [PID]

# Restart with new configuration
cd /Users/kenwilliams/Documents/github/ken-e/api
uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 6: Verify Deployments

#### Test KEN-E Agent (Chat)

1. Open frontend application
2. Try a chat query: "What's the latest news about Apple?"
3. Verify response is received
4. Check W&B traces show KEN-E agent activity

#### Test Strategy Supervisor (Account Creation)

1. Create a new account through the frontend
2. Monitor strategy document generation
3. Verify all 5 documents complete
4. Check W&B traces show strategy agent activity

## Deployment Outputs

Each deployment creates:

- **Deployment log file**: `ken_e_deployment.txt` or `strategy_supervisor_deployment.txt`
- **Engine ID**: Unique identifier for the deployed agent
- **Timestamp**: When the deployment occurred

## Common Issues and Solutions

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'google.adk'`
**Solution:** The deployment scripts handle this by creating proper wrappers

### Wrong Agent Responding

**Problem:** Chat queries getting strategy responses or vice versa
**Solution:** Verify environment variables point to correct Engine IDs

### Deployment Fails

**Problem:** ADK deployment command fails
**Causes:**

1. Missing GCP credentials - Run `gcloud auth application-default login`
2. Wrong project - Set `VERTEX_AI_PROJECT_ID` environment variable
3. Staging bucket doesn't exist - Create with `gsutil mb gs://[project]-adk-staging`

### Rate Limiting

**Problem:** Too many deployment attempts
**Solution:** Wait a few minutes between deployments

## Managing Multiple Deployments

### List All Reasoning Engines

```bash
# Using gcloud CLI (may have limitations)
gcloud ai reasoning-engines list --project=ken-e-staging --location=us-central1

# Using REST API directly for complete list
curl -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines" 2>/dev/null | jq '.reasoningEngines[] | {id: .name | split("/")[-1], displayName: .displayName, createTime: .createTime}'
```

### Clean Up Old Deployments

**⚠️ WARNING:** Always verify which engines to keep before deleting. Deleted engines cannot be recovered.

#### Method 1: Using Python Script

```bash
# Keep only the latest KEN-E and Strategy engines
uv run python cleanup_reasoning_engines.py
```

Edit the script to specify which engines to keep:
```python
ENGINES_TO_KEEP = {
    "projects/391472102753/locations/us-central1/reasoningEngines/[KEN-E-ENGINE-ID]",
    "projects/391472102753/locations/us-central1/reasoningEngines/[STRATEGY-ENGINE-ID]"
}
```

#### Method 2: Using REST API Directly

Delete individual engines:
```bash
# Delete a single engine
curl -X DELETE \
  -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines/[ENGINE-ID]"

# Force delete an engine with active sessions
curl -X DELETE \
  -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines/[ENGINE-ID]?force=true"
```

Batch delete multiple engines:
```bash
# List of engines to delete (replace with actual IDs)
for engine_id in ENGINE_ID_1 ENGINE_ID_2 ENGINE_ID_3; do
  echo "Deleting engine: $engine_id"
  curl -X DELETE \
    -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
    "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines/$engine_id?force=true"
  echo ""
done
```

### Verify Cleanup

After cleanup, verify only the desired engines remain:
```bash
# Count remaining engines
curl -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines" 2>/dev/null | jq '.reasoningEngines | length'

# List remaining engines with details
curl -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/391472102753/locations/us-central1/reasoningEngines" 2>/dev/null | jq '.reasoningEngines[] | {id: .name | split("/")[-1], displayName: .displayName}'
```

### Important Notes on Cleanup

1. **Active Sessions**: Engines with active sessions require the `force=true` parameter to delete
2. **No Recovery**: Deleted engines cannot be recovered - always verify before deleting
3. **Project IDs**: Replace `391472102753` with your actual project number:
   - Staging: 391472102753
   - Production: 395770269870
   - Development: 525657242938
4. **Regular Cleanup**: Clean up old engines regularly to:
   - Reduce clutter in the console
   - Avoid hitting quota limits
   - Improve listing performance

## Quick Reference

### Deployment Commands

```bash
# Deploy KEN-E (chat)
uv run python deploy_ken_e.py

# Deploy Strategy Supervisor (account creation)
uv run python deploy_strategy_supervisor.py

# Deploy with specific project
uv run python deploy_ken_e.py --project ken-e-staging --location us-central1
```

### Verification Commands

```bash
# Check deployment logs
cat ken_e_deployment.txt
cat strategy_supervisor_deployment.txt

# Verify agent configurations
grep "tools=" agents/ken_e_agent.py
grep "tools=" agents/create_strategy_docs_supervisor.py

# Check current Engine IDs in use
grep "ENGINE_ID" /Users/kenwilliams/Documents/github/ken-e/api/.env
```

### Testing Commands

```bash
# Test KEN-E agent locally
cd app/adk
uv run python -c "from agents.ken_e_agent import ken_e_agent; print(ken_e_agent.name)"

# Test Strategy Supervisor locally
cd app/adk
uv run python -c "from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor; print(create_strategy_docs_supervisor.name)"
```

## Implementation Details

### Phase 3 Changes (API Routing)

The API routing was updated to support the separated agents:

1. **Chat Router** (`api/src/kene_api/routers/chat.py`):

   ```python
   # Automatically uses KEN_E_ENGINE_ID or falls back
   self.agent_engine_id = os.getenv("KEN_E_ENGINE_ID") or os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
   ```

2. **Strategy Tasks** (`api/src/kene_api/tasks/strategy_tasks.py`):

   ```python
   # Automatically uses STRATEGY_SUPERVISOR_ENGINE_ID or falls back
   agent_engine_id = os.getenv("STRATEGY_SUPERVISOR_ENGINE_ID") or os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
   ```

3. **Environment Variables** (`.env.example`):
   - Added `KEN_E_ENGINE_ID` for chat agent
   - Added `STRATEGY_SUPERVISOR_ENGINE_ID` for strategy generation
   - Kept `VERTEX_AI_AGENT_ENGINE_ID` for backward compatibility

### Testing the Routing

Run the routing tests to verify the implementation:

```bash
cd /Users/kenwilliams/Documents/github/ken-e/api
uv run pytest tests/unit/test_agent_routing.py -v
```

Expected: 6+ tests should pass, verifying:

- KEN-E engine ID is used for chat
- Strategy supervisor engine ID is used for account creation
- Fallback to VERTEX_AI_AGENT_ENGINE_ID works
- New env vars take priority over old ones

## Architecture Benefits

### Separation Advantages

1. **Independent scaling** - Scale chat and strategy generation separately
2. **Isolated failures** - Issues in one agent don't affect the other
3. **Cleaner code** - Each agent has a specific, focused purpose
4. **Easier testing** - Test each agent independently
5. **Better monitoring** - Track usage and performance separately

### Migration Path

1. Deploy both new agents
2. Update API to route to appropriate agent
3. Test thoroughly
4. Deprecate old unified supervisor
5. Clean up old deployments

## Best Practices

### Before Deployment

1. Test agents locally first
2. Verify all tools are correctly assigned
3. Check environment variables are set
4. Review recent code changes

### During Deployment

1. Deploy one agent at a time
2. Save Engine IDs immediately
3. Monitor deployment output for errors
4. Don't interrupt deployment process

### After Deployment

1. Update all environment files
2. Test both agents thoroughly
3. Monitor W&B traces
4. Document any issues

## Rollback Process

If issues occur after deployment:

1. **Revert environment variables** to previous Engine IDs
2. **Restart API server** to apply changes
3. **Previous engines remain active** (not deleted)
4. **Investigate logs** in GCP Console
5. **Fix issues** and redeploy

## Notes

- Deployments take 3-5 minutes each
- Each deployment creates a new Engine ID
- Old engines remain active until manually deleted
- Use timestamps in deployment names for tracking
- Clean up old engines regularly to avoid clutter

---

**Remember:** The separation ensures cleaner, more maintainable code with better isolation between chat and strategy generation functions.
