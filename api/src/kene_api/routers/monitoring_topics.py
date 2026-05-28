"""Router for news and social media monitoring topics management."""

import logging
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
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
    AddCustomerConceptRequest,
    AddCustomerProfileRequest,
    ConceptOption,
    CustomerKeywordConcept,
    IndustryKeywords,
    IndustryKeywordsListResponse,
    MonitoringTopics,
    MonitoringTopicsResponse,
    PaginatedKeywordsResponse,
    UpdateCompanyKeywordsRequest,
    UpdateCompetitorRequest,
    UpdateCustomerKeywordsRequest,
    UpdateCustomerProfileRequest,
    UpdateIndustryKeywordsRequest,
)
from ..services.concept_service import ConceptDisambiguationService

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
INDUSTRY_KEYWORDS_COLLECTION = "industry_keywords"


def _monitoring_topics_subcollection(account_id: str) -> str:
    return f"accounts/{account_id}/monitoring_topics"


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
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
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
            customer_profile_entries=[],
            created_at=now,
            updated_at=now,
        )

        # Save to Firestore
        firestore.create_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data=monitoring_topics.model_dump(),
        )

        return monitoring_topics
    except Exception as e:
        logger.error(f"Error getting/creating monitoring topics: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve monitoring topics"
        ) from e


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
        logger.error(f"Error getting industry keywords: {e!s}")
        return []


async def update_accounts_with_industry(
    industry: str, keywords: list[str], firestore: FirestoreService
) -> None:
    """Update all accounts that have the specified industry."""
    try:
        # Use collection-group query per Shape B cross-account pattern (README §7.7).
        # Derive account_id from the document path — never from the payload field
        # (deriving from the payload would redirect writes to the wrong tenant on
        # corrupt or mismatched data — DM-PRD-04 §8 risk).
        db = firestore.get_client()
        # DM-PRD-04: Shape B subcollection name (post-migration), not the legacy
        # `monitoring_topics/{account_id}` root — collection-group query per README §7.7.
        for doc_snap in db.collection_group("monitoring_topics").stream():
            parent = doc_snap.reference.parent
            if parent is None or parent.parent is None:
                # Legacy root-level doc (before DM-28 runs); skip to avoid writing
                # to the wrong path.
                logger.debug(
                    f"Skipping legacy root-level monitoring_topics doc: {doc_snap.id}"
                )
                continue
            account_id = parent.parent.id
            # Verify path shape: must be accounts/{account_id}/monitoring_topics/{doc}
            # to guard against future subcollections at unexpected depths.
            expected_prefix = f"accounts/{account_id}/monitoring_topics"
            if not doc_snap.reference.path.startswith(expected_prefix):
                logger.warning(
                    f"Unexpected monitoring_topics path, skipping: {doc_snap.reference.path}"
                )
                continue
            # NOTE: This updates all accounts, not just those with the matching industry.
            # Filtering by account industry requires a join with account data and is
            # tracked as a follow-up (DM-PRD-04 §8 — industry-filter enhancement).
            firestore.update_document(
                collection=_monitoring_topics_subcollection(account_id),
                document_id="default",
                data={
                    "industry_keywords": keywords,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
    except Exception as e:
        logger.error(f"Error updating accounts with industry keywords: {e!s}")


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
            status_code=403, detail=f"Access denied to account {account_id}"
        )

    try:
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if doc:
            return MonitoringTopicsResponse(success=True, data=MonitoringTopics(**doc))
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
                    result = await session.run(
                        account_query, {"account_id": account_id}
                    )
                    record = await result.single()
            except Exception as e:
                logger.error(
                    f"Neo4j query error for account {account_id}: {e!s}",
                    exc_info=True,
                )
                raise

            if not record:
                logger.error(f"Account {account_id} not found in Neo4j")
                return MonitoringTopicsResponse(success=True, data=None)

            industry = record["industry"]
            organization_id = record["organization_id"]

            # Create monitoring topics document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )

            return MonitoringTopicsResponse(success=True, data=monitoring_topics)
    except Exception as e:
        logger.error(
            f"Error retrieving monitoring topics for account {account_id}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve monitoring topics: {e!s}"
        ) from e


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
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    try:
        # First check if document exists
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
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
                    raise HTTPException(status_code=404, detail="Account not found")

                industry = record["industry"]
                organization_id = record["organization_id"]

            # Create the document
            await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )

        # Now update the document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "company_keywords": request.company_keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Company keywords updated successfully",
            data={"company_keywords": request.company_keywords},
        )
    except Exception as e:
        logger.error(f"Error updating company keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update company keywords"
        ) from e


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
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    try:
        # First check if document exists
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
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
                    raise HTTPException(status_code=404, detail="Account not found")

                industry = record["industry"]
                organization_id = record["organization_id"]

            # Create the document
            await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )

        # Get existing concept keywords to preserve them
        existing_concepts = doc.get("customer_concepts", []) if doc else []
        concept_keywords = [
            c.get("keyword") for c in existing_concepts if c.get("keyword")
        ]

        # Combine the plain keywords from request with concept keywords
        # This maintains backward compatibility with the customer_keywords field
        all_keywords = list(set(request.customer_keywords + concept_keywords))

        # Now update the document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_keywords": all_keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Customer keywords updated successfully",
            data={"customer_keywords": all_keywords},
        )
    except Exception as e:
        logger.error(f"Error updating customer keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update customer keywords"
        ) from e


