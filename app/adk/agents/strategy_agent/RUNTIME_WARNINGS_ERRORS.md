# Runtime Warnings & Errors Analysis

**Source**: Cloud Run logs from downloaded-logs-20251008-203757.json
**Engine**: 9150421639375093760
**Date**: 2025-10-08

---

## Summary

Analysis of Cloud Run logs from a complete account creation run revealed **12 distinct warning/error patterns** (excluding fixed issues). Categorized by severity and actionability.

---

## P0 - Critical Errors (Fix Immediately)

### 1. ❌ StrengthWithRisks Missing `references` Attribute

**Count**: 2 occurrences
**Log**:
```
ERROR: 'StrengthWithRisks' object has no attribute 'references'
ERROR: [SPLIT AGENT] ❌ Error generating competitive_strategy: 'StrengthWithRisks' object has no attribute 'references'
```

**Root Cause**: competitive_models.py missing `references` field on `StrengthWithRisks` and `WeaknessWithOpportunities`

**Status**: ✅ FIXED (added references to both models)

**Files**: `app/adk/agents/strategy_agent/competitive_models.py:71, 91`

---

### 2. ✅ Unclosed Connector / Client Session

**Count**: 2 occurrences (from downloaded-logs-20251008)
**Log**:
```
ERROR: Unclosed connector
ERROR: Unclosed client session
```

**Root Cause**: ✅ IDENTIFIED - OpenAI client not being closed

**Location**: `app/adk/agents/strategy_agent/openai_formatter.py:48`

**The Problem**:
```python
client = OpenAIClient(api_key=api_key)
completion = client.beta.chat.completions.parse(...)
return ...  # ← Client never closed! Uses httpx internally
```

**Fix Applied** (not yet deployed):
```python
client = OpenAIClient(api_key=api_key)
try:
    completion = client.beta.chat.completions.parse(...)
    return ...
finally:
    client.close()  # ← Always cleanup
```

**Status**: ✅ FIXED (pending deployment)

**Priority**: P0 - Resource leak fixed

---

### 3. ✅ Exception in Thread (Gemini Schema Complexity)

**Count**: 2 occurrences
**Log**:
```
Exception in thread Thread-38 (_asyncio_thread_main):
Exception in thread Thread-17 (_asyncio_thread_main):
```

**Root Cause**: ✅ IDENTIFIED - Gemini formatter fails with complex schemas

**Full Error**:
```
google.genai.errors.ClientError: 400 INVALID_ARGUMENT
Message: 'The specified schema produces a constraint that has too many states for serving.
Typical causes: schemas with lots of text, long array length limits (nested), complex value matchers'
```

**Why It Happens**:
- Formatter agents use complex Pydantic schemas with nested arrays
- Gemini can't handle the complexity → throws 400 error
- Error occurs in ADK async thread infrastructure
- Gets caught by our try-except at orchestrator.py:485
- Falls back to OpenAI successfully

**Status**: ✅ WORKING AS DESIGNED - Handled exception, just noisy logs

**Fix Options**:
1. Simplify Pydantic schemas (not feasible - we need the structure)
2. Suppress ADK thread exception logging (not in our control)
3. Accept the noise (current approach - fallback works)

**Priority**: P3 - Cosmetic only (fallback succeeds)

---

## P1 - High Priority Warnings (Fix Soon)

### 4. ⚠️ Neo4j `id()` Function Deprecated

**Count**: 11 occurrences (5 in embeddings, 3 in other queries)
**Log**:
```
WARNING: id is deprecated. It is replaced by elementId or consider using an application-generated id
```

**Affected Queries**:
1. Embeddings batch update (5 times):
   ```cypher
   WHERE id(n) = update.node_id  // ← Using deprecated id()
   ```

2. Goal linking (3 times):
   ```cypher
   WHERE id(n) = $node_id  // ← Using deprecated id()
   ```

3. Other graph builder queries (3 times)

**Root Cause**: Using Neo4j's internal `id()` function instead of `elementId()` or application-generated IDs

**Fix**:
```python
# BEFORE (deprecated):
WHERE id(n) = $node_id

# AFTER (use elementId):
WHERE elementId(n) = $node_id

# OR BETTER (use our own node_id):
WHERE n.node_id = $node_id
```

**Files**:
- `app/adk/agents/strategy_agent/embeddings.py` (embeddings query)
- `app/adk/agents/strategy_agent/business_graph_builder.py:561-569` (_link_to_account)
- Anywhere using `id(n)` pattern

**Priority**: P1 - Will break when Neo4j removes id() function

---

