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
from collections.abc import Callable
from typing import Any

try:
    import weave

    HAS_WEAVE = True
except ImportError:
    weave = None  # type: ignore[assignment]
    HAS_WEAVE = False
from google.adk import Runner
from google.adk.agents import Agent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext
from google.genai.types import Content, Part

from .context_loader import HierarchicalContextManager

logger = logging.getLogger(__name__)


def extract_tenant_context(
    input_data: Any,
) -> tuple[str | None, dict[str, Any] | None, str]:
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

        # Extract tenant context (including credentials, property IDs, and account_id)
        tenant_id = input_data.get("tenant_id")
        tenant_credentials = input_data.get("tenant_credentials")
        account_id = input_data.get("account_id")

        if tenant_id or tenant_credentials or account_id:
            tenant_context = {
                "tenant_id": tenant_id,
                "tenant_credentials": tenant_credentials,
            }

            # Include account_id if provided (for organization context loading)
            if account_id:
                tenant_context["account_id"] = account_id

            # Include property IDs if provided
            if "selected_property_ids" in input_data:
                tenant_context["selected_property_ids"] = input_data[
                    "selected_property_ids"
                ]
            if "selected_properties" in input_data:
                tenant_context["selected_properties"] = input_data[
                    "selected_properties"
                ]
            if "default_property_id" in input_data:
                tenant_context["default_property_id"] = input_data[
                    "default_property_id"
                ]
    else:
        message = str(input_data)

    return tenant_id, tenant_context, message


