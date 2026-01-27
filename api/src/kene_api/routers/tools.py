"""API endpoints for tool discovery and management."""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..models.tool_models import (
    ToolCategoriesResponse,
    ToolCategoryResponse,
    ToolDiscoveryResponse,
    ToolInfoResponse,
    ToolParameterResponse,
    ToolSearchResultResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

# Add app path to enable importing from app.adk.tools
app_path = Path(__file__).parents[5] / "app" / "adk"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path.parent.parent))

# Lazy import to avoid circular dependencies
_discovery_service = None


def get_discovery_service():
    """Get or create the tool discovery service."""
    global _discovery_service
    if _discovery_service is None:
        try:
            from app.adk.tools.discovery.tool_discovery import ToolDiscoveryService

            _discovery_service = ToolDiscoveryService()
            logger.info("Tool discovery service initialized")
        except ImportError as e:
            logger.error(f"Failed to import tool discovery: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tool discovery service not available",
            ) from e
    return _discovery_service


def _get_user_permissions(user: UserContext, account_id: str | None) -> list[str]:
    """Extract user permissions based on connected accounts.

    Args:
        user: User context from auth
        account_id: Optional account ID to check integrations for

    Returns:
        List of permission scopes the user has
    """
    permissions: list[str] = []

    # For now, grant analytics:read if user has any account access
    # This will be enhanced when we have proper integration status checking
    if user.account_permissions:
        # User has some account access, grant basic analytics read
        permissions.append("analytics:read")

    # Super admins get all permissions
    if user.is_super_admin:
        permissions.extend(
            [
                "analytics:read",
                "analytics:write",
                "ads:read",
                "ads:write",
                "meta:read",
                "meta:write",
                "hubspot:read",
                "hubspot:write",
            ]
        )

    return list(set(permissions))  # Deduplicate


@router.get("/discover", response_model=ToolDiscoveryResponse)
async def discover_tools(
    query: str = Query(..., description="Search query for tool discovery"),
    category: str | None = Query(default=None, description="Filter by category"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum results"),
    account_id: str | None = Query(
        default=None, description="Account ID for permission filtering"
    ),
    user: UserContext = Depends(get_current_user_context),
) -> ToolDiscoveryResponse:
    """Discover available tools based on a search query.

    Search the tool registry for tools matching the query keywords.
    Results are filtered based on user permissions and sorted by relevance.

    Args:
        query: Keywords describing the capability needed
        category: Optional category filter (e.g., "analytics", "advertising")
        limit: Maximum number of results to return
        account_id: Optional account ID for permission-based filtering
        user: Current authenticated user

    Returns:
        ToolDiscoveryResponse with matching tools
    """
    logger.info(
        f"[TOOL-DISCOVERY-API] User {user.user_id} searching: "
        f"query='{query}', category={category}"
    )

    discovery = get_discovery_service()

    # Get user permissions
    user_permissions = _get_user_permissions(user, account_id)

    # Search for tools
    results = discovery.search(
        query=query,
        limit=limit,
        user_permissions=user_permissions if user_permissions else None,
        category=category,
    )

    # Convert to API response format
    response_results = [
        ToolSearchResultResponse(
            name=r.tool.name,
            description=r.tool.description,
            category=r.tool.category,
            score=r.score,
            match_reasons=r.match_reasons,
            parameters=[
                ToolParameterResponse(
                    name=p.name,
                    type=p.type,
                    description=p.description,
                    required=p.required,
                    default=str(p.default) if p.default is not None else None,
                )
                for p in r.tool.parameters
            ],
            permissions=[p.scope for p in r.tool.permissions if p.required],
            examples=r.tool.examples,
        )
        for r in results
    ]

    return ToolDiscoveryResponse(
        query=query,
        category=category,
        total_results=len(response_results),
        results=response_results,
    )


@router.get("/categories", response_model=ToolCategoriesResponse)
async def list_categories(
    user: UserContext = Depends(get_current_user_context),
) -> ToolCategoriesResponse:
    """List all available tool categories.

    Returns a list of tool categories with the count of tools in each.
    """
    discovery = get_discovery_service()

    categories = discovery.get_categories()

    category_responses = []
    for cat in categories:
        tools = discovery.list_by_category(cat)
        category_responses.append(ToolCategoryResponse(name=cat, tool_count=len(tools)))

    return ToolCategoriesResponse(categories=category_responses)


@router.get("/{tool_name}", response_model=ToolInfoResponse)
async def get_tool_info(
    tool_name: str,
    user: UserContext = Depends(get_current_user_context),
) -> ToolInfoResponse:
    """Get detailed information about a specific tool.

    Args:
        tool_name: Name of the tool to look up

    Returns:
        ToolInfoResponse with full tool details

    Raises:
        404: If tool not found
    """
    discovery = get_discovery_service()

    info = discovery.get_tool_info(tool_name)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
        )

    return ToolInfoResponse(
        name=info["name"],
        description=info["description"],
        category=info["category"],
        parameters=[
            ToolParameterResponse(
                name=p["name"],
                type=p["type"],
                description=p["description"],
                required=p["required"],
                default=str(p["default"]) if p.get("default") is not None else None,
            )
            for p in info["parameters"]
        ],
        permissions=[p["scope"] for p in info["permissions"] if p["required"]],
        examples=info["examples"],
        estimated_tokens=info["estimated_tokens"],
    )
