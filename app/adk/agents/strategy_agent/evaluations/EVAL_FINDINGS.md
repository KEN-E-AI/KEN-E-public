# Strategy Agent Evaluation Findings

**Analysis Date:** 2025-11-10
**Data Source:** W&B Weave feedback (3000+ scorer results)

## Executive Summary

Based on analysis of existing evaluation runs (`company_overview_alignment_eval` and `product_portfolio_alignment_eval`), the strategy agent has significant quality issues that need to be addressed through prompt improvements.

### Overall Performance

| Scorer | Pass Rate | Status | Priority |
|--------|-----------|--------|----------|
| **MissionStatementScorer** | 50.5% | ❌ CRITICAL | P0 |
| **ProductServiceDescriptionScorer** | 59.9% | ⚠️ POOR | P0 |
| **TargetCustomerScorer** | 60.6% | ⚠️ POOR | P1 |
| **CompanyOverviewLengthScorer** | 66.3% | ⚠️ NEEDS WORK | P1 |
| **BrandIdentityScorer** | 67.9% | ⚠️ NEEDS WORK | P2 |
| **FoundingDateScorer** | 75.6% | ⚙️ ACCEPTABLE | P2 |

---

## Critical Issues

### Issue #1: Empty/Missing Outputs (Cross-Cutting)

**Impact:** 15+ failures per scorer
**Root Cause:** Agent producing empty `company_overview_summary` outputs
**Severity:** CRITICAL

**Evidence:**
- All scorers report "Empty or missing summary" as top failure reason
- Affects ALL evaluation criteria uniformly

**Required Action:**
- Investigate why agent produces empty outputs
- Add validation/retry logic for empty responses
- Ensure prompts explicitly require non-empty outputs

---

### Issue #2: Mission Statement Missing/Incomplete (50.5% pass rate)

**Impact:** Half of all outputs lack acceptable mission statements
**Severity:** CRITICAL

**Failure Patterns:**
1. **Empty outputs** (15 failures) - No summary generated
2. **Missing mission** (11+ failures) - Summary describes company but doesn't state mission/vision/purpose

**Example Failures:**
- "The summary describes the company's services and structure but does not include an explicit or implied mission statement"
- "The summary describes what the company does and who it serves, but it does not explicitly state or imply the company's mission"

**Example Success:**
- "The summary explicitly states the company's mission: 'The company's mission is to develop, produce, package, and sell food products with high regard for...'"

**Required Prompt Changes:**
```
CURRENT: Generic instruction to include company overview
NEEDED: Explicit requirement:
  "You MUST include the company's mission statement, vision, or purpose.
   This should clearly state WHY the company exists and what it aims to achieve.
   Examples:
   - 'Mission: To empower every person and organization on the planet to achieve more'
   - 'Vision: To be the most customer-centric company'
   - 'Purpose: To organize the world's information and make it universally accessible'"
```

---

### Issue #3: Product/Service Descriptions Unclear (59.9% pass rate)

**Impact:** 40% of outputs have inadequate product/service descriptions
**Severity:** CRITICAL

**Failure Patterns:**
1. **Empty outputs** (77 failures) - No summary at all
2. **Generic descriptions** (56+ failures) - Mentions categories but not specific products
3. **Too vague** - "financial services" instead of specific offerings

**Example Failures:**
- "The summary mentions 'financial services' which is a generic category, not specific products or services"
- "The summary mentions commercial banking, wealth management, and investment banking, which are service categories, not specific products"

**Example Success:**
- "The summary mentions that Mapro Foods produces jams and is known for its fruit-based products, which clearly describes the type of product offered"

**Required Prompt Changes:**
```
CURRENT: Ask for products/services generally
NEEDED: Explicit requirement with examples:
  "Describe the company's SPECIFIC products and services, not just categories.

   BAD: 'Provides financial services'
   GOOD: 'Offers checking and savings accounts, mortgages, business loans, and wealth management'

   BAD: 'Technology company'
   GOOD: 'Develops cloud computing platforms, AI tools, and enterprise software solutions'

   Be concrete and specific about what the company actually sells or provides."
```

---

### Issue #4: Target Customer Identification Weak (60.6% pass rate)

**Impact:** 40% of outputs don't clearly identify target customers
**Severity:** HIGH

**Failure Patterns:**
1. **Empty outputs** (15 failures)
2. **Too vague** - Doesn't identify specific segments
3. **Missing entirely** - Summary doesn't mention customers at all

