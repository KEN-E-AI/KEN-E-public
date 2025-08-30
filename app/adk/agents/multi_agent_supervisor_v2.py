"""
Multi-Agent Supervisor V2 - Stateless orchestration with tenant context support
Handles routing between Company News, Google Analytics, and Strategy agents
"""

import os
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Tuple
import uuid
import json
from google.adk.agents import Agent
# No need to import Tool - functions are passed directly
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part

# Import our specialized agents
from .company_news_chatbot.agent import root_agent as news_agent
from .google_analytics_agent_v4 import google_analytics_agent_v4
from .strategy_agent.orchestrator import strategy_agent, execute_strategy_generation as invoke_strategy_agent_sync

logger = logging.getLogger(__name__)


def extract_tenant_context(input_data: Any) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extract tenant context from various input formats.
    
    Expected formats:
    1. String: "message"
    2. Dict: {"message": "...", "tenant_id": "...", "tenant_credentials": "..."}
    3. Dict: {"query": "...", "tenant_id": "...", "tenant_credentials": "..."}
    
    Returns: (tenant_id, tenant_credentials, message)
    """
    tenant_id = None
    tenant_credentials = None
    message = ""
    
    if isinstance(input_data, str):
        message = input_data
    elif isinstance(input_data, dict):
        # Extract message
        message = input_data.get('message', input_data.get('query', str(input_data)))
        
        # Extract tenant context
        tenant_id = input_data.get('tenant_id')
        tenant_credentials = input_data.get('tenant_credentials')
    else:
        message = str(input_data)
    
    return tenant_id, tenant_credentials, message


def invoke_agent_sync(
    agent: Agent, 
    query: str, 
    user_id: str = None, 
    session_id: str = None
) -> str:
    """
    Synchronous wrapper for agent invocation with proper async handling.
    Following ADK best practices from the codebase.
    """
    if user_id is None:
        user_id = f"supervisor_user_{uuid.uuid4().hex[:8]}"
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
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            # Follow ADK's official pattern from cli.py (lines 102-104)
            if event.content and event.content.parts:
                if text := ''.join(part.text or '' for part in event.content.parts):
                    # Accumulate all text responses
                    response_text += text
        
        return response_text
    
    try:
        # Handle event loop scenarios (following ADK pattern)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, use ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, invoke_agent())
                return future.result(timeout=300)  # 5 minute timeout
        else:
            # If no event loop is running, create one
            return loop.run_until_complete(invoke_agent())
    except Exception as e:
        logger.error(f"Error in sync agent invocation: {str(e)}")
        return f"Error invoking agent: {str(e)}"


# Dispatcher functions with tenant context support
def dispatch_to_company_news(query: str, tenant_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    News agent doesn't need tenant context as it uses public data.
    """
    try:
        logger.info(f"🔄 Routing company news query to specialized agent...")
        result = invoke_agent_sync(news_agent, query)
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'company_news_specialist',
            'agent': 'news'
        }
    except Exception as e:
        logger.error(f"Error in news agent dispatch: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'company_news_specialist',
            'agent': 'news'
        }


