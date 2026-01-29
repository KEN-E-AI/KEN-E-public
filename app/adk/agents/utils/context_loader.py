"""Organization and campaign context loading utilities.

This module loads context from Neo4j and formats it for injection into agent messages:
- Organization context: Account Info + Brand Voice/Tone
- Campaign context: Active campaigns with performance metrics (on-demand)

Phase 1 scope: Account Info + Brand Voice/Tone (~1,500 tokens)
Phase 2 scope: Campaign context with mock data (~3,000 tokens)
Future: Will expand to include Strategy, Competitors, Customer Profiles

New in Sprint 2: HierarchicalContextManager class for managing context hierarchy
with 3 levels (executive summary, sections, details).
"""

from datetime import datetime, timedelta
from typing import Any, ClassVar

from shared.context_utils import (
    format_campaign_markdown as _format_campaign_markdown,
)
from shared.context_utils import (
    format_context_markdown as _format_context_markdown,
)
from shared.context_utils import (
    inject_organization_context,
    should_load_section,
)
from shared.structured_logging import get_structured_logger, log_context
from shared.token_utils import TokenEstimator

from ..strategy_agent.neo4j_tools import Neo4jConnection

logger = get_structured_logger(__name__)

# Token budget for Level 1 context (Account + Brand)
MAX_CONTEXT_TOKENS = 5_000

# Token budget for campaign context
MAX_CAMPAIGN_TOKENS = 3_000


class HierarchicalContextManager:
    """Manages hierarchical loading of company context to optimize token usage.

    Implements 3-level hierarchy:
    - Level 1: Executive Summary (~5,000 tokens) - Always loaded
    - Level 2: Section Summaries (~10,000 tokens each) - Loaded on request
    - Level 3: Full Detail (~20,000 tokens each) - Loaded for specific tasks

    Example:
        >>> manager = HierarchicalContextManager("account_123")
        >>> manager.load_executive_summary()
        >>> if manager.should_load_section(user_message, "campaigns"):
        ...     manager.load_section("campaigns")
        >>> formatted_input = manager.inject_context(user_message)
    """

    AVAILABLE_SECTIONS: ClassVar[list[str]] = [
        "products", "icps", "competitors", "campaigns",
        "strategies", "brand", "performance", "calendar"
    ]

    MAX_EXECUTIVE_TOKENS: ClassVar[int] = 5_000
    MAX_SECTION_TOKENS: ClassVar[int] = 10_000
    MAX_DETAIL_TOKENS: ClassVar[int] = 20_000

    def __init__(self, account_id: str) -> None:
        """Initialize context manager for an account.

        Args:
            account_id: Account identifier for loading context
        """
        self.account_id = account_id
        self._executive_summary: str | None = None
        self._loaded_sections: dict[str, str] = {}
        self._loaded_details: dict[str, str] = {}
        self._total_tokens = 0

    def load_executive_summary(self) -> str | None:
        """Load Level 1 context (org + brand). Always call this first.

        Returns:
            Formatted markdown context string, or None if loading fails
        """
        try:
            # Fetch from Neo4j
            context_data = _fetch_context_from_neo4j(self.account_id)

            if not context_data:
                logger.warning(
                    "No executive summary data found",
                    extra=log_context(
                        component="hierarchical_context",
                        action="load_executive_summary",
                        account_id=self.account_id,
                        success=False,
                        error_message="No data in Neo4j",
                    ),
                )
                return None

            # Format as markdown
            context_markdown = _format_context_markdown(context_data)

            # Estimate tokens
            token_info = TokenEstimator.check_input_limit(
                context_markdown, raise_on_exceed=False
            )

            self._executive_summary = context_markdown
            self._total_tokens = token_info["estimated_tokens"]

            logger.info(
                "Loaded executive summary",
                extra=log_context(
                    component="hierarchical_context",
                    action="load_executive_summary",
                    account_id=self.account_id,
                    token_count=self._total_tokens,
                    success=True,
                ),
            )

            return context_markdown

        except Exception as e:
            logger.error(
                f"Failed to load executive summary: {e}",
                exc_info=True,
            )
            return None

    def load_section(self, section_name: str) -> str | None:
        """Load Level 2 section on demand (e.g., 'campaigns', 'products').

        Args:
            section_name: One of AVAILABLE_SECTIONS

        Returns:
            Formatted section context, or None if invalid/unavailable
        """
        if section_name not in self.AVAILABLE_SECTIONS:
            logger.warning(f"Invalid section name: {section_name}")
            return None

        # Currently only campaigns section is implemented
        if section_name == "campaigns":
            campaign_data = _fetch_campaigns_from_neo4j(self.account_id)
            if campaign_data:
                context = _format_campaign_markdown(campaign_data)
                self._loaded_sections[section_name] = context

                # Update token count
                token_info = TokenEstimator.check_input_limit(
                    context, raise_on_exceed=False
                )
                self._total_tokens += token_info["estimated_tokens"]

                logger.info(
                    f"Loaded section: {section_name}",
                    extra=log_context(
                        component="hierarchical_context",
                        action="load_section",
                        account_id=self.account_id,
                        success=True,
                        extra={"section": section_name},
                    ),
                )
                return context

        # Other sections not yet implemented - return None
        logger.info(f"Section {section_name} not yet implemented")
        return None

    def load_detail(self, detail_key: str) -> str | None:
        """Load Level 3 full detail for specific entity.

        Args:
            detail_key: Identifier for the detail (e.g., campaign_id)

        Returns:
            Detailed context, or None if unavailable

        Note:
            Level 3 loading requires Neo4j schema for detailed entities.
            Currently returns None - to be implemented in future sprints.
        """
        # Not yet implemented - requires Neo4j schema for detailed entities
        logger.info(f"Detail loading not yet implemented for: {detail_key}")
        return None

    def unload_section(self, section_name: str) -> None:
        """Unload section to free tokens.

        Args:
            section_name: Name of section to unload
        """
        if section_name in self._loaded_sections:
            del self._loaded_sections[section_name]
            logger.debug(f"Unloaded section: {section_name}")

    def unload_all_sections(self) -> None:
        """Unload all sections, keep only executive summary."""
        self._loaded_sections.clear()
        self._loaded_details.clear()
        logger.debug("Unloaded all sections and details")

    def get_total_tokens(self) -> int:
        """Get current token usage across all loaded context.

        Returns:
            Estimated total tokens for all loaded context
        """
        return self._total_tokens

    def get_context_for_agent(self) -> str:
        """Get all currently loaded context formatted for agent injection.

        Returns:
            Combined context string (executive summary + loaded sections)
        """
        parts = []

        if self._executive_summary:
            parts.append(self._executive_summary)

        for section_name in sorted(self._loaded_sections.keys()):
            parts.append(self._loaded_sections[section_name])

        for detail_key in sorted(self._loaded_details.keys()):
            parts.append(self._loaded_details[detail_key])

        return "\n\n".join(parts)

    def inject_context(self, message: str) -> str:
        """Inject all loaded context into a message.

        Args:
            message: Original user message

        Returns:
            Message with context injected, or original message if no context
        """
        context = self.get_context_for_agent()
        if not context:
            return message

        return inject_organization_context(message, context)

    # Delegate to shared pure function
    should_load_section = staticmethod(should_load_section)


def load_organization_context(account_id: str) -> str | None:
    """Load and validate organization context for an account.

    Loads Account info and Brand Voice/Tone from Neo4j, formats as markdown,
    and validates token budget.

    Note:
        For new code, prefer using HierarchicalContextManager.load_executive_summary()
        which provides better token management and section-based loading.

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


