"""Organization and campaign context loading utilities.

This module loads context from Neo4j and formats it for injection into agent messages:
- Organization context: Account Info + Brand Voice/Tone
- Campaign context: Active campaigns with performance metrics (on-demand)

Phase 1 scope: Account Info + Brand Voice/Tone (~1,500 tokens)
Phase 2 scope: Campaign context with mock data (~3,000 tokens)
Future: Will expand to include Strategy, Competitors, Customer Profiles
"""

from datetime import datetime, timedelta
from typing import Any

from ..strategy_agent.neo4j_tools import Neo4jConnection
from ..strategy_agent.token_utils import TokenEstimator
from .structured_logging import get_structured_logger, log_context

logger = get_structured_logger(__name__)

# Token budget for Level 1 context (Account + Brand)
MAX_CONTEXT_TOKENS = 5_000

# Token budget for campaign context
MAX_CAMPAIGN_TOKENS = 3_000

# Keywords that trigger campaign context loading
CAMPAIGN_KEYWORDS = [
    "campaign",
    "campaigns",
    "ad",
    "ads",
    "advertising",
    "performance",
    "roi",
    "roas",
    "ctr",
    "conversion",
    "conversions",
    "spend",
    "budget",
    "impression",
    "impressions",
    "click",
    "clicks",
    "cpc",
    "cpm",
]


def load_organization_context(account_id: str) -> str | None:
    """Load and validate organization context for an account.

    Loads Account info and Brand Voice/Tone from Neo4j, formats as markdown,
    and validates token budget.

    Args:
        account_id: Account identifier

    Returns:
        Formatted markdown context string, or None if loading fails

    Raises:
        Does not raise exceptions - logs errors and returns None for graceful degradation
    """
    try:
        # 1. Fetch from Neo4j
        context_data = _fetch_context_from_neo4j(account_id)

        if not context_data:
            logger.warning(
                "No organization context data found",
                extra=log_context(
                    component="org_context",
                    action="load",
                    account_id=account_id,
                    success=False,
                    error_message="No data in Neo4j",
                ),
            )
            return None

        # 2. Format as markdown
        context_markdown = _format_context_markdown(context_data)

        # 3. Validate token budget
        token_info = TokenEstimator.check_input_limit(
            context_markdown, raise_on_exceed=False
        )

        # 4. Log metrics with structured logging
        logger.info(
            "Loaded organization context",
            extra=log_context(
                component="org_context",
                action="load",
                account_id=account_id,
                token_count=token_info["estimated_tokens"],
                success=True,
                extra={
                    "input_limit_pct": round(token_info["percentage"], 1),
                    "budget_pct": round(
                        (token_info["estimated_tokens"] / MAX_CONTEXT_TOKENS) * 100, 1
                    ),
                    "max_budget": MAX_CONTEXT_TOKENS,
                },
            ),
        )

        # 5. Check if within context budget
        if token_info["estimated_tokens"] > MAX_CONTEXT_TOKENS:
            logger.warning(
                "Organization context exceeds token budget",
                extra=log_context(
                    component="org_context",
                    action="budget_exceeded",
                    account_id=account_id,
                    token_count=token_info["estimated_tokens"],
                    extra={"max_budget": MAX_CONTEXT_TOKENS},
                ),
            )

        return context_markdown

    except Exception as e:
        logger.error(
            f"Failed to load organization context for {account_id}: {e}", exc_info=True
        )
        return None


