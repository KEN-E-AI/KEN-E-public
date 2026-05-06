"""
Dispatch handlers for routing to specialized agents.
"""

import logging
import time
import uuid
from typing import Any

from google.adk.tools import ToolContext
from pydantic import ValidationError

from app.utils.weave_observability import safe_weave_op

from ..models.strategy_models import StrategyParameters, parse_strategy_query
from .agent_retry import (
    DEFAULT_RETRY_CONFIG,
    FAST_RETRY_CONFIG,
    invoke_agent_with_retry,
)
from .criteria_utils import MAX_CRITERIA_CHARS, sanitise_criteria
from .review_pipeline import (
    _check_hallucinated_approval,
    build_review_pipeline,
    extract_iterations,
    extract_pipeline_result,
    get_reviewer_name,
    get_worker_name,
)
from .review_pipeline_tracing import emit_iteration_span, set_pipeline_attrs
from .supervisor_utils import invoke_pipeline

logger = logging.getLogger(__name__)


@safe_weave_op(name="dispatch_to_company_news")
def dispatch_to_company_news(
    query: str,
    tool_context: ToolContext | None = None,
    tenant_context: dict[str, Any] | None = None,
    acceptance_criteria: str | None = None,
) -> dict[str, Any]:
    """
    Dispatch company news queries to the specialized news agent.
    News agent doesn't need tenant context as it uses public data.

    Args:
        query: User's question about company news
        tool_context: ADK ToolContext with session state (auto-injected)
        tenant_context: Legacy parameter for backward compatibility
        acceptance_criteria: Optional 2-4 measurable criteria the specialist's
            response must satisfy. None or empty string → single-pass dispatch
            (no review loop). Non-empty → builds a review pipeline via
            build_review_pipeline() and returns the §5.2-idiom outcome.
    """
    from shared.context_utils import inject_organization_context

    from ..registry import get_registry
    news_agent = get_registry().get("news")

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

        criteria = (acceptance_criteria or "").strip()
        if len(criteria) > MAX_CRITERIA_CHARS:
            logger.warning(
                f"[NEWS-DISPATCH] acceptance_criteria truncated from {len(criteria)} to {MAX_CRITERIA_CHARS} chars"
            )
            criteria = criteria[:MAX_CRITERIA_CHARS]
        criteria = sanitise_criteria(criteria)
        if criteria:
            logger.info("🔄 Building review pipeline for company news query...")
            pipeline = build_review_pipeline(
                specialist=news_agent,
                acceptance_criteria=criteria,
                output_key_prefix="news_review",
            )
            _text, final_state, events = invoke_pipeline(pipeline, query)
            _check_hallucinated_approval(events, "news_review")
            outcome = extract_pipeline_result(final_state, "news_review")
            worker_name = get_worker_name(news_agent)
            reviewer_name = get_reviewer_name("news_review")
            iterations = extract_iterations(events, worker_name, reviewer_name, "news_review")
            for it in iterations:
                emit_iteration_span(it.iteration, it.specialist_output, it.reviewer_output)
            set_pipeline_attrs(criteria, final_state, "news_review", len(iterations))
            return {
                **outcome,
                "status": "success",
                "query": query,
                "source": "company_news_specialist",
                "agent": "news",
            }

        logger.info("🔄 Routing company news query to specialized agent...")
        result = invoke_agent_with_retry(news_agent, query, retry_config=FAST_RETRY_CONFIG)

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


