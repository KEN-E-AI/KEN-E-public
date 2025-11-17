# Marketing Strategy API Implementation Plan

**Phase**: Steps 4 & 5 - Marketing Strategy Graph API
**Status**: Planning Phase
**Created**: 2025-01-13

---

## Executive Summary

This document provides the implementation plan for adding Marketing Strategy CRUD endpoints to the unified knowledge graph API. This extends the work from Steps 1-3 (Business & Competitive Strategy) to support customer intelligence and marketing strategy nodes.

**Key Insight from Code Review**: Marketing strategy has a **unique dual-parent architecture** where strategy nodes (ProblemAwareness, BrandAwareness, etc.) are scoped to **BOTH** ProductCategory AND CustomerProfile through separate relationships.

---

## Architecture Understanding (from marketing_graph_builder.py)

### Current Agent System Behavior

The marketing_graph_builder.py reveals the following pattern:

**Phase 1**: Create master CustomerProfile nodes (2-5 total)
- Only stores: display_name (lowercase), narrative, references
- NO strategy nodes created at this stage

**Phase 2**: For each ProductCategory that needs marketing:
- Create 5 strategy nodes **scoped to BOTH category + profile**
- Each strategy node has **dual parentage**:
  - Links to CustomerProfile via: DISCOVERS_THE_PROBLEM_BY, DISCOVERS_OUR_BRAND_BY, etc.
  - Links to ProductCategory via: HAS_PROBLEM_AWARENESS_STRATEGY, HAS_BRAND_AWARENESS_STRATEGY, etc.
- Create IS_MARKETED_TO relationship: `ProductCategory -[:IS_MARKETED_TO]-> CustomerProfile`

### Critical Architectural Insight

**Strategy nodes are NOT children of CustomerProfile alone**. They are:

1. **Scoped to a specific (ProductCategory, CustomerProfile) pair**
2. **node_id format**: `{strategy_type}_{product_category_id}_{customer_profile_id}`
3. **Dual relationships**: Connected to BOTH ProductCategory AND CustomerProfile
4. **Multiple instances**: Same CustomerProfile can have different strategies for different ProductCategories

**Example**:
- CustomerProfile: "Marketing Mary" (node_id: icp_abc123)
- ProductCategory A: "Cloud Services" (node_id: productcat_xyz)
- ProductCategory B: "AI Tools" (node_id: productcat_def)

This creates:
- ProblemAwarenessStrategy for (Cloud Services, Marketing Mary): `problemaware_productcat_xyz_icp_abc123`
- ProblemAwarenessStrategy for (AI Tools, Marketing Mary): `problemaware_productcat_def_icp_abc123`

**Implications for API Design**:
- We CANNOT auto-create strategy nodes when CustomerProfile is created (need ProductCategory context)
- We NEED a separate endpoint to create strategy nodes for a (ProductCategory, CustomerProfile) pair
- Deleting CustomerProfile should cascade delete ALL strategy nodes linked to it (across all ProductCategories)
- Deleting ProductCategory should cascade delete ALL strategy nodes linked to it

---

## Revised Implementation Plan

### Step 4: Update Marketing Documentation

**File**: `knowledge_graph/marketing_requirements.md`

**Required Updates**:

1. ✅ Add "Important Implementation Notes" section explaining:
   - Dual-parent architecture for strategy nodes
   - Strategy nodes are scoped to (ProductCategory, CustomerProfile) pairs
   - node_id format includes both parent IDs
   - Multiple strategy instances per profile (one per ProductCategory)
   - Cascade deletion behavior

2. ✅ Add `account_id` field to all node tables

3. ✅ Add `references` field to CustomerProfile and all strategy nodes

