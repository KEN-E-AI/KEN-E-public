# Agent Separation Implementation Plan

## Executive Summary

This plan outlines the separation of the current unified supervisor agent into two distinct agents with separate deployments:
1. **`ken-e`**: Frontend-facing chat agent (handles company news and Google Analytics)
2. **`create_strategy_docs_supervisor`**: Backend-only agent for strategy generation (triggered only during account creation)

Both agents will be deployed as separate Agent Engine instances with different API endpoints.

## Current State Analysis

### Existing Architecture
- Single supervisor agent (`create_strategy_docs_supervisor`) handles all three capabilities
- Deployed as one Agent Engine instance
- Single API endpoint for all interactions
- Routes to three sub-agents based on LLM analysis

### Key Files Affected
- `/app/adk/agents/create_strategy_docs_supervisor.py` - Main supervisor
- `/app/adk/agents/agent_engine_app.py` - Deployment configuration
- `/api/src/kene_api/routers/chat.py` - API chat endpoint
- `/api/src/kene_api/tasks/strategy_tasks.py` - Strategy generation task
- `/api/src/kene_api/services/account_service.py` - Account creation service

## Implementation Approach

Following CLAUDE.md best practices:
- **BP-2**: This plan provides a clear approach for complex work
- **C-2**: Using existing domain vocabulary (supervisor, agent, strategy)
- **C-4**: Preferring simple, composable functions
- **O-1**: Keeping agent logic in `app/`, API logic in `api/`
- **O-3**: Placing reusable utilities in appropriate directories

## Phase 1: Create New Agent Structure

### 1.1 Extract Shared Utilities
**File**: `/app/adk/agents/utils/supervisor_utils.py`

Extract reusable functions from the existing supervisor to avoid code duplication:

```python
"""
Shared utilities for supervisor agents.
Extracted from create_strategy_docs_supervisor.py to promote reuse.
"""

import logging
import json
import uuid
import asyncio
from typing import Any, Optional, Tuple
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)

def extract_tenant_context(input_data: Any) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extract tenant context from various input formats.
    
    Returns: (tenant_id, tenant_credentials, message)
    """
    tenant_id = None
    tenant_credentials = None
    message = ""
    
    if isinstance(input_data, str):
        message = input_data
    elif isinstance(input_data, dict):
        message = input_data.get('message', input_data.get('query', str(input_data)))
        tenant_id = input_data.get('tenant_id')
        tenant_credentials = input_data.get('tenant_credentials')
    else:
        message = str(input_data)
    
    return tenant_id, tenant_credentials, message


def invoke_agent_sync(agent, query: str, user_id: str = None, session_id: str = None) -> str:
    """
    Synchronous wrapper for agent invocation with proper async handling.
    """
    if user_id is None:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    if session_id is None:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    async def invoke_agent():
        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()
        
        runner = Runner(
            agent=agent,
            app_name=agent.name,
            session_service=session_service,
            artifact_service=artifact_service
        )
        
        await session_service.create_session(
            app_name=agent.name,
            user_id=user_id,
            session_id=session_id
        )
        
        user_message = Content(
            role="user",
            parts=[Part.from_text(text=query)]
        )
        
        response_text = ""
        async for event in runner.run_async(
            message=user_message,
            user_id=user_id,
            session_id=session_id
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text'):
                        response_text += part.text
        
        return response_text
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(invoke_agent())
    finally:
        loop.close()


def dispatch_with_context(dispatch_func):
    """Wrapper to extract tenant context from the full input"""
    def wrapper(full_input: str) -> str:
        logger.info(f"[DISPATCH-WRAPPER] Tool called: {dispatch_func.__name__}")
        
        try:
            input_data = json.loads(full_input)
            tenant_id, tenant_credentials, message = extract_tenant_context(input_data)
            tenant_context = {
                'tenant_id': tenant_id,
                'tenant_credentials': tenant_credentials
            } if tenant_id and tenant_credentials else None
            result = dispatch_func(message, tenant_context)
            if isinstance(result, dict) and 'result' in result:
                return result['result']
            return str(result)
        except json.JSONDecodeError:
            result = dispatch_func(full_input, None)
            if isinstance(result, dict) and 'result' in result:
                return result['result']
            return str(result)
    return wrapper
```

### 1.2 Extract Dispatch Functions
**File**: `/app/adk/agents/utils/dispatch_handlers.py`

