# Router Refactoring Implementation Plan

**Issue:** #3 - Reduce duplication in knowledge_graph.py router
**Status:** In Progress
**Created:** 2025-01-17
**Estimated Duration:** 5-7 days

---

## Executive Summary

**Goal:** Reduce the 5,476-line `knowledge_graph.py` router to ~2,720 lines through generic base class + inheritance pattern, while maintaining 100% API compatibility.

**Approach:** Generic CRUD functions + domain-based router split + explicit handling of special cases

**Timeline:** 5-7 days (big-bang replacement on feature branch)

**Risk Level:** Medium (functional code works; refactoring introduces risk but manageable with existing tests)

---

## Current State Analysis

### Router Statistics
- **5,476 lines** of code
- **28 node types** across 4 strategy domains
- **133 endpoints** total
- **~98% code duplication** - only node type names and models vary

### Node Types by Domain

**Business Strategy (9 types):**
- ProductCategory, Product, ValueProposition
- Strength, Weakness, Opportunity, Risk
- Goal, SWOTAnalysis

**Competitive Strategy (6 types):**
- Competitor, CompetitorTactic, CompetitorStrength, CompetitorWeakness
- SubstituteProduct, CompetitiveEnvironment

**Marketing Strategy (6 types):**
- CustomerProfile, ProblemAwarenessStrategy, BrandAwarenessStrategy
- ConsiderationStrategy, ConversionStrategy, LoyaltyStrategy

**Brand Strategy (7 types):**
- BrandPersonality, VoiceAndTone, ColorPalette, Typography
- ImageStyle, MissionAndValues, BrandIdentity

### Repetitive Patterns Identified

1. **Standard CRUD Pattern** (~22 node types):
   - CREATE: POST `/{account_id}/{node_type_plural}`
   - LIST: GET `/{account_id}/{node_type_plural}` with pagination
   - GET: GET `/{account_id}/{node_type_plural}/{node_id}`
   - UPDATE: PATCH `/{account_id}/{node_type_plural}/{node_id}`
   - DELETE: DELETE `/{account_id}/{node_type_plural}/{node_id}`

2. **Error Handling** (100% identical across all endpoints):
   - ValidationException → 400
   - DuplicateNodeException → 409
   - NodeNotFoundException → 404
   - NodeHasDependenciesException → 400
   - GraphSyncException → 500
   - Generic Exception → 500

3. **Dependencies** (100% identical):
   - `service: GraphSyncService = Depends(get_graph_sync_service)`
   - `user: UserContext = Depends(get_current_user)`

4. **Authorization** (100% identical):
   - Mutating operations: `check_graph_access(account_id, user, "edit")`
   - Read operations: `check_graph_access(account_id, user, "view")`

### Special Cases (6 node types)

1. **Product**: Optimized list query with category filtering
2. **ValueProposition**: Parent filtering in list
3. **Opportunity**: Parent filtering + relationship fetch
4. **Risk**: Parent filtering + relationship fetch
5. **CompetitiveEnvironment**: Hub node (GET + UPDATE only, no CREATE/DELETE/LIST)
6. **BrandIdentity**: Hub node (GET + UPDATE only)

---

## Design Decisions

### Configuration Location
**Decision:** Add to `/api/src/kene_api/constants.py`

**Rationale:**
- Current pattern: Configuration centralized in `constants.py`
- Already contains `VALID_NODE_TYPES` and `NODE_TYPE_TO_PREFIX`
- Imported by services that need node type metadata
- Consistent with existing codebase patterns

### Router Organization
**Decision:** Split into domain-based sub-routers

**Structure:**
```
api/src/kene_api/routers/knowledge_graph/
├── __init__.py          # Main router that includes sub-routers
├── crud_factory.py      # Generic CRUD endpoint implementations
├── business.py          # Business strategy endpoints (~450 lines)
├── competitive.py       # Competitive strategy endpoints (~450 lines)
├── marketing.py         # Marketing strategy endpoints (~450 lines)
├── brand.py             # Brand strategy endpoints (~550 lines)
└── aggregated.py        # Aggregated view endpoints (~400 lines)
```

**Rationale:**
- Current file is 5,476 lines (2x larger than next largest router)
- Existing pattern: Domain-based separation (e.g., `strategy.py`, `monitoring_topics.py`)
- Target ~400-550 lines per file (similar to other routers)
- Easier navigation and maintenance

### Models Organization
**Decision:** Keep single file `models/graph_models.py`

**Rationale:**
- Models are passive data structures (no complex logic)
- Better IDE autocomplete with single file
- Easier imports
- File size not causing maintenance issues

### Services Organization
**Decision:** Keep `services/graph_sync_service.py` as-is

**Rationale:**
- Already well-designed with generic + specialized methods
- No need to split or refactor
- Supports refactoring goals

### Aggregated Views
**Decision:** Extract to separate `aggregated.py` router

**Rationale:**
- Different concern (read-only views vs CRUD operations)
- Currently scattered throughout file
- ~400 lines → manageable separate file
- Easier to find "get full strategy" endpoints

---

## Phase 1: Setup & Configuration

### Duration
Day 1 - 4 hours

### Tasks

#### 1.1 Create Feature Branch
```bash
git checkout -b feature/router-refactoring
```

#### 1.2 Extend Constants Configuration

**File:** `/api/src/kene_api/constants.py`

**Add comprehensive node type configuration:**