4. ✅ Document ALL relationships:

   **From CustomerProfile**:
   - `CustomerProfile -[:BELONGS_TO]-> Account`
   - `CustomerProfile <-[:IS_MARKETED_TO]- ProductCategory`
   - `CustomerProfile -[:DISCOVERS_THE_PROBLEM_BY]-> ProblemAwarenessStrategy`
   - `CustomerProfile -[:DISCOVERS_OUR_BRAND_BY]-> BrandAwarenessStrategy`
   - `CustomerProfile -[:CONSIDERS_OUR_BRAND_BECAUSE]-> ConsiderationStrategy`
   - `CustomerProfile -[:PURCHASES_OUR_BRAND_BECAUSE]-> ConversionStrategy`
   - `CustomerProfile -[:BECOMES_AN_ADVOCATE_BECAUSE]-> LoyaltyStrategy`

   **From ProductCategory** (NEW - not in current docs):
   - `ProductCategory -[:HAS_PROBLEM_AWARENESS_STRATEGY]-> ProblemAwarenessStrategy`
   - `ProductCategory -[:HAS_BRAND_AWARENESS_STRATEGY]-> BrandAwarenessStrategy`
   - `ProductCategory -[:HAS_CONSIDERATION_STRATEGY]-> ConsiderationStrategy`
   - `ProductCategory -[:HAS_CONVERSION_STRATEGY]-> ConversionStrategy`
   - `ProductCategory -[:HAS_LOYALTY_STRATEGY]-> LoyaltyStrategy`

5. ✅ Add new fields to strategy node tables:
   - `customer_profile_node_id` (inferred from relationship, not stored as property)
   - `product_category_node_id` (inferred from relationship, not stored as property)

6. ✅ Fix CustomerProfile field naming:
   - Current docs show just "description"
   - Implementation uses: `display_name` (lowercase persona name) + `description` (narrative)
   - Should be: `display_name` + `narrative` to match Pydantic model

---

### Step 5: Add Marketing Strategy Endpoints

**Complexity Analysis**: **HIGHER** than Competitive Strategy due to:
- Dual-parent architecture (strategies linked to 2 nodes)
- Need for relationship management endpoints
- Complex creation flow (requires ProductCategory context)
- Complex deletion (cascade across multiple ProductCategories)

#### 5.1: Node Types & Prefixes

**Add to constants.py**:
```python
# Marketing Strategy nodes
"CustomerProfile",
"ProblemAwarenessStrategy",
"BrandAwarenessStrategy",
"ConsiderationStrategy",
"ConversionStrategy",
"LoyaltyStrategy",
```

**ID Prefixes**:
```python
"CustomerProfile": "icp",
"ProblemAwarenessStrategy": "problemaware",
"BrandAwarenessStrategy": "brandaware",
"ConsiderationStrategy": "consideration",
"ConversionStrategy": "conversion",
"LoyaltyStrategy": "loyalty",
```

#### 5.2: Pydantic Models (~28 models)

**CustomerProfile** (4 models):
```python
class CustomerProfileCreate(BaseModel):
    display_name: str  # e.g., "Marketing Mary"
    narrative: str  # Full persona description
    references: list[str] = []

class CustomerProfileUpdate(BaseModel):
    display_name: str | None
    narrative: str | None
    references: list[str] | None

class CustomerProfileResponse(NodeBase):
    display_name: str
    narrative: str  # NOT "description"
    references: list[str]

class CustomerProfileListResponse(BaseModel):
    profiles: list[CustomerProfileResponse]
    total_count: int
```

**Strategy Nodes** (4 models each × 5 types = 20 models):
```python
class ProblemAwarenessStrategyCreate(BaseModel):
    description: str
    references: list[str] = []
    customer_profile_node_id: str
    product_category_node_id: str  # Required for dual-parent

class ProblemAwarenessStrategyUpdate(BaseModel):
    description: str | None
    references: list[str] | None

class ProblemAwarenessStrategyResponse(NodeBase):
    description: str
    references: list[str]
    customer_profile_node_id: str  # From relationship query
    product_category_node_id: str  # From relationship query

class ProblemAwarenessStrategyListResponse(BaseModel):
    strategies: list[ProblemAwarenessStrategyResponse]
    total_count: int
```