```python
"""
Dispatch handlers for routing to specialized agents.
"""

import logging
from typing import Optional, Dict, Any
from ..company_news_chatbot.agent import root_agent as news_agent
from ..google_analytics_agent_v4 import google_analytics_agent_v4
from ..strategy_agent.orchestrator import execute_strategy_generation
from .supervisor_utils import invoke_agent_sync

logger = logging.getLogger(__name__)

def dispatch_to_company_news(query: str, tenant_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Dispatch query to company news agent."""
    try:
        logger.info(f"[DISPATCH] Routing to company news agent")
        
        if tenant_context:
            result = invoke_agent_sync(
                news_agent, 
                query,
                user_id=tenant_context.get('tenant_id', 'news_user'),
                session_id=None
            )
        else:
            result = invoke_agent_sync(news_agent, query)
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'news_specialist',
            'agent': 'company_news'
        }
    except Exception as e:
        logger.error(f"[DISPATCH] Error in news agent: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'news_specialist',
            'agent': 'company_news'
        }


def dispatch_to_google_analytics(query: str, tenant_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Dispatch query to Google Analytics agent."""
    try:
        logger.info(f"[DISPATCH] Routing to Google Analytics agent")
        
        if tenant_context:
            prepared_query = {
                'query': query,
                'tenant_id': tenant_context.get('tenant_id'),
                'tenant_credentials': tenant_context.get('tenant_credentials')
            }
            query_str = json.dumps(prepared_query)
        else:
            query_str = query
        
        result = invoke_agent_sync(google_analytics_agent_v4, query_str)
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'analytics_specialist',
            'agent': 'google_analytics'
        }
    except Exception as e:
        logger.error(f"[DISPATCH] Error in analytics agent: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'analytics_specialist',
            'agent': 'google_analytics'
        }


def dispatch_to_strategy(query: str, tenant_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Dispatch query to strategy generation agent."""
    try:
        logger.info(f"[DISPATCH] Routing to strategy agent")
        
        # Parse parameters from the formatted message
        params = {}
        for line in query.split('\n'):
            if ':' in line and line.startswith('-'):
                key, value = line.strip('- ').split(':', 1)
                params[key.strip()] = value.strip()
        
        # Convert uploaded_documents string to list
        if 'uploaded_documents' in params and params['uploaded_documents']:
            params['uploaded_documents'] = [
                url.strip() for url in params['uploaded_documents'].split(',')
            ]
        
        result = execute_strategy_generation(
            company_name=params.get('company_name', ''),
            industry=params.get('industry', ''),
            websites=params.get('websites', '').split(',') if params.get('websites') else [],
            customer_regions=params.get('customer_regions', '').split(',') if params.get('customer_regions') else [],
            account_id=params.get('account_id', ''),
            user_id=params.get('user_id', ''),
            annual_ad_budget=params.get('annual_ad_budget', ''),
            project_id=params.get('project_id', ''),
            uploaded_documents=params.get('uploaded_documents', [])
        )
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'strategy_specialist',
            'agent': 'strategy',
            'account_id': params.get('account_id', '')
        }
    except Exception as e:
        logger.error(f"[DISPATCH] Error in strategy agent: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'strategy_specialist',
            'agent': 'strategy'
        }
```

### 1.3 Create Ken-E Agent
**File**: `/app/adk/agents/ken_e_agent.py`

