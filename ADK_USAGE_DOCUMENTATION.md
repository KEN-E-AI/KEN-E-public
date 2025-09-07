# Agent Development Kit (ADK) Usage Documentation

## Overview

The Agent Development Kit (ADK) is used in the KEN-E application to power AI-driven features through Google's Vertex AI Agent Engine. This document explains how ADK is integrated into two key processes:

1. **Account Creation**: Automatic generation of strategy documents when a new account is created
2. **Chat Interface**: User-initiated conversations with the AI assistant

## Architecture Overview

The ADK implementation uses a multi-agent supervisor pattern with two layers:

### Two-Layer Architecture
- **Supervisor Layer** (`multi_agent_supervisor_v2.py`): Routes strategy requests between News, Analytics, and Strategy agents
- **Orchestrator Layer** (`orchestrator.py`): Manages sequential agent execution using Runner class

### Agent Hierarchy
```
create_strategy_docs_supervisor (Main Router)
├── Company News Agent
├── Google Analytics Agent  
└── Strategy Agent (Sequential Pipeline)
    ├── 1. Business Strategy Agent (LoopAgent with 3 internal roles)
    ├── 2. Competitive Strategy Agent (LoopAgent with 3 internal roles)  
    ├── 3. Customer Strategy Agent (LoopAgent with 3 internal roles)
    ├── 4. Marketing Strategy Agent (LoopAgent with 3 internal roles)
    └── 5. Brand Guidelines Agent (LoopAgent with 3 internal roles)
```

### Sequential Pipeline with Cascading Context
The system processes strategy documents in a strict order with each agent building on previous work:

| Order | Agent | Accesses Previous Docs | Key Focus | Model |
|-------|-------|------------------------|-----------|-------|
| 1 | **Business Strategy** | None | Company overview, market analysis, SWOT | gemini-2.5-pro (strategist), gemini-2.5-flash (reviewer/editor) |
| 2 | **Competitive Strategy** | business_strategy_doc | Competition analysis, positioning | gemini-2.5-pro (strategist), gemini-2.5-flash (reviewer/editor) |
| 3 | **Customer Strategy** | business + competitive docs | Personas, journey maps, insights | gemini-2.5-pro (strategist), gemini-2.5-flash (reviewer/editor) |
| 4 | **Marketing Strategy** | business + competitive + customer docs | Campaigns, channels, metrics | gemini-2.5-pro (strategist), gemini-2.5-flash (reviewer/editor) |
| 5 | **Brand Guidelines** | All previous docs (optional) | Identity, voice, visual standards | gemini-2.5-pro (strategist), gemini-2.5-flash (reviewer/editor) |

### Internal Refinement Pattern
Each strategy agent contains:
- **SequentialAgent**: Orchestrates the refinement process
- **LoopAgent**: Manages iterations (max 3)
- **Strategist**: Creates initial document using templates (gemini-2.5-pro for quality)
- **Reviewer**: Evaluates against quality guidelines (gemini-2.5-flash for speed/cost)
- **Editor**: Refines based on review feedback (gemini-2.5-flash for speed/cost)

### Model Optimization Strategy
- **Strategists** (5 agents): Use `gemini-2.5-pro` for high-quality document generation
- **Supporting agents** (10 reviewers/editors): Use `gemini-2.5-flash` for cost/speed optimization
- **Tool agents**: Use `gemini-2.5-flash` for Google Search operations

## Process 1: Account Creation with Strategy Document Generation

### Flow Overview

When a user creates a new account, the system automatically triggers the generation of 5 strategy documents using the ADK-powered strategy agent.

### Detailed Implementation

#### 1. Account Creation Endpoint
**File**: `api/src/kene_api/routers/accounts.py:549`

The account creation starts at the POST `/api/v1/accounts/` endpoint which:
- Accepts multipart form data with account details
- Optionally accepts uploaded business documents
- Calls the internal account creation service

#### 2. Internal Account Service  
**File**: `api/src/kene_api/services/account_service.py:35-275`

The `create_account_internal` function:
- Validates the organization exists and is not an agency (line 76-98)
- Triggers strategy generation as a background task (line 109-120)
- Creates the account in Neo4j database (line 146-184)
- Sets up Firestore collections for strategy documents (line 223-239)

