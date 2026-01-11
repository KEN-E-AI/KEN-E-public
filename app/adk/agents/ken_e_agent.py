"""
KEN-E Agent: Frontend-facing chat agent for company news and analytics.
"""

import logging

from google.adk.agents import Agent

from .strategy_agent.config_loader import load_config_from_firestore
from .utils.dispatch_handlers import (
    dispatch_to_company_news,
    dispatch_to_google_analytics,
)
from .utils.supervisor_utils import dispatch_with_context

logger = logging.getLogger(__name__)


def create_ken_e_agent(config_doc_id: str = "ken_e_chatbot"):
    """
    Create the KEN-E chat agent for frontend interactions.
    Handles company news and Google Analytics queries only.

    Args:
        config_doc_id: Firestore document ID for agent configuration (default: "ken_e_chatbot")
    """

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

    # Create dispatch functions with context handling
    search_company_news = dispatch_with_context(dispatch_to_company_news)
    search_company_news.__name__ = "search_company_news"
    search_company_news.__doc__ = """Search for company news, financial updates, earnings reports, market analysis, and business announcements.

Args:
    query: The user's question about company news, earnings, market updates, or business intelligence
"""

    query_google_analytics = dispatch_with_context(dispatch_to_google_analytics)
    query_google_analytics.__name__ = "query_google_analytics"
    query_google_analytics.__doc__ = """Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance, and access GA4 properties.

Args:
    query: The user's question about website analytics, traffic, user behavior, or GA4 data
"""

    ken_e = Agent(
        name="ken_e",
        model=model,
        instruction="""You are KEN-E, an intelligent AI assistant specializing in business intelligence and analytics.

**CRITICAL: When you call a tool, the tool's response contains the answer. You MUST present that response to the user. Never just acknowledge that you called the tool - always share what the tool returned.**

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

3. When routing, ALWAYS pass the COMPLETE user input to the tool

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

Remember: You are a router, not a data source. ALWAYS delegate to the appropriate specialized agent using the provided tools.""",
        tools=[search_company_news, query_google_analytics],
    )

    return ken_e


# Export the agent
ken_e_agent = create_ken_e_agent()