```python
from typing import TypedDict, Literal

class NodeTypeConfig(TypedDict):
    """Configuration for a knowledge graph node type."""
    neo4j_label: str                          # "Product", "Competitor", etc.
    url_path: str                             # "products", "competitors", etc.
    firestore_doc_type: Literal[              # Which Firestore strategy doc
        "business_strategy",
        "competitive_strategy",
        "marketing_strategy",
        "brand_strategy"
    ]
    prefix: str                               # "prod", "competitor", etc.
    max_per_account: int | None               # Resource limit (None = unlimited)
    list_field_name: str                      # "products", "competitors" (for list responses)
    human_readable: str                       # "product", "competitor" (for errors)
    has_parent_filter: bool                   # Whether list supports parent filtering
    parent_filter_param: str | None           # "category_node_id", "strength_node_id", etc.
    is_hub_node: bool                         # Special nodes like CompetitiveEnvironment

# Define all 28 node types
NODE_TYPE_REGISTRY: dict[str, NodeTypeConfig] = {
    # Business Strategy (9 types)
    "ProductCategory": {
        "neo4j_label": "ProductCategory",
        "url_path": "product-categories",
        "firestore_doc_type": "business_strategy",
        "prefix": "productcat",
        "max_per_account": None,
        "list_field_name": "categories",
        "human_readable": "product category",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Product": {
        "neo4j_label": "Product",
        "url_path": "products",
        "firestore_doc_type": "business_strategy",
        "prefix": "prod",
        "max_per_account": None,
        "list_field_name": "products",
        "human_readable": "product",
        "has_parent_filter": True,
        "parent_filter_param": "category_node_id",
        "is_hub_node": False,
    },
    "ValueProposition": {
        "neo4j_label": "ValueProposition",
        "url_path": "value-propositions",
        "firestore_doc_type": "business_strategy",
        "prefix": "valueprop",
        "max_per_account": None,
        "list_field_name": "value_propositions",
        "human_readable": "value proposition",
        "has_parent_filter": True,
        "parent_filter_param": "parent_node_id",
        "is_hub_node": False,
    },
    "Strength": {
        "neo4j_label": "Strength",
        "url_path": "strengths",
        "firestore_doc_type": "business_strategy",
        "prefix": "strength",
        "max_per_account": None,
        "list_field_name": "strengths",
        "human_readable": "strength",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Weakness": {
        "neo4j_label": "Weakness",
        "url_path": "weaknesses",
        "firestore_doc_type": "business_strategy",
        "prefix": "weakness",
        "max_per_account": None,
        "list_field_name": "weaknesses",
        "human_readable": "weakness",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Opportunity": {
        "neo4j_label": "Opportunity",
        "url_path": "opportunities",
        "firestore_doc_type": "business_strategy",
        "prefix": "opportunity",
        "max_per_account": None,
        "list_field_name": "opportunities",
        "human_readable": "opportunity",
        "has_parent_filter": True,
        "parent_filter_param": "strength_node_id",
        "is_hub_node": False,
    },
    "Risk": {
        "neo4j_label": "Risk",
        "url_path": "risks",
        "firestore_doc_type": "business_strategy",
        "prefix": "risk",
        "max_per_account": None,
        "list_field_name": "risks",
        "human_readable": "risk",
        "has_parent_filter": True,
        "parent_filter_param": "weakness_node_id",
        "is_hub_node": False,
    },
    "Goal": {
        "neo4j_label": "Goal",
        "url_path": "goals",
        "firestore_doc_type": "business_strategy",
        "prefix": "goal",
        "max_per_account": None,
        "list_field_name": "goals",
        "human_readable": "goal",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "SWOTAnalysis": {
        "neo4j_label": "SWOTAnalysis",
        "url_path": "swot-analysis",
        "firestore_doc_type": "business_strategy",
        "prefix": "swot",
        "max_per_account": 1,
        "list_field_name": "swot_analysis",
        "human_readable": "SWOT analysis",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },

    # Competitive Strategy (6 types)
    "Competitor": {
        "neo4j_label": "Competitor",
        "url_path": "competitors",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "competitor",
        "max_per_account": 5,
        "list_field_name": "competitors",
        "human_readable": "competitor",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "CompetitorTactic": {
        "neo4j_label": "CompetitorTactic",
        "url_path": "competitor-tactics",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "comptactic",
        "max_per_account": None,
        "list_field_name": "competitor_tactics",
        "human_readable": "competitor tactic",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "CompetitorStrength": {
        "neo4j_label": "CompetitorStrength",
        "url_path": "competitor-strengths",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "compstrength",
        "max_per_account": None,
        "list_field_name": "competitor_strengths",
        "human_readable": "competitor strength",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "CompetitorWeakness": {
        "neo4j_label": "CompetitorWeakness",
        "url_path": "competitor-weaknesses",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "compweakness",
        "max_per_account": None,
        "list_field_name": "competitor_weaknesses",
        "human_readable": "competitor weakness",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "SubstituteProduct": {
        "neo4j_label": "SubstituteProduct",
        "url_path": "substitute-products",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "substitute",
        "max_per_account": None,
        "list_field_name": "substitute_products",
        "human_readable": "substitute product",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "CompetitiveEnvironment": {
        "neo4j_label": "CompetitiveEnvironment",
        "url_path": "competitive-environment",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "compenv",
        "max_per_account": 1,
        "list_field_name": "competitive_environment",
        "human_readable": "competitive environment",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },

    # Marketing Strategy (6 types)
    "CustomerProfile": {
        "neo4j_label": "CustomerProfile",
        "url_path": "customer-profiles",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "custprof",
        "max_per_account": None,
        "list_field_name": "customer_profiles",
        "human_readable": "customer profile",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ProblemAwarenessStrategy": {
        "neo4j_label": "ProblemAwarenessStrategy",
        "url_path": "problem-awareness-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "probaware",
        "max_per_account": None,
        "list_field_name": "problem_awareness_strategies",
        "human_readable": "problem awareness strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "BrandAwarenessStrategy": {
        "neo4j_label": "BrandAwarenessStrategy",
        "url_path": "brand-awareness-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "brandaware",
        "max_per_account": None,
        "list_field_name": "brand_awareness_strategies",
        "human_readable": "brand awareness strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "ConsiderationStrategy": {
        "neo4j_label": "ConsiderationStrategy",
        "url_path": "consideration-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "consider",
        "max_per_account": None,
        "list_field_name": "consideration_strategies",
        "human_readable": "consideration strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "ConversionStrategy": {
        "neo4j_label": "ConversionStrategy",
        "url_path": "conversion-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "convert",
        "max_per_account": None,
        "list_field_name": "conversion_strategies",
        "human_readable": "conversion strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "LoyaltyStrategy": {
        "neo4j_label": "LoyaltyStrategy",
        "url_path": "loyalty-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "loyalty",
        "max_per_account": None,
        "list_field_name": "loyalty_strategies",
        "human_readable": "loyalty strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },

    # Brand Strategy (7 types)
    "BrandPersonality": {
        "neo4j_label": "BrandPersonality",
        "url_path": "brand-personalities",
        "firestore_doc_type": "brand_strategy",
        "prefix": "brandpers",
        "max_per_account": None,
        "list_field_name": "brand_personalities",
        "human_readable": "brand personality",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "VoiceAndTone": {
        "neo4j_label": "VoiceAndTone",
        "url_path": "voice-and-tone",
        "firestore_doc_type": "brand_strategy",
        "prefix": "voicetone",
        "max_per_account": None,
        "list_field_name": "voice_and_tone",
        "human_readable": "voice and tone",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ColorPalette": {
        "neo4j_label": "ColorPalette",
        "url_path": "color-palettes",
        "firestore_doc_type": "brand_strategy",
        "prefix": "colorpal",
        "max_per_account": None,
        "list_field_name": "color_palettes",
        "human_readable": "color palette",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Typography": {
        "neo4j_label": "Typography",
        "url_path": "typography",
        "firestore_doc_type": "brand_strategy",
        "prefix": "typo",
        "max_per_account": None,
        "list_field_name": "typography",
        "human_readable": "typography",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ImageStyle": {
        "neo4j_label": "ImageStyle",
        "url_path": "image-styles",
        "firestore_doc_type": "brand_strategy",
        "prefix": "imgstyle",
        "max_per_account": None,
        "list_field_name": "image_styles",
        "human_readable": "image style",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "MissionAndValues": {
        "neo4j_label": "MissionAndValues",
        "url_path": "mission-and-values",
        "firestore_doc_type": "brand_strategy",
        "prefix": "mission",
        "max_per_account": None,
        "list_field_name": "mission_and_values",
        "human_readable": "mission and values",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "BrandIdentity": {
        "neo4j_label": "BrandIdentity",
        "url_path": "brand-identity",
        "firestore_doc_type": "brand_strategy",
        "prefix": "brandid",
        "max_per_account": 1,
        "list_field_name": "brand_identity",
        "human_readable": "brand identity",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },
}
```

