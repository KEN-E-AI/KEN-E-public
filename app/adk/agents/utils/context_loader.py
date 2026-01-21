"""Organization context loading utilities.

This module loads organization-specific context (Account + Brand Voice/Tone)
from Neo4j and formats it for injection into agent messages.

Phase 1 scope: Account Info + Brand Voice/Tone (~1,500 tokens)
Future: Will expand to include Strategy, Competitors, Customer Profiles
"""

import logging

from ..strategy_agent.neo4j_tools import Neo4jConnection
from ..strategy_agent.token_utils import TokenEstimator

logger = logging.getLogger(__name__)

# Token budget for Level 1 context (Account + Brand)
MAX_CONTEXT_TOKENS = 5_000


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
            logger.warning(f"No context data found for account_id: {account_id}")
            return None

        # 2. Format as markdown
        context_markdown = _format_context_markdown(context_data)

        # 3. Validate token budget
        token_info = TokenEstimator.check_input_limit(
            context_markdown, raise_on_exceed=False
        )

        # 4. Log metrics
        logger.info(
            f"Loaded organization context for {account_id}: "
            f"{token_info['estimated_tokens']} tokens "
            f"({token_info['percentage']:.1f}% of input limit, "
            f"{(token_info['estimated_tokens'] / MAX_CONTEXT_TOKENS) * 100:.1f}% of context budget)"
        )

        # 5. Check if within context budget
        if token_info["estimated_tokens"] > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Context exceeds budget: {token_info['estimated_tokens']} > {MAX_CONTEXT_TOKENS} tokens"
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
