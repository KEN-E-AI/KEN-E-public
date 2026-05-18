"""
Dependency injection for API endpoints.

Provides reusable dependencies for FastAPI routes with proper caching
and lifecycle management.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from google.cloud import firestore

if TYPE_CHECKING:
    from .services.feature_flag_service import FeatureFlagService


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


# ---------------------------------------------------------------------------
# Feature Flags — FF-PRD-01 §5.1
# ---------------------------------------------------------------------------


def get_feature_flag_service() -> FeatureFlagService:
    """FastAPI dependency that returns the process-wide FeatureFlagService singleton.

    Delegates to ``services.feature_flag_service.get_feature_flag_service`` so the
    router path (FastAPI Depends) and the helper path (``is_feature_enabled``)
    share the same cached instance and its 60 s in-process TTL cache. Two
    separate ``@lru_cache`` factories would each hold their own cache, doubling
    the kill-switch propagation window (FF-PRD-01 §7.4).
    """
    from .services.feature_flag_service import (
        get_feature_flag_service as _svc_singleton,
    )

    return _svc_singleton()
