#!/usr/bin/env python3
"""
Strategy Supervisor Agent - Properly structured for ADK deployment.
This module properly imports all dependencies at the module level.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from google.adk.agents import Agent, SequentialAgent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content
from vertexai.preview import reasoning_engines

# Configure logging for Agent Engine
import sys
import os

# Set up basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Try to set up Google Cloud Logging if available
try:
    import google.cloud.logging
    # Initialize Cloud Logging client
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    logging_client = google.cloud.logging.Client(project=project_id)
    # Set up Cloud Logging handler
    logging_client.setup_logging()
    logging.info("Google Cloud Logging configured successfully")
except Exception as e:
    logging.info(f"Could not configure Google Cloud Logging: {e}, using stdout")

# Import W&B setup if available (will be created during deployment)
try:
    import wandb_setup
    logging.info("W&B configuration loaded from wandb_setup.py")
except ImportError:
    logging.info("wandb_setup.py not found, W&B will use environment variables")

# Import all strategy components at module level
# These imports will be resolved during deployment packaging
from agents.strategy_agent.models import StrategyContext
from agents.strategy_agent.sub_agents import (
    create_business_strategy_agent,
    create_competitive_strategy_agent,
    create_customer_strategy_agent,
    create_marketing_strategy_agent,
    create_brand_guidelines_agent
)
from agents.strategy_agent.utils import initialize_firestore as utils_init_firestore
from agents.strategy_agent.context import initialize_firestore as context_init_firestore

logger = logging.getLogger(__name__)

# Initialize W&B if available
try:
    import os
    import wandb
    import weave
    
    # Try to get W&B API key from environment
    wandb_api_key = os.getenv("WANDB_API_KEY")
    if wandb_api_key:
        wandb.login(key=wandb_api_key)
        logger.info("W&B authenticated with API key from environment")
    
    weave.init(project_name="ken-e-strategy-agent")
    logger.info("W&B observability initialized in strategy supervisor")
except Exception as e:
    logger.warning(f"W&B initialization skipped: {e}")


def parse_strategy_request(message: str) -> Dict[str, Any]:
    """
    Parse the strategy generation request message to extract parameters.
    """
    params = {
        'project_id': None,
        'company_name': None,
        'websites': [],
        'industry': None,
        'customer_regions': [],
        'annual_ad_budget': 0.0,
        'account_id': None,
        'user_id': None
    }
    
    # Parse the NEW INFORMATION section
    if "NEW INFORMATION:" in message:
        lines = message.split('\n')
        for line in lines:
            if line.startswith("Project ID:"):
                params['project_id'] = line.replace("Project ID:", "").strip()
            elif line.startswith("Account ID:"):
                params['account_id'] = line.replace("Account ID:", "").strip()
            elif line.startswith("Company to analyze:"):
                params['company_name'] = line.replace("Company to analyze:", "").strip()
            elif line.startswith("Company websites:"):
                websites_str = line.replace("Company websites:", "").strip()
                params['websites'] = [w.strip() for w in websites_str.strip('[]').split(',')]
            elif line.startswith("Industry:"):
                params['industry'] = line.replace("Industry:", "").strip()
            elif line.startswith("Customer regions:"):
                regions_str = line.replace("Customer regions:", "").strip()
                params['customer_regions'] = [r.strip() for r in regions_str.split(',')]
            elif line.startswith("Annual advertising budget:"):
                budget_str = line.replace("Annual advertising budget:", "").replace("$", "").replace(",", "").strip()
                try:
                    params['annual_ad_budget'] = float(budget_str)
                except:
                    params['annual_ad_budget'] = 0.0
    
    return params


def generate_strategy_documents(
    project_id: str,
    company_name: str,
    websites: Optional[list] = None,
    industry: Optional[str] = None,
    customer_regions: Optional[list] = None,
    annual_ad_budget: float = 0.0,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> str:
    """
    Generate all 5 strategy documents using the V3 Sequential Agent.
    
    This function is designed to be called as a tool by the supervisor agent.
    All imports are already done at module level.
    """
    logger.info(f"[STRATEGY] Starting generation for {company_name}")
    
    # Validate required parameters
    if not project_id:
        error_msg = "Project ID is required for strategy generation"
        logger.error(error_msg)
        return error_msg
    
    if not company_name:
        error_msg = "Company name is required for strategy generation"
        logger.error(error_msg)
        return error_msg
    
    # Initialize Firestore clients with the project_id
    try:
        utils_init_firestore(project_id)
        context_init_firestore(project_id)
        logger.info(f"Initialized Firestore clients with project: {project_id}")
    except Exception as e:
        error_msg = f"Failed to initialize Firestore: {e}"
        logger.error(error_msg)
        return error_msg
    
    # Create strategy context
    context = StrategyContext(
        project_id=project_id,
        account_id=account_id or str(uuid.uuid4()),
        user_id=user_id or "system",
        company_name=company_name,
        websites=websites or [],
        industry=industry or "General",
        customer_regions=customer_regions or [],
        annual_ad_budget=annual_ad_budget
    )
    
    logger.info(f"Creating V3 SequentialAgent for {company_name} in {industry} industry")
    
    try:
        # Create all 5 strategy agents
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
        
        logger.info(f"[EXECUTION] Starting SequentialAgent execution for {company_name}")
        
        # Execute the sequential agent with required parameters
        # Using InMemorySessionService for simplicity
        session_service = InMemorySessionService()
        
        # Create the session first
        app_name = f"strategy_gen_{account_id}"
        session_user_id = user_id or "system"
        session_id = f"session_{account_id}"
        
        # Create session before using it
        session = session_service.create_session_sync(
            app_name=app_name,
            user_id=session_user_id,
            session_id=session_id,
            state={}  # Initial empty state
        )
        logger.info(f"[EXECUTION] Created session: {session_id}")
        
        runner = Runner(
            agent=strategy_sequential_agent,
            app_name=app_name,
            session_service=session_service
        )
        execution_input = f"Generate all 5 strategy documents for {company_name} in the {industry} industry."
        
        # Create a proper Content object for the message
        message_content = Content(
            role='user',
            parts=[{'text': execution_input}]
        )
        
        # Run with required named parameters
        events = runner.run(
            user_id=session_user_id,
            session_id=session_id,
            new_message=message_content
        )
        
        # Process events from the generator and collect documents
        generated_documents = {}
        event_count = 0
        for event in events:
            event_count += 1
            # Log key event attributes
            event_info = f"[EXECUTION] Event #{event_count}"
            if hasattr(event, 'author'):
                event_info += f" author='{event.author}'"
            else:
                event_info += " NO_AUTHOR"
            if hasattr(event, 'actions'):
                event_info += " has_actions"
            logger.info(event_info)
            
            # Try to extract documents from the event
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                    state_delta = event.actions.state_delta
                    
                    # Log what's in state_delta
                    logger.info(f"[STATE_DELTA] Keys in state_delta: {list(state_delta.keys())}")
                    
                    # Check all keys to see what agents are outputting
                    for key in state_delta.keys():
                        value = state_delta[key]
                        if value:
                            if isinstance(value, str):
                                logger.info(f"[STATE_DELTA] {key}: string with {len(value)} chars")
                                if len(value) > 0 and len(value) < 100:
                                    logger.info(f"[STATE_DELTA] {key} content: {value}")
                            elif isinstance(value, dict):
                                logger.info(f"[STATE_DELTA] {key}: dict with keys {list(value.keys())[:5]}")
                            else:
                                logger.info(f"[STATE_DELTA] {key}: {type(value)}")
                    
                    # Look for updated_strategy_doc in state_delta
                    if 'updated_strategy_doc' in state_delta:
                        doc_content = state_delta['updated_strategy_doc']
                        
                        # Parse the document if it's a JSON string
                        if isinstance(doc_content, str):
                            # Remove markdown code blocks if present
                            doc_content = doc_content.strip()
                            if doc_content.startswith('```json'):
                                doc_content = doc_content[7:]  # Remove ```json
                            if doc_content.endswith('```'):
                                doc_content = doc_content[:-3]  # Remove ```
                            
                            try:
                                import json
                                import re
                                
                                # Clean the JSON string before parsing
                                # Remove any stray backslashes that aren't part of valid escape sequences
                                cleaned_content = doc_content.strip()
                                
                                # Fix common JSON issues
                                # Replace single backslashes that aren't part of valid escape sequences
                                # Valid escapes are: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
                                cleaned_content = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned_content)
                                
                                # Log if we had to clean anything
                                if cleaned_content != doc_content.strip():
                                    logger.warning(f"[DOCUMENT] Had to clean JSON - fixed invalid escape sequences")
                                
                                parsed_doc = json.loads(cleaned_content)
                                
                                # Determine document type from author
                                doc_type = None
                                if hasattr(event, 'author'):
                                    author = event.author
                                    logger.info(f"[DOCUMENT] Checking author field: '{author}'")
                                    
                                    # Make case-insensitive comparison
                                    author_lower = author.lower()
                                    
                                    if 'business' in author_lower:
                                        doc_type = 'business_strategy'
                                    elif 'competitive' in author_lower:
                                        doc_type = 'competitive_strategy'
                                    elif 'customer' in author_lower:
                                        doc_type = 'customer_strategy'
                                    elif 'marketing' in author_lower:
                                        doc_type = 'marketing_strategy'
                                    elif 'brand' in author_lower:
                                        doc_type = 'brand_guidelines'
                                    else:
                                        logger.warning(f"[DOCUMENT] Author '{author}' didn't match any document type")
                                else:
                                    logger.warning(f"[DOCUMENT] Event has no author field! Cannot determine doc type.")
                                
                                # Save the document if we determined its type
                                if doc_type and parsed_doc:
                                    generated_documents[doc_type] = parsed_doc
                                    author_name = event.author if hasattr(event, 'author') else 'unknown'
                                    logger.info(f"[DOCUMENT] Captured {doc_type} from {author_name}")
                                    
                                    # Save to Firestore immediately using sync version
                                    try:
                                        from agents.strategy_agent.utils import save_strategy_document_sync
                                        
                                        # Use the synchronous save function
                                        result = save_strategy_document_sync(
                                            account_id=account_id,
                                            doc_type=doc_type,
                                            content=parsed_doc,
                                            user_id=user_id
                                        )
                                        
                                        if result:
                                            logger.info(f"[FIRESTORE] Successfully saved {doc_type} to Firestore")
                                        else:
                                            logger.error(f"[FIRESTORE] Failed to save {doc_type} to Firestore")
                                    except Exception as e:
                                        logger.error(f"[FIRESTORE] Error saving {doc_type}: {e}")
                                            
                            except json.JSONDecodeError as e:
                                logger.error(f"[DOCUMENT] Failed to parse JSON: {e}")
                                # Log the problematic section of JSON around the error position
                                if hasattr(e, 'pos'):
                                    start = max(0, e.pos - 50)
                                    end = min(len(doc_content), e.pos + 50)
                                    logger.error(f"[DOCUMENT] JSON around error position {e.pos}:")
                                    logger.error(f"[DOCUMENT] ...{repr(doc_content[start:end])}...")
                                    
                                    # Try to identify the specific issue
                                    if e.pos > 0 and e.pos < len(doc_content):
                                        char_at_pos = doc_content[e.pos - 1:e.pos + 1]
                                        logger.error(f"[DOCUMENT] Character at error position: {repr(char_at_pos)}")
        
        logger.info(f"[EXECUTION] Completed strategy generation for {company_name}")
        logger.info(f"[EXECUTION] Generated documents: {list(generated_documents.keys())}")
        
        return f"Successfully generated {len(generated_documents)} strategy documents for {company_name}: {', '.join(generated_documents.keys())}"
        
    except Exception as e:
        error_msg = f"Failed to generate strategy documents: {e}"
        logger.error(error_msg)
        return error_msg


# Create the strategy supervisor agent
strategy_supervisor = Agent(
    name="strategy_supervisor",
    model="gemini-2.0-flash",
    instruction="""You are a strategy generation supervisor that coordinates the creation of marketing strategy documents.

When you receive a request to generate strategy documents:
1. Parse the request to extract all required information
2. Use the generate_strategy_documents tool to create the documents
3. Report the results back to the user

The request will contain:
- Project ID (required)
- Company name (required)
- Company websites
- Industry
- Customer regions
- Annual advertising budget

You must extract all these parameters and pass them to the generate_strategy_documents tool.""",
    tools=[generate_strategy_documents]
)

# Create the root_agent alias that ADK expects
root_agent = strategy_supervisor

# Create the app for deployment
app = reasoning_engines.AdkApp(
    agent=strategy_supervisor,
    enable_tracing=True
)

# Export for use
__all__ = ['strategy_supervisor', 'root_agent', 'app', 'generate_strategy_documents']