**Example Failures:**
- "The summary does not explicitly identify the company's target customers or customer segments"
- "It mentions services but not who the target customers are"

**Example Success:**
- "The summary mentions a 'nationwide presence' and aims to be a 'household name,' indicating a broad customer base"

**Required Prompt Changes:**
```
CURRENT: Implicit expectation of customer information
NEEDED: Explicit requirement:
  "Identify the company's target customers and customer segments.
   Be specific about:
   - WHO they serve (B2B, B2C, specific industries, demographics)
   - Market segments (e.g., 'small businesses', 'enterprise clients', 'millennials')
   - Geographic focus if relevant

   Example: 'Targets tech startups and SMBs in North America, with a focus on companies with 10-500 employees'"
```

---

## Moderate Issues

### Issue #5: Character Length (66.3% pass rate)

**Target Range:** 400-4000 characters
**Actual Range:** 335-894 characters (avg: 565)
**Severity:** MODERATE

**Analysis:**
- 33.7% of outputs are either too short or too long
- Average of 565 chars is well within range
- Issue is variability, not systematic under/over-generation

**Required Prompt Changes:**
```
Add explicit length guidance:
  "The company overview summary should be 400-4000 characters (roughly 2-3 substantial paragraphs).
   Aim for comprehensive but concise coverage of all key elements."
```

---

### Issue #6: Brand Identity Elements (67.9% pass rate)

**Impact:** 32% lack clear brand identity elements
**Severity:** MODERATE

**Failure Patterns:**
- Empty outputs (15 failures)
- Focuses on market position without brand characteristics
- Missing brand personality/positioning

**Example Failures:**
- "The summary describes the company's market position ('second-largest bank') but not brand identity elements"

**Example Success:**
- "Mentions Mapro being a 'leading Indian food processing company known for its fruit-based products' and aiming to be a 'household name'"

---

### Issue #7: Founding Date (75.6% pass rate)

**Impact:** 24% missing founding information
**Severity:** LOW

**Performance:** Acceptable but could be better

**Failure Patterns:**
- Mentions "rich history" but no specific founding date
- Mentions mergers but not original founding

**Required Prompt Changes:**
```
Add specific instruction:
  "Include the company's founding date or age if available.
   Example: 'Founded in 1959' or 'Established over 60 years ago'"
```

---

## Product Portfolio Evaluation

**Note:** Limited data available (need to check `product_portfolio_alignment_eval` specifically)

From available data:
- Product category descriptions need to be category-level, not single-product focused
- Length target: 200-1000 characters

---

## Action Plan

### Priority 0 (Critical - Must Fix)

1. **Fix Empty Outputs**
   - Add validation that company_overview_summary is not empty
   - Add retry logic if empty response received
   - Log/alert when empty outputs occur

2. **Improve Mission Statement Generation**
   - Add explicit prompt requirement with examples
   - Make mission/vision/purpose a mandatory field
   - Show clear examples of good vs bad

3. **Improve Product/Service Descriptions**
   - Require SPECIFIC products, not just categories
   - Provide clear examples of specificity
   - Penalize generic terms like "financial services"

### Priority 1 (High - Should Fix Soon)

4. **Clarify Target Customer Requirements**
   - Explicit instruction to identify segments
   - Require specificity (not just "nationwide")

5. **Add Length Constraints**
   - State 400-4000 character range explicitly
   - Suggest 2-3 substantial paragraphs

### Priority 2 (Medium - Nice to Have)

6. **Strengthen Brand Identity Prompts**
   - Ask for brand positioning explicitly
   - Distinguish between market position and brand identity

7. **Emphasize Founding Information**
   - Make founding date/age more prominent in prompt

---

## Next Steps

1. **Review actual prompts** - Look at current prompts in `strategy_agent/` code
2. **Update prompts** - Apply changes based on findings above
3. **Generate new outputs** - Run agent with updated prompts
4. **Create new dataset** - From fresh traces
5. **Re-evaluate** - Run evaluations to measure improvement
6. **Iterate** - Repeat based on new results

---

## Evaluation Infrastructure Status

✅ **COMPLETE AND WORKING:**
- Eval package structure in `app/adk/agents/strategy_agent/evaluations/`
- Connection to W&B Weave established
- All 9 scorers available and functional
- Datasets ready (llm_judge_alignment_set:v26, v28)
- Scripts ready to run new evaluations

**Ready to execute the iteration loop.**

