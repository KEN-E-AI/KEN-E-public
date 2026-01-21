"""
Dispatch handlers for routing to specialized agents.
"""

import logging
import os
import time
import uuid
from typing import Any

from google.adk.tools import ToolContext
from pydantic import ValidationError

from ..models.strategy_models import StrategyParameters, parse_strategy_query
from .agent_retry import invoke_agent_with_retry

logger = logging.getLogger(__name__)


def dispatch_to_company_news(
    query: str,
    tool_context: ToolContext | None = None,
    tenant_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    News agent doesn't need tenant context as it uses public data.

    Args:
        query: User's question about company news
        tool_context: ADK ToolContext with session state (auto-injected)
        tenant_context: Legacy parameter for backward compatibility
    """
    # Import here to avoid circular dependencies
    from ..company_news_chatbot.agent import root_agent as news_agent
    from .context_loader import inject_organization_context

    try:
        logger.info("[NEWS-DISPATCH] ========== DISPATCH START ==========")
        logger.info(f"[NEWS-DISPATCH] Query: {query[:200]}")
        logger.info(f"[NEWS-DISPATCH] tool_context present: {tool_context is not None}")

        # Extract account_id from session state
        account_id = None
        if tool_context and hasattr(tool_context, 'state'):
            account_id = tool_context.state.get("account_id")
            logger.info(f"[NEWS-DISPATCH] Retrieved account_id from session state: {account_id}")
        elif tenant_context:
            account_id = tenant_context.get("account_id")
            logger.info(f"[NEWS-DISPATCH] Retrieved account_id from tenant_context: {account_id}")

        # Inject pre-loaded organization context from session state
        # Context is loaded in API layer (which has Neo4j access) and stored in session state
        org_context = None
        if tool_context and hasattr(tool_context, 'state'):
            org_context = tool_context.state.get("organization_context")
            if org_context:
                query = inject_organization_context(query, org_context)
                logger.info(f"[NEWS-DISPATCH] ✅ Injected org context from session state, new query length: {len(query)}")
            else:
                logger.info("[NEWS-DISPATCH] No org context in session state")
        else:
            logger.info("[NEWS-DISPATCH] No tool_context available for org context")

        logger.info("🔄 Routing company news query to specialized agent...")
        # Use retry logic for robust agent invocation
        result = invoke_agent_with_retry(news_agent, query, max_attempts=3)

        return {
            "status": "success",
            "query": query,
            "result": result,
            "source": "company_news_specialist",
            "agent": "news",
        }
    except Exception as e:
        logger.error(f"Error in news agent dispatch: {e}")
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "source": "company_news_specialist",
            "agent": "news",
        }


def dispatch_to_google_analytics(
    query: str,
    tool_context: ToolContext | None = None,
    tenant_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Dispatch Google Analytics queries with tenant context from session state.

    Args:
        query: The Google Analytics query or question from the user
        tool_context: ADK ToolContext with session state (auto-injected by ADK)
        tenant_context: Legacy parameter for backward compatibility
    """
    # Import here to avoid circular dependencies
    from ..google_analytics_agent_v4 import google_analytics_agent_v4
    from .context_loader import inject_organization_context
    from .supervisor_utils import encode_ga_credentials

    try:
        logger.info("🔄 Routing Google Analytics query to specialized agent...")

        # Strategy 1: Extract from session state (preferred)
        account_id = None
        ga_credentials = None

        if tool_context and hasattr(tool_context, 'state'):
            account_id = tool_context.state.get("account_id")
            ga_credentials = tool_context.state.get("ga_credentials")
            logger.info(f"Retrieved credentials from session state for account: {account_id}")

            # Build tenant_context from session state
            if ga_credentials:
                selected_property_ids = ga_credentials.get("selected_property_ids", [])

                tenant_context = {
                    "tenant_id": ga_credentials["tenant_id"],
                    "tenant_credentials": encode_ga_credentials(ga_credentials),
                    "selected_property_ids": selected_property_ids,
                    "account_id": account_id,
                }
                # Set default property ID if only one property
                if len(selected_property_ids) == 1:
                    tenant_context["default_property_id"] = selected_property_ids[0]

                logger.info(f"Built tenant_context with {len(selected_property_ids)} properties")
        elif tenant_context:
            # Strategy 2: Fallback to passed tenant_context
            account_id = tenant_context.get("account_id")
            logger.info("Using tenant_context from parameter (fallback)")

        # Inject pre-loaded organization context from session state
        # Context is loaded in API layer (which has Neo4j access) and stored in session state
        org_context = None
        if tool_context and hasattr(tool_context, 'state'):
            org_context = tool_context.state.get("organization_context")
            if org_context:
                query = inject_organization_context(query, org_context)
                logger.info(f"Injected organization context, new query length: {len(query)}")

        # Fallback: use environment credentials for testing
        if not tenant_context or not tenant_context.get("tenant_credentials"):
            env_creds = os.getenv("GA_PERSONAL_CREDENTIALS")
            if env_creds:
                tenant_context = {
                    "tenant_id": os.getenv("GA_TENANT_ID", "test-org"),
                    "tenant_credentials": env_creds,
                }
                logger.info("Using test credentials from environment")

        # Prepare query with tenant context for GA agent
        if (
            tenant_context
            and tenant_context.get("tenant_id")
            and tenant_context.get("tenant_credentials")
        ):
            # Inject tenant context into the query for the GA agent
            enhanced_query = f"TENANT_ID:{tenant_context['tenant_id']} TENANT_CREDS:{tenant_context['tenant_credentials']}"

            # Include property IDs if available
            if tenant_context.get("default_property_id"):
                enhanced_query += f" PROPERTY_ID:{tenant_context['default_property_id']}"
            elif tenant_context.get("selected_property_ids"):
                property_ids = tenant_context['selected_property_ids']
                if len(property_ids) == 1:
                    enhanced_query += f" PROPERTY_ID:{property_ids[0]}"
                else:
                    enhanced_query += f" PROPERTY_IDS:{','.join(property_ids)}"

            enhanced_query += f" {query}"
        else:
            enhanced_query = query
            logger.warning("No credentials available for GA query")

        # Use retry logic for robust agent invocation
        result = invoke_agent_with_retry(
            google_analytics_agent_v4, enhanced_query, max_attempts=3
        )

        return {
            "status": "success",
            "query": query,
            "result": result,
            "source": "google_analytics_specialist",
            "agent": "analytics",
            "tenant_id": tenant_context.get("tenant_id") if tenant_context else None,
        }
    except Exception as e:
        logger.error(f"[GA-DISPATCH] Error in analytics agent dispatch: {e}")
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "source": "google_analytics_specialist",
            "agent": "analytics",
        }


