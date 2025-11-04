# Phase 1 Implementation Plan: Strategy Graph CRUD APIs

## Executive Summary

This document provides a comprehensive implementation plan for creating CRUD API endpoints for all four strategy types (Business, Competitive, Marketing, Brand). The goal is to enable users to edit individual nodes in the knowledge graph without regenerating entire strategy documents.

**Implementation Timeline**: Steps 1-7 (API & Documentation)
**Architecture**: Neo4j as primary source of truth, with bidirectional sync to Firestore (temporary, plan to deprecate)
**Code Organization**: Unified router and service (single file per layer) to eliminate code duplication
**Testing**: Unit tests + Integration tests following TDD principles
**Auth**: Reuse existing authentication patterns from `strategy.py`

### Key Architectural Decision: Unified Files

**This plan uses a UNIFIED architecture** (single router, single service) rather than separate files per strategy type.

**Why Unified:**
- ✅ **DRY Principle**: All CRUD operations follow identical patterns - write once, use for all 30 node types
- ✅ **CLAUDE.md C-9**: Don't extract functions unless reused (sync logic is identical across types)
- ✅ **Existing Pattern**: Matches `strategy.py` which handles all 4 strategy document types in one file
- ✅ **Maintainability**: Bug fixes and updates in single location
- ✅ **Consistency**: Enforced behavior across all node types
- ✅ **Simplicity**: 6 total files vs 16 files with separate architecture

**File Structure:**
- 1 Router: `knowledge_graph.py` (~1000 lines, well-organized with section headers)
- 2 Services: `graph_sync_service.py` + `graph_validation_service.py` (~1100 lines total)
- 1 Models: `graph_models.py` (~600 lines)
- 3 Test Files: Unit + Integration (~2100 lines total)