#### 3. Strategy Generation Task
**File**: `api/src/kene_api/tasks/strategy_tasks.py:22-781`

The `trigger_strategy_generation` function handles two paths:

**Path A: System-Triggered (Account Creation)**
- Lines 196-482: Direct Vertex AI Agent Engine invocation
- Uses `vertexai.agent_engines.get()` to get the deployed agent (line 230)
- Calls `agent_engine.stream_query()` with formatted parameters (line 245)
- Collects streaming response chunks (lines 267-409)
- Waits for document completion with polling (lines 424-466)

**Path B: User-Triggered (From Chat)**
- Lines 122-194: Uses existing user authentication context
- Calls through `AgentEngineClient.chat_completion()` (line 130)
- Also waits for document completion (lines 142-178)

#### 4. Agent Engine Communication
The strategy task formats a specific message for the supervisor agent:

```python
# Line 93-106 in strategy_tasks.py
message = f"""Generate all 5 strategy documents for {company_name}

Please execute strategy generation with these parameters:
- company_name: {company_name}
- industry: {industry}
- websites: {",".join(websites)}
- customer_regions: {",".join(customer_regions)}
- account_id: {account_id}
- user_id: {user_id}
- annual_ad_budget: {annual_ad_budget}
- project_id: {project_id}
"""
```

#### 5. Uploaded Document Processing
**File**: `api/src/kene_api/routers/accounts.py:647-711`

When files are uploaded during account creation:
- Files are validated for allowed extensions (.pdf, .xlsx, .docx, .pptx, .txt, .png, .jpg, .jpeg)
- Maximum file size: 25MB per file, 100MB total
- Files are uploaded to GCS using `StorageService.upload_business_documents()` (line 691)
- GCS URLs are extracted and passed to the account creation service (lines 698-700)

**File**: `api/src/kene_api/services/storage_service.py:118-227`

The `upload_business_documents` method:
- Uploads files to environment-specific GCS buckets (e.g., `ken-e-dev-files-us`)
- Files are stored at path: `accounts/{account_id}/{filename}` (line 157)
- Returns GCS URLs in format: `gs://bucket-name/accounts/{account_id}/{filename}` (line 199)

**File**: `api/src/kene_api/services/account_service.py:104-118`

The uploaded document URLs are passed to the strategy generation task:
- URLs are logged if present (line 105)
- Passed as `uploaded_document_urls` parameter to `trigger_strategy_generation()` (line 118)

**File**: `api/src/kene_api/tasks/strategy_tasks.py:104-109`

The strategy task includes uploaded documents in the agent message:
- If documents exist, adds them as comma-separated URLs (line 106)
- Format: `- uploaded_documents: url1,url2,url3`

#### 6. Document Verification
**File**: `api/src/kene_api/tasks/strategy_tasks.py:580-716`

The `verify_strategy_documents_created` function:
- Checks Firestore collection `strategy_docs_{account_id}` (line 598)
- Verifies all 5 expected documents exist:
  - business_strategy
  - competitive_strategy
  - customer_strategy
  - marketing_strategy
  - brand_guidelines
- Validates document completeness based on content size and structure (lines 625-645)

## Process 2: Chat Interface

### Flow Overview

Users can initiate conversations with the AI assistant through the web interface, which routes through the API to the Agent Engine.

### Detailed Implementation

#### 1. Frontend Chat Service
**File**: `frontend/src/services/chatService.ts:1-303`

The `ChatService` class:
- Sends chat messages to API endpoint `/api/v1/chat/completions` (line 91)
- Handles streaming responses (lines 113-165)
- Manages conversation sessions and history

#### 2. Chat API Router
**File**: `api/src/kene_api/routers/chat.py:1-900`

The chat router provides:
- `POST /api/v1/chat/completions` endpoint (line not shown in excerpt)
- Session management through ADK `VertexAiSessionService` (lines 159-177)
- Conversation tracking and metadata storage

#### 3. Agent Engine Client
**File**: `api/src/kene_api/routers/chat.py:102-799`

The `AgentEngineClient` class:
- Lazy-loads the agent engine using `agent_engines.get()` (line 135)
- Manages user sessions with ADK session service (lines 179-399)
- Processes chat completions through `chat_completion()` method (lines 570-799)

#### 4. Chat Completion Processing
**File**: `api/src/kene_api/routers/chat.py:570-799`