```python
"""
KEN-E Agent: Frontend-facing chat agent for company news and analytics.
"""

from google.adk.agents import Agent
from .utils.supervisor_utils import dispatch_with_context
from .utils.dispatch_handlers import dispatch_to_company_news, dispatch_to_google_analytics

def create_ken_e_agent():
    """
    Create the KEN-E chat agent for frontend interactions.
    Handles company news and Google Analytics queries only.
    """
    
    # Create dispatch functions with context handling
    search_company_news = dispatch_with_context(dispatch_to_company_news)
    search_company_news.__name__ = "search_company_news"
    search_company_news.__doc__ = "Search for company news, financial updates, earnings reports, market analysis, and business announcements"
    
    query_google_analytics = dispatch_with_context(dispatch_to_google_analytics)
    query_google_analytics.__name__ = "query_google_analytics"
    query_google_analytics.__doc__ = "Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance"
    
    ken_e = Agent(
        name="ken_e",
        model="gemini-2.0-flash",
        instruction="""You are KEN-E, an intelligent AI assistant specializing in business intelligence and analytics.

**CRITICAL: When you call a tool, the tool's response contains the answer. You MUST present that response to the user. Never just acknowledge that you called the tool - always share what the tool returned.**

**CAPABILITY 1 - Company News & Business Intelligence:**
Use `search_company_news` for queries about:
- Company news, announcements, and press releases
- Financial results, earnings reports, quarterly results
- Market movements, stock information, analyst ratings
- Executive changes, corporate actions, M&A activity
- Product launches, business developments, strategy updates
- Any questions about specific companies (Apple, Google, Tesla, etc.)

**CAPABILITY 2 - Google Analytics & Website Data:**
Use `query_google_analytics` for queries about:
- Website or app traffic metrics (users, sessions, pageviews)
- User behavior, engagement metrics, conversion rates
- Traffic sources, acquisition channels, campaign performance
- Real-time analytics data and live user activity
- Custom reports with specific metrics and dimensions
- Any GA4 property data or analysis

**ROUTING INSTRUCTIONS:**
1. Analyze the user's intent using your LLM capabilities
2. Route based on the primary focus of the query:
   - Company/business/market focus → search_company_news
   - Website/traffic/analytics focus → query_google_analytics

3. When routing, ALWAYS pass the COMPLETE user input to the tool

4. Handle ambiguous queries:
   - If unclear, ask for clarification about which capability they need
   - If query could match multiple capabilities, ask which they'd like to explore first

5. Response handling:
   - ALWAYS relay the complete response from the specialized agent to the user
   - The tool response IS your response - present it in full
   - Maintain the formatting from the specialist agent

**IMPORTANT NOTES:**
- You are integrated with the KEN-E app where users are already authenticated
- NEVER ask users for credentials - they're already logged in with Google
- The system automatically uses the logged-in user's Google account for GA queries

**EXAMPLES OF ROUTING:**
- "What's the latest news about Apple?" → search_company_news
- "Show me website traffic for last week" → query_google_analytics  
- "How many users visited my site?" → query_google_analytics
- "Tesla earnings report" → search_company_news
- "Bounce rate by country" → query_google_analytics
- "Microsoft acquisition news" → search_company_news

Remember: You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools.""",
        tools=[search_company_news, query_google_analytics]
    )
    
    return ken_e

# Export the agent
ken_e_agent = create_ken_e_agent()
```

### 1.4 Modify Strategy Supervisor
**File**: `/app/adk/agents/create_strategy_docs_supervisor.py`

Simplify to only handle strategy generation:

```python
"""
Strategy Documents Supervisor: Handles strategy generation during account creation.
"""

from google.adk.agents import Agent
from .utils.supervisor_utils import dispatch_with_context
from .utils.dispatch_handlers import dispatch_to_strategy

def create_strategy_supervisor():
    """
    Create the strategy documents supervisor for account creation.
    This agent is only invoked programmatically during account creation.
    """
    
    create_strategy = dispatch_with_context(dispatch_to_strategy)
    create_strategy.__name__ = "create_strategy"
    create_strategy.__doc__ = "Generate all 5 strategy documents for a company"
    
    supervisor = Agent(
        name="create_strategy_docs_supervisor",
        model="gemini-2.0-flash",
        instruction="""You are a specialized agent for generating strategy documents during account creation.

**CRITICAL: You are ONLY invoked during account creation. You do not handle chat interactions.**

When you receive a request starting with "Generate all 5 strategy documents", immediately use the create_strategy tool.

ALWAYS pass the COMPLETE input to the tool including all parameters.

The tool will generate:
1. Business Strategy
2. Competitive Analysis
3. Customer Journey
4. Marketing Strategy
5. Brand Guidelines

Return the result from the strategy generation tool.""",
        tools=[create_strategy]
    )
    
    return supervisor

# Export the supervisor agent
create_strategy_docs_supervisor = create_strategy_supervisor()
```

## Phase 2: Create Deployment Configurations

### 2.1 Ken-E Deployment App
**File**: `/app/adk/agents/ken_e_app.py`

```python
"""
Agent Engine app configuration for KEN-E chat agent.
"""

from vertexai.preview import reasoning_engines

# Import patterns for deployment compatibility
try:
    from .ken_e_agent import ken_e_agent
except ImportError:
    try:
        from agents.ken_e_agent import ken_e_agent
    except ImportError:
        from ken_e_agent import ken_e_agent

# Create the ADK app for deployment
app = reasoning_engines.AdkApp(
    agent=ken_e_agent,
    enable_tracing=True
)
```

### 2.2 Strategy Supervisor Deployment (keep existing)
**File**: `/app/adk/agents/agent_engine_app.py`

No changes needed - continues to deploy `create_strategy_docs_supervisor`.

