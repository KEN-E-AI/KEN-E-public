# Marketing Graph Builder Debugging Session Context

**Date:** 2025-10-30
**Primary Issue:** Strategy count mismatch - not all strategies being created in Neo4j
**Status:** Awaiting test with latest deployment

---

## Current Problem

When building marketing graphs, strategies are being skipped. Error logs show:
- "Strategy count mismatch: expected 20, but created 4"
- "Strategy count mismatch: expected 10, but created 0"
- "ProductCategory 'Primary Products' not found in graph, skipping strategies"

**Key insight:** "Primary Products" is a fallback placeholder that shouldn't appear if the real MarketingResearchReport is being processed correctly.

---

## Root Causes Identified & Fixed

### 1. Neo4j Query Result Indexing Bug ✅ FIXED
**File:** `app/adk/agents/strategy_agent/marketing_graph_builder.py`
**Line:** 263-264
**Problem:** Code was accessing `result[0]` but `neo4j_ops.connection.execute_query()` returns `list[dict]` directly
**Fix:** Changed from `for record in result[0]:` to `for record in result:`

### 2. API Server Secret Caching Issue ✅ FIXED
**File:** `api/src/kene_api/utils/secrets.py`
**Problem:** Secret Manager values are cached for application lifetime using:
- Module-level `_secret_cache` dictionary (line 33)
- `@lru_cache` decorator on `_fetch_secret()` function (line 73)

**Impact:** After deploying new Agent Engine and updating Secret Manager, API server continued using old cached engine ID

**Solution:** Must restart API server after every Secret Manager update to clear cache

### 3. DateTime Objects in Neo4j Node Data ✅ PREVIOUSLY FIXED
**Problem:** Python `datetime.now()` objects caused Neo4j's `+=` operator to fail silently
**Fix:** Removed `created_time`, `last_modified`, `created_by`, `last_modified_by` from node_data dictionaries

---

## Latest Deployment

**Engine ID:** `projects/525657242938/locations/us-central1/reasoningEngines/564484871653687296`
**Secret Manager Version:** 102
**Deployment Log:** `app/adk/agents/logs/strategy_supervisor_deployment.txt`

**Code Changes in This Deployment:**
1. Fixed Neo4j result indexing bug (line 263: `result` instead of `result[0]`)
2. Added comprehensive logging for product category lookups
3. Added profile name matching logging with lengths

**Expected Log Output (if working correctly):**
```
Querying Neo4j for product categories with account_id: xxx, category_names: ['Consumer Banking', 'Wealth Management']
Neo4j query returned 2 rows
Found ProductCategory in Neo4j: 'Consumer Banking' -> node_id_xxx
Found ProductCategory in Neo4j: 'Wealth Management' -> node_id_yyy
```

**API Server Status:**
- Running on port 8000
- Restarted at ~13:26 UTC (8:26 EST) to clear secret cache
- Health check: `curl http://localhost:8000/health`

---

## Test Data

**MarketingResearchReport Used in Tests:**

**Product Categories (should exist in Neo4j):**
- Consumer Banking
- Wealth Management

**Customer Profiles:**
1. College Student Carlos
2. Mid-Career Mom Maria
3. High-Net-Worth Henry

**Expected Strategy Counts:**
- Consumer Banking: 2 profiles × 5 strategies = 10 strategies
- Wealth Management: 2 profiles × 5 strategies = 10 strategies
- **Total: 20 strategies**

