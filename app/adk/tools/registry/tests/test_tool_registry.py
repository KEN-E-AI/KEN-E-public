"""Tests for Tool Registry functionality."""

from pathlib import Path

import pytest

from ..tool_registry import (
    ToolNotFoundError,
    ToolRegistry,
    get_default_registry,
)
from ..tool_schema import ToolDefinition, ToolParameter, ToolPermission


class TestToolPermission:
    """Tests for ToolPermission model."""

    def test_create_required_permission(self):
        perm = ToolPermission(scope="analytics:read", required=True)
        assert perm.scope == "analytics:read"
        assert perm.required is True

    def test_create_optional_permission(self):
        perm = ToolPermission(scope="analytics:write", required=False)
        assert perm.scope == "analytics:write"
        assert perm.required is False

    def test_default_required_is_true(self):
        perm = ToolPermission(scope="analytics:read")
        assert perm.required is True

    def test_scope_is_required(self):
        with pytest.raises(ValueError):
            ToolPermission(scope="")


class TestToolParameter:
    """Tests for ToolParameter model."""

    def test_create_string_parameter(self):
        param = ToolParameter(
            name="property_id",
            type="string",
            description="GA4 property ID",
            required=True,
        )
        assert param.name == "property_id"
        assert param.type == "string"
        assert param.required is True
        assert param.default is None

    def test_create_parameter_with_default(self):
        param = ToolParameter(
            name="limit",
            type="integer",
            description="Number of results",
            required=False,
            default=10,
        )
        assert param.name == "limit"
        assert param.required is False
        assert param.default == 10

    def test_type_normalized_to_lowercase(self):
        param = ToolParameter(name="test", type="STRING", description="Test parameter")
        assert param.type == "string"

    def test_invalid_type_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported type"):
            ToolParameter(name="test", type="invalid", description="Test")

    def test_all_supported_types(self):
        valid_types = ["string", "integer", "number", "boolean", "array", "object"]
        for type_name in valid_types:
            param = ToolParameter(name="test", type=type_name, description="Test")
            assert param.type == type_name


class TestToolDefinition:
    """Tests for ToolDefinition model."""

    @pytest.fixture
    def sample_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="query_ga_report",
            description="Query Google Analytics for metrics",
            category="analytics",
            mcp_server="google_analytics_mcp",
            parameters=[
                ToolParameter(
                    name="property_id",
                    type="string",
                    description="GA4 property ID",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max results",
                    required=False,
                    default=100,
                ),
            ],
            permissions=[
                ToolPermission(scope="analytics:read", required=True),
            ],
            keywords=["analytics", "ga4", "traffic", "report"],
            estimated_tokens=250,
        )

    def test_tool_creation(self, sample_tool: ToolDefinition):
        assert sample_tool.name == "query_ga_report"
        assert sample_tool.category == "analytics"
        assert len(sample_tool.parameters) == 2
        assert len(sample_tool.permissions) == 1
        assert len(sample_tool.keywords) == 4
        assert sample_tool.estimated_tokens == 250

    def test_name_normalized_to_lowercase_underscores(self):
        tool = ToolDefinition(
            name="Get-GA-Report",
            description="Test",
            category="analytics",
        )
        assert tool.name == "get_ga_report"

    def test_category_normalized_to_lowercase(self):
        tool = ToolDefinition(
            name="test",
            description="Test",
            category="Analytics",
        )
        assert tool.category == "analytics"

    def test_keywords_normalized_to_lowercase(self):
        tool = ToolDefinition(
            name="test",
            description="Test",
            category="analytics",
            keywords=["GA4", "Traffic", "USERS"],
        )
        assert tool.keywords == ["ga4", "traffic", "users"]

    def test_has_required_params(self, sample_tool: ToolDefinition):
        required = sample_tool.has_required_params()
        assert required == ["property_id"]

    def test_has_permission(self, sample_tool: ToolDefinition):
        assert sample_tool.has_permission("analytics:read") is True
        assert sample_tool.has_permission("analytics:write") is False

    def test_default_values(self):
        tool = ToolDefinition(
            name="test",
            description="Test tool",
            category="test",
        )
        assert tool.mcp_server is None
        assert tool.parameters == []
        assert tool.permissions == []
        assert tool.keywords == []
        assert tool.estimated_tokens == 150
        assert tool.examples == []


