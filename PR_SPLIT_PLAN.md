# PR #173 Split Plan - Three Smaller PRs

## Context
PR #173 is too large (11,613 additions) to review effectively. We're splitting it into 3 smaller PRs based on natural boundaries (strategy types).

## Current Branch Structure
The commits in `feature/extend-graph-api` are already organized by strategy:
- `32627c9` - Competitive Strategy implementation
- `1a39bd9` + `63743bd` - Marketing Strategy implementation
- `baf0e07` + `b37584c` + `ace1b5c` + `090f06a` - Brand Strategy + docs

---

## Execution Plan

### Step 1: Create feature/competitive-strategy branch (PR #1)
**Branch from**: `main`
**Commits to cherry-pick**: `32627c9`
**Size**: ~3,000 lines
**Node types**: 6 (CompetitiveEnvironment, Competitor, CompetitorTactic, CompetitorStrength, CompetitorWeakness, SubstituteProduct)

**Files changed**:
- `api/src/kene_api/constants.py` (add competitive constants)
- `api/src/kene_api/models/graph_models.py` (add competitive models)
- `api/src/kene_api/routers/knowledge_graph.py` (add competitive endpoints)
- `api/src/kene_api/services/graph_sync_service.py` (add competitive service methods)
- `api/src/kene_api/services/graph_validation_service.py` (update validation)
- `api/tests/integration/test_knowledge_graph_endpoints.py` (add competitive tests)
- `api/tests/unit/test_graph_sync_service.py` (add competitive unit tests)
- `knowledge_graph/COMPETITIVE_STRATEGY_IMPLEMENTATION_SUMMARY.md` (NEW)
- `knowledge_graph/competitor_requirements.md` (updates)

