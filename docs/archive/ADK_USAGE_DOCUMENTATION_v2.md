# Agent Development Kit (ADK) Usage Documentation v2

## Overview

The Agent Development Kit (ADK) powers AI-driven features in the KEN-E application through Google's Vertex AI Agent Engine. This document describes the separated agent architecture where different agents handle specific responsibilities:

1. **Chat Interface**: User interactions through the KEN-E agent
2. **Account Creation**: Automatic strategy document generation through a dedicated supervisor

## Architecture Overview

### Separated Agent Design

The system uses two independently deployed ADK agents:

#### 1. KEN-E Agent (`ken_e_agent`)
- **Purpose**: Handles all frontend chat interactions
- **Capabilities**: Company news and Google Analytics queries
- **Deployment**: Separate Agent Engine instance
- **API Endpoint**: `/api/v1/chat/completions`
- **Environment Variable**: `KEN_E_ENGINE_ID`

#### 2. Strategy Supervisor (`create_strategy_docs_supervisor`)
- **Purpose**: Generates strategy documents during account creation only
- **Capabilities**: Creates 5 strategy documents
- **Deployment**: Separate Agent Engine instance
- **API Access**: Direct invocation from `trigger_strategy_generation` task
- **Environment Variable**: `STRATEGY_SUPERVISOR_ENGINE_ID`

### Agent Hierarchy

```
Frontend Chat Interface
└── KEN-E Agent (Main Chat Router)
    ├── Company News Agent
    └── Google Analytics Agent

Account Creation Process
└── Strategy Supervisor (Strategy-Only Router)
    └── Strategy Agent (Sequential Pipeline)
        ├── 1. Business Strategy Agent
        ├── 2. Competitive Strategy Agent
        ├── 3. Customer Strategy Agent
        ├── 4. Marketing Strategy Agent
        └── 5. Brand Guidelines Agent
```

### Key Design Principles

1. **Separation of Concerns**: Chat and strategy generation are completely separated
2. **Independent Deployment**: Each agent can be deployed and scaled independently
3. **Clear API Boundaries**: Different endpoints for different purposes
4. **Reusable Utilities**: Shared code extracted to utility modules

## Process 1: Chat Interface with KEN-E

### Flow Overview

Users interact with the AI assistant through the web interface, which routes to the KEN-E agent for company news and analytics queries.

### Detailed Implementation

#### 1. Frontend Chat Service
**File**: `frontend/src/services/chatService.ts`

The chat service sends messages to the KEN-E-specific endpoint:
- Endpoint: `/api/v1/ken-e/chat/completions`
- Handles streaming responses
- Manages conversation sessions

#### 2. Chat API Router
**File**: `api/src/kene_api/routers/chat.py`

Router for chat interactions:
```python
@router.post("/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    current_user: UserContext = Depends(get_current_user)
) -> ChatCompletionResponse:
    """Create a chat completion using KEN-E agent."""
```

#### 3. Agent Engine Client
**File**: `api/src/kene_api/routers/chat.py:AgentEngineClient`

Manages connection to KEN-E agent:
- Uses `KEN_E_ENGINE_ID` or falls back to `VERTEX_AI_AGENT_ENGINE_ID`
- Handles streaming responses
- Manages user sessions

#### 4. KEN-E Agent Definition
**File**: `app/adk/agents/ken_e_agent.py`

The KEN-E agent:
- Model: `gemini-2.0-flash`
- Tools: `search_company_news`, `query_google_analytics`
- No access to strategy generation

### Routing Logic

KEN-E uses LLM-based routing to determine which sub-agent to invoke:
- Company/market queries → Company News Agent
- Analytics/traffic queries → Google Analytics Agent
- Strategy requests → Polite explanation that strategies are generated during account creation

## Process 2: Account Creation with Strategy Generation

### Flow Overview

When a user creates a new account, the system automatically triggers strategy document generation using the dedicated strategy supervisor agent.

### Detailed Implementation

#### 1. Account Creation Endpoint
**File**: `api/src/kene_api/routers/accounts.py`

POST `/api/v1/accounts/`:
- Accepts account details and optional business documents
- Triggers strategy generation as background task

#### 2. Account Service
**File**: `api/src/kene_api/services/account_service.py`

The `create_account_internal` function:
- Creates account in Neo4j
- Triggers `trigger_strategy_generation` task
- Sets up Firestore collections

#### 3. Strategy Generation Task
**File**: `api/src/kene_api/tasks/strategy_tasks.py`

Direct invocation of strategy supervisor:
```python
async def trigger_strategy_generation(...):
    strategy_agent_id = os.getenv("STRATEGY_SUPERVISOR_ENGINE_ID") or os.getenv("VERTEX_AI_AGENT_ENGINE_ID")
    agent_engine = agent_engines.get(strategy_agent_id)
    
    # Format message for strategy generation
    message = f"Generate all 5 strategy documents for {company_name}..."
    
    # Stream query to strategy supervisor
    for chunk in agent_engine.stream_query(message, user_id, session_id):
        # Process response
```