**Relationship Management** (2 models):
```python
class ProductCategoryCustomerProfileLinkCreate(BaseModel):
    product_category_node_id: str
    customer_profile_node_id: str

class ProductCategoryCustomerProfileLinkResponse(BaseModel):
    product_category_node_id: str
    customer_profile_node_id: str
    created_at: datetime
```

**Aggregated View** (1 model):
```python
class MarketingStrategyResponse(BaseModel):
    account_id: str
    customer_profiles: list[CustomerProfileResponse]
    problem_awareness_strategies: list[ProblemAwarenessStrategyResponse]
    brand_awareness_strategies: list[BrandAwarenessStrategyResponse]
    consideration_strategies: list[ConsiderationStrategyResponse]
    conversion_strategies: list[ConversionStrategyResponse]
    loyalty_strategies: list[LoyaltyStrategyResponse]
```

**Total**: 31 models

#### 5.3: Service Methods (~18 methods)

**CustomerProfile Methods** (3):
```python
async def create_customer_profile(...) -> CustomerProfileResponse:
    """Create standalone customer profile (NO strategies)."""

async def update_customer_profile(...) -> CustomerProfileResponse:
    """Update customer profile."""

async def delete_customer_profile(...) -> None:
    """Delete profile AND cascade delete all linked strategy nodes."""
    # 1. Find ALL strategy nodes linked to this profile (across all ProductCategories)
    # 2. Delete all strategy nodes (5 types)
    # 3. Delete all IS_MARKETED_TO relationships
    # 4. Delete CustomerProfile
```

**Strategy Node Methods** (10 = 2 per strategy type):
```python
async def create_problem_awareness_strategy(...) -> ProblemAwarenessStrategyResponse:
    """Create strategy node with dual-parent relationships."""
    # 1. Validate both CustomerProfile and ProductCategory exist
    # 2. Check if strategy already exists for this (category, profile) pair
    # 3. Create strategy node
    # 4. Create relationship to CustomerProfile
    # 5. Create relationship to ProductCategory
    # 6. Create IS_MARKETED_TO if doesn't exist

async def update_problem_awareness_strategy(...) -> ProblemAwarenessStrategyResponse:
    """Update strategy description/references."""

# Similar for: brand_awareness, consideration, conversion, loyalty
```

**Relationship Management** (2):
```python
async def create_is_marketed_to_link(...) -> dict:
    """Create IS_MARKETED_TO relationship between ProductCategory and CustomerProfile."""
    # Used when linking existing profile to existing category

async def delete_is_marketed_to_link(...) -> None:
    """Remove IS_MARKETED_TO relationship."""
    # Should also cascade delete the 5 strategy nodes for this (category, profile) pair
```

**Helper Method** (1):
```python
async def _get_strategy_nodes_for_profile(profile_node_id: str) -> list[dict]:
    """Find ALL strategy nodes linked to a customer profile (across all categories)."""
```

**Query Enhancement** (2):
```python
async def list_strategies_for_category(
    account_id: str,
    product_category_node_id: str,
    strategy_type: str
) -> list[dict]:
    """List all strategies of a type for a specific ProductCategory."""

async def list_strategies_for_profile(
    account_id: str,
    customer_profile_node_id: str,
    strategy_type: str
) -> list[dict]:
    """List all strategies of a type for a specific CustomerProfile."""
```

#### 5.4: Router Endpoints (~28 total)

**CustomerProfile** (5 endpoints):
```
POST   /{account_id}/customer-profiles          # Create profile only
GET    /{account_id}/customer-profiles           # List all profiles
GET    /{account_id}/customer-profiles/{node_id}
PATCH  /{account_id}/customer-profiles/{node_id}
DELETE /{account_id}/customer-profiles/{node_id} # Cascade delete
```

