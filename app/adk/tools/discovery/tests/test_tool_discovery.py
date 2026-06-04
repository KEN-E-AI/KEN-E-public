"""Tests for Tool Discovery functionality."""

from unittest.mock import MagicMock

import pytest

from ...registry.tool_registry import ToolRegistry
from ...registry.tool_schema import ToolDefinition, ToolParameter, ToolPermission
from ..discover_tools import (
    discover_tools,
    get_tool_details,
    list_tool_categories,
)
from ..tool_discovery import ToolDiscoveryService, ToolSearchResult


class TestToolSearchResult:
    """Tests for ToolSearchResult dataclass."""

    @pytest.fixture
    def sample_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="run_report_mt",
            description="Query Google Analytics for metrics",
            category="analytics",
            parameters=[
                ToolParameter(
                    name="property_id",
                    type="string",
                    description="GA4 property ID",
                    required=True,
                ),
            ],
            permissions=[ToolPermission(scope="analytics:read", required=True)],
            examples=["Show me website traffic"],
        )

    def test_to_dict(self, sample_tool: ToolDefinition):
        result = ToolSearchResult(
            tool=sample_tool,
            score=15.0,
            match_reasons=["keyword match: analytics", "name contains: ga"],
        )

        result_dict = result.to_dict()

        assert result_dict["name"] == "run_report_mt"
        assert result_dict["description"] == "Query Google Analytics for metrics"
        assert result_dict["category"] == "analytics"
        assert result_dict["score"] == 15.0
        assert "keyword match: analytics" in result_dict["match_reasons"]
        assert len(result_dict["parameters"]) == 1
        assert result_dict["permissions"] == ["analytics:read"]