**Total: 6 files instead of 16** - Same functionality, zero code duplication

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Design Principles](#design-principles)
3. [Implementation Steps](#implementation-steps)
4. [API Specifications](#api-specifications)
5. [Service Layer Design](#service-layer-design)
6. [Testing Strategy](#testing-strategy)
7. [Documentation Updates](#documentation-updates)
8. [Common Patterns](#common-patterns)
9. [Error Handling](#error-handling)
10. [Migration Path](#migration-path)

---

## Architecture Overview

### Current State
```
┌─────────────┐
│   Agent     │
│   System    │
└──────┬──────┘
       │
       │ Direct writes
       │
┌──────▼──────────────────────┐
│                              │
│  ┌────────────┐ ┌─────────┐ │
│  │   Neo4j    │ │Firestore│ │
│  │  (Graph)   │ │ (Docs)  │ │
│  └────────────┘ └─────────┘ │
│                              │
└──────────────────────────────┘
```

### Target State (Phase 1)
```
┌─────────────┐        ┌─────────────┐
│   Agent     │        │   Frontend  │
│   System    │        │             │
└──────┬──────┘        └──────┬──────┘
       │                      │
       │ Direct writes        │ REST API
       │                      │
       │              ┌───────▼──────────┐
       │              │  FastAPI         │
       │              │  ┌────────────┐  │
       │              │  │Graph Sync  │  │
       │              │  │Service     │  │
       │              │  └─────┬──────┘  │
       │              └────────┼─────────┘
       │                       │
       │                       │ Bidirectional sync
       │                       │
┌──────▼───────────────────────▼────┐
│                                    │
│  ┌────────────┐   ┌─────────────┐ │
│  │   Neo4j    │   │  Firestore  │ │
│  │  (Primary) │◄──┤  (Synced)   │ │
│  └────────────┘   └─────────────┘ │
│                                    │
└────────────────────────────────────┘
```

### Data Flow for User Edits
```
1. User edits node in Frontend
   ↓
2. Frontend sends PATCH /api/v1/knowledge-graph/{account_id}/products/{node_id}
   ↓
3. API validates request (auth, permissions, data)
   ↓
4. GraphSyncService starts transaction
   ↓
5. Update Neo4j (primary)
   ↓
6. Update Firestore document (sync)
   ↓
7. Both succeed → Commit transaction
   Any fails → Rollback both
   ↓
8. Trigger embedding regeneration (async)
   ↓
9. Return success response to Frontend
```

---

## Design Principles

### 1. CLAUDE.md Compliance

All code MUST follow best practices from CLAUDE.md:

**Before Coding:**
- BP-1: Clarify requirements with stakeholders
- BP-2: Draft approach for complex work
- BP-3: List pros/cons for alternatives

**While Coding:**
- C-1: Follow TDD (test first, then implement)
- C-4: Prefer simple, composable, testable functions
- C-9: Don't extract functions unless reused (DRY principle)
- PY-1: Use type hints for all functions
- PY-2: Use Pydantic models for validation
- PY-3: Use async/await for I/O operations
- PY-5: Use context managers for database operations

**Testing:**
- T-1: Colocate tests in `test_*.py` files
- T-4: Separate unit tests from integration tests
- T-5: Prefer integration tests over heavy mocking

**Database:**
- D-1: Use Neo4j session management with context managers
- D-2: Define Pydantic models in `api/src/kene_api/models/`

### 2. Consistency with Existing Code

**Reuse Patterns From:**
- `api/src/kene_api/routers/strategy.py` - Auth, access control, single router for all strategy types
- `api/src/kene_api/routers/products.py` - CRUD operations
- `api/src/kene_api/database.py` - Neo4j service patterns
- `app/adk/agents/strategy_agent/business_graph_builder.py` - Graph operations

**Naming Conventions:**
- Router file: `knowledge_graph.py` (unified, handles all node types)
- Service file: `graph_sync_service.py` (unified, generic CRUD logic)
- Validation file: `graph_validation_service.py` (shared validation rules)
- Model file: `graph_models.py` (all Pydantic models)
- Test files: `test_knowledge_graph.py`, `test_graph_sync_service.py`

### 3. Unified vs Separate Files Decision

**Architecture Choice: UNIFIED FILES**

Following CLAUDE.md best practice C-9 and existing codebase patterns (`strategy.py` handles all strategy document types), we use a **unified architecture**:

**Benefits:**
- ✅ **DRY Principle**: Generic CRUD logic written once, used for all node types
- ✅ **Consistency**: Single source of truth for sync operations
- ✅ **Maintainability**: Bug fixes in one place, not four
- ✅ **Codebase Pattern**: Matches `strategy.py` (single router for domain)
- ✅ **Simplicity**: Fewer files, clearer organization
- ✅ **CLAUDE.md C-9**: Don't extract unless reused (sync logic is identical across node types)

**File Size Justification:**
- Unified router: ~1000 lines (similar to `accounts.py` at 600 lines)
- Unified service: ~800 lines (manageable for single concern)
- Well-organized with clear section headers

### 4. Graph Integrity

**Strict Validation Rules:**
1. Never create orphaned nodes (always validate parent exists)
2. Validate all relationships before deletion
3. Check bidirectional relationships are maintained
4. Ensure `BELONGS_TO` relationship always exists for child nodes
5. Validate `Strategy` label is applied to all strategy nodes

### 5. Error Handling

**Atomic Operations with Rollback:**
```python
async def update_node_with_sync(node_id: str, updates: dict) -> Node:
    async with transaction_coordinator() as txn:
        try:
            # 1. Update Neo4j
            neo4j_result = await neo4j_service.update_node(node_id, updates, txn)

            # 2. Update Firestore
            firestore_result = await firestore_service.sync_node_update(node_id, updates, txn)

            # 3. Both succeed → commit
            if neo4j_result and firestore_result:
                await txn.commit()
                return neo4j_result
            else:
                raise Exception("Sync failed")

        except Exception as e:
            # Rollback both on any failure
            await txn.rollback()
            logger.error(f"Transaction failed: {e}")
            raise
```

---

## Implementation Steps

### Step 1: Create Unified API Foundation & Business Strategy Endpoints

**Goal**: Set up unified router/service architecture and implement Business Strategy CRUD endpoints

**Files to Create:**
- `api/src/kene_api/routers/knowledge_graph.py` (NEW - unified router for all strategies)
- `api/src/kene_api/services/graph_sync_service.py` (NEW - unified sync service)
- `api/src/kene_api/services/graph_validation_service.py` (NEW - shared validation)
- `api/src/kene_api/models/graph_models.py` (NEW - all Pydantic models)
- `api/tests/integration/test_knowledge_graph.py` (NEW - all endpoint tests)
- `api/tests/unit/services/test_graph_sync_service.py` (NEW - service tests)

**Why Unified Architecture:**
Following CLAUDE.md C-9 (don't extract unless reused) and existing patterns from `strategy.py`, we use a single router and service for all node types because:
- CRUD operations follow identical patterns across all node types
- Eliminates code duplication (DRY principle)
- Single source of truth for sync logic
- Consistent with `strategy.py` which handles all strategy document types in one file
- Easier maintenance (fix bugs once, not four times)

**Node Types to Support:**
- ProductCategory
- Product
- ValueProposition
- SWOTAnalysis (hub)
- Strength
- Weakness
- Opportunity
- Risk
- Goal

**Endpoints to Create:**

**ProductCategory:**
```
POST   /api/v1/knowledge-graph/{account_id}/product-categories
GET    /api/v1/knowledge-graph/{account_id}/product-categories
GET    /api/v1/knowledge-graph/{account_id}/product-categories/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/product-categories/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/product-categories/{node_id}
```

**Product:**
```
POST   /api/v1/knowledge-graph/{account_id}/products
GET    /api/v1/knowledge-graph/{account_id}/products
GET    /api/v1/knowledge-graph/{account_id}/products/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/products/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/products/{node_id}
```

**ValueProposition:**
```
POST   /api/v1/knowledge-graph/{account_id}/value-propositions
GET    /api/v1/knowledge-graph/{account_id}/value-propositions
GET    /api/v1/knowledge-graph/{account_id}/value-propositions/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/value-propositions/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/value-propositions/{node_id}
```

**SWOT Nodes (Strength, Weakness, Opportunity, Risk):**
```
POST   /api/v1/knowledge-graph/{account_id}/strengths
GET    /api/v1/knowledge-graph/{account_id}/strengths
GET    /api/v1/knowledge-graph/{account_id}/strengths/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/strengths/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/strengths/{node_id}

# Similar for weaknesses, opportunities, risks
```

**Goal:**
```
POST   /api/v1/knowledge-graph/{account_id}/goals
GET    /api/v1/knowledge-graph/{account_id}/goals
GET    /api/v1/knowledge-graph/{account_id}/goals/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/goals/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/goals/{node_id}
```

**Aggregated View:**
```
GET    /api/v1/knowledge-graph/{account_id}/business-strategy
```
Returns complete business strategy graph as JSON (similar to Firestore document structure)

---

### Step 2: Update Competitive Strategist Documentation

**Goal**: Ensure `knowledge_graph/competitor_requirements.md` accurately reflects Neo4j implementation

**Task**: Review `app/adk/agents/strategy_agent/competitive_graph_builder.py` and update documentation

**Required Updates:**

1. **Add Implementation Notes Section** (matching `business_requirements.md` format):
```markdown
**Important Implementation Notes:**

1. **Strategy Label**: All competitive strategy nodes receive TWO labels:
   - Specific node type (e.g., `Competitor`, `SubstituteProduct`)
   - Generic `Strategy` label for embedding search

2. **Bidirectional Relationships**:
   - `Account -[:OPERATES_WITHIN]-> CompetitiveEnvironment`
   - `CompetitiveEnvironment -[:BELONGS_TO]-> Account`

3. **SWOT Pattern**: Competitor strengths/weaknesses use CREATES relationships
   - CompetitorStrength -[:CREATES]-> Risk
   - CompetitorWeakness -[:CREATES]-> Opportunity
```

2. **Add Missing Fields:**
- Review each node type (Competitor, CompetitorTactic, SubstituteProduct, etc.)
- Ensure `references` field is documented
- Verify `created_time`, `last_modified`, `created_by`, `last_modified_by`, `embedding` fields
- Check all relationship types are bidirectional where needed

3. **Verify Node Structures:**
- CompetitiveEnvironment (hub node)
- Competitor
- CompetitorTactic
- CompetitorStrength
- CompetitorWeakness
- SubstituteProduct
- Risk (from competitor strengths)
- Opportunity (from competitor weaknesses)

4. **Document Relationships:**
- `Product -[:MAY_BE_SUBSTITUTED_FOR]-> SubstituteProduct`
- `Competitor -[:USES_MARKETING_TACTIC]-> CompetitorTactic`
- `Competitor -[:HAS_VALUE_PROPOSITION]-> ValueProposition`

---

### Step 3: Add Competitive Strategy Endpoints

**Goal**: Extend unified router/service to support Competitive Strategy nodes

**Files to Modify:**
- `api/src/kene_api/routers/knowledge_graph.py` (ADD competitive endpoints section)
- `api/src/kene_api/services/graph_sync_service.py` (ADD competitive-specific helpers if needed)
- `api/src/kene_api/models/graph_models.py` (ADD competitive Pydantic models)
- `api/tests/integration/test_knowledge_graph.py` (ADD competitive endpoint tests)
- `api/tests/unit/services/test_graph_sync_service.py` (ADD competitive operation tests)

**Node Types to Support:**
- CompetitiveEnvironment (hub)
- Competitor
- CompetitorTactic
- CompetitorStrength
- CompetitorWeakness
- SubstituteProduct
- Risk (competitive)
- Opportunity (competitive)

**Endpoints to Create:**

**Competitor:**
```
POST   /api/v1/knowledge-graph/{account_id}/competitors
GET    /api/v1/knowledge-graph/{account_id}/competitors
GET    /api/v1/knowledge-graph/{account_id}/competitors/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/competitors/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/competitors/{node_id}
```

**CompetitorTactic:**
```
POST   /api/v1/knowledge-graph/{account_id}/competitor-tactics
GET    /api/v1/knowledge-graph/{account_id}/competitor-tactics
GET    /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/competitor-tactics/{node_id}
```

**SubstituteProduct:**
```
POST   /api/v1/knowledge-graph/{account_id}/substitute-products
GET    /api/v1/knowledge-graph/{account_id}/substitute-products
GET    /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/substitute-products/{node_id}
```

**Aggregated View:**
```
GET    /api/v1/knowledge-graph/{account_id}/competitive-strategy
```

---

### Step 4: Update Marketing Strategist Documentation

**Goal**: Ensure `knowledge_graph/marketing_requirements.md` accurately reflects Neo4j implementation

**Task**: Review `app/adk/agents/strategy_agent/marketing_graph_builder.py` and update documentation

**Required Updates:**

1. **Add Implementation Notes Section**:
```markdown
**Important Implementation Notes:**

1. **Strategy Label**: All marketing nodes (CustomerProfile, strategy nodes) receive:
   - Specific label (e.g., `CustomerProfile`, `ProblemAwarenessStrategy`)
   - Generic `Strategy` label

2. **Linking Pattern**: ProductCategory links to CustomerProfile via:
   - `ProductCategory -[:IS_MARKETED_TO]-> CustomerProfile`

3. **Strategy Chain**: Each CustomerProfile connects to 5 strategy nodes:
   - ProblemAwarenessStrategy
   - BrandAwarenessStrategy
   - ConsiderationStrategy
   - ConversionStrategy
   - LoyaltyStrategy
```

2. **Add Missing Fields:**
- Add `references` field to CustomerProfile and strategy nodes
- Document standard audit fields (`created_time`, etc.)

3. **Verify Node Structures:**
- CustomerProfile (hub)
- ProblemAwarenessStrategy
- BrandAwarenessStrategy
- ConsiderationStrategy
- ConversionStrategy
- LoyaltyStrategy

---

### Step 5: Add Marketing Strategy Endpoints

**Goal**: Extend unified router/service to support Marketing Strategy nodes

**Files to Modify:**
- `api/src/kene_api/routers/knowledge_graph.py` (ADD marketing endpoints section)
- `api/src/kene_api/services/graph_sync_service.py` (ADD marketing-specific helpers if needed)
- `api/src/kene_api/models/graph_models.py` (ADD marketing Pydantic models)
- `api/tests/integration/test_knowledge_graph.py` (ADD marketing endpoint tests)
- `api/tests/unit/services/test_graph_sync_service.py` (ADD marketing operation tests)

**Node Types to Support:**
- CustomerProfile
- ProblemAwarenessStrategy
- BrandAwarenessStrategy
- ConsiderationStrategy
- ConversionStrategy
- LoyaltyStrategy

**Endpoints to Create:**

**CustomerProfile:**
```
POST   /api/v1/knowledge-graph/{account_id}/customer-profiles
GET    /api/v1/knowledge-graph/{account_id}/customer-profiles
GET    /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}
PATCH  /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}
DELETE /api/v1/knowledge-graph/{account_id}/customer-profiles/{node_id}
```

**Marketing Strategies:**
```
# Problem Awareness
PATCH  /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies/{node_id}
GET    /api/v1/knowledge-graph/{account_id}/problem-awareness-strategies/{node_id}

# Brand Awareness
PATCH  /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies/{node_id}
GET    /api/v1/knowledge-graph/{account_id}/brand-awareness-strategies/{node_id}

# Similar for consideration, conversion, loyalty
```

**Aggregated View:**
```
GET    /api/v1/knowledge-graph/{account_id}/marketing-strategy
```

---

### Step 6: Update Brand Strategist Documentation

**Goal**: Ensure `knowledge_graph/brand_requirements.md` accurately reflects Neo4j implementation

**Task**: Review `app/adk/agents/strategy_agent/brand_graph_builder.py` and update documentation

**Required Updates:**

1. **Add Implementation Notes Section**:
```markdown
**Important Implementation Notes:**

1. **Strategy Label**: All brand nodes receive dual labels:
   - Specific label (e.g., `BrandIdentity`, `BrandPersonality`)
   - Generic `Strategy` label

2. **Hub Pattern**: BrandIdentity is the central hub with 6 child nodes:
   - BrandPersonality
   - VoiceAndTone
   - ColorPalette
   - Typography
   - ImageStyle
   - MissionAndValues

3. **Account Link**:
   - `Account -[:FOLLOWS_THESE_BRAND_GUIDELINES]-> BrandIdentity`
```

2. **Add Missing Fields:**
- Add `references` field where applicable
- Document audit fields consistently

3. **Verify All 7 Node Types:**
- BrandIdentity (hub)
- BrandPersonality
- VoiceAndTone
- ColorPalette
- Typography
- ImageStyle
- MissionAndValues

---

### Step 7: Add Brand Strategy Endpoints

**Goal**: Extend unified router/service to support Brand Strategy nodes

**Files to Modify:**
- `api/src/kene_api/routers/knowledge_graph.py` (ADD brand endpoints section)
- `api/src/kene_api/services/graph_sync_service.py` (ADD brand-specific helpers if needed)
- `api/src/kene_api/models/graph_models.py` (ADD brand Pydantic models)
- `api/tests/integration/test_knowledge_graph.py` (ADD brand endpoint tests)
- `api/tests/unit/services/test_graph_sync_service.py` (ADD brand operation tests)

**Node Types to Support:**
- BrandIdentity (hub)
- BrandPersonality
- VoiceAndTone
- ColorPalette
- Typography
- ImageStyle
- MissionAndValues

**Endpoints to Create:**

**BrandIdentity:**
```
GET    /api/v1/knowledge-graph/{account_id}/brand-identity
PATCH  /api/v1/knowledge-graph/{account_id}/brand-identity
```

**Brand Child Nodes:**
```
PATCH  /api/v1/knowledge-graph/{account_id}/brand-personality
GET    /api/v1/knowledge-graph/{account_id}/brand-personality

PATCH  /api/v1/knowledge-graph/{account_id}/voice-and-tone
GET    /api/v1/knowledge-graph/{account_id}/voice-and-tone

# Similar for color-palette, typography, image-style, mission-and-values
```

**Aggregated View:**
```
GET    /api/v1/knowledge-graph/{account_id}/brand-guidelines
```

---

## API Specifications

### Common Request/Response Models

**All Pydantic models should be in:** `api/src/kene_api/models/graph_models.py`

#### Base Models

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class NodeBase(BaseModel):
    """Base model for all graph nodes."""
    node_id: str = Field(..., description="Unique node identifier")
    created_time: datetime
    last_modified: datetime
    created_by: str
    last_modified_by: str
    embedding: Optional[List[float]] = None


class ProductCategoryCreate(BaseModel):
    """Request model for creating a product category."""
    product_name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=4000)


class ProductCategoryUpdate(BaseModel):
    """Request model for updating a product category."""
    product_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=4000)


class ProductCategoryResponse(NodeBase):
    """Response model for product category."""
    product_name: str
    description: str
    account_id: str


class ProductCreate(BaseModel):
    """Request model for creating a product."""
    product_name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=4000)
    references: List[str] = Field(default_factory=list)
    product_detail_page: Optional[str] = None
    category_node_id: str = Field(..., description="Parent ProductCategory node_id")


class ProductUpdate(BaseModel):
    """Request model for updating a product."""
    product_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=4000)
    references: Optional[List[str]] = None
    product_detail_page: Optional[str] = None


class ProductResponse(NodeBase):
    """Response model for product."""
    product_name: str
    description: str
    references: List[str]
    product_detail_page: Optional[str]
    account_id: str
    category_node_id: str


class ValuePropositionCreate(BaseModel):
    """Request model for creating a value proposition."""
    display_name: str = Field(..., max_length=60)
    description: str = Field(..., max_length=4000)
    references: List[str] = Field(default_factory=list)
    parent_node_id: str = Field(..., description="Parent node (Product, ProductCategory, or Account)")
    parent_node_type: str = Field(..., description="Type of parent: Product, ProductCategory, or Account")


class ValuePropositionUpdate(BaseModel):
    """Request model for updating a value proposition."""
    display_name: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field(None, max_length=4000)
    references: Optional[List[str]] = None


class ValuePropositionResponse(NodeBase):
    """Response model for value proposition."""
    display_name: str
    description: str
    references: List[str]
    account_id: str
    parent_node_id: str
    parent_node_type: str
```

### Authentication & Authorization

**Reuse existing auth from `strategy.py`:**

```python
from ..auth.dependencies import get_current_user
from ..auth.models import UserContext


async def check_graph_access(
    account_id: str,
    user: UserContext,
    required_level: str = "view"
) -> UserContext:
    """
    Check if user has required access level for graph operations.

    Args:
        account_id: Account ID to check access for
        user: Current user context
        required_level: Required permission level (view or edit)

    Returns:
        User context if access granted

    Raises:
        HTTPException: If access denied
    """
    # Super admins always have access
    if user.is_super_admin:
        return user

    # Check account-level permissions
    if not user.has_account_access(account_id, [required_level] if required_level == "edit" else None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions for {required_level} access to account {account_id}"
        )

    return user
```

### Standard Endpoint Pattern

**Example for Product CRUD:**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..models.graph_models import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse
)
from ..services.graph_sync_service import GraphSyncService, get_graph_sync_service

router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["knowledge-graph"])


# ==================== BUSINESS STRATEGY ENDPOINTS ====================

@router.post("/{account_id}/products", response_model=ProductResponse)
async def create_product(
    account_id: str,
    product: ProductCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user)
) -> ProductResponse:
    """
    Create a new product node in the knowledge graph.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.create_product(account_id, product, user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create product: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create product")


@router.get("/{account_id}/products", response_model=ProductListResponse)
async def list_products(
    account_id: str,
    category_node_id: Optional[str] = Query(None, description="Filter by category"),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user)
) -> ProductListResponse:
    """
    List all products for an account.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        products = await service.list_products(account_id, category_node_id)
        return ProductListResponse(products=products, total_count=len(products))
    except Exception as e:
        logger.error(f"Failed to list products: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list products")


@router.get("/{account_id}/products/{node_id}", response_model=ProductResponse)
async def get_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user)
) -> ProductResponse:
    """
    Get a specific product by node_id.

    Requires view permission for the account.
    """
    await check_graph_access(account_id, user, "view")

    try:
        product = await service.get_product(account_id, node_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get product: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get product")


@router.patch("/{account_id}/products/{node_id}", response_model=ProductResponse)
async def update_product(
    account_id: str,
    node_id: str,
    updates: ProductUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user)
) -> ProductResponse:
    """
    Update a product node.

    Requires edit permission for the account.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        result = await service.update_product(account_id, node_id, updates, user.user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update product: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update product")


@router.delete("/{account_id}/products/{node_id}")
async def delete_product(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user)
) -> dict:
    """
    Delete a product node.

    Requires edit permission for the account.
    Validates that deletion won't orphan related nodes.
    """
    await check_graph_access(account_id, user, "edit")

    try:
        await service.delete_product(account_id, node_id, user.user_id)
        return {"success": True, "message": f"Product {node_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete product: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete product")
```

---

## Service Layer Design

### GraphSyncService (Unified)

**Location:** `api/src/kene_api/services/graph_sync_service.py`

**Purpose:** Unified service that coordinates Neo4j and Firestore updates for ALL strategy node types (Business, Competitive, Marketing, Brand)

**Architecture:** Generic CRUD operations that work for any node type through parameterization

**Key Methods:**

```python
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import uuid

from ..database import Neo4jService
from ..firestore import FirestoreService
from ..models.graph_models import (
    ProductCreate, ProductUpdate, ProductResponse,
    CompetitorCreate, CompetitorUpdate, CompetitorResponse,
    CustomerProfileCreate, CustomerProfileUpdate, CustomerProfileResponse,
    # ... all other models
)

logger = logging.getLogger(__name__)


class GraphSyncService:
    """
    Unified service for syncing ALL strategy nodes between Neo4j and Firestore.

    Handles: Business, Competitive, Marketing, and Brand strategy nodes.
    Uses generic CRUD operations to avoid code duplication.
    """

    def __init__(self, neo4j_service: Neo4jService, firestore_service: FirestoreService):
        self.neo4j = neo4j_service
        self.firestore = firestore_service

    # ==================== GENERIC CRUD OPERATIONS ====================
    # These methods work for ANY node type through parameterization

    async def create_node(
        self,
        account_id: str,
        node_type: str,
        node_data: dict,
        parent_node_id: Optional[str],
        parent_node_type: Optional[str],
        user_id: str,
        firestore_doc_type: str
    ) -> dict:
        """
        Generic node creation with Neo4j + Firestore sync.

        Works for ALL node types: Product, Competitor, CustomerProfile, etc.

        Args:
            node_type: "Product", "Competitor", "CustomerProfile", etc.
            node_data: Node properties (pre-validated by Pydantic)
            parent_node_id: Optional parent for relationship
            parent_node_type: Type of parent node
            firestore_doc_type: "business_strategy", "competitive_strategy", etc.
        """
        try:
            # 1. Validate account exists
            if not await self._validate_account_exists(account_id):
                raise ValueError(f"Account {account_id} not found")

            # 2. Validate parent exists (if required)
            if parent_node_id:
                if not await self._validate_node_exists(parent_node_id, parent_node_type):
                    raise ValueError(f"Parent {parent_node_type} {parent_node_id} not found")

            # 3. Generate node_id with appropriate prefix
            node_id = self._generate_node_id(node_type, account_id)

            # 4. Create in Neo4j with bidirectional relationships
            neo4j_result = await self._create_node_neo4j(
                node_id=node_id,
                node_type=node_type,
                node_data=node_data,
                account_id=account_id,
                parent_node_id=parent_node_id,
                parent_node_type=parent_node_type,
                user_id=user_id
            )

            # 5. Sync to Firestore
            try:
                await self._sync_node_to_firestore(
                    account_id=account_id,
                    node_id=node_id,
                    node_type=node_type,
                    node_data=neo4j_result,
                    firestore_doc_type=firestore_doc_type,
                    operation="create"
                )
            except Exception as firestore_error:
                # Rollback Neo4j on Firestore failure
                await self._delete_node_neo4j(node_id)
                raise Exception(f"Firestore sync failed, rolled back Neo4j: {firestore_error}")

            return neo4j_result

        except Exception as e:
            logger.error(f"Failed to create {node_type}: {e}")
            raise

    async def update_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        updates: dict,
        user_id: str,
        firestore_doc_type: str
    ) -> dict:
        """Generic node update with atomic rollback on failure."""
        # Similar implementation pattern...

    async def delete_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        user_id: str,
        firestore_doc_type: str,
        check_dependencies: bool = True
    ) -> None:
        """Generic node deletion with dependency validation."""
        # Similar implementation pattern...

    # ==================== CONVENIENCE WRAPPERS ====================
    # Domain-specific methods that call generic operations

    async def create_product_category(
        self,
        account_id: str,
        category: ProductCategoryCreate,
        user_id: str
    ) -> ProductCategoryResponse:
        """
        Convenience wrapper for creating product categories.

        Thin wrapper around generic create_node() method.
        """
        node_data = {
            "product_name": category.product_name,
            "description": category.description
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="ProductCategory",
            node_data=node_data,
            parent_node_id=None,  # ProductCategory links directly to Account
            parent_node_type="Account",
            user_id=user_id,
            firestore_doc_type="business_strategy"
        )

        return ProductCategoryResponse(**result)

    async def create_product(
        self,
        account_id: str,
        product: ProductCreate,
        user_id: str
    ) -> ProductResponse:
        """Convenience wrapper for creating products."""
        node_data = {
            "product_name": product.product_name,
            "description": product.description,
            "references": product.references,
            "product_detail_page": product.product_detail_page
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Product",
            node_data=node_data,
            parent_node_id=product.category_node_id,
            parent_node_type="ProductCategory",
            user_id=user_id,
            firestore_doc_type="business_strategy"
        )

        return ProductResponse(**result)

    async def create_competitor(
        self,
        account_id: str,
        competitor: CompetitorCreate,
        user_id: str
    ) -> CompetitorResponse:
        """Convenience wrapper for creating competitors."""
        node_data = {
            "name": competitor.name,
            "description": competitor.description,
            "website": competitor.website,
            "references": competitor.references
        }

        result = await self.create_node(
            account_id=account_id,
            node_type="Competitor",
            node_data=node_data,
            parent_node_id=None,  # Will link to CompetitiveEnvironment in _create_node_neo4j
            parent_node_type=None,
            user_id=user_id,
            firestore_doc_type="competitive_strategy"
        )

        return CompetitorResponse(**result)

    # ==================== GENERIC HELPER METHODS ====================

    def _generate_node_id(self, node_type: str, account_id: str) -> str:
        """
        Generate node_id with appropriate prefix based on node type.

        Matches naming conventions from graph builders.
        """
        prefix_map = {
            # Business Strategy
            "Product": "prod",
            "ProductCategory": "productcat",
            "ValueProposition": "value",
            "Strength": "strength",
            "Weakness": "weakness",
            "Opportunity": "opportunity",
            "Risk": "risk",
            "Goal": "goal",
            "SWOTAnalysis": "swot",

            # Competitive Strategy
            "Competitor": "competitor",
            "CompetitorTactic": "tactic",
            "SubstituteProduct": "substitute",
            "CompetitorStrength": "compstrength",
            "CompetitorWeakness": "compweakness",
            "CompetitiveEnvironment": "competitiveenv",

            # Marketing Strategy
            "CustomerProfile": "icp",
            "ProblemAwarenessStrategy": "probaware",
            "BrandAwarenessStrategy": "brandaware",
            "ConsiderationStrategy": "consider",
            "ConversionStrategy": "convert",
            "LoyaltyStrategy": "loyalty",

            # Brand Guidelines
            "BrandIdentity": "brand",
            "BrandPersonality": "personality",
            "VoiceAndTone": "voicetone",
            "ColorPalette": "colors",
            "Typography": "typography",
            "ImageStyle": "imagestyle",
            "MissionAndValues": "mission",
        }

        prefix = prefix_map.get(node_type, "node")
        return f"{prefix}_{account_id}_{uuid.uuid4().hex[:8]}"

    async def _create_node_neo4j(
        self,
        node_id: str,
        node_type: str,
        node_data: dict,
        account_id: str,
        parent_node_id: Optional[str],
        parent_node_type: Optional[str],
        user_id: str
    ) -> dict:
        """
        Generic Neo4j node creation with bidirectional relationships.

        Handles ALL node types through parameterization.
        Applies Strategy label and standard audit fields automatically.
        """
        # Get relationship configuration for this node type
        relationship_config = self._get_relationship_config(node_type, parent_node_type)

        # Build base query with Strategy label and standard fields
        query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        MERGE (node:{node_type}:Strategy {{node_id: $node_id}})
        SET node += $node_data,
            node.account_id = $account_id,
            node.created_time = COALESCE(node.created_time, datetime()),
            node.last_modified = datetime(),
            node.created_by = COALESCE(node.created_by, $user_id),
            node.last_modified_by = $user_id,
            node.embedding = null
        MERGE (node)-[:BELONGS_TO]->(acc)
        """

        # Add parent relationship if specified
        if parent_node_id and relationship_config:
            query += f"""
            WITH node, acc
            MATCH (parent:{parent_node_type} {{node_id: $parent_node_id}})
            MERGE (node)-[:{relationship_config['to_parent']}]->(parent)
            MERGE (parent)-[:{relationship_config['from_parent']}]->(node)
            """

        query += " RETURN node"

        params = {
            "node_id": node_id,
            "account_id": account_id,
            "node_data": node_data,
            "user_id": user_id,
            "parent_node_id": parent_node_id
        }

        result = await self.neo4j.execute_write_query(query, params)

        if not result:
            raise Exception(f"Failed to create {node_type} in Neo4j")

        return self._neo4j_node_to_dict(result[0]["node"])

    def _get_relationship_config(self, node_type: str, parent_node_type: Optional[str]) -> Optional[dict]:
        """
        Get bidirectional relationship configuration for node type and parent.

        Returns dict with 'to_parent' and 'from_parent' relationship types.
        """
        relationship_map = {
            # Business Strategy
            ("Product", "ProductCategory"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "INCLUDES_PRODUCT"
            },
            ("ValueProposition", "Product"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("ValueProposition", "ProductCategory"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("ValueProposition", "Account"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "HAS_VALUE_PROPOSITION"
            },
            ("Strength", "SWOTAnalysis"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "HAS_STRENGTH"
            },
            ("Opportunity", "Strength"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "CREATES"
            },

            # Competitive Strategy
            ("Competitor", "CompetitiveEnvironment"): {
                "to_parent": "OPERATES_IN",
                "from_parent": "INCLUDES_COMPETITOR"
            },
            ("CompetitorTactic", "Competitor"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "USES_MARKETING_TACTIC"
            },
            ("SubstituteProduct", "Competitor"): {
                "to_parent": "OFFERED_BY",
                "from_parent": "OFFERS_SUBSTITUTE"
            },

            # Marketing Strategy
            ("CustomerProfile", "ProductCategory"): {
                "to_parent": "BELONGS_TO",
                "from_parent": "IS_MARKETED_TO"
            },
            ("ProblemAwarenessStrategy", "CustomerProfile"): {
                "to_parent": "TARGETS",
                "from_parent": "DISCOVERS_THE_PROBLEM_BY"
            },

            # Brand Guidelines
            ("BrandPersonality", "BrandIdentity"): {
                "to_parent": "DEFINES",
                "from_parent": "HAS_TRAITS_AND_CHARACTERISTICS"
            },
            # ... add all other relationships
        }

        return relationship_map.get((node_type, parent_node_type))

    async def _sync_node_to_firestore(
        self,
        account_id: str,
        node_id: str,
        node_type: str,
        node_data: dict,
        firestore_doc_type: str,
        operation: str
    ) -> None:
        """
        Generic Firestore sync for any node type.

        Routes node updates to appropriate location in Firestore document structure.

        Args:
            firestore_doc_type: "business_strategy", "competitive_strategy", "marketing_strategy", "brand_guidelines"
            operation: "create", "update", "delete"
        """
        doc_ref = f"strategy_docs_{account_id}/{firestore_doc_type}"

        # Get current document
        doc = self.firestore.get_document_sync(doc_ref)
        if not doc:
            raise ValueError(f"Strategy document {firestore_doc_type} not found for account {account_id}")

        # Route to appropriate sync method based on node type
        if node_type in ["Product", "ProductCategory", "ValueProposition", "Strength", "Weakness", "Opportunity", "Risk", "Goal"]:
            self._sync_business_node_to_doc(doc, node_id, node_type, node_data, operation)
        elif node_type in ["Competitor", "CompetitorTactic", "SubstituteProduct", "CompetitorStrength", "CompetitorWeakness"]:
            self._sync_competitive_node_to_doc(doc, node_id, node_type, node_data, operation)
        elif node_type in ["CustomerProfile", "ProblemAwarenessStrategy", "BrandAwarenessStrategy", "ConsiderationStrategy", "ConversionStrategy", "LoyaltyStrategy"]:
            self._sync_marketing_node_to_doc(doc, node_id, node_type, node_data, operation)
        elif node_type in ["BrandIdentity", "BrandPersonality", "VoiceAndTone", "ColorPalette", "Typography", "ImageStyle", "MissionAndValues"]:
            self._sync_brand_node_to_doc(doc, node_id, node_type, node_data, operation)
        else:
            raise ValueError(f"Unknown node type: {node_type}")

        # Update document
        doc["updated_at"] = datetime.utcnow()
        self.firestore.update_document_sync(doc_ref, doc)

    def _sync_business_node_to_doc(
        self,
        doc: dict,
        node_id: str,
        node_type: str,
        node_data: dict,
        operation: str
    ) -> None:
        """Sync business strategy node to Firestore document structure."""
        if node_type == "ProductCategory":
            product_portfolio = doc.get("product_portfolio", [])
            if operation == "create":
                category_data = {
                    "category_name": node_data.get("product_name"),
                    "products": [],
                    "value_propositions": []
                }
                product_portfolio.append(category_data)
            elif operation == "update":
                # Find and update existing category
                for category in product_portfolio:
                    if category.get("node_id") == node_id:
                        category.update(node_data)
                        break
            elif operation == "delete":
                product_portfolio = [c for c in product_portfolio if c.get("node_id") != node_id]
            doc["product_portfolio"] = product_portfolio

        elif node_type == "Product":
            # Find parent category and update its products array
            # Implementation...

        # ... handle other business node types

    def _sync_competitive_node_to_doc(self, doc: dict, node_id: str, node_type: str, node_data: dict, operation: str) -> None:
        """Sync competitive strategy node to Firestore document structure."""
        # Implementation for competitive nodes...

    def _sync_marketing_node_to_doc(self, doc: dict, node_id: str, node_type: str, node_data: dict, operation: str) -> None:
        """Sync marketing strategy node to Firestore document structure."""
        # Implementation for marketing nodes...

    def _sync_brand_node_to_doc(self, doc: dict, node_id: str, node_type: str, node_data: dict, operation: str) -> None:
        """Sync brand guidelines node to Firestore document structure."""
        # Implementation for brand nodes...

    async def list_nodes(
        self,
        account_id: str,
        node_type: str,
        parent_node_id: Optional[str] = None
    ) -> List[dict]:
        """
        Generic list operation for any node type.

        Args:
            node_type: "Product", "Competitor", "CustomerProfile", etc.
            parent_node_id: Optional filter by parent relationship
        """
        if parent_node_id:
            # Get relationship type from map
            # Query with parent filter
            query = f"""
            MATCH (parent {{node_id: $parent_node_id}})-[r]->(node:{node_type})
            WHERE (acc:Account {{account_id: $account_id}})-[:BELONGS_TO*]-(node)
            RETURN node
            ORDER BY node.display_name, node.product_name, node.name
            """
        else:
            query = f"""
            MATCH (acc:Account {{account_id: $account_id}})-[:BELONGS_TO*]-(node:{node_type})
            RETURN node
            ORDER BY node.display_name, node.product_name, node.name
            """

        result = await self.neo4j.execute_query(query, {
            "account_id": account_id,
            "parent_node_id": parent_node_id
        })

        return [self._neo4j_node_to_dict(record["node"]) for record in result]

    async def get_node(
        self,
        account_id: str,
        node_id: str,
        node_type: str
    ) -> Optional[dict]:
        """Generic get operation for any node type."""
        query = f"""
        MATCH (node:{node_type} {{node_id: $node_id, account_id: $account_id}})
        RETURN node
        """

        result = await self.neo4j.execute_query(
            query,
            {"node_id": node_id, "account_id": account_id}
        )

        if not result:
            return None

        return self._neo4j_node_to_dict(result[0]["node"])

    # ==================== HELPER METHODS ====================

    async def _validate_account_exists(self, account_id: str) -> bool:
        """Check if account exists in Neo4j."""
        query = "MATCH (acc:Account {account_id: $account_id}) RETURN acc"
        result = await self.neo4j.execute_query(query, {"account_id": account_id})
        return len(result) > 0

    async def _has_dependent_products(self, category_node_id: str) -> bool:
        """Check if category has any products."""
        query = """
        MATCH (cat:ProductCategory {node_id: $node_id})-[:INCLUDES_PRODUCT]->(prod:Product)
        RETURN count(prod) as product_count
        """
        result = await self.neo4j.execute_query(query, {"node_id": category_node_id})
        return result[0]["product_count"] > 0

    def _neo4j_node_to_dict(self, node) -> Dict[str, Any]:
        """Convert Neo4j node to dictionary."""
        # Handle different node object types
        if hasattr(node, "__dict__"):
            return dict(node)
        return dict(node)

    async def _delete_node_neo4j(self, node_id: str) -> None:
        """Delete a node and its relationships from Neo4j."""
        query = """
        MATCH (n {node_id: $node_id})
        DETACH DELETE n
        """
        await self.neo4j.execute_write_operation(query, {"node_id": node_id})


def get_graph_sync_service(
    neo4j: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service)
) -> GraphSyncService:
    """Dependency injection for unified GraphSyncService."""
    return GraphSyncService(neo4j, firestore)
```

### Service Design Highlights

**Key Features of Unified GraphSyncService:**

1. **Generic Operations**: `create_node()`, `update_node()`, `delete_node()`, `list_nodes()`, `get_node()`
   - Work for ANY node type through parameterization
   - Eliminates code duplication

2. **Convenience Wrappers**: Domain-specific methods like `create_product()`, `create_competitor()`
   - Thin wrappers that call generic operations
   - Provide type-safe interfaces with Pydantic models
   - ~10 lines each (just parameter mapping)

3. **Relationship Management**: `_get_relationship_config()` maps all bidirectional relationships
   - Single source of truth for graph structure
   - Easy to extend for new node types

4. **Firestore Routing**: `_sync_node_to_firestore()` routes to strategy-specific sync methods
   - `_sync_business_node_to_doc()` for business nodes
   - `_sync_competitive_node_to_doc()` for competitive nodes
   - `_sync_marketing_node_to_doc()` for marketing nodes
   - `_sync_brand_node_to_doc()` for brand nodes

**Benefits:**
- ✅ Write once, use everywhere (DRY)
- ✅ Consistent behavior across all node types
- ✅ Easy to add new node types (add to maps, no new methods)
- ✅ Centralized error handling and logging
- ✅ Single transaction coordinator

---

## Testing Strategy

### Test Organization

**Unified test files matching unified implementation:**

```
api/tests/
├── unit/
│   └── services/
│       ├── test_graph_sync_service.py          (NEW - Tests all node types)
│       └── test_graph_validation_service.py    (NEW - Tests validation logic)
└── integration/
    └── test_knowledge_graph.py                 (NEW - Tests all endpoints)
```

**Test Organization Within Files:**

Use pytest classes to group tests by node type:

```python
# test_graph_sync_service.py
class TestProductOperations:
    """Tests for Product CRUD operations."""

class TestCompetitorOperations:
    """Tests for Competitor CRUD operations."""

class TestCustomerProfileOperations:
    """Tests for CustomerProfile CRUD operations."""
```

### Unit Test Example

**File:** `api/tests/unit/services/test_graph_sync_service.py`

```python
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from src.kene_api.services.graph_sync_service import GraphSyncService
from src.kene_api.models.graph_models import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCategoryResponse
)


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service."""
    service = AsyncMock()
    service.execute_query = AsyncMock()
    service.execute_write_query = AsyncMock()
    service.execute_write_operation = AsyncMock()
    return service


@pytest.fixture
def mock_firestore_service():
    """Mock Firestore service."""
    service = Mock()
    service.get_document_sync = Mock()
    service.update_document_sync = Mock()
    return service


@pytest.fixture
def graph_sync_service(mock_neo4j_service, mock_firestore_service):
    """Create GraphSyncService with mocked dependencies."""
    return GraphSyncService(mock_neo4j_service, mock_firestore_service)


class TestProductCategoryOperations:
    """Tests for ProductCategory CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_product_category_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service
    ):
        """Test successful product category creation."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category",
            description="Test description"
        )

        # Mock account validation
        mock_neo4j_service.execute_query.return_value = [{"acc": {"account_id": account_id}}]

        # Mock Neo4j create
        expected_node = {
            "node_id": "productcat_test123_abc123",
            "product_name": "Test Category",
            "description": "Test description",
            "account_id": account_id,
            "created_time": datetime.utcnow(),
            "last_modified": datetime.utcnow(),
            "created_by": user_id,
            "last_modified_by": user_id,
            "embedding": None
        }
        mock_neo4j_service.execute_write_query.return_value = [{"cat": expected_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document_sync.return_value = {
            "product_portfolio": []
        }

        # Act
        result = await graph_sync_service.create_product_category(
            account_id, category_create, user_id
        )

        # Assert
        assert result.product_name == "Test Category"
        assert result.description == "Test description"
        assert result.account_id == account_id

        # Verify Neo4j was called
        mock_neo4j_service.execute_write_query.assert_called_once()

        # Verify Firestore was synced
        mock_firestore_service.update_document_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_category_account_not_found(
        self,
        graph_sync_service,
        mock_neo4j_service
    ):
        """Test creation fails when account doesn't exist."""
        # Arrange
        account_id = "acc_nonexistent"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category",
            description="Test description"
        )

        # Mock account validation to return empty
        mock_neo4j_service.execute_query.return_value = []

        # Act & Assert
        with pytest.raises(ValueError, match="Account .* not found"):
            await graph_sync_service.create_product_category(
                account_id, category_create, user_id
            )

    @pytest.mark.asyncio
    async def test_create_product_category_firestore_sync_fails_rolls_back(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service
    ):
        """Test rollback when Firestore sync fails."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        category_create = ProductCategoryCreate(
            product_name="Test Category",
            description="Test description"
        )

        # Mock account validation
        mock_neo4j_service.execute_query.return_value = [{"acc": {"account_id": account_id}}]

        # Mock Neo4j create succeeds
        expected_node = {
            "node_id": "productcat_test123_abc123",
            "product_name": "Test Category",
            "description": "Test description",
            "account_id": account_id
        }
        mock_neo4j_service.execute_write_query.return_value = [{"cat": expected_node}]

        # Mock Firestore sync fails
        mock_firestore_service.get_document_sync.side_effect = Exception("Firestore error")

        # Act & Assert
        with pytest.raises(Exception, match="Firestore sync failed"):
            await graph_sync_service.create_product_category(
                account_id, category_create, user_id
            )

        # Verify rollback was attempted (delete node)
        mock_neo4j_service.execute_write_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_product_category_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service
    ):
        """Test successful product category update."""
        # Arrange
        account_id = "acc_test123"
        node_id = "productcat_test123_abc123"
        user_id = "user_test456"

        updates = ProductCategoryUpdate(
            product_name="Updated Category",
            description="Updated description"
        )

        # Mock existing node
        existing_node = {
            "node_id": node_id,
            "product_name": "Old Category",
            "description": "Old description",
            "account_id": account_id
        }
        mock_neo4j_service.execute_query.return_value = [{"cat": existing_node}]

        # Mock Neo4j update
        updated_node = {**existing_node, **updates.dict(exclude_unset=True)}
        mock_neo4j_service.execute_write_query.return_value = [{"cat": updated_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document_sync.return_value = {
            "product_portfolio": [{
                "category_name": "Old Category",
                "products": []
            }]
        }

        # Act
        result = await graph_sync_service.update_product_category(
            account_id, node_id, updates, user_id
        )

        # Assert
        assert result.product_name == "Updated Category"
        assert result.description == "Updated description"

        # Verify both Neo4j and Firestore were updated
        assert mock_neo4j_service.execute_write_query.call_count >= 1
        mock_firestore_service.update_document_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_product_category_with_products_fails(
        self,
        graph_sync_service,
        mock_neo4j_service
    ):
        """Test deletion fails when category has dependent products."""
        # Arrange
        account_id = "acc_test123"
        node_id = "productcat_test123_abc123"
        user_id = "user_test456"

        # Mock that category has products
        mock_neo4j_service.execute_query.return_value = [{"product_count": 3}]

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot delete ProductCategory with existing products"):
            await graph_sync_service.delete_product_category(
                account_id, node_id, user_id
            )


class TestCompetitorOperations:
    """Tests for Competitor CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_competitor_success(
        self,
        graph_sync_service,
        mock_neo4j_service,
        mock_firestore_service
    ):
        """Test successful competitor creation using same generic service."""
        # Arrange
        account_id = "acc_test123"
        user_id = "user_test456"
        competitor_create = CompetitorCreate(
            name="Acme Corp",
            description="Leading competitor in the space",
            website="https://acme.com"
        )

        # Mock account validation
        mock_neo4j_service.execute_query.return_value = [{"acc": {"account_id": account_id}}]

        # Mock Neo4j create
        expected_node = {
            "node_id": "competitor_test123_xyz789",
            "name": "Acme Corp",
            "description": "Leading competitor in the space",
            "website": "https://acme.com",
            "account_id": account_id
        }
        mock_neo4j_service.execute_write_query.return_value = [{"node": expected_node}]

        # Mock Firestore sync
        mock_firestore_service.get_document_sync.return_value = {"competitors": []}

        # Act
        result = await graph_sync_service.create_competitor(
            account_id, competitor_create, user_id
        )

        # Assert
        assert result.name == "Acme Corp"
        assert result.account_id == account_id

        # Verify same generic operations were used (DRY principle)
        mock_neo4j_service.execute_write_query.assert_called_once()
        mock_firestore_service.update_document_sync.assert_called_once()
```

### Integration Test Example

**File:** `api/tests/integration/test_knowledge_graph.py`

```python
import pytest
from httpx import AsyncClient
from datetime import datetime

from src.kene_api.main import app


@pytest.fixture
async def test_account_id(async_client: AsyncClient, auth_headers: dict):
    """Create a test account for integration tests."""
    # Create account via API
    response = await async_client.post(
        "/api/v1/accounts/",
        json={
            "account_name": "Test Account",
            "industry": "Technology",
            "websites": ["https://example.com"]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    account_id = response.json()["account_id"]

    yield account_id

    # Cleanup
    await async_client.delete(
        f"/api/v1/accounts/{account_id}",
        headers=auth_headers
    )


@pytest.mark.integration
class TestProductCategoryEndpoints:
    """Integration tests for ProductCategory endpoints."""

    async def test_create_list_get_update_delete_product_category_flow(
        self,
        async_client: AsyncClient,
        test_account_id: str,
        auth_headers: dict
    ):
        """Test complete CRUD flow for product category."""

        # Step 1: Create product category
        create_response = await async_client.post(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories",
            json={
                "product_name": "Software Services",
                "description": "Cloud-based software solutions"
            },
            headers=auth_headers
        )
        assert create_response.status_code == 200
        created_category = create_response.json()
        node_id = created_category["node_id"]

        assert created_category["product_name"] == "Software Services"
        assert created_category["account_id"] == test_account_id

        # Step 2: List product categories
        list_response = await async_client.get(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        categories = list_response.json()["products"]
        assert len(categories) == 1
        assert categories[0]["node_id"] == node_id

        # Step 3: Get specific product category
        get_response = await async_client.get(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories/{node_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        fetched_category = get_response.json()
        assert fetched_category["product_name"] == "Software Services"

        # Step 4: Update product category
        update_response = await async_client.patch(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories/{node_id}",
            json={
                "product_name": "Enterprise Software",
                "description": "Enterprise-grade software solutions"
            },
            headers=auth_headers
        )
        assert update_response.status_code == 200
        updated_category = update_response.json()
        assert updated_category["product_name"] == "Enterprise Software"

        # Step 5: Verify Firestore was synced
        # This requires Firestore client access in test
        # firestore_doc = firestore.get_document(f"strategy_docs_{test_account_id}/business_strategy")
        # assert any(cat["category_name"] == "Enterprise Software" for cat in firestore_doc["product_portfolio"])

        # Step 6: Delete product category
        delete_response = await async_client.delete(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories/{node_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200

        # Step 7: Verify deletion
        get_after_delete = await async_client.get(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories/{node_id}",
            headers=auth_headers
        )
        assert get_after_delete.status_code == 404

    async def test_cannot_delete_category_with_products(
        self,
        async_client: AsyncClient,
        test_account_id: str,
        auth_headers: dict
    ):
        """Test that category with products cannot be deleted."""

        # Create category
        category_response = await async_client.post(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories",
            json={
                "product_name": "Software Services",
                "description": "Cloud-based software solutions"
            },
            headers=auth_headers
        )
        category_node_id = category_response.json()["node_id"]

        # Create product in category
        product_response = await async_client.post(
            f"/api/v1/knowledge-graph/{test_account_id}/products",
            json={
                "product_name": "SaaS Platform",
                "description": "Multi-tenant SaaS platform",
                "category_node_id": category_node_id
            },
            headers=auth_headers
        )
        assert product_response.status_code == 200

        # Attempt to delete category
        delete_response = await async_client.delete(
            f"/api/v1/knowledge-graph/{test_account_id}/product-categories/{category_node_id}",
            headers=auth_headers
        )

        # Should fail with 400
        assert delete_response.status_code == 400
        assert "existing products" in delete_response.json()["detail"].lower()
```

### Test Coverage Requirements

**Minimum Coverage:**
- Unit tests: 80% coverage for service layer
- Integration tests: All CRUD endpoints
- Edge cases: Validation failures, rollback scenarios

**Test Scenarios to Cover:**

**For Each Node Type:**
1. Create success
2. Create with invalid data (validation)
3. Create when account doesn't exist
4. Create with Firestore sync failure (rollback)
5. List all nodes
6. List filtered by parent
7. Get specific node
8. Get non-existent node (404)
9. Update success
10. Update non-existent node (404)
11. Update with invalid data
12. Update with Firestore sync failure (rollback)
13. Delete success
14. Delete with dependencies (should fail)
15. Delete non-existent node (404)

---

## Documentation Updates

### Documentation Update Template

For each graph builder review (Steps 2, 4, 6), follow this template:

#### 1. Add Implementation Notes Section

Add after "Executive Summary" and before "Pydantic Model":

```markdown
**Important Implementation Notes:**

1. **Strategy Label**: All [strategy type] nodes receive TWO labels in Neo4j:
   - Their specific node type label (e.g., `[NodeType1]`, `[NodeType2]`)
   - The generic `Strategy` label

   The `Strategy` label enables vector embedding search across all strategic nodes. This dual-labeling is applied automatically by the graph builder.

2. **Bidirectional Relationships**: Key relationships are created bidirectionally:
   - `[Node1] -[:RELATIONSHIP1]-> [Node2]` AND `[Node2] -[:BELONGS_TO]-> [Node1]`
   - [List all bidirectional relationships]

3. **Hub Pattern** (if applicable): [Describe hub-and-spoke pattern]
   - Central hub node: [HubNodeType]
   - Child nodes link via: [List relationships]
```

#### 2. Add Missing Fields to Node Tables

For EVERY node definition table, ensure these fields are present:

```markdown
| name | type | description | example |
| :--- | :--- | :--- | :--- |
| node\_id | string | A unique identifier for the [NodeType]. Generated by the system when the node is created. | `[prefix]_c6051eee55b647ab81a80ffab37295e2` |
| label | string | The node type in neo4j. | `[NodeType]` |
| label | string | The node type in neo4j. The strategy label is used to indicate that the description for this node can be used to create searchable vector embeddings for a strategy search tool. | `Strategy` |
| [node-specific fields] | ... | ... | ... |
| references | list | A list of source URLs or document references that support this [node type]. | `["https://example.com/source"]` |
| created\_time | timestamp | The timestamp when the node was created. | 2025-07-29 22:06:45.928000 UTC |
| last\_modified | timestamp | The timestamp when the node was last modified | 2025-07-29 22:06:45.928000 UTC |
| created\_by | string | Identifies the user who approved the creation of the node, or identifies it as system generated. | `System generated` |
| last\_modified\_by | string | Identifies the user who last modified the node. | `John Doe` |
| embedding | list | Stores the vector embeddings used for search. Initially set to a null value when the node is created. | |
```

#### 3. Verify Relationship Tables

Ensure all relationship tables include bidirectional relationships:

```markdown
**Relationships**
| Label | Relationship | Label | Description |
| :--- | :--- | :--- | :--- |
| [NodeType] | `-[:BELONGS_TO]->` | Account | Each child node of the Account must have the BELONGS\_TO relationship. |
| [NodeType] | `<-[:PARENT_REL]-` | [ParentType] | [Description] (bidirectional relationship for efficient traversal). |
```

---

## Common Patterns

### Pattern 1: Node Creation with Bidirectional Relationships

```python
async def create_node_with_parent(
    node_type: str,
    node_data: dict,
    parent_id: str,
    parent_type: str,
    relationship_to_parent: str,
    relationship_from_parent: str
) -> dict:
    """
    Create a node with bidirectional relationships to parent.

    Example:
        Product -[:BELONGS_TO]-> Account
        Account -[:HAS_PRODUCT]-> Product
    """
    query = f"""
    MATCH (parent:{parent_type} {{node_id: $parent_id}})
    MERGE (node:{node_type}:Strategy {{node_id: $node_id}})
    SET node += $node_data,
        node.created_time = COALESCE(node.created_time, datetime()),
        node.last_modified = datetime()
    MERGE (node)-[:{relationship_to_parent}]->(parent)
    MERGE (parent)-[:{relationship_from_parent}]->(node)
    RETURN node
    """
    # Execute query...
```

### Pattern 2: Validation Before Deletion

```python
async def validate_can_delete(node_id: str, node_type: str) -> tuple[bool, str]:
    """
    Validate that a node can be safely deleted.

    Returns:
        (can_delete: bool, reason: str)
    """
    # Check for dependent nodes
    query = f"""
    MATCH (n:{node_type} {{node_id: $node_id}})-[r]->(dependent)
    WHERE NOT dependent:Account
    RETURN count(dependent) as dependent_count,
           collect(DISTINCT labels(dependent)) as dependent_types
    """
    result = await neo4j.execute_query(query, {"node_id": node_id})

    if result[0]["dependent_count"] > 0:
        types = ", ".join([t[0] for t in result[0]["dependent_types"]])
        return False, f"Cannot delete: node has {result[0]['dependent_count']} dependent nodes of types: {types}"

    return True, ""
```

### Pattern 3: Firestore Document Reconstruction

```python
async def reconstruct_firestore_document(account_id: str, doc_type: str) -> dict:
    """
    Reconstruct complete Firestore document from Neo4j graph.

    Use when Firestore and Neo4j are out of sync.
    """
    if doc_type == "business_strategy":
        # Query Neo4j for all business strategy nodes
        query = """
        MATCH (acc:Account {account_id: $account_id})
        OPTIONAL MATCH (acc)-[:OFFERS_PRODUCTS]->(cat:ProductCategory)
        OPTIONAL MATCH (cat)-[:INCLUDES_PRODUCT]->(prod:Product)
        OPTIONAL MATCH (prod)-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        OPTIONAL MATCH (acc)-[:AFFECTED_BY_ANALYSIS]->(swot:SWOTAnalysis)
        OPTIONAL MATCH (swot)-[:HAS_STRENGTH]->(strength:Strength)
        OPTIONAL MATCH (strength)-[:CREATES]->(opp:Opportunity)
        RETURN acc,
               collect(DISTINCT cat) as categories,
               collect(DISTINCT prod) as products,
               collect(DISTINCT vp) as value_propositions,
               collect(DISTINCT strength) as strengths,
               collect(DISTINCT opp) as opportunities
        """
        result = await neo4j.execute_query(query, {"account_id": account_id})

        # Transform to Firestore document structure
        doc = {
            "company_name": result[0]["acc"]["company_name"],
            "company_overview_summary": result[0]["acc"]["company_overview"],
            "product_portfolio": [],
            "swot_analysis": {
                "strengths_and_opportunities": []
            },
            # ... rest of document
        }

        return doc
```

### Pattern 4: Embedding Generation (Async)

```python
from fastapi import BackgroundTasks

async def trigger_embedding_generation(
    node_id: str,
    background_tasks: BackgroundTasks
):
    """
    Trigger embedding generation for a node (async, non-blocking).
    """
    background_tasks.add_task(generate_and_store_embedding, node_id)


async def generate_and_store_embedding(node_id: str):
    """
    Generate embedding and store in Neo4j (runs in background).
    """
    try:
        # Get node description
        query = """
        MATCH (n:Strategy {node_id: $node_id})
        RETURN n.description as description, labels(n) as labels
        """
        result = await neo4j.execute_query(query, {"node_id": node_id})

        if not result:
            return

        description = result[0]["description"]

        # Generate embedding (using Vertex AI or other service)
        embedding = await embedding_service.generate(description)

        # Store in Neo4j
        update_query = """
        MATCH (n:Strategy {node_id: $node_id})
        SET n.embedding = $embedding
        """
        await neo4j.execute_write_query(
            update_query,
            {"node_id": node_id, "embedding": embedding}
        )

        logger.info(f"Generated embedding for node {node_id}")

    except Exception as e:
        logger.error(f"Failed to generate embedding for {node_id}: {e}")
```

---

## Error Handling

### Error Categories

**1. Validation Errors (400 Bad Request)**
```python
class ValidationError(Exception):
    """Raised when input data fails validation."""
    pass

# Usage
if not account_exists:
    raise ValidationError(f"Account {account_id} not found")
```

**2. Authorization Errors (403 Forbidden)**
```python
# Handled by check_graph_access()
if not user.has_account_access(account_id, ["edit"]):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions"
    )
```

**3. Not Found Errors (404 Not Found)**
```python
node = await service.get_node(node_id)
if not node:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Node {node_id} not found"
    )
```

**4. Conflict Errors (409 Conflict)**
```python
# When deletion would break graph integrity
if has_dependent_nodes:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Cannot delete node with dependent relationships"
    )
```

**5. Sync Errors (500 Internal Server Error)**
```python
try:
    await update_neo4j()
    await update_firestore()
except Exception as e:
    logger.error(f"Sync failed: {e}")
    # Attempt rollback
    await rollback()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to sync changes"
    )
```

### Error Logging

**Log Format:**
```python
logger.error(
    f"[{service_name}] {operation} failed for {resource_type} {resource_id}: {error_message}",
    extra={
        "account_id": account_id,
        "node_id": node_id,
        "user_id": user_id,
        "operation": operation,
        "error": str(e)
    }
)
```

**Example:**
```python
logger.error(
    "[BusinessSyncService] update_product failed for Product prod_123abc: Firestore sync error",
    extra={
        "account_id": "acc_456def",
        "node_id": "prod_123abc",
        "user_id": "user_789ghi",
        "operation": "update",
        "error": "Connection timeout"
    }
)
```

---

## Migration Path

### Phase 1 Completion Checklist

After completing all 7 steps, verify:

- [ ] **Step 1: Unified API Foundation & Business Strategy**
  - [ ] Created `knowledge_graph.py` router with Business Strategy endpoints (9 node types)
  - [ ] Created `graph_sync_service.py` with generic CRUD operations
  - [ ] Created `graph_validation_service.py` with validation logic
  - [ ] Created `graph_models.py` with Business Strategy Pydantic models
  - [ ] Unit tests pass for generic operations (80%+ coverage)
  - [ ] Integration tests pass for Business Strategy CRUD flows
  - [ ] API documentation generated (OpenAPI/Swagger)

- [ ] **Step 2: Competitive Documentation Update**
  - [ ] Implementation Notes added (matching business_requirements.md style)
  - [ ] All nodes have `references` field documented
  - [ ] Bidirectional relationships documented
  - [ ] Matches actual competitive_graph_builder.py implementation

- [ ] **Step 3: Competitive Strategy Endpoints**
  - [ ] Added Competitive Strategy endpoints to `knowledge_graph.py` (8 node types)
  - [ ] Extended `graph_sync_service.py` with competitive-specific helpers
  - [ ] Added Competitive Strategy Pydantic models to `graph_models.py`
  - [ ] Added competitive operation tests to `test_graph_sync_service.py`
  - [ ] Added competitive endpoint tests to `test_knowledge_graph.py`
  - [ ] All tests pass

- [ ] **Step 4: Marketing Documentation Update**
  - [ ] Implementation Notes added
  - [ ] All nodes documented correctly with standard fields
  - [ ] Matches actual marketing_graph_builder.py implementation

- [ ] **Step 5: Marketing Strategy Endpoints**
  - [ ] Added Marketing Strategy endpoints to `knowledge_graph.py` (6 node types)
  - [ ] Extended `graph_sync_service.py` with marketing-specific helpers
  - [ ] Added Marketing Strategy Pydantic models to `graph_models.py`
  - [ ] Added marketing tests to test files
  - [ ] All tests pass

- [ ] **Step 6: Brand Documentation Update**
  - [ ] Implementation Notes added
  - [ ] All 7 nodes documented correctly
  - [ ] Hub pattern documented
  - [ ] Matches actual brand_graph_builder.py implementation

- [ ] **Step 7: Brand Strategy Endpoints**
  - [ ] Added Brand Strategy endpoints to `knowledge_graph.py` (7 node types)
  - [ ] Extended `graph_sync_service.py` with brand-specific helpers
  - [ ] Added Brand Strategy Pydantic models to `graph_models.py`
  - [ ] Added brand tests to test files
  - [ ] All tests pass

**Final Verification:**
- [ ] All 30 node types (9 + 8 + 6 + 7) have functional CRUD endpoints
- [ ] Generic operations work consistently across all node types
- [ ] Neo4j + Firestore stay in sync for all operations
- [ ] Rollback works correctly on sync failures
- [ ] Test coverage ≥ 80% for service layer
- [ ] All integration tests pass
- [ ] `make lint` passes
- [ ] OpenAPI documentation is complete and accurate

### Verification Commands

**Run All Tests:**
```bash
cd api
pytest tests/unit/services/test_graph_sync_service.py -v
pytest tests/unit/services/test_graph_validation_service.py -v
pytest tests/integration/test_knowledge_graph.py -v
```

**Check Test Coverage:**
```bash
cd api
pytest --cov=src/kene_api/services --cov-report=html
```

**Lint and Type Check:**
```bash
cd api
make lint  # Runs ruff, mypy, codespell
```

**Generate API Documentation:**
```bash
cd api
uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
# Visit http://localhost:8000/docs
```

---

## Graph Builder Integration Strategy

### Decision: Keep Agent Direct Writes (Do NOT Modify Graph Builders)

**IMPORTANT: The graph builders in `app/adk/agents/strategy_agent/` will NOT be modified to use API endpoints.**

#### Rationale

**1. Performance Optimization**
- **Direct writes**: ~50-100ms for entire graph
- **Via API**: ~200-500ms per node × 30-50 nodes = 6-25 seconds of added latency
- Agents generate complex graphs with many interconnected nodes - HTTP overhead is unacceptable

**2. Bulk Operations & Transaction Atomicity**
- Graph builders create entire strategy graphs in **single Neo4j transactions**
- Example: Business strategy creates 9 ProductCategories + 45 Products + 90 ValuePropositions in one atomic operation
- API approach would require 144 separate HTTP requests, losing transaction atomicity
- Partial failures would be difficult to rollback across HTTP boundary

**3. Different Use Cases Require Different Approaches**

| Aspect | Graph Builders (Agents) | API Endpoints (Users) |
|--------|------------------------|---------------------|
| **Purpose** | Bulk strategy generation | Individual node edits |
| **Frequency** | Once per account creation | Multiple times per day |
| **Volume** | 30-50 nodes at once | 1 node at a time |
| **Transaction** | Single atomic operation | Individual operations |
| **Caller** | Internal (Agent system) | External (Frontend) |
| **Validation** | Schema validation (Pydantic) | Schema + business rules |

**4. Architectural Simplicity**
- Agents run in same infrastructure as database (Cloud Run, Agent Engine)
- They already have direct database credentials and access
- Adding HTTP layer introduces:
  - Network failures
  - Serialization overhead
  - Additional error modes (timeouts, connection issues)
  - Unnecessary complexity

**5. Code Reuse Through Shared Services**
- BOTH paths should share common logic (validation, embedding generation)
- But execution path should differ (direct DB vs HTTP API)

#### Two-Path Architecture

```
┌────────────────────────────────────────────────────────────┐
│  PATH 1: Bulk Creation (Agents) - UNCHANGED                │
│  ────────────────────────────────────────────              │
│                                                             │
│  Agent System (app/)                                        │
│       ↓                                                     │
│  GraphBuilder (business_graph_builder.py)                  │
│       ↓                                                     │
│  Neo4jOperations (direct write)                            │
│       ↓                                                     │
│  Neo4j + Firestore (parallel writes)                       │
│                                                             │
│  ✓ Used during: Strategy generation                        │
│  ✓ Creates: 30-50 nodes per strategy                       │
│  ✓ Speed: ~100ms for entire graph                          │
│  ✓ Transaction: Single atomic operation                    │
│                                                             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  PATH 2: Individual Edits (Users) - NEW IN PHASE 1         │
│  ────────────────────────────────────────────              │
│                                                             │
│  Frontend (React)                                           │
│       ↓                                                     │
│  REST API (FastAPI routers)                                │
│       ↓                                                     │
│  SyncService (validation + dual write)                     │
│       ↓                                                     │
│  Neo4j + Firestore (atomic with rollback)                  │
│                                                             │
│  ✓ Used during: User editing in UI                         │
│  ✓ Creates: 1 node at a time                               │
│  ✓ Speed: ~200-300ms per operation                         │
│  ✓ Features: Validation, auth, rollback                    │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

#### Shared Components (DRY Principle)

While keeping separate execution paths, share common logic:

**Shared Validation Service** (Optional Enhancement - Post Phase 1):

```python
# api/src/kene_api/services/graph_validation_service.py

class GraphValidationService:
    """Validation logic shared by graph builders and API endpoints."""

    def validate_product_data(self, product_data: dict) -> ValidationResult:
        """
        Validate product node data structure.

        Can be used by:
        - API endpoints (enforced - raises exception)
        - Graph builders (optional - logs warnings)
        """
        errors = []

        # Check required fields
        if not product_data.get("product_name"):
            errors.append("product_name is required")

        # Validate field lengths
        if len(product_data.get("product_name", "")) > 200:
            errors.append("product_name must be ≤200 characters")

        # Check description
        if not product_data.get("description"):
            errors.append("description is required")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )

    def validate_relationships(
        self,
        node_type: str,
        parent_node_id: str,
        parent_node_type: str
    ) -> ValidationResult:
        """Validate that parent node exists and relationship is valid."""
        # Implementation...


# Usage in API endpoint (enforced)
validation_result = validation_service.validate_product_data(product_data)
if not validation_result.valid:
    raise HTTPException(400, detail=validation_result.errors)


# Usage in graph builder (optional warnings)
validation_result = validation_service.validate_product_data(product_data)
if not validation_result.valid:
    logger.warning(f"Product validation issues: {validation_result.errors}")
    # Continue anyway - agents know what they're doing
```

**Shared Embedding Service:**

```python
# Already exists, both paths can use it
from ..services.embedding_service import generate_embeddings_for_node

# In graph builder
await generate_embeddings_for_node(node_id)

# In API endpoint (background task)
background_tasks.add_task(generate_embeddings_for_node, node_id)
```

#### Why This Approach is Correct

**Benefits of Dual-Path:**
1. ✅ **Performance**: Agents stay fast with direct writes
2. ✅ **User Experience**: API provides validation, auth, rollback for UI
3. ✅ **Flexibility**: Each path optimized for its use case
4. ✅ **Maintainability**: Clear separation of concerns
5. ✅ **Simplicity**: No unnecessary HTTP layer in agent system

**Anti-Pattern to Avoid:**
```python
# ❌ DON'T DO THIS in graph builder
async def build_strategy_graph(strategy, account_id):
    # Bad: Making 50 HTTP calls from agent
    for product in strategy.products:
        await http_client.post(f"{api_url}/products", json=product)
    # This is slow, fragile, and unnecessary
```

**Correct Pattern:**
```python
# ✅ DO THIS in graph builder (current implementation)
def build_strategy_graph(self, strategy, account_id):
    # Good: Direct database write in single transaction
    with self.neo4j_ops.connection.session() as session:
        with session.begin_transaction() as tx:
            # Create all nodes and relationships
            for category in strategy.product_portfolio:
                self._create_product_category(category, tx)
                for product in category.products:
                    self._create_product(product, tx)
            tx.commit()

    # Sync to Firestore (single document write)
    self.firestore_client.save_strategy_document(account_id, strategy_dict)
```

#### When to Revisit This Decision

Consider migrating graph builders to use API endpoints ONLY if:

1. ❌ **Agents move to separate infrastructure** (different VPC, no direct DB access)
2. ❌ **Strict microservices architecture** is required (service isolation)
3. ❌ **Performance testing shows API is fast enough** (< 200ms for full graph via bulk endpoint)
4. ❌ **API provides significant value-add** that graph builders need (advanced validation, audit trails)

**Current status**: None of these conditions apply. Keep current architecture.

#### Summary

- **Graph Builders**: Keep direct Neo4j writes (unchanged)
- **API Endpoints**: New endpoints for user edits (Phase 1)
- **Both Paths**: Maintain Neo4j + Firestore sync
- **Shared Services**: Validation and embeddings (optional enhancement)

**No changes to `app/adk/agents/strategy_agent/*_graph_builder.py` files are needed in Phase 1.**

---

## Next Steps (Phase 2)

Once Phase 1 is complete, Phase 2 will implement frontend:

1. **Frontend Components** for editing nodes
2. **Real-time Updates** using WebSocket or polling
3. **Graph Visualization** for relationship editing
4. **Batch Operations** for bulk updates
5. **Firestore Deprecation** (migrate fully to Neo4j)

---

## Appendix: File Structure After Phase 1

**Unified architecture for simplicity and maintainability:**

```
api/src/kene_api/
├── routers/
│   ├── knowledge_graph.py              (NEW - unified router for ALL strategies, ~1000 lines)
│   └── strategy.py                     (EXISTING - document-level operations)
├── services/
│   ├── graph_sync_service.py           (NEW - unified sync for ALL node types, ~800 lines)
│   └── graph_validation_service.py     (NEW - shared validation logic, ~300 lines)
├── models/
│   └── graph_models.py                 (NEW - all Pydantic models, ~600 lines)
├── database.py                         (EXISTING)
└── firestore.py                        (EXISTING)

api/tests/
├── unit/
│   └── services/
│       ├── test_graph_sync_service.py          (NEW - tests all node types, ~800 lines)
│       └── test_graph_validation_service.py    (NEW - tests validation, ~300 lines)
└── integration/
    └── test_knowledge_graph.py                 (NEW - tests all endpoints, ~1000 lines)

knowledge_graph/
├── business_requirements.md            (UPDATED - Step 0, completed)
├── competitor_requirements.md          (UPDATED - Step 2)
├── marketing_requirements.md           (UPDATED - Step 4)
├── brand_requirements.md               (UPDATED - Step 6)
└── PHASE1_IMPLEMENTATION_PLAN.md       (THIS FILE)
```

**File Count Comparison:**

| Architecture | Router Files | Service Files | Test Files | Total |
|--------------|-------------|---------------|------------|-------|
| **Separate** | 4 | 4 | 8 | 16 files |
| **Unified** | 1 | 2 | 3 | 6 files |

**Lines of Code Comparison:**

| Architecture | Router LOC | Service LOC | Test LOC | Total LOC |
|--------------|-----------|-------------|----------|-----------|
| **Separate** | 4×250 = 1000 | 4×200 = 800 | 8×200 = 1600 | 3400 LOC |
| **Unified** | 1×1000 = 1000 | 1×800 + 1×300 = 1100 | 1×800 + 1×300 + 1×1000 = 2100 | 4200 LOC |

**Note**: Unified approach has slightly more LOC due to comprehensive generic methods, but:
- ✅ Zero code duplication (DRY)
- ✅ Easier to maintain (single source of truth)
- ✅ Consistent behavior (same logic for all node types)
- ✅ Better organized (clear section headers)

**File Organization Within `knowledge_graph.py`:**

```python
# ==================== IMPORTS & SETUP ====================
# (lines 1-50)

# ==================== AUTH HELPERS ====================
# (lines 51-100)

# ==================== BUSINESS STRATEGY ENDPOINTS ====================
# ProductCategory: POST, GET list, GET by ID, PATCH, DELETE
# Product: POST, GET list, GET by ID, PATCH, DELETE
# ValueProposition: POST, GET list, GET by ID, PATCH, DELETE
# Strength: POST, GET list, GET by ID, PATCH, DELETE
# Weakness: POST, GET list, GET by ID, PATCH, DELETE
# Opportunity: POST, GET list, GET by ID, PATCH, DELETE
# Risk: POST, GET list, GET by ID, PATCH, DELETE
# Goal: POST, GET list, GET by ID, PATCH, DELETE
# (lines 101-500)

# ==================== COMPETITIVE STRATEGY ENDPOINTS ====================
# Competitor: POST, GET list, GET by ID, PATCH, DELETE
# CompetitorTactic: POST, GET list, GET by ID, PATCH, DELETE
# SubstituteProduct: POST, GET list, GET by ID, PATCH, DELETE
# (lines 501-700)

# ==================== MARKETING STRATEGY ENDPOINTS ====================
# CustomerProfile: POST, GET list, GET by ID, PATCH, DELETE
# Marketing Strategies: GET by ID, PATCH (created with profile)
# (lines 701-850)

# ==================== BRAND GUIDELINES ENDPOINTS ====================
# BrandIdentity: GET, PATCH
# Brand Components: GET, PATCH
# (lines 851-950)

# ==================== AGGREGATED VIEWS ====================
# GET /business-strategy - complete graph
# GET /competitive-strategy - complete graph
# GET /marketing-strategy - complete graph
# GET /brand-guidelines - complete graph
# (lines 951-1000)
```

---

## Summary

This implementation plan provides:

1. ✅ **Comprehensive Architecture** - Clear separation between Neo4j (primary) and Firestore (sync)
2. ✅ **Unified Code Organization** - Single router and service eliminate duplication (DRY principle)
3. ✅ **Detailed Implementation Steps** - 7 concrete steps with file paths and code examples
4. ✅ **Generic CRUD Operations** - Parameterized methods work for all 30 node types
5. ✅ **Robust Error Handling** - Atomic operations with rollback on failure
6. ✅ **Extensive Testing** - Unit + integration tests with 80%+ coverage
7. ✅ **CLAUDE.md Compliance** - Follows all best practices (especially C-4, C-9: simplicity and DRY)
8. ✅ **Documentation Standards** - Consistent documentation format across all strategies
9. ✅ **Migration Path** - Clear verification checklist
10. ✅ **Two-Path Strategy** - Graph builders keep direct writes, API for user edits

### Why This Plan is Optimal

**Unified vs Separate Files:**

| Aspect | This Plan (Unified) | Alternative (Separate) |
|--------|---------------------|----------------------|
| **Files to Create** | 6 files | 16 files |
| **Code Duplication** | Zero (generic operations) | High (4× boilerplate) |
| **Maintenance** | Fix bugs once | Fix in 4 places |
| **CLAUDE.md C-9** | ✅ Compliant | ❌ Violates (extracts without reuse) |
| **Consistency** | ✅ Enforced | ⚠️ Risk of divergence |
| **Similar to Existing** | ✅ Matches `strategy.py` | ❌ New pattern |
| **Lines of Code** | ~4200 (no duplication) | ~3400 (with duplication) |

**Development can begin immediately following this plan.**

---

## Questions or Clarifications

For questions during implementation, refer to:
- `CLAUDE.md` - Best practices
- `knowledge_graph/business_requirements.md` - Reference implementation
- `app/adk/agents/strategy_agent/*_graph_builder.py` - Actual graph operations
- `api/src/kene_api/routers/strategy.py` - Auth patterns
- `api/src/kene_api/routers/products.py` - CRUD patterns

**End of Phase 1 Implementation Plan**
