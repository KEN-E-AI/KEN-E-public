"""MCP Server Management API endpoints.

Provides admin visibility into MCP server status, health, and management.
Includes tool execution usage tracking and session status monitoring.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..models.kene_models import RecoverableSessionInfo
from ..models.tool_models import ToolBreakdownResponse, UserBreakdownResponse

logger = __import__("logging").getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


def _require_admin(user: UserContext) -> None:
    """Raise 403 if the user is not a super admin."""
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


class MCPServerInfo(BaseModel):
    """Information about a loaded MCP server."""

    name: str
    tool_count: int
    tokens: int
    loaded_at: str
    last_used: str
    health_status: str


class MCPStatusResponse(BaseModel):
    """Status of all MCP servers."""

    loaded_count: int = Field(..., description="Number of currently loaded servers")
    max_servers: int = Field(..., description="Maximum allowed concurrent servers")
    servers: list[MCPServerInfo] = Field(..., description="Details of loaded servers")


class AgentEngineMCPServerHealth(BaseModel):
    """Health status of an Agent Engine MCP server (e.g. GA MCP)."""

    reachable: bool
    latency_ms: float | None = None
    url: str
    error: str | None = None


class AgentEngineMCPHealth(BaseModel):
    """Aggregated health of Agent Engine MCP connections."""

    ga_mcp_server: AgentEngineMCPServerHealth


class MCPHealthResponse(BaseModel):
    """Health status of MCP servers."""

    overall_status: str = Field(..., description="Overall health: healthy, degraded, unhealthy")
    total_servers: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    servers: list[MCPServerInfo]
    agent_engine_mcp: AgentEngineMCPHealth | None = Field(
        None, description="Health of Agent Engine MCP connections (GA MCP server)"
    )


class MCPLoadRequest(BaseModel):
    """Request to manually load an MCP server."""

    server_name: str = Field(..., description="Name of the server to load")


class MCPLoadResponse(BaseModel):
    """Response from loading an MCP server."""

    status: str
    server_name: str
    tool_count: int


class MCPConfigInfo(BaseModel):
    """Information about configured MCP servers."""

    name: str
    description: str
    category: str
    tool_count: int
    estimated_tokens: int
    enabled: bool
    connection_type: str


class MCPConfigListResponse(BaseModel):
    """List of all configured MCP servers."""

    total: int
    enabled_count: int
    servers: list[MCPConfigInfo]


def _get_mcp_manager():
    """Lazy import to avoid circular dependencies."""
    from app.adk.mcp_config import get_mcp_manager

    return get_mcp_manager()


def _get_mcp_config_loader():
    """Lazy import to avoid circular dependencies."""
    from app.adk.mcp_config import get_mcp_config_loader

    return get_mcp_config_loader()


@router.get("/status", response_model=MCPStatusResponse)
async def get_mcp_status(
    user: UserContext = Depends(get_current_user),
) -> MCPStatusResponse:
    """Get status of all loaded MCP servers.

    Returns current server load, token usage, and individual server details.
    Useful for monitoring resource usage and debugging connection issues.

    Requires: Admin access
    """
    _require_admin(user)
    manager = _get_mcp_manager()
    mcp_status = manager.get_status()

    return MCPStatusResponse(
        loaded_count=mcp_status["loaded_count"],
        max_servers=mcp_status["max_servers"],
        servers=[
            MCPServerInfo(
                name=s["name"],
                tool_count=s["tool_count"],
                tokens=s["tokens"],
                loaded_at=s["loaded_at"],
                last_used=s["last_used"],
                health_status=s["health_status"],
            )
            for s in mcp_status["servers"]
        ],
    )


@router.get("/health", response_model=MCPHealthResponse)
async def get_mcp_health(
    user: UserContext = Depends(get_current_user),
) -> MCPHealthResponse:
    """Get health status of MCP servers.

    Returns aggregated health metrics and per-server health status,
    including proactive reachability of the Agent Engine's GA MCP server.

    Requires: Admin access
    """
    _require_admin(user)
    manager = _get_mcp_manager()
    mcp_status = manager.get_status()

    servers = mcp_status["servers"]
    unhealthy_count = sum(1 for s in servers if s["health_status"] == "unhealthy")
    degraded_count = sum(1 for s in servers if s["health_status"] == "degraded")
    healthy_count = mcp_status["loaded_count"] - unhealthy_count - degraded_count

    overall = "healthy"
    if unhealthy_count > 0:
        overall = "unhealthy"
    elif degraded_count > 0:
        overall = "degraded"

    # Proactive ping of the GA MCP server used by Agent Engine
    agent_engine_mcp = None
    try:
        from ..services.mcp_health_service import check_ga_mcp_health

        ga_result = await check_ga_mcp_health()
        agent_engine_mcp = AgentEngineMCPHealth(
            ga_mcp_server=AgentEngineMCPServerHealth(**ga_result),
        )
    except Exception:
        logger.exception("Failed to check Agent Engine MCP health")

    return MCPHealthResponse(
        overall_status=overall,
        total_servers=mcp_status["loaded_count"],
        healthy_count=healthy_count,
        degraded_count=degraded_count,
        unhealthy_count=unhealthy_count,
        servers=[
            MCPServerInfo(
                name=s["name"],
                tool_count=s["tool_count"],
                tokens=s["tokens"],
                loaded_at=s["loaded_at"],
                last_used=s["last_used"],
                health_status=s["health_status"],
            )
            for s in servers
        ],
        agent_engine_mcp=agent_engine_mcp,
    )


@router.get("/config", response_model=MCPConfigListResponse)
async def get_mcp_config(
    user: UserContext = Depends(get_current_user),
) -> MCPConfigListResponse:
    """Get list of all configured MCP servers.

    Shows all servers defined in configuration, whether enabled or not.
    Useful for understanding available integrations.

    Requires: Admin access
    """
    _require_admin(user)
    loader = _get_mcp_config_loader()
    configs = loader.configs

    servers = []
    enabled_count = 0
    for name, config in configs.items():
        if config.enabled:
            enabled_count += 1
        servers.append(
            MCPConfigInfo(
                name=name,
                description=config.description,
                category=config.category,
                tool_count=config.tool_count,
                estimated_tokens=config.estimated_tokens,
                enabled=config.enabled,
                connection_type=config.connection.connection_type,
            )
        )

    return MCPConfigListResponse(
        total=len(servers),
        enabled_count=enabled_count,
        servers=servers,
    )


@router.post("/load", response_model=MCPLoadResponse)
async def load_mcp_server(
    request: MCPLoadRequest,
    user: UserContext = Depends(get_current_user),
) -> MCPLoadResponse:
    """Manually load an MCP server.

    Triggers lazy initialization of the specified server.
    Useful for pre-warming connections or testing configuration.

    Requires: Admin access
    """
    _require_admin(user)
    manager = _get_mcp_manager()

    try:
        tools = await manager.load_server(request.server_name)
        return MCPLoadResponse(
            status="loaded",
            server_name=request.server_name,
            tool_count=len(tools),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except ConnectionError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to MCP server '{request.server_name}'",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error loading MCP server '{request.server_name}'",
        ) from e


@router.post("/unload/{server_name}")
async def unload_mcp_server(
    server_name: str,
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually unload an MCP server.

    Gracefully closes the connection and frees resources.
    Useful for forcing reconnection or freeing resources.

    Requires: Admin access
    """
    _require_admin(user)
    manager = _get_mcp_manager()

    if not manager.is_loaded(server_name):
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' is not loaded")

    await manager.unload_server(server_name)
    return {"status": "unloaded", "server_name": server_name}