**Benefits**:
- Self-contained: No dependencies on Marketing/Brand
- Builds directly on Business Strategy (PR #168)
- Can be tested independently

---

### Step 2: Create feature/marketing-strategy branch (PR #2)
**Branch from**: `feature/competitive-strategy` (after PR #1 merged) OR `main` + rebase after
**Commits to cherry-pick**: `1a39bd9`, `63743bd`
**Size**: ~3,500 lines
**Node types**: 6 (CustomerProfile, ProblemAwarenessStrategy, BrandAwarenessStrategy, ConsiderationStrategy, ConversionStrategy, LoyaltyStrategy)

**Files changed**:
- `api/src/kene_api/constants.py` (add marketing constants)
- `api/src/kene_api/models/graph_models.py` (add marketing models)
- `api/src/kene_api/routers/knowledge_graph.py` (add marketing endpoints)
- `api/src/kene_api/services/graph_sync_service.py` (add marketing service methods)
- `api/tests/integration/test_knowledge_graph_endpoints.py` (add marketing tests)
- `api/tests/unit/test_graph_sync_service.py` (add marketing unit tests)
- `knowledge_graph/MARKETING_STRATEGY_IMPLEMENTATION_PLAN.md` (NEW)
- `knowledge_graph/marketing_requirements.md` (updates)

**Key complexity**: Dual-parent architecture (ProductCategory + CustomerProfile)

---

### Step 3: Create feature/brand-strategy branch (PR #3)
**Branch from**: `feature/marketing-strategy` (after PR #2 merged) OR `main` + rebase after
**Commits to cherry-pick**: `baf0e07`, `b37584c`, `ace1b5c`, `090f06a`
**Size**: ~3,500 lines
**Node types**: 7 (BrandIdentity, BrandPersonality, VoiceAndTone, ColorPalette, Typography, ImageStyle, MissionAndValues)

**Files changed**:
- `api/src/kene_api/constants.py` (add brand constants)
- `api/src/kene_api/models/graph_models.py` (add brand models)
- `api/src/kene_api/routers/knowledge_graph.py` (add brand endpoints)
- `api/src/kene_api/services/graph_sync_service.py` (add brand service methods)
- `api/tests/integration/test_knowledge_graph_endpoints.py` (add brand tests)
- `api/tests/unit/test_graph_sync_service.py` (add brand unit tests)
- `knowledge_graph/PHASE1_IMPLEMENTATION_PLAN.md` (comprehensive update)
- `knowledge_graph/brand_requirements.md` (updates)

**Key complexity**: Hub node pattern (BrandIdentity as central hub)

---

## Git Commands Sequence

### A. Create PR #1 (Competitive Strategy)
```bash
# From main branch
git checkout main
git pull origin main

# Create new branch
git checkout -b feature/competitive-strategy

# Cherry-pick competitive strategy commit
git cherry-pick 32627c9

# Push and create PR
git push -u origin feature/competitive-strategy
gh pr create --title "feat(api): implement Competitive Strategy CRUD endpoints (Steps 2-3)" \
  --body "Part 1 of 3 split from PR #173. Adds 6 competitive strategy node types with full CRUD operations."
```

### B. Create PR #2 (Marketing Strategy)
**Option 1** (if PR #1 not yet merged):
```bash
git checkout feature/competitive-strategy
git checkout -b feature/marketing-strategy
git cherry-pick 1a39bd9 63743bd
git push -u origin feature/marketing-strategy
```

**Option 2** (after PR #1 merged):
```bash
git checkout main
git pull origin main
git checkout -b feature/marketing-strategy
git cherry-pick 1a39bd9 63743bd
git push -u origin feature/marketing-strategy
```

### C. Create PR #3 (Brand Strategy)
**Option 1** (if PR #2 not yet merged):
```bash
git checkout feature/marketing-strategy
git checkout -b feature/brand-strategy
git cherry-pick baf0e07 b37584c ace1b5c 090f06a
git push -u origin feature/brand-strategy
```

**Option 2** (after PR #2 merged):
```bash
git checkout main
git pull origin main
git checkout -b feature/brand-strategy
git cherry-pick baf0e07 b37584c ace1b5c 090f06a
git push -u origin feature/brand-strategy
```

---

## Testing Strategy

Each PR should pass:
```bash
# Linting
cd api && uv run ruff check src/
cd api && uv run ruff format src/ --check

# Type checking
cd api && uv run mypy src/

# Unit tests
cd api && pytest tests/unit/ -v

# Integration tests
cd api && pytest tests/integration/test_knowledge_graph_endpoints.py -v

# Full test suite
cd api && pytest tests/ -v
```

---

## PR Descriptions

### PR #1: Competitive Strategy
```markdown
# Competitive Strategy CRUD Endpoints (Steps 2-3)

**Part 1 of 3** - Split from PR #173 for easier review

## Summary
Extends the unified knowledge graph API to support competitive analysis with 6 new node types.

## Node Types Added
- CompetitiveEnvironment (hub node)
- Competitor
- CompetitorTactic
- CompetitorStrength
- CompetitorWeakness
- SubstituteProduct

## Changes
- ✅ Constants: Added 6 node types to whitelist + ID prefixes
- ✅ Models: 31 new Pydantic models (Create/Update/Response/List)
- ✅ Service: CRUD methods in GraphSyncService
- ✅ Router: REST endpoints at `/api/v1/knowledge-graph/{account_id}/competitors/*`
- ✅ Tests: Integration + unit tests for all node types
- ✅ Docs: Implementation summary + requirements update

## Dependencies
- Builds on PR #168 (Business Strategy)
- No dependencies on Marketing or Brand strategies

## Size
~3,000 lines (vs 11,613 in original PR #173)

## Testing
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Lint checks pass
- [ ] Type checking passes
```

### PR #2: Marketing Strategy
```markdown
# Marketing Strategy CRUD Endpoints (Steps 4-5)

**Part 2 of 3** - Split from PR #173 for easier review

## Summary
Adds customer intelligence and customer journey strategy nodes with unique dual-parent architecture.

## Node Types Added
- CustomerProfile
- ProblemAwarenessStrategy
- BrandAwarenessStrategy
- ConsiderationStrategy
- ConversionStrategy
- LoyaltyStrategy

## Key Architecture Feature
**Dual-Parent Architecture**: Strategy nodes are scoped to (ProductCategory, CustomerProfile) pairs:
- Each strategy node has TWO parents
- node_id format: `{strategy}_{product_category_id}_{customer_profile_id}`
- Supports multiple strategies per profile (one per ProductCategory)

## Dependencies
- Depends on PR #168 (Business Strategy) - uses ProductCategory
- Can be merged independently of PR #1 (Competitive) and PR #3 (Brand)

## Size
~3,500 lines

## Testing
- [ ] Dual-parent relationship creation works
- [ ] Cascade deletion tested (deleting CustomerProfile or ProductCategory)
- [ ] All CRUD operations tested
```

### PR #3: Brand Strategy
```markdown
# Brand Strategy CRUD Endpoints (Steps 6-7)

**Part 3 of 3** - Split from PR #173 for easier review

## Summary
Completes the knowledge graph API with brand identity and visual design node types.

## Node Types Added
- BrandIdentity (hub node)
- BrandPersonality
- VoiceAndTone
- ColorPalette
- Typography
- ImageStyle
- MissionAndValues

## Key Architecture Feature
**Hub Node Pattern**: BrandIdentity acts as central hub (one per account) with all brand elements connected to it.

## Dependencies
- Depends on PR #168 (Business Strategy)
- Can be merged independently of PR #1 and PR #2

## Size
~3,500 lines

## Documentation Updates
- ✅ PHASE1_IMPLEMENTATION_PLAN.md - comprehensive completion status
- ✅ brand_requirements.md - implementation notes
```

---

## Rollback Plan

If issues are found in any PR after merge:
1. **PR #1 issues**: Revert PR #1 only
2. **PR #2 issues**: Revert PR #2 only (PR #1 unaffected)
3. **PR #3 issues**: Revert PR #3 only (PR #1 & #2 unaffected)

This is much safer than reverting a monolithic 11,613-line PR.

---

## Timeline

**Recommended approach**:
1. Create all 3 PRs immediately (stacked on each other)
2. Review & merge PR #1 first
3. Rebase PR #2 on updated main, review & merge
4. Rebase PR #3 on updated main, review & merge
5. Close PR #173 as superseded

**Estimated timeline**: 3-5 days (vs weeks for reviewing #173)

---

## Next Steps

1. ✅ Review this plan
2. Execute git commands to create 3 branches
3. Push branches and create PRs
4. Update PR #173 description to reference the split PRs
5. Begin review process with PR #1