The `chat_completion` method:
- Gets or creates a session for the user (line 594)
- Auto-generates conversation names from first message (lines 600-610)
- Calls `agent_engine.stream_query()` with parameters (lines 646-650)
- Processes streaming response chunks (lines 657-749)
- Handles various response formats from the agent

## ADK Supervisor Agent

### Agent Configuration
**File**: `app/adk/agents/create_strategy_docs_supervisor.py:1-453`

The supervisor agent (`create_strategy_docs_supervisor`):
- Routes queries to specialized agents based on intent (lines 368-447)
- Three main capabilities:
  1. **Company News**: Routes to `news_agent` (line 126-150)
  2. **Google Analytics**: Routes to `google_analytics_agent_v4` (line 153-203)
  3. **Strategy Generation**: Routes to `strategy_agent` (line 206-319)

### Routing Logic
The supervisor uses LLM-based routing with these patterns:
- Messages starting with "Generate all 5 strategy documents" → strategy agent
- Analytics/traffic queries → Google Analytics agent
- Company news/financial queries → news agent

### Strategy Agent Dispatcher
**File**: `app/adk/agents/create_strategy_docs_supervisor.py:206-319`

The `dispatch_to_strategy` function:
- Parses structured parameters from the formatted message (lines 236-263)
- Extracts `uploaded_documents` parameter and converts to list (lines 258-260)
- Calls `invoke_strategy_agent_sync()` with extracted parameters (lines 291-301)
- Passes `uploaded_documents` list to strategy orchestrator (line 299)
- Returns results with account context

### Strategy Agent Document Processing
**File**: `app/adk/agents/strategy_agent/orchestrator.py:121-237`

The `execute_strategy_generation` function:
- Receives `uploaded_documents` parameter as list of GCS URLs (line 130)
- Calls `load_uploaded_documents_as_artifacts()` to process documents (lines 193-199)
- Creates `GcsArtifactService` with uploaded documents loaded as artifacts (line 206)

**File**: `app/adk/agents/strategy_agent/artifact_utils.py:159-237`

The `load_uploaded_documents_as_artifacts` function:
- Parses GCS URLs to extract bucket and blob paths (lines 219-222)
- Downloads each document from GCS using Storage Client (line 224-226)
- Creates ADK `Part` objects from document content (lines 111-114)
- Saves documents as artifacts with prefix `input_strategy_` (line 144)
- Artifacts are stored in `GcsArtifactService` for agent access (lines 204-206)
- Logs success count of loaded documents (line 235)

**File**: `app/adk/agents/strategy_agent/agents.py:119-157`

Strategy agents are instructed to use uploaded documents:
- Each agent checks for artifacts starting with `input_strategy_` (lines 120-124)
- Instructions to list available artifacts: `context.list_artifacts()` (line 122)
- Filter for strategy documents: `[a for a in artifacts if a.filename.startswith('input_strategy_')]` (line 123)
- Load document content: `context.load_artifact(doc.filename)` (line 124)
- Extract relevant insights from uploaded documents (lines 125-131)
- Incorporate uploaded document insights into new strategy (lines 134, 154)

## File Locations

| Component | File | Purpose |
|-----------|------|---------|
| Main Supervisor | `app/adk/agents/multi_agent_supervisor_v2.py` | Routes requests between News, Analytics, and Strategy agents |
| Strategy Orchestrator | `app/adk/agents/strategy_agent/orchestrator.py` | Manages sequential execution with Runner class |
| Agent Definitions | `app/adk/agents/strategy_agent/agents.py` | Contains all 5 strategy agent definitions |
| Data Models | `app/adk/agents/strategy_agent/models.py` | StrategyContext and data structures |
| Firestore Integration | `app/adk/agents/strategy_agent/firestore.py` | Document storage and retrieval |
| Dependency Injection | `app/adk/agents/strategy_agent/providers.py` | Abstract interfaces for external dependencies |
| Deployment Scripts | `app/adk/agents/deploy_supervisor.py` | Deploys to Vertex AI Agent Engine |
| Artifact Utils | `app/adk/agents/strategy_agent/artifact_utils.py` | Handles uploaded document processing |

## Execution Flow