#### 4. Strategy Supervisor Agent
**File**: `app/adk/agents/create_strategy_docs_supervisor.py`

Simplified supervisor for strategy only:
- Model: `gemini-2.0-flash`
- Single tool: `create_strategy`
- Only responds to "Generate all 5 strategy documents" requests

#### 5. Strategy Orchestrator
**File**: `app/adk/agents/strategy_agent/orchestrator.py`

Manages sequential execution of 5 strategy agents with cascading context.

## ADK Agent Definitions

### KEN-E Agent Structure

```python
# app/adk/agents/ken_e_agent.py

def create_ken_e_agent():
    ken_e = Agent(
        name="ken_e",
        model="gemini-2.0-flash",
        instruction="...",  # Chat-focused instructions
        tools=[search_company_news, query_google_analytics]
    )
    return ken_e
```

### Strategy Supervisor Structure

```python
# app/adk/agents/create_strategy_docs_supervisor.py

def create_strategy_supervisor():
    supervisor = Agent(
        name="create_strategy_docs_supervisor",
        model="gemini-2.0-flash",
        instruction="...",  # Strategy-only instructions
        tools=[create_strategy]
    )
    return supervisor
```

## Shared Utilities

### Supervisor Utilities
**File**: `app/adk/agents/utils/supervisor_utils.py`

Extracted reusable functions:
- `extract_tenant_context()`: Parse input for tenant information
- `invoke_agent_sync()`: Synchronous agent invocation wrapper
- `dispatch_with_context()`: Context-aware dispatch wrapper

### Dispatch Handlers
**File**: `app/adk/agents/utils/dispatch_handlers.py`

Agent-specific dispatch logic:
- `dispatch_to_company_news()`: Route to news agent
- `dispatch_to_google_analytics()`: Route to analytics agent
- `dispatch_to_strategy()`: Route to strategy orchestrator

## Deployment Configuration

### Environment Variables

```bash
# KEN-E Agent (Chat)
KEN_E_ENGINE_ID=projects/{project}/locations/{location}/reasoningEngines/{ken-e-id}

# Strategy Supervisor (Account Creation)
STRATEGY_SUPERVISOR_ENGINE_ID=projects/{project}/locations/{location}/reasoningEngines/{strategy-id}

# Legacy/Fallback (kept for backward compatibility)
VERTEX_AI_AGENT_ENGINE_ID=projects/{project}/locations/{location}/reasoningEngines/{old-id}

# Common Configuration
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev
VERTEX_AI_LOCATION=us-central1
```

### Deployment Scripts

#### Deploy KEN-E
**File**: `app/adk/deploy_ken_e.py`

```bash
cd app/adk
uv run python deploy_ken_e.py
```

#### Deploy Strategy Supervisor
**File**: `app/adk/deploy_strategy_supervisor.py`

```bash
cd app/adk
uv run python deploy_strategy_supervisor.py
```

### ADK App Configurations

#### KEN-E App
**File**: `app/adk/ken_e_app.py`

```python
from vertexai.preview import reasoning_engines
from agents.ken_e_agent import ken_e_agent

app = reasoning_engines.AdkApp(
    agent=ken_e_agent,
    enable_tracing=True
)
```

#### Strategy App
**File**: `app/adk/agent_engine_app.py`

```python
from vertexai.preview import reasoning_engines
from agents.create_strategy_docs_supervisor import create_strategy_docs_supervisor

app = reasoning_engines.AdkApp(
    agent=create_strategy_docs_supervisor,
    enable_tracing=True
)
```

## API Endpoints

### Chat Endpoints (KEN-E)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/chat/completions` | POST | Chat with KEN-E agent |
| `/api/v1/chat/sessions` | GET | List user sessions |
| `/api/v1/chat/sessions/{id}` | GET | Get session history |

### Account Endpoints (Trigger Strategy)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/accounts/` | POST | Create account (triggers strategy) |
| `/api/v1/accounts/{id}/strategy-status` | GET | Check strategy generation status |

## File Locations

### Agent Definitions

| Component | File | Purpose |
|-----------|------|---------|
| KEN-E Agent | `app/adk/agents/ken_e_agent.py` | Chat agent definition |
| Strategy Supervisor | `app/adk/agents/create_strategy_docs_supervisor.py` | Strategy-only supervisor |
| Shared Utilities | `app/adk/agents/utils/supervisor_utils.py` | Reusable functions |
| Dispatch Handlers | `app/adk/agents/utils/dispatch_handlers.py` | Agent routing logic |

### API Layer

| Component | File | Purpose |
|-----------|------|---------|
| Chat Router | `api/src/kene_api/routers/chat.py` | Chat API endpoints |
| Account Router | `api/src/kene_api/routers/accounts.py` | Account creation |
| Strategy Tasks | `api/src/kene_api/tasks/strategy_tasks.py` | Strategy generation |

