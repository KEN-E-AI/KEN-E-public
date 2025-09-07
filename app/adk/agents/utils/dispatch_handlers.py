"""
Dispatch handlers for routing to specialized agents.
"""

import logging
import os
import re
import time
import uuid
from typing import Any

from .supervisor_utils import invoke_agent_sync

logger = logging.getLogger(__name__)


def dispatch_to_company_news(
    query: str, tenant_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    News agent doesn't need tenant context as it uses public data.
    """
    # Import here to avoid circular dependencies
    from ..company_news_chatbot.agent import root_agent as news_agent

    try:
        logger.info("🔄 Routing company news query to specialized agent...")
        result = invoke_agent_sync(news_agent, query)

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
    query: str, tenant_context: dict[str, Any] | None = None
) -> dict[str, Any]:
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

        result = invoke_agent_sync(google_analytics_agent_v4, enhanced_query)

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
    query: str, tenant_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Dispatch strategy queries to the iterative strategy agent.
    Strategy agent needs account context for document persistence.
    """
    # Import here to avoid circular dependencies
    from ..strategy_agent.logging_config import StrategyAgentLogger
    from ..strategy_agent.orchestrator import (
        execute_strategy_generation as invoke_strategy_agent_sync,
    )
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

        # Parse the query to extract strategy generation parameters
        # Extract parameters from the formatted message
        params = {}

        # Try to extract parameters from the structured format
        param_patterns = {
            "company_name": r"[-•]\s*company_name:\s*(.+?)(?:\n|$)",
            "industry": r"[-•]\s*industry:\s*(.+?)(?:\n|$)",
            "websites": r"[-•]\s*websites:\s*(.+?)(?:\n|$)",
            "customer_regions": r"[-•]\s*customer_regions:\s*(.+?)(?:\n|$)",
            "account_id": r"[-•]\s*account_id:\s*(.+?)(?:\n|$)",
            "user_id": r"[-•]\s*user_id:\s*(.+?)(?:\n|$)",
            "annual_ad_budget": r"[-•]\s*annual_ad_budget:\s*(.+?)(?:\n|$)",
            "project_id": r"[-•]\s*project_id:\s*(.+?)(?:\n|$)",
            "uploaded_documents": r"[-•]\s*uploaded_documents:\s*(.+?)(?:\n|$)",
        }

        for param_name, pattern in param_patterns.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # Convert annual_ad_budget to float
                if param_name == "annual_ad_budget":
                    try:
                        params[param_name] = float(value)
                    except (ValueError, TypeError):
                        params[param_name] = 0.0
                # Convert uploaded_documents to list
                elif param_name == "uploaded_documents":
                    # Split comma-separated URLs
                    params[param_name] = [
                        url.strip() for url in value.split(",") if url.strip()
                    ]
                else:
                    params[param_name] = value

        # Use tenant_context to fill in missing values
        if tenant_context:
            if "account_id" not in params:
                params["account_id"] = tenant_context.get(
                    "account_id"
                ) or tenant_context.get("tenant_id")
            if "user_id" not in params:
                params["user_id"] = tenant_context.get("user_id")
            if "project_id" not in params:
                params["project_id"] = tenant_context.get("project_id")

        # Check if we have the required parameters
        required_params = [
            "company_name",
            "industry",
            "websites",
            "customer_regions",
            "account_id",
            "user_id",
        ]
        missing_params = [
            p for p in required_params if p not in params or not params[p]
        ]

        if missing_params:
            logger.warning(
                f"[SUPERVISOR] Missing required parameters for strategy generation: {missing_params}"
            )
            logger.info(f"[SUPERVISOR] Extracted parameters: {params}")
            logger.info(f"[SUPERVISOR] Query preview: {query[:500]}")
            supervisor_logger.log_token_usage(
                phase="parameter_extraction",
                tokens={
                    "params_missing": len(missing_params),
                    "params_found": len(params),
                },
                percentage_of_limit=0.01,  # Very small
            )
            # Try to proceed with what we have

        # Set defaults for optional parameters
        params.setdefault("annual_ad_budget", 0.0)
        params.setdefault("project_id", os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev"))

        logger.info(
            f"[SUPERVISOR] Calling execute_strategy_generation with params: {params}"
        )
        supervisor_logger.log_token_usage(
            phase="pre_strategy_invocation",
            tokens={"param_count": len(params)},
            percentage_of_limit=0.01,
        )

        # Invoke the strategy agent with the correct parameters
        logger.info("[SUPERVISOR] Invoking strategy agent with timeout monitoring...")
        start_time = time.time()

        result = invoke_strategy_agent_sync(
            company_name=params.get("company_name", "Unknown Company"),
            industry=params.get("industry", "Unknown Industry"),
            websites=params.get("websites", ""),
            customer_regions=params.get("customer_regions", ""),
            account_id=params.get("account_id", ""),
            user_id=params.get("user_id", ""),
            annual_ad_budget=params.get("annual_ad_budget", 0.0),
            project_id=params.get("project_id"),
            uploaded_documents=params.get("uploaded_documents", []),
        )

        elapsed_time = time.time() - start_time
        logger.info(
            f"[SUPERVISOR] Strategy agent completed successfully in {elapsed_time:.2f} seconds"
        )

        supervisor_logger.log_completion(
            success=True,
            output_tokens=len(str(result)) // 4,
            metadata={
                "account_id": params.get("account_id", ""),
                "execution_time_seconds": elapsed_time,
            },
        )

        return {
            "status": "success",
            "query": query,
            "result": result,
            "source": "strategy_specialist",
            "agent": "strategy",
            "account_id": params.get("account_id", ""),
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