**Strategy Nodes** (5 endpoints each × 5 types = 25 total):
```
POST   /{account_id}/problem-awareness-strategies   # Requires both parent IDs
GET    /{account_id}/problem-awareness-strategies    # List all
GET    /{account_id}/problem-awareness-strategies/{node_id}
PATCH  /{account_id}/problem-awareness-strategies/{node_id}
DELETE /{account_id}/problem-awareness-strategies/{node_id}  # Allowed (deletes specific strategy instance)

# Similar for: brand-awareness, consideration, conversion, loyalty-strategies
```

**Relationship Management** (2 endpoints):
```
POST   /{account_id}/product-categories/{category_id}/market-to/{profile_id}
         # Create IS_MARKETED_TO link + 5 strategy nodes with empty descriptions

DELETE /{account_id}/product-categories/{category_id}/market-to/{profile_id}
         # Delete IS_MARKETED_TO link + cascade delete 5 strategy nodes
```

**Aggregated View** (1 endpoint):
```
GET    /{account_id}/marketing-strategy
```

#### 5.5: Validation Methods (~4)

```python
async def validate_unique_customer_profile_name(account_id, display_name) -> tuple[bool, str]:
    """Ensure no duplicate display_name in account."""

async def validate_can_delete_customer_profile(node_id) -> tuple[bool, str]:
    """Check if profile has linked strategies or IS_MARKETED_TO relationships."""
    # Should return count for informational purposes

async def validate_strategy_not_exists(
    product_category_id,
    customer_profile_id,
    strategy_type
) -> tuple[bool, str]:
    """Check if strategy already exists for (category, profile) pair."""

async def validate_can_delete_product_category_with_strategies(node_id) -> tuple[bool, str]:
    """Check if ProductCategory has marketing strategies."""
    # Extends existing validate_can_delete_product_category
```

#### 5.6: Relationship Mapping Updates

**Add to _get_relationship_config**:
```python
# Marketing Strategy - CustomerProfile relationships
("ProblemAwarenessStrategy", "CustomerProfile"): {"from_parent": "DISCOVERS_THE_PROBLEM_BY"},
("BrandAwarenessStrategy", "CustomerProfile"): {"from_parent": "DISCOVERS_OUR_BRAND_BY"},
("ConsiderationStrategy", "CustomerProfile"): {"from_parent": "CONSIDERS_OUR_BRAND_BECAUSE"},
("ConversionStrategy", "CustomerProfile"): {"from_parent": "PURCHASES_OUR_BRAND_BECAUSE"},
("LoyaltyStrategy", "CustomerProfile"): {"from_parent": "BECOMES_AN_ADVOCATE_BECAUSE"},

# Marketing Strategy - ProductCategory relationships
("ProblemAwarenessStrategy", "ProductCategory"): {"from_parent": "HAS_PROBLEM_AWARENESS_STRATEGY"},
("BrandAwarenessStrategy", "ProductCategory"): {"from_parent": "HAS_BRAND_AWARENESS_STRATEGY"},
("ConsiderationStrategy", "ProductCategory"): {"from_parent": "HAS_CONSIDERATION_STRATEGY"},
("ConversionStrategy", "ProductCategory"): {"from_parent": "HAS_CONVERSION_STRATEGY"},
("LoyaltyStrategy", "ProductCategory"): {"from_parent": "HAS_LOYALTY_STRATEGY"},
```

**Note**: Strategies need **CUSTOM** creation logic since they have 2 parents, not 1.

#### 5.7: Special Considerations

**1. Dual-Parent Strategy Creation**

Strategy nodes cannot use the generic `create_node()` method as-is because they need 2 parent relationships. Options:

**Option A**: Extend `create_node()` to support optional `secondary_parent_id` and `secondary_parent_type`
**Option B**: Create custom `_create_marketing_strategy_node()` helper that's called by all 5 strategy creation methods

**Recommendation**: **Option A** - Extend generic method for future flexibility