def _fetch_context_from_neo4j(account_id: str) -> dict | None:
    """Fetch organization context from Neo4j.

    Phase 1 query: Account + Brand Voice/Tone only
    Uses OPTIONAL MATCH for graceful degradation when brand data missing.

    Args:
        account_id: Account identifier

    Returns:
        Dictionary with account and brand data, or None if query fails
    """
    query = """
    MATCH (acc:Account {account_id: $account_id})

    // Brand Guidelines (highest priority)
    OPTIONAL MATCH (acc)-[:FOLLOWS_THESE_BRAND_GUIDELINES]->(brand:BrandIdentity)
    OPTIONAL MATCH (brand)-[:USES_COMMUNICATION_STYLE]->(voice:VoiceAndTone)
    OPTIONAL MATCH (brand)-[:HAS_TRAITS_AND_CHARACTERISTICS]->(personality:BrandPersonality)
    OPTIONAL MATCH (brand)-[:HAS_MISSION]->(mission:MissionAndValues)

    RETURN {
      account: {
        account_id: acc.account_id,
        company_name: acc.company_name,
        company_overview: acc.company_overview,
        industry: acc.industry,
        websites: acc.websites,
        customer_regions: acc.customer_regions
      },
      brand: {
        voice_tone: voice.tone_attributes,
        do_list: voice.do_list,
        dont_list: voice.dont_list,
        personality_traits: personality.traits,
        mission: mission.mission_statement,
        values: mission.core_values[..5]
      }
    } as context
    """

    try:
        connection = Neo4jConnection()
        result = connection.execute_query(query, {"account_id": account_id})
        connection.close()

        if not result or not result[0]:
            logger.warning(f"No results from Neo4j for account_id: {account_id}")
            return None

        return result[0]["context"]

    except Exception as e:
        logger.error(
            f"Neo4j query failed for account_id {account_id}: {e}", exc_info=True
        )
        return None


def _format_context_markdown(data: dict) -> str:
    """Format context data as markdown with YAML frontmatter.

    Uses markdown for optimal token efficiency:
    - YAML frontmatter for metadata (~50 tokens vs 80 for JSON)
    - Markdown headings (~20 tokens vs 35 for JSON keys)
    - Natural language (30% fewer tokens than JSON)

    Args:
        data: Dictionary with 'account' and 'brand' keys

    Returns:
        Formatted markdown string
    """
    account = data.get("account", {})
    brand = data.get("brand", {})

    # YAML frontmatter for metadata
    markdown_parts = ["---"]
    if account.get("account_id"):
        markdown_parts.append(f"account_id: {account['account_id']}")
    if account.get("company_name"):
        markdown_parts.append(f"company: {account['company_name']}")
    if account.get("industry"):
        markdown_parts.append(f"industry: {account['industry']}")
    markdown_parts.append("---\n")

    # Company Context section
    markdown_parts.append("# Company Context\n")

    # Company overview
    if account.get("company_overview"):
        markdown_parts.append(account["company_overview"])
        markdown_parts.append("\n")
    elif account.get("company_name"):
        # Fallback if no overview
        company_desc = f"{account['company_name']}"
        if account.get("industry"):
            company_desc += f" operates in the {account['industry']} industry"
        if account.get("customer_regions"):
            regions = ", ".join(account["customer_regions"])
            company_desc += f", serving customers in {regions}"
        markdown_parts.append(f"{company_desc}.\n")

    # Additional account details
    if account.get("websites"):
        websites = ", ".join(account["websites"])
        markdown_parts.append(f"\n**Websites:** {websites}\n")

    # Brand Voice & Communication Style section
    if brand and any(brand.values()):
        markdown_parts.append("\n## Brand Voice & Communication Style\n")

        # Tone attributes
        if brand.get("voice_tone"):
            if isinstance(brand["voice_tone"], list):
                tone = ", ".join(brand["voice_tone"])
            else:
                tone = brand["voice_tone"]
            markdown_parts.append(f"\n**Tone:** {tone}\n")

        # DO list
        if brand.get("do_list"):
            markdown_parts.append("\n**DO:**\n")
            for item in brand["do_list"]:
                markdown_parts.append(f"- {item}\n")

        # DON'T list
        if brand.get("dont_list"):
            markdown_parts.append("\n**DON'T:**\n")
            for item in brand["dont_list"]:
                markdown_parts.append(f"- {item}\n")

        # Personality traits
        if brand.get("personality_traits"):
            if isinstance(brand["personality_traits"], list):
                traits = ", ".join(brand["personality_traits"])
            else:
                traits = brand["personality_traits"]
            markdown_parts.append(f"\n**Personality Traits:** {traits}\n")

        # Mission
        if brand.get("mission"):
            markdown_parts.append(f"\n**Mission:** {brand['mission']}\n")

        # Core values
        if brand.get("values"):
            if isinstance(brand["values"], list):
                values = ", ".join(brand["values"])
            else:
                values = brand["values"]
            markdown_parts.append(f"\n**Core Values:** {values}\n")
    else:
        # Fallback if no brand data
        markdown_parts.append("\n## Brand Voice & Communication Style\n")
        markdown_parts.append(
            "\n**Tone:** Professional, Clear, Helpful\n"
            "\n**Note:** Specific brand guidelines not yet configured for this account.\n"
        )

    return "".join(markdown_parts)


