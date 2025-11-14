# Competitive Strategy CRUD Endpoints (Steps 2-3)

**Part 1 of 3** - Split from PR #173 for easier review

## Summary
Extends the unified knowledge graph API to support competitive analysis with 6 new node types. This PR builds directly on the Business Strategy foundation from PR #168.

## Node Types Added
- **CompetitiveEnvironment** (hub node) - one per account
- **Competitor** - direct competitors in the market
- **CompetitorTactic** - specific tactics used by competitors
- **CompetitorStrength** - competitive advantages (can create Opportunities for us)
- **CompetitorWeakness** - competitive vulnerabilities (can create Risks for us)
- **SubstituteProduct** - specific products that compete with ours

## Changes

### Constants (`api/src/kene_api/constants.py`)
- ✅ Added 6 node types to `VALID_NODE_TYPES` whitelist (prevents Cypher injection)
- ✅ Added ID prefixes: `competitiveenv`, `competitor`, `tactic`, `compstrength`, `compweakness`, `substitute`

### Models (`api/src/kene_api/models/graph_models.py`)
- ✅ 31 new Pydantic models with comprehensive validation
- ✅ Create/Update/Response/ListResponse models for each node type
- ✅ `CompetitiveStrategyResponse` for aggregated graph view
- ✅ Field validation: max_length, URL validation, required fields

### Service Layer (`api/src/kene_api/services/graph_sync_service.py`)
- ✅ CRUD methods for all 6 node types
- ✅ Hub node pattern for CompetitiveEnvironment (only one per account)
- ✅ Parent-child relationship management
- ✅ Bidirectional Neo4j ↔ Firestore sync
- ✅ Validation: unique display names, valid URLs, parent existence

### Router (`api/src/kene_api/routers/knowledge_graph.py`)
- ✅ REST endpoints at `/api/v1/knowledge-graph/{account_id}/competitive-*`
- ✅ Access control via `check_graph_access()`
- ✅ Comprehensive error handling
- ✅ Aggregated endpoint: `GET /competitive-strategy`

### Tests
- ✅ Integration tests (`test_knowledge_graph_endpoints.py`): Full CRUD flows
- ✅ Unit tests (`test_graph_sync_service.py`): Service method validation
- ✅ Validation tests (`test_node_type_validation.py`): Updated for new node types

### Documentation
- ✅ `COMPETITIVE_STRATEGY_IMPLEMENTATION_SUMMARY.md` - comprehensive implementation notes
- ✅ `competitor_requirements.md` - updated with implementation guidance

## API Endpoints

### Competitive Environment (Hub)
- `POST /api/v1/knowledge-graph/{account_id}/competitive-environment`
- `GET /api/v1/knowledge-graph/{account_id}/competitive-environment`
- `PATCH /api/v1/knowledge-graph/{account_id}/competitive-environment/{node_id}`

### Competitors
- `POST /api/v1/knowledge-graph/{account_id}/competitors`
- `GET /api/v1/knowledge-graph/{account_id}/competitors` (list)
- `GET /api/v1/knowledge-graph/{account_id}/competitors/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/competitors/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/competitors/{node_id}`

### Competitor Tactics
- `POST /api/v1/knowledge-graph/{account_id}/competitor-tactics`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-tactics`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}`

### Competitor Strengths
- `POST /api/v1/knowledge-graph/{account_id}/competitor-strengths`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-strengths`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-strengths/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/competitor-strengths/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/competitor-strengths/{node_id}`

