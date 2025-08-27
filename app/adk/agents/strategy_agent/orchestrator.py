#!/usr/bin/env python3
"""
Strategy Agent Orchestrator - Manages execution and persistence of strategy documents.
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from google.adk.agents import Agent, SequentialAgent
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content
from vertexai.preview import reasoning_engines

# Import strategy components
try:
    # Absolute imports for deployment
    from agents.strategy_agent.models import StrategyContext
    from agents.strategy_agent.agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent
    )
    from agents.strategy_agent.firestore import (
        FirestoreClient,
        save_strategy_document_sync,
        get_strategy_document,
        update_strategy_document
    )
except ImportError:
    # Relative imports for local testing
    from .models import StrategyContext
    from .agents import (
        create_business_strategy_agent,
        create_competitive_strategy_agent,
        create_customer_strategy_agent,
        create_marketing_strategy_agent,
        create_brand_guidelines_agent
    )
    from .firestore import (
        FirestoreClient,
        save_strategy_document_sync,
        get_strategy_document,
        update_strategy_document
    )

logger = logging.getLogger(__name__)

# Initialize W&B observability if available
try:
    import weave
    weave.init(project_name="ken-e-strategy-agent")
    logger.info("W&B observability initialized")
except Exception as e:
    logger.warning(f"W&B initialization skipped: {e}")


# Define the mapping of output keys to document types
DOCUMENT_KEY_MAPPING = {
    'business_strategy_doc': 'business_strategy',
    'competitive_strategy_doc': 'competitive_strategy',
    'customer_strategy_doc': 'customer_strategy',
    'marketing_strategy_doc': 'marketing_strategy',
    'brand_guidelines_doc': 'brand_guidelines'
}


def create_strategy_sequential_agent(context: StrategyContext) -> SequentialAgent:
    """
    Create the sequential agent with all 5 strategy sub-agents.
    
    Args:
        context: StrategyContext with company information
        
    Returns:
        SequentialAgent that runs all 5 strategy agents in sequence
    """
    logger.info(f"Creating Sequential Agent for {context.company_name}")
    
    # Create all 5 strategy agents in order
    business_agent = create_business_strategy_agent(context)
    competitive_agent = create_competitive_strategy_agent(context)
    customer_agent = create_customer_strategy_agent(context)
    marketing_agent = create_marketing_strategy_agent(context)
    brand_agent = create_brand_guidelines_agent(context)
    
    # Chain them together in a SequentialAgent
    strategy_sequential_agent = SequentialAgent(
        name="strategy_generator",
        sub_agents=[
            business_agent,
            competitive_agent,
            customer_agent,
            marketing_agent,
            brand_agent
        ],
        description="Generates all 5 strategy documents in sequence"
    )
    
    logger.info(f"✅ Sequential Agent created with 5 strategy agents for {context.company_name}")
    return strategy_sequential_agent


def execute_strategy_generation(
    company_name: str,
    industry: str,
    websites: str,
    customer_regions: str,
    account_id: str,
    user_id: str,
    annual_ad_budget: float = 0.0,
    project_id: Optional[str] = None,
    firestore_client: Optional[FirestoreClient] = None
) -> str:
    """
    Execute the complete strategy generation process.
    
    This function:
    1. Creates the strategy context
    2. Initializes the sequential agent
    3. Runs the agent pipeline
    4. Monitors execution and captures documents
    5. Saves documents to Firestore as they're generated
    
    Args:
        company_name: Name of the company
        industry: Industry sector
        websites: Comma-separated list of websites
        customer_regions: Comma-separated list of regions
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        annual_ad_budget: Annual advertising budget
        project_id: Optional GCP project ID
        
    Returns:
        Status message indicating success or failure
    """
    try:
        logger.info(f"[EXECUTION] Starting strategy generation for {company_name}")
        
        # Use provided client or create new one
        client = firestore_client or FirestoreClient(project_id=project_id)
        
        # Create context from inputs
        context = StrategyContext(
            account_id=account_id,
            user_id=user_id,
            company_name=company_name,
            websites=websites.split(',') if websites else [],
            industry=industry,
            customer_regions=customer_regions.split(',') if customer_regions else [],
            annual_ad_budget=annual_ad_budget
        )
        
        # Create the sequential agent with all 5 strategy agents
        strategy_sequential_agent = create_strategy_sequential_agent(context)
        
        # Set up session management
        session_service = InMemorySessionService()
        app_name = f"strategy_gen_{account_id}"
        session_user_id = user_id or "system"
        session_id = f"session_{account_id}_{uuid.uuid4().hex[:8]}"
        
        # Create session
        session = session_service.create_session_sync(
            app_name=app_name,
            user_id=session_user_id,
            session_id=session_id,
            state={}
        )
        logger.info(f"[EXECUTION] Created session: {session_id}")
        
        # Create runner
        runner = Runner(
            agent=strategy_sequential_agent,
            app_name=app_name,
            session_service=session_service
        )
        
        # Prepare execution message
        execution_input = f"Generate all 5 strategy documents for {company_name} in the {industry} industry."
        message_content = Content(
            role='user',
            parts=[{'text': execution_input}]
        )
        
        # Run the agent pipeline
        events = runner.run(
            user_id=session_user_id,
            session_id=session_id,
            new_message=message_content
        )
        
        # Process events and save documents
        generated_documents = process_and_save_documents(
            events, account_id, user_id, client
        )
        
        logger.info(f"[EXECUTION] Completed strategy generation for {company_name}")
        logger.info(f"[EXECUTION] Generated documents: {list(generated_documents.keys())}")
        
        return f"Successfully generated {len(generated_documents)} strategy documents for {company_name}: {', '.join(generated_documents.keys())}"
        
    except Exception as e:
        error_msg = f"Failed to generate strategy documents: {e}"
        logger.error(error_msg)
        return error_msg


def process_and_save_documents(
    events,
    account_id: str,
    user_id: str,
    firestore_client: FirestoreClient
) -> Dict[str, Any]:
    """
    Process execution events and save documents to Firestore.
    
    This function monitors the event stream from the agent execution,
    captures documents as they're generated, and saves them to Firestore.
    Now handles unique output keys for each document type.
    
    Args:
        events: Generator of execution events from Runner
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        firestore_client: Firestore client for saving documents
        
    Returns:
        Dictionary of generated documents
    """
    generated_documents = {}
    event_count = 0
    
    for event in events:
        event_count += 1
        
        # Log event details
        event_info = f"[EVENT #{event_count}]"
        if hasattr(event, 'author'):
            event_info += f" author='{event.author}'"
            
            # Log specific agent transitions
            if 'marketing_strategy_agent' in str(event.author):
                logger.info(f"[MARKETING AGENT] Event from marketing agent: {event.author}")
            elif 'brand_' in str(event.author):
                logger.info(f"[BRAND AGENT] Event from brand agent: {event.author}")
                
        logger.info(event_info)
        
        # Check for documents in state delta
        if hasattr(event, 'actions') and event.actions:
            if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                state_delta = event.actions.state_delta
                
                # Log all keys in state_delta for debugging
                if state_delta:
                    logger.info(f"[STATE_DELTA] Keys present: {list(state_delta.keys())[:10]}")  # Limit to first 10 keys
                
                # Check for each document type's unique key
                for doc_key, doc_type in DOCUMENT_KEY_MAPPING.items():
                    if doc_key in state_delta:
                        doc_content = state_delta[doc_key]
                        logger.info(f"[DOCUMENT] Found {doc_key} in state_delta for {doc_type}")
                        
                        # Parse the document
                        parsed_doc = parse_document_content(doc_content)
                        
                        if parsed_doc:
                            # Save to memory
                            generated_documents[doc_type] = parsed_doc
                            logger.info(f"[DOCUMENT] Captured {doc_type} from key {doc_key} - {len(json.dumps(parsed_doc))} bytes")
                            
                            # Save to Firestore immediately
                            try:
                                result = firestore_client.save_strategy_document_sync(
                                    account_id=account_id,
                                    doc_type=doc_type,
                                    content=parsed_doc,
                                    user_id=user_id
                                )
                                
                                if result:
                                    logger.info(f"[FIRESTORE] Successfully saved {doc_type}")
                                else:
                                    logger.error(f"[FIRESTORE] Failed to save {doc_type}")
                            except Exception as e:
                                logger.error(f"[FIRESTORE] Error saving {doc_type}: {e}")
                        else:
                            logger.error(f"[DOCUMENT] Failed to parse content for {doc_type} from key {doc_key}")
    
    return generated_documents


def parse_document_content(doc_content: Any) -> Optional[Dict]:
    """
    Parse document content from JSON string or dict.
    
    Args:
        doc_content: Raw document content (may be JSON string or dict)
        
    Returns:
        Parsed document dictionary or None if parsing fails
    """
    # If already a dict, return it
    if isinstance(doc_content, dict):
        return doc_content
    
    # If string, try to parse as JSON
    if isinstance(doc_content, str):
        doc_content = clean_json_string(doc_content)
        
        try:
            return json.loads(doc_content)
        except json.JSONDecodeError as e:
            logger.error(f"[DOCUMENT] Failed to parse JSON: {e}")
            return None
    
    # Unknown type
    logger.warning(f"[DOCUMENT] Unknown content type: {type(doc_content)}")
    return None


def clean_json_string(content: str) -> str:
    """
    Clean JSON string by removing markdown code blocks and fixing escape sequences.
    
    Args:
        content: Raw JSON string that may contain markdown or invalid escapes
        
    Returns:
        Cleaned JSON string
    """
    import re
    
    # Remove markdown code blocks if present
    content = content.strip()
    if content.startswith('```json'):
        content = content[7:]  # Remove ```json
    if content.endswith('```'):
        content = content[:-3]  # Remove ```
    
    # Fix common JSON issues
    # Replace single backslashes that aren't part of valid escape sequences
    # Valid escapes are: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', content.strip())
    
    return cleaned


# Create the main strategy agent for deployment
def create_strategy_agent_for_deployment():
    """
    Create a wrapper agent for deployment that handles strategy generation requests.
    """
    return Agent(
        name="strategy_orchestrator",
        model="gemini-2.0-flash",
        instruction="""You coordinate strategy document generation.
        
