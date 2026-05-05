"""
KEN-E Agent: Frontend-facing chat agent for company news and analytics.
"""

import logging
import os
from collections.abc import Callable
from pathlib import Path

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import ToolContext
from google.genai.types import GenerateContentConfig, ThinkingConfig

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
    adk_after_model_callback,
    adk_after_tool_callback,
    weave_after_agent_callback,
    weave_before_agent_callback,
)
from app.utils.weave_observability import init_weave_if_needed, safe_weave_op
from shared.structured_logging import configure_logging, get_structured_logger

from .strategy_agent.config_loader import load_config_from_firestore
from .utils import config_cache
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

**TASK DELEGATION:**
Before calling `search_company_news` or `query_google_analytics`, generate 2-4 specific acceptance criteria that the specialist's response must satisfy. Pass them as the `acceptance_criteria` parameter.

Good criteria are:
- **Verifiable from the draft text alone** — the reviewer is a structural/format checker, not a fact-checker; it cannot verify claims that require external knowledge
- **Measurable:** "Include a table with columns: campaign name, sessions, engagement rate"
- **Specific:** "Cover the past 30 days of data"
- **Format-bound:** "Output as a numbered list"

Bad criteria (vague or unverifiable):
- "Provide useful information" — vague; no clear pass/fail signal
- "Numbers must be accurate" — requires fact-checking; the reviewer cannot verify factual claims
- "Be comprehensive" — vague; cannot be verified from the response text

For trivially simple lookups, omit the criteria — the dispatch falls back to single-pass.

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
    """Build KEN-E's instruction from ``_BASE_INSTRUCTION`` + org context.

    Static alternative to the cache-backed :func:`_make_instruction_provider`
    closure. Kept because ``tests/unit/test_adk_agents/test_ken_e_instruction_provider.py``
    targets the static merge behavior directly (no cache / no Firestore),
    which is useful for regression-testing the org-context prepend logic
    independently of the hot-reload path.
    """
    org_context = context.state.get("organization_context")
    if org_context:
        return f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{_BASE_INSTRUCTION}"
    return _BASE_INSTRUCTION


def _make_instruction_provider(config_doc_id: str) -> Callable[[ReadonlyContext], str]:
    """Create an InstructionProvider that reads the latest instruction from cache.

    Per Sprint 6 Decision B, the instruction text is live-reloadable: every
    turn, the closure asks the agent config cache for the current
    instruction, so admin PUTs propagate within the cache TTL (~60 s) with
    no redeploy. The cache handles Firestore failures by serving the last
    known-good value. If even the cache is unusable (e.g., first call ever
    failed), fall back to the hardcoded ``_BASE_INSTRUCTION`` so the turn
    still runs rather than erroring out.

    Args:
        config_doc_id: Firestore document ID under ``agent_configs``.

    Returns:
        A callable ADK invokes each turn; returns the current instruction
        string (with organization context prepended if present in state).
    """

    def instruction_provider(context: ReadonlyContext) -> str:
        try:
            cfg, _, _ = config_cache.get_cached_config(config_doc_id)
            base_instruction = cfg.instruction or _BASE_INSTRUCTION
        except Exception as e:
            logger.warning(
                f"InstructionProvider could not load {config_doc_id!r} from cache "
                f"({e}); falling back to _BASE_INSTRUCTION for this turn."
            )
            base_instruction = _BASE_INSTRUCTION

        org_context = context.state.get("organization_context")
        if org_context:
            return f"[ORGANIZATION CONTEXT]\n{org_context}\n[END CONTEXT]\n\n{base_instruction}"
        return base_instruction

    return instruction_provider


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

    # Load model / description / generate_content_config from Firestore at
    # construction time — ADK bakes these into the Agent at __init__ and
    # doesn't accept callables for them (Sprint 6 Decision B). The agent's
    # ``instruction`` is read live from the config cache on every turn, so
    # it is NOT bound here.
    try:
        config, metadata, _ = load_config_from_firestore(config_doc_id)
        model = config.model
        description = config.description or ""
        generate_content_config = config.generate_content_config
        logger.info(
            f"Loaded KEN-E chatbot config from Firestore: {config_doc_id} "
            f"(version: {metadata.get('version', 'unknown')}, model: {model})"
        )
    except Exception as e:
        logger.warning(
            f"Failed to load KEN-E chatbot config from Firestore ({config_doc_id}): {e}. "
            f"Falling back to hardcoded defaults"
        )
        model = "gemini-2.5-pro"
        description = ""
        generate_content_config = None

    # Enable thinking so the model outputs reasoning about tool selection.
    # This makes thought parts available to adk_after_model_callback for
    # context_reasoning capture on tool call spans.
    if generate_content_config is None:
        generate_content_config = GenerateContentConfig(
            thinking_config=ThinkingConfig(include_thoughts=True),
        )
    elif not getattr(generate_content_config, "thinking_config", None):
        generate_content_config.thinking_config = ThinkingConfig(include_thoughts=True)

    # Create tool wrappers that expose ToolContext and return strings
    def search_company_news(
        query: str,
        acceptance_criteria: str = "",
        tool_context: ToolContext | None = None,
    ) -> str:
        """Search for company news, financial updates, earnings reports, market analysis, and business announcements.

        Args:
            query: The user's question about company news, earnings, market updates, or business intelligence
            acceptance_criteria: Optional 2-4 measurable criteria the specialist's response must satisfy.
                Empty string = single-pass dispatch (no review loop).
        """
        result = dispatch_to_company_news(
            query,
            tool_context,
            acceptance_criteria=acceptance_criteria or None,
        )
        return (
            result.get("result", str(result))
            if isinstance(result, dict)
            else str(result)
        )

    def query_google_analytics(
        query: str,
        acceptance_criteria: str = "",
        tool_context: ToolContext | None = None,
    ) -> str:
        """Query Google Analytics data, run reports, get real-time metrics, analyze website/app performance, and access GA4 properties.

        Args:
            query: The user's question about website analytics, traffic, user behavior, or GA4 data
            acceptance_criteria: Optional 2-4 measurable criteria the specialist's response must satisfy.
                Empty string = single-pass dispatch (no review loop).
        """
        result = dispatch_to_google_analytics(
            query,
            tool_context,
            acceptance_criteria=acceptance_criteria or None,
        )
        return (
            result.get("result", str(result))
            if isinstance(result, dict)
            else str(result)
        )

    # Apply Weave tracing to tool wrappers (dispatch handlers are already traced,
    # but these wrappers need their own spans for complete L3 tool coverage)
    search_company_news = safe_weave_op(name="search_company_news")(search_company_news)
    query_google_analytics = safe_weave_op(name="query_google_analytics")(
        query_google_analytics
    )

    ken_e = Agent(
        name="ken_e",
        model=model,
        description=description,
        instruction=_make_instruction_provider(config_doc_id),
        generate_content_config=generate_content_config,
        before_agent_callback=weave_before_agent_callback,
        after_agent_callback=weave_after_agent_callback,
        after_model_callback=adk_after_model_callback,
        before_tool_callback=adk_before_tool_callback,
        after_tool_callback=adk_after_tool_callback,
        tools=[search_company_news, query_google_analytics],
    )

    return ken_e


# Export the agent
ken_e_agent = create_ken_e_agent()
