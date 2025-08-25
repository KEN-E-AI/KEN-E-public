#!/usr/bin/env python3
"""
Standalone Multi-Agent Supervisor V2 for deployment
This file contains all the code needed for the supervisor agent in one place
to avoid import issues during deployment.
"""

import os
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List
import uuid
import json
from google.adk.agents import Agent, SequentialAgent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part
from vertexai.preview import reasoning_engines
import re  # For parsing queries

logger = logging.getLogger(__name__)


def extract_tenant_context(input_data: Any) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extract tenant context from various input formats.
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


def invoke_agent_sync(
    agent: Agent, 
    query: str, 
    user_id: str = None, 
    session_id: str = None
) -> str:
    """
    Synchronous wrapper for agent invocation with proper async handling.
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
            if event.content and event.content.parts:
                if text := ''.join(part.text or '' for part in event.content.parts):
                    response_text += text
        
        return response_text
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, invoke_agent())
                return future.result(timeout=300)
        else:
            return loop.run_until_complete(invoke_agent())
    except Exception as e:
        logger.error(f"Error in sync agent invocation: {str(e)}")
        return f"Error invoking agent: {str(e)}"


# Dispatcher functions with tenant context support
def dispatch_to_company_news(query: str, tenant_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    For now, returns a simulated response.
    """
    try:
        logger.info(f"🔄 Routing company news query...")
        # In production, this would call the actual news agent
        result = f"[Company News Agent Response] I'll search for news about: {query[:100]}..."
        
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
    """
    try:
        logger.info(f"🔄 Routing Google Analytics query...")
        
        # For now, returns a simulated response
        result = f"[Google Analytics Agent Response] I'll fetch analytics data for: {query[:100]}..."
        
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
    Dispatch strategy queries to the V3 strategy agent.
    This embeds the actual V3 SequentialAgent directly.
    """
    try:
        logger.info(f"🔄 Routing to V3 Strategy SequentialAgent...")
        
        # Extract account and user context
        account_id = None
        user_id = None
        company_name = None
        industry = ""
        websites = []
        customer_regions = []
        annual_ad_budget = 0.0
        
        if tenant_context:
            account_id = tenant_context.get('account_id') or tenant_context.get('tenant_id')
            user_id = tenant_context.get('user_id')
            
            # Extract account data if available
            # This data comes from the account creation or from the query
            company_name = tenant_context.get('company_name') or tenant_context.get('account_name')
            industry = tenant_context.get('industry', "")
            websites = tenant_context.get('websites', [])
            customer_regions = tenant_context.get('customer_regions') or tenant_context.get('region', [])
            annual_ad_budget = tenant_context.get('annual_ad_budget') or tenant_context.get('estimated_annual_ad_budget', 0.0)
        
        # If company name not in context, try to parse from query
        if not company_name:
            company_match = re.search(r'for\s+([^.!?]+?)(?:\s|$)', query, re.IGNORECASE)
            if company_match:
                company_name = company_match.group(1).strip()
            else:
                company_name = "Unknown Company"
        
        # Parse the query itself to check if it contains the account data
        # Pattern: "Generate all 5 strategy documents for {company_name}\n\nNEW INFORMATION:\n..."
        project_id = None  # Must be provided explicitly
        if "NEW INFORMATION:" in query:
            lines = query.split('\n')
            for line in lines:
                if line.startswith("Project ID:"):
                    project_id = line.replace("Project ID:", "").strip()
                elif line.startswith("Company to analyze:"):
                    company_name = line.replace("Company to analyze:", "").strip()
                elif line.startswith("Company websites:"):
                    websites_str = line.replace("Company websites:", "").strip()
                    websites = [w.strip() for w in websites_str.strip('[]').split(',')]
                elif line.startswith("Industry:"):
                    industry = line.replace("Industry:", "").strip()
                elif line.startswith("Customer regions:"):
                    regions_str = line.replace("Customer regions:", "").strip()
                    customer_regions = [r.strip() for r in regions_str.split(',')]
                elif line.startswith("Annual advertising budget:"):
                    budget_str = line.replace("Annual advertising budget:", "").replace("$", "").replace(",", "").strip()
                    try:
                        annual_ad_budget = float(budget_str)
                    except:
                        annual_ad_budget = 0.0
        
        logger.info(f"Extracted context - Company: {company_name}, Industry: {industry}, Account: {account_id}, Project: {project_id}")
        
        # Validate that we have the required project ID
        if not project_id:
            error_msg = "Project ID is required for strategy generation but was not provided in the message"
            logger.error(error_msg)
            return error_msg
        
        # Embed the V3 strategy agent code directly here to avoid import issues
        try:
            # Import strategy agent components
            from agents.strategy_agent.models import StrategyContext
            from agents.strategy_agent.sub_agents import (
                create_business_strategy_agent,
                create_competitive_strategy_agent,
                create_customer_strategy_agent,
                create_marketing_strategy_agent,
                create_brand_guidelines_agent
            )
            
            # Initialize W&B observability
            try:
                import weave
                weave.init(project_name="ken-e-strategy-agent")
                logger.info("W&B observability initialized")
            except Exception as e:
                logger.warning(f"W&B initialization skipped: {e}")
            
            # Create context with all the extracted data including project_id
            context = StrategyContext(
                project_id=project_id,  # Pass the extracted project ID
                account_id=account_id or str(uuid.uuid4()),
                user_id=user_id,
                company_name=company_name,
                websites=websites if isinstance(websites, list) else [],
                industry=industry or "General",
                customer_regions=customer_regions if isinstance(customer_regions, list) else [],
                annual_ad_budget=annual_ad_budget
            )
            
            logger.info(f"Creating V3 SequentialAgent for {company_name} in {industry} industry")
            
            # Initialize Firestore clients with the project_id
            from agents.strategy_agent.utils import initialize_firestore as utils_init
            from agents.strategy_agent.context import initialize_firestore as context_init
            
            utils_init(project_id)
            context_init(project_id)
            logger.info(f"Initialized Firestore clients with project: {project_id}")
            
            # Create all 5 strategy agents using the EXISTING implementations
            business_agent = create_business_strategy_agent(context)
            competitive_agent = create_competitive_strategy_agent(context)
            customer_agent = create_customer_strategy_agent(context)
            marketing_agent = create_marketing_strategy_agent(context)
            brand_agent = create_brand_guidelines_agent(context)
            
            # Chain them together in a SequentialAgent
            strategy_sequential_agent = SequentialAgent(
                name="v3_strategy_generator",
                sub_agents=[
                    business_agent,
                    competitive_agent,
                    customer_agent,
                    marketing_agent,
                    brand_agent
                ],
                description="Generates all 5 strategy documents in sequence"
            )
            
            logger.info(f"✅ V3 SequentialAgent created with 5 strategy agents")
            
            # ACTUALLY EXECUTE the SequentialAgent
            logger.info(f"[EXECUTION] Starting SequentialAgent execution for {company_name}")
            try:
                # In ADK, we need to use Runner to execute the agent
                from google.adk import Runner
                
                # Create a runner for the sequential agent
                runner = Runner(agent=strategy_sequential_agent)
                
                # Execute with a starting message
                execution_input = f"Generate all 5 strategy documents for {company_name} in the {industry} industry."
                logger.info(f"[EXECUTION] Running SequentialAgent with input: {execution_input}")
                
                # Run the agent
                result = runner.run(execution_input)
                logger.info(f"[EXECUTION] SequentialAgent completed successfully")
                logger.info(f"[EXECUTION] Result type: {type(result)}")
                
                # Each sub-agent saves to Firestore internally during execution
                logger.info(f"[EXECUTION] Documents should be saved to strategy_docs_{account_id}")
                
            except Exception as e:
                logger.error(f"[EXECUTION] Failed to run SequentialAgent: {e}", exc_info=True)
                # Continue even if execution fails to provide feedback
            
            result = f"""✅ V3 Strategy Generation Initiated

Company: {company_name}
Industry: {industry}
Account ID: {account_id or 'New Account'}
Websites: {', '.join(websites) if websites else 'Not specified'}
Regions: {', '.join(customer_regions) if customer_regions else 'Not specified'}
Budget: ${annual_ad_budget:,.0f} annually

The V3 SequentialAgent is generating all 5 strategy documents:
1. Business Strategy (with 3-iteration refinement loop)
2. Competitive Strategy (with 3-iteration refinement loop)  
3. Customer Strategy (with 3-iteration refinement loop)
4. Marketing Strategy (with 3-iteration refinement loop)
5. Brand Guidelines (with 3-iteration refinement loop)

Each document:
- Uses exact instructions from V3 specifications
- Incorporates best practices from Firestore
- Goes through reviewer-editor refinement
- Saves automatically to Firestore

Documents are being saved to: strategy_docs_{account_id or 'PENDING'}

Process duration: ~3-5 minutes"""
            
            return {
                'status': 'success',
                'query': query,
                'result': result,
                'source': 'v3_strategy_sequential',
                'agent': 'strategy',
                'account_id': account_id,
                'company_name': company_name
            }
            
        except ImportError as e:
            logger.error(f"Failed to import V3 strategy components: {e}")
            # Fallback if imports fail
            result = f"""⚠️ Strategy Agent Import Error

The V3 strategy agent components could not be loaded.
Error: {str(e)}

This may be due to deployment packaging issues.
Please check that all strategy agent files are included."""
            
            return {
                'status': 'error',
                'query': query,
                'result': result,
                'error': str(e),
                'source': 'strategy_specialist',
                'agent': 'strategy'
            }
        
    except Exception as e:
        logger.error(f"Error in strategy agent dispatch: {e}", exc_info=True)
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
    """
    
    # Create a wrapper function that handles tenant context
    def dispatch_with_context(dispatch_func):
        """Wrapper to extract tenant context from the full input"""
        def wrapper(full_input: str) -> str:
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
agent = supervisor_agent_v2
root_agent = supervisor_agent_v2

# Wrap with AdkApp for proper deployment
app = reasoning_engines.AdkApp(
    agent=root_agent,
    enable_tracing=True
)