def dispatch_to_strategy(
    query: str, tenant_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Dispatch strategy queries to the iterative strategy agent.
    Strategy agent needs account context for document persistence.
    """
    # Import here to avoid circular dependencies
    from ..strategy_agent.logging_config import StrategyAgentLogger
    from ..strategy_agent.orchestrator import execute_strategy_generation
    from ..strategy_agent.token_utils import check_and_log_tokens

    execution_id = str(uuid.uuid4())
    supervisor_logger = StrategyAgentLogger("strategy_dispatch")

    try:
        logger.info("🔄 [SUPERVISOR] Routing strategy query to specialized agent...")
        supervisor_logger.log_agent_start(
            execution_id=execution_id,
            input_tokens=len(query) // 4,  # Rough estimate
            context={"query_preview": query[:200], "tenant_context": tenant_context},
        )

        # Log the full query for debugging
        logger.info(f"[SUPERVISOR] Full query length: {len(query)} chars")
        logger.info(f"[SUPERVISOR] Query preview: {query[:500]}")

        # Check token usage
        check_and_log_tokens(
            query, "supervisor_strategy_dispatch", raise_on_exceed=False
        )

        # Parse the query string to extract parameters
        raw_params = parse_strategy_query(query)

        # Use tenant_context to fill in missing values
        if tenant_context:
            if "account_id" not in raw_params:
                raw_params["account_id"] = tenant_context.get(
                    "account_id"
                ) or tenant_context.get("tenant_id", "")
            if "user_id" not in raw_params:
                raw_params["user_id"] = tenant_context.get("user_id", "")
            if "project_id" not in raw_params:
                raw_params["project_id"] = tenant_context.get("project_id")

        # Validate and parse parameters using Pydantic
        try:
            params = StrategyParameters(**raw_params)
            logger.info("[SUPERVISOR] Successfully validated strategy parameters")
            supervisor_logger.log_token_usage(
                phase="parameter_validation",
                tokens={"params_validated": 1},
                percentage_of_limit=0.01,
            )
        except ValidationError as e:
            logger.warning(f"[SUPERVISOR] Parameter validation errors: {e.errors()}")
            # Try to create with defaults for missing required fields
            for error in e.errors():
                field = error["loc"][0]
                if error["type"] == "missing":
                    if field == "company_name":
                        raw_params[field] = "Unknown Company"
                    elif field == "industry":
                        raw_params[field] = "Unknown Industry"
                    elif field in ["account_id", "user_id"]:
                        raw_params[field] = "unknown"

            # Retry validation with defaults
            params = StrategyParameters(**raw_params)

        logger.info(
            "[SUPERVISOR] Calling execute_strategy_generation with validated params"
        )
        supervisor_logger.log_token_usage(
            phase="pre_strategy_invocation",
            tokens={"param_count": len(params.model_dump())},
            percentage_of_limit=0.01,
        )

        # Invoke the strategy generation function directly
        # Note: Using direct function call to avoid nested agent invocation issues
        logger.info("[SUPERVISOR] Invoking strategy generation with timeout monitoring...")
        start_time = time.time()

        result = execute_strategy_generation(
            company_name=params.company_name,
            industry=params.industry,
            websites=params.websites,
            customer_regions=params.customer_regions,
            account_id=params.account_id,
            user_id=params.user_id,
            annual_ad_budget=params.annual_ad_budget,
            project_id=params.project_id,
            uploaded_documents=params.uploaded_documents,
        )

        elapsed_time = time.time() - start_time
        logger.info(
            f"[SUPERVISOR] Strategy agent completed successfully in {elapsed_time:.2f} seconds"
        )

        supervisor_logger.log_completion(
            success=True,
            output_tokens=len(str(result)) // 4,
            metadata={
                "account_id": params.account_id,
                "execution_time_seconds": elapsed_time,
            },
        )

        return {
            "status": "success",
            "query": query,
            "result": result,
            "source": "strategy_specialist",
            "agent": "strategy",
            "account_id": params.account_id,
        }
    except Exception as e:
        logger.error(f"[SUPERVISOR] Error in strategy agent dispatch: {e}")
        supervisor_logger.log_error(
            e, {"phase": "strategy_dispatch", "query_preview": query[:200]}
        )
        supervisor_logger.log_completion(success=False, metadata={"error": str(e)})
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "source": "strategy_specialist",
            "agent": "strategy",
        }
