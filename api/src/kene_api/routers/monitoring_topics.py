"""Router for news and social media monitoring topics management."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from ..auth import UserContext, get_current_user_context
from ..cache import (
    CacheService,
    InMemoryCache,
    all_industry_keywords_key,
    industry_keywords_key,
)
from ..database import get_neo4j_service
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import SuccessResponse
from ..models.monitoring_models import (
    AddCompetitorRequest,
    CompetitorEntry,
    IndustryKeywords,
    IndustryKeywordsListResponse,
    MonitoringTopics,
    MonitoringTopicsResponse,
    PaginatedKeywordsRequest,
    PaginatedKeywordsResponse,
    UpdateCompanyKeywordsRequest,
    UpdateCompetitorRequest,
    UpdateCustomerKeywordsRequest,
    UpdateIndustryKeywordsRequest,
)
# Create a module-level cache service (in-memory for now)
# In production, this would be initialized with Redis
_cache_service = CacheService(InMemoryCache())

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
    {"value": "Administrative and Support and Waste Management and Remediation Services"},
    {"value": "Educational Services"},
    {"value": "Health Care and Social Assistance"},
    {"value": "Arts, Entertainment, and Recreation"},
    {"value": "Accommodation and Food Services"},
    {"value": "Other Services (except Public Administration)"},
    {"value": "Public Administration"},
]

router = APIRouter(prefix="/monitoring-topics", tags=["monitoring-topics"])


@router.get("/test/{account_id}")
async def test_account_access(
    account_id: str = Path(..., description="Account ID"),
    user: UserContext = Depends(get_current_user_context),
) -> dict:
    """Test endpoint to debug account access."""
    return {
        "account_id": account_id,
        "user_id": user.user_id,
        "email": user.email,
        "is_super_admin": user.is_super_admin,
        "has_account_access": user.has_account_access(account_id),
        "accessible_accounts": user.accessible_accounts,
        "organization_permissions": user.organization_permissions,
        "account_permissions": user.account_permissions,
    }

logger = logging.getLogger(__name__)

# Constants
MONITORING_TOPICS_COLLECTION = "monitoring_topics"
INDUSTRY_KEYWORDS_COLLECTION = "industry_keywords"


async def get_or_create_monitoring_topics(
    account_id: str,
    organization_id: str,
    industry: str,
    firestore: FirestoreService,
) -> MonitoringTopics:
    """Get existing monitoring topics or create new ones for an account."""
    try:
        # Try to get existing document
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if doc:
            return MonitoringTopics(**doc)
        
        # Create new document if not exists
        # Get industry keywords
        industry_keywords = await get_industry_keywords_for_industry(
            industry, firestore
        )
        
        now = datetime.utcnow().isoformat()
        monitoring_topics = MonitoringTopics(
            account_id=account_id,
            organization_id=organization_id,
            industry_keywords=industry_keywords,
            company_keywords=[],
            customer_keywords=[],
            competitor_entries=[],
            created_at=now,
            updated_at=now,
        )
        
        # Save to Firestore
        firestore.create_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data=monitoring_topics.model_dump(),
        )
        
        return monitoring_topics
    except Exception as e:
        logger.error(f"Error getting/creating monitoring topics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve monitoring topics"
        )


async def get_industry_keywords_for_industry(
    industry: str, firestore: FirestoreService
) -> list[str]:
    """Get keywords for a specific industry with caching."""
    cache_key = industry_keywords_key(industry)
    
    # Try cache first
    cached = _cache_service.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for industry keywords: {industry}")
        return cached
    
    try:
        doc_id = industry.lower().replace(" ", "_").replace(",", "")
        doc = firestore.get_document(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            document_id=doc_id,
        )
        
        keywords = doc.get("keywords", []) if doc else []
        
        # Cache for 24 hours (industry keywords change rarely)
        _cache_service.set(cache_key, keywords, ttl_seconds=86400)
        
        return keywords
    except Exception as e:
        logger.error(f"Error getting industry keywords: {str(e)}")
        return []


async def update_accounts_with_industry(
    industry: str, keywords: list[str], firestore: FirestoreService
) -> None:
    """Update all accounts that have the specified industry."""
    try:
        # Query all monitoring topics documents
        # Note: This is a simplified approach. In production, you might want to
        # batch process this or use a background job for large datasets
        all_docs = firestore.query_documents(
            collection=MONITORING_TOPICS_COLLECTION,
            limit=1000,  # Adjust based on expected scale
        )
        
        # Filter and update accounts with matching industry
        for doc in all_docs:
            # We need to cross-reference with account data to check industry
            # For now, we'll update based on a simple check
            # In production, you'd want to join with accounts data
            firestore.update_document(
                collection=MONITORING_TOPICS_COLLECTION,
                document_id=doc["account_id"],
                data={
                    "industry_keywords": keywords,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
    except Exception as e:
        logger.error(f"Error updating accounts with industry keywords: {str(e)}")


@router.get("/{account_id}", response_model=MonitoringTopicsResponse)
async def get_monitoring_topics(
    account_id: str = Path(..., description="Account ID"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> MonitoringTopicsResponse:
    """Get all monitoring topics for an account."""
    # Check user has access to this account
    if not user.has_account_access(account_id) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to account {account_id}"
        )
    
    try:
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if doc:
            return MonitoringTopicsResponse(
                success=True,
                data=MonitoringTopics(**doc)
            )
        else:
            # Document doesn't exist, try to create it
            # Get account details from Neo4j
            neo4j = await get_neo4j_service()
            
            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """
            
            try:
                async with neo4j.get_session() as session:
                    result = await session.run(account_query, {"account_id": account_id})
                    record = await result.single()
            except Exception as e:
                logger.error(f"Neo4j query error for account {account_id}: {str(e)}", exc_info=True)
                raise
                
            if not record:
                logger.error(f"Account {account_id} not found in Neo4j")
                return MonitoringTopicsResponse(
                    success=True,
                    data=None
                )
                
            industry = record["industry"]
            organization_id = record["organization_id"]
            
            # Create monitoring topics document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
            
            return MonitoringTopicsResponse(
                success=True,
                data=monitoring_topics
            )
    except Exception as e:
        logger.error(f"Error retrieving monitoring topics for account {account_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve monitoring topics: {str(e)}"
        )


