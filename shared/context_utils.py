"""Pure utility functions for context formatting and injection.

Extracted from app/adk/agents/utils/context_loader.py so both API and agent
containers can use them without cross-container imports.

All functions in this module are pure — no database or logging dependencies.
"""

from typing import Any

# Canonical Neo4j query for organization context (single source of truth).
# Both API-side and agent-side loaders use this query.
ORG_CONTEXT_QUERY = """
MATCH (acc:Account {account_id: $account_id})
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


def extract_context_from_result(result: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Extract context dict from a Neo4j query result.

    Args:
        result: List of result records from executing ORG_CONTEXT_QUERY

    Returns:
        Context dictionary with 'account' and 'brand' keys, or None if empty
    """
    if not result or not result[0]:
        return None
    return result[0]["context"]


# Keywords that trigger section loading for different context types
SECTION_KEYWORDS: dict[str, list[str]] = {
    "campaigns": [
        "campaign", "campaigns", "ad", "ads", "advertising", "performance",
        "roi", "roas", "ctr", "conversion", "conversions", "spend", "budget",
        "impression", "impressions", "click", "clicks", "cpc", "cpm",
    ],
    "products": [
        "product", "products", "service", "services", "offering", "offerings",
        "solution", "solutions", "feature", "features",
    ],
    "icps": [
        "icp", "icps", "ideal customer", "customer profile", "target audience",
        "persona", "personas", "buyer", "buyers", "segment", "segments",
    ],
    "competitors": [
        "competitor", "competitors", "competition", "competitive", "rival",
        "rivals", "alternative", "alternatives", "market share",
    ],
    "strategies": [
        "strategy", "strategies", "strategic", "plan", "plans", "roadmap",
        "initiative", "initiatives", "goal", "goals", "objective", "objectives",
    ],
    "brand": [
        "brand", "branding", "voice", "tone", "messaging", "identity",
        "guidelines", "style", "personality",
    ],
    "performance": [
        "kpi", "kpis", "metric", "metrics", "analytics", "report", "reports",
        "dashboard", "data", "trend", "trends", "growth",
    ],
    "calendar": [
        "calendar", "schedule", "timeline", "deadline", "deadlines", "event",
        "events", "launch", "launches", "date", "dates",
    ],
}

# Keywords that trigger campaign context loading
CAMPAIGN_KEYWORDS: list[str] = [
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
    return any(kw in message_lower for kw in CAMPAIGN_KEYWORDS)


def should_load_section(message: str, section: str) -> bool:
    """Check if message references a section that should be loaded.

    Args:
        message: User message to analyze
        section: Section name to check for

    Returns:
        True if message contains keywords for the section
    """
    if section not in SECTION_KEYWORDS:
        return False

    message_lower = message.lower()
    keywords = SECTION_KEYWORDS[section]

    return any(keyword in message_lower for keyword in keywords)


def format_context_markdown(data: dict[str, Any]) -> str:
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


def format_campaign_markdown(campaigns: list[dict[str, Any]]) -> str:
    """Format campaign data as markdown with YAML frontmatter.

    Mirrors the format_context_markdown pattern for organization context.

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
