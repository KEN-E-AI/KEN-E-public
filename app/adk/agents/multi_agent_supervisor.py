"""
Multi-Agent Supervisor - Orchestrates between Company News and Google Analytics agents
Following ADK best practices for agent composition and LLM-based routing
"""

import os
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any
import uuid
from google.adk.agents import Agent
from google.adk.resources import Tool
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part

# Import our specialized agents
from .company_news_chatbot.agent import root_agent as news_agent
from .google_analytics_agent import google_analytics_agent

logger = logging.getLogger(__name__)


def invoke_agent_sync(agent: Agent, query: str, user_id: str = None, session_id: str = None) -> str:
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
            if hasattr(event, 'message') and event.message:
                if hasattr(event.message, 'content') and event.message.content:
                    for part in event.message.content.parts:
                        if hasattr(part, 'text'):
                            response_text += part.text
        
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


# Dispatcher functions following ADK patterns
def dispatch_to_company_news(query: str) -> Dict[str, Any]:
    """
    Dispatch company news and business information queries to the specialized news agent.
    Returns structured response following ADK patterns.
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


def dispatch_to_google_analytics(query: str) -> Dict[str, Any]:
    """
    Dispatch Google Analytics queries to the specialized analytics agent.
    Returns structured response following ADK patterns.
    """
    try:
        logger.info(f"🔄 Routing Google Analytics query to specialized agent...")
        result = invoke_agent_sync(google_analytics_agent, query)
        
        return {
            'status': 'success',
            'query': query,
            'result': result,
            'source': 'google_analytics_specialist',
            'agent': 'analytics'
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


# Create the supervisor agent following ADK best practices
def create_supervisor_agent():
    """
    Create the main supervisor agent that uses LLM-based routing.
    Following ADK dispatcher pattern best practices.
    """
    
    # Create dispatcher tools
    news_dispatcher = Tool(
        function=dispatch_to_company_news,
        name="search_company_news",
        description="Search for company news, financial updates, earnings reports, market analysis, and business announcements"
    )
    
    analytics_dispatcher = Tool(
        function=dispatch_to_google_analytics,
        name="query_google_analytics",
        description="Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance, and access GA4 properties"
    )
    
    supervisor = Agent(
        name="multi_capability_supervisor",
        model="gemini-2.0-flash-exp",
        instruction="""You are an intelligent routing supervisor that provides access to two specialized capabilities:

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

**ROUTING GUIDELINES:**

1. **Analyze the user's intent using your LLM capabilities** - don't use hardcoded rules
2. **Route based on the primary focus of the query:**
   - Company/business/market focus → search_company_news
   - Website/traffic/analytics focus → query_google_analytics

3. **When routing, ALWAYS use the appropriate tool directly** - don't explain what you're going to do, just do it

4. **Handle ambiguous queries:**
   - If unclear, briefly ask: "Are you looking for company news or website analytics data?"
   - If query mentions both, ask which they'd like to explore first

5. **Response handling:**
   - Present the specialized agent's response directly
   - Don't add unnecessary wrapper text
   - Maintain the formatting from the specialist agent

**EXAMPLES OF ROUTING:**
- "What's the latest news about Apple?" → search_company_news
- "Show me website traffic for last week" → query_google_analytics  
- "How many users visited my site?" → query_google_analytics
- "Tesla earnings report" → search_company_news
- "Bounce rate by country" → query_google_analytics
- "Microsoft acquisition news" → search_company_news

**IMPORTANT:** You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools. Never attempt to answer from general knowledge.""",
        tools=[news_dispatcher, analytics_dispatcher]
    )
    
    return supervisor


# Export the supervisor agent - this is what ADK will use
supervisor_agent = create_supervisor_agent()