"""Industry templates router for managing industry-specific account templates."""

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import (
    IndustryTemplate,
    IndustryTemplateListResponse,
)

router = APIRouter()

logger = logging.getLogger(__name__)

INDUSTRY_TEMPLATES_COLLECTION = "industry-templates"

# Cache configuration
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "development") == "development"
CACHE_TTL_SECONDS = 0 if IS_DEVELOPMENT else 3600  # 1 hour in production
CACHE_MAX_SIZE = 0 if IS_DEVELOPMENT else 128


class ThreadSafeTemplateCache:
    """Thread-safe cache for industry templates with TTL and size limits."""

    def __init__(self, max_size: int = 128, ttl_seconds: int = 3600):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache if exists and not expired."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if self._ttl_seconds == 0:  # No caching in development
                    del self._cache[key]
                    self._miss_count += 1
                    return None

                if datetime.now(timezone.utc) - timestamp < timedelta(
                    seconds=self._ttl_seconds
                ):
                    self._hit_count += 1
                    # Move to end (LRU behavior)
                    del self._cache[key]
                    self._cache[key] = (value, timestamp)
                    return value
                else:
                    # Expired
                    del self._cache[key]

            self._miss_count += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        if self._max_size == 0:  # No caching
            return

        with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Remove first (oldest) item
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            # Add or update
            self._cache[key] = (value, datetime.now(timezone.utc))

    def invalidate(self, key: str | None = None) -> None:
        """Invalidate specific key or entire cache."""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()

    def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern."""
        with self._lock:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hit_count,
                "misses": self._miss_count,
                "hit_ratio": self._hit_count
                / max(1, self._hit_count + self._miss_count),
            }


# Global cache instance
_template_cache = ThreadSafeTemplateCache(
    max_size=CACHE_MAX_SIZE, ttl_seconds=CACHE_TTL_SECONDS
)


def _parse_template_data(template_dict: dict[str, Any]) -> IndustryTemplate:
    """Parse raw Firestore data into IndustryTemplate model.

    The Pydantic model now handles both snake_case and camelCase field names
    via aliases, so we can pass the raw Firestore data directly.

    Note: recommendedSettings, defaultSettings, and name fields have been
    deprecated and removed from Firestore.
    """
    # Add timestamps if missing
    if "created_at" not in template_dict:
        template_dict["created_at"] = datetime.now(timezone.utc).isoformat()
    if "updated_at" not in template_dict:
        template_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Let Pydantic handle the parsing with its aliases
    return IndustryTemplate(**template_dict)


async def _fetch_all_templates(
    firestore_service: FirestoreService,
) -> list[IndustryTemplate]:
    """
    Fetch all templates from Firestore with caching.
    Uses dependency injection for FirestoreService.
    """
    cache_key = "all_templates"

    # Check cache first
    cached = _template_cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for {cache_key}")
        return cached

    logger.debug(f"Cache miss for {cache_key}, fetching from Firestore")

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    templates_data = firestore_service.list_documents(
        collection=INDUSTRY_TEMPLATES_COLLECTION,
        where_filters=[],
        limit=100,  # Should be enough for all industries
    )

    templates = []
    for template_dict in templates_data:
        try:
            template = _parse_template_data(template_dict)
            templates.append(template)
        except Exception as e:
            logger.warning(
                f"Failed to parse template {template_dict.get('id', 'unknown')}: {e}"
            )
            continue

    # Cache the result
    _template_cache.set(cache_key, templates)

    return templates


async def _fetch_template_by_industry(
    industry: str, firestore_service: FirestoreService
) -> IndustryTemplate | None:
    """
    Fetch a specific template by industry with caching.
    Uses dependency injection for FirestoreService.
    """
    cache_key = f"industry:{industry}"

    # Check cache first
    cached = _template_cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for {cache_key}")
        return cached

    logger.debug(f"Cache miss for {cache_key}, fetching from Firestore")

    # Try to get from all templates cache first (more efficient)
    all_templates = await _fetch_all_templates(firestore_service)
    for template in all_templates:
        if template.industry == industry:
            _template_cache.set(cache_key, template)
            return template

    # Not found in cached all_templates, try direct query
    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    # Try to fetch by industry field
    templates_data = firestore_service.list_documents(
        collection=INDUSTRY_TEMPLATES_COLLECTION,
        where_filters=[("industry", "==", industry)],
        limit=1,
    )

    if not templates_data:
        # Try searching in recommended_settings.industry
        templates_data = firestore_service.list_documents(
            collection=INDUSTRY_TEMPLATES_COLLECTION,
            where_filters=[("recommended_settings.industry", "==", industry)],
            limit=1,
        )

    if templates_data:
        template = _parse_template_data(templates_data[0])
        _template_cache.set(cache_key, template)
        return template

    # Cache the "not found" result too
    _template_cache.set(cache_key, None)
    return None


@router.get(
    "/industry-templates",
    response_model=IndustryTemplateListResponse,
    response_model_by_alias=False,
)
async def list_industry_templates(
    active_only: bool = True,
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> IndustryTemplateListResponse:
    """
    Get all industry templates.

    **Parameters:**
    - `active_only` (query): Whether to return only active templates (default: true)

    **Returns:**
    - List of industry templates with their configurations

    **Example:**
    ```
    GET /api/v1/industry-templates?active_only=true
    ```
    """
    try:
        # Fetch all templates with caching
        all_templates = await _fetch_all_templates(firestore_service)

        # Filter if needed
        if active_only:
            templates = [t for t in all_templates if t.is_active]
        else:
            templates = all_templates

        return IndustryTemplateListResponse(templates=templates, total=len(templates))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching industry templates: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch industry templates"
        )


@router.get(
    "/industry-templates/industry/{industry}",
    response_model=IndustryTemplate,
    response_model_by_alias=False,
)
async def get_industry_template(
    industry: str = Path(
        ..., description="Industry name", min_length=1, max_length=200
    ),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> IndustryTemplate:
    """
    Get a specific industry template by industry name.

    **Parameters:**
    - `industry` (path): The industry name (e.g., "Retail Trade [B2C]")

    **Returns:**
    - Industry template with configuration

    **Example:**
    ```
    GET /api/v1/industry-templates/industry/Retail%20Trade%20%5BB2C%5D
    ```
    """
    try:
        template = await _fetch_template_by_industry(industry, firestore_service)

        if template is None:
            raise HTTPException(
                status_code=404, detail=f"Template not found for industry: {industry}"
            )

        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching template for industry {industry}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch template for industry: {industry}"
        )


@router.get(
    "/industry-templates/{template_id}",
    response_model=IndustryTemplate,
    response_model_by_alias=False,
)
async def get_template_by_id(
    template_id: str = Path(
        ..., description="Template ID", min_length=1, max_length=200
    ),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> IndustryTemplate:
    """
    Get a specific industry template by ID.

    **Parameters:**
    - `template_id` (path): The template ID

    **Returns:**
    - Industry template with configuration

    **Example:**
    ```
    GET /api/v1/industry-templates/e-commerce
    ```
    """
    try:
        # Check cache first
        cache_key = f"id:{template_id}"
        cached = _template_cache.get(cache_key)
        if cached is not None:
            return cached

        # Try to find in all templates cache
        all_templates = await _fetch_all_templates(firestore_service)
        for template in all_templates:
            if template.id == template_id:
                _template_cache.set(cache_key, template)
                return template

        # Not found in cache, fetch directly
        if not firestore_service.health_check():
            raise HTTPException(status_code=503, detail="Firestore service unavailable")

        template_dict = firestore_service.get_document(
            collection=INDUSTRY_TEMPLATES_COLLECTION, document_id=template_id
        )

        if not template_dict:
            raise HTTPException(
                status_code=404, detail=f"Template not found: {template_id}"
            )

        template = _parse_template_data(template_dict)
        _template_cache.set(cache_key, template)
        return template

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching template {template_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch template: {template_id}"
        )


@router.put(
    "/industry-templates/{template_id}",
    response_model=IndustryTemplate,
    response_model_by_alias=False,
)
async def update_industry_template(
    template_id: str = Path(
        ..., description="Template ID", min_length=1, max_length=200
    ),
    template_data: IndustryTemplate = ...,
    user: UserContext = Depends(get_current_user_context),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> IndustryTemplate:
    """
    Update an industry template (super admin only).

    **Authorization:** Super admin only

    **Parameters:**
    - `template_id` (path): The template ID to update
    - `template_data` (body): Updated template data

    **Returns:**
    - Updated industry template

    **Example:**
    ```
    PUT /api/v1/industry-templates/e-commerce
    ```
    """
    # Check super admin permission
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can update industry templates"
        )

    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    try:
        # Prepare update data
        update_data = template_data.model_dump()
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        update_data["id"] = template_id  # Ensure ID matches

        # Update in Firestore
        success = firestore_service.set_document(
            collection=INDUSTRY_TEMPLATES_COLLECTION,
            document_id=template_id,
            data=update_data,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update template")

        # Invalidate related cache entries
        _template_cache.invalidate("all_templates")
        _template_cache.invalidate(f"id:{template_id}")
        _template_cache.invalidate(f"industry:{template_data.industry}")

        logger.info(f"Updated template {template_id}, invalidated cache")

        return template_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template {template_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update template: {template_id}"
        )


@router.get("/industry-templates/cache/stats")
async def get_cache_stats(
    user: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """
    Get cache statistics (admin only).

    **Authorization:** Admin only

    **Returns:**
    - Cache statistics including size, hits, misses, and hit ratio
    """
    # Check admin permission
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only admins can view cache statistics"
        )

    return _template_cache.get_stats()


@router.post("/industry-templates/cache/clear")
async def clear_cache(
    pattern: str | None = None,
    user: UserContext = Depends(get_current_user_context),
) -> dict[str, str]:
    """
    Clear cache entries (admin only).

    **Authorization:** Admin only

    **Parameters:**
    - `pattern` (query): Optional pattern to match cache keys to clear

    **Returns:**
    - Success message
    """
    # Check admin permission
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Only admins can clear cache")

    if pattern:
        _template_cache.invalidate_pattern(pattern)
        return {"message": f"Cleared cache entries matching pattern: {pattern}"}
    else:
        _template_cache.invalidate()
        return {"message": "Cleared all cache entries"}