@router.put("/{account_id}/company", response_model=SuccessResponse)
async def update_company_keywords(
    account_id: str = Path(..., description="Account ID"),
    request: UpdateCompanyKeywordsRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Update company keywords for an account."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Write access denied to account {account_id}"
        )
    
    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID in path does not match request body"
        )
    
    try:
        # First check if document exists
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            # Need to get account info to create the document
            # Get account details from Neo4j
            neo4j = await get_neo4j_service()
            
            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """
            
            async with neo4j.get_session() as session:
                result = await session.run(account_query, {"account_id": account_id})
                record = await result.single()
                
                if not record:
                    raise HTTPException(
                        status_code=404,
                        detail="Account not found"
                    )
                
                industry = record["industry"]
                organization_id = record["organization_id"]
            
            # Create the document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
        
        # Now update the document
        firestore.update_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data={
                "company_keywords": request.company_keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        return SuccessResponse(
            message="Company keywords updated successfully",
            data={"company_keywords": request.company_keywords}
        )
    except Exception as e:
        logger.error(f"Error updating company keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update company keywords"
        )


@router.put("/{account_id}/customers", response_model=SuccessResponse)
async def update_customer_keywords(
    account_id: str = Path(..., description="Account ID"),
    request: UpdateCustomerKeywordsRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Update customer keywords for an account."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Write access denied to account {account_id}"
        )
    
    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID in path does not match request body"
        )
    
    try:
        # First check if document exists
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            # Need to get account info to create the document
            # Get account details from Neo4j
            neo4j = await get_neo4j_service()
            
            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """
            
            async with neo4j.get_session() as session:
                result = await session.run(account_query, {"account_id": account_id})
                record = await result.single()
                
                if not record:
                    raise HTTPException(
                        status_code=404,
                        detail="Account not found"
                    )
                
                industry = record["industry"]
                organization_id = record["organization_id"]
            
            # Create the document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
        
        # Now update the document
        firestore.update_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data={
                "customer_keywords": request.customer_keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        return SuccessResponse(
            message="Customer keywords updated successfully",
            data={"customer_keywords": request.customer_keywords}
        )
    except Exception as e:
        logger.error(f"Error updating customer keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update customer keywords"
        )


@router.post("/{account_id}/competitors", response_model=SuccessResponse)
async def add_competitor(
    account_id: str = Path(..., description="Account ID"),
    request: AddCompetitorRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Add a new competitor to monitor."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Write access denied to account {account_id}"
        )
    
    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID in path does not match request body"
        )
    
    try:
        # Get current document
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            # Need to get account info to create the document
            # Get account details from Neo4j
            neo4j = await get_neo4j_service()
            
            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """
            
            async with neo4j.get_session() as session:
                result = await session.run(account_query, {"account_id": account_id})
                record = await result.single()
                
                if not record:
                    raise HTTPException(
                        status_code=404,
                        detail="Account not found"
                    )
                
                industry = record["industry"]
                organization_id = record["organization_id"]
            
            # Create the document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
            doc = monitoring_topics.model_dump()
        
        # Add new competitor
        competitors = doc.get("competitor_entries", [])
        new_competitor = CompetitorEntry(
            name=request.name,
            website=request.website,
            keywords=request.keywords or [request.name.lower()]
        )
        competitors.append(new_competitor.model_dump())
        
        # Update document
        firestore.update_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        return SuccessResponse(
            message="Competitor added successfully",
            data={"competitor": new_competitor.model_dump()}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding competitor: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to add competitor"
        )


@router.put("/{account_id}/competitors/{competitor_index}", response_model=SuccessResponse)
async def update_competitor(
    account_id: str = Path(..., description="Account ID"),
    competitor_index: int = Path(..., description="Competitor index in array"),
    request: UpdateCompetitorRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Update an existing competitor."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Write access denied to account {account_id}"
        )
    
    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID in path does not match request body"
        )
    
    # Validate competitor_index matches
    if request.competitor_index != competitor_index:
        raise HTTPException(
            status_code=400,
            detail="Competitor index in path does not match request body"
        )
    
    try:
        # Get current document
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Monitoring topics not found for this account"
            )
        
        # Get competitors
        competitors = doc.get("competitor_entries", [])
        
        if competitor_index < 0 or competitor_index >= len(competitors):
            raise HTTPException(
                status_code=404,
                detail="Competitor not found at specified index"
            )
        
        # Update competitor
        if request.name is not None:
            competitors[competitor_index]["name"] = request.name
        if request.website is not None:
            competitors[competitor_index]["website"] = request.website
        if request.keywords is not None:
            competitors[competitor_index]["keywords"] = request.keywords
        
        # Update document
        firestore.update_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        return SuccessResponse(
            message="Competitor updated successfully",
            data={"competitor": competitors[competitor_index]}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating competitor: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update competitor"
        )


@router.delete("/{account_id}/competitors/{competitor_index}", response_model=SuccessResponse)
async def delete_competitor(
    account_id: str = Path(..., description="Account ID"),
    competitor_index: int = Path(..., description="Competitor index in array"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Delete a competitor from monitoring."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Write access denied to account {account_id}"
        )
    
    try:
        # Get current document
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail="Monitoring topics not found for this account"
            )
        
        # Get competitors
        competitors = doc.get("competitor_entries", [])
        
        if competitor_index < 0 or competitor_index >= len(competitors):
            raise HTTPException(
                status_code=404,
                detail="Competitor not found at specified index"
            )
        
        # Remove competitor
        deleted_competitor = competitors.pop(competitor_index)
        
        # Update document
        firestore.update_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        
        return SuccessResponse(
            message="Competitor deleted successfully",
            data={"deleted_competitor": deleted_competitor}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting competitor: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete competitor"
        )


@router.get("/{account_id}/company/paginated", response_model=PaginatedKeywordsResponse)
async def get_company_keywords_paginated(
    account_id: str = Path(..., description="Account ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    search: str | None = Query(None, description="Search term"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> PaginatedKeywordsResponse:
    """Get company keywords with pagination support."""
    # Check user has access to this account
    if not user.has_account_access(account_id) and not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to account {account_id}"
        )
    
    try:
        doc = firestore.get_document(
            collection=MONITORING_TOPICS_COLLECTION,
            document_id=account_id,
        )
        
        if not doc:
            return PaginatedKeywordsResponse(
                keywords=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )
        
        # Get all keywords
        all_keywords = doc.get("company_keywords", [])
        
        # Filter by search term if provided
        if search:
            search_lower = search.lower()
            all_keywords = [k for k in all_keywords if search_lower in k.lower()]
        
        # Calculate pagination
        total = len(all_keywords)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Get page of keywords
        page_keywords = all_keywords[start_idx:end_idx]
        
        return PaginatedKeywordsResponse(
            keywords=page_keywords,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    except Exception as e:
        logger.error(f"Error retrieving paginated company keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve keywords"
        )


@router.get("/industries/all", response_model=IndustryKeywordsListResponse)
async def get_all_industry_keywords(
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> IndustryKeywordsListResponse:
    """Get keywords for all industries (super admin only) with caching."""
    # Check if user is super admin
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can view industry keywords"
        )
    
    # Try cache first
    cache_key = all_industry_keywords_key()
    cached = _cache_service.get(cache_key)
    if cached is not None:
        logger.debug("Cache hit for all industry keywords")
        return IndustryKeywordsListResponse(
            success=True,
            industries=[IndustryKeywords(**item) for item in cached]
        )
    
    try:
        # Get all industry keyword documents
        docs = firestore.query_documents(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            limit=100,  # Should be enough for all industries
        )
        
        industries = []
        for doc in docs:
            industries.append(IndustryKeywords(**doc))
        
        # Cache for 24 hours
        _cache_service.set(
            cache_key, 
            [ind.model_dump() for ind in industries], 
            ttl_seconds=86400
        )
        
        return IndustryKeywordsListResponse(
            success=True,
            industries=industries
        )
    except Exception as e:
        logger.error(f"Error retrieving industry keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve industry keywords"
        )


@router.put("/industries/{industry}", response_model=SuccessResponse)
async def update_industry_keywords(
    industry: str = Path(..., description="Industry name"),
    request: UpdateIndustryKeywordsRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Update keywords for a specific industry (super admin only)."""
    # Check if user is super admin
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Only super admins can modify industry keywords"
        )
    
    # Validate industry exists
    valid_industries = [opt["value"] for opt in INDUSTRY_OPTIONS]
    if industry not in valid_industries:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid industry: {industry}"
        )
    
    try:
        # Update industry keywords document
        doc_id = industry.lower().replace(" ", "_").replace(",", "")
        doc_data = {
            "industry": industry,
            "keywords": request.keywords,
            "updated_by": user.user_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        firestore.create_document(
            collection=INDUSTRY_KEYWORDS_COLLECTION,
            document_id=doc_id,
            data=doc_data,
        )
        
        # Invalidate cache
        _cache_service.delete(industry_keywords_key(industry))
        _cache_service.delete(all_industry_keywords_key())
        
        # Update all accounts with this industry
        # Note: In production, this should be done asynchronously
        await update_accounts_with_industry(industry, request.keywords, firestore)
        
        return SuccessResponse(
            message=f"Industry keywords updated for {industry}",
            data={"keywords": request.keywords}
        )
    except Exception as e:
        logger.error(f"Error updating industry keywords: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update industry keywords"
        )