@safe_weave_op(name="dispatch_to_google_analytics")
def dispatch_to_google_analytics(
    query: str,
    tool_context: ToolContext | None = None,
    tenant_context: dict[str, Any] | None = None,
    acceptance_criteria: str | None = None,
) -> dict[str, Any]:
    """Dispatch Google Analytics queries to the specialized agent.

    Credentials flow automatically via session state -> McpToolset header_provider
    -> HTTP headers. No credential encoding or query injection needed.

    Args:
        query: The Google Analytics query or question from the user
        tool_context: ADK ToolContext with session state (auto-injected by ADK)
        tenant_context: Legacy parameter for backward compatibility
        acceptance_criteria: Optional 2-4 measurable criteria the specialist's
            response must satisfy. None or empty string → single-pass dispatch
            (no review loop). Non-empty → builds a review pipeline via
            build_review_pipeline() and returns the §5.2-idiom outcome.
            GA credentials initial_state is forwarded to invoke_pipeline() so
            the specialist's McpToolset header_provider can read them.
    """
    from shared.context_utils import (
        inject_campaign_context,
        inject_organization_context,
    )

    from ..registry import get_registry
    google_analytics_agent_v4 = get_registry().get("google_analytics")

    try:
        logger.info("Routing Google Analytics query to specialized agent...")

        account_id = None
        ga_credentials = None
        tenant_id = None

        if tool_context and hasattr(tool_context, 'state'):
            account_id = tool_context.state.get("account_id")
            ga_credentials = tool_context.state.get("ga_credentials")
            if ga_credentials:
                tenant_id = ga_credentials.get("tenant_id")
                selected_property_ids = ga_credentials.get("selected_property_ids", [])
                logger.info(
                    f"GA credentials in session state for account: {account_id}, "
                    f"properties: {len(selected_property_ids)}"
                )

                # Include property ID context in the query so the agent knows which property to use
                if len(selected_property_ids) == 1:
                    query = f"[Property ID: {selected_property_ids[0]}] {query}"
                elif selected_property_ids:
                    query = f"[Available Property IDs: {', '.join(selected_property_ids)}] {query}"
            else:
                logger.info(f"No GA credentials in session state for account: {account_id}")
        elif tenant_context:
            account_id = tenant_context.get("account_id")
            tenant_id = tenant_context.get("tenant_id")

        # Inject organization context from session state
        if tool_context and hasattr(tool_context, 'state'):
            org_context = tool_context.state.get("organization_context")
            if org_context:
                query = inject_organization_context(query, org_context)
                logger.info(f"Injected organization context, new query length: {len(query)}")

            campaign_context = tool_context.state.get("campaign_context")
            if campaign_context:
                query = inject_campaign_context(query, campaign_context)
                logger.info(f"Injected campaign context, new query length: {len(query)}")

        initial_state: dict[str, Any] | None = None
        if ga_credentials:
            initial_state = {"ga_credentials": ga_credentials}

        criteria = (acceptance_criteria or "").strip()
        if len(criteria) > MAX_CRITERIA_CHARS:
            logger.warning(
                f"[GA-DISPATCH] acceptance_criteria truncated from {len(criteria)} to {MAX_CRITERIA_CHARS} chars"
            )
            criteria = criteria[:MAX_CRITERIA_CHARS]
        criteria = sanitise_criteria(criteria)
        if criteria:
            logger.info("🔄 Building review pipeline for Google Analytics query...")
            pipeline = build_review_pipeline(
                specialist=google_analytics_agent_v4,
                acceptance_criteria=criteria,
                output_key_prefix="ga_review",
            )
            _text, final_state, events = invoke_pipeline(
                pipeline, query, state=initial_state
            )
            _check_hallucinated_approval(events, "ga_review")
            outcome = extract_pipeline_result(final_state, "ga_review")
            worker_name = get_worker_name(google_analytics_agent_v4)
            reviewer_name = get_reviewer_name("ga_review")
            iterations = extract_iterations(events, worker_name, reviewer_name, "ga_review")
            for it in iterations:
                emit_iteration_span(it.iteration, it.specialist_output, it.reviewer_output)
            set_pipeline_attrs(criteria, final_state, "ga_review", len(iterations))
            return {
                **outcome,
                "status": "success",
                "query": query,
                "source": "google_analytics_specialist",
                "agent": "analytics",
                "tenant_id": tenant_id,
            }

        result = invoke_agent_with_retry(
            google_analytics_agent_v4, query, state=initial_state, retry_config=DEFAULT_RETRY_CONFIG
        )

        return {
            "status": "success",
            "query": query,
            "result": result,
            "source": "google_analytics_specialist",
            "agent": "analytics",
            "tenant_id": tenant_id,
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


@safe_weave_op(name="dispatch_to_strategy")
def dispatch_to_strategy(
    query: str, tenant_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Dispatch strategy queries to the iterative strategy agent.
    Strategy agent needs account context for document persistence.
    """
    # Import here to avoid circular dependencies
    from shared.token_utils import check_and_log_tokens

    from ..strategy_agent.logging_config import StrategyAgentLogger
    from ..strategy_agent.orchestrator import execute_strategy_generation

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