# ============================================================================
# Tool Execution Usage Tracking Endpoints
# ============================================================================


class AccountToolUsageResponse(BaseModel):
    """Tool execution usage statistics."""

    period_start: datetime = Field(..., description="Start of the reporting period")
    period_end: datetime = Field(..., description="End of the reporting period")
    total_calls: int = Field(..., description="Total tool calls in period")
    success_count: int = Field(..., description="Successful executions")
    failure_count: int = Field(..., description="Failed executions")
    success_rate: float = Field(..., description="Success rate (0.0-1.0)")
    avg_duration_ms: float | None = Field(None, description="Average execution duration in ms")
    total_tokens: int = Field(..., description="Total tokens consumed")
    by_tool: dict[str, ToolBreakdownResponse] = Field(..., description="Breakdown by tool name")
    by_user: dict[str, UserBreakdownResponse] = Field(..., description="Breakdown by user")
    by_status: dict[str, int] = Field(..., description="Call counts by status")


class ToolUsagePendingResponse(BaseModel):
    """Information about pending (unbatched) usage events."""

    pending_count: int = Field(..., description="Events waiting to be flushed")
    stored_count: int = Field(..., description="Events already stored (in-memory)")
    using_firestore: bool = Field(..., description="Whether Firestore is being used")


def _get_usage_tracker():
    """Lazy import to avoid circular dependencies."""
    from app.adk.tracking.usage import get_usage_tracker

    return get_usage_tracker()


