"""Router for industry keywords management - provides admin interface for super admins."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..cache import (
    CacheService,
    all_industry_keywords_key,
    industry_keywords_key,
)
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import SuccessResponse
from ..models.monitoring_models import IndustryKeywords, IndustryKeywordsListResponse

logger = logging.getLogger(__name__)

# Module-level cache service. CacheService speaks the redis-py client
# protocol; with no Redis client configured it is constructed disabled so
# every get/set/delete cleanly short-circuits. Pass a real Redis client here
# to enable caching.
_cache_service = CacheService(None)

# Constants
INDUSTRY_KEYWORDS_COLLECTION = "industry_keywords"

# Define industry options locally until we have a shared constants file
INDUSTRY_OPTIONS = [
    {"value": "Agriculture, Forestry, Fishing and Hunting"},
    {"value": "Utilities"},
    {"value": "Construction"},
    {"value": "Manufacturing"},
    {"value": "Wholesale Trade [B2B]"},
    {"value": "Retail Trade"},
    {"value": "Transportation and Warehousing"},
    {"value": "Information"},
    {"value": "Finance and Insurance"},
    {"value": "Real Estate and Rental and Leasing"},
    {"value": "Professional, Scientific, and Technical Services"},
    {"value": "Management of Companies and Enterprises"},
    {
        "value": "Administrative and Support and Waste Management and Remediation Services"
    },
    {"value": "Educational Services"},
    {"value": "Health Care and Social Assistance"},
    {"value": "Arts, Entertainment, and Recreation"},
    {"value": "Accommodation and Food Services"},
    {"value": "Other Services (except Public Administration)"},
    {"value": "Public Administration"},
]

router = APIRouter(tags=["industry-keywords"])


async def check_super_admin(user: UserContext) -> None:
    """Check if user is super admin, raise 403 if not."""
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can manage industry keywords"
        )


@router.get("/", response_model=list[IndustryKeywords])
async def get_all_industry_keywords(
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> list[IndustryKeywords]:
    """
    Get keywords for all industries (super admin only).

    Returns a list of all industry keyword mappings.
    This endpoint is used by the admin panel to display and manage
    industry-specific keywords that are automatically applied to accounts.

    **Authorization**: Super admin only

    **Returns**:
    - List of IndustryKeywords objects

    **Example**:
    ```
    GET /api/v1/industry-keywords/
    ```
    """
    await check_super_admin(user)

    # Try cache first
    cache_key = all_industry_keywords_key()
    try:
        cached = _cache_service.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for all industry keywords")
            return [IndustryKeywords(**item) for item in cached]
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")

    try:
        # Get all industry keyword documents
        docs = firestore.list_documents(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            limit=100,  # Should be enough for all industries
        )

        industries = []
        for doc in docs:
            industries.append(IndustryKeywords(**doc))

        # Cache for 24 hours
        try:
            _cache_service.set(
                cache_key, [ind.model_dump() for ind in industries], ttl_seconds=86400
            )
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

        return industries
    except Exception as e:
        logger.error(f"Error retrieving industry keywords: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve industry keywords"
        )


@router.put("/{industry}", response_model=SuccessResponse)
async def update_industry_keywords(
    industry: str = Path(..., description="Industry name"),
    keywords: list[str] = Body(..., description="List of keywords for this industry"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update keywords for a specific industry (super admin only).

    This endpoint updates the keyword list for a given industry.
    The keywords are automatically applied to all accounts in that industry.

    **Authorization**: Super admin only

    **Parameters**:
    - `industry` (path): The industry name (must match one of the predefined industries)
    - `keywords` (body): List of keywords to associate with this industry

    **Returns**:
    - Success response with updated keywords

    **Example**:
    ```
    PUT /api/v1/industry-keywords/Finance%20and%20Insurance
    ["finance", "banking", "insurance", "investment", "fintech"]
    ```
    """
    await check_super_admin(user)

    # Validate industry exists
    valid_industries = [opt["value"] for opt in INDUSTRY_OPTIONS]
    if industry not in valid_industries:
        raise HTTPException(status_code=400, detail=f"Invalid industry: {industry}")

    try:
        # Update industry keywords document
        doc_id = industry.lower().replace(" ", "_").replace(",", "")
        doc_data = {
            "industry": industry,
            "keywords": keywords,
            "updated_by": user.user_id,
            "updated_at": datetime.utcnow().isoformat(),
        }

        firestore.create_document(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            document_id=doc_id,
            data=doc_data,
        )

        # Invalidate cache
        try:
            _cache_service.delete(industry_keywords_key(industry))
            _cache_service.delete(all_industry_keywords_key())
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")

        # Note: Updating accounts with this industry is handled asynchronously
        # in the actual implementation via a background job

        return SuccessResponse(
            message=f"Industry keywords updated for {industry}",
            data={"keywords": keywords},
        )
    except Exception as e:
        logger.error(f"Error updating industry keywords: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to update industry keywords"
        )


@router.delete("/{industry}", response_model=SuccessResponse)
async def delete_industry_keywords(
    industry: str = Path(..., description="Industry name"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete keywords for a specific industry (super admin only).

    This removes all keywords for the specified industry.
    Accounts in this industry will no longer have auto-generated keywords.

    **Authorization**: Super admin only

    **Parameters**:
    - `industry` (path): The industry name

    **Returns**:
    - Success response confirming deletion

    **Example**:
    ```
    DELETE /api/v1/industry-keywords/Finance%20and%20Insurance
    ```
    """
    await check_super_admin(user)

    # Validate industry exists
    valid_industries = [opt["value"] for opt in INDUSTRY_OPTIONS]
    if industry not in valid_industries:
        raise HTTPException(status_code=400, detail=f"Invalid industry: {industry}")

    try:
        # Delete industry keywords document
        doc_id = industry.lower().replace(" ", "_").replace(",", "")

        # Check if document exists
        existing_doc = firestore.get_document(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            document_id=doc_id,
        )

        if not existing_doc:
            raise HTTPException(
                status_code=404, detail=f"No keywords found for industry: {industry}"
            )

        # Delete the document
        firestore.delete_document(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            document_id=doc_id,
        )

        # Invalidate cache
        try:
            _cache_service.delete(industry_keywords_key(industry))
            _cache_service.delete(all_industry_keywords_key())
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")

        return SuccessResponse(
            message=f"Industry keywords deleted for {industry}",
            data={"industry": industry},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting industry keywords: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to delete industry keywords"
        )