### 5. ⚠️ `deleted` Property Doesn't Exist

**Count**: 6 occurrences
**Log**:
```
WARNING: property key does not exist. The property `deleted` does not exist in database `neo4j`
```

**Root Cause**: Code queries for `deleted` property but no nodes have it (soft delete feature not implemented)

**Likely Location**: `app/adk/agents/strategy_agent/neo4j_tools.py:378-414` (get_account_strategies)

**Fix Options**:
1. Remove checks for `deleted` property if soft delete not implemented
2. OR add `deleted: false` when creating nodes if soft delete is planned

**Priority**: P1 - Generates noise in logs, suggests incomplete feature

---

### 6. ❌ ProductCategory Not Found for CustomerProfile Linking

**Count**: 3 occurrences (first logs), 4 occurrences (latest logs)
**Log**:
```
WARNING: ProductCategory 'Public Administration Consulting' not found
WARNING: ProductCategory 'NFL (National Football League)' not found (4x in latest)
```

**Root Cause**: ✅ IDENTIFIED - Strategies generate category names independently

**Why Case-Insensitive Didn't Work**:
1. Business strategy creates: "Financial Services", "Investment Banking"
2. Marketing strategy generates: "NFL (National Football League)", "Public Administration"
3. **Names are COMPLETELY DIFFERENT** - not just case differences!

**Real Problem**: No coordination between business and marketing strategies
- Business generates categories based on company products
- Marketing generates categories based on customer segments
- They should reference the SAME categories

**Solution Options**:
1. Pass business strategy output (ProductCategory names) to marketing strategy
2. Marketing strategy queries existing ProductCategories and uses those names
3. Make ProductCategory creation in business strategy extract from both contexts

**Fix Applied** (not yet deployed):
- Changed to case-insensitive matching: `toLower(pc.category_name) = toLower($category_name)`
- But this won't help if names are completely different

**Status**: ⚠️ PARTIAL FIX - Case insensitive helps but doesn't solve coordination

**Priority**: P1 - Prevents CustomerProfile <-> ProductCategory linking

---

### 7. ⚠️ Firestore Index Missing for Bottlenecks Query

**Count**: 1 occurrence
**Log**:
```
ERROR: Failed to get bottlenecks: 400 The query requires an index
```

**Root Cause**: Firestore composite index not created for performance_profiles collection

**Required Index**:
- Collection: `performance_profiles_acc_{account_id}`
- Fields: `is_bottleneck`, `duration_seconds`, `timestamp`, `__name__`

**Fix**: Create Firestore index via console link or firestore.indexes.json

**Priority**: P1 - Performance profiling not working

---

## P2 - Medium Priority (Deprecations)

### 8. ⚠️ Deprecated Sync Method Usage

**Count**: 9 occurrences
**Log**:
```
WARNING: Deprecated. Please migrate to the async method.
```

**Root Cause**: Using sync Firestore methods instead of async

**Likely Location**: `app/adk/agents/strategy_agent/firestore.py` - methods ending with `_sync`

**Fix**: Migrate to async methods (but Agent Engine might require sync)

**Priority**: P2 - Works for now, but should migrate eventually

---

### 9. ⚠️ Vertex AI SDK Deprecation

**Count**: 2 occurrences
**Log**:
```
WARNING: This feature is deprecated as of June 24, 2025 and will be removed on June 24, 2026
File: vertexai/_model_garden/_model_garden_models.py:278
```

**Root Cause**: Using deprecated Vertex AI SDK feature

**Fix**: Needs investigation of what specific feature is deprecated

**Priority**: P2 - Have until June 2026 to fix

---

### 10. ⚠️ output_schema + Agent Transfer Conflict

**Count**: 4 occurrences (one per formatter agent)
**Log**:
```
WARNING: Invalid config for agent business_formatter: output_schema cannot co-exist with agent transfer configurations. Setting disallow_transfer_to_parent=True, disallow_transfer_to_peers=True
```

**Root Cause**: ADK limitation - agents with `output_schema` can't transfer to parent/peers

**Current Behavior**: ADK automatically disables transfers (expected, this is why we use split agent architecture)

**Status**: ✅ EXPECTED - This is the ADK constraint we're working around with split agents

**Priority**: P2 - Informational, not an error

---

## P3 - Low Priority (Informational)

### 11. ℹ️ ALTS Credentials Warning

**Count**: 13 occurrences
**Log**:
```
E0000 00:00:1759931220.754111 237 alts_credentials.cc:93] ALTS creds ignored. Not running on GCP and untrusted ALTS is not enabled.
```