### Complete Strategy Generation Flow
1. **Account Creation** triggers strategy generation via API
2. **Multi-Agent Supervisor** (`multi_agent_supervisor_v2.py`) receives and routes request
3. **Strategy Orchestrator** (`orchestrator.py`) is invoked via `execute_strategy_generation()`
4. **Runner** class executes the SequentialAgent with all 5 sub-agents
5. **Events** are monitored and documents saved immediately upon completion
6. **Firestore** stores completed documents in `strategy_docs_{account_id}`

### Typical Execution Time
The system deploys to Vertex AI Agent Engine using ADK (Agent Development Kit) and runs as a sequential pipeline that typically takes 3-5 minutes to generate all strategy documents with the optimized model configuration.

## Agent Engine Deployment

### Deployment Configuration
**File**: `app/adk/agents/agent_engine_app.py:1-23`

The agent is deployed as an ADK app:
```python
app = reasoning_engines.AdkApp(
    agent=create_strategy_docs_supervisor,
    enable_tracing=True
)
```

### Environment Configuration

Required environment variables:
- `VERTEX_AI_PROJECT_ID`: GCP project ID (ken-e-dev/staging/production)
- `VERTEX_AI_LOCATION`: Region (us-central1)
- `VERTEX_AI_AGENT_ENGINE_ID`: Deployed agent engine ID
- `GOOGLE_CLOUD_PROJECT_ID`: Current GCP project

## Key Implementation Details

### State Management
Documents are saved to conversation state with unique output keys:
- `business_strategy_doc`
- `competitive_strategy_doc`
- `customer_strategy_doc`
- `marketing_strategy_doc`
- `brand_guidelines_doc`

### Session Management
- ADK sessions are managed through `VertexAiSessionService`
- Sessions track conversation history and user context
- Session IDs follow format: `chat_{timestamp}_{random}` or ADK-generated IDs

### Error Handling
- Timeout handling: 600 seconds (10 minutes) for complex requests
- Fallback session creation if ADK service fails
- Document verification with retry logic

### Document Storage
- **Input**: Templates from `strategy_doc_guides` Firestore collection
- **Output**: Final documents to `strategy_docs_{account_id}` Firestore collection
- **Immediate Saving**: Documents saved to Firestore as each agent completes
- Each document contains structured content with metadata
- Status tracking for document generation progress

### Authentication Flow
- Frontend: Firebase Auth token attached to requests
- API: Token validation and user context extraction
- Agent Engine: User context passed with queries

### Tool Access
Available tools for agents:
- **Google Search Agent**: External web research (all strategists/editors can access)
- **exit_loop**: Signals approval to exit refinement loop
- Note: Internal Search Agent removed for optimization

### Enhanced Instructions
Each agent's instructions include:
- Mandatory research requirements with citations
- Specific search query examples
- Instructions to review prior strategy documents
- Process steps for document creation and validation

## Monitoring and Debugging

### Key Log Points
1. Account creation: `[ACCOUNT_CREATION]` prefix in logs
2. Strategy generation: `[STRATEGY_GENERATION]` prefix
3. Agent Engine calls: Look for "Calling agent engine" messages
4. Document verification: "Verifying strategy documents" messages

### Common Issues and Solutions

1. **Agent Engine Timeout**
   - Default timeout: 600 seconds
   - Can occur with complex strategy generation
   - Solution: Monitor logs for timeout messages, retry if needed

2. **Document Generation Incomplete**
   - Verification polls for up to 30 minutes
   - Check Firestore collection for partial documents
   - Solution: Check agent logs for errors, verify all parameters passed

3. **Session Management Issues**
   - ADK sessions may expire or fail to create
   - Fallback to manual session IDs implemented
   - Solution: Check session service initialization logs

## Testing Considerations

### Manual Testing
1. Create account through UI and verify 5 documents generated
2. Use chat interface to trigger strategy generation manually
3. Verify document content in Firestore console

### Integration Points
- Neo4j for account metadata
- Firestore for document storage
- GCS for uploaded business documents
- Vertex AI Agent Engine for AI processing

## How to Modify

### To change agent behavior:
1. Edit instruction templates in `app/adk/agents/strategy_agent/agents.py`
2. Modify best practices in Firestore `strategy_doc_guides` collection
3. Update reviewer guidelines in Firestore

