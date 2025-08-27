# Strategy Agent Implementation Plan

## Overview
This plan outlines the integration of an iterative strategy agent (from the Jupyter notebook) into the KEN-E chatbot system, along with adding Weights & Biases (Weave) observability for cost tracking and debugging.

## Part 1: Integrate Iterative Strategy Agent into Current Chatbot

### Task Group A: Core Agent Implementation
1. **Create new ADK agent module** (`app/agents/strategy_agent/`)
   - Convert notebook code to production Python modules
   - `strategy_agent.py` - Main iterative strategy agent
   - `sub_agents.py` - Strategist, reviewer, editor agents  
   - `tools.py` - Search tools, exit_loop function
   - `models.py` - Pydantic models for strategy documents

2. **Integrate with existing supervisor** (`app/agents/multi_agent_supervisor_v2.py`)
   - Add strategy agent as a sub-agent to supervisor
   - Create routing logic to detect strategy-related queries
   - Pass user context (Firebase UID + account_id) to strategy agent

3. **Create Firestore integration layer**
   - Add new collection: `strategy_documents`
   - Structure: `/accounts/{account_id}/strategy_docs/{doc_type}/{doc_id}`
   - Store: business_strategy, competitive_strategy, channel_strategies
   - Include version history and last_modified timestamps

### Task Group B: API & Storage Layer
1. **Create new API router** (`api/src/kene_api/routers/strategy.py`)
   - GET `/api/v1/strategy/{account_id}/documents` - List all docs
   - GET `/api/v1/strategy/{account_id}/documents/{doc_type}` - Get specific doc
   - POST `/api/v1/strategy/{account_id}/documents/{doc_type}` - Create/update doc
   - GET `/api/v1/strategy/{account_id}/templates/{doc_type}` - Get best practices

2. **Add Firestore models**
   - StrategyDocument model with JSON schema validation
   - Best practices templates storage
   - Reviewer guidelines storage

3. **Implement access control**
   - Check user has account access via existing auth system
   - Strategy docs scoped to account_id
   - Audit trail for document changes

### Task Group C: Integration & Testing
1. **Modify strategy agent to use Firestore**
   - Fetch existing strategy docs on agent initialization
   - Auto-save documents after approval (exit_loop)
   - Load best practices and guidelines from Firestore

2. **Session management**
   - Use ADK Session Service for conversation continuity
   - Store session metadata in Firestore
   - Link sessions to account_id for proper scoping

3. **Testing framework**
   - Unit tests for each sub-agent
   - Integration tests for full workflow
   - Mock Firestore for testing

## Part 2: Add Weights & Biases (Weave) Observability

### Task Group D: Observability Setup
1. **Environment configuration**
   - Add dependencies: `weave`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`
   - Use existing W&B project: `quickstart_playground`
   - Configure environment variables for API keys

2. **Create observability wrapper** (`app/utils/observability.py`)
   ```python
   def setup_weave_tracing(project_name="quickstart_playground"):
       # Initialize with existing project
       weave.init(project_name=project_name)
       # Configure OTLP exporter
       # Set tracer provider before ADK imports
       # Return configured tracer
   ```

3. **Instrument ADK agents**
   - Wrap agent creation with `@weave.op()` decorators
   - Track tool invocations
   - Log token usage per agent

### Task Group E: Cost Tracking & Reporting
1. **Token counting system**
   - Track prompt/response tokens per agent
   - Map agents to their model types (Gemini versions)
   - Calculate costs based on model pricing

2. **User attribution**
   - Tag all traces with user_id and account_id
   - Aggregate costs per user/account
   - Store daily/monthly summaries in Firestore

3. **Cost reporting API**
   - GET `/api/v1/usage/{user_id}/costs` - User's usage costs
   - GET `/api/v1/usage/{account_id}/costs` - Account-level costs
   - Support date range filtering

## Implementation Approach

### Dependencies Between Tasks:
```
A.1 (Core Agent) → A.2 (Supervisor Integration)
                 ↘
                   C.1 (Firestore Integration) ← B.2 (Firestore Models)
                 ↗
B.1 (API Router)

D.1 (Weave Setup) → D.2 (Wrapper) → D.3 (Instrumentation)
                                  ↘
                                    E.1 (Token Counting) → E.2 (Attribution)
```

### Suggested Development Order:
1. **Minimal Viable Integration** (can be done first):
   - A.1: Convert notebook to basic module
   - D.1-D.2: Setup Weave with existing project
   - Test: Verify agent works and traces appear in W&B

2. **Add Persistence** (can be done in parallel):
   - B.2: Create Firestore models
   - B.1: Create API endpoints
   - C.1: Connect agent to Firestore

3. **Full Integration**:
   - A.2: Integrate with supervisor
   - C.2: Add session management
   - D.3: Full instrumentation

4. **Cost Tracking** (can be added anytime after D.2):
   - E.1-E.2: Implement cost tracking
   - E.3: Add reporting endpoints

## Testing Strategy

**For Each Component:**
- Unit tests as you build
- Integration test when connecting components
- Manual testing in notebook first (like existing notebook)
- Deploy to staging for full testing

## Key Technical Decisions

1. **Use existing auth system** - Leverage current Firebase UID + account_id
2. **Firestore for persistence** - Consistent with current architecture
3. **Use existing W&B project** - `quickstart_playground` for immediate start
4. **Configurable project name** - Easy migration to production W&B project later
5. **Modular design** - Easy to extend with more strategy types
6. **Cost attribution** - Essential for usage-based billing

## Key Context from Analysis

### Notebook Functionality (`KEN_E____ADK____Iterative_Strategy_Agent.ipynb`)
- **Iterative Strategy Agent**: Sequential agent with two steps:
  1. Strategist agent creates/modifies document
  2. Refinement loop (reviewer + editor) ensures quality
- **Can handle both**: Creating new strategies AND editing existing ones
- **Uses Google Search and Vertex AI Search** for research
- **Already has Weave integration** (commented out: `weave.init(project_name="quickstart_playground")`)

### Current System Architecture
- **Authentication**: Firebase UID is permanent per user, account_id is KEN-E business concept
- **Authorization**: Users have limited access to specific accounts via permissions system
- **Current chatbot**: Located in `app/simple_company_chatbot/`, uses ADK with multi-agent supervisor
- **API**: FastAPI with routers, Firestore for document storage, Neo4j for graph data
- **Frontend**: Calls chat API endpoints, maintains session_id for conversations

### Implementation Notes
- Strategy documents need to be scoped per account_id
- User context includes both Firebase UID and selected account_id
- Existing W&B project "quickstart_playground" can be used immediately
- Migration to production W&B project is just a config change

## Todo List for Implementation

- [ ] A1: Create ADK strategy agent module structure
- [ ] A2: Convert notebook code to production modules
- [ ] A3: Integrate strategy agent with supervisor
- [ ] B1: Create Firestore models for strategy documents
- [ ] B2: Create API router for strategy documents
- [ ] B3: Implement access control for strategy docs
- [ ] C1: Connect agent to Firestore for persistence
- [ ] C2: Add session management
- [ ] D1: Setup Weave observability with quickstart_playground
- [ ] D2: Create observability wrapper
- [ ] D3: Instrument agents with Weave
- [ ] E1: Implement token counting and cost tracking
- [ ] E2: Add user attribution for costs
- [ ] E3: Create cost reporting API endpoints
- [ ] T1: Write unit tests
- [ ] T2: Write integration tests