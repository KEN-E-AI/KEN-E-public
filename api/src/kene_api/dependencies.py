"""
Dependency injection for API endpoints.

Provides reusable dependencies for FastAPI routes with proper caching
and lifecycle management.
"""

import os
from functools import lru_cache

from google.cloud import firestore


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.Client:
    """
    Get cached Firestore client instance.

    Uses lru_cache to ensure single instance across application lifecycle.
    Thread-safe and reuses connection pool for optimal performance.

    Returns:
        Firestore client instance

    Note:
        The client is cached for the entire application lifetime.
        This provides ~10x performance improvement over creating
        a new client on each request.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")
    return firestore.Client(project=project_id)


def get_firestore() -> firestore.Client:
    """
    FastAPI dependency for Firestore client.

    Returns the cached Firestore client instance. Use as a dependency
    in route handlers to automatically inject the client.

    Usage:
        @router.get("/endpoint")
        async def my_endpoint(db: firestore.Client = Depends(get_firestore)):
            # Use db here
            collection = db.collection("my_collection")

    Returns:
        Firestore client instance (cached singleton)
    """
    return get_firestore_client()