def inject_organization_context(message: str, context: str) -> str:
    """Prepend organization context to user message.

    Wraps context in clear delimiters for easy parsing by agents.

    Args:
        message: Original user message
        context: Formatted organization context

    Returns:
        Message with context injected
    """
    return f"""[ORGANIZATION CONTEXT]
{context}
[END CONTEXT]

{message}"""


# =============================================================================
# Campaign Context Functions
# =============================================================================


def should_load_campaigns(message: str) -> bool:
    """Check if message references campaigns and should load campaign context.

    Uses keyword detection to determine if the user's message is about
    campaigns or advertising performance.

    Args:
        message: User's message content

    Returns:
        True if message contains campaign-related keywords
    """
    message_lower = message.lower()
    matched_keywords = [kw for kw in CAMPAIGN_KEYWORDS if kw in message_lower]
    should_load = len(matched_keywords) > 0

    if should_load:
        logger.info(
            "Campaign keywords detected in message",
            extra=log_context(
                component="campaign_context",
                action="keyword_detect",
                success=True,
                extra={
                    "matched_keywords": matched_keywords[:5],  # Limit to first 5
                    "message_preview": message[:100],
                },
            ),
        )

    return should_load


def load_campaign_context(account_id: str) -> str | None:
    """Load campaign context for an account.

    Mirrors the load_organization_context pattern. For Sprint 2, returns
    mock data until Campaign nodes exist in Neo4j.

    Args:
        account_id: Account identifier

    Returns:
        Formatted markdown context string, or None if loading fails

    Raises:
        Does not raise exceptions - logs errors and returns None
    """
    try:
        # 1. Fetch from Neo4j (or mock for now)
        campaign_data = _fetch_campaigns_from_neo4j(account_id)

        if not campaign_data:
            logger.warning(
                "No campaign data found",
                extra=log_context(
                    component="campaign_context",
                    action="load",
                    account_id=account_id,
                    success=False,
                    error_message="No campaign data available",
                ),
            )
            return None

        # 2. Format as markdown
        context_markdown = _format_campaign_markdown(campaign_data)

        # 3. Validate token budget
        token_info = TokenEstimator.check_input_limit(
            context_markdown, raise_on_exceed=False
        )

        # Count campaigns by status
        active_count = sum(1 for c in campaign_data if c.get("status") == "active")
        paused_count = sum(1 for c in campaign_data if c.get("status") == "paused")

        # 4. Log metrics with structured logging
        logger.info(
            "Loaded campaign context",
            extra=log_context(
                component="campaign_context",
                action="load",
                account_id=account_id,
                token_count=token_info["estimated_tokens"],
                success=True,
                extra={
                    "campaign_count": len(campaign_data),
                    "active_campaigns": active_count,
                    "paused_campaigns": paused_count,
                    "budget_pct": round(
                        (token_info["estimated_tokens"] / MAX_CAMPAIGN_TOKENS) * 100, 1
                    ),
                    "max_budget": MAX_CAMPAIGN_TOKENS,
                },
            ),
        )

        # 5. Check if within budget
        if token_info["estimated_tokens"] > MAX_CAMPAIGN_TOKENS:
            logger.warning(
                "Campaign context exceeds token budget",
                extra=log_context(
                    component="campaign_context",
                    action="budget_exceeded",
                    account_id=account_id,
                    token_count=token_info["estimated_tokens"],
                    extra={"max_budget": MAX_CAMPAIGN_TOKENS},
                ),
            )

        return context_markdown

    except Exception as e:
        logger.error(
            "Failed to load campaign context",
            extra=log_context(
                component="campaign_context",
                action="load",
                account_id=account_id,
                success=False,
                error_message=str(e),
            ),
            exc_info=True,
        )
        return None