When you receive a request to generate strategy documents, you MUST use the execute_strategy_generation tool.

Look for messages that contain parameters like:
- company_name
- industry
- websites
- customer_regions
- account_id
- user_id
- annual_ad_budget
- project_id

Extract these parameters from the message and call execute_strategy_generation with them.

For example, if you receive:
"Please execute strategy generation with these parameters:
- company_name: Example Corp
- industry: Technology
- websites: example.com
- customer_regions: USA,Europe
- account_id: acc_123
- user_id: user_456
- annual_ad_budget: 100000
- project_id: ken-e-dev"

You should call execute_strategy_generation(
    company_name="Example Corp",
    industry="Technology", 
    websites="example.com",
    customer_regions="USA,Europe",
    account_id="acc_123",
    user_id="user_456",
    annual_ad_budget=100000.0,
    project_id="ken-e-dev"
)

ALWAYS use the execute_strategy_generation tool when asked to generate strategies.
Do NOT just respond with text - actually execute the tool.""",
        tools=[execute_strategy_generation]
    )


# Create the agent and app for deployment
strategy_agent = create_strategy_agent_for_deployment()

try:
    # Wrap with AdkApp for deployment
    app = reasoning_engines.AdkApp(
        agent=strategy_agent,
        enable_tracing=True
    )
    logger.info("✅ Strategy Agent ready for deployment")
except Exception as e:
    logger.error(f"Failed to create Strategy Agent app: {e}")
    app = None


__all__ = [
    'strategy_agent',
    'app',
    'create_strategy_sequential_agent',
    'execute_strategy_generation'
]