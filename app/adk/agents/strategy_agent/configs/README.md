# Agent Configuration Guide for Evaluators

## Overview

This guide explains how to iterate on agent configurations without redeployment using Firestore and Weave. The business strategy agents (researcher + formatter) now load their configurations from Firestore at runtime, enabling instant iteration cycles.

## Quick Start Workflow

```
1. Edit config in Firestore Console
   ↓
2. Test via deployed Agent Engine (no redeploy!)
   ↓
3. View results in Weave
   ↓
4. Compare variants
   ↓
5. Iterate (repeat from step 1)
```

**Key Benefit:** Go from config change to results in seconds, not 15-20 minutes!

---

## Step 1: Accessing Firestore Configurations

### Firebase Console

1. Open [Firebase Console](https://console.firebase.google.com/project/ken-e-dev/firestore)
2. Navigate to **Firestore Database**
3. Find the `agent_configs` collection
4. You'll see two documents:
   - `business_researcher` - Research agent with google_search tool
   - `business_formatter` - Formatting agent with StructuredBusinessStrategy schema

### Config Structure

Each config document contains:

```json
{
  "name": "business_researcher",
  "model": "gemini-2.0-flash",
  "description": "Researches business strategy information",
  "instruction": "You are a business strategy researcher...",
  "generate_content_config": {
    "temperature": 0.3,
    "max_output_tokens": 2500
  },
  "metadata": {
    "version": "v1.0",
    "variant_name": "baseline",
    "experiment_id": "baseline",
    "updated_at": "2025-10-15T00:00:00Z",
    "updated_by": "your-email@example.com",
    "notes": "Description of changes"
  }
}
```

---

## Step 2: Making Configuration Changes

### What You Can Change

#### 1. **Instructions** (Most Common)
- Edit the `instruction` field
- Add/remove examples
- Adjust tone or specificity
- Change prompt structure

**Example Changes:**
- Make instructions more detailed
- Add specific formatting requirements
- Include domain-specific examples

#### 2. **Model Selection**
- Change `model` field
- Options:
  - `gemini-2.0-flash` (fast, cheap)
  - `gemini-2.5-flash` (newer, faster)
  - `gemini-2.5-pro` (best quality, expensive)

#### 3. **Temperature**
- Edit `generate_content_config.temperature`
- Range: 0.0 to 1.0
- Lower = more focused/deterministic
- Higher = more creative/varied

#### 4. **Max Tokens**
- Edit `generate_content_config.max_output_tokens`
- Typical range: 1000-8000
- Higher = longer responses

### What NOT to Change

❌ **Do NOT modify:**
- `name` field (used for lookups)
- `tools` (managed in code)
- `output_schema` (managed in code)

### Update Metadata

**Always update metadata when making changes:**

```json
{
  "metadata": {
    "version": "v1.1",                    // Increment version
    "variant_name": "detailed_swot",      // Descriptive name
    "experiment_id": "exp_002",           // Group related tests
    "updated_at": "2025-10-15T10:30:00Z", // Current timestamp
    "updated_by": "evaluator@ken-e.com",  // Your email
    "notes": "Added more detailed SWOT analysis instructions with examples"
  }
}
```

---

## Step 3: Testing Your Changes

### No Deployment Required!

Once you save changes in Firestore:
1. Changes take effect **immediately**
2. Next agent invocation uses new config
3. No need to redeploy code

### Invoke Agent Engine

**Via API:**
```bash
curl -X POST https://[agent-engine-url]/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": "Generate business strategy for TestCorp"
    }]
  }'
```

**Via Frontend:**
- Use the KEN-E application
- Trigger account creation flow
- Strategy generation will use latest configs

---

## Step 4: Viewing Results in Weave

### Accessing Weave

1. Open [Weave Dashboard](https://wandb.ai/your-org/ken-e-strategy-agent)
2. Navigate to **Traces** tab
3. Find your recent execution

### What You'll See

#### Config Metadata in Traces

Every trace includes:
- `config_version` - Which version was used
- `variant_name` - Which variant
- `experiment_id` - Experiment grouping
- `model` - Model used
- `temperature` - Temperature setting
- `updated_by` - Who made the config
- `updated_at` - When it was updated

#### Execution Details

- Full execution trace
- Input/output for each agent
- Token usage and costs
- Response time
- Error details (if any)

### Finding Your Traces

#### Filter by Config Version
```
config_version:v1.1
```

#### Filter by Variant
```
variant_name:detailed_swot
```

#### Filter by Experiment
```
experiment_id:exp_002
```

#### Filter by Date Range
Use Weave's date picker to narrow results

---

## Step 5: Comparing Variants

### Side-by-Side Comparison

1. Select multiple traces in Weave
2. Click "Compare" button
3. View differences:
   - Output quality
   - Token usage
   - Response time
   - Cost per run
   - Config parameters

### Comparison Checklist

When comparing variants, evaluate:

- [ ] **Output Quality**
  - Completeness
  - Accuracy
  - Relevance
  - Formatting

- [ ] **Performance**
  - Response time
  - Token usage
  - Cost

- [ ] **Consistency**
  - Results across multiple runs
  - Error rates

### Documenting Results

Create a comparison table:

| Variant | Version | Model | Temp | Tokens | Cost | Quality Score | Notes |
|---------|---------|-------|------|--------|------|---------------|-------|
| baseline | v1.0 | 2.0-flash | 0.3 | 1500 | $0.15 | 7/10 | Too generic |
| detailed_swot | v1.1 | 2.0-flash | 0.3 | 2200 | $0.22 | 9/10 | Much better! |
| high_temp | v1.2 | 2.0-flash | 0.7 | 2100 | $0.21 | 6/10 | Too creative |

---

## Common Iteration Patterns

### Pattern 1: Refining Instructions

**Goal:** Improve output specificity

```
v1.0 → v1.1 → v1.2 → v1.3
      Add     Add      Simplify
   examples structure
```

**Steps:**
1. Baseline (v1.0)
2. Add specific examples (v1.1)
3. Add structural requirements (v1.2)
4. Simplify if needed (v1.3)

### Pattern 2: Model Selection

**Goal:** Balance cost vs quality

```
Try: gemini-2.0-flash → gemini-2.5-flash → gemini-2.5-pro
           ↓                    ↓                  ↓
         cheap             moderate            expensive
         fast              faster              slower
         good              better              best
```

### Pattern 3: Temperature Tuning

**Goal:** Find optimal creativity

```
Try: 0.1 → 0.3 → 0.5 → 0.7
      ↓     ↓     ↓     ↓
    rigid  good  varied  creative
```

### Pattern 4: A/B Testing

**Goal:** Compare two approaches

1. Create variant A: `experiment_id: "exp_001_a"`
2. Create variant B: `experiment_id: "exp_001_b"`
3. Run multiple tests with each
4. Compare results in Weave
5. Choose winner

---

## Best Practices

### Version Control

- **Increment version** for every change
- Use semantic versioning: `v1.0`, `v1.1`, `v2.0`
- Major changes = bump major version
- Minor tweaks = bump minor version

### Naming Conventions

- **variant_name:** Descriptive, lowercase-hyphenated
  - ✅ `detailed-swot-with-examples`
  - ❌ `My Test 2`

- **experiment_id:** Group related tests
  - ✅ `exp_001_prompt_length`
  - ❌ `test123`

### Documentation

Always update `notes` field:
```json
"notes": "Changed instruction to include specific SWOT examples. Testing if examples improve output structure. Previous version was too vague about opportunity/risk links."
```

### Testing Protocol

1. **Baseline First:** Always test baseline before changes
2. **Multiple Runs:** Test each variant 3-5 times
3. **Same Test Cases:** Use consistent test companies
4. **Document Results:** Record findings in comparison table

---

## Creating Config Variants

### Option 1: Edit Existing (Recommended for Iteration)

1. Open config in Firestore Console
2. Edit fields directly
3. Update metadata
4. Save

**Pro:** Quick, preserves history in Weave
**Con:** Overwrites previous version

### Option 2: Create New Document (Recommended for A/B Tests)

1. Duplicate existing config
2. Rename document (e.g., `business_researcher_variant_a`)
3. Modify fields
4. Update code to use new doc_id

**Pro:** Parallel testing, easy rollback
**Con:** Requires code change to switch

---

## Rollback Procedure

### If Config Causes Issues

1. **Immediate Fix:** Revert config in Firestore
   - Copy previous values
   - Update metadata
   - Save

2. **Verify Fix:** Test agent invocation

3. **Document:** Add notes about what went wrong

### Version History

Firestore doesn't auto-version. **Recommendation:**
- Keep baseline configs in this repo
- Commit winning configs to git
- Use git history for rollback reference

---

## Troubleshooting

### Config Not Taking Effect

**Symptoms:** Agent still using old config

**Solutions:**
1. Verify you saved changes in Firestore
2. Check `doc_id` matches code (`business_researcher` or `business_formatter`)
3. Check Agent Engine logs for config load errors
4. Verify no caching issues

### Config Load Errors

**Symptoms:** Agent fails to start, error in logs

**Common Issues:**
1. **Invalid JSON in instruction field**
   - Check for unescaped quotes
   - Use JSON validator

2. **Missing required fields**
   - Ensure `name`, `model`, `instruction` present

3. **Invalid model name**
   - Use exact model names (see list above)

### Weave Not Showing Config Metadata

**Symptoms:** Traces missing config info

**Solutions:**
1. Check Weave initialization in logs
2. Verify WANDB_API_KEY in Secret Manager
3. Check firestore connection
4. Confirm config_loader imported correctly

---

## Example: Complete Iteration Cycle

### Scenario

Improve SWOT analysis quality in business strategy

### Steps

**1. Baseline Test (v1.0)**
```
experiment_id: "swot_improvement"
variant_name: "baseline"
version: "v1.0"
```
- Run 3 tests
- Quality score: 6/10
- Issue: Opportunities/risks not specific enough

**2. Add Examples (v1.1)**
```
Updated instruction field:
"For each strength, identify 2-3 concrete opportunities.
Example:
Strength: Strong brand recognition
Opportunities:
- Launch premium product line leveraging brand trust
- Expand to adjacent markets with brand as anchor
"
```
- Run 3 tests
- Quality score: 8/10
- Better, but still needs work

**3. Add Structure (v1.2)**
```
Added structural requirements:
"Format each opportunity as:
1. Opportunity title (action-oriented)
2. How it leverages the strength
3. Expected impact
"
```
- Run 3 tests
- Quality score: 9/10
- Winner!

**4. Document & Commit**
- Export v1.2 config
- Commit to git
- Update baseline in repo

---

## FAQ

**Q: How long does it take for config changes to apply?**
A: Immediately. Next agent invocation uses the new config.

**Q: Can I test multiple variants simultaneously?**
A: Yes, but you need to create separate config documents and update code to reference them.

**Q: What if I break the config?**
A: Revert in Firestore Console. Previous config takes effect immediately.

**Q: Can I version configs automatically?**
A: Not currently. Use git to track baseline configs and manual metadata for variants.

**Q: Do config changes affect running executions?**
A: No, only new executions use updated configs.

**Q: Can I see config diff in Weave?**
A: Not directly, but config metadata helps identify which version was used. Compare manually.

---

## Support

**Questions?** Contact the team:
- Check existing traces in Weave for examples
- Review baseline configs in this repo
- Ask in #ken-e-strategy-agents Slack channel

---

## Next Steps

1. ✅ Initialize baseline configs: `python scripts/upload_baseline_configs.py`
2. ✅ Verify configs in Firestore Console
3. ✅ Run baseline test and view in Weave
4. ✅ Create your first variant
5. ✅ Compare results
6. ✅ Iterate!

Happy evaluating! 🚀