**2. Query Methods Need Enhancement**

Strategy nodes need to return BOTH parent node_ids. Current `get_node()` and `list_nodes()` methods return single parent. Need to:
- Query BOTH relationships
- Return both `customer_profile_node_id` AND `product_category_node_id` in response

**3. Deletion Cascade Logic**

When deleting CustomerProfile:
```cypher
// Find all strategies linked to profile (across all categories)
MATCH (cp:CustomerProfile {node_id: $profile_id})-[r]-(strategy:Strategy)
WHERE strategy:ProblemAwarenessStrategy OR strategy:BrandAwarenessStrategy
   OR strategy:ConsiderationStrategy OR strategy:ConversionStrategy
   OR strategy:LoyaltyStrategy
DETACH DELETE strategy

// Delete IS_MARKETED_TO relationships
MATCH (cp:CustomerProfile {node_id: $profile_id})<-[r:IS_MARKETED_TO]-()
DELETE r

// Finally delete profile
MATCH (cp:CustomerProfile {node_id: $profile_id})
DETACH DELETE cp
```

**4. IS_MARKETED_TO Relationship Management**

This relationship is created when:
- Agent system creates strategies for (category, profile) pair
- User creates first strategy for (category, profile) pair via API
- User explicitly calls "market-to" endpoint

Should be deleted when:
- User deletes last strategy for (category, profile) pair
- User explicitly calls "delete market-to" endpoint
- CustomerProfile is deleted (cascade)
- ProductCategory is deleted (cascade)

---

## Answers to Key Questions

Based on code review of marketing_graph_builder.py:

### Q1: CustomerProfile Creation - Strategy Descriptions?

**Answer**: CustomerProfile is created **WITHOUT** any strategy nodes. Strategy nodes are created later when linking to a ProductCategory.

**API Flow**:
1. Create CustomerProfile (standalone) → No strategies yet
2. Create strategy nodes for (ProductCategory, CustomerProfile) pair → Creates 5 strategies + IS_MARKETED_TO link

### Q2: ProductCategory Linking - How is IS_MARKETED_TO created?

**Answer**: IS_MARKETED_TO is created when creating strategy nodes for a (category, profile) pair.

**Proposed API**:
```
POST /{account_id}/product-categories/{category_id}/marketing-strategies
Body: {
  "customer_profile_node_id": "icp_abc123",
  "strategies": {
    "problem_awareness": "Strategy description...",
    "brand_awareness": "Strategy description...",
    "consideration": "Strategy description...",
    "conversion": "Strategy description...",
    "loyalty": "Strategy description..."
  }
}
```

This endpoint:
- Creates 5 strategy nodes
- Links each to both ProductCategory AND CustomerProfile
- Creates IS_MARKETED_TO relationship

**Alternative Simpler API** (Recommended):
Create strategies individually:
```
POST /{account_id}/problem-awareness-strategies
Body: {
  "description": "...",
  "customer_profile_node_id": "icp_abc123",
  "product_category_node_id": "productcat_xyz"
}
```
- Auto-creates IS_MARKETED_TO on first strategy creation for (category, profile) pair

### Q3: Strategy Parent References - Stored or Inferred?

**Current Implementation**: Relationships only, NO stored properties.

**Problem**: Response models need parent IDs, but they're not stored as properties.

**Solution**: Enhance query methods to return parent IDs:

```python
async def get_node(account_id, node_id, node_type):
    # For strategy nodes, also query relationships
    if node_type in MARKETING_STRATEGY_TYPES:
        query = f"""
        MATCH (strategy:{node_type} {{node_id: $node_id}})
        MATCH (cp:CustomerProfile)-[]->(strategy)
        MATCH (pc:ProductCategory)-[]->(strategy)
        WHERE (strategy)-[:BELONGS_TO]->(:Account {{account_id: $account_id}})
        RETURN strategy,
               cp.node_id as customer_profile_node_id,
               pc.node_id as product_category_node_id,
               $account_id as account_id
        """
    else:
        # Use existing query for non-marketing nodes
```

