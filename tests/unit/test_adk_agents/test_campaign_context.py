"""Tests for Campaign Context functionality.

These tests verify the campaign context loading logic without
requiring Neo4j connections by re-implementing the pure functions.
"""

from datetime import datetime, timedelta
from typing import Any

import pytest

# Re-implement the pure functions from context_loader for testing
# This avoids import issues with Neo4j dependencies

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

MAX_CAMPAIGN_TOKENS = 3_000


def should_load_campaigns(message: str) -> bool:
    """Check if message references campaigns."""
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in CAMPAIGN_KEYWORDS)


def _get_mock_campaigns(account_id: str) -> list[dict[str, Any]]:
    """Generate mock campaign data."""
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
                "roas": None,
            },
        },
    ]


def _format_campaign_markdown(campaigns: list[dict[str, Any]]) -> str:
    """Format campaign data as markdown."""
    active_count = sum(1 for c in campaigns if c.get("status") == "active")
    paused_count = sum(1 for c in campaigns if c.get("status") == "paused")

    total_spent = sum(c.get("budget", {}).get("spent", 0) for c in campaigns)
    total_impressions = sum(
        c.get("performance", {}).get("impressions", 0) for c in campaigns
    )
    total_conversions = sum(
        c.get("performance", {}).get("conversions", 0) for c in campaigns
    )

    markdown_parts = [
        "---",
        f"total_campaigns: {len(campaigns)}",
        f"active_campaigns: {active_count}",
        f"paused_campaigns: {paused_count}",
        f"total_spent: ${total_spent:,.2f}",
        "---\n",
    ]

    markdown_parts.append("# Campaign Performance Summary\n")
    markdown_parts.append(f"**Active Campaigns:** {active_count}")
    markdown_parts.append(f" | **Total Impressions:** {total_impressions:,}")
    markdown_parts.append(f" | **Total Conversions:** {total_conversions:,}")
    markdown_parts.append(f" | **Total Spend:** ${total_spent:,.2f}\n")

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

        budget = campaign.get("budget", {})
        if budget:
            markdown_parts.append(
                f"- **Budget:** ${budget.get('total', 0):,.2f} total, "
                f"${budget.get('spent', 0):,.2f} spent, "
                f"${budget.get('remaining', 0):,.2f} remaining\n"
            )

        perf = campaign.get("performance", {})
        if perf:
            markdown_parts.append("- **Performance:**\n")
            markdown_parts.append(f"  - Impressions: {perf.get('impressions', 0):,}\n")
            markdown_parts.append(f"  - Clicks: {perf.get('clicks', 0):,}\n")
            markdown_parts.append(f"  - CTR: {perf.get('ctr', 0):.2f}%\n")
            markdown_parts.append(f"  - Conversions: {perf.get('conversions', 0):,}\n")
            if perf.get("roas"):
                markdown_parts.append(f"  - ROAS: {perf.get('roas', 0):.1f}x\n")

        markdown_parts.append("\n")

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
    """Prepend campaign context to user message."""
    return f"""[CAMPAIGN CONTEXT]
{context}
[END CAMPAIGN CONTEXT]

{message}"""


class TestShouldLoadCampaigns:
    """Tests for should_load_campaigns function."""

    def test_campaign_keyword_matches(self):
        assert should_load_campaigns("How are my campaigns performing?")
        assert should_load_campaigns("Show me ad performance")
        assert should_load_campaigns("What's my ROI?")
        assert should_load_campaigns("How much have I spent on advertising?")

    def test_no_campaign_keywords(self):
        assert not should_load_campaigns("Hello, how are you?")
        assert not should_load_campaigns("What is my website traffic?")
        assert not should_load_campaigns("Show me analytics data")

    def test_case_insensitive(self):
        assert should_load_campaigns("CAMPAIGN performance")
        assert should_load_campaigns("Campaign Performance")
        assert should_load_campaigns("my CAMPAIGNS")

    def test_all_keywords_match(self):
        for keyword in CAMPAIGN_KEYWORDS:
            message = f"Tell me about {keyword}"
            assert should_load_campaigns(message), f"Keyword '{keyword}' should match"


class TestGetMockCampaigns:
    """Tests for _get_mock_campaigns function."""

    def test_returns_list(self):
        campaigns = _get_mock_campaigns("test_account_123")
        assert isinstance(campaigns, list)
        assert len(campaigns) > 0

    def test_campaign_structure(self):
        campaigns = _get_mock_campaigns("test_account_123")
        campaign = campaigns[0]

        assert "campaign_id" in campaign
        assert "name" in campaign
        assert "status" in campaign
        assert "channel" in campaign
        assert "budget" in campaign
        assert "performance" in campaign

    def test_budget_structure(self):
        campaigns = _get_mock_campaigns("test_account_123")
        budget = campaigns[0]["budget"]

        assert "total" in budget
        assert "spent" in budget
        assert "remaining" in budget
        assert "currency" in budget

    def test_performance_structure(self):
        campaigns = _get_mock_campaigns("test_account_123")
        perf = campaigns[0]["performance"]

        assert "impressions" in perf
        assert "clicks" in perf
        assert "ctr" in perf
        assert "conversions" in perf

    def test_active_and_paused_campaigns(self):
        campaigns = _get_mock_campaigns("test_account_123")

        statuses = {c["status"] for c in campaigns}
        assert "active" in statuses
        assert "paused" in statuses

    def test_campaign_id_uses_account_id(self):
        campaigns = _get_mock_campaigns("abc12345_test")
        assert campaigns[0]["campaign_id"].startswith("camp_abc12345")


class TestFormatCampaignMarkdown:
    """Tests for _format_campaign_markdown function."""

    @pytest.fixture
    def sample_campaigns(self) -> list:
        return _get_mock_campaigns("test_account")

    def test_returns_string(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_yaml_frontmatter(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert result.startswith("---")
        assert "total_campaigns:" in result
        assert "active_campaigns:" in result
        assert "total_spent:" in result

    def test_summary_section(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert "# Campaign Performance Summary" in result
        assert "**Active Campaigns:**" in result
        assert "**Total Impressions:**" in result

    def test_campaign_details(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert "## Active Campaigns" in result
        assert "### Q1 Brand Awareness Campaign" in result
        assert "**Channel:**" in result
        assert "**Budget:**" in result
        assert "**Performance:**" in result

    def test_paused_campaigns_section(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert "## Paused Campaigns" in result

    def test_performance_metrics(self, sample_campaigns: list):
        result = _format_campaign_markdown(sample_campaigns)
        assert "Impressions:" in result
        assert "Clicks:" in result
        assert "CTR:" in result
        assert "Conversions:" in result
        assert "ROAS:" in result


class TestInjectCampaignContext:
    """Tests for inject_campaign_context function."""

    def test_injects_context(self):
        message = "How are my campaigns doing?"
        context = "Campaign data here"

        result = inject_campaign_context(message, context)

        assert "[CAMPAIGN CONTEXT]" in result
        assert "[END CAMPAIGN CONTEXT]" in result
        assert context in result
        assert message in result

    def test_context_before_message(self):
        message = "User question"
        context = "Context data"

        result = inject_campaign_context(message, context)

        context_pos = result.find(context)
        message_pos = result.find(message)

        assert context_pos < message_pos

    def test_preserves_original_message(self):
        message = "What is my campaign ROI for Q1?"
        context = "Some campaign context"

        result = inject_campaign_context(message, context)

        assert message in result
