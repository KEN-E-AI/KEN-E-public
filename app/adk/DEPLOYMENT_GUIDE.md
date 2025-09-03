# Agent Engine Deployment Guide

## Overview
This guide documents the correct process for deploying the multi-agent supervisor to Google Cloud Agent Engine (Vertex AI Reasoning Engines).

## ⚠️ CRITICAL: Pre-Deployment Checklist
Before deploying, you MUST verify:

1. **Check agent.py imports the supervisor, NOT the strategy orchestrator**
   ```python
   # CORRECT - agent.py should contain:
   from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor
   root_agent = create_strategy_docs_supervisor
   
   # WRONG - agent.py should NOT contain:
   from agents.strategy_agent.orchestrator import app, strategy_agent
   root_agent = strategy_agent
   ```

2. **Remove or rename conflicting files**
   - Any `agents_broken.py` files should be renamed to `.old`
   - Check for duplicate agent files with different configurations

3. **Verify token limits are correct**
   - Check `agents/strategy_agent/agents.py` has `max_output_tokens=32768` (NOT 65535)
   - Verify `max_iterations=2` for LoopAgents (NOT 3)

## Current Working Deployment Script
**Use: `deploy_supervisor_fixed.py`**

This is the ONLY deployment script that correctly:
- Handles imports without requiring `google.adk` in runtime
- Includes all agent subdirectories (especially `strategy_agent/`)
- Creates proper wrapper files for Agent Engine compatibility
- Saves deployment information for tracking

## Understanding the Architecture

### The Multi-Agent System Flow
```
API Request → Supervisor → Routes to Appropriate Agent → Returns Response
                 ↓
         Routes based on message:
         • "Generate all 5 strategy documents" → Strategy Agent
         • "Get company news" → News Agent
         • "Analytics data" → GA Agent
```

### Why the Supervisor is Essential
The supervisor (`create_strategy_docs_supervisor`) is the entry point that:
1. Receives all messages from the API
2. Analyzes the message content
3. Routes to the appropriate specialized agent
4. Returns the consolidated response

**Without the supervisor, strategy generation will fail** because the strategy orchestrator doesn't understand routing messages.

## Deployment Process

### 1. Pre-Deployment Verification
```bash
# Verify agent.py is correct
cat agent.py | grep "create_strategy_docs_supervisor"  # Should find this
cat agent.py | grep "strategy_agent"                   # Should NOT find this

# Check for problematic files
ls agents/strategy_agent/agents*.py  # Should only show agents.py

# Verify token limits
grep "max_output_tokens" agents/strategy_agent/agents.py | head -5
```

### 2. Run Deployment
```bash
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_supervisor_fixed.py
```

### 3. Monitor Deployment
The script will:
1. Create a temporary directory with all necessary files
2. Copy agents, requirements, and environment files
3. Create wrapper files (`agent.py`, `agent_engine_app.py`)
4. Deploy using ADK CLI
5. Output the new Engine ID (save this immediately!)

Deployment typically takes 3-5 minutes. Watch for:
- "Deployment successful!" message
- Engine ID in format: `projects/525657242938/locations/us-central1/reasoningEngines/[ID]`

### 4. Update Environment Variables
After successful deployment, update these files with the new Engine ID:

**API Environment Files:**
- `/api/.env`
- `/api/.env.development`
- `/api/.env.staging` (if applicable)
- `/api/.env.production` (if applicable)

Update ALL these variables to the SAME Engine ID:
```bash
SUPERVISOR_ENHANCED_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[NEW_ID]
VERTEX_AI_AGENT_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[NEW_ID]
CREATE_STRATEGY_DOCS_ENGINE_ID=projects/525657242938/locations/us-central1/reasoningEngines/[NEW_ID]
```