def invoke_agent_sync(
    agent: Agent,
    query: str,
    user_id: str | None = None,
    session_id: str | None = None,
    state: dict[str, Any] | None = None,
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
            app_name=agent.name, user_id=user_id, session_id=session_id, state=state
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
            executor_cls = weave.ThreadPoolExecutor if HAS_WEAVE else concurrent.futures.ThreadPoolExecutor
            with executor_cls() as executor:
                future = executor.submit(asyncio.run, invoke_agent())
                return future.result(timeout=300)
        else:
            # If no event loop is running, create one
            return loop.run_until_complete(invoke_agent())
    except concurrent.futures.TimeoutError as e:
        logger.error(f"Agent invocation timed out after 5 minutes: {e!s}")
        return "Error: Request timed out after 5 minutes. Please try again with simpler requirements."
    except Exception as e:
        logger.error(f"Error in sync agent invocation: {e!s}")
        return f"Error: Failed to complete the request - {e!s}"


def dispatch_with_context(dispatch_func: Callable) -> Callable[[str], str]:
    """Wrapper to extract tenant context from session state or fallback to message parsing.

    This wrapper:
    1. Checks for ToolContext (ADK auto-injects this)
    2. Reads account_id and GA credentials from tool_context.state
    3. Loads organization context from Neo4j using account_id
    4. Builds tenant_context for specialized agents (with credentials)
    5. Injects organization context into the message
    6. Falls back to JSON parsing for backward compatibility
    """

    @functools.wraps(dispatch_func)
    def wrapper(query: str, tool_context: ToolContext | None = None, **kwargs) -> str:
        logger.info("[DISPATCH-WRAPPER] ========== TOOL CALL START ==========")
        logger.info(f"[DISPATCH-WRAPPER] Tool called: {dispatch_func.__name__}")
        logger.info(f"[DISPATCH-WRAPPER] Query length: {len(query)} chars")
        logger.info(f"[DISPATCH-WRAPPER] Query preview: {query[:200]}")
        logger.info(f"[DISPATCH-WRAPPER] tool_context present: {tool_context is not None}")
        logger.info(f"[DISPATCH-WRAPPER] tool_context type: {type(tool_context)}")
        logger.info(f"[DISPATCH-WRAPPER] kwargs keys: {list(kwargs.keys()) if kwargs else []}")

        # CRITICAL DEBUG: Log if tool_context exists and what's in its state
        if tool_context:
            logger.info("[DISPATCH-WRAPPER] ✅ ToolContext received!")
            logger.info(f"[DISPATCH-WRAPPER] State keys: {list(tool_context.state.keys()) if hasattr(tool_context, 'state') else 'no state attr'}")
            if hasattr(tool_context, 'state'):
                logger.info(f"[DISPATCH-WRAPPER] Full state: {tool_context.state}")
        else:
            logger.warning("[DISPATCH-WRAPPER] ⚠️  NO ToolContext - will use fallback")
        logger.info("[DISPATCH-WRAPPER] ========== TOOL CALL INFO END ==========")

        # Initialize variables
        account_id = None
        ga_credentials = None
        tenant_context = None

        # Strategy 1: Read from session state (preferred method)
        if tool_context:
            account_id = tool_context.state.get("account_id")
            ga_credentials = tool_context.state.get("ga_credentials")
            logger.info("[DISPATCH-WRAPPER] Retrieved from session state:")
            logger.info(f"  - account_id: {account_id}")
            logger.info(f"  - ga_credentials: {'present' if ga_credentials else 'none'}")

            # Build tenant_context from session state
            # Credentials flow via McpToolset header_provider (no encoding needed)
            if ga_credentials:
                tenant_context = {
                    "tenant_id": ga_credentials.get("tenant_id"),
                    "selected_property_ids": ga_credentials.get(
                        "selected_property_ids", []
                    ),
                    "selected_properties": ga_credentials.get("selected_properties", []),
                    "account_id": account_id,
                }
                logger.info(
                    f"[DISPATCH-WRAPPER] Built tenant_context from session state with {len(ga_credentials.get('selected_property_ids', []))} properties"
                )
            elif account_id:
                # For non-GA queries, still pass account_id
                tenant_context = {"account_id": account_id}
                logger.info(
                    "[DISPATCH-WRAPPER] Built minimal tenant_context with account_id only"
                )

            # Inject organization context: prefer session state, fallback to Neo4j
            if account_id:
                try:
                    org_context = tool_context.state.get("organization_context")
                    if org_context:
                        from shared.context_utils import inject_organization_context
                        query = inject_organization_context(query, org_context)
                        logger.info(
                            f"[DISPATCH-WRAPPER] Org context injected from session state, length: {len(query)}"
                        )
                    else:
                        # Fallback: load from Neo4j (standalone invocations or missing state)
                        logger.info(
                            "[DISPATCH-WRAPPER] No org context in session state, falling back to Neo4j"
                        )
                        context_manager = HierarchicalContextManager(account_id)
                        neo4j_context = context_manager.load_executive_summary()
                        if neo4j_context:
                            query = context_manager.inject_context(query)
                            logger.info(
                                f"[DISPATCH-WRAPPER] Org context injected from Neo4j, length: {len(query)}"
                            )
                except Exception as e:
                    logger.error(
                        f"[DISPATCH-WRAPPER] Failed to load org context: {e}",
                        exc_info=True,
                    )

        # Strategy 2: Fallback to JSON parsing (backward compatibility)
        else:
            logger.info(
                "[DISPATCH-WRAPPER] No tool_context - trying JSON parsing fallback"
            )
            try:
                input_data = json.loads(query)
                _tenant_id, tenant_context, message = extract_tenant_context(input_data)
                logger.info(
                    f"[DISPATCH-WRAPPER] Parsed JSON, extracted message length: {len(message)}"
                )

                # Load organization context if account_id present in JSON
                if tenant_context and tenant_context.get("account_id"):
                    try:
                        logger.info(
                            f"[DISPATCH-WRAPPER] Loading org context for: {tenant_context['account_id']}"
                        )
                        context_manager = HierarchicalContextManager(
                            tenant_context["account_id"]
                        )
                        org_context = context_manager.load_executive_summary()
                        if org_context:
                            message = context_manager.inject_context(message)
                            logger.info(
                                f"[DISPATCH-WRAPPER] Org context injected (JSON path), new length: {len(message)}"
                            )
                    except Exception as e:
                        logger.error(
                            f"[DISPATCH-WRAPPER] Failed to load org context: {e}",
                            exc_info=True,
                        )

                # Use extracted message instead of original query
                query = message
            except json.JSONDecodeError:
                logger.info("[DISPATCH-WRAPPER] Using raw string input (not JSON)")

                # Check kwargs for tenant_context (old pattern)
                if "tenant_context" in kwargs:
                    tenant_context = kwargs["tenant_context"]
                    logger.info(
                        f"[DISPATCH-WRAPPER] Found tenant_context in kwargs: {list(tenant_context.keys()) if tenant_context else 'none'}"
                    )

        # Call dispatch function with context
        result = dispatch_func(query, tenant_context)

        # Return just the result string, not the full dict
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return str(result)

    return wrapper
