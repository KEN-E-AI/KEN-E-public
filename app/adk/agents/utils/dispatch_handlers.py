"""
Dispatch handlers for routing to specialized agents.
"""

import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from pydantic import ValidationError

from ..models.strategy_models import StrategyParameters, parse_strategy_query
from .agent_retry import invoke_agent_with_retry
from .supervisor_utils import invoke_agent_sync

logger = logging.getLogger(__name__)


def dispatch_to_company_news(
    query: str, tenant_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    News agent doesn't need tenant context as it uses public data.
    """
    # Import here to avoid circular dependencies
    from ..company_news_chatbot.agent import root_agent as news_agent

    try:
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
    query: str, tenant_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Dispatch Google Analytics queries with tenant context.
    In production, tenant context comes from the authenticated user's session.
    For testing, we use environment variables.
    """
    # Import here to avoid circular dependencies
    from ..google_analytics_agent_v4 import google_analytics_agent_v4

    try:
        logger.info("🔄 Routing Google Analytics query to specialized agent...")

        # In production, credentials would come from the KEN-E app's user session
        # For testing/development, use environment variables
        if not tenant_context or not tenant_context.get("tenant_credentials"):
            # Testing mode: use environment credentials
            env_creds = os.getenv("GA_PERSONAL_CREDENTIALS")
            if env_creds:
                tenant_context = {
                    "tenant_id": os.getenv("GA_TENANT_ID", "test-org"),
                    "tenant_credentials": env_creds,
                }
                logger.info("Using test credentials from environment")

        # Prepare query with tenant context
        if (
            tenant_context
            and tenant_context.get("tenant_id")
            and tenant_context.get("tenant_credentials")
        ):
            # Inject tenant context into the query for the GA agent
            enhanced_query = f"TENANT_ID:{tenant_context['tenant_id']} TENANT_CREDS:{tenant_context['tenant_credentials']} {query}"
        else:
            # No credentials available
            enhanced_query = query

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
        logger.error(f"Error in analytics agent dispatch: {e}")
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "source": "google_analytics_specialist",
            "agent": "analytics",
        }


def dispatch_to_strategy(
    query: str, tenant_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
            logger.info(f"[SUPERVISOR] Successfully validated strategy parameters")
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
            f"[SUPERVISOR] Calling execute_strategy_generation with validated params"
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
