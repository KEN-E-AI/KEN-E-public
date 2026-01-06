"""
Shared utilities for supervisor agents.
Extracted from create_strategy_docs_supervisor.py to promote reuse.
"""

import asyncio
import concurrent.futures
import functools
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional, Tuple, Union

from google.adk import Runner
from google.adk.agents import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

logger = logging.getLogger(__name__)


def extract_tenant_context(input_data: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
    """
    Extract tenant context from various input formats.

    Expected formats:
    1. String: "message"
    2. Dict: {"message": "...", "tenant_id": "...", "tenant_credentials": "...", "selected_property_ids": [...]}
    3. Dict: {"query": "...", "tenant_id": "...", "tenant_credentials": "..."}

    Returns: (tenant_id, tenant_context_dict, message)
    """
    tenant_id = None
    tenant_context = None
    message = ""

    if isinstance(input_data, str):
        message = input_data
    elif isinstance(input_data, dict):
        # Extract message
        message = input_data.get("message", input_data.get("query", str(input_data)))

        # Extract tenant context (including credentials and property IDs)
        tenant_id = input_data.get("tenant_id")
        tenant_credentials = input_data.get("tenant_credentials")

        if tenant_id or tenant_credentials:
            tenant_context = {
                "tenant_id": tenant_id,
                "tenant_credentials": tenant_credentials,
            }

            # Include property IDs if provided
            if "selected_property_ids" in input_data:
                tenant_context["selected_property_ids"] = input_data["selected_property_ids"]
            if "selected_properties" in input_data:
                tenant_context["selected_properties"] = input_data["selected_properties"]
            if "default_property_id" in input_data:
                tenant_context["default_property_id"] = input_data["default_property_id"]
    else:
        message = str(input_data)

    return tenant_id, tenant_context, message


def invoke_agent_sync(
    agent: Agent,
    query: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Synchronous wrapper for agent invocation with proper async handling.
    Following ADK best practices from the codebase.
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
            artifact_service=artifact_service,
        )

        await session_service.create_session(
            app_name=agent.name, user_id=user_id, session_id=session_id
        )

        user_message = Content(role="user", parts=[Part.from_text(text=query)])

        response_text = ""
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_message
        ):
            # Follow ADK's official pattern
            if event.content and event.content.parts:
                if text := "".join(part.text or "" for part in event.content.parts):
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
                # Increased timeout to 30 minutes for complex operations
                return future.result(timeout=1800)  # 30 minute timeout
        else:
            # If no event loop is running, create one
            return loop.run_until_complete(invoke_agent())
    except concurrent.futures.TimeoutError as e:
        logger.error(f"Agent invocation timed out after 30 minutes: {e!s}")
        return "Error: Request timed out after 30 minutes. Please try again with simpler requirements."
    except Exception as e:
        logger.error(f"Error in sync agent invocation: {e!s}")
        return f"Error: Failed to complete the request - {e!s}"


def dispatch_with_context(dispatch_func: Callable) -> Callable[[str], str]:
    """Wrapper to extract tenant context from the full input"""

    @functools.wraps(dispatch_func)
    def wrapper(query: str, **kwargs) -> str:
        print(f"[DISPATCH-WRAPPER] Tool called: {dispatch_func.__name__}")
        print(f"[DISPATCH-WRAPPER] Input length: {len(query)} chars")
        print(f"[DISPATCH-WRAPPER] Input preview: {query[:200]}")
        print(f"[DISPATCH-WRAPPER] kwargs: {list(kwargs.keys()) if kwargs else 'none'}")
        logger.info(f"[DISPATCH-WRAPPER] Tool called: {dispatch_func.__name__}")
        logger.info(f"[DISPATCH-WRAPPER] Input length: {len(query)} chars")
        logger.info(f"[DISPATCH-WRAPPER] Input preview: {query[:200]}")
        logger.info(f"[DISPATCH-WRAPPER] kwargs: {list(kwargs.keys()) if kwargs else 'none'}")

        # Try to parse as JSON first (for structured input from web service)
        try:
            input_data = json.loads(query)
            tenant_id, tenant_context, message = extract_tenant_context(input_data)
            print(f"[DISPATCH-WRAPPER] Successfully parsed JSON")
            print(f"[DISPATCH-WRAPPER] Extracted message length: {len(message)}")
            print(f"[DISPATCH-WRAPPER] Tenant context: {tenant_context}")
            logger.info(
                f"[DISPATCH-WRAPPER] Parsed JSON input, extracted message length: {len(message)}"
            )
            if tenant_context:
                logger.info(f"[DISPATCH-WRAPPER] Tenant context keys: {list(tenant_context.keys())}")
            result = dispatch_func(message, tenant_context)
            # Return just the result string, not the full dict
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return str(result)
        except json.JSONDecodeError:
            # Fall back to string input
            logger.info("[DISPATCH-WRAPPER] Using raw string input")
            result = dispatch_func(query, None)
            # Return just the result string, not the full dict
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return str(result)

    return wrapper
