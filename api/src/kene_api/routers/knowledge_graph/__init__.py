"""Unified knowledge graph router.

Combines all domain-specific routers (business, competitive, marketing, brand)
and aggregated view endpoints into a single knowledge graph API.
"""

from fastapi import APIRouter

from . import aggregated, brand, business, competitive, marketing

# Main router with prefix and tags
router = APIRouter(
    prefix="/api/v1/knowledge-graph",
    tags=["knowledge-graph"],
)

# Include all domain routers
router.include_router(business.router)
router.include_router(competitive.router)
router.include_router(marketing.router)
router.include_router(brand.router)
router.include_router(aggregated.router)

__all__ = ["router"]
