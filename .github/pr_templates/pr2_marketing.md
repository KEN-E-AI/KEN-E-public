# Marketing Strategy CRUD Endpoints (Steps 4-5)

**Part 2 of 3** - Split from PR #173 for easier review

## Summary
Adds customer intelligence and customer journey strategy nodes with a unique **dual-parent architecture**. This PR extends the knowledge graph to support persona-based marketing strategies across the customer lifecycle.

## Node Types Added
- **CustomerProfile** - Ideal Customer Profile (ICP) personas
- **ProblemAwarenessStrategy** - How personas discover the problem
- **BrandAwarenessStrategy** - How personas discover our brand
- **ConsiderationStrategy** - Why personas consider our solution
- **ConversionStrategy** - Why personas purchase
- **LoyaltyStrategy** - Why customers become advocates

## Key Architectural Innovation: Dual-Parent Structure

Unlike other node types, **marketing strategy nodes are scoped to BOTH a ProductCategory AND a CustomerProfile**:

```
ProductCategory: "Cloud Services" (productcat_xyz)
CustomerProfile: "Marketing Mary" (icp_abc123)

Creates:
ProblemAwarenessStrategy: problemaware_productcat_xyz_icp_abc123
BrandAwarenessStrategy: brandaware_productcat_xyz_icp_abc123
ConsiderationStrategy: consideration_productcat_xyz_icp_abc123
ConversionStrategy: conversion_productcat_xyz_icp_abc123
LoyaltyStrategy: loyalty_productcat_xyz_icp_abc123
```

### Why Dual Parents?
- Same persona needs **different strategies** for different products
- Marketing Mary's journey for "Cloud Services" ≠ journey for "AI Tools"
- node_id format: `{strategy_type}_{product_category_id}_{customer_profile_id}`

### Implications
- ✅ Strategy nodes have **TWO relationships** (one to ProductCategory, one to CustomerProfile)
- ✅ Deleting CustomerProfile **cascades** to all strategy nodes
- ✅ Deleting ProductCategory **cascades** to all strategy nodes
- ✅ Same profile can appear in strategies for multiple categories

## Changes

### Constants (`api/src/kene_api/constants.py`)
- ✅ Added 6 node types to `VALID_NODE_TYPES` whitelist
- ✅ Added ID prefixes: `icp`, `problemaware`, `brandaware`, `consideration`, `conversion`, `loyalty`

### Models (`api/src/kene_api/models/graph_models.py`)
- ✅ 30 new Pydantic models with comprehensive validation
- ✅ Create models require **both** `customer_profile_node_id` AND `product_category_node_id`
- ✅ `MarketingStrategyResponse` for aggregated graph view
- ✅ CustomerProfile has `display_name` (e.g., "Marketing Mary") and `narrative` (full persona)

### Service Layer (`api/src/kene_api/services/graph_sync_service.py`)
- ✅ CRUD methods for all 6 node types
- ✅ Dual-parent relationship creation (TWO Neo4j relationships per strategy node)
- ✅ Validation: both parents must exist before creating strategy node
- ✅ Cascade deletion logic
- ✅ Bidirectional Neo4j ↔ Firestore sync

### Router (`api/src/kene_api/routers/knowledge_graph.py`)
- ✅ REST endpoints at `/api/v1/knowledge-graph/{account_id}/customer-*`
- ✅ Access control via `check_graph_access()`
- ✅ Comprehensive error handling
- ✅ Aggregated endpoint: `GET /marketing-strategy`

### Tests
- ✅ Unit tests (`test_graph_sync_service.py`): Dual-parent validation
- ✅ Service method tests for all node types
- ✅ Cascade deletion tests

### Documentation
- ✅ `MARKETING_STRATEGY_IMPLEMENTATION_PLAN.md` - comprehensive implementation notes
- ✅ `marketing_requirements.md` - updated with dual-parent architecture explanation

## API Endpoints

### Customer Profiles
- `POST /api/v1/knowledge-graph/{account_id}/customer-profiles`
- `GET /api/v1/knowledge-graph/{account_id}/customer-profiles` (list)
- `GET /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}` (cascades!)

### Problem Awareness Strategy
- `POST /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies`
  - Requires: `customer_profile_node_id`, `product_category_node_id`
- `GET /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies`
- `GET /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies/{node_id}`

### Brand Awareness Strategy
- `POST /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies`
  - Requires: `customer_profile_node_id`, `product_category_node_id`
- `GET /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies`
- `GET /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies/{node_id}`

### Consideration Strategy
- `POST /api/v1/knowledge-graph/{account_id}/consideration-strategies`
  - Requires: `customer_profile_node_id`, `product_category_node_id`
- `GET /api/v1/knowledge-graph/{account_id}/consideration-strategies`
- `GET /api/v1/knowledge-graph/{account_id}/consideration-strategies/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/consideration-strategies/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/consideration-strategies/{node_id}`

### Conversion Strategy
- `POST /api/v1/knowledge-graph/{account_id}/conversion-strategies`
  - Requires: `customer_profile_node_id`, `product_category_node_id`
- `GET /api/v1/knowledge-graph/{account_id}/conversion-strategies`
- `GET /api/v1/knowledge-graph/{account_id}/conversion-strategies/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/conversion-strategies/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/conversion-strategies/{node_id}`

### Loyalty Strategy
- `POST /api/v1/knowledge-graph/{account_id}/loyalty-strategies`
  - Requires: `customer_profile_node_id`, `product_category_node_id`
- `GET /api/v1/knowledge-graph/{account_id}/loyalty-strategies`
- `GET /api/v1/knowledge-graph/{account_id}/loyalty-strategies/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/loyalty-strategies/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/loyalty-strategies/{node_id}`