#### 1.3 Testing
- Add unit test to verify all 28 types are registered
- Validate config structure

**Checklist:**
- [ ] Create feature branch
- [ ] Add `NODE_TYPE_REGISTRY` to constants.py
- [ ] Write unit tests for configuration
- [ ] All tests pass

---

## Phase 2: Create Generic CRUD Utilities

### Duration
Day 1-2 - 8 hours

### Tasks

#### 2.1 Create Router Directory Structure
```bash
mkdir -p api/src/kene_api/routers/knowledge_graph
```

#### 2.2 Create CRUD Factory Module

**New file:** `/api/src/kene_api/routers/knowledge_graph/crud_factory.py`

This module provides generic CRUD endpoint implementations that will be called by specific endpoint functions.

```python
"""Generic CRUD endpoint implementations for knowledge graph nodes.

Provides reusable endpoint logic following the Generic Base Class + Inheritance pattern.
"""

import logging
from typing import Any, Callable, TypeVar

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...constants import NODE_TYPE_REGISTRY
from ...exceptions import (
    DuplicateNodeException,
    GraphSyncException,
    NodeHasDependenciesException,
    NodeNotFoundException,
    ValidationException,
)
from ...models.graph_models import DeleteResponse
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service

logger = logging.getLogger(__name__)

# Type variables for generic typing
CreateModel = TypeVar("CreateModel", bound=BaseModel)
UpdateModel = TypeVar("UpdateModel", bound=BaseModel)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
ListResponseModel = TypeVar("ListResponseModel", bound=BaseModel)


async def check_graph_access(
    account_id: str,
    user: UserContext,
    required_level: str = "view",
) -> UserContext:
    """Check if user has required access level for graph operations.

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

    # Check if user has org admin/owner access (grants access to ALL accounts)
    has_org_admin = any(
        role in ["admin", "owner"] for role in user.organization_permissions.values()
    )
    if has_org_admin:
        logger.info(
            f"[check_graph_access] Access granted via org admin for user {user.email}"
        )
        return user

    # For non-admin users, check account-specific permissions
    if required_level == "edit":
        # Edit requires explicit "edit" role
        if not user.has_account_access(account_id, ["edit"]):
            logger.warning(
                f"[check_graph_access] Edit access denied for user {user.email} to account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for edit access to account {account_id}",
            )
    else:
        # View access: just check if account is accessible
        if not user.has_account_access(account_id) and not user.is_super_admin:
            logger.warning(
                f"[check_graph_access] View access denied for user {user.email} to account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied to account {account_id}",
            )

    logger.info(
        f"[check_graph_access] Access granted for user {user.email} to account {account_id}"
    )
    return user


class CRUDEndpoints:
    """Generic CRUD endpoint implementations for knowledge graph nodes."""

    @staticmethod
    async def create_node(
        account_id: str,
        node_type: str,
        create_data: CreateModel,
        response_model_class: type[ResponseModel],
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic CREATE endpoint implementation.

        Args:
            account_id: Account identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            create_data: Pydantic create model instance
            response_model_class: Response model class for instantiation
            service_method: Service method to call (e.g., service.create_goal)
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model instance

        Raises:
            HTTPException: With appropriate status codes
        """
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            result = await service_method(account_id, create_data, user.user_id)
            return response_model_class(**result)
        except ValidationException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except DuplicateNodeException as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error creating {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create {config['human_readable']}",
            ) from e

    @staticmethod
    async def list_nodes(
        account_id: str,
        node_type: str,
        response_model_class: type[ResponseModel],
        list_response_class: type[ListResponseModel],
        skip: int,
        limit: int | None,
        service: GraphSyncService,
        user: UserContext,
        parent_filter_id: str | None = None,
        parent_node_type: str | None = None,
    ) -> ListResponseModel:
        """Generic LIST endpoint implementation.

        Handles pagination and optional parent filtering.
        """
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            # Get total count
            total_count = await service.count_nodes(
                account_id,
                config["neo4j_label"],
                parent_node_id=parent_filter_id,
                parent_node_type=parent_node_type,
            )

            # Get paginated results
            nodes_data = await service.list_nodes(
                account_id,
                config["neo4j_label"],
                skip=skip,
                limit=limit,
                parent_node_id=parent_filter_id,
                parent_node_type=parent_node_type,
            )

            nodes = [response_model_class(**node) for node in nodes_data]

            # Construct list response dynamically
            return list_response_class(
                **{config["list_field_name"]: nodes, "total_count": total_count}
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to list {config['list_field_name']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list {config['list_field_name']}",
            ) from e

    @staticmethod
    async def get_node(
        account_id: str,
        node_id: str,
        node_type: str,
        response_model_class: type[ResponseModel],
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic GET endpoint implementation."""
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            node = await service.get_node(account_id, node_id, config["neo4j_label"])
            if not node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{config['human_readable'].capitalize()} not found",
                )
            return response_model_class(**node)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to get {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get {config['human_readable']}",
            ) from e

    @staticmethod
    async def update_node(
        account_id: str,
        node_id: str,
        node_type: str,
        update_data: UpdateModel,
        response_model_class: type[ResponseModel],
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Generic UPDATE endpoint implementation."""
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            result = await service_method(account_id, node_id, update_data, user.user_id)
            return response_model_class(**result)
        except ValidationException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except DuplicateNodeException as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error updating {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update {config['human_readable']}",
            ) from e

    @staticmethod
    async def delete_node(
        account_id: str,
        node_id: str,
        node_type: str,
        service_method: Callable,
        service: GraphSyncService,
        user: UserContext,
    ) -> DeleteResponse:
        """Generic DELETE endpoint implementation."""
        await check_graph_access(account_id, user, "edit")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            await service_method(account_id, node_id, user.user_id)
            return DeleteResponse(
                success=True,
                message=f"{config['human_readable'].capitalize()} {node_id} deleted successfully",
                deleted_node_id=node_id,
            )
        except NodeHasDependenciesException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        except NodeNotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        except GraphSyncException as e:
            logger.error(f"Graph sync error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            ) from e
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error deleting {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete {config['human_readable']}",
            ) from e

    @staticmethod
    async def get_node_with_relationship(
        account_id: str,
        node_id: str,
        node_type: str,
        relationship_query: str,
        relationship_field: str,
        response_model_class: type[ResponseModel],
        service: GraphSyncService,
        user: UserContext,
    ) -> ResponseModel:
        """Get node and populate a field from a relationship query.

        Used by Opportunity/Risk to fetch parent relationship.

        Args:
            account_id: Account identifier
            node_id: Node identifier
            node_type: Node type from NODE_TYPE_REGISTRY
            relationship_query: Cypher query to fetch relationship (must include $node_id parameter)
            relationship_field: Field name to populate in response
            response_model_class: Response model class
            service: GraphSyncService instance
            user: Authenticated user context

        Returns:
            Response model with relationship field populated
        """
        await check_graph_access(account_id, user, "view")

        config = NODE_TYPE_REGISTRY[node_type]

        try:
            node = await service.get_node(account_id, node_id, config["neo4j_label"])
            if not node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{config['human_readable'].capitalize()} not found",
                )

            # Execute relationship query
            result = await service.neo4j.execute_query(
                relationship_query, {"node_id": node_id}
            )
            if result and result[0]:
                node[relationship_field] = result[0][relationship_field]

            return response_model_class(**node)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to get {config['human_readable']}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get {config['human_readable']}",
            ) from e
```

