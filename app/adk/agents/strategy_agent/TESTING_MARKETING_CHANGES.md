# Testing Guide: Master Customer Profile Changes

This guide explains how to test the new two-phase marketing strategy approach locally.

## Prerequisites

1. **Google Cloud Authentication**
   ```bash
   gcloud auth application-default login
   gcloud config set project ken-e-dev
   ```

2. **Environment Setup**
   ```bash
   cd api && ./scripts/set_environment.sh development
   ```

3. **Update Firestore Config**
   - Navigate to Firebase Console → Firestore Database
   - Collection: `agent_configs`
   - Document ID: `marketing_researcher`
   - Copy content from `firestore_config_marketing_researcher.md`
   - Update the document in Firestore

## Testing Approach

### Option 1: Unit Tests (No API/Network Required)

The safest way to verify the changes work correctly:

```bash
# Run the new marketing models tests
uv run pytest app/adk/agents/strategy_agent/tests/test_marketing_models.py -v

# Expected: All 10 tests pass ✅
```

These tests verify:
- Master profile list constraints (2-5 total)
- Profile reference validation
- Profile reusage across categories
- Pydantic model validation

### Option 2: Local API Testing (Requires GCP Access)

Test the full end-to-end flow:

```bash
# Start API server
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, test the strategy generation endpoint
curl -X POST http://localhost:8000/api/v1/strategy/generate \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Clothing Retailer",
    "industry": "Fashion & Apparel",
    "websites": "example.com",
    "customer_regions": "USA,Europe",
    "annual_ad_budget": 100000
  }'
```

### Option 3: Frontend Testing (Full Stack)

Test through the UI:

```bash
# Terminal 1: Start API
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend
cd frontend && npm run dev:development
```

Then navigate to `http://localhost:8080` and:
1. Create a new strategy
2. Wait for marketing strategy to complete
3. Verify the customer profiles section shows 2-5 total profiles (not per category)

## What to Verify

### In the Response/Database

Check the `marketing_strategy` document structure:

```json
{
  "ideal_customer_profiles": [
    {
      "display_name": "Marketing Manager Mary",
      "narrative": "...",
      "problem_awareness_strategy": "...",
      "brand_awareness_strategy": "...",
      "consideration_strategy": "...",
      "conversion_strategy": "...",
      "loyalty_strategy": "...",
      "references": [...]
    },
    {
      "display_name": "Technical Director Tom",
      "narrative": "...",
      ...
    }
  ],
  "product_category_mappings": [
    {
      "category_name": "Cloud Services",
      "ideal_customer_profile_names": [
        "Marketing Manager Mary",
        "Technical Director Tom"
      ]
    },
    {
      "category_name": "Analytics Platform",
      "ideal_customer_profile_names": [
        "Marketing Manager Mary"
      ]
    }
  ]
}
```

### Success Criteria

✅ **Total profiles: 2-5** (not 6-15)
✅ **Profiles have unique display_name values**
✅ **product_category_mappings references match display_names**
✅ **Same profile can appear in multiple categories**
✅ **No duplicate CustomerProfile nodes in Neo4j**

### In Neo4j (if accessible)

Run this Cypher query to verify:

```cypher
MATCH (cp:CustomerProfile)-[:BELONGS_TO]->(:Account {account_id: "your_account_id"})
RETURN count(cp) as total_profiles

// Should return 2-5, not 6-15
```

Check profile reusage:

```cypher
MATCH (pc:ProductCategory)-[:IS_MARKETED_TO]->(cp:CustomerProfile)
WHERE pc.account_id = "your_account_id"
RETURN pc.product_name, collect(cp.description) as profiles
```

## Troubleshooting

### Issue: "Profile reference not found"

**Cause**: The formatter created profiles with display_names that don't match the mappings

**Fix**: Check Firestore config was updated correctly. The instructions should emphasize using the exact display_name in mappings.

### Issue: Still seeing 6-15 profiles

**Cause**: Firestore config not updated OR using cached agent config

**Solution**:
1. Verify Firestore `agent_configs/marketing_researcher` has the new v2.0.0 config
2. Clear any agent caches
3. Restart the API server

### Issue: Validation error on min_length

**Cause**: Pydantic validation requires at least 2 master profiles

**Solution**: This is expected behavior. The agent should always create 2-5 profiles.

## Example Test Scenarios

### Scenario 1: B2B SaaS Company

**Input:**
- Company: "CloudTech Solutions"
- Products: Cloud Services, Analytics Platform, Security Tools

**Expected Output:**
- 3-4 master profiles (e.g., "Marketing Manager Mary", "Technical Director Tom", "Data Analyst Dana")
- Cloud Services → mapped to 2-3 profiles
- Analytics Platform → mapped to 2 profiles
- Security Tools → mapped to 1-2 profiles

### Scenario 2: Clothing Retailer

**Input:**
- Company: "Fashion Forward"
- Products: Men's Clothes, Women's Clothes, Children's Clothes

**Expected Output:**
- 4 master profiles (e.g., "Young Men", "Old Men", "Young Women", "Old Women")
- Men's Clothes → Young Men, Old Men
- Women's Clothes → Young Women, Old Women
- Children's Clothes → Young Women, Old Women (parents buying for kids)

## Rollback Plan

If issues arise, you can revert:

1. **Revert Code Changes:**
   ```bash
   git checkout main app/adk/agents/strategy_agent/marketing_models.py
   git checkout main app/adk/agents/strategy_agent/marketing_graph_builder.py
   git checkout main app/adk/agents/strategy_agent/orchestrator.py
   ```

2. **Revert Firestore Config:**
   - Restore the previous `marketing_researcher` config in Firestore
   - Or set version back to v1.0.0

3. **Delete test file:**
   ```bash
   rm app/adk/agents/strategy_agent/tests/test_marketing_models.py
   ```

## Questions?

Contact the development team or check:
- [marketing_models.py](marketing_models.py) - Pydantic schema definitions
- [marketing_graph_builder.py](marketing_graph_builder.py) - Graph building logic
- [orchestrator.py](orchestrator.py) - Agent orchestration and instructions
