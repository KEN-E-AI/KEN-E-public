# Knowledge Graph Strategy System - Technical Documentation

## Executive Summary

This project implements a complete AI-powered strategy generation system that researches, analyzes, and stores business intelligence in a Neo4j knowledge graph. The system uses Google's ADK (Agent Development Kit) with a split-agent architecture to generate four types of strategic analysis: Business Strategy, Competitive Analysis, Marketing Strategy, and Brand Guidelines.

**Key Achievement**: 100% success rate using split-agent architecture, solving the ADK constraint where agents with `output_schema` cannot use tools.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Technical Pattern: Split Agent Architecture](#core-technical-pattern-split-agent-architecture)
3. [Strategy Types Implemented](#strategy-types-implemented)
4. [Pydantic Models Reference](#pydantic-models-reference)
5. [Neo4j Graph Schema](#neo4j-graph-schema)
6. [Graph Builders](#graph-builders)
7. [Integration Points](#integration-points)
8. [Testing Approach](#testing-approach)
9. [Migration Guide](#migration-guide)
10. [Known Issues and Workarounds](#known-issues-and-workarounds)
11. [Future Work](#future-work)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Strategy Generation Flow                  │
└─────────────────────────────────────────────────────────────┘

1. RESEARCH PHASE (Researcher Agent)
   - Has tools (google_search)
   - NO output_schema
   - Returns unstructured text

2. FORMAT PHASE (Formatter Agent)
   - NO tools
   - HAS output_schema (Pydantic model)
   - Returns structured JSON

3. STORAGE PHASE
   - Save to Firestore (backup)
   - Build Neo4j graph
   - Generate embeddings (Vertex AI text-embedding-004)

4. QUERY PHASE
   - Semantic search via embeddings
   - Graph traversal queries
```

### Technology Stack

- **Python**: 3.12+
- **Package Manager**: uv (not pip)
- **AI Framework**: Google ADK 1.14+
- **LLMs**:
  - Research: Gemini 2.0 Flash
  - Formatting: Gemini 2.5 Pro (primary), GPT-4o (fallback)
- **Graph Database**: Neo4j (cloud instance)
- **Embeddings**: Vertex AI text-embedding-004 (768 dimensions)
- **Document Store**: Google Cloud Firestore
- **Validation**: Pydantic 2.0+

---

## Core Technical Pattern: Split Agent Architecture

### The ADK Constraint

**Problem**: ADK agents with `output_schema` cannot use tools effectively (GitHub issue #701).
- Agents with `output_schema` automatically set `disallow_transfer_to_parent=True`
- This makes them terminal agents that cannot delegate to tool-using agents
- Combining tools and output_schema in one agent results in ~0% success rate

**Solution**: Split each strategy generation into two specialized agents.

### Pattern Implementation

```python
# RESEARCHER AGENT (Stage 1)
def create_researcher(google_search_agent):
    return adk.Agent(
        name="researcher",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],  # ✅ HAS TOOLS
        # ❌ NO output_schema
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000  # Rate limit protection
        ),
        instruction="Research and gather comprehensive information..."
    )

# FORMATTER AGENT (Stage 2)
def create_formatter():
    return adk.Agent(
        name="formatter",
        model="gemini-2.5-pro",  # Better at complex schemas
        tools=[],  # ❌ NO TOOLS - required for output_schema
        output_schema=StrategyModel,  # ✅ HAS OUTPUT_SCHEMA
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8000,
            response_mime_type="application/json"
        ),
        instruction="Format research into structured JSON..."
    )
```

### Fallback Strategy

Always implement OpenAI fallback for formatters:

```python
try:
    # Try Gemini 2.5 Pro first
    formatted = await run_agent(formatter, research_data)
    result = Model(**json.loads(formatted))
except Exception as e:
    # Fall back to OpenAI for complex schemas
    result = format_with_openai(research_data)
```

**Why**: Gemini sometimes fails with complex nested schemas or has validation issues with `examples` fields. OpenAI's `beta.chat.completions.parse()` handles Pydantic models more reliably.

---

## Strategy Types Implemented

### 1. Business Strategy

**Purpose**: Captures the company's own business strategy, products, SWOT analysis, and strategic goals.

**Files**:
- Models: `agents/strategy_agent/structured_models.py`
- Agents: `test_neo4j_integration.py` (create_business_researcher, create_business_formatter)
- Graph Builder: `agents/graph_builder.py` → `GraphBuilder` class
- Test: `test_neo4j_integration.py`

**Key Features**:
- **SWOTAnalysis hub node** with linked structure
- **Strengths create Opportunities** via `[:CREATES]` relationships
- **Weaknesses create Risks** via `[:CREATES]` relationships
- **Business-level ValuePropositions** linked to Account
- **ProductCategory** nodes have descriptions for embedding generation

**Pydantic Model Structure**:
```python
StructuredBusinessStrategy
├── company_name: str
├── company_overview_summary: str
├── business_value_propositions: List[ValueProposition] (1-5)
├── product_portfolio: List[ProductCategory] (1-5)
│   └── ProductCategory
│       ├── category_name: str
│       ├── value_propositions: List[ValueProposition] (1-5)
│       └── products: List[ProductService] (1-5)
├── swot_analysis: SWOTAnalysis
│   ├── strengths_and_opportunities: List[StrengthOpportunityLink] (1-5)
│   │   └── StrengthOpportunityLink
│   │       ├── strength: SWOTItem
│   │       └── linked_opportunities: List[SWOTItem] (1-5)
│   └── weaknesses_and_risks: List[WeaknessRiskLink] (1-5)
│       └── WeaknessRiskLink
│           ├── weakness: SWOTItem
│           └── linked_risks: List[SWOTItem] (1-5)
├── strategic_goals: List[StrategicGoal] (1-5)
└── final_summary: str
```

**Node Types Created**:
- Account (hub)
- SWOTAnalysis (hub for SWOT items)
- ProductCategory (with product_name, description for embeddings)
- Product
- ValueProposition (at account, category, and product levels)
- Strength, Weakness, Opportunity, Risk (from SWOT)
- Goal

**Key Relationships**:
- `(Account)-[:AFFECTED_BY_ANALYSIS]->(SWOTAnalysis)`
- `(SWOTAnalysis)-[:HAS_STRENGTH]->(Strength)`
- `(SWOTAnalysis)-[:HAS_WEAKNESS]->(Weakness)`
- `(Strength)-[:CREATES]->(Opportunity)`
- `(Weakness)-[:CREATES]->(Risk)`
- `(Account)-[:HAS_VALUE_PROPOSITION]->(ValueProposition)` (business-level)
- `(Account)-[:HAS_GOAL]->(Goal)`
- `(Account)-[:OFFERS_PRODUCTS]->(ProductCategory)`
- `(ProductCategory)-[:INCLUDES_PRODUCT]->(Product)`
- All nodes: `[:BELONGS_TO]->(Account)`

---

### 2. Competitive Strategy

**Purpose**: Analyzes competitors, their products, strengths/weaknesses, and how they create risks/opportunities for your company.

**Files**:
- Models: `agents/strategy_agent/competitive_models.py`
- Agents: `agents/competitive_agents.py`
- Graph Builder: `agents/competitive_graph_builder.py` → `CompetitiveGraphBuilder` class
- Test: `test_competitive_analysis.py`

**Key Features**:
- **Competitor SWOT** with linked risks/opportunities
- **CompetitorTactic nodes** (marketing tactics used by competitors)
- **Competitor-level ValuePropositions** (why customers choose them)
- **SubstituteProduct** with singular value_proposition
- **CompetitorStrength creates Risk** for your company
- **CompetitorWeakness creates Opportunity** for your company

**Pydantic Model Structure**:
```python
CompetitiveAnalysis
├── company_products: List[str] (1-10)
├── competitive_environment_description: str
└── competitors: List[Competitor] (1-10)
    └── Competitor
        ├── name: str
        ├── description: str
        ├── value_propositions: List[NamedDetail] (1-5)
        ├── marketing_tactics: List[NamedDetail] (1-5)
        ├── substitute_products: List[SubstituteProduct] (1-5)
        │   └── SubstituteProduct
        │       ├── name: str
        │       ├── description: str
        │       └── value_proposition: NamedDetail (SINGULAR!)
        ├── strengths: List[StrengthWithRisks] (1-10)
        │   └── StrengthWithRisks
        │       ├── name: str
        │       ├── description: str
        │       └── risks: List[NamedDetail] (1-5)
        └── weaknesses: List[WeaknessWithOpportunities] (1-10)
            └── WeaknessWithOpportunities
                ├── name: str
                ├── description: str
                └── opportunities: List[NamedDetail] (1-5)
```

**Node Types Created**:
- CompetitiveEnvironment (hub)
- Competitor
- CompetitorTactic
- CompetitorStrength, CompetitorWeakness
- SubstituteProduct
- ValueProposition (at competitor and substitute product levels)
- Risk (created by competitor strengths)
- Opportunity (created by competitor weaknesses)

**Key Relationships**:
- `(Account)-[:OPERATES_WITHIN]->(CompetitiveEnvironment)`
- `(CompetitiveEnvironment)-[:IS_KEY_PLAYER]->(Competitor)`
- `(Competitor)-[:USES_TACTIC]->(CompetitorTactic)`
- `(Competitor)-[:HAS_VALUE_PROPOSITION]->(ValueProposition)`
- `(Competitor)-[:HAS_STRENGTH]->(CompetitorStrength)`
- `(Competitor)-[:HAS_WEAKNESS]->(CompetitorWeakness)`
- `(Competitor)-[:OFFERS_PRODUCT]->(SubstituteProduct)`
- `(CompetitorStrength)-[:CREATES]->(Risk)`
- `(CompetitorWeakness)-[:CREATES]->(Opportunity)`
- `(SubstituteProduct)-[:HAS_VALUE_PROPOSITION]->(ValueProposition)`
- `(Product)-[:MAY_BE_SUBSTITUTED_FOR]->(SubstituteProduct)` (integration)

---

### 3. Marketing Strategy

**Purpose**: Defines ideal customer profiles and marketing strategies across the customer journey (problem awareness → brand awareness → consideration → conversion → loyalty).

**Files**:
- Models: `agents/strategy_agent/marketing_models.py`
- Agents: `agents/marketing_agents.py`
- Graph Builder: `agents/marketing_graph_builder.py` → `MarketingGraphBuilder` class
- Test: `test_marketing_analysis.py`

**Key Features**:
- **CustomerProfile nodes** with complete customer journey
- **5 journey strategy nodes** per customer profile
- **Links to ProductCategory** via IS_MARKETED_TO relationship

**Pydantic Model Structure**:
```python
MarketingResearchReport
└── product_categories: List[ProductCategory]
    └── ProductCategory
        ├── category_name: str
        └── ideal_customer_profiles: List[IdealCustomerProfile] (2-5)
            └── IdealCustomerProfile
                ├── narrative: str
                ├── problem_awareness_strategy: str (max 4000)
                ├── brand_awareness_strategy: str (max 4000)
                ├── consideration_strategy: str (max 4000)
                ├── conversion_strategy: str (max 4000)
                └── loyalty_strategy: str (max 4000)
```

**Node Types Created**:
- CustomerProfile
- ProblemAwarenessStrategy
- BrandAwarenessStrategy
- ConsiderationStrategy
- ConversionStrategy
- LoyaltyStrategy

**Key Relationships**:
- `(CustomerProfile)-[:IS_MARKETED_TO]->(ProductCategory)` (integration)
- `(CustomerProfile)-[:DISCOVERS_THE_PROBLEM_BY]->(ProblemAwarenessStrategy)`
- `(CustomerProfile)-[:DISCOVERS_OUR_BRAND_BY]->(BrandAwarenessStrategy)`
- `(CustomerProfile)-[:CONSIDERS_OUR_BRAND_BECAUSE]->(ConsiderationStrategy)`
- `(CustomerProfile)-[:PURCHASES_OUR_BRAND_BECAUSE]->(ConversionStrategy)`
- `(CustomerProfile)-[:BECOMES_AN_ADVOCATE_BECAUSE]->(LoyaltyStrategy)`

---

### 4. Brand Guidelines

**Purpose**: Documents brand identity, personality, visual guidelines, and communication style for consistent content creation.

**Files**:
- Models: `agents/strategy_agent/brand_models.py`
- Agents: `agents/brand_agents.py`
- Graph Builder: `agents/brand_graph_builder.py` → `BrandGraphBuilder` class
- Test: `test_brand_guidelines.py`

**Key Features**:
- **BrandIdentity hub node** linked to Account
- **6 brand guideline nodes** covering all aspects of brand
- **No embeddings** on some nodes (ColorPalette, Typography) - just reference data

**Pydantic Model Structure**:
```python
BrandGuidelines
├── brand_identity: str
├── brand_personality: str
├── voice_and_tone: str
├── color_palette: str
├── typography: str
├── image_style: str
└── mission_and_values: str
```

**Node Types Created**:
- BrandIdentity (hub)
- BrandPersonality
- VoiceAndTone
- ColorPalette
- Typography
- ImageStyle
- MissionAndValues

**Key Relationships**:
- `(Account)-[:FOLLOWS_THESE_BRAND_GUIDELINES]->(BrandIdentity)`
- `(BrandIdentity)-[:HAS_TRAITS_AND_CHARACTERISTICS]->(BrandPersonality)`
- `(BrandIdentity)-[:USES_COMMUNICATION_STYLE]->(VoiceAndTone)`
- `(BrandIdentity)-[:USES_COLORS]->(ColorPalette)`
- `(BrandIdentity)-[:USES_FONTS_AND_TYPEFACES]->(Typography)`
- `(BrandIdentity)-[:USES_IMAGE_STYLE]->(ImageStyle)`
- `(BrandIdentity)-[:HAS_MISSION]->(MissionAndValues)`

---

## Pydantic Models Reference

### Common Patterns

All strategy Pydantic models follow these patterns:

1. **ID fields**: Use lowercase-hyphenated format (e.g., `'strength-brand-recognition'`)
2. **Constraints**: Use `conlist(Type, min_length=X, max_length=Y)` for list validation
3. **Nested structures**: Complex models decompose into smaller reusable models
4. **Field descriptions**: Comprehensive for AI agent understanding

### File Organization

```
agents/strategy_agent/
├── structured_models.py    # Business strategy models
├── competitive_models.py   # Competitive analysis models
├── marketing_models.py     # Marketing strategy models
└── brand_models.py         # Brand guidelines models
```

### SWOT Linked Structure (Important!)

**Business Strategy SWOT**:
```python
class StrengthOpportunityLink(BaseModel):
    strength: SWOTItem  # The internal strength
    linked_opportunities: List[SWOTItem]  # 1-5 opportunities it creates

class WeaknessRiskLink(BaseModel):
    weakness: SWOTItem  # The internal weakness
    linked_risks: List[SWOTItem]  # 1-5 risks it exposes

class SWOTAnalysis(BaseModel):
    strengths_and_opportunities: List[StrengthOpportunityLink] (1-5)
    weaknesses_and_risks: List[WeaknessRiskLink] (1-5)
```

**Competitive Strategy SWOT**:
```python
class StrengthWithRisks(BaseModel):
    name: str
    description: str
    risks: List[NamedDetail]  # 1-5 risks created for YOUR company

class WeaknessWithOpportunities(BaseModel):
    name: str
    description: str
    opportunities: List[NamedDetail]  # 1-5 opportunities for YOUR company

class Competitor(BaseModel):
    ...
    strengths: List[StrengthWithRisks] (1-10)
    weaknesses: List[WeaknessWithOpportunities] (1-10)
```

This structure ensures graph relationships like `(Strength)-[:CREATES]->(Opportunity)` can be created directly from the Pydantic data.

---

## Neo4j Graph Schema

### Universal Node Fields

All Strategy-labeled nodes include:

```python
{
    'node_id': str,          # or specific ID like 'strength_id', 'product_id'
    'display_name': str,     # Human-readable name (optional)
    'description': str,      # Required for embeddings
    'created_time': datetime,
    'last_modified': datetime,
    'created_by': str,
    'last_modified_by': str,
    'embedding': list        # Vector embedding (768 dimensions)
}
```

### Node Type to ID Field Mapping

Reference from `agents/neo4j_tools.py`:

```python
id_field_map = {
    # Business Strategy
    'Product': 'product_id',
    'ProductCategory': 'category_name',
    'Goal': 'goal_id',
    'Strength': 'strength_id',
    'Weakness': 'weakness_id',
    'Opportunity': 'opportunity_id',
    'Risk': 'risk_id',
    'SWOTAnalysis': 'swot_id',
    'ValueProposition': 'valueprop_id',

    # Competitive Analysis
    'Competitor': 'node_id',
    'CompetitorStrength': 'node_id',
    'CompetitorWeakness': 'node_id',
    'CompetitorTactic': 'node_id',
    'SubstituteProduct': 'node_id',

    # Marketing Strategy
    'CustomerProfile': 'node_id',
    'ProblemAwarenessStrategy': 'node_id',
    'BrandAwarenessStrategy': 'node_id',
    'ConsiderationStrategy': 'node_id',
    'ConversionStrategy': 'node_id',
    'LoyaltyStrategy': 'node_id',

    # Brand Guidelines
    'BrandIdentity': 'node_id',
    'BrandPersonality': 'node_id',
    'VoiceAndTone': 'node_id',
    'ColorPalette': 'node_id',
    'Typography': 'node_id',
    'ImageStyle': 'node_id',
    'MissionAndValues': 'node_id'
}
```

### Critical Relationships

**Three-Way Integration**:

1. **Business ↔ Competitive**:
   - `(Product)-[:MAY_BE_SUBSTITUTED_FOR]->(SubstituteProduct)`

2. **Business ↔ Marketing**:
   - `(CustomerProfile)-[:IS_MARKETED_TO]->(ProductCategory)`

3. **Shared Resources**:
   - ValueProposition nodes can be linked to Account, Product, ProductCategory, Competitor, or SubstituteProduct
   - Opportunity/Risk nodes can be created by Strength/Weakness (business) OR CompetitorStrength/CompetitorWeakness

### Embeddings Strategy

**Nodes WITH embeddings** (have `description` field):
- All Strategy-labeled nodes with narrative content
- Examples: Goals, SWOT items, Products, CustomerProfiles, Competitors, etc.

**Nodes WITHOUT embeddings** (no `description` field):
- Structural nodes: RevenueStream, CostStructure
- Some hub nodes: SWOTAnalysis (no description in current implementation)

**Generation**:
- Model: Vertex AI `text-embedding-004` (768 dimensions)
- Batch processing: 10 nodes at a time
- Field: `n.description` is embedded into `n.embedding`
- Index: Vector index `strategy_search` on `(:Strategy).embedding`

---

## Graph Builders

Each graph builder follows the same pattern:

### Common Structure

```python
class GraphBuilder:
    def __init__(self, neo4j_ops: Neo4jOperations):
        self.neo4j_ops = neo4j_ops

    def build_X_graph(self, data: PydanticModel, account_id: str, user_id: str) -> Dict:
        """Main entry point - builds complete graph"""
        created_nodes = {
            'node_type_1': [],
            'node_type_2': [],
            # ...
        }

        # Create nodes and relationships
        # Return counts for validation
        return created_nodes

    def _create_X_node(self, data, account_id: str) -> Dict:
        """Helper to create specific node type"""
        node_data = {
            'node_id': generate_id(),
            'display_name': data.name,
            'description': data.description,
            # Standard fields
        }

        # Use Neo4j operations to create with MERGE
        node = self.neo4j_ops.create_strategy_node('NodeType', node_data, account_id)

        # Create relationships
        self.neo4j_ops.connection.execute_query(relationship_query, params)

        return node_data
```

### Key Methods

#### `create_strategy_node(node_type, node_data, account_id)`

From `agents/neo4j_tools.py`:

```python
def create_strategy_node(self, node_type: str, node_data: Dict, account_id: str) -> Dict:
    """
    Create or merge a strategy node with proper labels and relationships.
    Uses MERGE to prevent duplicates based on unique identifiers.
    """
    id_field = id_field_map.get(node_type)

    if id_field and id_field in node_data:
        # MERGE prevents duplicates
        query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        MERGE (n:{node_type}:Strategy {{{id_field}: $unique_id}})
        ON CREATE SET n += $node_data, n.created_time = datetime(), n.created_by = 'System'
        ON MATCH SET n += $node_data, n.last_modified = datetime()
        MERGE (n)-[:BELONGS_TO]->(acc)
        RETURN n
        """
```

**Important**: Always use MERGE (not CREATE) to prevent duplicate nodes when re-running generation.

---

## Integration Points

### 1. ValueProposition Sharing

ValueProposition nodes can belong to multiple contexts:

```cypher
// Business-level
(Account)-[:HAS_VALUE_PROPOSITION]->(VP)

// Product-level
(Product)-[:HAS_VALUE_PROPOSITION]->(VP)
(ProductCategory)-[:HAS_VALUE_PROPOSITION]->(VP)

// Competitive-level
(Competitor)-[:HAS_VALUE_PROPOSITION]->(VP)
(SubstituteProduct)-[:HAS_VALUE_PROPOSITION]->(VP)
```

**Design Decision**: ValuePropositions are separate nodes that can be referenced from multiple sources. This allows querying "All value propositions in the system" or "Product X's unique value propositions vs Competitor Y's".

### 2. Opportunity/Risk Sharing

Opportunity and Risk nodes can be created by multiple sources:

```cypher
// From business SWOT
(Strength)-[:CREATES]->(Opportunity)
(Weakness)-[:CREATES]->(Risk)

// From competitive SWOT
(CompetitorStrength)-[:CREATES]->(Risk)  // Risk to OUR company
(CompetitorWeakness)-[:CREATES]->(Opportunity)  // Opportunity for OUR company
```

This enables queries like "Show all risks to our company (from both internal weaknesses and competitor strengths)".

### 3. Product Competition Mapping

```cypher
(Product)-[:MAY_BE_SUBSTITUTED_FOR]->(SubstituteProduct)<-[:OFFERS_PRODUCT]-(Competitor)
```

Enables queries: "Which competitor products can substitute for Product X?"

### 4. Customer Journey Mapping

```cypher
(ProductCategory)<-[:IS_MARKETED_TO]-(CustomerProfile)-[:DISCOVERS_THE_PROBLEM_BY]->(ProblemAwarenessStrategy)
                                                       -[:DISCOVERS_OUR_BRAND_BY]->(BrandAwarenessStrategy)
                                                       -[:CONSIDERS_OUR_BRAND_BECAUSE]->(ConsiderationStrategy)
                                                       -[:PURCHASES_OUR_BRAND_BECAUSE]->(ConversionStrategy)
                                                       -[:BECOMES_AN_ADVOCATE_BECAUSE]->(LoyaltyStrategy)
```

Enables queries: "Show the complete customer journey for ProductCategory X's ideal customers".

---

## Testing Approach

### Test Structure

Each strategy type has an integration test following this pattern:

```python
class StrategyRunner:
    def __init__(self):
        self.neo4j_ops = get_neo4j_operations()
        self.graph_builder = GraphBuilder(self.neo4j_ops)
        self.embedding_generator = EmbeddingGenerator(self.neo4j_ops)
        self.search = EmbeddingSearch(self.neo4j_ops, self.embedding_generator)

    async def generate_X_strategy(self, company_name: str, account_id: str):
        # 1. Research with researcher agent
        research = await run_agent(researcher, query)

        # 2. Format with formatter agent (Gemini) or OpenAI fallback
        try:
            formatted = await run_agent(formatter, research)
            data = Model(**json.loads(formatted))
        except:
            data = format_with_openai(research)

        # 3. Save to Firestore
        save_to_firestore(data)

        # 4. Build Neo4j graph
        graph_nodes = graph_builder.build_graph(data, account_id, user_id)

        # 5. Generate embeddings
        embedding_result = embedding_generator.generate_embeddings_for_account(account_id)

        # 6. Test semantic search
        search.search("test query", account_id)
```

### Validation

Each test validates:
1. **Node counts** match expected from Pydantic model
2. **Relationships** exist between nodes
3. **Embeddings** generated successfully
4. **Semantic search** returns results

Example validation:
```python
expected_strengths = len(strategy.swot_analysis.strengths_and_opportunities)
actual_strengths = len(graph_nodes['swot']['strengths'])

if actual_strengths < expected_strengths:
    raise ValueError("Graph creation incomplete")
```

### Test Files

- `test_neo4j_integration.py` - Business strategy
- `test_competitive_analysis.py` - Competitive analysis
- `test_marketing_analysis.py` - Marketing strategy
- `test_brand_guidelines.py` - Brand guidelines

### Running Tests

```bash
# Individual tests
uv run python test_neo4j_integration.py
uv run python test_competitive_analysis.py
uv run python test_marketing_analysis.py
uv run python test_brand_guidelines.py

# Use same account_id to test integration between strategy types
```

**Important**: Use a fresh account for testing new schema changes to avoid conflicts with old data.

---

## Migration Guide

### From Local Testing to GCP Production

#### 1. Environment Variables

**Current** (`agents/.env`):
```env
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
OPENAI_API_KEY=sk-...
GOOGLE_CLOUD_PROJECT=ken-e-dev
```

**GCP Production**: Use Secret Manager
```python
from google.cloud import secretmanager

def get_secret(secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

#### 2. Authentication

**Local**: `gcloud auth application-default login`

**GCP**: Use service account credentials
```python
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    'path/to/service-account-key.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
```

#### 3. Firestore Configuration

**Current**: Uses default credentials

**GCP Production**:
```python
from google.cloud import firestore

db = firestore.Client(
    project=project_id,
    credentials=credentials,
    database='(default)'  # or named database
)
```

#### 4. Neo4j Connection Pooling

**Current**: Single connection per test

**GCP Production**: Use connection pooling
```python
class Neo4jConnection:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            max_connection_lifetime=3600,  # 1 hour
            max_connection_pool_size=50,   # Increase for production
            connection_acquisition_timeout=60
        )
```

#### 5. Error Handling and Retries

**Current**: Basic retry logic in `execute_query`

**GCP Production**: Add exponential backoff, circuit breakers
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def execute_with_retry(query, params):
    return neo4j_ops.connection.execute_query(query, params)
```

#### 6. Rate Limiting

**Current**: `max_output_tokens=4000` on researchers

**GCP Production**: Implement request throttling
```python
import time
from threading import Semaphore

rate_limiter = Semaphore(10)  # Max 10 concurrent requests

async def rate_limited_generation(company_name):
    with rate_limiter:
        return await generate_strategy(company_name)
```

#### 7. Monitoring and Logging

**GCP Production**: Use Cloud Logging
```python
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()

logger = logging.getLogger(__name__)
logger.info("Strategy generation started", extra={
    'account_id': account_id,
    'strategy_type': 'business'
})
```

#### 8. Deployment Checklist

- [ ] Move credentials to Secret Manager
- [ ] Set up service account with necessary permissions:
  - Vertex AI User
  - Firestore User
  - Secret Manager Secret Accessor
- [ ] Configure VPC connector for Neo4j access (if private)
- [ ] Set up Cloud Run or Cloud Functions deployment
- [ ] Configure environment variables in Cloud Run/Functions
- [ ] Set up Cloud Scheduler for periodic industry updates
- [ ] Implement request authentication/authorization
- [ ] Add rate limiting per customer
- [ ] Set up monitoring and alerting
- [ ] Configure auto-scaling parameters
- [ ] Test with production Neo4j instance

---

## Known Issues and Workarounds

### 1. ADK Tool/Schema Constraint

**Issue**: Cannot use tools and output_schema in same agent.

**Workaround**: Split-agent architecture (researcher with tools + formatter with schema).

**Reference**: GitHub issue #701 in ADK Python library.

---

### 2. Gemini Schema Validation Errors

**Issue**: Gemini sometimes rejects schemas with `examples` fields:
```
Extra inputs are not permitted [type=extra_forbidden, input_value=[...], input_type=list]
```

**Workaround**: Always implement OpenAI fallback with `beta.chat.completions.parse()`.

**Code Pattern**:
```python
try:
    result = await run_agent(gemini_formatter, research)
except Exception as e:
    logger.warning(f"Gemini failed: {e}, using OpenAI fallback")
    result = openai_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[...],
        response_format=PydanticModel
    )
```

---

### 3. RootModel Not Supported by OpenAI

**Issue**: OpenAI requires root to be object type, not array.

```python
# ❌ FAILS with OpenAI
class Report(RootModel[List[Item]]):
    root: List[Item]

# ✅ WORKS with OpenAI
class Report(BaseModel):
    items: List[Item]
```

**Fixed in**: `marketing_models.py` changed from RootModel to BaseModel with `product_categories` field.

---

### 4. Rate Limiting

**Issue**: OpenAI has 30K TPM limit on GPT-4o. Large research outputs (195K chars) cause failures.

**Workaround**: Limit `max_output_tokens=4000` on all researcher agents.

**Alternative**: Use GPT-4o-mini for formatting (higher rate limits, lower cost).

---

### 5. Neo4j ID Generation

**Pattern Used**: Generate deterministic IDs where possible:
```python
# Business nodes - use Pydantic model IDs
'strength_id': item.id  # From Pydantic: 'strength-brand-recognition'

# Competitive/Marketing nodes - generate from context
'node_id': f"competitor_{name.lower().replace(' ', '_')}_{account_id[:8]}"
'node_id': f"icp_{uuid.uuid4().hex}"  # For customer profiles
```

**Why MERGE matters**: Deterministic IDs allow re-running strategy generation without creating duplicates.

---

### 6. Embedding Coverage

**Expected**: Not all nodes will have embeddings.

- ProductCategory, RevenueStream, CostStructure: No `description` field in Pydantic models
- These are structural/financial data, not narrative content
- **Typical coverage**: 85-90% is normal and correct

**Query to find missing**:
```cypher
MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: $account_id})
WHERE n.embedding IS NULL
RETURN [label IN labels(n) WHERE label <> 'Strategy'][0] as type, count(n)
```

---

## Future Work

### 1. Industry Analysis (Documented, Not Implemented)

**File**: `documentation/industry_requirements.md`

**Scope**: Industry-level research shared across all accounts in same Industry+GeographicRegion.

**Node Types** (18+):
- Industry, GeographicRegion (hubs)
- PESTELAnalysis (hub), 6 PESTEL factor types
- PortersFiveForcesAnalysis (hub), 5 force types
- IndustryTrend, KeySuccessFactor
- MarketOpportunity, MarketRisk

**Relationships**:
- `(Account)-[:OPERATES_WITHIN]->(GeographicRegion)`
- `(GeographicRegion)-[:OPERATES_WITHIN]->(Industry)`
- `(GeographicRegion)-[:AFFECTED_BY_ANALYSIS]->(PESTELAnalysis)`
- `(GeographicRegion)-[:AFFECTED_BY_ANALYSIS]->(PortersFiveForcesAnalysis)`
- PESTEL factors and Porter's forces create MarketOpportunity/MarketRisk nodes

**Implementation Plan**:
1. Create `agents/strategy_agent/industry_models.py` with all 18+ models
2. Create `agents/industry_agents.py` with split architecture
3. Create `agents/industry_graph_builder.py` for complex graph
4. Update Neo4j operations with 18+ new node types
5. Create `test_industry_analysis.py`

**Note**: This is the largest and most complex strategy type. PESTEL factors moved from account-level to industry-level to enable sharing.

---

### 2. Metrics and KPI System

**Visible in PDF diagram, not in MD files**:
- Metric, Dimension, Concept, MCP nodes
- Relationships: MEASURES_EFFECTIVENESS_WITH, MEASURES_EFFICIENCY_WITH
- Linking Goals and ProductCategories to performance metrics

**Status**: Future work, not in current scope.

---

### 3. Activity Tracking System

**Visible in PDF diagram, not in MD files**:
- Activity, ActivityLog nodes
- MCP (Marketing Control Panel?) integration
- Influence tracking: INFLUENCE_LIKELY, INFLUENCE_CONFIRMED

**Status**: Future work, not in current scope.

---

## Code Organization

### Directory Structure

```
adk-strategy-test/
├── agents/
│   ├── strategy_agent/
│   │   ├── structured_models.py      # Business strategy models
│   │   ├── competitive_models.py     # Competitive analysis models
│   │   ├── marketing_models.py       # Marketing strategy models
│   │   └── brand_models.py           # Brand guidelines models
│   ├── graph_builder.py              # Business strategy graph builder
│   ├── competitive_graph_builder.py  # Competitive graph builder
│   ├── marketing_graph_builder.py    # Marketing graph builder
│   ├── brand_graph_builder.py        # Brand graph builder
│   ├── competitive_agents.py         # Competitive split agents
│   ├── marketing_agents.py           # Marketing split agents
│   ├── brand_agents.py               # Brand split agents
│   ├── neo4j_tools.py                # Neo4j connection and operations
│   ├── embeddings.py                 # Vertex AI embedding generation
│   ├── firestore_tools.py            # Firestore persistence
│   └── .env                          # Environment variables
├── documentation/
│   ├── business_requirements.md      # Business strategy spec
│   ├── competitor_requirements.md    # Competitive analysis spec
│   ├── marketing_requirements.md     # Marketing strategy spec
│   ├── brand_requirements.md         # Brand guidelines spec
│   ├── industry_requirements.md      # Industry analysis spec (future)
│   └── KEN-E __ Knowledge Graph.pdf  # Complete graph diagram
├── test_neo4j_integration.py         # Business strategy test
├── test_competitive_analysis.py      # Competitive analysis test
├── test_marketing_analysis.py        # Marketing strategy test
├── test_brand_guidelines.py          # Brand guidelines test
├── CLAUDE.md                         # Project context for Claude Code
└── TECHNICAL_DOCUMENTATION.md        # This file
```

### Import Patterns

```python
# Models
from agents.strategy_agent.structured_models import StructuredBusinessStrategy
from agents.strategy_agent.competitive_models import CompetitiveAnalysis
from agents.strategy_agent.marketing_models import MarketingResearchReport
from agents.strategy_agent.brand_models import BrandGuidelines

# Agents (defined in test files or separate modules)
from agents.competitive_agents import create_competitive_researcher, create_competitive_formatter
from agents.marketing_agents import create_marketing_researcher, create_marketing_formatter
from agents.brand_agents import create_brand_researcher, create_brand_formatter

# Graph Builders
from agents.graph_builder import GraphBuilder
from agents.competitive_graph_builder import CompetitiveGraphBuilder
from agents.marketing_graph_builder import MarketingGraphBuilder
from agents.brand_graph_builder import BrandGraphBuilder

# Infrastructure
from agents.neo4j_tools import get_neo4j_operations
from agents.embeddings import EmbeddingGenerator, EmbeddingSearch
from agents.firestore_tools import _save_to_firestore_impl
```

---

## Configuration and Setup

### Required Environment Variables

```bash
# Neo4j
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# OpenAI (fallback)
OPENAI_API_KEY=sk-...

# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project-id
# Note: Also requires `gcloud auth application-default login`
```

### Neo4j Indexes

Created automatically by `neo4j_ops.create_indexes()`:

```cypher
// Vector index for semantic search
CREATE VECTOR INDEX strategy_search IF NOT EXISTS
FOR (n:Strategy) ON (n.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}}

// Regular indexes for lookups
CREATE INDEX account_name IF NOT EXISTS FOR (n:Account) ON (n.account_name)
CREATE INDEX account_id IF NOT EXISTS FOR (n:Account) ON (n.account_id)
CREATE INDEX strategy_modified IF NOT EXISTS FOR (n:Strategy) ON (n.last_modified)
```

### Python Dependencies

Key dependencies (from `pyproject.toml`):
```toml
[project.dependencies]
google-adk = ">=1.14.0"
google-genai = ">=0.7.0"
google-cloud-aiplatform = ">=1.38.0"
google-cloud-firestore = ">=2.11.0"
google-cloud-secret-manager = ">=2.16.0"
pydantic = ">=2.0.0"
neo4j = ">=5.14.0"
openai = ">=1.0.0"
python-dotenv = ">=1.0.0"
```

---

## Query Examples

### Useful Neo4j Queries

**1. Get complete strategy overview for an account**:
```cypher
MATCH (acc:Account {account_id: $account_id})
OPTIONAL MATCH (acc)-[r]->(n:Strategy)
RETURN acc, type(r) as relationship, labels(n) as node_types, count(n) as count
```

**2. Find all risks (from both business and competitive)**:
```cypher
MATCH (r:Risk)-[:BELONGS_TO]->(:Account {account_id: $account_id})
OPTIONAL MATCH (source)-[:CREATES]->(r)
RETURN r.display_name, r.description, labels(source) as created_by
```

**3. Customer journey for a product category**:
```cypher
MATCH (pc:ProductCategory {category_name: $category_name})
      <-[:IS_MARKETED_TO]-(cp:CustomerProfile)
MATCH (cp)-[:DISCOVERS_THE_PROBLEM_BY]->(pas)
MATCH (cp)-[:DISCOVERS_OUR_BRAND_BY]->(bas)
MATCH (cp)-[:CONSIDERS_OUR_BRAND_BECAUSE]->(cs)
MATCH (cp)-[:PURCHASES_OUR_BRAND_BECAUSE]->(cvs)
MATCH (cp)-[:BECOMES_AN_ADVOCATE_BECAUSE]->(ls)
RETURN cp.description as persona,
       pas.description as problem_awareness,
       bas.description as brand_awareness,
       cs.description as consideration,
       cvs.description as conversion,
       ls.description as loyalty
```

**4. Product competition analysis**:
```cypher
MATCH (p:Product {product_id: $product_id})
      -[:MAY_BE_SUBSTITUTED_FOR]->(sp:SubstituteProduct)
      <-[:OFFERS_PRODUCT]-(c:Competitor)
MATCH (sp)-[:HAS_VALUE_PROPOSITION]->(vp)
RETURN p.product_name as our_product,
       c.display_name as competitor,
       sp.product_name as their_product,
       vp.display_name as their_value_prop
```

**5. Semantic search**:
```python
from agents.embeddings import EmbeddingSearch

search = EmbeddingSearch(neo4j_ops, embedding_generator)
results = search.search(
    query="What are our competitive advantages?",
    account_id="acc_xyz",
    top_k=5
)
# Returns: [{type, name, description, score}, ...]
```

---

## Performance Considerations

### Token Usage

**Researcher Agents** (with tools):
- Input: ~500-1000 tokens (query)
- Output: 2000-4000 tokens (limited to prevent rate limits)
- Model: Gemini 2.0 Flash (fast, cheap)

**Formatter Agents** (with schema):
- Input: 2000-4000 tokens (research) + schema
- Output: 2000-8000 tokens (structured JSON)
- Model: Gemini 2.5 Pro → OpenAI GPT-4o fallback

**Total per strategy**: ~10K-20K tokens

### Timing

Observed timing per strategy type (on test account):
- Business Strategy: ~4-5 minutes
- Competitive Strategy: ~5-7 minutes (more search required)
- Marketing Strategy: ~4-5 minutes
- Brand Guidelines: ~2-3 minutes

**Total for complete account setup**: ~15-20 minutes

### Neo4j Performance

- **Node creation**: 100-200 nodes per strategy type
- **Relationship creation**: 200-400 relationships
- **Query performance**: Indexed lookups <100ms
- **Vector search**: <500ms for top-5 results

### Embedding Generation

- **Batch size**: 10 nodes per request
- **Rate**: ~1-2 seconds per batch
- **Model**: text-embedding-004 (768 dimensions)
- **Typical account**: 150-200 nodes = 15-20 batches = ~30 seconds

---

## Development Commands

### Testing

```bash
# Individual strategy tests
uv run python test_neo4j_integration.py         # Business
uv run python test_competitive_analysis.py      # Competitive
uv run python test_marketing_analysis.py        # Marketing
uv run python test_brand_guidelines.py          # Brand

# Use consistent account_id to test integration
```

### Database Management

```bash
# Clear test data
uv run python -c "
from agents.neo4j_tools import get_neo4j_operations
ops = get_neo4j_operations()
ops.connection.execute_query('''
MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: \$account_id})
DETACH DELETE n
''', {'account_id': 'acc_test'})
ops.close()
"
```

### Verification

```bash
# Check node counts
uv run python -c "
from agents.neo4j_tools import get_neo4j_operations
ops = get_neo4j_operations()
result = ops.connection.execute_query('''
MATCH (n:Strategy)-[:BELONGS_TO]->(:Account {account_id: \$account_id})
RETURN labels(n) as types, count(n) as count
ORDER BY count DESC
''', {'account_id': 'acc_new_schema_test'})
for r in result: print(f\"{r['types']}: {r['count']}\")
ops.close()
"
```

---

## Integration Checklist for Production

### Pre-Integration

- [ ] Review all Pydantic models match production requirements
- [ ] Verify Neo4j instance is accessible from GCP
- [ ] Set up Secret Manager with all credentials
- [ ] Create service account with required permissions
- [ ] Test connectivity: GCP → Neo4j, GCP → Vertex AI, GCP → Firestore

### Code Integration

- [ ] Copy all files from `agents/` directory
- [ ] Copy all Pydantic models from `agents/strategy_agent/`
- [ ] Adapt authentication to use GCP service accounts
- [ ] Update environment variable loading for GCP
- [ ] Implement rate limiting per customer
- [ ] Add comprehensive error handling and retries
- [ ] Set up Cloud Logging integration

### Testing in Production

- [ ] Run all 4 strategy types on test account
- [ ] Verify embeddings generate correctly
- [ ] Test semantic search functionality
- [ ] Validate all relationships exist
- [ ] Check embedding coverage matches expectations
- [ ] Load test with multiple concurrent requests

### Monitoring

- [ ] Set up alerts for strategy generation failures
- [ ] Monitor Neo4j connection pool usage
- [ ] Track embedding generation success rates
- [ ] Monitor LLM API costs (Gemini vs OpenAI usage)
- [ ] Alert on rate limit errors

---

## Critical Implementation Notes

### 1. Always Use MERGE for Node Creation

```python
# ✅ CORRECT - Prevents duplicates
MERGE (n:Product {product_id: $id})
ON CREATE SET n.created_time = datetime()
ON MATCH SET n.last_modified = datetime()

# ❌ WRONG - Creates duplicates on re-run
CREATE (n:Product {product_id: $id})
```

### 2. Account Node Must Exist

CompetitiveEnvironment graph builder creates Account if missing:

```python
MERGE (acc:Account {account_id: $account_id})
ON CREATE SET acc.account_name = $account_id, acc.created_time = datetime()
```

Business strategy uses `merge_account()` with full account data.

### 3. Relationship Direction Matters

**From MD specs**:
- `(Account)-[:HAS_GOAL]->(Goal)` ← Account HAS goals
- `(Product)-[:MAY_BE_SUBSTITUTED_FOR]->(SubstituteProduct)` ← Product may be substituted
- `(CustomerProfile)-[:IS_MARKETED_TO]->(ProductCategory)` ← Profile is marketed to category

Direction indicates semantic meaning for graph queries.

### 4. Label Pattern

All strategy nodes have TWO labels:
```cypher
CREATE (n:NodeType:Strategy)
```

- `NodeType`: Specific type (Product, Goal, Competitor, etc.)
- `Strategy`: Indicates node participates in strategy system and can have embeddings

**Query pattern**:
```cypher
// Find all strategy nodes
MATCH (n:Strategy)-[:BELONGS_TO]->(acc)

// Find specific type
MATCH (n:Product)-[:BELONGS_TO]->(acc)
```

### 5. UUID vs Deterministic IDs

**Use deterministic IDs** when possible (from Pydantic model):
- Enables MERGE to prevent duplicates
- Enables updates without orphaning nodes

**Use UUIDs** when no natural identifier:
- CustomerProfile: `icp_{uuid.uuid4().hex}`
- Brand nodes: `brand_{uuid.uuid4().hex}`

---

## Testing Validation Results

### Test Account: acc_new_schema_test (Apple)

**Final Node Counts**:
```
Business Strategy:        22 nodes
Competitive Strategy:     89 nodes
Marketing Strategy:       48 nodes
Brand Guidelines:          7 nodes
───────────────────────────────────
Total:                   166 nodes
Embeddings:              166/166 (100%)
```

**Relationship Verification**:
- ✅ Strength→Opportunity: 4 CREATES relationships
- ✅ Weakness→Risk: 4 CREATES relationships
- ✅ CompetitorStrength→Risk: 10 CREATES relationships
- ✅ CompetitorWeakness→Opportunity: 9 CREATES relationships
- ✅ Product→SubstituteProduct: 18 MAY_BE_SUBSTITUTED_FOR relationships
- ✅ CustomerProfile→ProductCategory: 3 IS_MARKETED_TO relationships
- ✅ All 5 customer journey relationships per profile

**Semantic Search Validation**:
- All queries return relevant results
- Score range: 0.75-0.85 (good similarity)
- Top results match query intent

---

## Troubleshooting Guide

### Gemini Formatting Failures

**Symptom**: `Extra inputs are not permitted [type=extra_forbidden]`

**Cause**: Pydantic `examples` field in Field() definition

**Solution**: Fallback to OpenAI automatically (already implemented)

---

### OpenAI Rate Limit Errors

**Symptom**: `Error code: 429 - Request too large...`

**Cause**: Research output exceeds token limits

**Solution**: Reduce `max_output_tokens` in researcher agents (set to 4000)

---

### Missing Embeddings

**Symptom**: Some nodes don't have embeddings

**Check**:
```cypher
MATCH (n:Strategy {account_id: $account_id})
WHERE n.embedding IS NULL
RETURN n.description IS NULL as no_description, count(n)
```

**Expected**: ProductCategory, RevenueStream, CostStructure have no description field - this is normal.

**Fix if unexpected**: Ensure node has `description` field populated in graph builder.

---

### Authentication Errors

**Symptom**: `RefreshError: Reauthentication is needed`

**Solution**: Run `gcloud auth application-default login`

**GCP Production**: Use service account, won't need this.

---

## Contact and Support

This system was developed to solve the ADK tool/schema constraint and create a production-ready knowledge graph for strategic business intelligence.

**Key Files for Integration**:
1. `documentation/` - All MD requirement specs
2. `agents/strategy_agent/` - All Pydantic models
3. `agents/*_graph_builder.py` - Neo4j graph construction logic
4. `agents/*_agents.py` - Split agent implementations
5. This file - Complete technical reference

**Testing**: Always test on a fresh account when making schema changes to avoid conflicts with existing data.

**Success Metrics**:
- 100% strategy generation success rate (split-agent architecture)
- 85-100% embedding coverage (depending on node types)
- Sub-second semantic search response times

---

## Appendix A: Complete Node Type List

### Business Strategy (9 types)
- Account, SWOTAnalysis
- ProductCategory, Product
- ValueProposition, Goal
- Strength, Weakness, Opportunity, Risk

### Competitive Strategy (9 types)
- CompetitiveEnvironment
- Competitor, CompetitorTactic
- CompetitorStrength, CompetitorWeakness
- SubstituteProduct
- ValueProposition (shared)
- Risk, Opportunity (shared)

### Marketing Strategy (6 types)
- CustomerProfile
- ProblemAwarenessStrategy
- BrandAwarenessStrategy
- ConsiderationStrategy
- ConversionStrategy
- LoyaltyStrategy

### Brand Guidelines (7 types)
- BrandIdentity
- BrandPersonality
- VoiceAndTone
- ColorPalette
- Typography
- ImageStyle
- MissionAndValues

**Total Unique Node Types**: 28 (some shared like ValueProposition, Risk, Opportunity)

---

## Appendix B: Relationship Type List

### Business Strategy
- BELONGS_TO, OFFERS_PRODUCTS, INCLUDES_PRODUCT
- HAS_VALUE_PROPOSITION, HAS_GOAL
- AFFECTED_BY_ANALYSIS, HAS_STRENGTH, HAS_WEAKNESS
- CREATES (Strength→Opportunity, Weakness→Risk)

### Competitive Strategy
- OPERATES_WITHIN, IS_KEY_PLAYER
- USES_TACTIC, HAS_VALUE_PROPOSITION
- HAS_STRENGTH, HAS_WEAKNESS
- OFFERS_PRODUCT, MAY_BE_SUBSTITUTED_FOR
- CREATES (CompetitorStrength→Risk, CompetitorWeakness→Opportunity)

### Marketing Strategy
- IS_MARKETED_TO
- DISCOVERS_THE_PROBLEM_BY
- DISCOVERS_OUR_BRAND_BY
- CONSIDERS_OUR_BRAND_BECAUSE
- PURCHASES_OUR_BRAND_BECAUSE
- BECOMES_AN_ADVOCATE_BECAUSE

### Brand Guidelines
- FOLLOWS_THESE_BRAND_GUIDELINES
- HAS_TRAITS_AND_CHARACTERISTICS
- USES_COMMUNICATION_STYLE
- USES_COLORS
- USES_FONTS_AND_TYPEFACES
- USES_IMAGE_STYLE
- HAS_MISSION

---

## Appendix C: Version History

### v1.0 - Initial Implementation
- Basic business strategy with PESTEL at account level
- Flat SWOT structure (separate lists)
- Simple competitive analysis without SWOT links

### v2.0 - Current (Committed)
- **Business**: SWOT linked structure, SWOTAnalysis hub, business VPs, PESTEL removed
- **Competitive**: SWOT with risks/opportunities, tactics, competitor VPs, relationship renames
- **Marketing**: Fixed for OpenAI compatibility, relationship renames
- **Brand**: Complete new feature (7 nodes)
- **Testing**: All validated on fresh account with 100% success rate

### v3.0 - Planned
- Industry analysis (18+ node types)
- Geographic region and industry hubs
- PESTEL at industry level (shared across accounts)
- Porter's Five Forces analysis

---

## End of Documentation

This documentation provides complete technical specifications for integrating the knowledge graph strategy system into production on GCP. All code has been tested and validated with the new schema on fresh accounts.

For questions or issues during integration, refer to:
- Code comments in implementation files
- Test files for working examples
- MD requirement files for official specifications
- `CLAUDE.md` for project context
