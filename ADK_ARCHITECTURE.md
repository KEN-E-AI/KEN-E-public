# ADK (Agent Development Kit) Architecture

## Overview

KEN-E uses Google's Agent Development Kit (ADK) deployed to Vertex AI Agent Engine for its conversational AI capabilities. The system provides a clean, single-agent architecture that integrates directly with the frontend through a REST API.

## Architecture Components

### 1. **ADK Agent Engine**
- **Platform**: Google Vertex AI Agent Engine
- **Agent ID**: Configured via `VERTEX_AI_AGENT_ENGINE_ID` environment variable
- **Location**: `us-central1`
- **Session Management**: ADK Session Service for conversation persistence

### 2. **API Integration Layer**
- **File**: `api/src/kene_api/routers/chat.py`
- **Class**: `AgentEngineClient`
- **Endpoints**:
  - `POST /api/v1/chat/completions` - Send messages to agent
  - `GET /api/v1/chat/health` - Health check
  - `POST /api/v1/chat/conversations` - Create new conversation
  - `GET /api/v1/chat/conversations` - List conversations
  - `PUT /api/v1/chat/conversations/{session_id}` - Update conversation
  - `GET /api/v1/chat/conversations/{session_id}/history` - Get conversation history
  - `DELETE /api/v1/chat/conversations/{session_id}` - Delete conversation

### 3. **Frontend Integration**
- **Service**: `frontend/src/services/chatService.ts`
- **Components**:
  - `HomeChatArea.tsx` - Main chat interface
  - `ChatSidebar.tsx` - Dashboard chat sidebar
- **Features**:
  - Real-time chat with ADK agent
  - Conversation persistence and history
  - Session management
  - Streaming support (infrastructure ready)

## Data Flow

```
User Input → Frontend Component → ChatService → API Router → AgentEngineClient → ADK Agent Engine
                ↓                                                                        ↓
            UI Update ← ChatService ← API Router ← AgentEngineClient ← ADK Response
                                                                            ↓
                                                                    Session Storage
```

## Key Features

### Session Persistence
- Conversations automatically saved to ADK Session Service
- Cross-session conversation history
- User-scoped session management with `app_name="ken-e-chatbot"`

### Response Handling
- Parses ADK's nested response structure: `{content: {parts: [{text: '...'}]}}`
- Handles both streaming and non-streaming modes
- Graceful error handling and fallbacks

### Authentication
- Firebase Auth integration for user authentication
- Automatic token injection in API requests
- Cross-project authentication support

## Environment Configuration

### Required Environment Variables

```bash
# API Service
VERTEX_AI_AGENT_ENGINE_ID=projects/{project}/locations/{location}/reasoningEngines/{id}
VERTEX_AI_LOCATION=us-central1
GOOGLE_CLOUD_PROJECT_ID={project-id}

# Frontend
VITE_API_BASE_URL=http://localhost:8000  # Or production URL
VITE_FIREBASE_*  # Firebase configuration
```

### Deployment Configuration

The ADK Agent Engine ID is configured in the deployment pipelines:

- **Staging**: `projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232`
- **Production**: Configure in Cloud Build trigger variables

## Development Workflow

1. **Local Development**:
   - Start API: `cd api && uv run --active -- uvicorn src.kene_api.main:app --reload`
   - Start Frontend: `cd frontend && npm run dev:development`

2. **Testing**:
   - Test ADK integration: `cd api && python scripts/test_agent_chat.py`
   - Test frontend integration: Access http://localhost:8080

3. **Deployment**:
   - Staging: Automatic on merge to main
   - Production: Manual trigger with approval

## Benefits of ADK-Only Architecture

1. **Simplicity**: Single agent implementation without complex orchestration
2. **Reliability**: Direct integration with Google's managed ADK service
3. **Scalability**: Leverages Vertex AI's infrastructure
4. **Maintainability**: Clear separation between frontend, API, and agent
5. **Session Management**: Built-in conversation persistence via ADK

## Testing Scripts

- `api/scripts/test_agent_chat.py` - Test ADK integration
- `api/scripts/test_reasoning_engine_methods.py` - Debug ADK API methods
- `api/scripts/test_conversation_persistence.py` - Test session persistence

## Migration from CrewAI

This architecture replaces the previous CrewAI + LangGraph implementation with a cleaner, ADK-only approach. The frontend was already using ADK through the API, so no frontend changes were required during the migration.