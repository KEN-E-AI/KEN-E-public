"""Kene API - FastAPI main application."""

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

# Load environment variables from .env file
load_dotenv()

# Configure structured logging for Google Cloud
# Import after load_dotenv so environment is available
from shared.structured_logging import configure_logging

# Get log level from environment (default INFO)
_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
configure_logging(level=_log_level)

# Configure ADK logging to match
logging.getLogger("google.adk").setLevel(_log_level)

# ruff: noqa: E402 - imports must come after load_dotenv() and logging configuration
from .config import settings
from .database import neo4j_service
from .firestore import get_firestore_service
from .routers import (
    account_tools,
    accounts,
    activities,
    agent_configs,
    auth,
    chat,
    datasets,
    firestore,
    funnel_reports,
    home,
    industry_keywords,
    industry_templates,
    insights,
    integrations,
    intuitions,
    items,
    knowledge_graph,
    mcp,
    mcp_server_configs,
    metrics,
    monitoring,
    monitoring_topics,
    oauth_integrations,
    organizations,
    products,
    strategy,
    subscription_plans,
    superset_saved_queries,
    tools,
    usage,
    users,
)

# Separated import to avoid circular dependency:
# notifications_v2 imports from other routers that import from main
from .routers import (
    notifications_v2 as notifications,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting up Kene API...")
    try:
        await neo4j_service.connect()
        logger.info("Neo4j connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        # You might want to decide whether to continue without Neo4j or exit

    try:
        get_firestore_service()  # This will initialize the service
        logger.info("Firestore service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore: {e}")
        # Continue without Firestore if initialization fails

    # Initialize Weave tracing (idempotent, graceful degradation)
    try:
        from app.utils.weave_observability import init_weave_if_needed

        init_weave_if_needed()
        logger.info("Weave tracing initialization attempted")
    except Exception as e:
        logger.warning(f"Failed to initialize Weave tracing: {e}")

    # Initialize Redis (non-blocking - will work with or without Redis)
    try:
        from .redis_client import get_redis_service

        redis_service = get_redis_service()
        if redis_service.is_available():
            logger.info("Redis cache enabled and connected")
        else:
            logger.info("Redis cache not available - running without caching")
    except Exception as e:
        logger.warning(f"Redis initialization check failed: {e}")

    # Start usage tracker auto-flush
    try:
        from app.adk.tracking.usage import get_usage_tracker

        usage_tracker = get_usage_tracker()
        await usage_tracker.start_auto_flush()
        logger.info("Usage tracker auto-flush started")
    except Exception as e:
        logger.warning(f"Failed to start usage tracker auto-flush: {e}")

    # Validate agent registry config doc IDs
    try:
        from app.adk.agents.registry import validate_registry_at_startup

        validate_registry_at_startup()
    except Exception as e:
        logger.warning(f"Agent registry validation failed: {e}")

    # Pre-load agent engine connection to avoid 3s lazy-load on first request
    # This is done in a non-blocking background thread
    try:
        from .routers.chat import _preload_agent_engine

        threading.Thread(target=_preload_agent_engine, daemon=True).start()
        logger.info("Agent Engine pre-loading started in background")
    except Exception as e:
        logger.warning(f"Failed to start Agent Engine pre-loading: {e}")

    # Start MCP health monitor
    try:
        from app.adk.mcp_config import get_mcp_manager

        mcp_manager = get_mcp_manager()
        await mcp_manager.start_health_monitor()
        logger.info("MCP health monitor started")
    except Exception as e:
        logger.warning(f"Failed to start MCP health monitor: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Kene API...")

    # Stop usage tracker
    try:
        from app.adk.tracking.usage import get_usage_tracker

        usage_tracker = get_usage_tracker()
        await usage_tracker.stop_auto_flush()
        logger.info("Usage tracker auto-flush stopped")
    except Exception as e:
        logger.warning(f"Failed to stop usage tracker: {e}")

    # Stop MCP health monitor
    try:
        from app.adk.mcp_config import get_mcp_manager

        mcp_manager = get_mcp_manager()
        await mcp_manager.stop_health_monitor()
        logger.info("MCP health monitor stopped")
    except Exception as e:
        logger.warning(f"Failed to stop MCP health monitor: {e}")

    await neo4j_service.close()
    logger.info("Neo4j connection closed")


app = FastAPI(
    title="Kene API",
    description="A FastAPI web service for managing activities, metrics, and insights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


def parse_cors_setting(value: str, default: list[str] | None = None) -> list[str]:
    """Parse comma-separated CORS configuration string into a list.

    Args:
        value: Comma-separated string of CORS values
        default: Default list to return if value is empty (defaults to ["*"])

    Returns:
        List of parsed and stripped values
    """
    if default is None:
        default = ["*"]
    return [item.strip() for item in value.split(",")] if value else default


# Configure CORS
# Parse CORS settings from environment (comma-separated strings)
cors_origins = parse_cors_setting(settings.cors_origins)
cors_methods = parse_cors_setting(settings.cors_methods)
cors_headers = parse_cors_setting(settings.cors_headers)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

# Request ID middleware (generates correlation ID per request)
from .middleware.request_id import RequestIdMiddleware

app.add_middleware(RequestIdMiddleware)

# Latency metrics middleware (Prometheus histogram per route)
from .metrics.latency_metrics import LatencyMiddleware

app.add_middleware(LatencyMiddleware)

# Include routers
app.include_router(auth.router)  # Auth router already has its prefix
app.include_router(
    organizations.router, prefix="/api/v1/organizations", tags=["organizations"]
)
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(agent_configs.router)  # Agent configs router already has its prefix
app.include_router(agent_configs.account_router)  # Per-account agent-config CRUD (AH-PRD-02 Phase 3)
app.include_router(account_tools.router)  # Per-account tool inventory (AH-PRD-06)
app.include_router(integrations.router)  # Integrations router already has its prefix
app.include_router(oauth_integrations.router)  # OAuth router already has its prefix
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(monitoring.router)  # Monitoring router for Prometheus metrics
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["datasets"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(activities.router, prefix="/api/v1/activities", tags=["activities"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(intuitions.router, prefix="/api/v1/intuitions", tags=["intuitions"])
app.include_router(chat.router)  # Chat router already has its prefix
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
app.include_router(home.router, prefix="/api/v1/home", tags=["home"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(
    notifications.router, prefix="/api/v1/notifications", tags=["notifications"]
)
app.include_router(
    funnel_reports.router, prefix="/api/v1/funnel-reports", tags=["funnel-reports"]
)
app.include_router(firestore.router, prefix="/api/v1/firestore", tags=["firestore"])
app.include_router(
    superset_saved_queries.router,
    prefix="/api/v1/superset/saved-queries",
    tags=["superset-saved-queries"],
)
app.include_router(
    subscription_plans.router,
    prefix="/api/v1",
    tags=["subscription-plans"],
)
app.include_router(
    monitoring_topics.router,
    prefix="/api/v1",
    tags=["monitoring-topics"],
)
app.include_router(strategy.router)  # Strategy router already has its prefix
app.include_router(usage.router)  # Usage router already has its prefix
app.include_router(
    industry_keywords.router,
    prefix="/api/v1/industry-keywords",
    tags=["industry-keywords"],
)
app.include_router(
    industry_templates.router,
    prefix="/api/v1",
    tags=["industry-templates"],
)
app.include_router(knowledge_graph.router)  # Knowledge graph router already has its prefix
app.include_router(tools.router)  # Tools router already has its prefix
app.include_router(mcp.router)  # MCP server management router already has its prefix
app.include_router(mcp_server_configs.router)  # MCP server config admin router has its prefix


# Health and root endpoints below routers


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Kene API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for liveness probes.

    Returns 200 with healthy status when all critical services are up.
    Returns 503 with degraded status when any critical service is down.
    """
    try:
        neo4j_healthy = await neo4j_service.health_check()
    except Exception:
        neo4j_healthy = False

    try:
        firestore_healthy = get_firestore_service().health_check()
    except Exception:
        firestore_healthy = False

    # Check Redis health
    try:
        from .redis_client import get_redis_service

        redis_service = get_redis_service()
        redis_healthy = redis_service.is_available()
    except Exception:
        redis_healthy = False

    # Check MCP health
    mcp_status: dict[str, Any] = {}
    try:
        from app.adk.mcp_config import get_mcp_manager

        mcp_mgr = get_mcp_manager()
        mcp_status = mcp_mgr.get_status()
    except Exception:
        pass

    # Overall health is true if critical services are healthy
    # Redis and MCP are not critical - system works without them
    overall_healthy = neo4j_healthy and firestore_healthy
    status = "healthy" if overall_healthy else "degraded"
    status_code = 200 if overall_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "message": "API is running",
            "services": {
                "neo4j": "healthy" if neo4j_healthy else "unhealthy",
                "firestore": "healthy" if firestore_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unavailable",
                "mcp": {
                    "loaded_servers": mcp_status.get("loaded_count", 0),
                    "servers": [
                        {"name": s["name"], "health": s["health_status"]}
                        for s in mcp_status.get("servers", [])
                    ],
                }
                if mcp_status
                else "unavailable",
            },
        },
    )


@app.get("/ready")
async def readiness_check():
    """Readiness probe for Kubernetes.

    Returns 200 only when ALL critical dependencies are available.
    Returns 503 when not ready to serve traffic.
    """
    try:
        neo4j_healthy = await neo4j_service.health_check()
    except Exception:
        neo4j_healthy = False

    try:
        firestore_healthy = get_firestore_service().health_check()
    except Exception:
        firestore_healthy = False

    # Both critical services must be healthy for readiness
    if neo4j_healthy and firestore_healthy:
        return PlainTextResponse(status_code=200, content="Ready")
    else:
        return PlainTextResponse(status_code=503, content="Not Ready")
