"""
KEN-E Agent: Frontend-facing chat agent for company news and analytics.
"""

import logging
import os
from pathlib import Path

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import ToolContext

# Load environment variables from .env file BEFORE reading any env vars.
# On Agent Engine the .env is deployed alongside the agent code.
try:
    from dotenv import load_dotenv

    base_path = Path(__file__).resolve().parent
    possible_paths = [
        base_path.parent / ".env",
        base_path / ".env",
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)
            break
except ImportError:
    pass

from app.adk.security.hooks import adk_before_tool_callback
from app.adk.tracking.callbacks import (
    adk_after_tool_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)
from app.utils.weave_observability import init_weave_if_needed
from shared.structured_logging import configure_logging, get_structured_logger

from .strategy_agent.config_loader import load_config_from_firestore
from .utils.dispatch_handlers import (
    dispatch_to_company_news,
    dispatch_to_google_analytics,
)

_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
configure_logging(level=_log_level)

logger = get_structured_logger(__name__)

_BASE_INSTRUCTION = """You are KEN-E, an intelligent AI assistant specializing in business intelligence and analytics.

**CRITICAL: When you call a tool, the tool's response contains the answer. You MUST present that response to the user. Never just acknowledge that you called the tool - always share what the tool returned.**

**ORGANIZATION CONTEXT:**
When organization context is available, it appears at the top of this instruction under [ORGANIZATION CONTEXT].

CRITICAL - When formulating responses, ALWAYS:
- Match the brand's tone and communication style (see "DO" and "DON'T" lists in context)
- Use the personality traits as a guide for your voice and approach
- Reference the company's mission when explaining capabilities or providing recommendations
- Stay aligned with the company's core values in your responses

Example: If the brand voice says "DO: Use data-driven language", then include metrics and evidence in your responses. If it says "DON'T: Use jargon", then explain technical concepts in plain language.

The context ensures all responses are contextually appropriate for your organization.

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
- Any GA4 property data or analysis

**ROUTING INSTRUCTIONS:**
1. Analyze the user's intent using your LLM capabilities
2. Route based on the primary focus of the query:
   - Company/business/market focus → search_company_news
   - Website/traffic/analytics focus → query_google_analytics

3. When routing, pass the user's question to the appropriate tool
   - Extract the actual question from the message
   - Pass it as a clear, natural language query

4. Handle ambiguous queries:
   - If unclear, ask for clarification about which capability they need
   - If query could match multiple capabilities, ask which they'd like to explore first

5. Response handling:
   - ALWAYS relay the complete response from the specialized agent to the user
   - The tool response IS your response - present it in full
   - Maintain the formatting from the specialist agent

**IMPORTANT NOTES:**
- You are integrated with the KEN-E app where users are already authenticated
- NEVER ask users for credentials - they're already logged in with Google
- The system automatically uses the logged-in user's Google account for GA queries
- Strategy document generation is handled separately during account creation

**STRATEGY DOCUMENTS NOTE:**
If users ask about creating or generating strategy documents, explain:
"Strategy documents are automatically generated when you create a new account. They include business strategy, competitive analysis, customer journey, marketing strategy, and brand guidelines tailored to your company. These comprehensive documents are created once during account setup to provide a strong foundation for your marketing efforts."

**EXAMPLES OF ROUTING:**
- "What's the latest news about Apple?" → search_company_news
- "Show me website traffic for last week" → query_google_analytics
- "How many users visited my site?" → query_google_analytics
- "Tesla earnings report" → search_company_news
- "Bounce rate by country" → query_google_analytics
- "Microsoft acquisition news" → search_company_news

Remember: You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools."""


def build_ken_e_instruction(context: ReadonlyContext) -> str:
    """Build KEN-E instruction with organization context from session state.

    ADK calls this on each turn, reading org context that was stored
    in session state at session creation time (no DB call here).

    Args:
        context: ADK ReadonlyContext with access to session state
    """
    org_context = context.state.get("organization_context")
    if org_context:
        return f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{_BASE_INSTRUCTION}"
    return _BASE_INSTRUCTION


def create_ken_e_agent(config_doc_id: str = "ken_e_chatbot"):
    """
    Create the KEN-E chat agent for frontend interactions.
    Handles company news and Google Analytics queries only.

    Args:
        config_doc_id: Firestore document ID for agent configuration (default: "ken_e_chatbot")
    """

    # Initialize Weave tracing — log loudly on failure but don't block agent
    weave_ok = init_weave_if_needed()
    if not weave_ok:
        logger.error(
            "WEAVE INITIALIZATION FAILED — traces will NOT be captured. "
            "Check that WANDB_API_KEY is set in .env and the weave package is installed."
        )

    # Load configuration from Firestore with fallback to hardcoded values
    try:
        config, metadata = load_config_from_firestore(config_doc_id)
        model = config.model
        logger.info(
            f"Loaded KEN-E chatbot config from Firestore: {config_doc_id} "
            f"(version: {metadata.get('version', 'unknown')}, model: {model})"
        )
    except Exception as e:
        logger.warning(
            f"Failed to load KEN-E chatbot config from Firestore ({config_doc_id}): {e}. "
            f"Falling back to hardcoded model: gemini-2.0-flash"
        )
        model = "gemini-2.0-flash"

    # Create tool wrappers that expose ToolContext and return strings
    def search_company_news(query: str, tool_context: ToolContext | None = None) -> str:
        """Search for company news, financial updates, earnings reports, market analysis, and business announcements.

        Args:
            query: The user's question about company news, earnings, market updates, or business intelligence
        """
        result = dispatch_to_company_news(query, tool_context)
        return result.get("result", str(result)) if isinstance(result, dict) else str(result)

    def query_google_analytics(query: str, tool_context: ToolContext | None = None) -> str:
        """Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance, and access GA4 properties.

        Args:
            query: The user's question about website analytics, traffic, user behavior, or GA4 data
        """
        result = dispatch_to_google_analytics(query, tool_context)
        return result.get("result", str(result)) if isinstance(result, dict) else str(result)

    ken_e = Agent(
        name="ken_e",
        model=model,
        before_agent_callback=weave_before_agent_callback,
        after_agent_callback=weave_after_agent_callback,
        before_tool_callback=adk_before_tool_callback,
        after_tool_callback=adk_after_tool_callback,
        instruction=build_ken_e_instruction,
        tools=[search_company_news, query_google_analytics],
    )

    return ken_e


# Export the agent
ken_e_agent = create_ken_e_agent()
