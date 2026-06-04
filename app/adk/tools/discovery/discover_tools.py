"""Agent tool for runtime tool discovery.

This module provides the `discover_tools` function that can be used as an
agent tool to query the Tool Registry and help users understand what
capabilities are available.
"""

import logging

from google.adk.tools import ToolContext

from app.utils.weave_observability import safe_weave_op

from .tool_discovery import get_default_discovery

logger = logging.getLogger(__name__)


@safe_weave_op(name="discover_tools")
def discover_tools(
    query: str,
    tool_context: ToolContext | None = None,
    category: str | None = None,
    limit: int = 5,
) -> str:
    """Discover available tools based on a search query.

    This function is designed to be used as an agent tool for runtime
    tool discovery. It searches the Tool Registry and returns formatted
    information about matching tools.

    Args:
        query: Keywords describing the capability needed
            (e.g., "analytics traffic", "website performance")
        tool_context: Optional ADK tool context for accessing session state
        category: Optional category filter (e.g., "analytics", "advertising")
        limit: Maximum number of tools to return (default: 5)

    Returns:
        Formatted string describing matching tools and their capabilities

    Example:
        User: "What analytics tools do I have access to?"
        Agent calls: discover_tools("analytics", category="analytics")
        Returns: "Found 4 analytics tools:\n1. run_report_mt - ..."
    """
    logger.info(
        f"[TOOL-DISCOVERY] Searching for tools: query='{query}', category={category}"
    )

    # Get discovery service
    discovery = get_default_discovery()

    # Get user's connected accounts from session state if available
    connected_accounts: list[str] | None = None
    user_permissions: list[str] | None = None

    if tool_context and hasattr(tool_context, "state"):
        # Check for connected account types in session state
        connected_accounts = tool_context.state.get("connected_accounts")
        if connected_accounts:
            logger.info(
                f"[TOOL-DISCOVERY] User has connected accounts: {connected_accounts}"
            )
            # Convert to permissions
            user_permissions = []
            for account_type in connected_accounts:
                perms = discovery.ACCOUNT_TYPE_PERMISSIONS.get(account_type.lower(), [])
                user_permissions.extend(perms)

    # Search for tools
    results = discovery.search(
        query=query, limit=limit, user_permissions=user_permissions, category=category
    )

    if not results:
        return _format_no_results(query, category)

    return _format_results(results, query, category)


def _format_no_results(query: str, category: str | None) -> str:
    """Format response when no tools found."""
    msg = f"No tools found matching '{query}'"
    if category:
        msg += f" in category '{category}'"
    msg += ".\n\nAvailable categories: analytics, advertising, content"
    return msg


def _format_results(results: list, query: str, category: str | None) -> str:
    """Format search results as markdown."""
    lines = []

    # Header
    if category:
        lines.append(f"## {category.title()} Tools matching '{query}'")
    else:
        lines.append(f"## Tools matching '{query}'")

    lines.append(f"\nFound {len(results)} matching tool(s):\n")

    # Format each result
    for i, result in enumerate(results, 1):
        tool = result.tool
        lines.append(f"### {i}. {tool.name}")
        lines.append(f"**Description:** {tool.description}")
        lines.append(f"**Category:** {tool.category}")

        # Parameters
        if tool.parameters:
            required_params = [p for p in tool.parameters if p.required]
            if required_params:
                params_str = ", ".join(f"`{p.name}`" for p in required_params)
                lines.append(f"**Required parameters:** {params_str}")

        # Examples
        if tool.examples:
            lines.append("**Example queries:**")
            for example in tool.examples[:3]:  # Limit to 3 examples
                lines.append(f'  - "{example}"')

        lines.append("")  # Blank line between tools

    return "\n".join(lines)


@safe_weave_op(name="list_tool_categories")
def list_tool_categories(tool_context: ToolContext | None = None) -> str:
    """List all available tool categories.

    This function returns a list of tool categories and the number of
    tools in each category.

    Args:
        tool_context: Optional ADK tool context (unused but kept for consistency)

    Returns:
        Formatted string listing all categories
    """
    discovery = get_default_discovery()
    categories = discovery.get_categories()

    if not categories:
        return "No tool categories available."

    lines = ["## Available Tool Categories\n"]

    for category in sorted(categories):
        tools = discovery.list_by_category(category)
        lines.append(f"- **{category}**: {len(tools)} tool(s)")

    return "\n".join(lines)


@safe_weave_op(name="get_tool_details")
def get_tool_details(tool_name: str, tool_context: ToolContext | None = None) -> str:
    """Get detailed information about a specific tool.

    Args:
        tool_name: Name of the tool to look up
        tool_context: Optional ADK tool context (unused but kept for consistency)

    Returns:
        Formatted string with tool details or error message
    """
    discovery = get_default_discovery()
    info = discovery.get_tool_info(tool_name)

    if info is None:
        return f"Tool '{tool_name}' not found in registry."

    lines = [f"## {info['name']}\n"]
    lines.append(f"**Description:** {info['description']}")
    lines.append(f"**Category:** {info['category']}")

    if info.get("mcp_server"):
        lines.append(f"**MCP Server:** {info['mcp_server']}")

    lines.append(f"\n**Estimated tokens:** {info['estimated_tokens']}")

    # Parameters section
    if info["parameters"]:
        lines.append("\n### Parameters\n")
        for param in info["parameters"]:
            required = "required" if param["required"] else "optional"
            default = f", default: {param['default']}" if param.get("default") else ""
            lines.append(
                f"- `{param['name']}` ({param['type']}, {required}{default}): "
                f"{param['description']}"
            )

    # Permissions section
    if info["permissions"]:
        lines.append("\n### Required Permissions\n")
        for perm in info["permissions"]:
            required = "(required)" if perm["required"] else "(optional)"
            lines.append(f"- `{perm['scope']}` {required}")

    # Examples section
    if info["examples"]:
        lines.append("\n### Example Queries\n")
        for example in info["examples"]:
            lines.append(f'- "{example}"')

    return "\n".join(lines)
