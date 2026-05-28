"""Tool Discovery service for searching and filtering available tools.

The Tool Discovery service queries the Tool Registry to help users and agents
understand what tools are available. It supports:
- Keyword search across tool names, descriptions, and tags
- Filtering by user permissions (connected accounts)
- Filtering by tool category
- Relevance ranking of search results
"""

import logging
from dataclasses import dataclass
from typing import Any, ClassVar

# Try shared import first, fall back to standard logging (when imported directly in tests)
try:
    from shared.structured_logging import get_structured_logger, log_context
except ImportError:
    # Fallback for direct imports (e.g., in tests)
    def get_structured_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

    def log_context(**kwargs: Any) -> dict[str, Any]:
        return {"json_fields": kwargs}


from ..registry.tool_registry import ToolRegistry, get_default_registry
from ..registry.tool_schema import ToolDefinition

logger = get_structured_logger(__name__)


@dataclass
class ToolSearchResult:
    """Result from a tool search operation.

    Attributes:
        tool: The matched tool definition
        score: Relevance score (higher is more relevant)
        match_reasons: List of reasons why this tool matched
    """

    tool: ToolDefinition
    score: float
    match_reasons: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "name": self.tool.name,
            "description": self.tool.description,
            "category": self.tool.category,
            "score": self.score,
            "match_reasons": self.match_reasons,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                }
                for p in self.tool.parameters
            ],
            "permissions": [p.scope for p in self.tool.permissions if p.required],
            "examples": self.tool.examples,
        }