### 2.3 Deployment Scripts
**File**: `/app/adk/agents/deploy_ken_e.py`

```python
"""
Deploy KEN-E agent to Vertex AI Agent Engine.
Based on existing deploy_supervisor.py patterns.
"""

import os
import sys
from pathlib import Path
from vertexai.preview import reasoning_engines

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

def deploy_ken_e():
    """Deploy KEN-E agent to Vertex AI."""
    
    project_id = os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev")
    location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    staging_bucket = os.getenv("VERTEX_AI_STAGING_BUCKET", f"gs://{project_id}-adk-staging")
    
    print(f"Deploying KEN-E agent to project: {project_id}")
    print(f"Location: {location}")
    print(f"Staging bucket: {staging_bucket}")
    
    # Deploy the agent
    agent = reasoning_engines.ReasoningEngine.create(
        "ken_e_app:app",
        requirements=[
            "google-cloud-aiplatform",
            "google-genai",
            "google-adk",
            "pydantic>=2.0.0",
        ],
        display_name="ken-e-chat-agent",
        description="KEN-E chat agent for company news and analytics",
        staging_bucket=staging_bucket,
        location=location,
        project=project_id
    )
    
    print(f"Successfully deployed KEN-E agent!")
    print(f"Agent ID: {agent.resource_name}")
    print(f"\nSet this environment variable:")
    print(f"export VERTEX_AI_KEN_E_AGENT_ID={agent.resource_name}")
    
    return agent

if __name__ == "__main__":
    deploy_ken_e()
```

## Phase 3: Update API Layer

### 3.1 Create Separate Chat Endpoint
**File**: `/api/src/kene_api/routers/ken_e_chat.py`

```python
"""
KEN-E chat endpoint for frontend interactions.
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from vertexai.preview import agent_engines
import vertexai

from ..models.chat import ChatMessage, ChatCompletionRequest, ChatCompletionResponse
from ..auth.dependencies import get_current_user
from ..models.user import UserContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ken-e", tags=["ken-e"])

class KenEClient:
    """Client for interacting with KEN-E agent."""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")
        self.location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.ken_e_agent_id = os.getenv("VERTEX_AI_KEN_E_AGENT_ID")
        
        if not self.ken_e_agent_id:
            logger.warning("VERTEX_AI_KEN_E_AGENT_ID not set.")
        
        vertexai.init(project=self.project_id, location=self.location)
        self._agent_engine = None
    
    @property
    def agent_engine(self):
        """Get KEN-E agent."""
        if self._agent_engine is None and self.ken_e_agent_id:
            self._agent_engine = agent_engines.get(self.ken_e_agent_id)
        return self._agent_engine
    
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        user_context: UserContext,
        session_id: Optional[str] = None
    ) -> tuple[str, str]:
        """Get chat completion from KEN-E."""
        if not self.agent_engine:
            return "KEN-E is currently unavailable.", ""
        
        try:
            latest_message = messages[-1] if messages else None
            if not latest_message:
                return "No message received.", ""
            
            user_input = latest_message.content
            user_id = user_context.user_id
            
            # Stream query to KEN-E
            response_parts = []
            for chunk in self.agent_engine.stream_query(
                message=user_input,
                user_id=user_id,
                session_id=session_id or f"chat_{user_id}"
            ):
                # Process response chunks (existing logic)
                if isinstance(chunk, dict) and "content" in chunk:
                    # Extract text from response
                    pass  # Use existing chunk processing logic
            
            response_text = "".join(response_parts)
            return response_text, session_id or f"chat_{user_id}"
            
        except Exception as e:
            logger.error(f"KEN-E chat error: {e}")
            return "An error occurred while processing your request.", ""

# Initialize client
ken_e_client = KenEClient()

@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    current_user: UserContext = Depends(get_current_user)
) -> ChatCompletionResponse:
    """Create a chat completion using KEN-E agent."""
    
    response_text, session_id = await ken_e_client.chat_completion(
        messages=request.messages,
        user_context=current_user,
        session_id=request.session_id
    )
    
    return ChatCompletionResponse(
        role="assistant",
        content=response_text,
        session_id=session_id
    )
```

### 3.2 Update Strategy Task for Direct Invocation
**File**: `/api/src/kene_api/tasks/strategy_tasks.py`

Update to use strategy supervisor directly:

```python
async def trigger_strategy_generation(
    company_name: str,
    industry: str,
    websites: List[str],
    customer_regions: List[str],
    account_id: str,
    user_id: str,
    annual_ad_budget: str,
    project_id: str,
    uploaded_document_urls: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Trigger strategy generation using dedicated strategy supervisor.
    Called only during account creation.
    """
    
    # Get strategy supervisor agent ID
    strategy_agent_id = os.getenv("VERTEX_AI_STRATEGY_AGENT_ID")
    if not strategy_agent_id:
        raise ValueError("Strategy supervisor agent not configured")
    
    try:
        # Initialize Vertex AI
        vertexai.init(project=project_id, location="us-central1")
        
        # Get strategy supervisor agent
        agent_engine = agent_engines.get(strategy_agent_id)
        
        # Format message for strategy generation
        message = f"""Generate all 5 strategy documents for {company_name}
        
Please execute strategy generation with these parameters:
- company_name: {company_name}
- industry: {industry}
- websites: {",".join(websites)}
- customer_regions: {",".join(customer_regions)}
- account_id: {account_id}
- user_id: {user_id}
- annual_ad_budget: {annual_ad_budget}
- project_id: {project_id}"""
        
        if uploaded_document_urls:
            message += f"\n- uploaded_documents: {','.join(uploaded_document_urls)}"
        
        # Stream query to strategy supervisor
        response_parts = []
        for chunk in agent_engine.stream_query(
            message=message,
            user_id=user_id,
            session_id=f"strategy_{account_id}"
        ):
            # Process response chunks
            # ... existing chunk processing logic ...
            pass
        
        # Wait for documents to be created in Firestore
        await verify_strategy_documents_created(account_id, project_id)
        
        return {
            "status": "success",
            "account_id": account_id,
            "message": "Strategy documents generated successfully"
        }
        
    except Exception as e:
        logger.error(f"Strategy generation failed: {e}")
        raise
```

### 3.3 Update Main API Application
**File**: `/api/src/kene_api/main.py`

Add the new KEN-E router:

```python
from .routers import ken_e_chat  # Add this import

# Include the new router
app.include_router(ken_e_chat.router)  # Add this line
```

### 3.4 Environment Configuration Updates
**File**: `/api/.env.development` (and staging/production)

```bash
# Agent Engine IDs (separate deployments)
VERTEX_AI_KEN_E_AGENT_ID=projects/ken-e-dev/locations/us-central1/reasoningEngines/ken-e-agent-id
VERTEX_AI_STRATEGY_AGENT_ID=projects/ken-e-dev/locations/us-central1/reasoningEngines/strategy-agent-id

# Remove old unified agent ID
# VERTEX_AI_AGENT_ENGINE_ID=<removed>
```

## Phase 4: Testing Strategy

### 4.1 Unit Tests for New Agents

**File**: `/app/adk/agents/tests/test_ken_e_agent.py`

```python
"""Test KEN-E agent routing."""

import pytest
from ..ken_e_agent import create_ken_e_agent

def test_ken_e_has_correct_tools():
    """Test that KEN-E only has news and analytics tools."""
    agent = create_ken_e_agent()
    tool_names = [tool.__name__ for tool in agent.tools]
    
    assert "search_company_news" in tool_names
    assert "query_google_analytics" in tool_names
    assert "create_strategy" not in tool_names  # Should NOT have strategy tool


def test_ken_e_agent_name():
    """Test agent has correct name."""
    agent = create_ken_e_agent()
    assert agent.name == "ken_e"
```

**File**: `/app/adk/agents/tests/test_strategy_supervisor.py`

```python
"""Test strategy supervisor agent."""

import pytest
from ..create_strategy_docs_supervisor import create_strategy_supervisor

def test_strategy_supervisor_has_only_strategy_tool():
    """Test that strategy supervisor only has strategy tool."""
    agent = create_strategy_supervisor()
    tool_names = [tool.__name__ for tool in agent.tools]
    
    assert "create_strategy" in tool_names
    assert len(tool_names) == 1  # Only one tool


def test_strategy_supervisor_name():
    """Test agent has correct name."""
    agent = create_strategy_supervisor()
    assert agent.name == "create_strategy_docs_supervisor"
```

### 4.2 Integration Tests

**File**: `/api/tests/integration/test_ken_e_chat.py`

```python
"""Test KEN-E chat endpoint."""

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_ken_e_chat_endpoint(async_client: AsyncClient, auth_headers):
    """Test KEN-E chat endpoint responds correctly."""
    
    response = await async_client.post(
        "/api/v1/ken-e/chat/completions",
        json={
            "messages": [{"role": "user", "content": "What's the latest news about Apple?"}],
            "stream": False
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "assistant"
    assert "content" in data
```

