# Agent Development Kit (ADK) Usage Documentation

## Overview

The Agent Development Kit (ADK) is used in the KEN-E application to power AI-driven features through Google's Vertex AI Agent Engine. This document explains how ADK is integrated into two key processes:

1. **Account Creation**: Automatic generation of strategy documents when a new account is created
2. **Chat Interface**: User-initiated conversations with the AI assistant

## Architecture Overview

The ADK implementation uses a multi-agent supervisor pattern:

```
create_strategy_docs_supervisor (Main Router)
├── Company News Agent
├── Google Analytics Agent
└── Strategy Agent (5 document generator)
```

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

### Session Management
- ADK sessions are managed through `VertexAiSessionService`
- Sessions track conversation history and user context
- Session IDs follow format: `chat_{timestamp}_{random}` or ADK-generated IDs

### Error Handling
- Timeout handling: 600 seconds (10 minutes) for complex requests
- Fallback session creation if ADK service fails
- Document verification with retry logic

### Document Storage
- Strategy documents stored in Firestore collections: `strategy_docs_{account_id}`
- Each document contains structured content with metadata
- Status tracking for document generation progress

### Authentication Flow
- Frontend: Firebase Auth token attached to requests
- API: Token validation and user context extraction
- Agent Engine: User context passed with queries

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

## Future Enhancements

Potential improvements identified in the codebase:
1. Progress tracking granularity (currently simplified)
2. Retry mechanism for failed document generation
3. Document versioning and update tracking
4. Real-time progress updates to frontend