### To add new strategy types:
1. Create new agent function in `app/adk/agents/strategy_agent/agents.py`
2. Add to sequential pipeline in `app/adk/agents/strategy_agent/orchestrator.py`
3. Update `StrategyContext` in `app/adk/agents/strategy_agent/models.py`
4. Add new output_key to state management
5. Update DOCUMENT_KEY_MAPPING in orchestrator.py

### To change data flow:
1. Update agent instructions to reference new state variables
2. Modify output_key assignments in agent definitions
3. Adjust DOCUMENT_KEY_MAPPING in orchestrator.py

## Recent Improvements

### Improvements Made:
1. **Renamed** `agent_standalone.py` → `create_strategy_docs.py` for clarity
2. **Integrated** orchestrator.py for proper sequential execution
3. **Fixed** agent execution using Runner class instead of manual invocation
4. **Optimized** model usage (Pro for strategists, Flash for support)
5. **Enhanced** instructions with mandatory citations and research
6. **Added** cascading document review between agents
7. **Implemented** immediate Firestore saving after each agent
8. **Fixed** W&B observability integration

## Advanced Analytics System

### Overview
The ADK agents now include comprehensive analytics capabilities for tracking costs, performance, and optimization opportunities. The system uses a dual-database architecture to separate high-volume analytics data from operational data.

### Analytics Architecture

#### Database Separation
- **'analytics' Database**: High-volume time-series data
  - `agent_analytics_{account_id}`: Raw execution metrics
  - `cost_aggregations_{account_id}`: Daily/monthly cost rollups
  - `performance_profiles_{account_id}`: Performance traces
  
- **'(default)' Database**: Configuration and recommendations
  - `alert_configurations`: Per-account alert settings
  - `optimization_recommendations`: Improvement suggestions

#### Analytics Components

1. **AnalyticsService** (`analytics_service.py`)
   - Tracks token usage and costs per agent execution
   - Aggregates daily/monthly costs
   - Manages retention policies (90 days raw, 2 years aggregated)

2. **PerformanceProfiler** (`performance_profiler.py`)
   - Profiles execution times per agent
   - Identifies bottlenecks
   - Tracks operation dependencies

3. **AlertManager** (`alert_manager.py`)
   - Monitors token usage against thresholds (50%, 75%, 90%, 95%)
   - Sends notifications via email, webhook, and Firestore
   - Implements circuit breaker pattern at 100% usage

4. **OptimizationAnalyzer** (`optimization_analyzer.py`)
   - Analyzes usage patterns
   - Generates cost-saving recommendations
   - Suggests model downgrades and context optimizations

### Analytics Integration Guide for New Agents

#### Required Imports
```python
from strategy_agent.analytics_service import AnalyticsService
from strategy_agent.performance_profiler import PerformanceProfiler
from strategy_agent.alert_manager import AlertManager
from strategy_agent.token_utils import check_and_log_tokens, TokenEstimator
```

#### Agent Implementation Template
```python
def new_agent_function(context, state):
    # Initialize analytics (if not passed from orchestrator)
    analytics = AnalyticsService(context.account_id)
    profiler = PerformanceProfiler(context.account_id)
    alerts = AlertManager(context.account_id)
    
    # Start performance tracking
    operation = profiler.start_operation(
        agent_name="new_agent",
        operation="task_execution"
    )
    
    # Check input tokens before processing
    input_tokens = TokenEstimator.estimate_tokens(state)
    alerts.check_token_usage(
        current_tokens=input_tokens,
        max_tokens=TokenEstimator.MAX_INPUT_TOKENS,
        context="agent_input",
        agent_name="new_agent"
    )
    
    try:
        # Execute agent logic
        result = perform_agent_task(state)
        
        # Track execution metrics
        if hasattr(result, "usage_metadata"):
            usage = result.usage_metadata
            analytics.track_agent_execution(
                agent_name="new_agent",
                prompt_tokens=usage.prompt_token_count or 0,
                response_tokens=usage.candidates_token_count or 0,
                model="gemini-2.5-flash",  # or "gemini-2.5-pro"
                execution_time=time.time() - operation.start_time,
                success=True
            )
        
        # Complete performance tracking
        profiler.end_operation(operation, success=True)
        
        return result
        
    except Exception as e:
        # Track failure
        profiler.end_operation(operation, success=False, error=str(e))
        analytics.track_agent_execution(
            agent_name="new_agent",
            prompt_tokens=0,
            response_tokens=0,
            model="gemini-2.5-flash",
            execution_time=time.time() - operation.start_time,
            success=False,
            error_message=str(e)
        )
        raise
```