@router.get("/tools/usage", response_model=AccountToolUsageResponse)
async def get_tool_usage(
    account_id: str = Query(..., description="Account to get usage for"),
    days: int = Query(7, ge=1, le=90, description="Number of days to query"),
    user: UserContext = Depends(get_current_user),
) -> AccountToolUsageResponse:
    """Get tool execution usage statistics for an account.

    Returns aggregated statistics including:
    - Total calls, success/failure counts
    - Average execution duration
    - Breakdown by tool, user, and status

    Requires: Admin access to the specified account
    """
    # Permission check
    if not user.is_super_admin and not user.has_account_access(account_id, ["edit"]):
        raise HTTPException(status_code=403, detail="Admin access required for account usage")

    tracker = _get_usage_tracker()

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    try:
        # Flush pending events before querying
        await tracker.flush()

        agg = await tracker.get_usage_aggregation(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )

        return AccountToolUsageResponse(**agg.model_dump())
    except Exception as e:
        logger.exception("Failed to retrieve tool usage")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage") from e


@router.get("/tools/usage/pending", response_model=ToolUsagePendingResponse)
async def get_tool_usage_pending(
    user: UserContext = Depends(get_current_user),
) -> ToolUsagePendingResponse:
    """Get information about pending usage events.

    Shows how many events are waiting to be flushed to storage.
    Useful for debugging and monitoring the usage tracking system.

    Requires: Admin access
    """
    _require_admin(user)
    tracker = _get_usage_tracker()

    return ToolUsagePendingResponse(
        pending_count=tracker.get_pending_count(),
        stored_count=tracker.get_stored_count(),
        using_firestore=tracker.is_using_firestore,
    )