### Competitor Weaknesses
- `POST /api/v1/knowledge-graph/{account_id}/competitor-weaknesses`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-weaknesses`
- `GET /api/v1/knowledge-graph/{account_id}/competitor-weaknesses/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/competitor-weaknesses/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/competitor-weaknesses/{node_id}`

### Substitute Products
- `POST /api/v1/knowledge-graph/{account_id}/substitute-products`
- `GET /api/v1/knowledge-graph/{account_id}/substitute-products`
- `GET /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}`
- `PATCH /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}`
- `DELETE /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}`

### Aggregated View
- `GET /api/v1/knowledge-graph/{account_id}/competitive-strategy` - returns all competitive nodes

## Graph Relationships

```
Account
  └─[:HAS_COMPETITIVE_ENVIRONMENT]─> CompetitiveEnvironment
  └─[:OPERATES_WITHIN]─> Competitor
      ├─[:IS_KEY_PLAYER]─> CompetitiveEnvironment
      ├─[:EMPLOYS_TACTIC]─> CompetitorTactic
      ├─[:HAS_STRENGTH]─> CompetitorStrength
      │   └─[:CREATES]─> Opportunity (shared with Business Strategy)
      ├─[:HAS_WEAKNESS]─> CompetitorWeakness
      │   └─[:CREATES]─> Risk (shared with Business Strategy)
      └─[:OFFERS_PRODUCT]─> SubstituteProduct
```

## Architecture Decisions

### Hub Node Pattern
`CompetitiveEnvironment` uses hub node pattern:
- Only **one** per account
- If exists, POST request updates it
- Provides context for all competitive analysis

### Shared SWOT Pattern
- `CompetitorStrength -[:CREATES]-> Opportunity` (our opportunity from their strength)
- `CompetitorWeakness -[:CREATES]-> Risk` (our risk from their weakness)
- Opportunity/Risk nodes are **shared** with Business Strategy

### Parent-Child Relationships
All child nodes (tactics, strengths, weaknesses, products) require valid `competitor_node_id` on creation.

## Dependencies
- **Requires**: PR #168 (Business Strategy) - merged to main
- **Independent of**: Marketing Strategy (PR #2), Brand Strategy (PR #3)

## Size Metrics
- **Lines changed**: +4,368, -376 (net +3,992)
- **Files changed**: 9
- **New models**: 31
- **New endpoints**: 31
- **Test cases added**: 25+

This is **~34% of original PR #173** (11,613 lines), making it much more reviewable.

## Testing Checklist

### Unit Tests
- [x] CompetitiveEnvironment CRUD
- [x] Competitor CRUD
- [x] CompetitorTactic CRUD with parent validation
- [x] CompetitorStrength CRUD with parent validation
- [x] CompetitorWeakness CRUD with parent validation
- [x] SubstituteProduct CRUD with parent validation
- [x] Hub node pattern (upsert behavior)
- [x] Validation: unique display names
- [x] Validation: URL format in references

### Integration Tests
- [x] Full CRUD flow for all node types
- [x] Aggregated competitive strategy endpoint
- [x] Access control enforcement
- [x] Error handling (404, 400, 403)
- [x] Neo4j ↔ Firestore sync

### Manual Testing
- [ ] Create competitive environment via API
- [ ] Add multiple competitors
- [ ] Add tactics/strengths/weaknesses to competitors
- [ ] Create Opportunity from CompetitorStrength
- [ ] Create Risk from CompetitorWeakness
- [ ] Query aggregated competitive-strategy endpoint
- [ ] Verify Firestore sync

## Pre-Merge Checklist
- [ ] All unit tests pass (`pytest tests/unit/`)
- [ ] All integration tests pass (`pytest tests/integration/`)
- [ ] Linting passes (`ruff check src/`)
- [ ] Formatting passes (`ruff format src/ --check`)
- [ ] Type checking passes (`mypy src/`)
- [ ] No merge conflicts with main
- [ ] Documentation reviewed
- [ ] API endpoints manually tested

## Follow-up Work
After this PR:
- PR #2: Marketing Strategy (Steps 4-5)
- PR #3: Brand Strategy (Steps 6-7)

## Related
- Supersedes: Part of PR #173 (will be closed after all 3 PRs merged)
- Depends on: PR #168 (Business Strategy) ✅ merged
- Blocks: PR #2 (Marketing Strategy) - can be reviewed in parallel