def dispatch_to_google_analytics(
    query: str, 
    tenant_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Dispatch Google Analytics queries with tenant context.
    In production, tenant context comes from the authenticated user's session.
    For testing, we use environment variables.
    """
    try:
        logger.info(f"🔄 Routing Google Analytics query to specialized agent...")
        
        # In production, credentials would come from the KEN-E app's user session
        # For testing/development, use environment variables
        if not tenant_context or not tenant_context.get('tenant_credentials'):
            # Testing mode: use environment credentials
            env_creds = os.getenv('GA_PERSONAL_CREDENTIALS')
            if env_creds:
                tenant_context = {
                    'tenant_id': os.getenv('GA_TENANT_ID', 'test-org'),
                    'tenant_credentials': env_creds
                }
                logger.info("Using test credentials from environment")
        
        # Prepare query with tenant context
        if tenant_context and tenant_context.get('tenant_id') and tenant_context.get('tenant_credentials'):
            # Inject tenant context into the query for the GA agent
            enhanced_query = f"TENANT_ID:{tenant_context['tenant_id']} TENANT_CREDS:{tenant_context['tenant_credentials']} {query}"
        else:
            # No credentials available
            enhanced_query = query
        
        result = invoke_agent_sync(google_analytics_agent_v4, enhanced_query)
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'google_analytics_specialist',
            'agent': 'analytics',
            'tenant_id': tenant_context.get('tenant_id') if tenant_context else None
        }
    except Exception as e:
        logger.error(f"Error in analytics agent dispatch: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'google_analytics_specialist',
            'agent': 'analytics'
        }


def dispatch_to_strategy(
    query: str,
    tenant_context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Dispatch strategy queries to the iterative strategy agent.
    Strategy agent needs account context for document persistence.
    """
    try:
        logger.info(f"🔄 Routing strategy query to specialized agent...")
        
        # Parse the query to extract strategy generation parameters
        # The query format from API is:
        # "Generate all 5 strategy documents for {company_name}
        #  Please execute strategy generation with these parameters:
        #  - company_name: ...
        #  - industry: ...
        #  - websites: ...
        #  - customer_regions: ...
        #  - account_id: ...
        #  - user_id: ...
        #  - annual_ad_budget: ...
        #  - project_id: ..."
        
        import re
        
        # Extract parameters from the formatted message
        params = {}
        
        # Try to extract parameters from the structured format
        param_patterns = {
            'company_name': r'[-•]\s*company_name:\s*(.+?)(?:\n|$)',
            'industry': r'[-•]\s*industry:\s*(.+?)(?:\n|$)',
            'websites': r'[-•]\s*websites:\s*(.+?)(?:\n|$)',
            'customer_regions': r'[-•]\s*customer_regions:\s*(.+?)(?:\n|$)',
            'account_id': r'[-•]\s*account_id:\s*(.+?)(?:\n|$)',
            'user_id': r'[-•]\s*user_id:\s*(.+?)(?:\n|$)',
            'annual_ad_budget': r'[-•]\s*annual_ad_budget:\s*(.+?)(?:\n|$)',
            'project_id': r'[-•]\s*project_id:\s*(.+?)(?:\n|$)'
        }
        
        for param_name, pattern in param_patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Convert annual_ad_budget to float
                if param_name == 'annual_ad_budget':
                    try:
                        params[param_name] = float(value)
                    except (ValueError, TypeError):
                        params[param_name] = 0.0
                else:
                    params[param_name] = value
        
        # Use tenant_context to fill in missing values
        if tenant_context:
            if 'account_id' not in params:
                params['account_id'] = tenant_context.get('account_id') or tenant_context.get('tenant_id')
            if 'user_id' not in params:
                params['user_id'] = tenant_context.get('user_id')
            if 'project_id' not in params:
                params['project_id'] = tenant_context.get('project_id')
        
        # Check if we have the required parameters
        required_params = ['company_name', 'industry', 'websites', 'customer_regions', 'account_id', 'user_id']
        missing_params = [p for p in required_params if p not in params or not params[p]]
        
        if missing_params:
            logger.warning(f"Missing required parameters for strategy generation: {missing_params}")
            logger.info(f"Extracted parameters: {params}")
            logger.info(f"Query preview: {query[:500]}")
            # Try to proceed with what we have
        
        # Set defaults for optional parameters
        params.setdefault('annual_ad_budget', 0.0)
        params.setdefault('project_id', os.getenv('VERTEX_AI_PROJECT_ID', 'ken-e-dev'))
        
        logger.info(f"Calling execute_strategy_generation with params: {params}")
        
        # Invoke the strategy agent with the correct parameters
        result = invoke_strategy_agent_sync(
            company_name=params.get('company_name', 'Unknown Company'),
            industry=params.get('industry', 'Unknown Industry'),
            websites=params.get('websites', ''),
            customer_regions=params.get('customer_regions', ''),
            account_id=params.get('account_id', ''),
            user_id=params.get('user_id', ''),
            annual_ad_budget=params.get('annual_ad_budget', 0.0),
            project_id=params.get('project_id')
        )
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'strategy_specialist',
            'agent': 'strategy',
            'account_id': account_id
        }
    except Exception as e:
        logger.error(f"Error in strategy agent dispatch: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e),
            'source': 'strategy_specialist',
            'agent': 'strategy'
        }


