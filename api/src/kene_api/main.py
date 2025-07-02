"""Kene API - FastAPI main application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import neo4j_service
from .firestore import firestore_service
from .routers import (
    activities,
    firestore,
    funnel_reports,
    home,
    insights,
    intuitions,
    items,
    metrics,
    superset_saved_queries,
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
        firestore_service.initialize()
        logger.info("Firestore service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore: {e}")
        # Continue without Firestore if initialization fails

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
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(activities.router, prefix="/api/v1/activities", tags=["activities"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(intuitions.router, prefix="/api/v1/intuitions", tags=["intuitions"])
app.include_router(items.router, prefix="/api/v1/items", tags=["items"])
app.include_router(home.router, prefix="/api/v1/home", tags=["home"])
app.include_router(
    funnel_reports.router, prefix="/api/v1/funnel-reports", tags=["funnel-reports"]
)
app.include_router(firestore.router, prefix="/api/v1/firestore", tags=["firestore"])
app.include_router(
    superset_saved_queries.router, 
    prefix="/api/v1/superset/saved-queries", 
    tags=["superset-saved-queries"]
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
        firestore_healthy = firestore_service.health_check()
    except Exception:
        firestore_healthy = False

    overall_healthy = neo4j_healthy and firestore_healthy

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "message": "API is running",
        "services": {
            "neo4j": "healthy" if neo4j_healthy else "unhealthy",
            "firestore": "healthy" if firestore_healthy else "unhealthy"
        },
    }