**Recommendation**: Add `customer_profile_node_id` and `product_category_node_id` as **stored properties** on strategy nodes for simpler queries. This deviates from current implementation but improves query performance and API simplicity.

**Proposed Change**:
```python
node_data = {
    "node_id": node_id,
    "description": description,
    "references": references,
    "customer_profile_node_id": customer_profile_id,  # ADD THIS
    "product_category_node_id": product_category_id,  # ADD THIS
    # ... audit fields
}
```

### Q4: Duplicate Display Names - Allowed?

**Answer**: NO - Enforce unique display_name per account (user requirement).

**Implementation**:
```python
async def validate_unique_customer_profile_name(
    account_id: str,
    display_name: str,
    exclude_node_id: str | None = None
) -> tuple[bool, str]:
    """Check for duplicate CustomerProfile display_name in account."""
    query = """
    MATCH (cp:CustomerProfile)-[:BELONGS_TO]->(:Account {account_id: $account_id})
    WHERE toLower(cp.display_name) = toLower($display_name)
    AND ($exclude_node_id IS NULL OR cp.node_id <> $exclude_node_id)
    RETURN count(cp) as count
    """
    # ...
```

### Q5: CustomerProfile Deletion Behavior

**Answer**: Cascade delete all 5 strategy nodes AND all IS_MARKETED_TO relationships (user requirement).

**Implementation**: See section 5.7, item 3 above.

---

## Recommendation: Store Parent IDs as Properties

**Current Issue**: Strategy nodes use relationships only to identify parents. This requires complex queries with multiple MATCH clauses.

**Proposed Solution**: Store parent node_ids as properties:

**Benefits**:
- ✅ Simpler queries (no relationship traversal needed)
- ✅ Faster performance (indexed property lookups)
- ✅ Easier to filter/paginate (e.g., "get all strategies for ProductCategory X")
- ✅ Consistent with how Competitor tactics store `competitor_node_id`

**Implementation**:
```python
# When creating strategy:
node_data = {
    "node_id": f"problemaware_{category_id}_{profile_id}",
    "description": description,
    "references": references,
    "customer_profile_node_id": profile_id,  # STORE AS PROPERTY
    "product_category_node_id": category_id,  # STORE AS PROPERTY
    # ... audit fields
}
```

**Relationships still created** for graph traversal, but properties make queries simpler.

**Decision Required**: Should we store parent IDs as properties or rely on relationships only?

---

## Implementation Checklist

### Step 4: Documentation (1-2 hours)

- [ ] Add "Important Implementation Notes" section to marketing_requirements.md
- [ ] Document dual-parent architecture and scoping
- [ ] Add account_id to all node tables
- [ ] Add references field to all nodes
- [ ] Fix CustomerProfile fields (display_name + narrative, not description)
- [ ] Document ProductCategory relationships (HAS_*_STRATEGY)
- [ ] Add strategy node fields (customer_profile_node_id, product_category_node_id) if storing as properties
- [ ] Document cascade deletion behavior
- [ ] Document IS_MARKETED_TO relationship lifecycle

### Step 5: Implementation (4-6 hours)

**Constants** (10 min):
- [ ] Add 6 marketing node types to VALID_NODE_TYPES
- [ ] Add 6 node types to NODE_TYPE_TO_PREFIX

**Models** (1 hour):
- [ ] Create 4 CustomerProfile models
- [ ] Create 20 strategy node models (4 each × 5 types)
- [ ] Create 2 relationship management models
- [ ] Create 1 aggregated view model
- [ ] Create helper models if needed

