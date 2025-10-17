"""Internal account creation service with pure business logic."""

import logging
import uuid
from datetime import datetime

from fastapi import BackgroundTasks, HTTPException

from ..auth import UserContext
from ..bigquery import BigQueryService
from ..database import Neo4jService
from ..firestore import FirestoreService
from ..models.kene_models import Account, AccountRequest
from ..services.storage_service import StorageService

logger = logging.getLogger(__name__)

# Removed update_account_progress function - simplified progress tracking


def generate_unique_account_id() -> str:
    """Generate a unique account ID."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"account_{timestamp}_{unique_id}"


async def create_initial_activity_logs(
    account_id: str, industry: str, db: BigQueryService | None
) -> int:
    """Stub for creating initial activity logs."""
    if not db:
        return 0
    logger.info(
        f"[ACCOUNT_CREATION] Creating initial activity logs for {account_id} in {industry}"
    )
    return 0


async def create_account_internal(
    request: AccountRequest,
    uploaded_document_urls: list[str],
    background_tasks: BackgroundTasks,
    user: UserContext,
    firestore: FirestoreService,
    storage: StorageService,
    neo4j_service: Neo4jService,
    bigquery_service: BigQueryService | None = None,
) -> Account:
    """
    Internal account creation logic - testable without HTTP concerns.

    This function contains the core business logic for creating an account,
    separated from HTTP request/response handling.

    Args:
        request: Validated account request data
        uploaded_document_urls: List of uploaded document URLs from GCS
        background_tasks: FastAPI background tasks for async operations
        user: Current authenticated user context
        firestore: Firestore service instance
        storage: Storage service instance
        bigquery_service: Optional BigQuery service instance

    Returns:
        Account: The created account object

    Raises:
        HTTPException: If validation or creation fails
    """
    # Generate account ID if not provided
    account_id = request.account_id or generate_unique_account_id()

    logger.info(
        f"[ACCOUNT_CREATION] Starting internal account creation for: {account_id}"
    )

    # Log account creation start (progress tracking simplified)
    logger.info(f"[ACCOUNT_CREATION] Setting up database structures for {account_id}")

    # Check if organization exists in Neo4j and get organization details
    logger.info(
        f"[ACCOUNT_CREATION] Checking if organization exists: {request.organization_id}"
    )
    org_query = """
    MATCH (org:Organization {organization_id: $organization_id})
    RETURN org.agency as agency, org.organization_name as organization_name
    """
    org_result = await neo4j_service.execute_query(
        org_query, {"organization_id": request.organization_id}
    )

    if not org_result:
        logger.error(
            f"[ACCOUNT_CREATION] Organization not found: {request.organization_id}"
        )
        raise HTTPException(
            status_code=404, detail=f"Organization {request.organization_id} not found"
        )

    # Extract organization details
    organization_name = org_result[0].get(
        "organization_name", request.account_name
    )  # Fallback to account_name if not found
    is_agency = org_result[0].get("agency", False)

    logger.info(
        f"[ACCOUNT_CREATION] Organization found: {organization_name} (agency: {is_agency})"
    )

    # Check if organization is an agency
    if is_agency is True:
        logger.warning(
            f"[ACCOUNT_CREATION] Attempted to create account for agency organization: {request.organization_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Agency organizations cannot create accounts. Only regular organizations can have accounts.",
        )

    # Trigger strategy generation in background using organization_name as company_name
    # Import here to avoid circular dependency
    from ..tasks.strategy_tasks import trigger_strategy_generation

    if uploaded_document_urls:
        logger.info(
            f"[ACCOUNT_CREATION] {len(uploaded_document_urls)} documents uploaded for strategy generation"
        )

    logger.info(
        f"[ACCOUNT_CREATION] Triggering strategy generation for company: {request.account_name}"
    )

    background_tasks.add_task(
        trigger_strategy_generation,
        account_id=account_id,
        company_name=request.account_name,  # Use the actual company name from account form
        websites=request.websites,
        industry=request.industry,
        customer_regions=request.region or [],
        user_id=user.user_id,
        annual_ad_budget=request.estimated_annual_ad_budget,
        uploaded_document_urls=uploaded_document_urls,
        user_context=None,  # No user context for background task
    )

    # Log account structure created (progress tracking simplified)
    logger.info(
        f"[ACCOUNT_CREATION] Account structure created for {account_id}, preparing research"
    )

    # Prepare account data for Firestore
    account_data = {
        "account_id": account_id,
        "account_name": request.account_name,
        "organization_id": request.organization_id,
        "industry": request.industry,
        "status": request.status,
        "websites": request.websites,
        "timezone": request.timezone,
        "data_region": request.data_region,
        "region": request.region,
        "marketing_channels": request.marketing_channels or [],
        "product_integrations": request.product_integrations or [],
        "estimated_annual_ad_budget": request.estimated_annual_ad_budget,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user.user_id,  # Fixed: use user_id instead of uid
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by": user.user_id,  # Fixed: use user_id instead of uid
    }

    # Create account in Neo4j database
    logger.info(f"[ACCOUNT_CREATION] Creating account in Neo4j: {account_id}")
    create_query = """
    MATCH (org:Organization {organization_id: $organization_id})
    CREATE (acc:Account {
        account_id: $account_id,
        account_name: $account_name,
        company_name: $company_name,
        organization_id: $organization_id,
        industry: $industry,
        status: $status,
        websites: $websites,
        timezone: $timezone,
        data_region: $data_region,
        region: $region,
        estimated_annual_ad_budget: $estimated_annual_ad_budget,
        marketing_channels: $marketing_channels,
        product_integrations: $product_integrations
    })
    CREATE (acc)-[:BELONGS_TO]->(org)
    RETURN acc
    """

    params = {
        "account_id": account_id,
        "account_name": request.account_name,
        "company_name": request.account_name,  # Initially same as account_name, agents can refine
        "organization_id": request.organization_id,
        "industry": request.industry,
        "status": request.status,
        "websites": request.websites,
        "timezone": request.timezone,
        "data_region": request.data_region or "",
        "region": request.region or [],
        "estimated_annual_ad_budget": request.estimated_annual_ad_budget,
        "marketing_channels": request.marketing_channels or [],
        "product_integrations": request.product_integrations or [],
    }

    try:
        result = await neo4j_service.execute_write_query(create_query, params)
        logger.info(
            f"[ACCOUNT_CREATION] Account created successfully in Neo4j: {account_id}"
        )

        # Verify account data was saved correctly
        verify_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc.websites as websites, acc.industry as industry, acc.estimated_annual_ad_budget as budget
        """
        verify_result = await neo4j_service.execute_query(
            verify_query, {"account_id": account_id}
        )
        if verify_result and len(verify_result) > 0:
            saved_data = verify_result[0]
            logger.info(
                f"[ACCOUNT_CREATION] Verification - Websites: {saved_data.get('websites', [])}"
            )
            logger.info(
                f"[ACCOUNT_CREATION] Verification - Industry: {saved_data.get('industry')}"
            )
            logger.info(
                f"[ACCOUNT_CREATION] Verification - Budget: {saved_data.get('budget')}"
            )

            # Warn if user provided websites but they weren't saved
            if request.websites and not saved_data.get("websites"):
                logger.warning(
                    "[ACCOUNT_CREATION] ⚠️ User provided websites but none were saved to Neo4j!"
                )
            elif request.websites and saved_data.get("websites"):
                logger.info(
                    f"[ACCOUNT_CREATION] ✅ {len(saved_data.get('websites'))} website(s) saved correctly"
                )
        else:
            logger.warning("[ACCOUNT_CREATION] Could not verify account data")

    except Exception as e:
        logger.error(f"[ACCOUNT_CREATION] Failed to create account in Neo4j: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create account: {e!s}")

    # Log database setup continuing (progress tracking simplified)
    logger.info(f"[ACCOUNT_CREATION] Setting up database structures for {account_id}")

    # Create initial activities from Firestore templates
    try:
        from ..routers.accounts import _create_initial_activities

        activities_count = await _create_initial_activities(
            db=neo4j_service, firestore=firestore, account_id=account_id
        )
        logger.info(
            f"[ACCOUNT_CREATION] Created {activities_count} initial activities"
        )
    except Exception as e:
        logger.error(f"[ACCOUNT_CREATION] Failed to create initial activities: {e}")
        # Don't fail account creation if initial activities fail

    # Create initial activity logs if BigQuery service is available
    if bigquery_service:
        try:
            created_count = await create_initial_activity_logs(
                account_id=account_id, industry=request.industry, db=bigquery_service
            )
            logger.info(
                f"[ACCOUNT_CREATION] Created {created_count} initial activity logs"
            )
        except Exception as e:
            logger.error(f"[ACCOUNT_CREATION] Failed to create activity logs: {e}")
            # Don't fail account creation if activity logs fail

    # Log database setup continuing (progress tracking simplified)
    logger.info(f"[ACCOUNT_CREATION] Configuring data streams for {account_id}")

    # Ensure GCS bucket and folder exist for the account
    try:
        data_region = request.data_region or "US"
        bucket_name, location = await storage.ensure_bucket_exists(data_region)
        logger.info(
            f"Ensured GCS bucket {bucket_name} exists in {location} for account {account_id}"
        )

        # Create account folder
        folder_created = await storage.ensure_account_folder(account_id, data_region)
        if folder_created:
            logger.info(
                f"Created GCS folder for account {account_id} in region {data_region}"
            )
    except Exception as e:
        logger.error(f"Failed to ensure GCS storage for account {account_id}: {e}")
        # Don't fail account creation if storage setup fails

    # Create Firestore collection for strategy documents
    try:
        collection_name = f"strategy_docs_{account_id}"
        initial_doc_data = {
            "account_id": account_id,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": user.user_id,
            "type": "placeholder",
            "description": "Initial placeholder document - collection ready for business strategy documents",
            "organization_id": request.organization_id,
        }
        doc_id = firestore.create_document(
            collection_name, "_placeholder", initial_doc_data
        )
        logger.info(
            f"Created Firestore collection '{collection_name}' with placeholder document: {doc_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to create Firestore collection for account {account_id}: {e}"
        )
        # Don't fail account creation if collection creation fails

    # Grant the creating user admin permissions on the new account
    try:
        success = firestore.set_nested_field(
            collection="users",
            document_id=user.user_id,
            field_path=f"permissions.accounts.{account_id}",
            value="admin",
        )
        if success:
            logger.info(
                f"Granted admin permissions to user {user.user_id} for account {account_id}"
            )
        else:
            logger.warning(
                f"Failed to grant permissions to user {user.user_id} for account {account_id}"
            )
    except Exception as e:
        logger.error(
            f"Error granting permissions to user {user.user_id} for account {account_id}: {e}"
        )
        # Don't fail account creation if permission grant fails

    # Invalidate the user's cache to ensure their context includes the new account
    try:
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user.user_id)
        logger.info(
            f"Invalidated cache for user {user.user_id} after creating account {account_id}"
        )
    except Exception as e:
        logger.error(f"Failed to invalidate user cache: {e}")
        # Don't fail account creation if cache invalidation fails

    # Log database setup complete (progress tracking simplified)
    # Don't mark as fully complete yet - the strategy generation task will do that
    logger.info(
        f"[ACCOUNT_CREATION] Database setup complete for {account_id}, starting business research"
    )

    logger.info(
        f"[ACCOUNT_CREATION] Successfully created account: {account_id}, strategy generation in progress"
    )

    # Return the created account
    # Note: Strategy generation continues in the background and will update progress when complete
    return Account(**account_data)