**Root Cause**: Google ALTS (Application Layer Transport Security) only works on GCP infrastructure

**Status**: ✅ EXPECTED - Agent Engine runs in GCP sandbox, not directly on GCP Compute

**Priority**: P3 - Informational, can be ignored

---

### 12. ℹ️ Non-Text Parts in Response (function_call)

**Count**: 4 occurrences
**Log**:
```
WARNING: Warning: there are non-text parts in the response: ['function_call'], returning concatenated text result from text parts
```

**Root Cause**: Gemini returns function_call parts when using tools (google_search_agent)

**Status**: ✅ EXPECTED - This is how tool calls work, warning can be ignored

**Priority**: P3 - Informational

---

### 13. ℹ️ Gemini Formatting Fallback to OpenAI

**Count**: 2 occurrences
**Log**:
```
WARNING: [SPLIT AGENT] ⚠️ Gemini formatting failed: Expecting value: line 1 column 1 (char 0), falling back to OpenAI
```

**Root Cause**: Gemini formatter occasionally returns invalid JSON

**Status**: ✅ WORKING AS DESIGNED - OpenAI fallback catches it

**Priority**: P3 - Fallback mechanism working correctly

---

### 14. ℹ️ Operation Timeout Warnings

**Count**: 5 occurrences per run
**Log**:
```
WARNING: Operation timeout warning: orchestrator:strategy_generation took 393.96s (latest)
WARNING: Operation timeout warning: marketing_strategy_split:strategy_generation took 138.33s
WARNING: Operation timeout warning: competitive_strategy_split:strategy_generation took 98.36s
WARNING: Operation timeout warning: business_strategy_split:strategy_generation took 109.86s
WARNING: Operation timeout warning: brand_guidelines_split:strategy_generation took 45.00s
```

**Root Cause**: Performance profiling threshold set too low for expected operation time

**Status**: ✅ WORKING - Strategies complete successfully despite warnings

**Impact**: Total ~6-7 minutes for full strategy generation (within acceptable range for complex AI operations)

**Recommendation**: Change from WARNING to INFO level
- These are informational metrics, not problems
- Or increase threshold to 600s (10 minutes)

**Priority**: P3 - Cosmetic log noise, should downgrade to INFO

---

## Summary by Priority

| Priority | Count | Action Needed |
|----------|-------|---------------|
| **P0 - Critical** | 3 | Fix immediately (unclosed connections, thread exceptions) |
| **P1 - High** | 4 | Fix soon (Neo4j deprecations, missing indexes, ProductCategory lookup) |
| **P2 - Medium** | 3 | Plan migration (sync→async, SDK deprecation, expected warnings) |
| **P3 - Low** | 5 | Informational (expected behavior, performance notes) |

**Total Issues**: 15
**Already Fixed**: 1 (StrengthWithRisks.references)
**Actionable**: 7
**Informational**: 7

---

## Recommended Actions

### Immediate (P0):

1. **Fix unclosed connections**
   - Add proper connection cleanup in orchestrator
   - Use context managers for Neo4j sessions
   - Ensure all async clients are closed

2. **Investigate thread exceptions**
   - Get full stack traces
   - May be related to unclosed connections

### Soon (P1):

3. **Replace id() with elementId() or node.node_id**
   - Update embeddings.py query
   - Update business_graph_builder.py _link_to_account
   - Use application-generated node_id instead

4. **Fix ProductCategory lookup for CustomerProfiles**
   - Case-insensitive matching
   - OR pass category list between strategies
   - OR use node_id references

5. **Remove deleted property checks**
   - OR implement soft delete feature properly

6. **Create Firestore index for bottlenecks**
   - Run provided console link
   - OR add to firestore.indexes.json

### Later (P2):

7. **Migrate to async Firestore methods** (if Agent Engine supports it)
8. **Check Vertex AI SDK deprecation details**
9. **Confirm output_schema warnings are expected**

---

## Files Requiring Changes:

**High Priority**:
- `app/adk/agents/strategy_agent/orchestrator.py` - Connection cleanup
- `app/adk/agents/strategy_agent/embeddings.py` - Replace id() function
- `app/adk/agents/strategy_agent/business_graph_builder.py:561-569` - Replace id() function
- `app/adk/agents/strategy_agent/marketing_graph_builder.py:337` - ProductCategory lookup
- `app/adk/agents/strategy_agent/neo4j_tools.py:378-414` - Remove deleted property checks

**Medium Priority**:
- `app/adk/agents/strategy_agent/firestore.py` - Async migration
- Firestore indexes configuration