@router.get(
    "/{account_id}/customers/search-concepts", response_model=list[ConceptOption]
)
async def search_customer_concepts(
    account_id: str = Path(..., description="Account ID"),
    term: str = Query(..., description="Term to disambiguate"),
    user: UserContext = Depends(get_current_user_context),
) -> list[ConceptOption]:
    """Search for concept interpretations using free APIs and Gemini."""
    logger.info(
        f"Concept search request - account: {account_id}, term: {term}, user: {user.email}"
    )

    # Check user has access to this account
    if not user.has_account_access(account_id) and not user.is_super_admin:
        logger.warning(f"Access denied for user {user.email} to account {account_id}")
        raise HTTPException(
            status_code=403, detail=f"Access denied to account {account_id}"
        )

    try:
        # Check cache first (if available)
        cache_key = f"concepts:{term.lower()}"
        try:
            cached_results = await _cache_service.get(cache_key)
            if cached_results:
                logger.info(f"Returning cached concepts for term: {term}")
                return cached_results
        except AttributeError as e:
            # Cache service not available, continue without cache
            logger.debug(f"Cache service not available: {e}")
        except TypeError as e:
            # Cache service likely not initialized properly
            logger.debug(f"Cache service type error, likely not initialized: {e}")

        # Search for concepts
        logger.info(f"Initializing ConceptDisambiguationService for term: {term}")
        service = ConceptDisambiguationService()
        concepts = await service.search_concepts(term)

        # Cache results for 1 hour to reduce API calls (if cache is available)
        if concepts:
            try:
                # Note: CacheService.set uses ttl_seconds, not ttl
                _cache_service.set(cache_key, concepts, ttl_seconds=3600)
                logger.info(f"Cached {len(concepts)} concepts for term: {term}")
            except AttributeError as e:
                logger.debug(
                    f"Could not cache concepts, cache service not available: {e}"
                )
            except TypeError as e:
                logger.debug(f"Could not cache concepts, type error: {e}")
        else:
            logger.warning(f"No concepts found for term: {term}")

        return concepts

    except Exception as e:
        logger.error(
            f"Error in search_customer_concepts for term '{term}': {e!s}", exc_info=True
        )
        # Return empty list instead of raising error to allow frontend to handle gracefully
        return []


@router.post(
    "/{account_id}/customers/add-concept", response_model=CustomerKeywordConcept
)
async def add_customer_concept(
    account_id: str = Path(..., description="Account ID"),
    request: AddCustomerConceptRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> CustomerKeywordConcept:
    """Add a customer keyword with selected concept disambiguation."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    # Create concept entry
    concept = CustomerKeywordConcept(
        keyword=request.keyword,
        concept_id=request.concept_id,
        concept_type=request.concept_type,
        reference=request.reference,
        added_by=user.user_id,
        added_at=datetime.utcnow().isoformat(),
    )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            # Need to create the document first
            neo4j = await get_neo4j_service()
            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """

            async with neo4j.get_session() as session:
                result = await session.run(account_query, {"account_id": account_id})
                record = await result.single()

                if not record:
                    raise HTTPException(status_code=404, detail="Account not found")

                industry = record["industry"]
                organization_id = record["organization_id"]

            # Create monitoring topics document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
            doc = monitoring_topics.model_dump()

        # Add the new concept
        concepts = doc.get("customer_concepts", [])
        concepts.append(concept.model_dump())

        # Also update legacy customer_keywords for backward compatibility
        keywords = doc.get("customer_keywords", [])
        if request.keyword not in keywords:
            keywords.append(request.keyword)

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_concepts": concepts,
                "customer_keywords": keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return concept

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding customer concept: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to add customer concept"
        ) from e