**Actual Results (from 08:44 EST test):**
- Created 4 strategies (should be 20+)
- "Primary Products" error appeared (fallback placeholder - shouldn't happen)

---

## How to Continue Debugging

### Step 1: Run New Test
User needs to run test using the frontend to trigger strategy generation

### Step 2: Check Cloud Logs
Search for these strings in Cloud Logging (past hour):
```
"Querying Neo4j for product categories"
"Neo4j query returned"
"Found ProductCategory in Neo4j"
"Strategy count mismatch"
```

**If new logging NOT visible:**
- API server not using correct engine ID
- Check Secret Manager has correct engine ID
- Restart API server again

**If new logging IS visible:**
- Examine what categories Neo4j returns
- Check if "Primary Products" still appears (shouldn't)
- Compare requested categories vs found categories

### Step 3: Investigate Based on Logs

**Scenario A: Categories Not Found in Neo4j**
- Check Neo4j database: do "Consumer Banking" and "Wealth Management" nodes exist?
- Verify `product_name` field name in Neo4j schema
- Check case sensitivity in Neo4j (query uses `toLower()`)

**Scenario B: Profile Matching Failure**
- Look for "Looking up profile with key" log messages
- Check if profile names match between Phase 1 (creation) and Phase 2 (reference)
- Profile matching uses `.lower().strip()` normalization

**Scenario C: "Primary Products" Still Appearing**
- Indicates fallback placeholder being used
- Check `app/adk/agents/strategy_agent/orchestrator.py` line 876
- Means the `_create_placeholder_strategy()` is being triggered
- Investigate why strategy generation is failing and triggering fallback

---

## Key Files

### Agent Code
- `app/adk/agents/strategy_agent/marketing_graph_builder.py` - Main graph builder (MODIFIED)
- `app/adk/agents/strategy_agent/orchestrator.py` - Contains fallback logic (line 126, 876)
- `app/adk/agents/strategy_agent/neo4j_tools.py` - Neo4j connection wrapper
- `app/adk/deploy_with_sys_version.py` - Deployment script

### API Code
- `api/src/kene_api/utils/secrets.py` - Secret Manager integration with caching
- `api/src/kene_api/tasks/strategy_tasks.py` - Loads STRATEGY_SUPERVISOR_ENGINE_ID (line 228)
- `api/.env` - Contains `STRATEGY_SUPERVISOR_ENGINE_ID=sm://strategy-supervisor-engine-id`

### Logs & Config
- `app/adk/agents/logs/strategy_supervisor_deployment.txt` - Latest deployment info
- Cloud Logging - Search resource: `cloud_run_revision`

---

## Commands Reference

### Check Secret Manager (needs gcloud auth)
```bash
gcloud secrets versions access latest --secret="strategy-supervisor-engine-id" --project=ken-e-dev
```

### Restart API Server
```bash
# Kill existing
pkill -9 -f "uvicorn src.kene_api.main:app"

# Start fresh (from repo root)
cd /Users/kenwilliams/Documents/github/ken-e/api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Check health
curl http://localhost:8000/health
```

### Deploy New Agent Engine
```bash
cd /Users/kenwilliams/Documents/github/ken-e/app/adk
uv run python deploy_with_sys_version.py

# Update secret manager (done automatically by deploy script)
# Restart API server to clear cache (MANUAL STEP)
```

### Search Cloud Logs
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.message=~"Strategy count mismatch"' --limit 50 --project ken-e-dev --freshness 1h
```

---

## Architecture Notes

### Two-Phase Customer Profile Approach
1. **Phase 1:** Create 2-5 master CustomerProfile nodes (from `ideal_customer_profiles`)
2. **Phase 2:** Map profiles to product categories with 5 strategy types per profile:
   - Problem Awareness
   - Brand Awareness
   - Consideration
   - Conversion
   - Loyalty

### Strategy Count Validation
**File:** `marketing_graph_builder.py` line 200-219

Validates that all expected strategies were created:
```python
expected_count = sum(
    len(mapping.customer_strategies) * 5  # 5 strategy types
    for mapping in research_report.product_category_mappings
)
```

If mismatch, raises `ValueError` which triggers fallback placeholder logic in orchestrator.

### Product Category Lookup Flow
1. Extract category names from `product_category_mappings`
2. Batch query Neo4j using `_get_product_category_node_ids()` (line 242)
3. Neo4j query uses case-insensitive matching: `toLower(pc.product_name)`
4. Build map of `category_name -> node_id`
5. For each category, iterate through customer strategies and create 5 strategy nodes

---

## Next Steps After Computer Restart

1. **Verify API server is running:**
   ```bash
   curl http://localhost:8000/health
   ```
   If not running, start it (see Commands Reference above)

2. **Verify correct engine deployed:**
   ```bash
   cat /Users/kenwilliams/Documents/github/ken-e/app/adk/agents/logs/strategy_supervisor_deployment.txt
   ```
   Should show: `projects/525657242938/locations/us-central1/reasoningEngines/564484871653687296`

3. **Run test from frontend**

4. **Check Cloud Logs** for new logging statements

5. **Analyze results** based on scenarios above

---

## Historical Context

This debugging session started with a code review of PR #166. During testing, discovered:
1. Missing `display_name` attribute (fixed - datetime issue)
2. Strategy count mismatches (current issue)
3. Multiple deployment cycles to add logging
4. API caching issue discovered and documented

**Previous Engine IDs (for reference):**
- 1868276963777445888
- 1688132978682626048
- 4903140162671738880
- 2847246932777107456
- 1455634647919624192
- **564484871653687296** (CURRENT)

---

## Important Notes

⚠️ **Always restart API server after deploying new Agent Engine**
- Secret Manager caching means API won't pick up new engine ID automatically
- Restart required to clear `_secret_cache` and `@lru_cache`

⚠️ **Timezone confusion**
- Cloud logs show Eastern Time (EST/EDT)
- Be aware when correlating log timestamps with deployment times

⚠️ **Strategy count validation is strict**
- ANY mismatch triggers ValueError and fallback placeholder
- This is why "Primary Products" appears when real strategies fail to create
- Fix the underlying cause (category lookup, profile matching) rather than disabling validation