class ToolDiscoveryService:
    """Service for discovering and searching available tools.

    Provides search and filtering capabilities over the Tool Registry,
    with support for permission-based filtering and relevance ranking.

    Example:
        >>> discovery = ToolDiscoveryService()
        >>> results = discovery.search("analytics traffic")
        >>> for result in results:
        ...     print(f"{result.tool.name}: {result.score}")
    """

    # Connected account type to permission scope mapping
    ACCOUNT_TYPE_PERMISSIONS: ClassVar[dict[str, list[str]]] = {
        "google_analytics": ["analytics:read"],
        "google_ads": ["ads:read", "ads:write"],
        "meta_ads": ["meta:read", "meta:write"],
        "hubspot": ["hubspot:read", "hubspot:write"],
    }

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        """Initialize discovery service.

        Args:
            registry: Optional tool registry. Uses default if not provided.
        """
        self._registry = registry or get_default_registry()

    def search(
        self,
        query: str,
        limit: int = 10,
        user_permissions: list[str] | None = None,
        category: str | None = None,
    ) -> list[ToolSearchResult]:
        """Search tools by query with optional filtering.

        Args:
            query: Search query (keywords)
            limit: Maximum results to return
            user_permissions: Optional list of user permission scopes for filtering
            category: Optional category filter

        Returns:
            List of ToolSearchResult sorted by relevance
        """
        query_lower = query.lower()
        query_terms = query_lower.split()

        results: list[ToolSearchResult] = []

        for tool in self._registry.list_tools():
            # Apply category filter
            if category and tool.category != category.lower():
                continue

            # Calculate relevance score
            score, reasons = self._calculate_relevance(tool, query_terms)

            if score > 0:
                results.append(
                    ToolSearchResult(tool=tool, score=score, match_reasons=reasons)
                )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply permission filter if provided
        if user_permissions is not None:
            results = [
                r for r in results if self._check_permissions(r.tool, user_permissions)
            ]

        final_results = results[:limit]

        # Log the search
        logger.info(
            "Tool discovery search completed",
            extra=log_context(
                component="tool_discovery",
                action="search",
                query=query,
                results_count=len(final_results),
                category=category or "",
                extra={
                    "total_matches": len(results),
                    "limit": limit,
                    "has_permission_filter": user_permissions is not None,
                    "top_results": [r.tool.name for r in final_results[:3]],
                },
            ),
        )

        return final_results

    def _calculate_relevance(
        self, tool: ToolDefinition, query_terms: list[str]
    ) -> tuple[float, list[str]]:
        """Calculate relevance score for a tool.

        Args:
            tool: Tool to score
            query_terms: List of search terms

        Returns:
            Tuple of (score, list of match reasons)
        """
        score = 0.0
        reasons: list[str] = []

        for term in query_terms:
            # Exact keyword match (highest priority)
            if term in tool.keywords:
                score += 10.0
                reasons.append(f"keyword match: {term}")

            # Name contains term
            if term in tool.name:
                score += 5.0
                reasons.append(f"name contains: {term}")

            # Description contains term
            if term in tool.description.lower():
                score += 2.0
                reasons.append(f"description contains: {term}")

            # Category match
            if term in tool.category:
                score += 3.0
                reasons.append(f"category match: {term}")

        return score, reasons

    def _check_permissions(
        self, tool: ToolDefinition, user_permissions: list[str]
    ) -> bool:
        """Check if user has required permissions for tool.

        Args:
            tool: Tool to check
            user_permissions: User's permission scopes

        Returns:
            True if user has all required permissions
        """
        for perm in tool.permissions:
            if perm.required and perm.scope not in user_permissions:
                return False
        return True

    def filter_by_connected_accounts(
        self,
        tools: list[ToolDefinition] | None = None,
        connected_accounts: list[str] | None = None,
    ) -> list[ToolDefinition]:
        """Filter tools to those available for connected accounts.

        Args:
            tools: List of tools to filter (uses all tools if None)
            connected_accounts: List of connected account types
                (e.g., ["google_analytics", "google_ads"])

        Returns:
            List of tools accessible with connected accounts
        """
        if tools is None:
            tools = self._registry.list_tools()

        if not connected_accounts:
            return []

        # Convert account types to permission scopes
        user_permissions: set[str] = set()
        for account_type in connected_accounts:
            permissions = self.ACCOUNT_TYPE_PERMISSIONS.get(account_type.lower(), [])
            user_permissions.update(permissions)

        return [
            tool
            for tool in tools
            if self._check_permissions(tool, list(user_permissions))
        ]

    def list_by_category(self, category: str) -> list[ToolDefinition]:
        """List all tools in a category.

        Args:
            category: Category name

        Returns:
            List of tools in the category
        """
        return self._registry.list_by_category(category)

    def get_tool_info(self, tool_name: str) -> dict | None:
        """Get detailed information about a specific tool.

        Args:
            tool_name: Tool identifier

        Returns:
            Tool info dict or None if not found
        """
        tool = self._registry.get_tool(tool_name)
        if tool is None:
            return None

        return {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "mcp_server": tool.mcp_server,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                }
                for p in tool.parameters
            ],
            "permissions": [
                {"scope": p.scope, "required": p.required} for p in tool.permissions
            ],
            "keywords": tool.keywords,
            "estimated_tokens": tool.estimated_tokens,
            "examples": tool.examples,
        }

    def get_categories(self) -> list[str]:
        """Get list of available tool categories.

        Returns:
            List of category names
        """
        return self._registry.get_categories()

    def suggest_tools(
        self,
        intent: str,
        connected_accounts: list[str] | None = None,
        limit: int = 5,
    ) -> list[ToolSearchResult]:
        """Suggest tools based on user intent.

        This is a higher-level method that interprets user intent
        and suggests relevant tools.

        Args:
            intent: User's expressed intent (e.g., "analyze my website traffic")
            connected_accounts: User's connected account types
            limit: Maximum suggestions

        Returns:
            List of suggested tools with relevance scores
        """
        # Convert connected accounts to permissions
        user_permissions: list[str] | None = None
        if connected_accounts:
            user_permissions = []
            for account_type in connected_accounts:
                perms = self.ACCOUNT_TYPE_PERMISSIONS.get(account_type.lower(), [])
                user_permissions.extend(perms)

        return self.search(query=intent, limit=limit, user_permissions=user_permissions)


# Default discovery service instance
_default_discovery: ToolDiscoveryService | None = None


def get_default_discovery() -> ToolDiscoveryService:
    """Get or create the default discovery service.

    Returns:
        Default ToolDiscoveryService instance
    """
    global _default_discovery

    if _default_discovery is None:
        _default_discovery = ToolDiscoveryService()

    return _default_discovery