class TestToolRegistry:
    """Tests for ToolRegistry service."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    @pytest.fixture
    def sample_tool(self) -> ToolDefinition:
        return ToolDefinition(
            name="test_tool",
            description="A test tool",
            category="testing",
            keywords=["test", "sample"],
            permissions=[ToolPermission(scope="test:read", required=True)],
        )

    def test_register_and_get_tool(
        self, registry: ToolRegistry, sample_tool: ToolDefinition
    ):
        registry.register_tool(sample_tool)
        retrieved = registry.get_tool("test_tool")
        assert retrieved == sample_tool

    def test_get_nonexistent_tool_returns_none(self, registry: ToolRegistry):
        assert registry.get_tool("nonexistent") is None

    def test_get_tool_or_raise(
        self, registry: ToolRegistry, sample_tool: ToolDefinition
    ):
        registry.register_tool(sample_tool)

        # Should return tool when exists
        tool = registry.get_tool_or_raise("test_tool")
        assert tool == sample_tool

        # Should raise when not found
        with pytest.raises(ToolNotFoundError):
            registry.get_tool_or_raise("nonexistent")

    def test_get_tool_normalizes_name(
        self, registry: ToolRegistry, sample_tool: ToolDefinition
    ):
        registry.register_tool(sample_tool)

        # All these should find the same tool
        assert registry.get_tool("test_tool") == sample_tool
        assert registry.get_tool("Test-Tool") == sample_tool
        assert registry.get_tool("test tool") == sample_tool

    def test_list_tools(self, registry: ToolRegistry, sample_tool: ToolDefinition):
        registry.register_tool(sample_tool)

        tool2 = ToolDefinition(
            name="another_tool",
            description="Another test",
            category="testing",
        )
        registry.register_tool(tool2)

        tools = registry.list_tools()
        assert len(tools) == 2
        assert sample_tool in tools
        assert tool2 in tools

    def test_list_by_category(self, registry: ToolRegistry):
        analytics_tool = ToolDefinition(
            name="analytics_tool",
            description="Analytics",
            category="analytics",
        )
        content_tool = ToolDefinition(
            name="content_tool",
            description="Content",
            category="content",
        )

        registry.register_tool(analytics_tool)
        registry.register_tool(content_tool)

        analytics_tools = registry.list_by_category("analytics")
        assert len(analytics_tools) == 1
        assert analytics_tools[0] == analytics_tool

        content_tools = registry.list_by_category("content")
        assert len(content_tools) == 1
        assert content_tools[0] == content_tool

    def test_search_by_keyword(self, registry: ToolRegistry):
        tool1 = ToolDefinition(
            name="ga_report",
            description="GA report",
            category="analytics",
            keywords=["analytics", "ga4", "report"],
        )
        tool2 = ToolDefinition(
            name="ads_report",
            description="Ads report",
            category="advertising",
            keywords=["ads", "report"],
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)

        # Search for "report" should find both
        report_tools = registry.search_by_keyword("report")
        assert len(report_tools) == 2

        # Search for "analytics" should find only tool1
        analytics_tools = registry.search_by_keyword("analytics")
        assert len(analytics_tools) == 1
        assert analytics_tools[0] == tool1

    def test_search(self, registry: ToolRegistry):
        tool1 = ToolDefinition(
            name="query_ga_report",
            description="Query Google Analytics for traffic metrics",
            category="analytics",
            keywords=["analytics", "ga4", "traffic", "report"],
        )
        tool2 = ToolDefinition(
            name="list_ga_accounts",
            description="List GA accounts",
            category="analytics",
            keywords=["analytics", "accounts", "list"],
        )
        tool3 = ToolDefinition(
            name="get_ads_performance",
            description="Get ads performance",
            category="advertising",
            keywords=["ads", "performance"],
        )

        registry.register_tool(tool1)
        registry.register_tool(tool2)
        registry.register_tool(tool3)

        # Search for "traffic" should find tool1
        results = registry.search("traffic")
        assert len(results) >= 1
        assert results[0] == tool1

        # Search for "analytics" should find both analytics tools
        results = registry.search("analytics")
        assert len(results) >= 2

    def test_validate_permissions(
        self, registry: ToolRegistry, sample_tool: ToolDefinition
    ):
        registry.register_tool(sample_tool)

        # User with required permission
        assert registry.validate_permissions("test_tool", ["test:read"]) is True

        # User without required permission
        assert registry.validate_permissions("test_tool", ["other:read"]) is False

        # Nonexistent tool
        assert registry.validate_permissions("nonexistent", ["test:read"]) is False

    def test_filter_by_permissions(self, registry: ToolRegistry):
        tool1 = ToolDefinition(
            name="tool1",
            description="Tool 1",
            category="test",
            permissions=[ToolPermission(scope="scope_a", required=True)],
        )
        tool2 = ToolDefinition(
            name="tool2",
            description="Tool 2",
            category="test",
            permissions=[ToolPermission(scope="scope_b", required=True)],
        )
        tool3 = ToolDefinition(
            name="tool3",
            description="Tool 3",
            category="test",
            permissions=[
                ToolPermission(scope="scope_a", required=True),
                ToolPermission(scope="scope_b", required=True),
            ],
        )

        all_tools = [tool1, tool2, tool3]

        # User with scope_a can access tool1 and needs both for tool3
        filtered = registry.filter_by_permissions(all_tools, ["scope_a"])
        assert len(filtered) == 1
        assert tool1 in filtered

        # User with both scopes can access all
        filtered = registry.filter_by_permissions(all_tools, ["scope_a", "scope_b"])
        assert len(filtered) == 3

    def test_get_categories(self, registry: ToolRegistry):
        tool1 = ToolDefinition(name="tool1", description="Test", category="analytics")
        tool2 = ToolDefinition(name="tool2", description="Test", category="advertising")
        tool3 = ToolDefinition(name="tool3", description="Test", category="analytics")

        registry.register_tool(tool1)
        registry.register_tool(tool2)
        registry.register_tool(tool3)

        categories = registry.get_categories()
        assert set(categories) == {"analytics", "advertising"}

    def test_count(self, registry: ToolRegistry, sample_tool: ToolDefinition):
        assert registry.count() == 0

        registry.register_tool(sample_tool)
        assert registry.count() == 1

        tool2 = ToolDefinition(name="another", description="Another", category="test")
        registry.register_tool(tool2)
        assert registry.count() == 2

    def test_clear(self, registry: ToolRegistry, sample_tool: ToolDefinition):
        registry.register_tool(sample_tool)
        assert registry.count() == 1

        registry.clear()
        assert registry.count() == 0
        assert registry.get_tool("test_tool") is None


class TestLoadFromConfig:
    """Tests for loading tools from YAML configuration."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    def test_load_default_config(self, registry: ToolRegistry):
        config_path = Path(__file__).parent.parent / "config" / "tools.yaml"
        loaded = registry.load_from_config(config_path)

        # 8 GA tools + at least one function tool (create_visualization)
        assert loaded >= 9

        # GA tool: source=mcp, mcp_server set
        tool = registry.get_tool("query_ga_report")
        assert tool is not None
        assert tool.category == "analytics"
        assert tool.source == "mcp"
        assert tool.mcp_server == "google_analytics_mcp"
        assert "analytics:read" in [p.scope for p in tool.permissions]

        # Function tool: source=function, default_global=True, no mcp_server
        viz = registry.get_tool("create_visualization")
        assert viz is not None
        assert viz.source == "function"
        assert viz.default_global is True
        assert viz.mcp_server is None

    def test_load_nonexistent_config_raises(self, registry: ToolRegistry):
        with pytest.raises(FileNotFoundError):
            registry.load_from_config("/nonexistent/path.yaml")

    def test_load_function_tools_section(self, registry: ToolRegistry, tmp_path: Path):
        config = tmp_path / "tools.yaml"
        config.write_text(
            "tools:\n"
            "  - name: query_ga_report\n"
            "    description: Query GA\n"
            "    category: analytics\n"
            "    mcp_server: google_analytics_mcp\n"
            "function_tools:\n"
            "  - name: create_visualization\n"
            "    description: Render a chart\n"
            "    category: visualization\n"
            "    default_global: true\n"
        )
        loaded = registry.load_from_config(config)
        assert loaded == 2

        ga = registry.get_tool("query_ga_report")
        assert ga is not None and ga.source == "mcp"
        assert ga.default_global is False

        viz = registry.get_tool("create_visualization")
        assert viz is not None and viz.source == "function"
        assert viz.default_global is True
        assert viz.mcp_server is None

    def test_function_tool_section_ignores_stray_mcp_server(
        self, registry: ToolRegistry, tmp_path: Path
    ):
        # A YAML author mistakenly putting `mcp_server:` inside `function_tools:`
        # would otherwise trip the source-consistency validator. The loader scrubs
        # the field on the way in so the entry still registers cleanly.
        config = tmp_path / "tools.yaml"
        config.write_text(
            "function_tools:\n"
            "  - name: create_visualization\n"
            "    description: Render a chart\n"
            "    category: visualization\n"
            "    mcp_server: stray_value\n"
        )
        loaded = registry.load_from_config(config)
        assert loaded == 1
        viz = registry.get_tool("create_visualization")
        assert viz is not None
        assert viz.source == "function"
        assert viz.mcp_server is None