#### 2.3 Testing

Create unit tests for generic CRUD methods:

**New file:** `/api/tests/unit/routers/test_crud_factory.py`

```python
"""Unit tests for generic CRUD endpoint factory."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from src.kene_api.routers.knowledge_graph.crud_factory import CRUDEndpoints
from src.kene_api.models.graph_models import (
    GoalCreate,
    GoalResponse,
    GoalListResponse,
)
from src.kene_api.exceptions import (
    NodeNotFoundException,
    ValidationException,
    DuplicateNodeException,
)


@pytest.mark.asyncio
async def test_create_node_success():
    """Test successful node creation via generic endpoint."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    goal_data = GoalCreate(goal_text="Increase revenue", target_value="$1M")
    service_method = AsyncMock(return_value={
        "node_id": "goal_123",
        "account_id": "acc_123",
        "goal_text": "Increase revenue",
        "target_value": "$1M",
        "created_time": "2025-01-01T00:00:00Z",
        "last_modified": "2025-01-01T00:00:00Z",
        "created_by": "user_123",
        "last_modified_by": "user_123",
    })

    result = await CRUDEndpoints.create_node(
        account_id="acc_123",
        node_type="Goal",
        create_data=goal_data,
        response_model_class=GoalResponse,
        service_method=service_method,
        service=service,
        user=user,
    )

    assert result.node_id == "goal_123"
    assert result.goal_text == "Increase revenue"
    service_method.assert_called_once()


@pytest.mark.asyncio
async def test_create_node_validation_error():
    """Test that ValidationException is converted to 400 error."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    service_method = AsyncMock(side_effect=ValidationException("Invalid data"))

    with pytest.raises(HTTPException) as exc_info:
        await CRUDEndpoints.create_node(
            account_id="acc_123",
            node_type="Goal",
            create_data=GoalCreate(goal_text="Test"),
            response_model_class=GoalResponse,
            service_method=service_method,
            service=service,
            user=user,
        )

    assert exc_info.value.status_code == 400
    assert "Invalid data" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_node_duplicate_error():
    """Test that DuplicateNodeException is converted to 409 error."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    service_method = AsyncMock(side_effect=DuplicateNodeException("Duplicate"))

    with pytest.raises(HTTPException) as exc_info:
        await CRUDEndpoints.create_node(
            account_id="acc_123",
            node_type="Goal",
            create_data=GoalCreate(goal_text="Test"),
            response_model_class=GoalResponse,
            service_method=service_method,
            service=service,
            user=user,
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_list_nodes_success():
    """Test successful node listing with pagination."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    service.count_nodes = AsyncMock(return_value=2)
    service.list_nodes = AsyncMock(return_value=[
        {"node_id": "goal_1", "goal_text": "Goal 1", "account_id": "acc_123",
         "created_time": "2025-01-01T00:00:00Z", "last_modified": "2025-01-01T00:00:00Z",
         "created_by": "user_123", "last_modified_by": "user_123"},
        {"node_id": "goal_2", "goal_text": "Goal 2", "account_id": "acc_123",
         "created_time": "2025-01-01T00:00:00Z", "last_modified": "2025-01-01T00:00:00Z",
         "created_by": "user_123", "last_modified_by": "user_123"},
    ])

    result = await CRUDEndpoints.list_nodes(
        account_id="acc_123",
        node_type="Goal",
        response_model_class=GoalResponse,
        list_response_class=GoalListResponse,
        skip=0,
        limit=10,
        service=service,
        user=user,
    )

    assert result.total_count == 2
    assert len(result.goals) == 2
    assert result.goals[0].node_id == "goal_1"


@pytest.mark.asyncio
async def test_get_node_success():
    """Test successful node retrieval."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    service.get_node = AsyncMock(return_value={
        "node_id": "goal_123",
        "account_id": "acc_123",
        "goal_text": "Increase revenue",
        "created_time": "2025-01-01T00:00:00Z",
        "last_modified": "2025-01-01T00:00:00Z",
        "created_by": "user_123",
        "last_modified_by": "user_123",
    })

    result = await CRUDEndpoints.get_node(
        account_id="acc_123",
        node_id="goal_123",
        node_type="Goal",
        response_model_class=GoalResponse,
        service=service,
        user=user,
    )

    assert result.node_id == "goal_123"
    assert result.goal_text == "Increase revenue"


@pytest.mark.asyncio
async def test_get_node_not_found():
    """Test 404 error when node not found."""
    service = AsyncMock()
    user = MagicMock()
    user.is_super_admin = True

    service.get_node = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await CRUDEndpoints.get_node(
            account_id="acc_123",
            node_id="nonexistent",
            node_type="Goal",
            response_model_class=GoalResponse,
            service=service,
            user=user,
        )

    assert exc_info.value.status_code == 404
```