**Service Layer** (2 hours):
- [ ] Add CustomerProfile CRUD methods (3)
- [ ] Add strategy node CRUD methods (10 = 2 per type)
- [ ] Add relationship management methods (2)
- [ ] Add query helper methods (2-3)
- [ ] Update relationship mapping (10 new mappings)
- [ ] Update _create_node_neo4j to support dual parents (if using Option A)
- [ ] Update _validate_can_delete for CustomerProfile
- [ ] Add Firestore sync support for marketing_strategy doc type

**Validation** (30 min):
- [ ] Add validate_unique_customer_profile_name
- [ ] Add validate_can_delete_customer_profile
- [ ] Add validate_strategy_not_exists
- [ ] Update validate_can_delete_product_category to check marketing strategies

**Router** (2 hours):
- [ ] Add imports for 31 new models
- [ ] Add CustomerProfile endpoints (5)
- [ ] Add ProblemAwarenessStrategy endpoints (5)
- [ ] Add BrandAwarenessStrategy endpoints (5)
- [ ] Add ConsiderationStrategy endpoints (5)
- [ ] Add ConversionStrategy endpoints (5)
- [ ] Add LoyaltyStrategy endpoints (5)
- [ ] Add relationship management endpoints (2)
- [ ] Add aggregated view endpoint (1)

**Testing** (1-2 hours):
- [ ] Write 6-8 unit tests
- [ ] Write 3-4 integration test classes
- [ ] Test dual-parent creation
- [ ] Test cascade deletion
- [ ] Test IS_MARKETED_TO relationship management
- [ ] Fix any test failures

**Quality** (30 min):
- [ ] Run ruff format
- [ ] Run ruff check --fix
- [ ] Run pytest
- [ ] Fix any failures
- [ ] Update MARKETING_STRATEGY_IMPLEMENTATION_SUMMARY.md

---

## Estimated Scope

**Total Lines**: ~3,200-3,800 (more than competitive due to dual-parent complexity)
**Time**: 6-8 hours
**Complexity**: **HIGH** (dual-parent architecture, cascade deletion, relationship management)

---

## Critical Decision Points

### Decision 1: Store Parent IDs as Properties?

**Option A**: Store as properties (RECOMMENDED)
- Simpler queries, faster performance
- Consistent with competitive strategy pattern (competitor_node_id)
- Easier API implementation

**Option B**: Relationships only (current agent implementation)
- More "graph native"
- Requires complex queries for every get/list operation
- Harder to filter/paginate

**Recommendation**: **Option A** - Store parent IDs as properties for API simplicity

### Decision 2: Strategy Creation API Design

**Option A**: Individual strategy creation (RECOMMENDED)
```
POST /{account_id}/problem-awareness-strategies
Body: { description, customer_profile_node_id, product_category_node_id }
```
- Create one strategy at a time
- More RESTful
- Easier to implement

**Option B**: Batch strategy creation
```
POST /{account_id}/product-categories/{category_id}/marketing-strategies/{profile_id}
Body: { problem_awareness, brand_awareness, consideration, conversion, loyalty }
```
- Create all 5 at once
- Matches agent system behavior
- More complex implementation

**Recommendation**: **Option A** for initial implementation, can add Option B later as convenience endpoint

### Decision 3: Cascade Deletion Behavior

When deleting CustomerProfile, should we:

**Option A**: Block deletion if IS_MARKETED_TO relationships exist
- Safer, prevents accidental data loss
- Forces user to explicitly remove links first

**Option B**: Cascade delete (RECOMMENDED per user requirement)
- Deletes all strategy nodes
- Deletes all IS_MARKETED_TO relationships
- More convenient, matches user expectation

**Recommendation**: **Option B** - Cascade delete per user requirement

---

## Next Steps

1. **Get decision on parent ID storage** (properties vs relationships only)
2. **Confirm API design** (individual vs batch strategy creation)
3. **Review and approve this plan**
4. **Begin implementation** following TDD approach

**Would you like me to:**
- A) Proceed with implementation using recommended approaches (Option A for all decisions)
- B) Discuss the architectural decisions first
- C) Start with Step 4 (documentation) while you review the plan
