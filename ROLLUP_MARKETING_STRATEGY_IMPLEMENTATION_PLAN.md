# Rollup Marketing Strategy - Complete Implementation Plan

**Feature**: Create consolidated rollup marketing strategies that summarize all individual (product category × customer profile) strategies into a single company-wide marketing strategy.

**Status**: Design Complete - Ready for Implementation
**Created**: 2025-12-10
**Estimated Effort**: 4-6 hours

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Graph Structure Design](#graph-structure-design)
4. [Implementation Details](#implementation-details)
5. [API Endpoints (Option B - Full CRUD)](#api-endpoints-option-b---full-crud)
6. [Testing Strategy](#testing-strategy)
7. [Files to Modify](#files-to-modify)
8. [Implementation Checklist](#implementation-checklist)
9. [Design Decisions & Rationale](#design-decisions--rationale)
10. [Future Enhancements](#future-enhancements)

---

## Executive Summary

### Problem Statement

Currently, marketing strategies are created for each (ProductCategory × CustomerProfile) combination, resulting in many individual strategies. There's no consolidated view showing the overall marketing approach for the entire business.

### Solution

After all individual strategies are created, automatically generate:
1. **One RollupMarketingStrategy hub node** - central entry point
2. **Five rollup strategy nodes** - one per funnel stage (Problem Awareness, Brand Awareness, Consideration, Conversion, Loyalty)
3. **Relationships** - hub links to Account and all 5 rollup strategies
4. **Customization links** - each rollup links back to all individual strategies via `[:CAN_BE_CUSTOMIZED_BY]`

### Key Benefits

- Single consolidated marketing strategy view for the entire business
- Maintains traceability to individual strategies
- Fully editable via API (Option B - Full CRUD)
- Automatic creation during account setup
- No changes to existing agent architecture

---

## Architecture Overview

### Current System Flow

```
Account Creation (API)
  ↓
Trigger Strategy Generation (async task)
  ↓
Orchestrator: execute_strategy_generation_direct()
  ↓
PHASE 1: Business Strategy (sequential)
  ├── Extract product categories
  ↓
PHASE 2: Marketing + Competitive + Brand (parallel)
  ├── Marketing Strategy
  │   ├── Researcher Agent (with tools, no schema)
  │   ├── Formatter Agent (no tools, with schema)
  │   ├── Firestore save
  │   ├── MarketingGraphBuilder.build_marketing_graph()
  │   │   ├── Phase 1: Create CustomerProfile nodes (2-5)
  │   │   ├── Phase 2: Create Strategy nodes (5 per category×profile combo)
  │   │   └── Phase 3: [NEW] Create Rollup Strategies
  │   └── Generate embeddings
```

### New Phase 3: Rollup Creation

**Location**: `MarketingGraphBuilder.build_marketing_graph()` - after Phase 2 completes

**Steps**:
1. Verify individual strategies were created successfully
2. Create `RollupMarketingStrategy` hub node
3. Link hub to Account via `[:INCREASES_CUSTOMERS_BY]`
4. Create 5 rollup strategy nodes (one per funnel stage)
5. Link hub to each rollup strategy node
6. Link each rollup strategy to individual strategies via `[:CAN_BE_CUSTOMIZED_BY]`
7. Add rollup nodes to `created_nodes` tracking dict

**Error Handling**:
- Rollup creation is **optional** (won't fail entire graph build)
- Log warnings if rollup creation fails
- Continue with embedding generation even if rollups fail

---

## Graph Structure Design

### Node Types

#### 1. RollupMarketingStrategy (Hub Node)

**Labels**: `:RollupMarketingStrategy:Strategy`

**Properties**:
```python
{
    "node_id": "rollup_marketing_hub_{account_id}",  # Deterministic
    "account_id": "{account_id}",
    "description": "Consolidated marketing strategy for the entire business",
    "created_time": "2025-12-10T10:00:00Z",
    "last_modified": "2025-12-10T10:00:00Z",
    "created_by": "System",
    "last_modified_by": "System",
    "embedding": None  # Will be populated by embedding generation
}
```

**Relationships**:
- `(RollupMarketingStrategy)-[:INCREASES_CUSTOMERS_BY]->(Account)` - Links to account
- `(RollupMarketingStrategy)-[:INCREASES_PROBLEM_AWARENESS_BY]->(ProblemAwarenessStrategy)` - Links to rollup strategy
- `(RollupMarketingStrategy)-[:INCREASES_BRAND_AWARENESS_BY]->(BrandAwarenessStrategy)` - Links to rollup strategy
- `(RollupMarketingStrategy)-[:INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY]->(ConsiderationStrategy)` - Links to rollup strategy
- `(RollupMarketingStrategy)-[:INCREASES_PAYING_CUSTOMERS_BY]->(ConversionStrategy)` - Links to rollup strategy
- `(RollupMarketingStrategy)-[:INCREASES_LOYAL_CUSTOMERS_BY]->(LoyaltyStrategy)` - Links to rollup strategy

#### 2. Rollup Strategy Nodes (5 types)

**Node Types**: Use SAME types as individual strategies
- `ProblemAwarenessStrategy:Strategy` (rollup)
- `BrandAwarenessStrategy:Strategy` (rollup)
- `ConsiderationStrategy:Strategy` (rollup)
- `ConversionStrategy:Strategy` (rollup)
- `LoyaltyStrategy:Strategy` (rollup)

**Distinguished by node_id pattern**:
- Individual: `problemaware_{product_category_id}_{customer_profile_id}`
- Rollup: `rollup_problemaware_{account_id}`

**Properties** (example for ProblemAwarenessStrategy):
```python
{
    "node_id": "rollup_problemaware_{account_id}",  # Deterministic
    "account_id": "{account_id}",
    "description": "Consolidated summary of all problem awareness strategies",
    "references": [],  # Empty or aggregate all references
    "created_time": "2025-12-10T10:00:00Z",
    "last_modified": "2025-12-10T10:00:00Z",
    "created_by": "System",
    "last_modified_by": "System",
    "embedding": None
}
```

**Relationships**:
- `(RollupProblemAwarenessStrategy)-[:BELONGS_TO]->(Account)` - Standard for all Strategy nodes
- `(RollupProblemAwarenessStrategy)<-[:INCREASES_PROBLEM_AWARENESS_BY]-(RollupMarketingStrategy)` - From hub
- `(RollupProblemAwarenessStrategy)-[:CAN_BE_CUSTOMIZED_BY]->(ProblemAwarenessStrategy)` - Links to all individual strategies (many)

### Complete Graph Structure

```
Account
  ↑
  [:INCREASES_CUSTOMERS_BY]
  |
RollupMarketingStrategy (hub)
  |
  ├─[:INCREASES_PROBLEM_AWARENESS_BY]──→ ProblemAwarenessStrategy (rollup)
  |                                         ├─[:CAN_BE_CUSTOMIZED_BY]→ ProblemAwarenessStrategy (individual 1)
  |                                         ├─[:CAN_BE_CUSTOMIZED_BY]→ ProblemAwarenessStrategy (individual 2)
  |                                         └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all problem awareness strategies)
  |
  ├─[:INCREASES_BRAND_AWARENESS_BY]────→ BrandAwarenessStrategy (rollup)
  |                                         └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all brand awareness strategies)
  |
  ├─[:INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY]→ ConsiderationStrategy (rollup)
  |                                                    └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all consideration strategies)
  |
  ├─[:INCREASES_PAYING_CUSTOMERS_BY]───→ ConversionStrategy (rollup)
  |                                         └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all conversion strategies)
  |
  └─[:INCREASES_LOYAL_CUSTOMERS_BY]────→ LoyaltyStrategy (rollup)
                                            └─[:CAN_BE_CUSTOMIZED_BY]→ ... (all loyalty strategies)
```

---

## Implementation Details

### 1. Graph Builder Changes

**File**: `app/adk/agents/strategy_agent/marketing_graph_builder.py`

**IMPORTANT - MVP Simplification**: Rollup strategies will have **empty description fields** initially. This avoids complexity of text summarization while allowing the node structure to be in place. Descriptions can be populated later via API PATCH endpoints or future LLM enhancement.

#### A. Update `build_marketing_graph()` Method

Add Phase 3 after Phase 2 completes:

```python
def build_marketing_graph(
    self,
    research_report: MarketingResearchReport,
    account_id: str,
    user_id: str
) -> dict:
    """
    Build complete marketing strategy graph in Neo4j.

    Phase 1: Create CustomerProfile nodes (2-5 master profiles)
    Phase 2: Create strategy nodes (5 per category×profile combo)
    Phase 3: Create rollup strategies (NEW)
    """
    try:
        created_nodes = {
            "customer_profiles": [],
            "problem_awareness_strategies": [],
            "brand_awareness_strategies": [],
            "consideration_strategies": [],
            "conversion_strategies": [],
            "loyalty_strategies": [],
            "is_marketed_to_relationships": [],
            "rollup_marketing_hub": None,  # NEW
            "rollup_strategies": {},  # NEW
        }

        # Phase 1: Create master CustomerProfile nodes (existing code)
        # ... existing implementation ...

        # Phase 2: Create product-scoped strategies (existing code)
        # ... existing implementation ...

        # Phase 3 (NEW): Create rollup strategies
        try:
            rollup_nodes = self._create_rollup_strategies(
                research_report=research_report,
                account_id=account_id,
                user_id=user_id,
                created_nodes=created_nodes,
            )
            created_nodes["rollup_marketing_hub"] = rollup_nodes["hub"]
            created_nodes["rollup_strategies"] = rollup_nodes["strategies"]
            logger.info(
                f"Successfully created rollup marketing strategy with "
                f"{len(rollup_nodes['strategies'])} rollup strategy nodes"
            )
        except Exception as rollup_error:
            # Log warning but don't fail entire graph build
            logger.warning(
                f"Failed to create rollup strategies (non-critical): {rollup_error}",
                exc_info=True
            )

        return created_nodes

    except Exception as e:
        logger.error(f"Failed to build marketing graph: {e}", exc_info=True)
        raise
```

#### B. Add Rollup Creation Methods

```python
def _create_rollup_strategies(
    self,
    research_report: MarketingResearchReport,
    account_id: str,
    user_id: str,
    created_nodes: dict,
) -> dict:
    """
    Create rollup marketing strategies that consolidate all individual strategies.

    Creates:
    1. One RollupMarketingStrategy hub node
    2. Five rollup strategy nodes (one per funnel stage)
    3. Relationships: hub → account, hub → rollup strategies, rollup strategies → individuals

    Args:
        research_report: Marketing research with profiles and category mappings
        account_id: Account identifier
        user_id: User identifier
        created_nodes: Dictionary with previously created nodes

    Returns:
        Dictionary with hub and strategy nodes
    """
    # Verify we have individual strategies to roll up
    required_keys = [
        "problem_awareness_strategies",
        "brand_awareness_strategies",
        "consideration_strategies",
        "conversion_strategies",
        "loyalty_strategies",
    ]

    for key in required_keys:
        if not created_nodes.get(key):
            raise ValueError(
                f"Cannot create rollup strategies: {key} is empty. "
                "Individual strategies must be created first."
            )

    # Step 1: Create hub node
    hub_node = self._create_rollup_marketing_hub(account_id, user_id)

    # Step 2: Create 5 rollup strategy nodes
    rollup_configs = [
        {
            "stage": "problem_awareness",
            "node_type": "ProblemAwarenessStrategy",
            "created_key": "problem_awareness_strategies",
            "hub_relationship": "INCREASES_PROBLEM_AWARENESS_BY",
        },
        {
            "stage": "brand_awareness",
            "node_type": "BrandAwarenessStrategy",
            "created_key": "brand_awareness_strategies",
            "hub_relationship": "INCREASES_BRAND_AWARENESS_BY",
        },
        {
            "stage": "consideration",
            "node_type": "ConsiderationStrategy",
            "created_key": "consideration_strategies",
            "hub_relationship": "INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY",
        },
        {
            "stage": "conversion",
            "node_type": "ConversionStrategy",
            "created_key": "conversion_strategies",
            "hub_relationship": "INCREASES_PAYING_CUSTOMERS_BY",
        },
        {
            "stage": "loyalty",
            "node_type": "LoyaltyStrategy",
            "created_key": "loyalty_strategies",
            "hub_relationship": "INCREASES_LOYAL_CUSTOMERS_BY",
        },
    ]

    strategy_nodes = {}

    for config in rollup_configs:
        individual_strategies = created_nodes[config["created_key"]]

        rollup_node = self._create_single_rollup_strategy(
            config=config,
            individual_strategies=individual_strategies,
            hub_node_id=hub_node["node_id"],
            account_id=account_id,
            user_id=user_id,
        )

        strategy_nodes[config["stage"]] = rollup_node

    return {
        "hub": hub_node,
        "strategies": strategy_nodes,
    }


def _create_rollup_marketing_hub(
    self,
    account_id: str,
    user_id: str,
) -> dict:
    """
    Create RollupMarketingStrategy hub node.

    This is the central node that links to the Account and all 5 rollup strategies.
    """
    node_id = f"rollup_marketing_hub_{account_id}"

    node_data = {
        "node_id": node_id,
        "description": "Consolidated marketing strategy for the entire business",
        "created_time": datetime.now().isoformat(),
        "last_modified": datetime.now().isoformat(),
        "created_by": user_id,
        "last_modified_by": user_id,
        "embedding": None,
    }

    # Create hub node
    self.neo4j_ops.create_strategy_node(
        "RollupMarketingStrategy",
        node_data,
        account_id
    )

    # Link hub to Account
    query = """
    MATCH (hub:RollupMarketingStrategy {node_id: $hub_id})
    MATCH (acc:Account {account_id: $account_id})
    MERGE (hub)-[:INCREASES_CUSTOMERS_BY]->(acc)
    """
    self.neo4j_ops.connection.execute_query(
        query,
        {"hub_id": node_id, "account_id": account_id}
    )

    logger.info(f"Created RollupMarketingStrategy hub: {node_id}")
    return node_data


def _create_single_rollup_strategy(
    self,
    config: dict,
    individual_strategies: list[dict],
    hub_node_id: str,
    account_id: str,
    user_id: str,
) -> dict:
    """
    Create a single rollup strategy node for one funnel stage.

    Args:
        config: Configuration dict with stage, node_type, hub_relationship
        individual_strategies: List of individual strategy nodes to consolidate
        hub_node_id: Node ID of the RollupMarketingStrategy hub
        account_id: Account identifier
        user_id: User identifier

    Returns:
        Created rollup strategy node data
    """
    # Generate deterministic node ID
    node_id = f"rollup_{config['stage'].replace('_', '')}_{account_id}"

    # MVP: Empty description field (can be populated later via API or LLM enhancement)
    # Future enhancement: Could aggregate references or create summary
    node_data = {
        "node_id": node_id,
        "description": "",  # Empty for MVP - populate via API PATCH later
        "references": [],  # Empty for MVP - could aggregate from individuals later
        "created_time": datetime.now().isoformat(),
        "last_modified": datetime.now().isoformat(),
        "created_by": user_id,
        "last_modified_by": user_id,
        "embedding": None,
    }

    # Create rollup strategy node
    self.neo4j_ops.create_strategy_node(
        config["node_type"],
        node_data,
        account_id
    )

    # Link hub to rollup strategy
    link_hub_query = f"""
    MATCH (hub:RollupMarketingStrategy {{node_id: $hub_id}})
    MATCH (rollup:{config['node_type']} {{node_id: $rollup_id}})
    MERGE (hub)-[:{config['hub_relationship']}]->(rollup)
    """
    self.neo4j_ops.connection.execute_query(
        link_hub_query,
        {"hub_id": hub_node_id, "rollup_id": node_id}
    )

    # Link rollup strategy to all individual strategies via [:CAN_BE_CUSTOMIZED_BY]
    individual_ids = [s["node_id"] for s in individual_strategies]

    link_individuals_query = f"""
    MATCH (rollup:{config['node_type']} {{node_id: $rollup_id}})
    MATCH (individual:{config['node_type']})
    WHERE individual.node_id IN $individual_ids
    MERGE (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual)
    """
    self.neo4j_ops.connection.execute_query(
        link_individuals_query,
        {"rollup_id": node_id, "individual_ids": individual_ids}
    )

    logger.info(
        f"Created rollup {config['node_type']} (node_id: {node_id}) "
        f"consolidating {len(individual_strategies)} individual strategies"
    )

    return node_data
```

**Note**: The `_summarize_strategy_descriptions()` method has been **removed** from the MVP implementation. Rollup strategies are created with empty descriptions that can be populated later via:
- Manual editing through API PATCH endpoints
- Future LLM enhancement (see Future Enhancements section)
- Automated summarization tool (future feature)

---

## API Endpoints (Option B - Full CRUD)

### Overview

Following the existing pattern in `api/src/kene_api/routers/knowledge_graph/marketing.py`, we'll add full CRUD endpoints for:
1. **RollupMarketingStrategy** (hub node)
2. **Rollup versions of 5 strategy types** (using same node types, distinguished by node_id pattern)

### A. Pydantic Models

**File**: `api/src/kene_api/models/graph_models.py`

Add these models (following existing patterns):

```python
# ==================== ROLLUP MARKETING STRATEGY HUB ====================

class RollupMarketingStrategyBase(BaseModel):
    """Base model for RollupMarketingStrategy hub node."""
    description: str = Field(..., description="Overall marketing strategy description")

class RollupMarketingStrategyCreate(RollupMarketingStrategyBase):
    """Create model for RollupMarketingStrategy."""
    pass

class RollupMarketingStrategyUpdate(BaseModel):
    """Update model for RollupMarketingStrategy."""
    description: str | None = None

class RollupMarketingStrategyResponse(RollupMarketingStrategyBase):
    """Response model for RollupMarketingStrategy."""
    node_id: str
    account_id: str
    created_time: str
    last_modified: str
    created_by: str
    last_modified_by: str
    embedding: list[float] | None = None

    # Optional: Include linked strategies
    rollup_strategies: dict[str, str] | None = Field(
        None,
        description="Map of stage name to rollup strategy node_id"
    )

class RollupMarketingStrategyListResponse(BaseModel):
    """List response for RollupMarketingStrategy."""
    items: list[RollupMarketingStrategyResponse]
    total: int
    skip: int
    limit: int | None


# ==================== ROLLUP STRATEGY RESPONSES ====================
# Note: We can reuse existing Create/Update models since rollup strategies
# use the same node types as individual strategies. Only add new List/Response
# models if we need different behavior.

class RollupStrategyListResponse(BaseModel):
    """Generic list response for rollup strategies."""
    items: list[ProblemAwarenessStrategyResponse]  # Type varies by endpoint
    total: int
    skip: int
    limit: int | None
    individual_strategy_count: int | None = Field(
        None,
        description="Count of individual strategies linked via CAN_BE_CUSTOMIZED_BY"
    )
```

### B. Service Methods

**File**: `api/src/kene_api/services/graph_sync_service.py`

Add these methods:

```python
async def get_rollup_marketing_hub(
    self,
    account_id: str,
) -> dict | None:
    """
    Get the RollupMarketingStrategy hub node for an account.

    Args:
        account_id: Account identifier

    Returns:
        Hub node with linked rollup strategy node_ids, or None if not found
    """
    query = """
    MATCH (hub:RollupMarketingStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    OPTIONAL MATCH (hub)-[r]->(rollup:Strategy)
    WHERE type(r) STARTS WITH 'INCREASES_'
    RETURN hub, collect({type: type(r), node_id: rollup.node_id}) as linked_strategies
    """

    result = self.neo4j_connection.execute_query(
        query,
        {"account_id": account_id}
    )

    if not result:
        return None

    hub_data = result[0]["hub"]
    linked = result[0]["linked_strategies"]

    # Build rollup_strategies map
    rollup_strategies = {}
    for link in linked:
        if link["type"] == "INCREASES_PROBLEM_AWARENESS_BY":
            rollup_strategies["problem_awareness"] = link["node_id"]
        elif link["type"] == "INCREASES_BRAND_AWARENESS_BY":
            rollup_strategies["brand_awareness"] = link["node_id"]
        elif link["type"] == "INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY":
            rollup_strategies["consideration"] = link["node_id"]
        elif link["type"] == "INCREASES_PAYING_CUSTOMERS_BY":
            rollup_strategies["conversion"] = link["node_id"]
        elif link["type"] == "INCREASES_LOYAL_CUSTOMERS_BY":
            rollup_strategies["loyalty"] = link["node_id"]

    hub_data["rollup_strategies"] = rollup_strategies
    return hub_data


async def create_rollup_marketing_hub(
    self,
    account_id: str,
    data: dict,
    user_id: str,
) -> dict:
    """Create a new RollupMarketingStrategy hub node."""
    node_id = f"rollup_marketing_hub_{account_id}"

    node_data = {
        "node_id": node_id,
        "description": data["description"],
        "created_time": datetime.now().isoformat(),
        "last_modified": datetime.now().isoformat(),
        "created_by": user_id,
        "last_modified_by": user_id,
        "embedding": None,
    }

    self.neo4j_ops.create_strategy_node(
        "RollupMarketingStrategy",
        node_data,
        account_id
    )

    # Link to Account
    link_query = """
    MATCH (hub:RollupMarketingStrategy {node_id: $node_id})
    MATCH (acc:Account {account_id: $account_id})
    MERGE (hub)-[:INCREASES_CUSTOMERS_BY]->(acc)
    """
    self.neo4j_connection.execute_query(
        link_query,
        {"node_id": node_id, "account_id": account_id}
    )

    return node_data


async def update_rollup_marketing_hub(
    self,
    account_id: str,
    node_id: str,
    updates: dict,
    user_id: str,
) -> dict:
    """Update an existing RollupMarketingStrategy hub node."""
    return self.neo4j_ops.update_strategy_node(node_id, updates, user_id)


async def delete_rollup_marketing_hub(
    self,
    account_id: str,
    node_id: str,
) -> bool:
    """
    Delete RollupMarketingStrategy hub node.

    Note: This will NOT cascade delete rollup strategies.
    Only deletes the hub and its relationships.
    """
    query = """
    MATCH (hub:RollupMarketingStrategy {node_id: $node_id})
    MATCH (hub)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    DETACH DELETE hub
    RETURN count(hub) as deleted
    """

    result = self.neo4j_connection.execute_query(
        query,
        {"node_id": node_id, "account_id": account_id}
    )

    return result[0]["deleted"] > 0 if result else False


async def list_rollup_strategies_by_type(
    self,
    account_id: str,
    strategy_type: str,  # e.g., "ProblemAwarenessStrategy"
    skip: int = 0,
    limit: int | None = None,
) -> dict:
    """
    List rollup strategies of a specific type for an account.

    Only returns rollup strategies (node_id starts with 'rollup_').
    """
    query = """
    MATCH (strategy:{strategy_type})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    WHERE strategy.node_id STARTS WITH 'rollup_'
    OPTIONAL MATCH (strategy)-[:CAN_BE_CUSTOMIZED_BY]->(individual)
    WITH strategy, count(individual) as individual_count
    ORDER BY strategy.created_time DESC
    SKIP $skip
    """

    if limit:
        query += " LIMIT $limit"

    query += " RETURN strategy, individual_count"

    # Get total count
    count_query = """
    MATCH (strategy:{strategy_type})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    WHERE strategy.node_id STARTS WITH 'rollup_'
    RETURN count(strategy) as total
    """

    results = self.neo4j_connection.execute_query(
        query.replace("{strategy_type}", strategy_type),
        {"account_id": account_id, "skip": skip, "limit": limit}
    )

    count_result = self.neo4j_connection.execute_query(
        count_query.replace("{strategy_type}", strategy_type),
        {"account_id": account_id}
    )

    items = []
    for record in results:
        strategy_data = record["strategy"]
        strategy_data["individual_strategy_count"] = record["individual_count"]
        items.append(strategy_data)

    total = count_result[0]["total"] if count_result else 0

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


async def get_rollup_strategy_with_individuals(
    self,
    account_id: str,
    node_id: str,
    strategy_type: str,
) -> dict | None:
    """
    Get a rollup strategy node with its linked individual strategies.

    Args:
        account_id: Account identifier
        node_id: Rollup strategy node_id
        strategy_type: Strategy node type (e.g., "ProblemAwarenessStrategy")

    Returns:
        Rollup strategy with list of individual strategy node_ids
    """
    query = """
    MATCH (rollup:{strategy_type} {node_id: $node_id})
    MATCH (rollup)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    OPTIONAL MATCH (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual:{strategy_type})
    RETURN rollup, collect(individual.node_id) as individual_ids
    """

    result = self.neo4j_connection.execute_query(
        query.replace("{strategy_type}", strategy_type),
        {"node_id": node_id, "account_id": account_id}
    )

    if not result:
        return None

    rollup_data = result[0]["rollup"]
    rollup_data["linked_individual_strategies"] = result[0]["individual_ids"]
    return rollup_data
```

### C. Router Endpoints

**File**: `api/src/kene_api/routers/knowledge_graph/marketing.py`

Add these endpoints at the end:

```python
# ==================== ROLLUP MARKETING STRATEGY HUB ENDPOINTS ====================

@router.post(
    "/{account_id}/rollup-marketing-strategy",
    response_model=RollupMarketingStrategyResponse
)
async def create_rollup_marketing_hub(
    account_id: str,
    hub_data: RollupMarketingStrategyCreate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RollupMarketingStrategyResponse:
    """
    Create a new RollupMarketingStrategy hub node.

    Requires edit permission for the account.

    Note: This is typically auto-generated during account setup.
    Manual creation is only needed if regenerating the rollup.
    """
    return await CRUDEndpoints.create_node(
        account_id=account_id,
        node_type="RollupMarketingStrategy",
        create_data=hub_data,
        service_method=service.create_rollup_marketing_hub,
        service=service,
        user=user,
    )


@router.get(
    "/{account_id}/rollup-marketing-strategy",
    response_model=RollupMarketingStrategyResponse
)
async def get_rollup_marketing_hub(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RollupMarketingStrategyResponse:
    """
    Get the RollupMarketingStrategy hub node for an account.

    Returns the hub with links to all 5 rollup strategy nodes.
    """
    # Verify user has access to account
    await user.check_account_access(account_id, "view")

    hub = await service.get_rollup_marketing_hub(account_id)

    if not hub:
        raise HTTPException(
            status_code=404,
            detail=f"RollupMarketingStrategy hub not found for account {account_id}"
        )

    return RollupMarketingStrategyResponse(**hub)


@router.patch(
    "/{account_id}/rollup-marketing-strategy/{node_id}",
    response_model=RollupMarketingStrategyResponse
)
async def update_rollup_marketing_hub(
    account_id: str,
    node_id: str,
    updates: RollupMarketingStrategyUpdate,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> RollupMarketingStrategyResponse:
    """Update the RollupMarketingStrategy hub node."""
    return await CRUDEndpoints.update_node(
        account_id=account_id,
        node_id=node_id,
        node_type="RollupMarketingStrategy",
        update_data=updates,
        service_method=service.update_rollup_marketing_hub,
        service=service,
        user=user,
    )


@router.delete(
    "/{account_id}/rollup-marketing-strategy/{node_id}",
    response_model=DeleteResponse
)
async def delete_rollup_marketing_hub(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> DeleteResponse:
    """
    Delete the RollupMarketingStrategy hub node.

    Warning: This does NOT cascade delete the rollup strategies.
    To fully remove rollups, delete individual rollup strategies separately.
    """
    return await CRUDEndpoints.delete_node(
        account_id=account_id,
        node_id=node_id,
        node_type="RollupMarketingStrategy",
        service_method=service.delete_rollup_marketing_hub,
        service=service,
        user=user,
    )


# ==================== ROLLUP STRATEGY ENDPOINTS ====================
# These endpoints list/get/update/delete the rollup versions of strategies
# (distinguished by node_id starting with 'rollup_')

@router.get(
    "/{account_id}/rollup-problem-awareness-strategies",
    response_model=ProblemAwarenessStrategyListResponse
)
async def list_rollup_problem_awareness_strategies(
    account_id: str,
    skip: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyListResponse:
    """
    List rollup problem awareness strategies for an account.

    Only returns rollup strategies (node_id starts with 'rollup_').
    Typically there will be 0 or 1 rollup strategy per account.
    """
    await user.check_account_access(account_id, "view")

    result = await service.list_rollup_strategies_by_type(
        account_id=account_id,
        strategy_type="ProblemAwarenessStrategy",
        skip=skip,
        limit=limit,
    )

    return ProblemAwarenessStrategyListResponse(**result)


@router.get(
    "/{account_id}/rollup-problem-awareness-strategies/{node_id}",
    response_model=ProblemAwarenessStrategyResponse
)
async def get_rollup_problem_awareness_strategy(
    account_id: str,
    node_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
) -> ProblemAwarenessStrategyResponse:
    """
    Get a rollup problem awareness strategy with its linked individual strategies.
    """
    await user.check_account_access(account_id, "view")

    strategy = await service.get_rollup_strategy_with_individuals(
        account_id=account_id,
        node_id=node_id,
        strategy_type="ProblemAwarenessStrategy",
    )

    if not strategy:
        raise HTTPException(
            status_code=404,
            detail=f"Rollup problem awareness strategy {node_id} not found"
        )

    return ProblemAwarenessStrategyResponse(**strategy)


# Repeat for other 4 strategy types:
# - rollup-brand-awareness-strategies
# - rollup-consideration-strategies
# - rollup-conversion-strategies
# - rollup-loyalty-strategies
# (Following same pattern as above)
```

### D. API Tests

**File**: `api/tests/routers/knowledge_graph/test_marketing_rollup_endpoints.py` (NEW)

Create comprehensive tests:

```python
"""Tests for rollup marketing strategy API endpoints."""

import pytest
from fastapi import status


class TestRollupMarketingHub:
    """Tests for RollupMarketingStrategy hub endpoints."""

    async def test_get_rollup_hub_success(
        self,
        client,
        auth_headers,
        sample_account_id,
    ):
        """Test GET rollup marketing hub returns hub with linked strategies."""
        response = await client.get(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-marketing-strategy",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["node_id"] == f"rollup_marketing_hub_{sample_account_id}"
        assert "rollup_strategies" in data
        assert "problem_awareness" in data["rollup_strategies"]

    async def test_get_rollup_hub_not_found(
        self,
        client,
        auth_headers,
    ):
        """Test GET rollup hub returns 404 if not created yet."""
        response = await client.get(
            f"/knowledge-graph/marketing/nonexistent_account/rollup-marketing-strategy",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_rollup_hub(
        self,
        client,
        auth_headers,
        sample_account_id,
    ):
        """Test POST creates rollup marketing hub."""
        response = await client.post(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-marketing-strategy",
            headers=auth_headers,
            json={
                "description": "Test rollup marketing strategy"
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        assert data["node_id"].startswith("rollup_marketing_hub_")
        assert data["description"] == "Test rollup marketing strategy"

    async def test_update_rollup_hub(
        self,
        client,
        auth_headers,
        sample_account_id,
        existing_rollup_hub_node_id,
    ):
        """Test PATCH updates rollup hub description."""
        response = await client.patch(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-marketing-strategy/{existing_rollup_hub_node_id}",
            headers=auth_headers,
            json={
                "description": "Updated rollup description"
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["description"] == "Updated rollup description"

    async def test_delete_rollup_hub(
        self,
        client,
        auth_headers,
        sample_account_id,
        existing_rollup_hub_node_id,
    ):
        """Test DELETE removes rollup hub."""
        response = await client.delete(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-marketing-strategy/{existing_rollup_hub_node_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify it's deleted
        get_response = await client.get(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-marketing-strategy",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND


class TestRollupStrategies:
    """Tests for rollup strategy endpoints."""

    async def test_list_rollup_problem_awareness_strategies(
        self,
        client,
        auth_headers,
        sample_account_id,
    ):
        """Test listing rollup problem awareness strategies."""
        response = await client.get(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-problem-awareness-strategies",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "items" in data
        assert data["total"] >= 0

        # If rollup exists, verify it has correct structure
        if data["total"] > 0:
            rollup = data["items"][0]
            assert rollup["node_id"].startswith("rollup_problemaware_")
            assert "individual_strategy_count" in rollup

    async def test_get_rollup_strategy_with_individuals(
        self,
        client,
        auth_headers,
        sample_account_id,
        existing_rollup_problem_awareness_node_id,
    ):
        """Test getting rollup strategy includes linked individual strategies."""
        response = await client.get(
            f"/knowledge-graph/marketing/{sample_account_id}/rollup-problem-awareness-strategies/{existing_rollup_problem_awareness_node_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "linked_individual_strategies" in data
        assert isinstance(data["linked_individual_strategies"], list)
        assert len(data["linked_individual_strategies"]) > 0

    async def test_rollup_strategies_excluded_from_regular_list(
        self,
        client,
        auth_headers,
        sample_account_id,
    ):
        """Test that rollup strategies don't appear in regular strategy lists."""
        # List regular problem awareness strategies
        response = await client.get(
            f"/knowledge-graph/marketing/{sample_account_id}/problem-awareness-strategies",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify no rollup strategies (node_id starting with 'rollup_') in results
        for strategy in data["items"]:
            assert not strategy["node_id"].startswith("rollup_")
```

---

## Testing Strategy

### Unit Tests

**File**: `app/adk/agents/strategy_agent/tests/test_marketing_graph_builder.py`

Add these test cases:

```python
def test_create_rollup_marketing_hub(graph_builder, mock_neo4j_ops):
    """Test that rollup marketing hub is created correctly."""
    account_id = "test_acc_123"
    user_id = "user_456"

    hub_node = graph_builder._create_rollup_marketing_hub(account_id, user_id)

    # Verify node structure
    assert hub_node["node_id"] == f"rollup_marketing_hub_{account_id}"
    assert hub_node["description"]
    assert hub_node["created_by"] == user_id

    # Verify create_strategy_node was called
    mock_neo4j_ops.create_strategy_node.assert_called_once()
    call_args = mock_neo4j_ops.create_strategy_node.call_args
    assert call_args[0][0] == "RollupMarketingStrategy"

    # Verify link to Account was created
    assert mock_neo4j_ops.connection.execute_query.called


def test_create_single_rollup_strategy(graph_builder, mock_neo4j_ops):
    """Test creating a single rollup strategy node."""
    config = {
        "stage": "problem_awareness",
        "node_type": "ProblemAwarenessStrategy",
        "hub_relationship": "INCREASES_PROBLEM_AWARENESS_BY",
    }

    individual_strategies = [
        {"node_id": "pas_1", "description": "Strategy 1 for profile A"},
        {"node_id": "pas_2", "description": "Strategy 2 for profile B"},
        {"node_id": "pas_3", "description": "Strategy 3 for profile C"},
    ]

    hub_node_id = "rollup_marketing_hub_test_acc"
    account_id = "test_acc_123"
    user_id = "user_456"

    rollup_node = graph_builder._create_single_rollup_strategy(
        config=config,
        individual_strategies=individual_strategies,
        hub_node_id=hub_node_id,
        account_id=account_id,
        user_id=user_id,
    )

    # Verify node structure
    assert rollup_node["node_id"] == f"rollup_problemaware_{account_id}"
    assert rollup_node["description"]
    assert len(rollup_node["description"]) > 0

    # Verify relationships created (hub link + individual links)
    assert mock_neo4j_ops.connection.execute_query.call_count >= 2


def test_rollup_strategy_has_empty_description(graph_builder, mock_neo4j_ops):
    """Test that rollup strategies are created with empty descriptions for MVP."""
    config = {
        "stage": "problem_awareness",
        "node_type": "ProblemAwarenessStrategy",
        "hub_relationship": "INCREASES_PROBLEM_AWARENESS_BY",
    }

    individual_strategies = [
        {"node_id": "pas_1", "description": "Strategy 1 with content"},
        {"node_id": "pas_2", "description": "Strategy 2 with content"},
    ]

    rollup_node = graph_builder._create_single_rollup_strategy(
        config=config,
        individual_strategies=individual_strategies,
        hub_node_id="rollup_marketing_hub_test",
        account_id="test_acc",
        user_id="test_user",
    )

    # Verify description is empty string
    assert rollup_node["description"] == ""
    # Verify references is empty list
    assert rollup_node["references"] == []


def test_create_rollup_strategies_success(
    graph_builder,
    mock_neo4j_ops,
    sample_marketing_report,
):
    """Test full rollup strategy creation flow."""
    account_id = "test_acc_123"
    user_id = "user_456"

    # Create individual strategies first
    created_nodes = {
        "problem_awareness_strategies": [
            {"node_id": "pas_1", "description": "Strategy 1"},
            {"node_id": "pas_2", "description": "Strategy 2"},
        ],
        "brand_awareness_strategies": [
            {"node_id": "bas_1", "description": "Brand 1"},
        ],
        "consideration_strategies": [
            {"node_id": "cs_1", "description": "Consideration 1"},
        ],
        "conversion_strategies": [
            {"node_id": "cvs_1", "description": "Conversion 1"},
        ],
        "loyalty_strategies": [
            {"node_id": "ls_1", "description": "Loyalty 1"},
        ],
    }

    rollup_nodes = graph_builder._create_rollup_strategies(
        research_report=sample_marketing_report,
        account_id=account_id,
        user_id=user_id,
        created_nodes=created_nodes,
    )

    # Verify structure
    assert "hub" in rollup_nodes
    assert "strategies" in rollup_nodes

    # Verify hub
    assert rollup_nodes["hub"]["node_id"] == f"rollup_marketing_hub_{account_id}"

    # Verify 5 rollup strategies created
    assert len(rollup_nodes["strategies"]) == 5
    assert "problem_awareness" in rollup_nodes["strategies"]
    assert "brand_awareness" in rollup_nodes["strategies"]
    assert "consideration" in rollup_nodes["strategies"]
    assert "conversion" in rollup_nodes["strategies"]
    assert "loyalty" in rollup_nodes["strategies"]


def test_create_rollup_strategies_fails_without_individuals(
    graph_builder,
    sample_marketing_report,
):
    """Test that rollup creation fails if individual strategies don't exist."""
    account_id = "test_acc_123"
    user_id = "user_456"

    # Empty created_nodes
    created_nodes = {
        "problem_awareness_strategies": [],  # Empty!
        "brand_awareness_strategies": [],
        "consideration_strategies": [],
        "conversion_strategies": [],
        "loyalty_strategies": [],
    }

    with pytest.raises(ValueError, match="Cannot create rollup strategies"):
        graph_builder._create_rollup_strategies(
            research_report=sample_marketing_report,
            account_id=account_id,
            user_id=user_id,
            created_nodes=created_nodes,
        )


def test_build_marketing_graph_includes_rollups(
    graph_builder,
    mock_neo4j_ops,
    sample_marketing_report,
):
    """Test that build_marketing_graph creates rollups in Phase 3."""
    account_id = "test_acc_789"
    user_id = "user_123"

    # Mock product categories exist
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Cloud Services", "node_id": "pc_001"},
    ]

    result = graph_builder.build_marketing_graph(
        sample_marketing_report,
        account_id,
        user_id,
    )

    # Verify rollups were created
    assert "rollup_marketing_hub" in result
    assert "rollup_strategies" in result

    # Verify hub exists
    assert result["rollup_marketing_hub"] is not None
    assert result["rollup_marketing_hub"]["node_id"].startswith("rollup_marketing_hub_")

    # Verify 5 rollup strategies
    assert len(result["rollup_strategies"]) == 5


def test_build_marketing_graph_rollup_failure_is_non_critical(
    graph_builder,
    mock_neo4j_ops,
    sample_marketing_report,
    caplog,
):
    """Test that rollup creation failure doesn't fail entire graph build."""
    account_id = "test_acc_999"
    user_id = "user_999"

    # Mock product categories
    mock_neo4j_ops.connection.execute_query.return_value = [
        {"category_name": "Cloud Services", "node_id": "pc_001"},
    ]

    # Mock rollup creation to fail
    def side_effect(*args, **kwargs):
        if "RollupMarketingStrategy" in str(args):
            raise Exception("Rollup creation failed!")
        return []

    mock_neo4j_ops.create_strategy_node.side_effect = side_effect

    # Should NOT raise exception
    result = graph_builder.build_marketing_graph(
        sample_marketing_report,
        account_id,
        user_id,
    )

    # Verify individual strategies still created
    assert len(result["problem_awareness_strategies"]) > 0

    # Verify warning was logged
    assert "Failed to create rollup strategies" in caplog.text
```

### Integration Tests

**File**: `app/adk/agents/strategy_agent/tests/neo4j/test_marketing_neo4j.py`

Add integration test:

```python
def test_end_to_end_with_rollups(self, neo4j_connection):
    """
    Test complete marketing graph creation including rollup strategies.

    Verifies:
    1. Individual strategies created
    2. Rollup hub created
    3. Rollup strategies created
    4. All relationships exist
    5. Rollup strategies link to individuals via CAN_BE_CUSTOMIZED_BY
    """
    account_id = f"test_rollup_{uuid.uuid4().hex[:8]}"

    # Create sample marketing report
    report = create_sample_marketing_report()

    # Build graph (includes rollups)
    graph_nodes = self.graph_builder.build_marketing_graph(
        report,
        account_id,
        "test_user",
    )

    try:
        # Verify rollup hub created
        hub_query = """
        MATCH (hub:RollupMarketingStrategy)-[:INCREASES_CUSTOMERS_BY]->(acc:Account {account_id: $account_id})
        RETURN hub
        """
        hub_result = neo4j_connection.execute_query(hub_query, {"account_id": account_id})
        assert len(hub_result) == 1
        hub_node = hub_result[0]["hub"]
        assert hub_node["node_id"] == f"rollup_marketing_hub_{account_id}"

        # Verify 5 rollup strategies created
        rollup_query = """
        MATCH (hub:RollupMarketingStrategy {node_id: $hub_id})
        MATCH (hub)-[r]->(rollup:Strategy)
        WHERE type(r) STARTS WITH 'INCREASES_'
        RETURN type(r) as relationship_type, rollup
        """
        rollup_result = neo4j_connection.execute_query(
            rollup_query,
            {"hub_id": hub_node["node_id"]}
        )
        assert len(rollup_result) == 5

        # Verify each rollup strategy links to individual strategies
        for rollup_record in rollup_result:
            rollup = rollup_record["rollup"]

            customization_query = """
            MATCH (rollup:Strategy {node_id: $rollup_id})
            MATCH (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual:Strategy)
            RETURN count(individual) as count
            """
            custom_result = neo4j_connection.execute_query(
                customization_query,
                {"rollup_id": rollup["node_id"]}
            )

            # Each rollup should link to at least 1 individual strategy
            assert custom_result[0]["count"] > 0

        # Verify rollup strategies have summaries
        for stage in ["problem_awareness", "brand_awareness", "consideration", "conversion", "loyalty"]:
            rollup_strategy = graph_nodes["rollup_strategies"][stage]
            assert rollup_strategy["description"]
            assert len(rollup_strategy["description"]) > 0
            assert rollup_strategy["description"] != "No strategies defined."

    finally:
        # Cleanup
        cleanup_query = """
        MATCH (n)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        DETACH DELETE n
        """
        neo4j_connection.execute_query(cleanup_query, {"account_id": account_id})
```

---

## Files to Modify

### Core Implementation

1. **`app/adk/agents/strategy_agent/marketing_graph_builder.py`** ⭐
   - Update `build_marketing_graph()` - add Phase 3
   - Add `_create_rollup_strategies()`
   - Add `_create_rollup_marketing_hub()`
   - Add `_create_single_rollup_strategy()`
   - ~~Add `_summarize_strategy_descriptions()`~~ (NOT NEEDED for MVP)

### API Layer

2. **`api/src/kene_api/models/graph_models.py`**
   - Add `RollupMarketingStrategyBase`
   - Add `RollupMarketingStrategyCreate`
   - Add `RollupMarketingStrategyUpdate`
   - Add `RollupMarketingStrategyResponse`
   - Add `RollupMarketingStrategyListResponse`

3. **`api/src/kene_api/services/graph_sync_service.py`**
   - Add `get_rollup_marketing_hub()`
   - Add `create_rollup_marketing_hub()`
   - Add `update_rollup_marketing_hub()`
   - Add `delete_rollup_marketing_hub()`
   - Add `list_rollup_strategies_by_type()`
   - Add `get_rollup_strategy_with_individuals()`

4. **`api/src/kene_api/routers/knowledge_graph/marketing.py`**
   - Add rollup hub endpoints (POST, GET, PATCH, DELETE)
   - Add rollup strategy list endpoints (GET for each type)
   - Add rollup strategy get endpoints (GET by node_id)

### Testing

5. **`app/adk/agents/strategy_agent/tests/test_marketing_graph_builder.py`**
   - Add unit tests for all rollup methods (10+ tests)

6. **`app/adk/agents/strategy_agent/tests/neo4j/test_marketing_neo4j.py`**
   - Add integration test `test_end_to_end_with_rollups()`

7. **`api/tests/routers/knowledge_graph/test_marketing_rollup_endpoints.py`** (NEW)
   - Add API endpoint tests (10+ tests)

### Documentation

8. **`knowledge_graph/marketing_requirements.md`**
   - Add RollupMarketingStrategy hub node specification
   - Document relationship types
   - Add examples

9. **`ROLLUP_MARKETING_STRATEGY_IMPLEMENTATION_PLAN.md`** (THIS FILE)
   - Keep as reference during implementation

---

## Implementation Checklist

### Phase 1: Core Graph Builder (2-3 hours)

- [ ] **Update `marketing_graph_builder.py`**
  - [ ] Add `_create_rollup_strategies()` method
  - [ ] Add `_create_rollup_marketing_hub()` method
  - [ ] Add `_create_single_rollup_strategy()` method
  - [ ] ~~Add `_summarize_strategy_descriptions()` helper~~ (NOT NEEDED - empty descriptions for MVP)
  - [ ] Update `build_marketing_graph()` - add Phase 3 call
  - [ ] Add try/except for rollup creation (non-critical failure)
  - [ ] Update `created_nodes` dict to include rollup tracking

- [ ] **Unit Tests**
  - [ ] Test `_create_rollup_marketing_hub()` creates hub and links to account
  - [ ] Test `_create_single_rollup_strategy()` creates node and relationships
  - [ ] Test `_create_single_rollup_strategy()` creates node with empty description
  - [ ] Test `_create_rollup_strategies()` creates all 5 rollup strategies
  - [ ] Test rollup creation fails gracefully without individual strategies
  - [ ] Test `build_marketing_graph()` includes rollups in returned dict
  - [ ] Test rollup failure doesn't break entire graph build

- [ ] **Integration Test**
  - [ ] Add `test_end_to_end_with_rollups()` in `test_marketing_neo4j.py`
  - [ ] Verify all nodes and relationships created in Neo4j
  - [ ] Verify `[:CAN_BE_CUSTOMIZED_BY]` relationships exist
  - [ ] Test with real Neo4j instance

### Phase 2: API Models (30 min)

- [ ] **Update `graph_models.py`**
  - [ ] Add `RollupMarketingStrategyBase`
  - [ ] Add `RollupMarketingStrategyCreate`
  - [ ] Add `RollupMarketingStrategyUpdate`
  - [ ] Add `RollupMarketingStrategyResponse`
  - [ ] Add `RollupMarketingStrategyListResponse`

### Phase 3: Service Layer (1 hour)

- [ ] **Update `graph_sync_service.py`**
  - [ ] Add `get_rollup_marketing_hub()`
  - [ ] Add `create_rollup_marketing_hub()`
  - [ ] Add `update_rollup_marketing_hub()`
  - [ ] Add `delete_rollup_marketing_hub()`
  - [ ] Add `list_rollup_strategies_by_type()`
  - [ ] Add `get_rollup_strategy_with_individuals()`

### Phase 4: API Endpoints (1-2 hours)

- [ ] **Update `marketing.py` router**
  - [ ] Add `POST /{account_id}/rollup-marketing-strategy`
  - [ ] Add `GET /{account_id}/rollup-marketing-strategy`
  - [ ] Add `PATCH /{account_id}/rollup-marketing-strategy/{node_id}`
  - [ ] Add `DELETE /{account_id}/rollup-marketing-strategy/{node_id}`
  - [ ] Add `GET /{account_id}/rollup-problem-awareness-strategies`
  - [ ] Add `GET /{account_id}/rollup-problem-awareness-strategies/{node_id}`
  - [ ] Add endpoints for other 4 rollup strategy types

- [ ] **API Tests**
  - [ ] Create `test_marketing_rollup_endpoints.py`
  - [ ] Test GET hub returns hub with linked strategies
  - [ ] Test GET hub returns 404 if not found
  - [ ] Test POST creates hub
  - [ ] Test PATCH updates hub
  - [ ] Test DELETE removes hub
  - [ ] Test list rollup strategies endpoint
  - [ ] Test get single rollup strategy with individuals
  - [ ] Test rollup strategies excluded from regular lists

### Phase 5: Documentation (30 min)

- [ ] **Update `marketing_requirements.md`**
  - [ ] Add RollupMarketingStrategy node specification
  - [ ] Document new relationship types
  - [ ] Add graph structure diagrams
  - [ ] Add query examples

- [ ] **Cleanup**
  - [ ] Remove temporary exploration docs (README_MARKETING_ROLLUP.md, etc.)
  - [ ] Verify all code follows CLAUDE.md best practices

### Phase 6: End-to-End Verification (30 min)

- [ ] **Manual Testing**
  - [ ] Create new account via API
  - [ ] Verify rollup hub and strategies created automatically
  - [ ] Test GET endpoints return rollup data
  - [ ] Test UPDATE endpoints modify rollups
  - [ ] Verify individual strategies still work correctly

- [ ] **Run Full Test Suite**
  - [ ] `cd app && pytest tests/` - all agent tests pass
  - [ ] `cd api && pytest tests/` - all API tests pass
  - [ ] `make lint` - code quality checks pass
  - [ ] `npm run typecheck` (frontend) - no type errors

---

## Design Decisions & Rationale

### 1. Why Create Rollups in Graph Builder (Not Researcher/Formatter)?

**Decision**: Create rollups in `MarketingGraphBuilder` after individual strategies exist.

**Rationale**:
- **Timing**: Individual strategies don't exist when researcher/formatter run
- **Separation of concerns**:
  - Researcher = external data gathering
  - Formatter = structuring external data
  - Graph builder = internal data transformation
- **No schema changes**: Keeps `MarketingResearchReport` Pydantic model stable
- **Architectural fit**: Rollups are graph enrichment, not external research

### 2. Why Use Same Node Types (Not Separate RollupProblemAwarenessStrategy)?

**Decision**: Rollup strategies use same types as individual strategies (`ProblemAwarenessStrategy:Strategy`), distinguished by `node_id` pattern.

**Rationale**:
- **Consistency**: All problem awareness strategies (individual or rollup) have same properties
- **Embedding generation**: Rollups can participate in semantic search like individuals
- **Query simplicity**: Can query all strategies of a type with single label match
- **Less code**: Reuse existing Pydantic models and service methods

**Alternative considered**: Create separate node types like `RollupProblemAwarenessStrategy`
- Rejected because it duplicates code and makes queries more complex

### 3. Why Option B (Full CRUD) for API?

**Decision**: Provide full CREATE, READ, UPDATE, DELETE endpoints for rollup strategies.

**Rationale**:
- **User requested**: Explicit requirement from user
- **Flexibility**: Allows manual editing/customization of rollups
- **Consistency**: Matches existing API pattern for all other strategy types
- **Future-proof**: Enables advanced features (manual regeneration, A/B testing, etc.)

**Trade-off**: More complex than read-only, but provides needed flexibility.

### 4. Why Deterministic Node IDs (Not UUIDs)?

**Decision**: Use deterministic IDs like `rollup_problemaware_{account_id}`.

**Rationale**:
- **Idempotency**: `MERGE` will work correctly if called multiple times
- **Easy querying**: Can construct node_id without database lookup
- **One rollup per account**: Ensures only one rollup exists per account
- **Testing**: Predictable IDs make tests easier to write

### 5. Why Empty Descriptions (Not Text Summarization or LLM)?

**Decision**: Create rollup strategies with **empty description fields** for MVP.

**Rationale**:
- **Simplicity**: No summarization logic needed
- **Speed**: Instant creation, no processing time
- **Cost**: Free (no API calls)
- **Flexibility**: Users can populate via API PATCH with their own summaries
- **Extensibility**: Future enhancement can add automated summarization without breaking existing rollups

**Alternatives Considered**:
1. **Simple text extraction**: Combine first N chars from each strategy
   - Rejected: User feedback indicated this adds unnecessary complexity for MVP
2. **LLM summarization**: Call LLM to create quality summaries
   - Rejected: Slower, more expensive, overly complex for MVP

**Future Enhancement Path**:
- Add API endpoint to regenerate descriptions from individuals
- Add LLM-powered summarization tool
- Add batch update utility for existing rollups

### 6. Why Non-Critical Rollup Creation?

**Decision**: Rollup creation failure logs warning but doesn't fail graph build.

**Rationale**:
- **Core functionality preserved**: Individual strategies are the source of truth
- **Rollups are enhancement**: Nice to have, not essential
- **Better UX**: User gets strategies even if rollup fails
- **Debuggable**: Warnings logged for investigation

**Pattern**: Matches embedding generation behavior (optional enhancement).

---

## Future Enhancements

### 1. Automated Description Population

**Improvement**: Add automated description generation for rollup strategies.

**Options**:

**Option A: Simple Text Aggregation**
```python
def populate_rollup_descriptions(self, account_id: str) -> None:
    """Populate empty rollup descriptions with aggregated text from individuals."""
    # For each rollup strategy
    # - Fetch all linked individual strategies
    # - Extract key points (first 200 chars from each)
    # - Combine and store in rollup description field
```

**Option B: LLM-Enhanced Summarization**
```python
def generate_llm_rollup_summary(
    self,
    individual_strategies: list[dict],
    stage: str,
) -> str:
    """Use LLM to create consolidated summary."""
    prompt = f"""
    You are summarizing {len(individual_strategies)} {stage} marketing strategies
    into a single consolidated strategy for the entire business.

    Individual strategies:
    {chr(10).join(f"{i+1}. {s['description'][:500]}" for i, s in enumerate(individual_strategies))}

    Create a consolidated summary (300-500 words) that:
    1. Identifies common themes across all strategies
    2. Highlights unique approaches for different customer segments
    3. Provides actionable guidance for the overall business
    """

    # Call LLM (Gemini or OpenAI)
    summary = call_llm(prompt)
    return summary
```

**Implementation Paths**:
1. **API Endpoint**: `POST /{account_id}/rollup-marketing-strategy/generate-descriptions`
2. **Batch Script**: Populate descriptions for all existing rollup strategies
3. **Auto-populate**: Add flag to graph builder to populate on creation

**Estimated Effort**: 2-3 hours

### 2. Rollup Regeneration API

**Improvement**: Add endpoint to regenerate rollup strategies on demand.

**Use Case**: After editing individual strategies, regenerate rollup to reflect changes.

**Implementation**:
```python
@router.post(
    "/{account_id}/rollup-marketing-strategy/regenerate",
    response_model=RollupMarketingStrategyResponse
)
async def regenerate_rollup_marketing_strategy(
    account_id: str,
    service: GraphSyncService = Depends(get_graph_sync_service),
    user: UserContext = Depends(get_current_user),
):
    """Regenerate rollup strategies from current individual strategies."""
    # Delete existing rollups
    # Fetch all individual strategies
    # Create new rollups with updated summaries
    pass
```

**Estimated Effort**: 3 hours

### 3. Rollup Diff View

**Improvement**: API endpoint that shows what changed between rollup and individuals.

**Use Case**: See which individual strategies were updated since rollup was created.

**Implementation**:
```python
@router.get(
    "/{account_id}/rollup-marketing-strategy/diff",
    response_model=RollupDiffResponse
)
async def get_rollup_diff(account_id: str):
    """Show differences between rollup and individual strategies."""
    # Compare rollup.last_modified with individual.last_modified
    # Return list of changed strategies
    pass
```

**Estimated Effort**: 2 hours

### 4. Rollup Customization Tracking

**Improvement**: Track which individual strategies influenced which parts of rollup.

**Implementation**: Add metadata to `[:CAN_BE_CUSTOMIZED_BY]` relationships:
```cypher
(rollup)-[:CAN_BE_CUSTOMIZED_BY {
    influence_score: 0.8,
    key_contribution: "Social media focus",
    included_in_summary: true
}]->(individual)
```

**Estimated Effort**: 4 hours

### 5. Multi-Level Rollups

**Improvement**: Create intermediate rollups (by product category or customer profile).

**Structure**:
```
Account
  ├─ Category 1 Rollup
  │   └─ Strategies for all profiles in Category 1
  ├─ Category 2 Rollup
  │   └─ Strategies for all profiles in Category 2
  └─ Overall Rollup (existing)
      └─ Consolidates all category rollups
```

**Estimated Effort**: 6-8 hours

---

## Appendix: Neo4j Relationship Types

### New Relationships Introduced

| Source Node | Relationship | Target Node | Description |
|-------------|--------------|-------------|-------------|
| `RollupMarketingStrategy` | `[:INCREASES_CUSTOMERS_BY]` | `Account` | Links rollup hub to account |
| `RollupMarketingStrategy` | `[:INCREASES_PROBLEM_AWARENESS_BY]` | `ProblemAwarenessStrategy` (rollup) | Links hub to problem awareness rollup |
| `RollupMarketingStrategy` | `[:INCREASES_BRAND_AWARENESS_BY]` | `BrandAwarenessStrategy` (rollup) | Links hub to brand awareness rollup |
| `RollupMarketingStrategy` | `[:INCREASES_CUSTOMERS_CONSIDERING_PURCHASE_BY]` | `ConsiderationStrategy` (rollup) | Links hub to consideration rollup |
| `RollupMarketingStrategy` | `[:INCREASES_PAYING_CUSTOMERS_BY]` | `ConversionStrategy` (rollup) | Links hub to conversion rollup |
| `RollupMarketingStrategy` | `[:INCREASES_LOYAL_CUSTOMERS_BY]` | `LoyaltyStrategy` (rollup) | Links hub to loyalty rollup |
| `ProblemAwarenessStrategy` (rollup) | `[:CAN_BE_CUSTOMIZED_BY]` | `ProblemAwarenessStrategy` (individual) | Links rollup to individual strategies it consolidates |
| `BrandAwarenessStrategy` (rollup) | `[:CAN_BE_CUSTOMIZED_BY]` | `BrandAwarenessStrategy` (individual) | Same for brand awareness |
| `ConsiderationStrategy` (rollup) | `[:CAN_BE_CUSTOMIZED_BY]` | `ConsiderationStrategy` (individual) | Same for consideration |
| `ConversionStrategy` (rollup) | `[:CAN_BE_CUSTOMIZED_BY]` | `ConversionStrategy` (individual) | Same for conversion |
| `LoyaltyStrategy` (rollup) | `[:CAN_BE_CUSTOMIZED_BY]` | `LoyaltyStrategy` (individual) | Same for loyalty |

### Query Examples

**Get rollup hub with all linked strategies:**
```cypher
MATCH (hub:RollupMarketingStrategy)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
OPTIONAL MATCH (hub)-[r]->(rollup:Strategy)
WHERE type(r) STARTS WITH 'INCREASES_'
RETURN hub, collect({type: type(r), strategy: rollup}) as linked_strategies
```

**Get rollup strategy with all individual strategies it consolidates:**
```cypher
MATCH (rollup:ProblemAwarenessStrategy {node_id: $rollup_id})
WHERE rollup.node_id STARTS WITH 'rollup_'
MATCH (rollup)-[:CAN_BE_CUSTOMIZED_BY]->(individual:ProblemAwarenessStrategy)
RETURN rollup, collect(individual) as individual_strategies
```

**Count total strategies vs rollup strategies:**
```cypher
MATCH (acc:Account {account_id: $account_id})
MATCH (acc)<-[:BELONGS_TO]-(strategy:ProblemAwarenessStrategy)
WITH
    count(strategy) as total,
    size([s IN collect(strategy) WHERE s.node_id STARTS WITH 'rollup_']) as rollups
RETURN total, rollups, total - rollups as individuals
```

---

## Implementation Prompt for Future LLM Session

**Use this prompt to start implementation in a new session:**

```
I need to implement the rollup marketing strategy feature as specified in:
/Users/kenwilliams/Documents/github/ken-e/ROLLUP_MARKETING_STRATEGY_IMPLEMENTATION_PLAN.md

Please:
1. Read ROLLUP_MARKETING_STRATEGY_IMPLEMENTATION_PLAN.md completely
2. Review CLAUDE.md for coding best practices
3. Read knowledge_graph/marketing_requirements.md for context
4. Review the current implementation in:
   - app/adk/agents/strategy_agent/marketing_graph_builder.py
   - app/adk/agents/strategy_agent/marketing_models.py
   - api/src/kene_api/routers/knowledge_graph/marketing.py

Then:
1. Confirm you understand the full implementation plan
2. Ask any clarifying questions about the design
3. Follow the Implementation Checklist in the plan document
4. Use qnew, qplan, qcode, and qcheck shortcuts as appropriate
5. Write comprehensive tests following T-1 through T-8 in CLAUDE.md
6. Follow all Python and testing best practices from CLAUDE.md

Key requirements:
- Create rollups in graph builder Phase 3 (NOT in researcher/formatter agents)
- MVP: Create rollup nodes with EMPTY description fields (populate via API later)
- Rollup creation is non-critical (log warning on failure, don't break graph build)
- Implement full CRUD API endpoints (Option B)
- Use deterministic node IDs: rollup_problemaware_{account_id}
- Rollup strategies use SAME node types as individuals (distinguished by node_id)
- Add comprehensive unit and integration tests
- Follow existing patterns in marketing.py for API endpoints

Ready to start?
```

---

**END OF IMPLEMENTATION PLAN**