# Create the stateless supervisor agent
def create_supervisor_agent():
    """
    Create the main supervisor agent that uses LLM-based routing.
    Handles tenant context extraction and passing.
    """
    
    # Create a wrapper function that handles tenant context
    def dispatch_with_context(dispatch_func):
        """Wrapper to extract tenant context from the full input"""
        def wrapper(full_input: str) -> str:  # Return string, not dict!
            # Try to parse as JSON first (for structured input from web service)
            try:
                input_data = json.loads(full_input)
                tenant_id, tenant_credentials, message = extract_tenant_context(input_data)
                tenant_context = {
                    'tenant_id': tenant_id,
                    'tenant_credentials': tenant_credentials
                } if tenant_id and tenant_credentials else None
                result = dispatch_func(message, tenant_context)
                # Return just the result string, not the full dict
                if isinstance(result, dict) and 'result' in result:
                    return result['result']
                return str(result)
            except json.JSONDecodeError:
                # Fall back to string input
                result = dispatch_func(full_input, None)
                # Return just the result string, not the full dict
                if isinstance(result, dict) and 'result' in result:
                    return result['result']
                return str(result)
        return wrapper
    
    # Create dispatcher functions with context handling
    search_company_news = dispatch_with_context(dispatch_to_company_news)
    search_company_news.__name__ = "search_company_news"
    search_company_news.__doc__ = "Search for company news, financial updates, earnings reports, market analysis, and business announcements"
    
    query_google_analytics = dispatch_with_context(dispatch_to_google_analytics)
    query_google_analytics.__name__ = "query_google_analytics"
    query_google_analytics.__doc__ = "Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance, and access GA4 properties"
    
    create_update_strategy = dispatch_with_context(dispatch_to_strategy)
    create_update_strategy.__name__ = "create_update_strategy"
    create_update_strategy.__doc__ = "Create or update business strategy documents, competitive strategy documents, or channel strategy documents using iterative refinement"
    
    supervisor = Agent(
        name="multi_capability_supervisor_v2",
        model="gemini-2.0-flash",
        instruction="""You are an intelligent routing supervisor that provides access to three specialized capabilities.

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
- GA4 property configuration and account information

**CAPABILITY 3 - Strategy Document Creation & Management:**
Use `create_update_strategy` for queries about:
- Creating business strategy documents
- Creating competitive strategy documents
- Creating channel strategy documents (email, social media, etc.)
- Updating existing strategy documents with new information
- Refining or improving strategy documents
- Strategic planning and recommendations
- Marketing strategy development
- **Generate all 5 strategy documents** (this is a strategy creation request)
- **Generate strategy documents for [company name]** (strategy creation)

**ROUTING GUIDELINES:**

1. **Analyze the user's intent using your LLM capabilities** - don't use hardcoded rules
2. **Route based on the primary focus of the query:**
   - Company/business/market focus → search_company_news
   - Website/traffic/analytics focus → query_google_analytics
   - Strategy creation/planning focus → create_update_strategy
   - **Messages starting with "Generate all 5 strategy documents" → create_update_strategy**
   - **Messages starting with "Generate strategy documents" → create_update_strategy**

3. **When routing, ALWAYS pass the COMPLETE user input to the tool** - if you received JSON, pass the entire JSON string, not just the message

4. **Handle ambiguous queries:**
   - If unclear, briefly ask for clarification about which capability they need
   - If query could match multiple capabilities, ask which they'd like to explore first

5. **Response handling:**
   - ALWAYS relay the complete response from the specialized agent to the user
   - The tool response IS your response - present it in full
   - Don't just say "OK" or "Thank you" - share the actual information returned
   - Maintain the formatting from the specialist agent

**IMPORTANT NOTES:**
- You are integrated with the KEN-E app where users are already authenticated
- NEVER ask users for credentials - they're already logged in with Google
- The system automatically uses the logged-in user's Google account for GA queries
- Just route the queries - authentication is handled by the platform

**EXAMPLES OF ROUTING:**
- "What's the latest news about Apple?" → search_company_news
- "Show me website traffic for last week" → query_google_analytics  
- "How many users visited my site?" → query_google_analytics
- "Tesla earnings report" → search_company_news
- "Bounce rate by country" → query_google_analytics
- "Microsoft acquisition news" → search_company_news
- "Create a business strategy for my company" → create_update_strategy
- "Update our competitive strategy document" → create_update_strategy
- "Develop an email marketing strategy" → create_update_strategy
- "Help me with strategic planning" → create_update_strategy
- "Generate all 5 strategy documents for Acme Corp" → create_update_strategy
- "Generate strategy documents for my company" → create_update_strategy

Remember: You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools.""",
        tools=[search_company_news, query_google_analytics, create_update_strategy]
    )
    
    return supervisor


# Export the supervisor agent
supervisor_agent_v2 = create_supervisor_agent()