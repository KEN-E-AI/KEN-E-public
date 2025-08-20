"""
Main strategy agent module that handles strategy document creation and updates.
"""

import json
import logging
import os
from typing import Dict, Any, Optional, Tuple
import uuid
import asyncio
import concurrent.futures
from datetime import datetime

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai.types import Content, Part

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sub_agents import strategy_agent as iterative_strategy_agent
from models import StrategyRequest, StrategyDocument
# Simple, self-contained observability without external dependencies
import weave
import wandb
import os

def setup_local_weave():
    """Initialize Weave with environment variables."""
    api_key = os.getenv('WANDB_API_KEY')
    project = os.getenv('WEAVE_PROJECT_NAME', 'ken-e-strategy-agent')
    
    # Debug logging for deployment using proper logger
    logger.info(f"DEBUG: WANDB_API_KEY present: {bool(api_key)}")
    logger.info(f"DEBUG: WEAVE_PROJECT_NAME: {project}")
    
    if api_key:
        try:
            weave.init(project)
            logger.info(f"DEBUG: Weave initialization successful for project: {project}")
            return project
        except Exception as e:
            logger.error(f"DEBUG: Weave initialization failed: {e}")
            logger.warning(f"Weave initialization failed: {e}")
    else:
        logger.warning("DEBUG: WANDB_API_KEY not found in environment")
    return None

def track_agent_operation(agent_name, operation, sanitize=True):
    """Simple decorator for tracking agent operations."""
    def decorator(func):
        @weave.op()
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

logger = logging.getLogger(__name__)

# Test log message to verify logging is working
logger.warning("STRATEGY AGENT MODULE LOADED - This should appear in logs")

# Initialize Weave tracing lazily to avoid build-time issues
weave_project = None

def _ensure_observability():
    """Lazily initialize observability components."""
    global weave_project
    if weave_project is None:
        weave_project = setup_local_weave()
        if weave_project:
            logger.info(f"Weave tracing enabled for project: {weave_project}")
    return weave_project


def extract_strategy_context(input_data: Any) -> Tuple[Optional[str], Optional[str], str, Optional[Dict]]:
    """
    Extract strategy context from various input formats.
    
    Returns: (account_id, user_id, message, strategy_params)
    """
    account_id = None
    user_id = None
    message = ""
    strategy_params = None
    
    if isinstance(input_data, str):
        message = input_data
    elif isinstance(input_data, dict):
        # Extract message
        message = input_data.get('message', input_data.get('query', str(input_data)))
        
        # Extract context
        account_id = input_data.get('account_id')
        user_id = input_data.get('user_id')
        
        # Extract strategy-specific parameters
        strategy_params = {
            'doc_type': input_data.get('doc_type', 'business_strategy'),
            'existing_document': input_data.get('existing_document'),
            'best_practices': input_data.get('best_practices'),
            'reviewer_guidelines': input_data.get('reviewer_guidelines'),
            'new_information': input_data.get('new_information'),
            'max_iterations': input_data.get('max_iterations', 3)
        }
    else:
        message = str(input_data)
    
    return account_id, user_id, message, strategy_params