@router.post("/tools/usage/flush")
async def flush_tool_usage(
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Force flush pending usage events to storage.

    Normally events are batched and flushed periodically.
    Use this to force immediate persistence.

    Requires: Admin access
    """
    _require_admin(user)
    tracker = _get_usage_tracker()

    pending_before = tracker.get_pending_count()
    await tracker.flush()
    pending_after = tracker.get_pending_count()

    return {
        "status": "flushed",
        "events_flushed": pending_before - pending_after,
        "pending_remaining": pending_after,
    }


# ============================================================================
# Session Status Endpoints
# ============================================================================


class SessionStatusResponse(BaseModel):
    """Overall session management status."""

    recovery_window_days: int = Field(..., description="Days sessions are recoverable")


def _get_recovery_service():
    """Lazy import to avoid circular dependencies."""
    from app.adk.session.recovery import get_recovery_service

    return get_recovery_service()


@router.get("/sessions/status", response_model=SessionStatusResponse)
async def get_session_status(
    user: UserContext = Depends(get_current_user),
) -> SessionStatusResponse:
    """Get session management system status.

    Requires: Admin access
    """
    _require_admin(user)
    try:
        recovery_svc = _get_recovery_service()
        return SessionStatusResponse(
            recovery_window_days=recovery_svc.RECOVERY_WINDOW_DAYS,
        )
    except Exception:
        return SessionStatusResponse(
            recovery_window_days=30,
        )


@router.get("/sessions/recoverable", response_model=list[RecoverableSessionInfo])
async def get_recoverable_sessions(
    limit: int = Query(10, ge=1, le=50, description="Max sessions to return"),
    user: UserContext = Depends(get_current_user),
) -> list[RecoverableSessionInfo]:
    """List recoverable sessions for the current user.

    Returns sessions from the last 30 days that can be recovered.
    Sessions are sorted by last updated time (most recent first).

    Requires: Authenticated user
    """
    try:
        recovery_svc = _get_recovery_service()
        sessions = await recovery_svc.list_recoverable_sessions(
            user_id=user.user_id,
            limit=limit,
        )

        return [
            RecoverableSessionInfo(
                session_id=s.session_id,
                conversation_name=s.conversation_name,
                last_updated=s.last_updated.isoformat() if hasattr(s.last_updated, "isoformat") else str(s.last_updated),
                message_count=s.message_count,
                preview=s.preview,
            )
            for s in sessions
        ]
    except Exception:
        logger.exception("Failed to list recoverable sessions")
        raise HTTPException(
            status_code=500, detail="Failed to list recoverable sessions"
        ) from None


# ============================================================================
# Admin Dashboard Summary Endpoint
# ============================================================================


class Sprint3StatusResponse(BaseModel):
    """Complete Sprint 3 system status for admin dashboard."""

    mcp_servers: MCPStatusResponse = Field(..., description="MCP server status")
    mcp_health: MCPHealthResponse = Field(..., description="MCP health status")
    tool_usage_pending: ToolUsagePendingResponse = Field(
        ..., description="Pending usage events"
    )
    session_status: SessionStatusResponse = Field(..., description="Session management status")
    features_enabled: dict[str, bool] = Field(..., description="Sprint 3 features status")


@router.get("/admin/dashboard", response_model=Sprint3StatusResponse)
async def get_admin_dashboard(
    user: UserContext = Depends(get_current_user),
) -> Sprint3StatusResponse:
    """Get complete Sprint 3 system status.

    Combines all monitoring endpoints into a single admin dashboard view.
    Shows MCP servers, health, usage tracking, and session management.

    Requires: Admin access
    """
    _require_admin(user)
    # Get MCP status
    manager = _get_mcp_manager()
    raw_status = manager.get_status()

    mcp_status = MCPStatusResponse(
        loaded_count=raw_status["loaded_count"],
        max_servers=raw_status["max_servers"],
        servers=[
            MCPServerInfo(
                name=s["name"],
                tool_count=s["tool_count"],
                tokens=s["tokens"],
                loaded_at=s["loaded_at"],
                last_used=s["last_used"],
                health_status=s["health_status"],
            )
            for s in raw_status["servers"]
        ],
    )

    # Get health status
    servers = raw_status["servers"]
    unhealthy_count = sum(1 for s in servers if s["health_status"] == "unhealthy")
    degraded_count = sum(1 for s in servers if s["health_status"] == "degraded")
    healthy_count = raw_status["loaded_count"] - unhealthy_count - degraded_count

    overall = "healthy"
    if unhealthy_count > 0:
        overall = "unhealthy"
    elif degraded_count > 0:
        overall = "degraded"

    # Proactive ping of the GA MCP server used by Agent Engine
    agent_engine_mcp = None
    try:
        from ..services.mcp_health_service import check_ga_mcp_health

        ga_result = await check_ga_mcp_health()
        agent_engine_mcp = AgentEngineMCPHealth(
            ga_mcp_server=AgentEngineMCPServerHealth(**ga_result),
        )
    except Exception:
        logger.exception("Failed to check Agent Engine MCP health")

    mcp_health = MCPHealthResponse(
        overall_status=overall,
        total_servers=raw_status["loaded_count"],
        healthy_count=healthy_count,
        degraded_count=degraded_count,
        unhealthy_count=unhealthy_count,
        servers=[
            MCPServerInfo(
                name=s["name"],
                tool_count=s["tool_count"],
                tokens=s["tokens"],
                loaded_at=s["loaded_at"],
                last_used=s["last_used"],
                health_status=s["health_status"],
            )
            for s in servers
        ],
        agent_engine_mcp=agent_engine_mcp,
    )

    # Get usage tracker status
    tracker = _get_usage_tracker()
    usage_pending = ToolUsagePendingResponse(
        pending_count=tracker.get_pending_count(),
        stored_count=tracker.get_stored_count(),
        using_firestore=tracker.is_using_firestore,
    )

    # Get session status
    session_status = await get_session_status(user)

    # Check which features are enabled
    features_enabled = {
        "mcp_lazy_loading": True,  # Always enabled in Sprint 3
        "mcp_lru_eviction": False,
        "mcp_health_monitoring": True,
        "oauth_header_auth": True,
        "tool_usage_tracking": True,
        "session_recovery": True,
    }

    return Sprint3StatusResponse(
        mcp_servers=mcp_status,
        mcp_health=mcp_health,
        tool_usage_pending=usage_pending,
        session_status=session_status,
        features_enabled=features_enabled,
    )