def _fetch_campaigns_from_neo4j(account_id: str) -> list[dict[str, Any]] | None:
    """Fetch campaigns from Neo4j.

    For Sprint 2: Returns mock data until Campaign nodes exist in Neo4j.

    TODO: Replace with real Neo4j query when Campaign schema is defined:
    ```
    MATCH (acc:Account {account_id: $account_id})-[:HAS_CAMPAIGN]->(c:Campaign)
    WHERE c.status = 'active'
    OPTIONAL MATCH (c)-[:HAS_PERFORMANCE]->(p:CampaignPerformance)
    RETURN c, p ORDER BY c.created_at DESC LIMIT 10
    ```

    Args:
        account_id: Account identifier

    Returns:
        List of campaign dictionaries, or None if query fails
    """
    # TODO: Implement real Neo4j query when Campaign nodes exist
    # For now, return mock data
    return _get_mock_campaigns(account_id)


def _get_mock_campaigns(account_id: str) -> list[dict[str, Any]]:
    """Generate mock campaign data for Sprint 2 development.

    This mock data will be replaced with real Neo4j queries once the
    Campaign schema is defined and populated.

    Args:
        account_id: Account identifier (used in mock data)

    Returns:
        List of mock campaign dictionaries
    """
    # Generate realistic-looking dates
    now = datetime.now()

    return [
        {
            "campaign_id": f"camp_{account_id[:8]}_001",
            "name": "Q1 Brand Awareness Campaign",
            "status": "active",
            "channel": "google_ads",
            "objective": "Brand awareness",
            "budget": {
                "total": 5000.00,
                "spent": 3250.00,
                "remaining": 1750.00,
                "currency": "USD",
            },
            "date_range": {
                "start_date": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
            },
            "performance": {
                "impressions": 125000,
                "clicks": 3200,
                "ctr": 2.56,
                "conversions": 145,
                "conversion_rate": 4.53,
                "cost_per_click": 1.02,
                "cost_per_conversion": 22.41,
                "roas": 3.2,
            },
        },
        {
            "campaign_id": f"camp_{account_id[:8]}_002",
            "name": "Product Launch - Spring Collection",
            "status": "active",
            "channel": "meta_ads",
            "objective": "Conversions",
            "budget": {
                "total": 8000.00,
                "spent": 4500.00,
                "remaining": 3500.00,
                "currency": "USD",
            },
            "date_range": {
                "start_date": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=45)).strftime("%Y-%m-%d"),
            },
            "performance": {
                "impressions": 95000,
                "clicks": 4750,
                "ctr": 5.0,
                "conversions": 285,
                "conversion_rate": 6.0,
                "cost_per_click": 0.95,
                "cost_per_conversion": 15.79,
                "roas": 4.5,
            },
        },
        {
            "campaign_id": f"camp_{account_id[:8]}_003",
            "name": "Retargeting - Cart Abandoners",
            "status": "active",
            "channel": "google_ads",
            "objective": "Conversions",
            "budget": {
                "total": 2000.00,
                "spent": 1200.00,
                "remaining": 800.00,
                "currency": "USD",
            },
            "date_range": {
                "start_date": (now - timedelta(days=45)).strftime("%Y-%m-%d"),
                "end_date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            },
            "performance": {
                "impressions": 35000,
                "clicks": 2100,
                "ctr": 6.0,
                "conversions": 168,
                "conversion_rate": 8.0,
                "cost_per_click": 0.57,
                "cost_per_conversion": 7.14,
                "roas": 6.8,
            },
        },
        {
            "campaign_id": f"camp_{account_id[:8]}_004",
            "name": "Email Newsletter Promotion",
            "status": "paused",
            "channel": "google_ads",
            "objective": "Lead generation",
            "budget": {
                "total": 1500.00,
                "spent": 1500.00,
                "remaining": 0.00,
                "currency": "USD",
            },
            "date_range": {
                "start_date": (now - timedelta(days=60)).strftime("%Y-%m-%d"),
                "end_date": (now - timedelta(days=15)).strftime("%Y-%m-%d"),
            },
            "performance": {
                "impressions": 42000,
                "clicks": 1890,
                "ctr": 4.5,
                "conversions": 378,
                "conversion_rate": 20.0,
                "cost_per_click": 0.79,
                "cost_per_conversion": 3.97,
                "roas": None,  # Lead gen, no revenue
            },
        },
    ]