**Checklist:**
- [ ] Create router directory structure
- [ ] Create crud_factory.py with all generic methods
- [ ] Create unit tests for crud_factory
- [ ] All unit tests pass

---

## Phase 3: Create Domain-Based Router Structure

### Duration
Day 2-3 - 6 hours

### Tasks

#### 3.1 Extract Aggregated Views Router (Easiest First)

**New file:** `/api/src/kene_api/routers/knowledge_graph/aggregated.py`

Copy the 4 aggregated view endpoints from the old router:
- `get_business_strategy`
- `get_competitive_strategy`
- `get_marketing_strategy`
- `get_brand_strategy`

```python
"""Aggregated strategy view endpoints.

Read-only endpoints that combine multiple node types into unified strategy views.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...models.graph_models import (
    BusinessStrategyResponse,
    CompetitiveStrategyResponse,
    MarketingStrategyResponse,
    BrandStrategyResponse,
    # Import all necessary response models
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import check_graph_access

logger = logging.getLogger(__name__)

router = APIRouter()  # No prefix - parent handles it


@router.get("/{account_id}/business-strategy", response_model=BusinessStrategyResponse)
async def get_business_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> BusinessStrategyResponse:
    """Get complete business strategy graph for an account.

    Returns all nodes in a hierarchical structure.
    Requires view permission for the account.
    """
    # Copy implementation from old knowledge_graph.py
    # Lines ~1919-1983
    ...

# Similar for other 3 aggregated endpoints
```

#### 3.2 Create Business Strategy Router

**New file:** `/api/src/kene_api/routers/knowledge_graph/business.py`

Implement all 9 business strategy node types using generic CRUD:

```python
"""Business strategy node endpoints.

CRUD endpoints for 9 business strategy node types:
- ProductCategory, Product, ValueProposition
- Strength, Weakness, Opportunity, Risk
- Goal, SWOTAnalysis
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...auth.dependencies import get_current_user
from ...auth.models import UserContext
from ...constants import NODE_TYPE_REGISTRY
from ...models.graph_models import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCategoryResponse,
    ProductCategoryListResponse,
    GoalCreate,
    GoalUpdate,
    GoalResponse,
    GoalListResponse,
    DeleteResponse,
    # Import all business strategy models
)
from ...services.graph_sync_service import GraphSyncService, get_graph_sync_service
from .crud_factory import CRUDEndpoints, check_graph_access

logger = logging.getLogger(__name__)

router = APIRouter()  # No prefix


# ==================== PRODUCT CATEGORY ENDPOINTS ====================

@router.post("/{account_id}/product-categories", response_model=ProductCategoryResponse)
async def create_product_category(
    account_id: str,
    category: ProductCategoryCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Create a new product category.

    Requires edit permission for the account.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="ProductCategory",
        create_data=category,
        response_model_class=ProductCategoryResponse,
        service_method=service.create_product_category,
        service=service,
        user=user,
    )


@router.get("/{account_id}/product-categories", response_model=ProductCategoryListResponse)
async def list_product_categories(
    account_id: str,
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int | None = Query(
        None, ge=1, le=1000, description="Maximum number of items to return"
    ),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryListResponse:
    """List all product categories with optional pagination."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ProductCategory",
        response_model_class=ProductCategoryResponse,
        list_response_class=ProductCategoryListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
    )


@router.get("/{account_id}/product-categories/{node_id}", response_model=ProductCategoryResponse)
async def get_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Get a specific product category by node_id."""
    return await CRUDEndpoints.get_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        response_model_class=ProductCategoryResponse,
        service=service,
        user=user,
    )


@router.patch("/{account_id}/product-categories/{node_id}", response_model=ProductCategoryResponse)
async def update_product_category(
    account_id: str,
    node_id: str,
    updates: ProductCategoryUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductCategoryResponse:
    """Update a product category."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        update_data=updates,
        response_model_class=ProductCategoryResponse,
        service_method=service.update_product_category,
        service=service,
        user=user,
    )


@router.delete("/{account_id}/product-categories/{node_id}", response_model=DeleteResponse)
async def delete_product_category(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a product category."""
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="ProductCategory",
        service_method=service.delete_product_category,
        service=service,
        user=user,
    )

# Repeat for all 9 business strategy node types
# Use same pattern for Goal, Strength, Weakness, etc.
```

#### 3.3 Create Competitive Strategy Router

**New file:** `/api/src/kene_api/routers/knowledge_graph/competitive.py`

Similar pattern for 6 competitive node types.

#### 3.4 Create Marketing Strategy Router

**New file:** `/api/src/kene_api/routers/knowledge_graph/marketing.py`

Similar pattern for 6 marketing node types.

#### 3.5 Create Brand Strategy Router

**New file:** `/api/src/kene_api/routers/knowledge_graph/brand.py`

Similar pattern for 7 brand node types.

**Checklist:**
- [ ] Extract aggregated.py router
- [ ] Create business.py router with all 9 types
- [ ] Create competitive.py router with 6 types
- [ ] Create marketing.py router with 6 types
- [ ] Create brand.py router with 7 types

---

## Phase 4: Wire Together with Main Router

### Duration
Day 3 - 2 hours

### Tasks

#### 4.1 Create Main Router

**New file:** `/api/src/kene_api/routers/knowledge_graph/__init__.py`

```python
"""Unified knowledge graph router.

Combines all domain-specific routers (business, competitive, marketing, brand)
and aggregated view endpoints.
"""

from fastapi import APIRouter

from . import aggregated, business, competitive, marketing, brand

# Main router with prefix and tags
router = APIRouter(
    prefix="/api/v1/knowledge-graph",
    tags=["knowledge-graph"],
)

# Include all domain routers
router.include_router(business.router)
router.include_router(competitive.router)
router.include_router(marketing.router)
router.include_router(brand.router)
router.include_router(aggregated.router)

__all__ = ["router"]
```

#### 4.2 Update Main App

**File:** `/api/src/kene_api/main.py`

Change import:

```python
# OLD:
from .routers import knowledge_graph

# NEW:
from .routers.knowledge_graph import router as knowledge_graph_router

# OLD:
app.include_router(knowledge_graph.router)

# NEW:
app.include_router(knowledge_graph_router)
```

**Checklist:**
- [ ] Create __init__.py with router composition
- [ ] Update main.py imports
- [ ] Verify app starts without errors

---

## Phase 5: Handle Special Cases

### Duration
Day 4 - 6 hours

### Special Case Implementations

#### 1. Product (Optimized List Query)

In `business.py`, keep custom implementation for `list_products`:

```python
@router.get("/{account_id}/products", response_model=ProductListResponse)
async def list_products(
    account_id: str,
    category_node_id: str | None = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProductListResponse:
    """List products with optional category filtering.

    Uses optimized query to avoid N+1 problems.
    """
    await check_graph_access(account_id, user, "view")

    try:
        # SPECIAL: Use optimized service method
        products_data, total_count = await service.list_products_with_categories(
            account_id=account_id,
            category_node_id=category_node_id,
            skip=skip,
            limit=limit,
        )
        products = [ProductResponse(**prod) for prod in products_data]
        return ProductListResponse(products=products, total_count=total_count)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list products",
        ) from e
```

#### 2. ValueProposition (Parent Filtering)

Can use generic `list_nodes` with parent filter:

```python
@router.get("/{account_id}/value-propositions", response_model=ValuePropositionListResponse)
async def list_value_propositions(
    account_id: str,
    parent_node_id: str | None = Query(
        None, description="Filter by parent (Product, ProductCategory, Account)"
    ),
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ValuePropositionListResponse:
    """List value propositions with optional parent filtering."""
    return await CRUDEndpoints.list_nodes(
        account_id=account_id,
        node_type="ValueProposition",
        response_model_class=ValuePropositionResponse,
        list_response_class=ValuePropositionListResponse,
        skip=skip,
        limit=limit,
        service=service,
        user=user,
        parent_filter_id=parent_node_id,
    )
```

#### 3. Opportunity (Relationship Fetch)

Use `get_node_with_relationship`:

