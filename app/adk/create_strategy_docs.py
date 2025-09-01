#!/usr/bin/env python3
"""
Create Strategy Documents Agent - Main Entry Point for Strategy Generation
This agent serves as the supervisor that routes strategy generation requests
to the orchestrator and manages the creation of all 5 strategy documents.
"""

import os
import logging
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Try to load from app/adk/.env first, then fall back to current directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"Loaded environment from {env_path}")
    else:
        load_dotenv()  # Try default locations
except ImportError:
    logging.warning("python-dotenv not available, using system environment variables only")
import asyncio
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List
import uuid
import json
from datetime import datetime
from google.adk.agents import Agent, SequentialAgent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part
from vertexai.preview import reasoning_engines
import re  # For parsing queries

# Import optional dependencies
try:
    import weave
    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False
    weave = None

# Import strategy agent components at module level so they're packaged
try:
    from agents.strategy_agent.models import StrategyContext
    from agents.strategy_agent.agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent
    )
    from agents.strategy_agent.firestore import initialize_firestore
    STRATEGY_AGENTS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Strategy agent modules imported successfully at module level")
except ImportError as e:
    STRATEGY_AGENTS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"Strategy agent modules not available: {e}")
    # Define dummy classes/functions to prevent errors
    StrategyContext = None
    create_business_strategy_agent = None
    create_competitive_strategy_agent = None
    create_customer_strategy_agent = None
    create_marketing_strategy_agent = None
    create_brand_guidelines_agent = None
    initialize_firestore = None


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
                for part in event.content.parts:
                    # Handle text parts
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
                    # Handle function call parts (log but don't add to response)
                    elif hasattr(part, 'function_call'):
                        logger.debug(f"Function call part: {part.function_call}")
                    # Log other non-text parts without warning
                    else:
                        logger.debug(f"Non-text part type: {type(part).__name__}")
        
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
        # The API may send in two different formats:
        # Format 1: "Please execute strategy generation with these parameters:\n- company_name: ..."
        # Format 2: "Generate all 5 strategy documents for {company_name}\n\nNEW INFORMATION:\n..."
        project_id = None  # Must be provided explicitly
        
        # Check for Format 1: Parameter list format
        if "execute strategy generation with these parameters:" in query.lower():
            lines = query.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith("- company_name:"):
                    company_name = line.replace("- company_name:", "").strip()
                elif line.startswith("- project_id:"):
                    project_id = line.replace("- project_id:", "").strip()
                elif line.startswith("- industry:"):
                    industry = line.replace("- industry:", "").strip()
                elif line.startswith("- websites:"):
                    websites_str = line.replace("- websites:", "").strip()
                    websites = [w.strip() for w in websites_str.split(',')]
                elif line.startswith("- customer_regions:"):
                    regions_str = line.replace("- customer_regions:", "").strip()
                    customer_regions = [r.strip() for r in regions_str.split(',')]
                elif line.startswith("- account_id:"):
                    # Extract only the account ID, handling cases where multiple parameters might be on same line
                    account_id_raw = line.replace("- account_id:", "").strip()
                    # Split on common delimiters that might appear if lines are concatenated
                    account_id = account_id_raw.split(' - ')[0].strip()
                    logger.info(f"Parsed account_id: '{account_id}' from line: '{line}'")
                elif line.startswith("- user_id:"):
                    user_id = line.replace("- user_id:", "").strip().split(' - ')[0].strip()
                elif line.startswith("- annual_ad_budget:"):
                    budget_str = line.replace("- annual_ad_budget:", "").replace("$", "").replace(",", "").strip().split(' - ')[0].strip()
                    try:
                        annual_ad_budget = float(budget_str)
                    except:
                        annual_ad_budget = 0.0
        
        # Check for Format 2: NEW INFORMATION format
        elif "NEW INFORMATION:" in query:
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
        
        # Check if strategy agents are available (imported at module level)
        if not STRATEGY_AGENTS_AVAILABLE:
            logger.error("Strategy agents not available - modules not imported")
            error_msg = """⚠️ Strategy Agent Not Available

The strategy agent components are not available in this deployment.
This is likely due to the agent modules not being included in the deployment package.

Please ensure the 'agents' directory is properly packaged during deployment."""
            return {
                'status': 'error',
                'query': query,
                'result': error_msg,
                'source': 'strategy_specialist',
                'agent': 'strategy'
            }
        
        try:
            # Strategy agents were imported at module level, so they're available here
            logger.info("Using pre-imported strategy agent modules")
            
            # Initialize W&B observability with API key from environment
            if WEAVE_AVAILABLE and weave:
                try:
                    # Set W&B API key from environment if available
                    wandb_api_key = os.getenv("WANDB_API_KEY")
                    if wandb_api_key:
                        os.environ["WANDB_API_KEY"] = wandb_api_key
                        # Also try to login with wandb if available
                        try:
                            import wandb
                            wandb.login(key=wandb_api_key, relogin=True)
                            logger.info("W&B authenticated with API key")
                        except Exception as e:
                            logger.debug(f"W&B login attempt: {e}")
                    
                    # Initialize weave for observability
                    weave.init(project_name="ken-e-strategy-agent")
                    logger.info("W&B observability initialized successfully")
                except Exception as e:
                    logger.warning(f"W&B initialization failed: {e}")
            else:
                logger.info("W&B observability not available")
            
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
            
            # Log the actual data being passed to the agents
            logger.info(f"[DATA_DEBUG] Creating strategy agents with:")
            logger.info(f"[DATA_DEBUG] - Company Name: {company_name}")
            logger.info(f"[DATA_DEBUG] - Industry: {industry}")
            logger.info(f"[DATA_DEBUG] - Websites: {websites}")
            logger.info(f"[DATA_DEBUG] - Customer Regions: {customer_regions}")
            logger.info(f"[DATA_DEBUG] - Annual Ad Budget: ${annual_ad_budget:,.2f}" if annual_ad_budget else "[DATA_DEBUG] - Annual Ad Budget: Not specified")
            logger.info(f"[DATA_DEBUG] - Account ID: {account_id}")
            logger.info(f"[DATA_DEBUG] - User ID: {user_id}")
            logger.info(f"[DATA_DEBUG] - Project ID: {project_id}")
            
            logger.info(f"Creating V3 SequentialAgent for {company_name} in {industry} industry")
            
            # Initialize Firestore clients with the project_id
            if initialize_firestore:
                initialize_firestore(project_id)
                logger.info(f"Initialized Firestore clients with project: {project_id}")
            else:
                logger.warning("Firestore initialization function not available")
            
            # Import the orchestrator's execution function
            try:
                from agents.strategy_agent.orchestrator import execute_strategy_generation
                from agents.strategy_agent.firestore import FirestoreClient
                
                logger.info("✅ Orchestrator imported successfully")
                
                # Use the orchestrator to execute all 5 agents properly
                logger.info(f"[ORCHESTRATOR] Starting orchestrated execution for {company_name}")
                
                # Create Firestore client
                firestore_client = None
                if initialize_firestore:
                    try:
                        firestore_client = FirestoreClient(project_id=project_id)
                        logger.info(f"[ORCHESTRATOR] Firestore client initialized")
                    except Exception as e:
                        logger.error(f"[ORCHESTRATOR] Failed to initialize Firestore client: {e}")
                
                # Execute the strategy generation using the orchestrator
                orchestrator_result = execute_strategy_generation(
                    company_name=company_name,
                    industry=industry,
                    websites=','.join(websites) if websites else '',
                    customer_regions=','.join(customer_regions) if customer_regions else '',
                    account_id=account_id,
                    user_id=user_id,
                    annual_ad_budget=annual_ad_budget,
                    project_id=project_id,
                    firestore_client=firestore_client
                )
                
                logger.info(f"[ORCHESTRATOR] Result: {orchestrator_result}")
                
                # Set results for the response
                results = {"orchestrator_status": orchestrator_result}
                
            except ImportError as e:
                logger.error(f"[ORCHESTRATOR] Failed to import orchestrator: {e}")
                # Fallback: Just create the agents without executing them
                # This at least creates the placeholder documents
                logger.info("Falling back to creating agents without execution")
                
                business_agent = create_business_strategy_agent(context)
                competitive_agent = create_competitive_strategy_agent(context)
                customer_agent = create_customer_strategy_agent(context)
                marketing_agent = create_marketing_strategy_agent(context)
                brand_agent = create_brand_guidelines_agent(context)
                
                logger.info(f"✅ V3 Strategy Agents created (but not executed due to orchestrator import failure)")
                results = {"status": "Agents created but orchestrator not available"}
            
            # Save initial context to Firestore for agents to access
            try:
                if initialize_firestore:
                    # Save context for agents to use
                    from google.cloud import firestore
                    db = firestore.Client(project=project_id)
                    
                    # Create initial document structure
                    strategy_context_ref = db.collection(f"strategy_docs_{account_id}").document("context")
                    strategy_context_ref.set({
                        "company_name": company_name,
                        "industry": industry,
                        "websites": websites,
                        "customer_regions": customer_regions,
                        "annual_ad_budget": annual_ad_budget,
                        "account_id": account_id,
                        "user_id": user_id,
                        "project_id": project_id,
                        "status": "initiated",
                        "created_at": datetime.utcnow().isoformat()
                    })
                    logger.info(f"[FIRESTORE] Saved strategy context for {account_id}")
                    
                    # Create placeholder documents for each strategy type
                    strategy_types = [
                        "business_strategy",
                        "competitive_strategy",
                        "customer_strategy",
                        "marketing_strategy",
                        "brand_guidelines"
                    ]
                    
                    for doc_type in strategy_types:
                        doc_ref = db.collection(f"strategy_docs_{account_id}").document(doc_type)
                        doc_ref.set({
                            "status": "pending",
                            "created_at": datetime.utcnow().isoformat(),
                            "metadata": {
                                "company_name": company_name,
                                "industry": industry,
                                "account_id": account_id,
                                "doc_type": doc_type
                            }
                        })
                    
                    logger.info(f"[FIRESTORE] Created placeholder documents for all strategy types")
                    
            except Exception as e:
                logger.error(f"[FIRESTORE] Failed to save context: {e}")
                # Continue even if Firestore save fails
            
            # Prepare summary of results
            if "orchestrator_status" in results:
                # Using orchestrator results
                orchestrator_msg = results.get("orchestrator_status", "Unknown status")
                if "Successfully generated" in orchestrator_msg:
                    result = f"""✅ V3 Strategy Generation Completed

Company: {company_name}
Industry: {industry}
Account ID: {account_id or 'New Account'}
Websites: {', '.join(websites) if websites else 'Not specified'}
Regions: {', '.join(customer_regions) if customer_regions else 'Not specified'}
Budget: ${annual_ad_budget:,.0f} annually

{orchestrator_msg}

Each document has been:
- Generated using Gemini 2.5 Pro with 3-iteration refinement loops
- Saved to Firestore collection: strategy_docs_{account_id or 'PENDING'}

The strategy documents are now available for viewing."""
                else:
                    result = f"""⚠️ V3 Strategy Generation In Progress

Company: {company_name}
Industry: {industry}
Account ID: {account_id or 'New Account'}

Status: {orchestrator_msg}

Documents will be saved to: strategy_docs_{account_id or 'PENDING'}"""
            else:
                # Fallback message if orchestrator wasn't used
                result = f"""⚠️ V3 Strategy Agents Created

Company: {company_name}
Industry: {industry}
Account ID: {account_id or 'New Account'}

The strategy agents have been configured but the orchestrator is not available for execution.
Manual intervention may be required to generate the strategy documents.

Target collection: strategy_docs_{account_id or 'PENDING'}"""
            
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
            import sys
            logger.error(f"Failed to import V3 strategy components: {e}")
            logger.error(f"Python path: {sys.path}")
            logger.error(f"Current file: {__file__ if '__file__' in globals() else 'unknown'}")
            
            # Fallback if imports fail
            result = f"""⚠️ Strategy Agent Import Error

The V3 strategy agent components could not be loaded.
Error: {str(e)}

Python Path: {sys.path[:3]}...
Current Directory: {os.getcwd() if 'os' in globals() else 'unknown'}

This may be due to deployment packaging issues.
Please check that all strategy agent files are included in the deployment."""
            
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