@track_agent_operation("strategy_agent", "invoke", sanitize=True)
async def invoke_strategy_agent(
    query: str,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None,
    strategy_params: Optional[Dict] = None
) -> str:
    """
    Invoke the iterative strategy agent with proper context.
    
    Args:
        query: The user's request for strategy creation/update
        account_id: Account ID for document scoping
        user_id: User ID for attribution
        strategy_params: Additional parameters for strategy creation
        
    Returns:
        The final strategy document or error message
    """
    if user_id is None:
        user_id = f"strategy_user_{uuid.uuid4().hex[:8]}"
    
    session_id = f"strategy_session_{uuid.uuid4().hex[:8]}"
    
    # Ensure observability is initialized
    logger.info(f"DEBUG: Initializing strategy agent for query: {query[:50]}...")
    weave_status = _ensure_observability()
    logger.info(f"DEBUG: Weave project status: {weave_status}")
    
    try:
        # Initialize services
        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()
        
        # Create runner
        runner = Runner(
            agent=iterative_strategy_agent,
            app_name=iterative_strategy_agent.name,
            session_service=session_service,
            artifact_service=artifact_service
        )
        
        # Create session
        await session_service.create_session(
            app_name=iterative_strategy_agent.name,
            user_id=user_id,
            session_id=session_id
        )
        
        # Prepare message parts
        message_parts = [Part.from_text(text=query)]
        
        # Add strategy parameters if provided
        if strategy_params:
            # Add existing document if available
            if strategy_params.get('existing_document'):
                message_parts.append(Part.from_text(
                    text=f"THE EXISTING STRATEGY DOCUMENT FOR YOU TO MODIFY: {strategy_params['existing_document']}"
                ))
            else:
                message_parts.append(Part.from_text(
                    text="No strategy document has been created yet. Your task is to create a new one."
                ))
            
            # Add best practices
            if strategy_params.get('best_practices'):
                message_parts.append(Part.from_text(
                    text=f"BEST PRACTICES: {strategy_params['best_practices']}"
                ))
            
            # Add reviewer guidelines
            if strategy_params.get('reviewer_guidelines'):
                message_parts.append(Part.from_text(
                    text=f"REVIEWER GUIDELINES: {strategy_params['reviewer_guidelines']}"
                ))
            
            # Add new information
            if strategy_params.get('new_information'):
                message_parts.append(Part.from_text(
                    text=f"NEW INFORMATION: {strategy_params['new_information']}"
                ))
        
        # Create user message
        user_message = Content(
            role="user",
            parts=message_parts
        )
        
        # Run the agent
        response_text = ""
        total_prompt_tokens = 0
        total_response_tokens = 0
        start_time = datetime.utcnow()
        
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message
        ):
            # Track token usage
            if hasattr(event, 'usage_metadata') and event.usage_metadata:
                if hasattr(event.usage_metadata, 'prompt_token_count'):
                    total_prompt_tokens += event.usage_metadata.prompt_token_count or 0
                if hasattr(event.usage_metadata, 'candidates_token_count'):
                    total_response_tokens += event.usage_metadata.candidates_token_count or 0
            
            # Accumulate text responses
            if event.content and event.content.parts:
                if text := ''.join(part.text or '' for part in event.content.parts):
                    response_text += text
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Track token usage and costs (disabled for now)
        # if total_prompt_tokens > 0 or total_response_tokens > 0:
        #     track_token_usage(
        #         agent_name="strategy_agent",
        #         user_id=user_id or "unknown",
        #         account_id=account_id or "unknown",
        #         prompt_tokens=total_prompt_tokens,
        #         response_tokens=total_response_tokens,
        #         model="gemini-1.5-pro-002",
        #         operation="strategy_generation"
        #     )
        
        # Log completion
        logger.info(
            f"Strategy agent completed for account: {account_id}, user: {user_id}, "
            f"tokens: {total_prompt_tokens + total_response_tokens}, time: {execution_time:.2f}s"
        )
        
        return response_text
        
    except Exception as e:
        logger.error(f"Error in strategy agent invocation: {str(e)}")
        return f"Error creating/updating strategy: {str(e)}"


@track_agent_operation("strategy_agent", "invoke_sync", sanitize=True)
def invoke_strategy_agent_sync(
    query: str,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None,
    strategy_params: Optional[Dict] = None
) -> str:
    """
    Synchronous wrapper for strategy agent invocation.
    """
    async def run_async():
        return await invoke_strategy_agent(query, account_id, user_id, strategy_params)
    
    try:
        # Handle event loop scenarios
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, use ThreadPoolExecutor
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, run_async())
                return future.result(timeout=600)  # 10 minute timeout for strategy creation
        else:
            # If no event loop is running, create one
            return loop.run_until_complete(run_async())
    except Exception as e:
        logger.error(f"Error in sync strategy agent invocation: {str(e)}")
        return f"Error invoking strategy agent: {str(e)}"


# Export the main agent
strategy_agent = iterative_strategy_agent