def _format_campaign_markdown(campaigns: list[dict[str, Any]]) -> str:
    """Format campaign data as markdown with YAML frontmatter.

    Mirrors the _format_context_markdown pattern for organization context.

    Args:
        campaigns: List of campaign dictionaries

    Returns:
        Formatted markdown string
    """
    # Count campaigns by status
    active_count = sum(1 for c in campaigns if c.get("status") == "active")
    paused_count = sum(1 for c in campaigns if c.get("status") == "paused")

    # Calculate totals
    total_spent = sum(c.get("budget", {}).get("spent", 0) for c in campaigns)
    total_impressions = sum(
        c.get("performance", {}).get("impressions", 0) for c in campaigns
    )
    total_conversions = sum(
        c.get("performance", {}).get("conversions", 0) for c in campaigns
    )

    # YAML frontmatter
    markdown_parts = [
        "---",
        f"total_campaigns: {len(campaigns)}",
        f"active_campaigns: {active_count}",
        f"paused_campaigns: {paused_count}",
        f"total_spent: ${total_spent:,.2f}",
        "---\n",
    ]

    # Summary section
    markdown_parts.append("# Campaign Performance Summary\n")
    markdown_parts.append(f"**Active Campaigns:** {active_count}")
    markdown_parts.append(f" | **Total Impressions:** {total_impressions:,}")
    markdown_parts.append(f" | **Total Conversions:** {total_conversions:,}")
    markdown_parts.append(f" | **Total Spend:** ${total_spent:,.2f}\n")

    # Individual campaigns
    markdown_parts.append("\n## Active Campaigns\n")

    for campaign in campaigns:
        if campaign.get("status") != "active":
            continue

        markdown_parts.append(f"### {campaign['name']}\n")
        markdown_parts.append(f"- **Channel:** {campaign.get('channel', 'Unknown')}")
        markdown_parts.append(
            f" | **Objective:** {campaign.get('objective', 'Unknown')}"
        )
        markdown_parts.append(f" | **Status:** {campaign.get('status', 'Unknown')}\n")

        # Budget info
        budget = campaign.get("budget", {})
        if budget:
            markdown_parts.append(
                f"- **Budget:** ${budget.get('total', 0):,.2f} total, "
                f"${budget.get('spent', 0):,.2f} spent, "
                f"${budget.get('remaining', 0):,.2f} remaining\n"
            )

        # Performance metrics
        perf = campaign.get("performance", {})
        if perf:
            markdown_parts.append("- **Performance:**\n")
            markdown_parts.append(f"  - Impressions: {perf.get('impressions', 0):,}\n")
            markdown_parts.append(f"  - Clicks: {perf.get('clicks', 0):,}\n")
            markdown_parts.append(f"  - CTR: {perf.get('ctr', 0):.2f}%\n")
            markdown_parts.append(f"  - Conversions: {perf.get('conversions', 0):,}\n")
            markdown_parts.append(
                f"  - Conversion Rate: {perf.get('conversion_rate', 0):.2f}%\n"
            )
            markdown_parts.append(
                f"  - Cost per Click: ${perf.get('cost_per_click', 0):.2f}\n"
            )
            markdown_parts.append(
                f"  - Cost per Conversion: ${perf.get('cost_per_conversion', 0):.2f}\n"
            )
            if perf.get("roas"):
                markdown_parts.append(f"  - ROAS: {perf.get('roas', 0):.1f}x\n")

        markdown_parts.append("\n")

    # Paused campaigns (brief)
    paused_campaigns = [c for c in campaigns if c.get("status") == "paused"]
    if paused_campaigns:
        markdown_parts.append("## Paused Campaigns\n")
        for campaign in paused_campaigns:
            budget = campaign.get("budget", {})
            markdown_parts.append(
                f"- **{campaign['name']}** ({campaign.get('channel', 'Unknown')}) - "
                f"Spent ${budget.get('spent', 0):,.2f}\n"
            )

    return "".join(markdown_parts)


def inject_campaign_context(message: str, context: str) -> str:
    """Prepend campaign context to user message.

    Mirrors inject_organization_context pattern with campaign-specific delimiters.

    Args:
        message: Original user message
        context: Formatted campaign context

    Returns:
        Message with campaign context injected
    """
    return f"""[CAMPAIGN CONTEXT]
{context}
[END CAMPAIGN CONTEXT]

{message}"""