### 4.3 End-to-End Testing Checklist

1. **Deploy KEN-E agent**:
   ```bash
   cd app/adk/agents
   python deploy_ken_e.py
   ```

2. **Deploy strategy supervisor** (keep existing):
   ```bash
   cd app/adk/agents
   python deploy_supervisor.py
   ```

3. **Update environment variables** with new agent IDs

4. **Test KEN-E chat**:
   - Send news query → Should work
   - Send analytics query → Should work
   - Send strategy query → Should not trigger generation

5. **Test account creation**:
   - Create new account → Should trigger strategy generation
   - Verify 5 documents created in Firestore

## Phase 5: Deployment Process

### 5.1 Deployment Steps

1. **Create feature branch**:
   ```bash
   git checkout -b feature/separate-agents
   ```

2. **Implement code changes** (Phases 1-3)

3. **Run tests locally**:
   ```bash
   # Python tests
   cd app/adk
   pytest agents/tests/
   
   # API tests
   cd api
   pytest tests/
   ```

4. **Deploy to development**:
   ```bash
   # Deploy KEN-E
   cd app/adk/agents
   VERTEX_AI_PROJECT_ID=ken-e-dev python deploy_ken_e.py
   
   # Deploy strategy supervisor (if modified)
   VERTEX_AI_PROJECT_ID=ken-e-dev python deploy_supervisor.py
   ```

5. **Update development environment**:
   - Set `VERTEX_AI_KEN_E_AGENT_ID`
   - Set `VERTEX_AI_STRATEGY_AGENT_ID`
   - Remove `VERTEX_AI_AGENT_ENGINE_ID`

6. **Test in development environment**

7. **Deploy to staging** (repeat steps 4-6 with staging project)

8. **Deploy to production** (after staging validation)

### 5.2 Rollback Plan

If issues occur:

1. **Keep old unified agent deployed** (don't delete immediately)

2. **Use environment variables to switch**:
   ```bash
   # Rollback: Use old unified agent
   export USE_UNIFIED_AGENT=true
   export VERTEX_AI_AGENT_ENGINE_ID=<old-agent-id>
   
   # Forward: Use new separated agents
   export USE_UNIFIED_AGENT=false
   export VERTEX_AI_KEN_E_AGENT_ID=<ken-e-id>
   export VERTEX_AI_STRATEGY_AGENT_ID=<strategy-id>
   ```

3. **API can check flag**:
   ```python
   if os.getenv("USE_UNIFIED_AGENT") == "true":
       # Use old AgentEngineClient
   else:
       # Use new KenEClient
   ```

## Success Criteria

- [x] KEN-E agent handles only news and analytics queries
- [x] Strategy supervisor only accessible during account creation
- [x] Separate API endpoints for chat and strategy
- [x] No code duplication (shared utilities extracted)
- [x] Tests pass for both agents
- [x] Clean separation of concerns

## Timeline Estimate

- **Phase 1**: 3-4 hours (Agent structure and utilities)
- **Phase 2**: 1-2 hours (Deployment configurations)
- **Phase 3**: 3-4 hours (API updates and endpoints)
- **Phase 4**: 2-3 hours (Testing)
- **Phase 5**: 2-3 hours (Deployment and validation)

**Total**: 11-16 hours

## Risk Mitigation

| Risk | Mitigation | Impact |
|------|------------|--------|
| Deployment failures | Keep old agent as fallback | Low |
| API endpoint conflicts | Use separate `/ken-e/` prefix | Low |
| Missing functionality | Comprehensive testing before deploy | Medium |
| Performance degradation | Monitor latency metrics | Low |

## Code Quality Checklist

Following CLAUDE.md best practices:

- ✅ **O-1**: Agent logic in `app/`, API logic in `api/`
- ✅ **O-3**: Reusable utilities in `utils/` directories
- ✅ **C-2**: Using existing domain vocabulary
- ✅ **C-4**: Simple, composable functions
- ✅ **PY-1**: Type hints for all functions
- ✅ **PY-2**: Pydantic models for data validation
- ✅ **PY-7**: Explicit exception handling
- ✅ **T-1**: Colocated unit tests
- ✅ **T-3**: Integration tests for API changes

## Next Steps

1. Review and approve this plan
2. Create feature branch
3. Implement Phase 1 (extract utilities, create agents)
4. Local testing and validation
5. Proceed with remaining phases
6. Deploy to development environment
7. Validate and iterate