class TestToolDiscoveryService:
    """Tests for ToolDiscoveryService."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        registry = ToolRegistry()

        # Add test tools
        registry.register_tool(
            ToolDefinition(
                name="run_report_mt",
                description="Query Google Analytics for traffic metrics",
                category="analytics",
                keywords=["analytics", "ga4", "traffic", "report"],
                permissions=[ToolPermission(scope="analytics:read", required=True)],
                examples=["Show me website traffic"],
            )
        )

        registry.register_tool(
            ToolDefinition(
                name="get_account_summaries_mt",
                description="List GA accounts",
                category="analytics",
                keywords=["analytics", "accounts", "list"],
                permissions=[ToolPermission(scope="analytics:read", required=True)],
            )
        )

        registry.register_tool(
            ToolDefinition(
                name="get_ads_performance",
                description="Get advertising performance metrics",
                category="advertising",
                keywords=["ads", "performance", "metrics"],
                permissions=[ToolPermission(scope="ads:read", required=True)],
            )
        )

        return registry

    @pytest.fixture
    def discovery(self, registry: ToolRegistry) -> ToolDiscoveryService:
        return ToolDiscoveryService(registry=registry)

    def test_search_by_keyword(self, discovery: ToolDiscoveryService):
        results = discovery.search("analytics")

        # Should find both analytics tools
        assert len(results) == 2
        tool_names = [r.tool.name for r in results]
        assert "run_report_mt" in tool_names
        assert "get_account_summaries_mt" in tool_names

    def test_search_returns_sorted_by_score(self, discovery: ToolDiscoveryService):
        results = discovery.search("traffic analytics")

        # run_report_mt should score higher (has both keywords)
        assert len(results) >= 1
        assert results[0].tool.name == "run_report_mt"
        assert results[0].score > results[1].score if len(results) > 1 else True

    def test_search_with_limit(self, discovery: ToolDiscoveryService):
        results = discovery.search("analytics", limit=1)
        assert len(results) == 1

    def test_search_with_category_filter(self, discovery: ToolDiscoveryService):
        results = discovery.search("performance", category="advertising")

        assert len(results) == 1
        assert results[0].tool.name == "get_ads_performance"

    def test_search_with_permissions_filter(self, discovery: ToolDiscoveryService):
        # User only has analytics permissions
        results = discovery.search(
            "performance metrics", user_permissions=["analytics:read"]
        )

        # Should only find analytics tools, not ads tool
        tool_names = [r.tool.name for r in results]
        assert "get_ads_performance" not in tool_names

    def test_search_no_results(self, discovery: ToolDiscoveryService):
        results = discovery.search("nonexistent feature")
        assert results == []

    def test_filter_by_connected_accounts(self, discovery: ToolDiscoveryService):
        all_tools = discovery._registry.list_tools()

        # User with Google Analytics connected
        filtered = discovery.filter_by_connected_accounts(
            tools=all_tools, connected_accounts=["google_analytics"]
        )

        tool_names = [t.name for t in filtered]
        assert "run_report_mt" in tool_names
        assert "get_account_summaries_mt" in tool_names
        assert "get_ads_performance" not in tool_names

    def test_filter_by_connected_accounts_multiple(
        self, discovery: ToolDiscoveryService
    ):
        all_tools = discovery._registry.list_tools()

        # User with multiple accounts connected
        filtered = discovery.filter_by_connected_accounts(
            tools=all_tools, connected_accounts=["google_analytics", "google_ads"]
        )

        assert len(filtered) == 3

    def test_filter_by_connected_accounts_none(self, discovery: ToolDiscoveryService):
        filtered = discovery.filter_by_connected_accounts(connected_accounts=None)
        assert filtered == []

    def test_list_by_category(self, discovery: ToolDiscoveryService):
        analytics_tools = discovery.list_by_category("analytics")
        assert len(analytics_tools) == 2

        ads_tools = discovery.list_by_category("advertising")
        assert len(ads_tools) == 1

    def test_get_tool_info(self, discovery: ToolDiscoveryService):
        info = discovery.get_tool_info("run_report_mt")

        assert info is not None
        assert info["name"] == "run_report_mt"
        assert info["category"] == "analytics"
        assert len(info["permissions"]) == 1

    def test_get_tool_info_not_found(self, discovery: ToolDiscoveryService):
        info = discovery.get_tool_info("nonexistent")
        assert info is None

    def test_get_categories(self, discovery: ToolDiscoveryService):
        categories = discovery.get_categories()
        assert set(categories) == {"analytics", "advertising"}

    def test_suggest_tools(self, discovery: ToolDiscoveryService):
        suggestions = discovery.suggest_tools(
            intent="analyze website traffic",
            connected_accounts=["google_analytics"],
            limit=3,
        )

        assert len(suggestions) >= 1
        # Should prioritize traffic-related tools
        assert suggestions[0].tool.name == "run_report_mt"


class TestDiscoverToolsAgent:
    """Tests for discover_tools agent function."""

    def test_discover_tools_basic(self):
        result = discover_tools("analytics")

        assert "analytics" in result.lower()
        assert "run_report_mt" in result or "Tools matching" in result

    def test_discover_tools_with_category(self):
        result = discover_tools("report", category="analytics")

        assert "analytics" in result.lower()

    def test_discover_tools_no_results(self):
        result = discover_tools("nonexistent feature xyz123")

        assert "No tools found" in result

    def test_discover_tools_with_context(self):
        # Mock tool context with connected accounts
        mock_context = MagicMock()
        mock_context.state = {"connected_accounts": ["google_analytics"]}

        result = discover_tools("analytics", tool_context=mock_context)

        assert "analytics" in result.lower()


class TestListToolCategories:
    """Tests for list_tool_categories function."""

    def test_list_categories(self):
        result = list_tool_categories()

        assert "analytics" in result.lower()
        assert "advertising" in result.lower() or "Available Tool Categories" in result


class TestGetToolDetails:
    """Tests for get_tool_details function."""

    def test_get_details_existing_tool(self):
        result = get_tool_details("run_report_mt")

        assert "run_report_mt" in result
        assert "Description" in result

    def test_get_details_nonexistent_tool(self):
        result = get_tool_details("nonexistent_tool")

        assert "not found" in result.lower()
