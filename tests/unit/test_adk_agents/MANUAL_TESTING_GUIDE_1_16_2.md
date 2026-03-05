# Manual Testing Guide: Story 1.16.2 - Fix ADK EventsCompactionConfig Version Mismatch

## Prerequisites
- Access to Google Cloud Console for project `ken-e-dev`
- The agent has been deployed via `app/adk/deploy_ken_e.py` (deployment log: `app/adk/agents/logs/ken_e_deployment.txt`)
- Access to the KEN-E chat interface (frontend running on port 8080) or the API endpoint

### Start Services
```bash
# Start API
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Start Frontend
cd frontend && npm run dev:development
```

App URL: http://localhost:8080

## Test 1: No AttributeError on EventsCompactionConfig (AC1)

**Context:** Previously, the deployed ADK version (1.23.0) was missing `token_threshold` and `event_retention_size` attributes on `EventsCompactionConfig`, causing `AttributeError` at runtime. The fix pins ADK to 1.26.0 which natively supports these attributes.

**Steps:**
1. Open Google Cloud Console > Cloud Logging for project `ken-e-dev`
2. Filter logs for the Reasoning Engine resource:
   ```
   resource.type="aiplatform.googleapis.com/ReasoningEngine"
   ```
3. Send a test message via the chat interface: "What is KEN-E?"
4. Check the logs for any `AttributeError` mentioning `EventsCompactionConfig`, `token_threshold`, or `event_retention_size`

**Expected Results:**
- [ ] No `AttributeError` appears in logs related to `EventsCompactionConfig`
- [ ] The chat response is returned successfully (not an error message)
- [ ] Logs show normal agent execution without compaction-related crashes

## Test 2: Deployment Succeeds Without Compaction Errors (AC3)

**Steps:**
1. Check the deployment log file:
   ```bash
   cat app/adk/agents/logs/ken_e_deployment.txt
   ```
2. Verify the deployment record in Google Cloud Console:
   - Navigate to Vertex AI > Agent Engine
   - Locate the engine ID from the deployment log
3. Check the Agent Engine health endpoint:
   ```bash
   curl http://localhost:8000/api/v1/chat/health
   ```

**Expected Results:**
- [ ] `ken_e_deployment.txt` contains a valid Engine ID and recent timestamp
- [ ] The engine is listed and active in Google Cloud Console
- [ ] Health endpoint returns a successful status (not an error about compaction)

## Test 3: Session Compaction Works After Fix (AC4)

**Context:** EventsCompactionConfig is set to compact every 5 user invocations with a 50K token threshold and 10 event retention.

**Steps:**
1. Open the KEN-E chat interface at http://localhost:8080
2. Start a new chat session
3. Send at least 6 messages in sequence (to trigger compaction at 5 invocations):
   - Message 1: "Tell me about digital marketing trends"
   - Message 2: "What are the best practices for SEO in 2026?"
   - Message 3: "How does social media advertising compare to search advertising?"
   - Message 4: "What metrics should I track for a marketing campaign?"
   - Message 5: "Can you summarize the key points from our conversation?"
   - Message 6: "What new topics should I explore based on our discussion?"
4. After message 6, check Cloud Logging for compaction activity:
   ```
   resource.type="aiplatform.googleapis.com/ReasoningEngine"
   "compaction" OR "summarize" OR "LlmEventSummarizer"
   ```
5. Verify that message 6's response acknowledges prior conversation context (proving compaction preserved context)

**Expected Results:**
- [ ] All 6 messages receive valid responses without errors
- [ ] Message 6's response references topics from earlier messages (context preserved)
- [ ] No `RuntimeError: Event loop is closed` in logs (previous compaction bug)
- [ ] No `AttributeError` related to compaction in logs
- [ ] Compaction-related log entries appear (if verbose logging is enabled)

## Test 4: Version Compatibility Documentation (AC5)

**Steps:**
1. Check that the ADK version is explicitly pinned in requirements:
   ```bash
   grep "google-adk" app/adk/requirements.txt
   ```
2. Check that pyproject.toml has the minimum version:
   ```bash
   grep "google-adk" app/adk/pyproject.toml
   ```
3. Review the deploy script for version-related documentation:
   ```bash
   head -30 app/adk/deploy_ken_e.py
   ```

**Expected Results:**
- [ ] `requirements.txt` shows `google-adk==1.26.0` (exact pin)
- [ ] `pyproject.toml` shows `google-adk>=1.26.0` (minimum version)
- [ ] The monkey-patch hack (`object.__setattr__` for `token_threshold`/`event_retention_size`) has been removed from `deploy_ken_e.py`
- [ ] `EventsCompactionConfig` now uses native `token_threshold=50000` and `event_retention_size=10` parameters

## Verification Checklist Summary

| Test | What It Validates | AC |
|------|-------------------|----|
| Test 1 | No AttributeError on EventsCompactionConfig | AC1 |
| Test 2 | Deployment succeeds without compaction errors | AC3 |
| Test 3 | Session compaction works correctly | AC4 |
| Test 4 | Version compatibility documented | AC5, AC2 |