### Configuration

#### Environment Variables
```bash
# Google Cloud project
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev
```

#### Alert Configuration
Alert thresholds are stored per account in Firestore. Default configuration:
- 50% usage: INFO level (logging only)
- 75% usage: WARNING level (logging + Firestore)
- 90% usage: ERROR level (logging + Firestore + webhook)
- 95% usage: CRITICAL level (all channels: logging + Firestore + webhook + email)
- 100% usage: Circuit breaker triggers, halting operations

#### Notification Channels Configuration
Configure notification channels in the `alert_configurations` collection:
```json
{
  "notification_channels": {
    "email": {
      "enabled": false,
      "recipients": ["admin@example.com", "ops@example.com"]
    },
    "webhook": {
      "enabled": false,
      "url": "https://example.com/webhook/alerts",
      "headers": {
        "Authorization": "Bearer webhook_token"
      }
    }
  }
}
```

### Monitoring and Dashboards

#### Key Metrics to Track
1. **Cost Metrics**
   - Total cost per account per day
   - Cost by agent
   - Cost by model (Pro vs Flash)

2. **Performance Metrics**
   - Average execution time per agent
   - Bottleneck identification
   - Error rates

3. **Token Usage**
   - Context utilization percentage
   - Token distribution across agents
   - Peak usage times

#### Accessing Analytics Data

```python
# Get execution summary
analytics = AnalyticsService(account_id)
summary = analytics.get_execution_summary()
print(f"Total cost: ${summary['total_cost']:.4f}")
print(f"Total tokens: {summary['total_tokens']:,}")

# Get cost trends
trends = analytics.get_cost_trends(days=30)
for day in trends:
    print(f"{day['date']}: ${day['total_cost']:.2f}")

# Get performance bottlenecks
profiler = PerformanceProfiler(account_id)
bottlenecks = profiler.get_bottlenecks(time_window_hours=24)
for bottleneck in bottlenecks:
    print(f"{bottleneck['agent_name']}: {bottleneck['duration']}s")

# Get optimization recommendations
analyzer = OptimizationAnalyzer(account_id)
recommendations = analyzer.generate_recommendations()
for rec in recommendations:
    print(f"• {rec.description} (Savings: {rec.estimated_savings_percentage}%)")
```

### Best Practices

1. **Model Selection**
   - Use `gemini-2.5-flash` for reviewers and editors
   - Use `gemini-2.5-pro` only for complex strategist agents
   - Monitor average token usage to identify downgrade opportunities

2. **Context Management**
   - Keep context utilization between 20-80%
   - Implement document chunking for large inputs
   - Remove redundant information between agents

3. **Performance Optimization**
   - Identify and optimize agents with >10s execution time
   - Consider parallel execution where dependencies allow
   - Cache frequently accessed data

4. **Cost Optimization**
   - Review daily cost aggregations
   - Implement recommendations with >20% savings potential
   - Monitor error rates to avoid wasted tokens

### Troubleshooting

#### Common Issues

1. **"Circuit breaker open" errors**
   - Check token usage in recent executions
   - Review context size being passed to agents
   - Consider chunking or summarization

2. **Missing analytics data**
   - Verify 'analytics' database exists in Firestore
   - Check service account permissions
   - Review logs for connection errors

3. **Notifications not received**
   - Check alert configuration in Firestore
   - Verify email/webhook settings in notification_channels
   - Confirm notification channels are enabled
   - Check logs for webhook/email delivery errors

#### Debug Commands

```bash
# Check analytics database collections
gcloud firestore databases list

# View recent alerts
gcloud firestore documents read alert_configurations/[ACCOUNT_ID]/alerts

# Check cost aggregations
gcloud firestore documents list analytics/cost_aggregations_[ACCOUNT_ID]
```

## Pydantic Validation and Error Handling

### Overview

The ADK agents use Pydantic for structured output validation. Following an incident where the customer_strategist agent failed validation after 6 minutes of execution, the system was updated to use ADK's built-in validation and retry mechanisms to prevent future failures.

### Current Implementation

All strategy agents now use ADK's built-in `output_schema` parameter for automatic validation and retry:

```python
def create_business_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the business strategy strategist agent."""
    # ...
    agent = Agent(
        model="gemini-2.5-pro",
        instructions=instructions,
        tools=[google_search_agent],
        output_key="business_strategy_doc",
        output_schema=BusinessStrategy  # ADK handles validation automatically
    )
    # ADK handles output validation internally via output_schema parameter
    return agent
```

### How ADK Handles Validation

When an `output_schema` is provided, ADK automatically:
1. **Validates** agent responses against the Pydantic schema
2. **Retries** on validation errors with clearer instructions
3. **Extracts** JSON from markdown code blocks or mixed text
4. **Provides** error feedback to the agent on retry attempts

### Common Agent Response Issues

Agents may return invalid responses in these scenarios:
- **Plain text responses**: Agent returns narrative text instead of JSON
- **Markdown-wrapped JSON**: JSON embedded in markdown code blocks  
- **Schema mismatches**: Missing required fields or incorrect data types
- **Token limit issues**: Truncated responses due to max_output_tokens

ADK's built-in validation handles these cases automatically.

### Validation Best Practices

#### 1. Schema Design

Create robust Pydantic schemas with clear field descriptions:

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class BusinessStrategy(BaseModel):
    """Structured output for business strategy document."""
    businessStrategySummary: str = Field(
        ...,
        description="A high-level summary of the company's situation..."
    )
    companyOverview: str = Field(
        ...,
        description="A comprehensive narrative that introduces..."
    )
    # Additional fields with detailed descriptions
```

#### 2. Instruction Engineering

While ADK handles validation, strengthen agent instructions for better first-attempt success:
- Include "Output must be valid JSON" in instructions
- Provide example of expected structure
- Reference field descriptions from the schema

#### 3. Token Management

Prevent truncation issues:
- Monitor token usage in agent responses  
- Set appropriate max_output_tokens
- Keep context utilization between 20-80%
- Consider chunking large outputs if needed

### Testing Validation

#### Unit Tests

```python
def test_agent_output_validation(agent, test_input):
    """Test that agent produces valid schema output."""
    result = agent.invoke(test_input)
    try:
        # ADK should have already validated, but we can double-check
        validated = BusinessStrategy.model_validate(result['business_strategy_doc'])
        return True
    except ValidationError as e:
        logger.error(f"Unexpected validation failure: {e}")
        return False
```

#### Integration Tests

Test complete agent flow with:
- Various input types and edge cases
- Empty data and special characters
- Token limit scenarios
- Long-running operations

### Monitoring and Debugging

#### Validation Metrics to Track

- Validation error rates per agent
- Retry success rates (when ADK retries)
- Token usage patterns
- Response truncation incidents

#### Common Issues and Solutions

**"Pydantic ValidationError" in logs**
- **Cause**: Agent output doesn't match schema despite ADK retry
- **Solutions**:
  - Review agent instructions for clarity
  - Check if schema requirements are too complex
  - Verify token limits aren't causing truncation
  - Monitor for patterns in failed validations

**Truncated JSON responses**
- **Cause**: Output exceeds max_output_tokens
- **Solutions**:
  - Increase max_output_tokens if possible
  - Simplify output requirements
  - Split complex outputs into multiple agents

### Historical Context

The PYDANTIC_VALIDATION_RECOMMENDATIONS.md file references a custom retry wrapper approach that was initially considered but ultimately replaced by ADK's built-in functionality. The current implementation relies entirely on ADK's native `output_schema` parameter for validation and retry logic.

### Key Takeaways

1. **ADK handles validation**: No custom retry wrappers needed with `output_schema`
2. **Consistency is critical**: All agents with structured output use `output_schema`
3. **Defense in depth**: ADK provides automatic retry and JSON extraction
4. **Monitor patterns**: Track validation failures to improve instructions
5. **Test thoroughly**: Validate edge cases and token limit scenarios

## Future Enhancements

Potential improvements identified in the codebase:
1. Progress tracking granularity (currently simplified)
2. Enhanced validation error reporting and analytics
3. Document versioning and update tracking
4. Real-time progress updates to frontend
5. Automated cost optimization implementation
6. Machine learning-based usage prediction
7. A/B testing for instruction optimization to reduce validation errors
8. Automated schema evolution based on validation patterns