class TestSourceAndDefaultGlobal:
    """Tests for the `source` + `default_global` fields on ToolDefinition."""

    def test_default_source_is_mcp(self):
        tool = ToolDefinition(name="t", description="d", category="c")
        assert tool.source == "mcp"
        assert tool.default_global is False

    def test_function_tool_with_default_global(self):
        tool = ToolDefinition(
            name="create_visualization",
            description="Render a chart",
            category="visualization",
            source="function",
            default_global=True,
        )
        assert tool.source == "function"
        assert tool.default_global is True
        assert tool.mcp_server is None

    def test_function_source_rejects_mcp_server(self):
        with pytest.raises(ValueError, match="source='function' requires mcp_server=None"):
            ToolDefinition(
                name="t",
                description="d",
                category="c",
                source="function",
                mcp_server="some_server",
            )

    def test_default_global_rejects_mcp_source(self):
        with pytest.raises(ValueError, match="default_global=True is only allowed"):
            ToolDefinition(
                name="t",
                description="d",
                category="c",
                mcp_server="some_server",
                default_global=True,
            )


class TestListByKindHelpers:
    """Tests for list_mcp_tools / list_function_tools / list_default_global_tools."""

    @pytest.fixture
    def loaded_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register_tool(
            ToolDefinition(
                name="mcp_a",
                description="d",
                category="c",
                mcp_server="server_a",
            )
        )
        registry.register_tool(
            ToolDefinition(
                name="fn_a",
                description="d",
                category="c",
                source="function",
                default_global=True,
            )
        )
        registry.register_tool(
            ToolDefinition(
                name="fn_b",
                description="d",
                category="c",
                source="function",
            )
        )
        return registry

    def test_list_mcp_tools(self, loaded_registry: ToolRegistry):
        assert [t.name for t in loaded_registry.list_mcp_tools()] == ["mcp_a"]

    def test_list_function_tools(self, loaded_registry: ToolRegistry):
        assert sorted(t.name for t in loaded_registry.list_function_tools()) == [
            "fn_a",
            "fn_b",
        ]

    def test_list_default_global_tools(self, loaded_registry: ToolRegistry):
        assert [t.name for t in loaded_registry.list_default_global_tools()] == ["fn_a"]


