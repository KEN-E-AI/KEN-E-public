"""Kene API - FastAPI main application."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

from .database import neo4j_service
from .firestore import get_firestore_service
from .routers import (
    accounts,
    activities,
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
    metrics,
    monitoring,
    monitoring_topics,
    oauth_integrations,
    organizations,
    products,
    strategy,
    subscription_plans,
    superset_saved_queries,
    usage,
    users,
)
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

    yield

    # Shutdown
    logger.info("Shutting down Kene API...")
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)  # Auth router already has its prefix
app.include_router(
    organizations.router, prefix="/api/v1/organizations", tags=["organizations"]
)
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
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
    """Health check endpoint."""
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

    # Overall health is true if critical services are healthy
    # Redis is not critical - system works without it
    overall_healthy = neo4j_healthy and firestore_healthy

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "message": "API is running",
        "services": {
            "neo4j": "healthy" if neo4j_healthy else "unhealthy",
            "firestore": "healthy" if firestore_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unavailable",
        },
    }