```python
@router.get("/{account_id}/opportunities/{node_id}", response_model=OpportunityResponse)
async def get_opportunity(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> OpportunityResponse:
    """Get a specific opportunity by node_id."""
    relationship_query = """
    MATCH (s:Strength)-[:CREATES]->(o:Opportunity {node_id: $node_id})
    RETURN s.node_id as strength_node_id
    LIMIT 1
    """
    return await CRUDEndpoints.get_node_with_relationship(
        account_id=account_id,
        node_id=node_id,
        node_type="Opportunity",
        relationship_query=relationship_query,
        relationship_field="strength_node_id",
        response_model_class=OpportunityResponse,
        service=service,
        user=user,
    )
```

#### 4. Risk (Similar to Opportunity)

Similar pattern with different relationship query.

#### 5-6. Hub Nodes (CompetitiveEnvironment, BrandIdentity)

Keep explicit GET + UPDATE only implementations (no CREATE/DELETE/LIST):

```python
@router.get("/{account_id}/competitive-environment", response_model=CompetitiveEnvironmentResponse)
async def get_competitive_environment(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> CompetitiveEnvironmentResponse:
    """Get the competitive environment hub for an account."""
    await check_graph_access(account_id, user, "view")

    try:
        envs = await service.list_nodes(
            account_id, "CompetitiveEnvironment", skip=0, limit=1
        )
        if not envs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Competitive environment not found. Create a competitor to auto-create the environment.",
            )
        return CompetitiveEnvironmentResponse(**envs[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get competitive environment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get competitive environment",
        ) from e
```

**Checklist:**
- [ ] Implement custom Product list logic
- [ ] Implement ValueProposition with parent filter
- [ ] Implement Opportunity with relationship fetch
- [ ] Implement Risk with relationship fetch
- [ ] Implement CompetitiveEnvironment hub logic
- [ ] Implement BrandIdentity hub logic

---

## Phase 6: Testing & Validation

### Duration
Day 5-6 - 12 hours

### Tasks

#### 6.1 Run Existing Integration Tests

```bash
cd api
DATABASE_INTEGRATION_TESTS=true pytest tests/integration/test_knowledge_graph_endpoints.py -v
```

**Expected:** All 1,792 lines of tests should pass without modification.

#### 6.2 Manual Testing Checklist

Test each operation for representative node types:

**ProductCategory (Standard CRUD):**
- [ ] Create new product category
- [ ] List product categories
- [ ] Get specific product category
- [ ] Update product category
- [ ] Delete product category

**Product (Special: Category Filter):**
- [ ] Create product
- [ ] List products (no filter)
- [ ] List products (with category filter)
- [ ] Get product
- [ ] Update product
- [ ] Delete product

**Opportunity (Special: Relationship Fetch):**
- [ ] Create opportunity
- [ ] List opportunities (with strength filter)
- [ ] Get opportunity (verify strength_node_id populated)
- [ ] Update opportunity
- [ ] Delete opportunity

**CompetitiveEnvironment (Hub Node):**
- [ ] Get competitive environment
- [ ] Update competitive environment
- [ ] Verify no CREATE/DELETE/LIST endpoints exist

**Aggregated Views:**
- [ ] Get business strategy
- [ ] Get competitive strategy
- [ ] Get marketing strategy
- [ ] Get brand strategy

#### 6.3 Error Testing

- [ ] Test 400 errors (validation failures)
- [ ] Test 404 errors (node not found)
- [ ] Test 409 errors (duplicates)
- [ ] Test 403 errors (unauthorized)

#### 6.4 Performance Testing

- [ ] Compare response times before/after refactoring
- [ ] Verify no N+1 query regressions

**Checklist:**
- [ ] All integration tests pass
- [ ] Manual testing completed
- [ ] Error scenarios tested
- [ ] Performance validated

---

## Phase 7: Cleanup & Documentation

### Duration
Day 7 - 4 hours

### Tasks

#### 7.1 Delete Old Router

```bash
git rm api/src/kene_api/routers/knowledge_graph.py
```

#### 7.2 Run Formatting and Type Checking

```bash
cd api
# Run ruff formatting
ruff format .

# Run ruff linting
ruff check .

# Run mypy type checking
mypy src/

# Run codespell
codespell
```

Fix any issues that arise.

#### 7.3 Update Documentation

**File:** `knowledge_graph/PHASE1_IMPLEMENTATION_PLAN.md`

Add completion section:

```markdown
## Router Refactoring (Completed)

**Date:** [Date]
**PR:** #[PR number]

### Changes Made

1. **Reduced code from 5,476 lines to ~2,720 lines** (50% reduction)
2. **Created domain-based router structure:**
   - `routers/knowledge_graph/business.py` (~450 lines)
   - `routers/knowledge_graph/competitive.py` (~450 lines)
   - `routers/knowledge_graph/marketing.py` (~450 lines)
   - `routers/knowledge_graph/brand.py` (~550 lines)
   - `routers/knowledge_graph/aggregated.py` (~400 lines)
   - `routers/knowledge_graph/crud_factory.py` (~400 lines)

3. **Extracted generic CRUD logic** to eliminate duplication
4. **Maintained 100% API compatibility** - all existing tests pass
5. **Added node type registry** in `constants.py` for configuration

### Benefits

- **Easier to maintain**: Changes to CRUD logic update all endpoints
- **Better organization**: Domain-based split improves navigation
- **Consistent error handling**: Single source of truth
- **Easier testing**: Generic logic can be unit tested
- **No breaking changes**: Existing integrations unaffected

### Special Cases Preserved

Six node types retain custom implementations:
- Product (optimized category query)
- ValueProposition (parent filtering)
- Opportunity (relationship fetch)
- Risk (relationship fetch)
- CompetitiveEnvironment (hub node)
- BrandIdentity (hub node)
```

#### 7.4 Update CLAUDE.md

Add section:

```markdown
### Knowledge Graph Routers

The knowledge graph API is organized by strategy domain:

- `business.py` - Business strategy nodes (ProductCategory, Product, Goal, etc.)
- `competitive.py` - Competitive strategy nodes (Competitor, SubstituteProduct, etc.)
- `marketing.py` - Marketing strategy nodes (CustomerProfile, *Strategy, etc.)
- `brand.py` - Brand strategy nodes (BrandPersonality, ColorPalette, etc.)
- `aggregated.py` - Aggregated view endpoints
- `crud_factory.py` - Generic CRUD implementations (DRY principle)

To add a new node type:
1. Add model definitions to `models/graph_models.py`
2. Add configuration to `constants.NODE_TYPE_REGISTRY`
3. Add service methods to `services/graph_sync_service.py`
4. Add endpoints to appropriate domain router using `CRUDEndpoints`
```

**Checklist:**
- [ ] Delete old router file
- [ ] Run formatting tools (ruff format)
- [ ] Run linting (ruff check)
- [ ] Run type checking (mypy)
- [ ] Update PHASE1_IMPLEMENTATION_PLAN.md
- [ ] Update CLAUDE.md

---

## Risk Management & Rollback Plan

### Risks

1. **Introduced bugs in refactoring** (MEDIUM)
   - **Mitigation:** Comprehensive test suite (1,792 integration tests)
   - All tests must pass before merge

2. **Breaking API compatibility** (LOW)
   - **Mitigation:** No changes to endpoint signatures or responses
   - URL paths unchanged

3. **Performance regression** (LOW)
   - **Mitigation:** No changes to service layer logic
   - Generic functions add minimal overhead (single function call)

4. **Merge conflicts** (LOW)
   - **Mitigation:** Big-bang on feature branch
   - Coordinate with team on timing

### Rollback Plan

If critical issues discovered after merge:

1. **Immediate:** Revert the merge commit
2. **Short-term:** Debug on feature branch
3. **Long-term:** Re-merge after fixes

The old `knowledge_graph.py` will be preserved in git history for reference.

---

## Success Metrics

- [ ] Code reduced from 5,476 lines to ~2,720 lines (50% reduction)
- [ ] All 1,792 integration tests pass
- [ ] New unit tests added for generic CRUD (>80% coverage)
- [ ] Manual testing checklist completed
- [ ] No API breaking changes
- [ ] Documentation updated
- [ ] Code passes ruff format, ruff check, mypy

---

## Estimated Line Count After Refactoring

| File | Before | After | Savings |
|------|--------|-------|---------|
| knowledge_graph.py | 5,476 | 0 (deleted) | -5,476 |
| business.py | 0 | ~450 | +450 |
| competitive.py | 0 | ~450 | +450 |
| marketing.py | 0 | ~450 | +450 |
| brand.py | 0 | ~550 | +550 |
| aggregated.py | 0 | ~400 | +400 |
| crud_factory.py | 0 | ~400 | +400 |
| __init__.py | 0 | ~20 | +20 |
| **Total** | **5,476** | **~2,720** | **-2,756** |

Additional changes:
- constants.py: +200 lines (node registry)
- test_crud_factory.py: +400 lines (unit tests)

**Net reduction: ~2,750 lines** (50%) while adding configuration and tests!

---

## Implementation Checklist

### Day 1: Setup (4 hours)
- [ ] Create feature branch `feature/router-refactoring`
- [ ] Add `NODE_TYPE_REGISTRY` to `constants.py`
- [ ] Create `routers/knowledge_graph/` directory
- [ ] Create `crud_factory.py` with all generic methods
- [ ] Write unit tests for crud_factory
- [ ] All unit tests pass

### Day 2: Extract Routers Part 1 (8 hours)
- [ ] Extract `aggregated.py`
- [ ] Test aggregated endpoints manually
- [ ] Extract `business.py` with all 9 node types
- [ ] Test business endpoints manually

### Day 3: Extract Routers Part 2 (8 hours)
- [ ] Extract `competitive.py` with 6 node types
- [ ] Extract `marketing.py` with 6 node types
- [ ] Extract `brand.py` with 7 node types
- [ ] Create `__init__.py` to wire everything
- [ ] Update `main.py` imports
- [ ] Verify app starts

### Day 4: Handle Special Cases (6 hours)
- [ ] Implement custom Product list logic
- [ ] Implement custom ValueProposition logic
- [ ] Implement custom Opportunity logic
- [ ] Implement custom Risk logic
- [ ] Implement hub node logic (CompetitiveEnvironment, BrandIdentity)
- [ ] Test all special cases manually

### Day 5: Testing (8 hours)
- [ ] Run all integration tests (must pass 100%)
- [ ] Complete manual testing checklist
- [ ] Test error scenarios
- [ ] Fix any bugs discovered

### Day 6: Polish (6 hours)
- [ ] Address any remaining test failures
- [ ] Performance testing
- [ ] Code review preparation
- [ ] Documentation updates

### Day 7: Finalize (2 hours)
- [ ] Run formatting (ruff format)
- [ ] Run linting (ruff check)
- [ ] Run type checking (mypy)
- [ ] Delete old router file
- [ ] Final documentation updates
- [ ] Create pull request

---

## Summary

This refactoring will:

✅ **Reduce code by 50%** (5,476 → 2,720 lines)
✅ **Improve maintainability** via domain-based organization
✅ **Eliminate duplication** through generic CRUD functions
✅ **Maintain API compatibility** (zero breaking changes)
✅ **Follow existing patterns** (consistent with codebase)
✅ **Preserve special cases** (explicit implementations where needed)
✅ **Pass all tests** (1,792 integration tests)

The refactoring uses **Generic Base Class + Inheritance** pattern, keeping explicit endpoint definitions for IDE support while extracting all common logic into reusable generic functions.