@router.delete(
    "/{account_id}/customers/concepts/{concept_id}", response_model=SuccessResponse
)
async def remove_customer_concept(
    account_id: str = Path(..., description="Account ID"),
    concept_id: str = Path(..., description="Concept ID to remove"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Remove a customer concept."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            raise HTTPException(status_code=404, detail="Monitoring topics not found")

        # Remove the concept
        concepts = doc.get("customer_concepts", [])
        keyword_to_remove = None

        # Find and remove the concept
        updated_concepts = []
        found_concept = False
        for c in concepts:
            if c.get("concept_id") != concept_id:
                updated_concepts.append(c)
            else:
                keyword_to_remove = c.get("keyword")
                found_concept = True
                logger.info(
                    f"Found concept to remove: {concept_id}, keyword: {keyword_to_remove}"
                )

        if not found_concept:
            logger.warning(f"Concept {concept_id} not found in concepts list")
            raise HTTPException(
                status_code=404, detail=f"Concept {concept_id} not found"
            )

        # Also update legacy customer_keywords by removing the keyword
        keywords = doc.get("customer_keywords", [])
        if keyword_to_remove and keyword_to_remove in keywords:
            keywords.remove(keyword_to_remove)
            logger.info(f"Removed keyword '{keyword_to_remove}' from customer_keywords")

        # Log what we're updating
        logger.info(
            f"Updating document with {len(updated_concepts)} concepts (was {len(concepts)})"
        )
        logger.info(
            f"Updating document with {len(keywords)} keywords (was {len(doc.get('customer_keywords', []))})"
        )

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_concepts": updated_concepts,
                "customer_keywords": keywords,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Customer concept removed successfully",
            data={"removed_concept_id": concept_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing customer concept: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to remove customer concept"
        ) from e


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
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
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
                    raise HTTPException(status_code=404, detail="Account not found")

                industry = record["industry"]
                organization_id = record["organization_id"]

            # Create the document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
            doc = monitoring_topics.model_dump()

        # Add new competitor
        competitors = doc.get("competitor_entries", [])
        new_entry = request.competitor_entry
        competitors.append(new_entry.model_dump())

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Competitor added successfully",
            data={"competitor": new_entry.model_dump()},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding competitor: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to add competitor") from e


@router.put(
    "/{account_id}/competitors/{competitor_index}", response_model=SuccessResponse
)
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
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    # Validate competitor_index matches
    if request.competitor_index != competitor_index:
        raise HTTPException(
            status_code=400,
            detail="Competitor index in path does not match request body",
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            raise HTTPException(
                status_code=404, detail="Monitoring topics not found for this account"
            )

        # Get competitors
        competitors = doc.get("competitor_entries", [])

        if competitor_index < 0 or competitor_index >= len(competitors):
            raise HTTPException(
                status_code=404, detail="Competitor not found at specified index"
            )

        # Update competitor
        if request.node_id is not None:
            competitors[competitor_index]["node_id"] = request.node_id
        if request.name is not None:
            competitors[competitor_index]["name"] = request.name
        if request.website is not None:
            competitors[competitor_index]["website"] = request.website
        if request.keywords is not None:
            competitors[competitor_index]["keywords"] = request.keywords

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Competitor updated successfully",
            data={"competitor": competitors[competitor_index]},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating competitor: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update competitor"
        ) from e


@router.delete(
    "/{account_id}/competitors/{competitor_index}", response_model=SuccessResponse
)
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
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            raise HTTPException(
                status_code=404, detail="Monitoring topics not found for this account"
            )

        # Get competitors
        competitors = doc.get("competitor_entries", [])

        if competitor_index < 0 or competitor_index >= len(competitors):
            raise HTTPException(
                status_code=404, detail="Competitor not found at specified index"
            )

        # Remove competitor
        deleted_competitor = competitors.pop(competitor_index)

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "competitor_entries": competitors,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Competitor deleted successfully",
            data={"deleted_competitor": deleted_competitor},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting competitor: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to delete competitor"
        ) from e


# ==================== CUSTOMER PROFILE MONITORING ENDPOINTS ====================


@router.post("/{account_id}/customer-profiles", response_model=SuccessResponse)
async def add_customer_profile_keywords(
    account_id: str = Path(..., description="Account ID"),
    request: AddCustomerProfileRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Add a new customer profile to monitoring."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            # Need to get account info to create the document
            neo4j = await get_neo4j_service()

            account_query = """
            MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
            RETURN acc.industry as industry, org.organization_id as organization_id
            """

            async with neo4j.get_session() as session:
                result = await session.run(account_query, {"account_id": account_id})
                record = await result.single()

                if not record:
                    raise HTTPException(status_code=404, detail="Account not found")

                industry = record["industry"]
                organization_id = record["organization_id"]

            # Create the document
            monitoring_topics = await get_or_create_monitoring_topics(
                account_id, organization_id, industry, firestore
            )
            doc = monitoring_topics.model_dump()

        # Add new customer profile entry
        customer_profiles = doc.get("customer_profile_entries", [])
        new_entry = request.customer_profile_entry
        customer_profiles.append(new_entry.model_dump())

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_profile_entries": customer_profiles,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Customer profile keywords added successfully",
            data={"customer_profile": new_entry.model_dump()},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding customer profile keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to add customer profile keywords"
        ) from e


@router.put(
    "/{account_id}/customer-profiles/{customer_profile_index}",
    response_model=SuccessResponse,
)
async def update_customer_profile_keywords(
    account_id: str = Path(..., description="Account ID"),
    customer_profile_index: int = Path(
        ..., ge=0, description="Customer profile index in array"
    ),
    request: UpdateCustomerProfileRequest = Body(...),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Update an existing customer profile entry."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    # Validate account_id matches
    if request.account_id != account_id:
        raise HTTPException(
            status_code=400, detail="Account ID in path does not match request body"
        )

    # Validate customer_profile_index matches
    if request.customer_profile_index != customer_profile_index:
        raise HTTPException(
            status_code=400,
            detail="Customer profile index in path does not match request body",
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            raise HTTPException(
                status_code=404, detail="Monitoring topics not found for this account"
            )

        # Get customer profile entries
        customer_profiles = doc.get("customer_profile_entries", [])

        if customer_profile_index < 0 or customer_profile_index >= len(
            customer_profiles
        ):
            raise HTTPException(
                status_code=404,
                detail="Customer profile not found at specified index",
            )

        # Update customer profile
        if request.node_id is not None:
            customer_profiles[customer_profile_index]["node_id"] = request.node_id
        if request.keywords is not None:
            customer_profiles[customer_profile_index]["keywords"] = request.keywords

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_profile_entries": customer_profiles,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Customer profile keywords updated successfully",
            data={"customer_profile": customer_profiles[customer_profile_index]},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer profile keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update customer profile keywords"
        ) from e


@router.delete(
    "/{account_id}/customer-profiles/{customer_profile_index}",
    response_model=SuccessResponse,
)
async def delete_customer_profile_keywords(
    account_id: str = Path(..., description="Account ID"),
    customer_profile_index: int = Path(
        ..., ge=0, description="Customer profile index in array"
    ),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Delete a customer profile from monitoring."""
    # Check user has write access to this account
    if not user.has_account_access(account_id, ["edit"]) and not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail=f"Write access denied to account {account_id}"
        )

    try:
        # Get current document
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            raise HTTPException(
                status_code=404, detail="Monitoring topics not found for this account"
            )

        # Get customer profile entries
        customer_profiles = doc.get("customer_profile_entries", [])

        if customer_profile_index < 0 or customer_profile_index >= len(
            customer_profiles
        ):
            raise HTTPException(
                status_code=404,
                detail="Customer profile not found at specified index",
            )

        # Remove customer profile
        deleted_profile = customer_profiles.pop(customer_profile_index)

        # Update document
        firestore.update_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
            data={
                "customer_profile_entries": customer_profiles,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

        return SuccessResponse(
            message="Customer profile keywords deleted successfully",
            data={"deleted_customer_profile": deleted_profile},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer profile keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to delete customer profile keywords"
        ) from e


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
            status_code=403, detail=f"Access denied to account {account_id}"
        )

    try:
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            return PaginatedKeywordsResponse(
                keywords=[], total=0, page=page, page_size=page_size, total_pages=0
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
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Error retrieving paginated company keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve keywords"
        ) from e


@router.get("/industries/all", response_model=IndustryKeywordsListResponse)
async def get_all_industry_keywords(
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> IndustryKeywordsListResponse:
    """Get keywords for all industries (super admin only) with caching."""
    # Check if user is super admin
    if not user.is_super_admin:
        raise HTTPException(
            status_code=403, detail="Only super admins can view industry keywords"
        )

    # Try cache first
    cache_key = all_industry_keywords_key()
    cached = _cache_service.get(cache_key)
    if cached is not None:
        logger.debug("Cache hit for all industry keywords")
        return IndustryKeywordsListResponse(
            success=True, industries=[IndustryKeywords(**item) for item in cached]
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
            cache_key, [ind.model_dump() for ind in industries], ttl_seconds=86400
        )

        return IndustryKeywordsListResponse(success=True, industries=industries)
    except Exception as e:
        logger.error(f"Error retrieving industry keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve industry keywords"
        ) from e


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
            status_code=403, detail="Only super admins can modify industry keywords"
        )

    # Validate industry exists
    valid_industries = [opt["value"] for opt in INDUSTRY_OPTIONS]
    if industry not in valid_industries:
        raise HTTPException(status_code=400, detail=f"Invalid industry: {industry}")

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
            data={"keywords": request.keywords},
        )
    except Exception as e:
        logger.error(f"Error updating industry keywords: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update industry keywords"
        ) from e


@router.post("/{account_id}/cleanup-orphaned-entries", response_model=SuccessResponse)
async def cleanup_orphaned_monitoring_entries(
    account_id: str = Path(..., description="Account ID"),
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Clean up monitoring entries for deleted competitors/customer profiles.

    This endpoint finds and removes monitoring entries whose node_ids
    no longer exist in Neo4j. Requires admin access.

    Args:
        account_id: Account identifier
        user: User context from authentication
        firestore: Firestore service instance

    Returns:
        SuccessResponse with count of removed entries

    Raises:
        HTTPException: If user lacks admin access or cleanup fails
    """
    # Check user has admin access
    if not user.is_super_admin and not user.has_account_access(account_id, ["admin"]):
        raise HTTPException(
            status_code=403, detail=f"Admin access required for account {account_id}"
        )

    try:
        # Get monitoring topics
        doc = firestore.get_document(
            collection=_monitoring_topics_subcollection(account_id),
            document_id="default",
        )

        if not doc:
            return SuccessResponse(message="No monitoring topics found")

        neo4j = await get_neo4j_service()
        removed_count = 0

        # Check competitor entries
        if "competitor_entries" in doc:
            competitors = doc["competitor_entries"]
            valid_competitors = []

            for entry in competitors:
                node_id = entry.get("node_id")
                if node_id:
                    # Check if node exists in Neo4j
                    exists_query = """
                    MATCH (c:Competitor {node_id: $node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
                    RETURN count(c) > 0 as exists
                    """
                    result = await neo4j.execute_query(
                        exists_query, {"node_id": node_id, "account_id": account_id}
                    )
                    if result and result[0]["exists"]:
                        valid_competitors.append(entry)
                    else:
                        removed_count += 1
                        logger.info(
                            f"Removing orphaned competitor entry: {node_id} from account {account_id}"
                        )
                else:
                    # Keep legacy entries without node_id
                    valid_competitors.append(entry)

            doc["competitor_entries"] = valid_competitors

        # Check customer profile entries
        if "customer_profile_entries" in doc:
            profiles = doc["customer_profile_entries"]
            valid_profiles = []

            for entry in profiles:
                node_id = entry.get("node_id")
                if node_id:
                    exists_query = """
                    MATCH (cp:CustomerProfile {node_id: $node_id})-[:BELONGS_TO]->(:Account {account_id: $account_id})
                    RETURN count(cp) > 0 as exists
                    """
                    result = await neo4j.execute_query(
                        exists_query, {"node_id": node_id, "account_id": account_id}
                    )
                    if result and result[0]["exists"]:
                        valid_profiles.append(entry)
                    else:
                        removed_count += 1
                        logger.info(
                            f"Removing orphaned customer profile entry: {node_id} from account {account_id}"
                        )
                else:
                    # Keep legacy entries without node_id
                    valid_profiles.append(entry)

            doc["customer_profile_entries"] = valid_profiles

        # Update document if changes were made
        if removed_count > 0:
            firestore.update_document(
                collection=_monitoring_topics_subcollection(account_id),
                document_id="default",
                data={
                    "competitor_entries": doc.get("competitor_entries", []),
                    "customer_profile_entries": doc.get("customer_profile_entries", []),
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

        return SuccessResponse(
            message=f"Cleanup complete. Removed {removed_count} orphaned entries.",
            data={"removed_count": removed_count},
        )

    except Exception as e:
        logger.error(f"Error cleaning up orphaned entries: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to cleanup orphaned entries"
        ) from e