### Deployment

| Component | File | Purpose |
|-----------|------|---------|
| KEN-E Deployment | `app/adk/deploy_ken_e.py` | Deploy chat agent |
| Strategy Deployment | `app/adk/deploy_strategy_supervisor.py` | Deploy strategy agent |
| KEN-E App | `app/adk/ken_e_app.py` | ADK app config |
| Strategy App | `app/adk/agent_engine_app.py` | ADK app config |

## Testing Strategy

### Unit Tests

```bash
# Test KEN-E agent
pytest app/adk/agents/tests/test_ken_e_agent.py

# Test strategy supervisor
pytest app/adk/agents/tests/test_strategy_supervisor.py

# Test shared utilities
pytest app/adk/agents/tests/test_supervisor_utils.py
```

### Integration Tests

```bash
# Test KEN-E chat API
pytest api/tests/integration/test_ken_e_chat.py

# Test account creation with strategy
pytest api/tests/integration/test_account_creation.py
```

## Monitoring and Debugging

### Key Log Points

1. **KEN-E Chat**: `[KEN-E]` prefix in logs
2. **Strategy Generation**: `[STRATEGY_GENERATION]` prefix
3. **Agent Routing**: `[DISPATCH]` prefix for routing decisions
4. **Agent Invocation**: `[INVOKE]` prefix for agent calls

### Common Issues and Solutions

#### KEN-E Not Responding
- Check `KEN_E_ENGINE_ID` environment variable
- Verify agent is deployed: `gcloud ai reasoning-engines list`
- Check API logs for connection errors
- Verify fallback to `VERTEX_AI_AGENT_ENGINE_ID` if primary not set

#### Strategy Not Generating
- Check `STRATEGY_SUPERVISOR_ENGINE_ID` environment variable
- Verify strategy supervisor is deployed
- Check Firestore for partial documents
- Review task logs for errors
- Verify fallback to `VERTEX_AI_AGENT_ENGINE_ID` if primary not set

#### Wrong Agent Responding
- Verify API endpoints are correctly configured
- Check environment variables for agent IDs
- Ensure proper routing in API layer

## Pydantic Validation and Error Handling

### Current Implementation

All strategy agents use ADK's built-in `output_schema` parameter for automatic validation:

```python
agent = Agent(
    model="gemini-2.5-pro",
    instructions=instructions,
    output_schema=BusinessStrategy  # ADK handles validation
)
```

### How ADK Handles Validation

When `output_schema` is provided, ADK automatically:
1. Validates agent responses against Pydantic schema
2. Retries on validation errors with clearer instructions
3. Extracts JSON from markdown or mixed text
4. Provides error feedback to agent on retry

## Analytics and Monitoring

### Analytics Service
**File**: `app/adk/agents/strategy_agent/analytics_service.py`

Tracks metrics for both agents:
- Token usage and costs
- Execution times
- Error rates
- Success rates

### Performance Profiling
**File**: `app/adk/agents/strategy_agent/performance_profiler.py`

Identifies bottlenecks:
- Agent response times
- Token consumption patterns
- Retry frequencies

## Migration from v1

### Key Changes

1. **Separated Agents**: Single supervisor split into KEN-E and strategy supervisor
2. **Same Endpoint**: `/api/v1/chat/completions` (no change to frontend)
3. **Environment Variables**: 
   - Old: `VERTEX_AI_AGENT_ENGINE_ID` (kept for fallback)
   - New: `KEN_E_ENGINE_ID`, `STRATEGY_SUPERVISOR_ENGINE_ID`
4. **Deployment**: Two separate Agent Engine deployments

### Backward Compatibility

- Same chat endpoint maintained (`/api/v1/chat/completions`)
- Environment variable fallback to `VERTEX_AI_AGENT_ENGINE_ID`
- Existing Firestore documents remain unchanged
- No frontend changes required

## Best Practices

### Code Organization
- Agent definitions in `app/adk/agents/`
- Shared utilities in `app/adk/agents/utils/`
- API routers in `api/src/kene_api/routers/`
- Keep separation between chat and strategy clear

### Testing
- Unit test each agent independently
- Integration test API endpoints
- End-to-end test both flows separately

### Deployment
- Deploy agents independently
- Update environment variables atomically
- Test in development before staging/production

### Monitoring
- Use distinct log prefixes for each agent
- Track metrics separately for chat vs strategy
- Monitor token usage per agent

## Future Enhancements

1. **Additional Chat Capabilities**: Add more tools to KEN-E as needed
2. **Strategy Refinement**: Allow manual strategy regeneration
3. **Session Management**: Enhanced conversation history
4. **Analytics Dashboard**: Visualize agent performance metrics
5. **A/B Testing**: Compare different agent configurations
6. **Cost Optimization**: Automatic model selection based on query complexity