### 5. Restart API Server
The API server must be restarted to use the new Engine ID:
```bash
# Kill existing server (find process with ps aux | grep uvicorn)
# Then restart:
cd /Users/kenwilliams/Documents/github/ken-e/api
uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Verify Deployment
1. Check deployment log: `supervisor_deployment.txt`
2. Test from frontend by creating a new account
3. Monitor Weights & Biases traces for agent execution
4. Verify all 5 strategy documents complete

## Common Issues and Solutions

### Import Errors
**Problem:** `ModuleNotFoundError: No module named 'google.adk'`
**Solution:** Use `deploy_supervisor_fixed.py` which creates proper import wrappers

### Strategy Documents Not Generating
**Problem:** 0/5 documents complete, W&B shows no agent activity
**Causes & Solutions:**
1. **Wrong agent deployed** - Check `agent.py` imports supervisor, not strategy orchestrator
2. **Supervisor not routing** - Verify message starts with "Generate all 5 strategy documents"
3. **Engine ID mismatch** - Ensure all env vars use the same Engine ID

### agents_broken.py Contamination
**Problem:** W&B shows old token limits (65535) even after updating agents.py
**Solution:** 
1. Rename any `agents_broken.py` to `agents_broken.py.old`
2. Redeploy to ensure only correct file is included

### Timeout Issues
**Problem:** Brand guidelines document times out
**Solution:** Verify in `agents/strategy_agent/agents.py`:
- `max_output_tokens=32768` (not 65535)
- `max_iterations=2` (not 3)

### Project ID Mismatch
**Problem:** Documents saved to wrong project
**Solution:** Force project ID in Firestore initialization (already implemented)

## Key Files and Their Purpose

### Required Files (DO NOT DELETE)
- `agents/create_strategy_docs_supervisor.py` - Main supervisor orchestrator
- `agents/strategy_agent/*.py` - Strategy document generation agents
- `agents/company_news_agent.py` - News fetching and analysis
- `agents/google_analytics_agent.py` - Analytics insights
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (project ID, locations)
- `deploy_supervisor_fixed.py` - Current working deployment script

### Generated During Deployment
- `agent.py` - Wrapper that imports and exports the supervisor (created in temp dir)
- `agent_engine_app.py` - ADK app configuration (created in temp dir)
- `supervisor_deployment.txt` - Deployment record with Engine ID

### Deprecated Files (Safe to Delete)
All files with `.old` suffix are deprecated deployment scripts that should not be used.

## Import Architecture Explained

### The Import Challenge
- **Local development** uses: `from google.adk.agents import Agent`
- **Agent Engine runtime** doesn't have `google.adk` available
- **Solution**: Wrapper pattern in deployment

### How deploy_supervisor_fixed.py Solves This
1. **Preserves original imports** - Agent files keep their `google.adk` imports
2. **Creates wrapper layer** - Temporary `agent.py` imports from local agents
3. **ADK CLI handles transformation** - Converts for Agent Engine runtime

The deployment script NEVER modifies the original agent files, ensuring consistency between development and deployment.

## Deployment History Tracking
- **Latest deployment info**: Check `supervisor_deployment.txt`
- **Previous deployments**: Remain active until explicitly deleted in GCP Console
- **Naming convention**: `multi-agent-supervisor-v2-YYYYMMDD-HHMMSS`

## Best Practices

### Before Deployment
1. **Always verify agent.py** - Most critical file to check
2. **Clean up old files** - Remove or rename deprecated/broken versions
3. **Test locally first** - Ensure agents work in development
4. **Document changes** - Update this guide with new learnings

### During Deployment
1. **Save Engine ID immediately** - Copy as soon as it appears
2. **Don't interrupt deployment** - Let it complete fully
3. **Monitor output** - Watch for errors or warnings

### After Deployment
1. **Update ALL env files** - Consistency is crucial
2. **Restart API server** - Required for new Engine ID
3. **Test immediately** - Verify with a simple request
4. **Keep deployment logs** - For troubleshooting

## Rollback Process

If a deployment fails or causes issues:

1. Revert environment variables to previous Engine ID (check git history)
2. Restart API server
3. Previous engine remains available (not overwritten)
4. Investigate logs in Google Cloud Console
5. Fix issues and redeploy using `deploy_supervisor_fixed.py`

## Testing Checklist

After deployment, verify:
- [ ] API server running with new Engine ID
- [ ] Frontend can create accounts
- [ ] Strategy generation starts (check W&B)
- [ ] All 5 documents complete
- [ ] No timeout errors
- [ ] Documents saved to correct project

## Critical Lessons Learned

1. **The supervisor is not optional** - It's the router for all agent communications
2. **agent.py determines what gets deployed** - Always verify this file
3. **File conflicts cause subtle bugs** - Remove duplicates with different configs
4. **Import patterns matter** - Use wrappers, don't modify originals
5. **Test the full flow** - From API to agents to Firestore

## Quick Commands Reference

```bash
# Check current deployment
cat supervisor_deployment.txt

# Verify agent.py
grep "create_strategy_docs_supervisor\|strategy_agent" agent.py

# Deploy
uv run python deploy_supervisor_fixed.py

# Check token limits
grep "max_output_tokens" agents/strategy_agent/agents.py

# Find deprecated files
ls deploy*.py.old
```

## Managing Reasoning Engines

After deployments, you may accumulate multiple reasoning engines that are no longer in use. Use the `manage_reasoning_engines.py` script to list and clean up unused engines.

### List All Engines
```bash
# List all reasoning engines in the project
uv run python manage_reasoning_engines.py --list

# List engines in a specific project
uv run python manage_reasoning_engines.py --project my-project --list
```

### Delete Unused Engines
```bash
# Delete all engines except a specific one (interactive confirmation)
uv run python manage_reasoning_engines.py --delete --keep-id 1824877040805871616

# Delete without confirmation prompt
uv run python manage_reasoning_engines.py --delete --keep-id 1824877040805871616 --yes

# Dry run - see what would be deleted without actually deleting
uv run python manage_reasoning_engines.py --delete --keep-id 1824877040805871616 --dry-run
```

### Important Notes About Engine Management
- **Rate Limits**: The script handles rate limiting automatically (8 requests/minute)
- **Force Deletion**: The script uses force=true to delete engines with active sessions
- **Retries**: Failed deletions due to rate limits are automatically retried
- **Verification**: After deletion, the script verifies the final state
- **Safety**: Always specify --keep-id to avoid deleting all engines accidentally

### Finding the Current Engine ID
The current engine ID in use can be found in:
- `supervisor_deployment.txt` (latest deployment record)
- API environment files (`/api/.env*`)
- Look for variables like `VERTEX_AI_AGENT_ENGINE_ID`

## Notes

- Deployment typically takes 3-5 minutes
- Each deployment creates a new Engine ID (old ones remain active)
- Use timestamps in deployment names for tracking
- The deployment script outputs progress to console
- Deployment info is saved to `supervisor_deployment.txt`
- Clean up old engines regularly using `manage_reasoning_engines.py`

---

**Remember:** When in doubt, verify `agent.py` imports the supervisor, not the strategy orchestrator!