### Aggregated View
- `GET /api/v1/knowledge-graph/{account_id}/marketing-strategy` - returns all marketing nodes

## Graph Relationships

```
Account
  └─[:BELONGS_TO]─> CustomerProfile
      ├─[:DISCOVERS_THE_PROBLEM_BY]─> ProblemAwarenessStrategy
      │   └─[:HAS_PROBLEM_AWARENESS_STRATEGY]─ ProductCategory
      ├─[:DISCOVERS_OUR_BRAND_BY]─> BrandAwarenessStrategy
      │   └─[:HAS_BRAND_AWARENESS_STRATEGY]─ ProductCategory
      ├─[:CONSIDERS_OUR_BRAND_BECAUSE]─> ConsiderationStrategy
      │   └─[:HAS_CONSIDERATION_STRATEGY]─ ProductCategory
      ├─[:PURCHASES_OUR_BRAND_BECAUSE]─> ConversionStrategy
      │   └─[:HAS_CONVERSION_STRATEGY]─ ProductCategory
      └─[:BECOMES_AN_ADVOCATE_BECAUSE]─> LoyaltyStrategy
          └─[:HAS_LOYALTY_STRATEGY]─ ProductCategory

ProductCategory -[:IS_MARKETED_TO]-> CustomerProfile
```

## Example Usage Flow

```python
# 1. Create customer profile
POST /customer-profiles
{
  "display_name": "Marketing Mary",
  "narrative": "35-year-old marketing director at mid-sized SaaS...",
  "references": ["https://research.com/persona-study"]
}
# Returns: node_id = "icp_acc123_abc456"

# 2. Create problem awareness strategy (for specific product + profile)
POST /problem-awareness-strategies
{
  "description": "Marketing Mary discovers attribution problems through...",
  "customer_profile_node_id": "icp_acc123_abc456",
  "product_category_node_id": "productcat_acc123_xyz789",
  "references": []
}
# Returns: node_id = "problemaware_productcat_acc123_xyz789_icp_acc123_abc456"

# 3. Same profile, different product category
POST /problem-awareness-strategies
{
  "description": "Marketing Mary discovers email problems through...",
  "customer_profile_node_id": "icp_acc123_abc456",
  "product_category_node_id": "productcat_acc123_def999",  # Different category!
  "references": []
}
# Returns: node_id = "problemaware_productcat_acc123_def999_icp_acc123_abc456"
```

## Architecture Decisions

### Why Not Auto-Create Strategies?
We **cannot** auto-create strategy nodes when CustomerProfile is created because:
- Strategy nodes need ProductCategory context (dual parent requirement)
- Different products = different strategies for same persona
- Must be explicitly created with both parent IDs

### Cascade Deletion Behavior
**Deleting CustomerProfile**:
- Deletes ALL strategy nodes linked to that profile (across all ProductCategories)
- Example: Deleting "Marketing Mary" removes all 5 strategies for all products

**Deleting ProductCategory**:
- Deletes ALL strategy nodes linked to that category
- Example: Deleting "Cloud Services" removes all strategies for all personas

### Validation Rules
- Both `customer_profile_node_id` and `product_category_node_id` must exist
- Both must belong to the same `account_id`
- Strategy node_id uniquely identifies the (ProductCategory, CustomerProfile) pair

## Dependencies
- **Requires**: PR #168 (Business Strategy) - uses ProductCategory ✅ merged
- **Independent of**: PR #1 (Competitive Strategy), PR #3 (Brand Strategy)
- **Base branch**: `feature/competitive-strategy` (will rebase to `main` after PR #174 merges)

## Size Metrics
- **Lines changed**: +3,596, -14 (net +3,582)
- **Files changed**: 8
- **New models**: 30
- **New endpoints**: 30
- **Test cases added**: 20+

This is **~31% of original PR #173** (11,613 lines).

## Testing Checklist

### Unit Tests
- [x] CustomerProfile CRUD
- [x] ProblemAwarenessStrategy CRUD with dual-parent validation
- [x] BrandAwarenessStrategy CRUD with dual-parent validation
- [x] ConsiderationStrategy CRUD with dual-parent validation
- [x] ConversionStrategy CRUD with dual-parent validation
- [x] LoyaltyStrategy CRUD with dual-parent validation
- [x] Validation: both parents must exist
- [x] Validation: both parents in same account
- [x] Cascade deletion behavior

### Integration Tests
- [ ] Create profile + strategies for multiple products
- [ ] Delete profile → verify all strategies deleted
- [ ] Delete category → verify all strategies deleted
- [ ] Aggregated marketing-strategy endpoint
- [ ] Access control enforcement

### Manual Testing
- [ ] Create 2-3 customer profiles
- [ ] Create 5 strategies for (Profile A, Category 1)
- [ ] Create 5 strategies for (Profile A, Category 2)
- [ ] Verify different node_ids
- [ ] Delete Profile A → verify 10 strategies deleted
- [ ] Query aggregated endpoint

## Pre-Merge Checklist
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Linting passes
- [ ] Formatting passes
- [ ] Type checking passes
- [ ] No merge conflicts with base branch
- [ ] Documentation reviewed

## Follow-up Work
After this PR:
- PR #3: Brand Strategy (Steps 6-7)
- Integration tests for cascade deletion
- Performance testing for aggregated endpoints

## Related
- Supersedes: Part of PR #173 (will be closed after all 3 PRs merged)
- Depends on: PR #168 (Business Strategy) ✅ merged
- Stacked on: PR #174 (Competitive Strategy) - in review
- Blocks: PR #3 (Brand Strategy)
