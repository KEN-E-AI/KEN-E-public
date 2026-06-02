"""Tool Registry service for managing tool definitions.

The Tool Registry is a metadata catalog that describes available tools.
It does NOT replace or change how agents invoke tools - agents continue
to use their existing tool implementations (e.g., GAMCPClient for GA tools).

The registry enables:
- Tool Discovery: Query what tools are available
- Permission Checking: Verify user has required scopes
- Documentation: Describe tool capabilities without reading code
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from .tool_schema import ToolDefinition, ToolParameter, ToolPermission

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Base exception for tool registry errors."""

    pass


class ToolNotFoundError(ToolRegistryError):
    """Raised when a tool is not found in the registry."""

    pass


class ToolValidationError(ToolRegistryError):
    """Raised when tool definition fails validation."""

    pass


class ToolRegistry:
    """Central registry for tool definitions.

    Provides registration, lookup, and filtering of tool metadata.
    Tools are loaded from YAML configuration files.

    Example:
        >>> registry = ToolRegistry()
        >>> registry.load_from_config("tools.yaml")
        >>> tool = registry.get_tool("list_ga_accounts")
        >>> if tool:
        ...     print(f"Tool: {tool.name}, Category: {tool.category}")
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, ToolDefinition] = {}
        self._categories: dict[str, list[str]] = {}
        self._keyword_index: dict[str, list[str]] = {}

    def load_from_config(self, config_path: str | Path) -> int:
        """Load tool definitions from YAML configuration file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Number of tools loaded

        Raises:
            FileNotFoundError: If config file doesn't exist
            ToolValidationError: If tool definition is invalid
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config or not any(
            section in config for section in ("tools", "function_tools", "agent_tools")
        ):
            logger.warning(f"No tools defined in {config_path}")
            return 0

        loaded_count = 0
        for tool_data in config.get("tools") or []:
            try:
                tool = self._parse_tool_definition(tool_data, source="mcp")
                self.register_tool(tool)
                loaded_count += 1
            except Exception as e:
                tool_name = tool_data.get("name", "unknown")
                logger.error(f"Failed to load tool '{tool_name}': {e}")

        for tool_data in config.get("function_tools") or []:
            try:
                tool = self._parse_tool_definition(tool_data, source="function")
                self.register_tool(tool)
                loaded_count += 1
            except Exception as e:
                tool_name = tool_data.get("name", "unknown")
                logger.error(f"Failed to load function tool '{tool_name}': {e}")

        for tool_data in config.get("agent_tools") or []:
            try:
                tool = self._parse_tool_definition(tool_data, source="agent")
                self.register_tool(tool)
                loaded_count += 1
            except Exception as e:
                tool_name = tool_data.get("name", "unknown")
                logger.error(f"Failed to load agent tool '{tool_name}': {e}")

        logger.info(f"Loaded {loaded_count} tools from {config_path}")
        return loaded_count

    def _parse_tool_definition(
        self, data: dict[str, Any], *, source: str = "mcp"
    ) -> ToolDefinition:
        """Parse tool definition from raw dict data.

        Args:
            data: Raw tool data from YAML

        Returns:
            Validated ToolDefinition

        Raises:
            ToolValidationError: If data fails validation
        """
        try:
            # Parse parameters
            parameters = []
            for param_data in data.get("parameters", []):
                parameters.append(ToolParameter(**param_data))

            # Parse permissions
            permissions = []
            for perm_data in data.get("permissions", []):
                permissions.append(ToolPermission(**perm_data))

            # Function tools live in a different YAML section and are never bound
            # to an MCP server, so we ignore any stray `mcp_server` field from
            # function-tool entries and force `source` from the loader argument.
            mcp_server = data.get("mcp_server") if source == "mcp" else None
            return ToolDefinition(
                name=data["name"],
                description=data["description"],
                category=data["category"],
                mcp_server=mcp_server,
                source=source,  # type: ignore[arg-type]
                default_global=bool(data.get("default_global", False)),
                parameters=parameters,
                permissions=permissions,
                keywords=data.get("keywords", []),
                estimated_tokens=data.get("estimated_tokens", 150),
                examples=data.get("examples", []),
            )
        except Exception as e:
            raise ToolValidationError(f"Invalid tool definition: {e}") from e

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool definition in the registry.

        Args:
            tool: Tool definition to register

        Raises:
            ToolValidationError: If tool with same name already exists
        """
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")

        self._tools[tool.name] = tool

        # Update category index
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        if tool.name not in self._categories[tool.category]:
            self._categories[tool.category].append(tool.name)

        # Update keyword index
        for keyword in tool.keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            if tool.name not in self._keyword_index[keyword]:
                self._keyword_index[keyword].append(tool.name)

        logger.debug(f"Registered tool: {tool.name} (category: {tool.category})")

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Get tool by name.

        Args:
            name: Tool identifier

        Returns:
            ToolDefinition if found, None otherwise
        """
        normalized_name = name.lower().replace("-", "_").replace(" ", "_")
        return self._tools.get(normalized_name)

    def get_tool_or_raise(self, name: str) -> ToolDefinition:
        """Get tool by name, raising if not found.

        Args:
            name: Tool identifier

        Returns:
            ToolDefinition

        Raises:
            ToolNotFoundError: If tool not in registry
        """
        tool = self.get_tool(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool not found: {name}")
        return tool

    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools.

        Returns:
            List of all tool definitions
        """
        return list(self._tools.values())

    def list_mcp_tools(self) -> list[ToolDefinition]:
        """List tools delivered by an MCP server (``source == "mcp"``)."""
        return [t for t in self._tools.values() if t.source == "mcp"]

    def list_function_tools(self) -> list[ToolDefinition]:
        """List built-in function tools (``source == "function"``)."""
        return [t for t in self._tools.values() if t.source == "function"]

    def list_agent_tools(self) -> list[ToolDefinition]:
        """List agent-as-a-tool entries (``source == "agent"``).

        These are ADK ``AgentTool`` wrappers around a leaf sub-agent (e.g.
        ``google_search``). Their runtime instances live in
        ``agent_tool_registry``; this method only returns their metadata.
        """
        return [t for t in self._tools.values() if t.source == "agent"]

    def list_default_global_tools(self) -> list[ToolDefinition]:
        """List tools that are part of every account's default inventory.

        These are function tools tagged ``default_global: true`` in the YAML's
        ``function_tools:`` section. They are returned by the account tool
        inventory endpoint unconditionally — no integration required.
        """
        return [t for t in self._tools.values() if t.default_global]

    def list_by_category(self, category: str) -> list[ToolDefinition]:
        """List tools in a specific category.

        Args:
            category: Category to filter by

        Returns:
            List of tools in the category
        """
        normalized_category = category.lower()
        tool_names = self._categories.get(normalized_category, [])
        return [self._tools[name] for name in tool_names]

    def search_by_keyword(self, keyword: str) -> list[ToolDefinition]:
        """Search tools by keyword.

        Args:
            keyword: Search keyword

        Returns:
            List of matching tools
        """
        normalized_keyword = keyword.lower()
        tool_names = self._keyword_index.get(normalized_keyword, [])
        return [self._tools[name] for name in tool_names]

    def search(self, query: str) -> list[ToolDefinition]:
        """Search tools by query string (matches keywords, name, or description).

        Args:
            query: Search query

        Returns:
            List of matching tools, sorted by relevance
        """
        query_lower = query.lower()
        query_terms = query_lower.split()

        matches: dict[str, int] = {}

        for tool in self._tools.values():
            score = 0

            # Exact keyword match (highest priority)
            for term in query_terms:
                if term in tool.keywords:
                    score += 10

            # Name contains query term
            for term in query_terms:
                if term in tool.name:
                    score += 5

            # Description contains query term
            for term in query_terms:
                if term in tool.description.lower():
                    score += 2

            # Category match
            for term in query_terms:
                if term in tool.category:
                    score += 3

            if score > 0:
                matches[tool.name] = score

        # Sort by score descending
        sorted_names = sorted(matches.keys(), key=lambda n: matches[n], reverse=True)
        return [self._tools[name] for name in sorted_names]

    def validate_permissions(self, tool_name: str, user_permissions: list[str]) -> bool:
        """Check if user has required permissions for a tool.

        Args:
            tool_name: Tool identifier
            user_permissions: List of permission scopes user has

        Returns:
            True if user has all required permissions
        """
        tool = self.get_tool(tool_name)
        if tool is None:
            return False

        for permission in tool.permissions:
            if permission.required and permission.scope not in user_permissions:
                return False

        return True

    def filter_by_permissions(
        self,
        tools: list[ToolDefinition],
        user_permissions: list[str],
    ) -> list[ToolDefinition]:
        """Filter tools to those user has permission to use.

        Args:
            tools: List of tools to filter
            user_permissions: User's permission scopes

        Returns:
            List of tools user can access
        """
        result = []
        for tool in tools:
            has_all_permissions = all(
                not perm.required or perm.scope in user_permissions
                for perm in tool.permissions
            )
            if has_all_permissions:
                result.append(tool)
        return result

    def get_categories(self) -> list[str]:
        """Get list of all tool categories.

        Returns:
            List of category names
        """
        return list(self._categories.keys())

    def get_index_for_context(self) -> str:
        """Generate compact text representation for agent context.

        Creates a ~2,000 token index of available tools organized by category,
        suitable for inclusion in Tool Discovery Agent prompts.

        Returns:
            Markdown-formatted string listing tools by category
        """
        lines = ["## Available Tool Categories\n"]

        for category in sorted(self._categories.keys()):
            tool_names = self._categories[category]
            tools = [self._tools[name] for name in tool_names]

            lines.append(f"\n### {category.title()}")
            for tool in tools:
                desc = (
                    tool.description[:80] + "..."
                    if len(tool.description) > 80
                    else tool.description
                )
                lines.append(f"- **{tool.name}**: {desc}")

        lines.append("\n\nUse `search_tools` to find specific tools by keyword.")
        return "\n".join(lines)

    def count(self) -> int:
        """Get total number of registered tools.

        Returns:
            Tool count
        """
        return len(self._tools)

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._categories.clear()
        self._keyword_index.clear()


# Global registry instance
_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """Get or create the default tool registry.

    Loads tools from the default config file on first access.

    Returns:
        Default ToolRegistry instance
    """
    global _default_registry

    if _default_registry is None:
        _default_registry = ToolRegistry()

        # Load default config
        default_config = Path(__file__).parent / "config" / "tools.yaml"
        if default_config.exists():
            _default_registry.load_from_config(default_config)
        else:
            logger.warning(f"Default config not found: {default_config}")

    return _default_registry