class TestGetIndexForContext:
    """Tests for get_index_for_context method."""

    @pytest.fixture
    def registry_with_tools(self) -> ToolRegistry:
        """Create a registry with multiple tools across categories."""
        registry = ToolRegistry()

        # Analytics tools
        registry.register_tool(
            ToolDefinition(
                name="query_ga_report",
                description="Query Google Analytics for website traffic metrics and user behavior data",
                category="analytics",
                keywords=["analytics", "ga4", "traffic"],
            )
        )
        registry.register_tool(
            ToolDefinition(
                name="list_ga_accounts",
                description="List all Google Analytics accounts and properties",
                category="analytics",
                keywords=["analytics", "accounts"],
            )
        )

        # Advertising tools
        registry.register_tool(
            ToolDefinition(
                name="get_ads_performance",
                description="Get performance metrics for advertising campaigns including CTR and conversions",
                category="advertising",
                keywords=["ads", "performance", "campaigns"],
            )
        )

        # Content tools
        registry.register_tool(
            ToolDefinition(
                name="generate_content",
                description="Generate marketing content for various channels",
                category="content",
                keywords=["content", "generation", "marketing"],
            )
        )

        return registry

    def test_get_index_for_context_returns_string(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that get_index_for_context returns a non-empty string."""
        index = registry_with_tools.get_index_for_context()

        assert isinstance(index, str)
        assert len(index) > 0

    def test_get_index_for_context_contains_categories(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that index contains category headers."""
        index = registry_with_tools.get_index_for_context()

        assert "### Advertising" in index
        assert "### Analytics" in index
        assert "### Content" in index

    def test_get_index_for_context_contains_tool_names(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that index contains tool names."""
        index = registry_with_tools.get_index_for_context()

        assert "query_ga_report" in index
        assert "list_ga_accounts" in index
        assert "get_ads_performance" in index
        assert "generate_content" in index

    def test_get_index_for_context_truncates_long_descriptions(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that descriptions longer than 80 chars are truncated."""
        # Add tool with very long description
        long_desc = "A" * 200  # 200 character description
        registry_with_tools.register_tool(
            ToolDefinition(
                name="long_desc_tool",
                description=long_desc,
                category="testing",
            )
        )

        index = registry_with_tools.get_index_for_context()

        # Should contain truncated version with ...
        assert "..." in index
        # Should NOT contain full 200 char description
        assert long_desc not in index

    def test_get_index_for_context_sorted_categories(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that categories are sorted alphabetically."""
        index = registry_with_tools.get_index_for_context()

        # Find positions of category headers
        advertising_pos = index.find("### Advertising")
        analytics_pos = index.find("### Analytics")
        content_pos = index.find("### Content")

        # Verify alphabetical order
        assert advertising_pos < analytics_pos < content_pos

    def test_get_index_for_context_empty_registry(self):
        """Test get_index_for_context with empty registry."""
        registry = ToolRegistry()

        index = registry.get_index_for_context()

        assert "## Available Tool Categories" in index
        assert "Use `search_tools`" in index

    def test_get_index_for_context_includes_usage_hint(
        self, registry_with_tools: ToolRegistry
    ):
        """Test that index includes hint about search_tools."""
        index = registry_with_tools.get_index_for_context()

        assert "Use `search_tools` to find specific tools by keyword" in index


class TestDefaultRegistry:
    """Tests for default registry singleton."""

    def test_get_default_registry(self):
        registry = get_default_registry()
        assert registry is not None
        assert isinstance(registry, ToolRegistry)

        # Should have loaded tools from default config
        assert registry.count() > 0

    def test_default_registry_is_singleton(self):
        registry1 = get_default_registry()
        registry2 = get_default_registry()
        assert registry1 is registry2
