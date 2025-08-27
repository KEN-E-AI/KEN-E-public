"""Accounts router for CRUD operations on account entities."""

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..auth import UserContext, get_current_user_context
from ..bigquery import BigQueryService, get_bigquery_service
from ..database import Neo4jService, get_neo4j_service
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import (
    Account,
    AccountListResponse,
    AccountRequest,
    NotificationCategory,
    NotificationStatus,
    SuccessResponse,
)
from ..repositories import FirestoreNotificationRepository
from ..services.notification_service_v2 import NotificationService
from ..services.storage_service import StorageService, get_storage_service

router = APIRouter(tags=["accounts"])

# Logger
logger = logging.getLogger(__name__)


def generate_unique_account_id() -> str:
    """
    Generate a unique account ID using UUID4.

    Returns:
        str: A unique account ID in the format 'acc_<uuid>'

    Example:
        'acc_550e8400e29b41d4a716446655440000'
    """
    # Generate UUID4 and remove hyphens for cleaner format
    unique_id = str(uuid.uuid4()).replace("-", "")
    return f"acc_{unique_id}"


def generate_timestamp_account_id() -> str:
    """
    Generate a unique account ID using timestamp and UUID.

    Returns:
        str: A unique account ID in the format 'acc_<timestamp>_<uuid_suffix>'

    Example:
        'acc_1705123456789_a1b2c3d4'
    """
    timestamp = int(datetime.now().timestamp() * 1000)
    uuid_suffix = str(uuid.uuid4()).replace("-", "")[:8]
    return f"acc_{timestamp}_{uuid_suffix}"


# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."
ACCOUNT_NOT_FOUND_MESSAGE = "Account not found"
ORGANIZATION_NOT_FOUND_MESSAGE = "Organization not found"


@router.get("/", response_model=AccountListResponse)
async def get_accounts(
    organization_id: str | None = Query(
        None, description="Filter accounts by organization ID"
    ),
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> AccountListResponse:
    """
    Get accounts accessible to the current user, optionally filtered by organization.

    **Parameters (query):**
    - `organization_id` (optional): Filter accounts by organization ID

    **Returns:**
    - `accounts`: List of account objects with all properties
    - `total`: Total number of accounts found

    **Example:**
    ```
    GET /api/v1/accounts/
    GET /api/v1/accounts/?organization_id=healthway
    ```

    **Note:** User must have access to the accounts and organization (if specified).
    """
    import time
    start_time = time.time()
    
    try:
        # Check Neo4j connectivity
        health_check_start = time.time()
        is_healthy = await db.health_check()
        health_check_time = time.time() - health_check_start
        logger.info(f"[TIMING] Neo4j health check for get_accounts took {health_check_time:.3f}s")
        
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Build query based on user permissions
        if user.is_super_admin:
            # Super admins can see all accounts
            if organization_id:
                accounts_query = """
                MATCH (org:Organization {organization_id: $organization_id})<-[:BELONGS_TO]-(acc:Account)
                RETURN acc
                ORDER BY acc.account_name
                """
                params = {"organization_id": organization_id}
            else:
                accounts_query = """
                MATCH (acc:Account)
                RETURN acc
                ORDER BY acc.account_name
                """
                params = {}
        else:
            # Regular users need to check permissions
            if organization_id:
                # Verify user has access to the organization
                if not user.has_organization_access(organization_id):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access denied to organization {organization_id}",
                    )

                # Check if user is org admin
                if user.organization_permissions.get(organization_id) == "admin":
                    # Org admins can see all accounts in their organization
                    accounts_query = """
                    MATCH (org:Organization {organization_id: $organization_id})<-[:BELONGS_TO]-(acc:Account)
                    RETURN acc
                    ORDER BY acc.account_name
                    """
                    params = {"organization_id": organization_id}
                else:
                    # View-role users see only accounts they have explicit access to
                    accessible_account_ids = list(user.account_permissions.keys())
                    if not accessible_account_ids:
                        return AccountListResponse(accounts=[], total=0)

                    accounts_query = """
                    MATCH (org:Organization {organization_id: $organization_id})<-[:BELONGS_TO]-(acc:Account)
                    WHERE acc.account_id IN $account_ids
                    RETURN acc
                    ORDER BY acc.account_name
                    """
                    params = {
                        "organization_id": organization_id,
                        "account_ids": accessible_account_ids,
                    }
            else:
                # No organization filter - need to find all accessible accounts
                accessible_account_ids = []

                # Add accounts from organizations where user is admin
                for org_id, role in user.organization_permissions.items():
                    if role == "admin":
                        # Get all accounts for this org
                        org_accounts_query = """
                        MATCH (org:Organization {organization_id: $org_id})<-[:BELONGS_TO]-(acc:Account)
                        RETURN acc.account_id as account_id
                        """
                        org_result = await db.execute_query(
                            org_accounts_query, {"org_id": org_id}
                        )
                        accessible_account_ids.extend(
                            [r["account_id"] for r in org_result]
                        )

                # Add explicitly granted accounts for view-role users
                accessible_account_ids.extend(list(user.account_permissions.keys()))

                # Remove duplicates
                accessible_account_ids = list(set(accessible_account_ids))

                if not accessible_account_ids:
                    return AccountListResponse(accounts=[], total=0)

                accounts_query = """
                MATCH (acc:Account)
                WHERE acc.account_id IN $account_ids
                RETURN acc
                ORDER BY acc.account_name
                """
                params = {"account_ids": accessible_account_ids}

        query_start = time.time()
        result = await db.execute_query(accounts_query, params)
        query_time = time.time() - query_start
        logger.info(f"[TIMING] Neo4j query execution took {query_time:.3f}s")

        # Debug logging
        logger.info(f"[DEBUG] Neo4j query executed: {accounts_query}")
        logger.info(f"[DEBUG] Query params: {params}")
        logger.info(f"[DEBUG] Number of records returned: {len(result)}")

        accounts = []
        for i, record in enumerate(result):
            logger.info(f"[DEBUG] Record {i} keys: {list(record.keys())}")
            acc_data = record.get("acc")
            if acc_data:
                logger.info(f"[DEBUG] Processing account: {acc_data.get('account_id')}")
                account = _create_account_from_record(acc_data)
                accounts.append(account)

        total_time = time.time() - start_time
        logger.info(f"[TIMING] Total get_accounts execution took {total_time:.3f}s for {len(accounts)} accounts")
        return AccountListResponse(accounts=accounts, total=len(accounts))

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error fetching accounts: {e!s}"
        ) from e


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Account:
    """
    Get a specific account by ID.

    **Parameters:**
    - `account_id` (path): The unique identifier for the account

    **Returns:**
    - Account object with all properties

    **Example:**
    ```
    GET /api/v1/accounts/intellipure-b2c
    ```

    **Note:** User must have access to the account.
    """
    try:
        # Check if user has access to this account
        # First, we need to find which organization this account belongs to
        org_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id
        """
        org_result = await db.execute_query(org_query, {"account_id": account_id})

        if not org_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = org_result[0]["organization_id"]

        # Now check access with the organization context
        if not user.is_super_admin:
            # Check if user has organization access
            if not user.has_organization_access(organization_id):
                raise HTTPException(
                    status_code=403, detail=f"Access denied to account {account_id}"
                )

            # If user is view-role, check account-specific permissions
            if user.organization_permissions.get(organization_id) == "view":
                if account_id not in user.account_permissions:
                    raise HTTPException(
                        status_code=403, detail=f"Access denied to account {account_id}"
                    )

        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch specific account
        account_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc
        """

        result = await db.execute_query(account_query, {"account_id": account_id})

        if not result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        acc_data = result[0].get("acc")
        account = _create_account_from_record(acc_data)

        return account

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error fetching account: {e!s}"
        ) from e


async def _create_initial_activities(
    db: Neo4jService, firestore: FirestoreService, account_id: str
) -> int:
    """
    Create initial activities for a new account from Firestore template.

    Args:
        db: Neo4j database service
        firestore: Firestore service
        account_id: ID of the newly created account

    Returns:
        int: Number of activities created
    """
    try:
        # Fetch all documents from initial-activities collection
        initial_activities = firestore.list_documents("initial-activities")

        if not initial_activities:
            logger.info(
                f"No initial activities found in Firestore for account {account_id}"
            )
            return 0

        # Prepare activities for batch creation
        activities_data = []
        for activity_doc in initial_activities:
            # Use the activity_id from Firestore document
            activity_data = {
                "activity_id": activity_doc.get("activity_id"),
                "activity_name": activity_doc.get("activity_name", ""),
                "activity_description": activity_doc.get("activity_description", ""),
                "expected_impact": activity_doc.get("expected_impact", ""),
                "internal": activity_doc.get("internal", False),
                "known_activity": activity_doc.get("known_activity", False),
            }

            # Only add if activity_id exists
            if activity_data["activity_id"]:
                activities_data.append(activity_data)
            else:
                logger.warning(
                    "Skipping activity without activity_id in initial-activities collection"
                )

        if not activities_data:
            logger.warning(f"No valid activities to create for account {account_id}")
            return 0

        # Create activities in batch using UNWIND
        create_query = """
        UNWIND $activities AS activity
        MATCH (account:Account {account_id: $account_id})
        CREATE (a:Activity {
            activity_id: activity.activity_id,
            activity_name: activity.activity_name,
            activity_description: activity.activity_description,
            expected_impact: activity.expected_impact,
            internal: activity.internal,
            known_activity: activity.known_activity
        })
        CREATE (a)-[:BELONGS_TO]->(account)
        RETURN count(a) as created_count
        """

        params = {"account_id": account_id, "activities": activities_data}

        result = await db.execute_write_query(create_query, params)
        created_count = result[0]["created_count"] if result else 0

        logger.info(
            f"Created {created_count} initial activities for account {account_id}"
        )
        return created_count

    except Exception as e:
        logger.error(
            f"Error creating initial activities for account {account_id}: {type(e).__name__}: {e!s}"
        )
        logger.error(f"Exception details for account {account_id}: {e!r}")
        # Don't raise - let account creation succeed even if initial activities fail
        return 0


async def _create_initial_activity_logs(
    db: Neo4jService,
    bigquery: BigQueryService,
    account_id: str,
    organization_id: str,
    regions: list[str],
) -> int:
    """
    Create initial activity logs for regional holiday activities from BigQuery holiday data.

    Args:
        db: Neo4j database service
        bigquery: BigQuery service
        account_id: ID of the newly created account
        organization_id: ID of the organization (used to get GCP project)
        regions: List of regions for the account

    Returns:
        int: Number of activity logs created
    """
    try:
        # Get GCP project ID from environment
        import os

        from ..models.kene_models import REGION_TO_HOLIDAY_ACTIVITY_ID

        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            logger.warning(
                "GOOGLE_CLOUD_PROJECT_ID not set, skipping holiday activity logs"
            )
            return 0

        # Check if regional holiday activities exist for this account
        check_query = """
        MATCH (a:Activity)-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
        WHERE a.activity_id STARTS WITH 'act_00_'
        RETURN count(a) as activity_count
        """
        result = await db.execute_query(check_query, {"account_id": account_id})
        if not result or result[0]["activity_count"] == 0:
            logger.warning(
                f"No regional holiday activities found for account {account_id}"
            )
            return 0

        # Query holiday activities from BigQuery
        logger.info(
            f"Querying BigQuery for holidays in project {project_id} for regions {regions}"
        )
        holidays = bigquery.query_holiday_activities(project_id, regions)
        if not holidays:
            logger.info(f"No holiday activities found for regions {regions}")
            return 0
        logger.info(f"Found {len(holidays)} holiday activities from BigQuery")

        # Create activity logs in batch
        activity_logs_data = []
        for holiday in holidays:
            region = holiday.get("region")
            # Map region to appropriate activity_id
            activity_id = REGION_TO_HOLIDAY_ACTIVITY_ID.get(
                region, f"act_00_{region.lower()}" if region else "act_00"
            )

            log_id = str(uuid.uuid4())
            activity_logs_data.append(
                {
                    "activity_log_id": f"log_{log_id}",
                    "activity_id": activity_id,
                    "account_id": account_id,
                    "start_date": holiday["start_date"],
                    "end_date": holiday["end_date"],
                    "description": holiday["description"],
                    # Omit evidence field - Neo4j doesn't accept empty dicts
                }
            )

        # Create activity logs with LOGGED relationships
        create_query = """
        UNWIND $logs AS log
        MATCH (activity:Activity {activity_id: log.activity_id})-[:BELONGS_TO]->(account:Account {account_id: log.account_id})
        CREATE (al:ActivityLog {
            activity_log_id: log.activity_log_id,
            account_id: log.account_id,
            start_date: log.start_date,
            end_date: log.end_date,
            description: log.description
        })
        CREATE (al)-[:LOGGED]->(activity)
        CREATE (al)-[:BELONGS_TO]->(account)
        RETURN count(al) as created_count
        """

        params = {"logs": activity_logs_data}
        result = await db.execute_write_query(create_query, params)
        created_count = result[0]["created_count"] if result else 0

        logger.info(
            f"Created {created_count} holiday activity logs for account {account_id}"
        )
        return created_count

    except Exception as e:
        logger.error(
            f"Error creating initial activity logs for account {account_id}: {e!s}"
        )
        # Don't raise - let account creation succeed even if activity logs fail
        return 0


@router.post("/", response_model=Account)
async def create_account(
    request: AccountRequest,
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(get_current_user_context),
    firestore: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> Account:
    """
    Create a new account.

    **Request Body:**
    - `account_name` (required): Name of the account
    - `organization_id` (required): ID of the organization this account belongs to
    - `industry` (required): Industry category
    - `status` (required): Account status (e.g., Active, Inactive)
    - `websites` (required): List of websites associated with the account
    - `timezone` (required): Timezone for the account

    **Returns:**
    - Created account object with generated account_id

    **Errors:**
    - `403 Forbidden`: If the organization is an agency (agency=true). Agency organizations cannot create accounts.
    - `404 Not Found`: If the organization does not exist
    - `400 Bad Request`: If required fields are missing

    **Example:**
    ```
    POST /api/v1/accounts/
    {
        "account_name": "New Account",
        "organization_id": "healthway",
        "industry": "Technology",
        "status": "Active",
        "websites": ["https://example.com"],
        "timezone": "America/New_York"
    }
    ```

    **Note:** Only regular organizations (agency=false) can create accounts. Agency organizations are restricted from creating accounts.
    """
    # Generate unique account_id FIRST - this will always succeed
    account_id = generate_unique_account_id()
    print(f"[ACCOUNT_CREATION] Starting for: {account_id}")
    logger.info(f"[ACCOUNT_CREATION] Starting account creation for account_id: {account_id}")
    
    # CRITICAL: Trigger strategy generation IMMEDIATELY
    # This ensures it runs regardless of any failures below
    # User explicitly requested: "feel free to create strategy generation regardless of whatever else fails"
    strategy_generation_triggered = False
    try:
        print(f"[STRATEGY] About to trigger generation for {account_id}")
        logger.info(f"[STRATEGY] Triggering strategy generation for account {account_id} BEFORE any database operations")
        
        from ..tasks.strategy_tasks import trigger_strategy_generation
        
        # Use FastAPI's background tasks to run strategy generation truly asynchronously
        # This will run after the response is sent, ensuring no blocking
        background_tasks.add_task(
            trigger_strategy_generation,
            account_id=account_id,
            company_name=request.account_name,
            websites=request.websites,
            industry=request.industry,
            customer_regions=request.region or [],
            user_id=user.user_id,
            annual_ad_budget=request.estimated_annual_ad_budget,
            user_context=None  # No user context for background task
        )
        
        strategy_generation_triggered = True
        logger.info(f"[STRATEGY] Successfully triggered strategy generation for account {account_id} as background task")
    except Exception as e:
        logger.error(f"[STRATEGY] Failed to trigger strategy generation for account {account_id}: {e}", exc_info=True)
    
    # Now proceed with the rest of account creation
    # Even if this fails, strategy generation has already been triggered
    try:
        # Get Neo4j service (we removed it from dependencies to ensure strategy runs first)
        from ..database import get_neo4j_service
        db = await get_neo4j_service()
        
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            # Neo4j is down, but strategy generation was already triggered
            logger.warning(f"Neo4j unavailable, but strategy generation already triggered for {account_id}")
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Validate required fields
        if not request.account_name:
            raise HTTPException(status_code=400, detail="account_name is required")
        if not request.organization_id:
            raise HTTPException(status_code=400, detail="organization_id is required")
        if not request.industry:
            raise HTTPException(status_code=400, detail="industry is required")
        if not request.status:
            raise HTTPException(status_code=400, detail="status is required")
        if request.websites is None:
            raise HTTPException(status_code=400, detail="websites is required")
        if not request.timezone:
            raise HTTPException(status_code=400, detail="timezone is required")

        # Check if organization exists
        logger.info(f"[ACCOUNT_CREATION] Checking if organization {request.organization_id} exists...")
        org_exists = await _check_organization_exists(db, request.organization_id)
        if not org_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Organization {request.organization_id} not found",
            )
        logger.info(f"[ACCOUNT_CREATION] Organization {request.organization_id} exists")

        # Check if organization is an agency (agency organizations cannot create accounts)
        logger.info(f"[ACCOUNT_CREATION] Checking agency status for {request.organization_id}...")
        is_agency = await _get_organization_agency_status(db, request.organization_id)
        if is_agency is True:
            raise HTTPException(
                status_code=403,
                detail="Account creation is not permitted for agency organizations",
            )
        logger.info(f"[ACCOUNT_CREATION] Organization is not an agency (agency={is_agency})")

        # Account ID was already generated at the beginning
        # Check if account already exists (extremely unlikely with UUID4)
        logger.info(f"[ACCOUNT_CREATION] Checking if account {account_id} already exists...")
        existing_acc = await _check_account_exists(db, account_id)
        if existing_acc:
            logger.warning(f"UUID collision detected for account_id: {account_id}")
            # Generate a new UUID if collision occurs (extremely rare)
            old_account_id = account_id
            account_id = generate_unique_account_id()
            existing_acc = await _check_account_exists(db, account_id)
            if existing_acc:
                raise HTTPException(
                    status_code=500,
                    detail="Unable to generate unique account ID. Please try again.",
                )
            # Update the strategy generation with new account_id if we had to regenerate
            if strategy_generation_triggered:
                logger.info(f"[STRATEGY] Updating strategy generation from {old_account_id} to {account_id}")

        # Create account node and BELONGS_TO relationship
        create_query = """
        MATCH (org:Organization {organization_id: $organization_id})
        CREATE (acc:Account {
            account_id: $account_id,
            account_name: $account_name,
            organization_id: $organization_id,
            industry: $industry,
            status: $status,
            websites: $websites,
            timezone: $timezone,
            data_region: $data_region,
            region: $region,
            estimated_annual_ad_budget: $estimated_annual_ad_budget,
            setup_status: $setup_status,
            setup_started_at: $setup_started_at,
            setup_completed_at: $setup_completed_at,
            marketing_channels: $marketing_channels,
            product_integrations: $product_integrations
        })
        CREATE (acc)-[:BELONGS_TO]->(org)
        RETURN acc
        """

        params = {
            "account_id": account_id,
            "account_name": request.account_name,
            "organization_id": request.organization_id,
            "industry": request.industry,
            "status": request.status,
            "websites": request.websites,
            "timezone": request.timezone,
            "data_region": request.data_region or "",
            "region": request.region or [],
            "estimated_annual_ad_budget": request.estimated_annual_ad_budget,
            "setup_status": "pending",  # Initial status
            "setup_started_at": None,
            "setup_completed_at": None,
            "marketing_channels": request.marketing_channels or [],
            "product_integrations": request.product_integrations or [],
        }

        logger.info(f"[ACCOUNT_CREATION] About to execute write query for account {account_id}")
        logger.info(f"[ACCOUNT_CREATION] Query params: organization_id={request.organization_id}")
        
        try:
            result = await db.execute_write_query(create_query, params)
            logger.info(f"[ACCOUNT_CREATION] Write query successful! Result: {result}")
        except Exception as e:
            logger.error(f"[ACCOUNT_CREATION] Write query failed: {e}")
            logger.error(f"[ACCOUNT_CREATION] Error type: {type(e).__name__}")
            raise

        # Account creation successful - log completion
        logger.info(f"=== ACCOUNT CREATION COMPLETE for {account_id} ===")

        # Invalidate the creating user's cache to ensure their context includes the new account
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user.user_id)
        logger.info(
            f"Invalidated cache for user {user.user_id} after creating account {account_id}"
        )

        # Ensure GCS bucket exists for business strategy documents
        try:
            storage_service = get_storage_service()
            bucket_name, location = await storage_service.ensure_bucket_exists(
                request.data_region or "US"
            )
            logger.info(
                f"Ensured GCS bucket {bucket_name} exists in {location} "
                f"for account {account_id} with data region {request.data_region or 'US'}"
            )
        except Exception as e:
            # Log error but don't fail account creation if bucket creation fails
            logger.error(
                f"Failed to ensure GCS bucket for account {account_id} "
                f"with data region {request.data_region or 'US'}: {e}"
            )

        # Create Firestore collection strategy_docs_{account_id} with initial placeholder document
        try:
            collection_name = f"strategy_docs_{account_id}"
            initial_doc_data = {
                "account_id": account_id,
                "created_at": datetime.now().isoformat(),
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
            # Log error but don't fail account creation if collection creation fails
            logger.error(
                f"Failed to create Firestore collection for account {account_id}: {e}"
            )

        # Create initial activities for the new account
        activities_created = await _create_initial_activities(db, firestore, account_id)
        if activities_created > 0:
            logger.info(
                f"Successfully created {activities_created} initial activities for account {account_id}"
            )

        # Create initial activity logs for act_00 if regions are specified
        if request.region:
            logger.info(
                f"Account {account_id} has regions: {request.region}, attempting to create holiday activity logs"
            )
            bigquery = get_bigquery_service()
            logs_created = await _create_initial_activity_logs(
                db, bigquery, account_id, request.organization_id, request.region
            )
            if logs_created > 0:
                logger.info(
                    f"Successfully created {logs_created} holiday activity logs for account {account_id}"
                )
            else:
                logger.info(
                    f"No regional holidays found - no activity logs created for account {account_id}"
                )

        # Create Google Cloud Storage folder for the account
        try:
            data_region = request.data_region or "US"
            folder_created = await storage.ensure_account_folder(
                account_id, data_region
            )
            if folder_created:
                logger.info(
                    f"Created GCS folder for account {account_id} in region {data_region}"
                )
            else:
                logger.warning(
                    f"Failed to create GCS folder for account {account_id} in region {data_region}"
                )
        except Exception as e:
            # Don't fail account creation if storage folder creation fails
            logger.error(
                f"Failed to create GCS folder for new account {account_id}: {e}"
            )

        # Create notification for the new account
        logger.info(f"Starting notification creation for account {account_id}")
        try:
            # Create repository and service instances
            notification_repository = FirestoreNotificationRepository(
                firestore.get_client()
            )
            notification_service = NotificationService(notification_repository)
            notification_id = await notification_service.create_notification(
                account_id=account_id,
                category=NotificationCategory.NEW_FEATURES,
                description="Configure your new account",
                data={
                    "account_name": request.account_name,
                    "created_by": user.user_id,
                    "created_at": datetime.now().isoformat(),
                },
            )
            logger.info(
                f"Created new account notification {notification_id} for account {account_id}"
            )

            # Try to initialize notification for user if method exists
            if hasattr(notification_service, 'initialize_notification_for_user'):
                await notification_service.initialize_notification_for_user(
                    notification_id=notification_id,
                    user_id=user.user_id,
                    category=NotificationCategory.NEW_FEATURES,
                )
            else:
                # Ensure the creating user can see the notification immediately
                # Create notification status directly for the creating user
                await notification_repository.batch_create_user_statuses(
                    [
                        {
                            "user_id": user.user_id,
                            "notification_id": notification_id,
                            "status": NotificationStatus.UNREAD.value,
                            "updated_at": datetime.now().isoformat(),
                        }
                    ]
                )
        except Exception as e:
            # Don't fail account creation if notification fails
            logger.error(
                f"Failed to create notification for new account {account_id}: {e}"
            )
        
        logger.info(f"Completed notification section for account {account_id}")

        # Strategy generation was already triggered at the beginning
        # Log the status for clarity
        if strategy_generation_triggered:
            logger.info(f"[STRATEGY] Strategy generation was already triggered for account {account_id}")
        else:
            logger.warning(f"[STRATEGY] Strategy generation was not triggered for account {account_id}")

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

                # Invalidate the user's cache again to ensure permissions are updated
                cached_user_service.invalidate_user_context(user.user_id)
                logger.info(
                    f"Invalidated cache again for user {user.user_id} after granting account permissions"
                )
            else:
                logger.warning(
                    f"Failed to grant permissions to user {user.user_id} for account {account_id}, "
                    "but account was created successfully"
                )
        except Exception as e:
            # Don't fail account creation if permission grant fails
            logger.error(
                f"Error granting permissions to user {user.user_id} for account {account_id}: {e}, "
                "but account was created successfully"
            )

        # Fetch the created account
        return await get_account(account_id, user, db)

    except HTTPException:
        # Even if account creation failed, strategy generation was already triggered
        if strategy_generation_triggered:
            logger.info(f"[STRATEGY] Account creation failed but strategy generation was triggered for {account_id}")
        raise
    except Exception as e:
        # Even if account creation failed, strategy generation was already triggered
        if strategy_generation_triggered:
            logger.info(f"[STRATEGY] Account creation failed but strategy generation was triggered for {account_id}")
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error creating account: {e!s}"
        ) from e


@router.put("/{account_id}", response_model=Account)
async def update_account(
    account_id: str,
    request: AccountRequest,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    bigquery: BigQueryService = Depends(get_bigquery_service),
) -> Account:
    """
    Update an existing account.

    **Parameters:**
    - `account_id` (path): The unique identifier for the account

    **Request Body:**
    - All fields are optional, only provided fields will be updated
    - Note: organization_id cannot be updated

    **Returns:**
    - Updated account object

    **Example:**
    ```
    PUT /api/v1/accounts/intellipure-b2c
    {
        "status": "Inactive",
        "websites": ["https://new-example.com"]
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Check if account exists
        existing_acc = await _check_account_exists(db, account_id)
        if not existing_acc:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        # Get the current account to check if regions are being updated
        current_account = await get_account(account_id, user, db)
        current_regions = set(current_account.region or [])
        new_regions = set(request.region) if request.region is not None else None
        regions_changed = new_regions is not None and current_regions != new_regions

        # Build update query dynamically based on provided fields
        update_clauses = []
        params = {"account_id": account_id}

        if request.account_name is not None:
            update_clauses.append("acc.account_name = $account_name")
            params["account_name"] = request.account_name

        # organization_id cannot be updated
        if request.organization_id is not None:
            logger.warning(
                f"Attempt to update organization_id for account {account_id} ignored"
            )

        if request.industry is not None:
            update_clauses.append("acc.industry = $industry")
            params["industry"] = request.industry

        if request.status is not None:
            update_clauses.append("acc.status = $status")
            params["status"] = request.status

        if request.websites is not None:
            update_clauses.append("acc.websites = $websites")
            params["websites"] = request.websites

        if request.timezone is not None:
            update_clauses.append("acc.timezone = $timezone")
            params["timezone"] = request.timezone

        if request.data_region is not None:
            update_clauses.append("acc.data_region = $data_region")
            params["data_region"] = request.data_region

        if request.region is not None:
            update_clauses.append("acc.region = $region")
            params["region"] = request.region

        if request.estimated_annual_ad_budget is not None:
            update_clauses.append(
                "acc.estimated_annual_ad_budget = $estimated_annual_ad_budget"
            )
            params["estimated_annual_ad_budget"] = request.estimated_annual_ad_budget

        if request.marketing_channels is not None:
            update_clauses.append("acc.marketing_channels = $marketing_channels")
            params["marketing_channels"] = request.marketing_channels

        if request.product_integrations is not None:
            update_clauses.append("acc.product_integrations = $product_integrations")
            params["product_integrations"] = request.product_integrations

        if not update_clauses:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Execute update query
        update_query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        SET {", ".join(update_clauses)}
        RETURN acc
        """

        await db.execute_write_query(update_query, params)

        # Invalidate the updating user's cache to ensure fresh context
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user.user_id)
        logger.info(
            f"Invalidated cache for user {user.user_id} after updating account {account_id}"
        )

        # If regions were updated, sync holiday activity logs
        if regions_changed:
            organization_id = current_account.organization_id
            await _sync_holiday_activity_logs_for_account(
                db, bigquery, account_id, organization_id, list(new_regions)
            )

        # Return updated account
        return await get_account(account_id, user, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error updating account: {e!s}"
        ) from e


@router.delete("/{account_id}", response_model=SuccessResponse)
async def delete_account(
    account_id: str,
    db: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
    storage: StorageService = Depends(get_storage_service),
) -> SuccessResponse:
    """
    Delete an account and all related entities.

    This endpoint performs a cascade delete of:
    - The account node itself
    - All entities with BELONGS_TO relationship to the account
    - All ActivityLog nodes with LOGGED relationship to deleted Activity nodes
    - All business strategy documents from Google Cloud Storage
    - The Firestore collection strategy_docs_{account_id}

    **Parameters:**
    - `account_id` (path): The unique identifier for the account

    **Returns:**
    - Success response with deletion details including counts of deleted entities

    **Example:**
    ```
    DELETE /api/v1/accounts/intellipure-b2c
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Check if account exists and get account data for cleanup
        account_query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc.data_region as data_region
        """
        account_result = await db.execute_query(
            account_query, {"account_id": account_id}
        )

        if not account_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        data_region = account_result[0]["data_region"] or "US"

        # Clean up external resources before deleting from Neo4j
        cleanup_results = {
            "gcs_documents_deleted": 0,
            "firestore_collection_deleted": False,
            "cleanup_errors": [],
        }

        # Delete GCS documents for this account
        try:
            deleted_documents = await storage.delete_account_documents(
                account_id, data_region
            )
            cleanup_results["gcs_documents_deleted"] = 1 if deleted_documents else 0
            logger.info(
                f"Deleted GCS documents for account {account_id} in region {data_region}"
            )
        except Exception as e:
            logger.error(
                f"Failed to delete GCS documents for account {account_id}: {e}"
            )
            cleanup_results["cleanup_errors"].append(f"GCS cleanup failed: {e}")

        # Delete Firestore collection strategy_docs_{account_id}
        try:
            collection_name = f"strategy_docs_{account_id}"
            # Delete all documents in the collection
            firestore_db = firestore.get_client()
            collection_ref = firestore_db.collection(collection_name)

            # Get all documents in the collection
            docs = collection_ref.list_documents()
            deleted_docs_count = 0

            for doc in docs:
                doc.delete()
                deleted_docs_count += 1

            if deleted_docs_count > 0:
                cleanup_results["firestore_collection_deleted"] = True
                logger.info(
                    f"Deleted Firestore collection '{collection_name}' with {deleted_docs_count} documents"
                )
            else:
                logger.info(
                    f"Firestore collection '{collection_name}' was empty or did not exist"
                )

        except Exception as e:
            logger.error(
                f"Failed to delete Firestore collection for account {account_id}: {e}"
            )
            cleanup_results["cleanup_errors"].append(f"Firestore cleanup failed: {e}")

        # Delete Neo4j entities in multiple simpler queries
        total_nodes_deleted = 0
        total_relationships_deleted = 0

        # First, delete all ActivityLog nodes
        delete_logs_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)<-[:LOGGED]-(log:ActivityLog)
        DETACH DELETE log
        """
        logs_summary = await db.execute_write_operation(
            delete_logs_query, {"account_id": account_id}
        )
        total_nodes_deleted += logs_summary.get("nodes_deleted", 0)
        total_relationships_deleted += logs_summary.get("relationships_deleted", 0)

        # Then delete all entities with BELONGS_TO relationship
        delete_entities_query = """
        MATCH (acc:Account {account_id: $account_id})<-[:BELONGS_TO]-(entity)
        DETACH DELETE entity
        """
        entities_summary = await db.execute_write_operation(
            delete_entities_query, {"account_id": account_id}
        )
        total_nodes_deleted += entities_summary.get("nodes_deleted", 0)
        total_relationships_deleted += entities_summary.get("relationships_deleted", 0)

        # Finally delete the account itself
        delete_account_query = """
        MATCH (acc:Account {account_id: $account_id})
        DETACH DELETE acc
        """
        account_summary = await db.execute_write_operation(
            delete_account_query, {"account_id": account_id}
        )
        total_nodes_deleted += account_summary.get("nodes_deleted", 0)
        total_relationships_deleted += account_summary.get("relationships_deleted", 0)

        # Log the deletion for auditing
        logger.info(
            f"Deleted account {account_id} with cascade delete: "
            f"{total_nodes_deleted} nodes, "
            f"{total_relationships_deleted} relationships, "
            f"GCS documents: {cleanup_results['gcs_documents_deleted']}, "
            f"Firestore collection: {cleanup_results['firestore_collection_deleted']}"
        )

        return SuccessResponse(
            message=f"Account {account_id} and all related entities deleted successfully",
            data={
                "account_id": account_id,
                "nodes_deleted": total_nodes_deleted,
                "relationships_deleted": total_relationships_deleted,
                "gcs_documents_deleted": cleanup_results["gcs_documents_deleted"],
                "firestore_collection_deleted": cleanup_results[
                    "firestore_collection_deleted"
                ],
                "cleanup_errors": cleanup_results["cleanup_errors"],
                "data_region": data_region,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error deleting account: {e!s}"
        ) from e


@router.get(
    "/organization/{organization_id}/accounts", response_model=AccountListResponse
)
async def get_accounts_by_organization(
    organization_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> AccountListResponse:
    """
    Get all accounts for a specific organization.

    **Parameters:**
    - `organization_id` (path): The unique identifier for the organization

    **Returns:**
    - `accounts`: List of account objects for the organization
    - `total`: Total number of accounts found

    **Example:**
    ```
    GET /api/v1/accounts/organization/healthway/accounts
    ```
    """
    # This is essentially the same as get_accounts with organization_id filter
    return await get_accounts(organization_id=organization_id, user=user, db=db)


async def _check_account_exists(db: Neo4jService, account_id: str) -> bool:
    """Check if an account exists in the database."""
    query = """
    MATCH (acc:Account {account_id: $account_id})
    RETURN count(acc) > 0 as exists
    """
    result = await db.execute_query(query, {"account_id": account_id})
    return result[0]["exists"] if result else False


async def _check_organization_exists(db: Neo4jService, organization_id: str) -> bool:
    """Check if an organization exists in the database."""
    query = """
    MATCH (org:Organization {organization_id: $organization_id})
    RETURN count(org) > 0 as exists
    """
    result = await db.execute_query(query, {"organization_id": organization_id})
    return result[0]["exists"] if result else False


async def _get_organization_agency_status(
    db: Neo4jService, organization_id: str
) -> bool | None:
    """Get the agency status of an organization. Returns None if organization not found."""
    query = """
    MATCH (org:Organization {organization_id: $organization_id})
    RETURN org.agency as agency
    """
    result = await db.execute_query(query, {"organization_id": organization_id})
    return result[0]["agency"] if result else None


def _create_account_from_record(acc_data: dict[str, Any]) -> Account:
    """Create an Account object from a Neo4j record."""
    # Debug logging to see what's in the Neo4j record
    logger.info(
        f"[DEBUG] Creating account from Neo4j record for account_id: {acc_data.get('account_id')}"
    )
    logger.info(f"[DEBUG] Raw acc_data keys: {list(acc_data.keys())}")
    logger.info(
        f"[DEBUG] marketing_channels in record: {acc_data.get('marketing_channels')}"
    )
    logger.info(
        f"[DEBUG] product_integrations in record: {acc_data.get('product_integrations')}"
    )

    return Account(
        account_id=acc_data.get("account_id"),
        account_name=acc_data.get("account_name"),
        organization_id=acc_data.get("organization_id"),
        industry=acc_data.get("industry"),
        status=acc_data.get("status"),
        websites=acc_data.get("websites", []),
        timezone=acc_data.get("timezone"),
        data_region=acc_data.get("data_region", ""),
        region=acc_data.get("region", []),
        estimated_annual_ad_budget=acc_data.get("estimated_annual_ad_budget"),
        marketing_channels=acc_data.get("marketing_channels", []),
        product_integrations=acc_data.get("product_integrations", []),
    )


async def _sync_holiday_activity_logs_for_account(
    db: Neo4jService,
    bigquery: BigQueryService,
    account_id: str,
    organization_id: str,
    regions: list[str],
) -> dict[str, Any]:
    """
    Sync holiday activity logs when account regions are updated.

    This function replicates the core logic from the activities sync endpoint.
    It's called when an account's regions are modified.

    Args:
        db: Neo4j database service
        bigquery: BigQuery service instance
        account_id: ID of the account to sync
        organization_id: ID of the organization (used for logging)
        regions: List of regions to sync

    Returns:
        dict: Sync operation results
    """
    try:
        # Import here to avoid circular dependency
        from ..routers.activities import (
            _calculate_sync_operations,
            _execute_sync_operations,
            _fetch_bigquery_holidays,
            _fetch_existing_activity_logs,
        )

        # Get project ID
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            logger.warning(
                "GOOGLE_CLOUD_PROJECT_ID not set, skipping holiday activity logs sync"
            )
            return {"created": 0, "deleted": 0, "errors": ["No project ID"]}

        # Always fetch existing logs, even if no regions (to delete them)
        existing_holidays, protected_logs = await _fetch_existing_activity_logs(
            db, account_id
        )

        # Fetch holidays from BigQuery (will be empty if no regions)
        if regions:
            holidays = await _fetch_bigquery_holidays(bigquery, project_id, regions)
        else:
            # No regions means no holidays should exist
            holidays = []
            logger.info(
                f"No regions configured for account {account_id}, will delete all {len(existing_holidays)} existing holiday logs"
            )

        # Calculate sync operations
        operations = _calculate_sync_operations(
            existing_holidays, holidays, protected_logs, account_id
        )

        # Execute sync operations
        sync_results = await _execute_sync_operations(db, operations)

        logger.info(
            f"Successfully synced holiday activity logs for account {account_id}: "
            f"Created {sync_results['created']} new logs, deleted {sync_results['deleted']} outdated logs"
        )

        # Add operations to results for debugging
        sync_results["operations"] = operations
        return sync_results

    except Exception as e:
        # Log the error but don't fail the account update
        logger.error(
            f"Failed to sync holiday activity logs for account {account_id}: {e!s}"
        )
        # Don't raise - let account update succeed even if sync fails
        return {"created": 0, "deleted": 0, "errors": [str(e)]}


# Account Permission Models
class GrantAccountAccessRequest(BaseModel):
    """Request model for granting account access."""

    user_id: str = Field(..., description="User ID to grant access to")
    access_level: str = Field(..., description="Access level: edit or view")


class AccountPermissionsResponse(BaseModel):
    """Response model for account permissions."""

    account_id: str = Field(..., description="Account ID")
    permissions: list[dict[str, Any]] = Field(
        ..., description="List of user permissions"
    )
    total: int = Field(..., description="Total number of users with access")


class UserAccountPermission(BaseModel):
    """Model for a user's permission on an account."""

    user_id: str
    email: str
    access_level: str
    granted_by: str | None = None
    granted_at: str | None = None


# Account Permission Endpoints
@router.post("/{account_id}/grant-access", response_model=SuccessResponse)
async def grant_account_access(
    account_id: str,
    request: GrantAccountAccessRequest,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Grant a user access to an account.

    Only organization admins can grant account access.
    This is used to give view-role users access to specific accounts.

    **Parameters:**
    - `account_id` (path): Account ID
    - `user_id` (body): User ID to grant access to
    - `access_level` (body): Access level (edit or view)

    **Returns:**
    - Success response
    """
    try:
        # Validate access level
        if request.access_level not in ["edit", "view"]:
            raise HTTPException(
                status_code=400, detail="Invalid access_level. Must be 'edit' or 'view'"
            )

        # Check database connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Get account's organization
        org_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id
        """
        org_result = await db.execute_query(org_query, {"account_id": account_id})

        if not org_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = org_result[0]["organization_id"]

        # Check if user has admin access to the organization
        if (
            not user.is_super_admin
            and user.organization_permissions.get(organization_id) != "admin"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only organization admins can grant account access",
            )

        # Check if target user exists and has access to the organization
        target_user_doc = firestore.get_document("users", request.user_id)
        if not target_user_doc:
            raise HTTPException(
                status_code=404, detail=f"User {request.user_id} not found"
            )

        target_permissions = target_user_doc.get("permissions", {})
        target_org_permissions = target_permissions.get("organizations", {})

        # Check if target user is a super admin
        target_email = target_user_doc.get("profile", {}).get("email", "")
        if target_email.lower().endswith("@ken-e.ai"):
            raise HTTPException(
                status_code=403,
                detail="Cannot modify permissions for KEN-E support team members",
            )

        if organization_id not in target_org_permissions:
            raise HTTPException(
                status_code=400,
                detail=f"User {request.user_id} does not have access to the organization",
            )

        # Don't grant explicit permissions to org admins (they already have implicit access)
        if target_org_permissions[organization_id] == "admin":
            raise HTTPException(
                status_code=400,
                detail="Organization admins already have access to all accounts",
            )

        # Grant account permission in Firestore
        success = firestore.set_nested_field(
            collection="users",
            document_id=request.user_id,
            field_path=f"permissions.account_permissions.{account_id}",
            value=request.access_level,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to grant account access"
            )

        # Invalidate user cache
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(request.user_id)

        # Log the permission grant
        logger.info(
            f"User {user.user_id} granted {request.access_level} access to account {account_id} for user {request.user_id}"
        )

        return SuccessResponse(
            success=True,
            message=f"Granted {request.access_level} access to user {request.user_id}",
            data={
                "account_id": account_id,
                "user_id": request.user_id,
                "access_level": request.access_level,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error granting account access: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error granting account access: {e!s}"
        ) from e


@router.delete("/{account_id}/revoke-access/{user_id}", response_model=SuccessResponse)
async def revoke_account_access(
    account_id: str,
    user_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Revoke a user's access to an account.

    Only organization admins can revoke account access.
    Cannot revoke access from org admins (they have implicit access).

    **Parameters:**
    - `account_id` (path): Account ID
    - `user_id` (path): User ID to revoke access from

    **Returns:**
    - Success response
    """
    try:
        # Check database connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Get account's organization
        org_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id
        """
        org_result = await db.execute_query(org_query, {"account_id": account_id})

        if not org_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = org_result[0]["organization_id"]

        # Check if user has admin access to the organization
        if (
            not user.is_super_admin
            and user.organization_permissions.get(organization_id) != "admin"
        ):
            raise HTTPException(
                status_code=403,
                detail="Only organization admins can revoke account access",
            )

        # Check target user's org role
        target_user_doc = firestore.get_document("users", user_id)
        if target_user_doc:
            target_permissions = target_user_doc.get("permissions", {})
            target_org_permissions = target_permissions.get("organizations", {})

            # Check if target user is a super admin
            target_email = target_user_doc.get("profile", {}).get("email", "")
            if target_email.lower().endswith("@ken-e.ai"):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot modify permissions for KEN-E support team members",
                )

            if target_org_permissions.get(organization_id) == "admin":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot revoke access from organization admins",
                )

        # Remove account permission from Firestore
        firestore_db = firestore.get_client()
        user_ref = firestore_db.collection("users").document(user_id)

        # Use field delete to remove the specific account permission
        from google.cloud.firestore_v1 import DELETE_FIELD

        user_ref.update({f"permissions.account_permissions.{account_id}": DELETE_FIELD})

        # Invalidate user cache
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user_id)

        # Log the permission revocation
        logger.info(
            f"User {user.user_id} revoked access to account {account_id} from user {user_id}"
        )

        return SuccessResponse(
            success=True,
            message=f"Revoked access from user {user_id}",
            data={"account_id": account_id, "user_id": user_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking account access: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error revoking account access: {e!s}"
        ) from e


@router.get("/{account_id}/permissions", response_model=AccountPermissionsResponse)
async def get_account_permissions(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> AccountPermissionsResponse:
    """
    Get all users with explicit access to an account.

    Only shows users with explicit permissions (view-role users).
    Organization admins are not shown as they have implicit access.

    **Parameters:**
    - `account_id` (path): Account ID

    **Returns:**
    - List of users with their access levels
    """
    try:
        # Check database connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Get account's organization
        org_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id
        """
        org_result = await db.execute_query(org_query, {"account_id": account_id})

        if not org_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = org_result[0]["organization_id"]

        # Check if user has access to view permissions
        if not user.is_super_admin:
            if not user.has_organization_access(organization_id):
                raise HTTPException(status_code=403, detail="Access denied")

        # Query all users to find those with explicit account permissions
        firestore_db = firestore.get_client()
        users_ref = firestore_db.collection("users")
        all_users = users_ref.stream()

        permissions_list = []

        for user_doc in all_users:
            user_data = user_doc.to_dict()
            user_permissions = user_data.get("permissions", {})
            account_permissions = user_permissions.get("account_permissions", {})

            # Check if user has explicit permission for this account
            if account_id in account_permissions:
                permission_info = {
                    "user_id": user_doc.id,
                    "email": user_data.get("profile", {}).get("email", ""),
                    "access_level": account_permissions[account_id],
                    "first_name": user_data.get("profile", {}).get("firstName", ""),
                    "last_name": user_data.get("profile", {}).get("lastName", ""),
                }
                permissions_list.append(permission_info)

        return AccountPermissionsResponse(
            account_id=account_id,
            permissions=permissions_list,
            total=len(permissions_list),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account permissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error getting account permissions: {e!s}"
        ) from e


@router.post("/{account_id}/documents")
async def upload_business_documents(
    account_id: str,
    files: list[UploadFile] = File(...),
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    storage: StorageService = Depends(get_storage_service),
) -> dict[str, Any]:
    """
    Upload business strategy documents for an account.

    Supported file types: .pdf, .xlsx, .docx, .pptx, .txt, .png, .jpg
    Maximum file size: 25MB per file, 100MB total per account
    Maximum files: 10 per account

    **Parameters:**
    - `account_id` (path): Account ID
    - `files` (form data): List of files to upload

    **Returns:**
    - Upload results with file information
    """
    try:
        # Check database connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Check if account exists and user has access, get account data_region
        account_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id, acc.data_region as data_region
        """
        account_result = await db.execute_query(
            account_query, {"account_id": account_id}
        )

        if not account_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = account_result[0]["organization_id"]
        data_region = account_result[0]["data_region"] or "US"

        # Check user access
        if not user.is_super_admin:
            if not user.has_organization_access(organization_id):
                raise HTTPException(status_code=403, detail="Access denied to account")

            # Check account-specific access for view-role users
            if user.organization_permissions.get(organization_id) == "view":
                if account_id not in user.account_permissions:
                    raise HTTPException(
                        status_code=403, detail="Access denied to account"
                    )

        # Validate files
        ALLOWED_EXTENSIONS = {
            ".pdf",
            ".xlsx",
            ".docx",
            ".pptx",
            ".txt",
            ".png",
            ".jpg",
            ".jpeg",
        }
        MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
        MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB
        MAX_FILES = 10

        if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=400, detail=f"Maximum {MAX_FILES} files allowed"
            )

        total_size = 0
        for file in files:
            # Check file extension
            if file.filename:
                file_ext = "." + file.filename.split(".")[-1].lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File type {file_ext} not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}",
                    )

            # Check file size (read a bit to get size)
            content = await file.read()
            file_size = len(content)
            total_size += file_size

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds maximum size of 25MB",
                )

            # Reset file pointer
            await file.seek(0)

        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=400, detail="Total file size exceeds 100MB limit"
            )

        # Upload files to GCS
        uploaded_files = await storage.upload_business_documents(
            account_id, data_region, files
        )

        # Store file metadata in Firestore for search/indexing
        try:
            successful_uploads = [f for f in uploaded_files if "error" not in f]
            if successful_uploads:
                firestore = get_firestore_service()
                doc_data = {
                    "account_id": account_id,
                    "files": successful_uploads,
                    "uploaded_by": user.user_id,
                    "uploaded_at": datetime.now().isoformat(),
                    "organization_id": organization_id,
                }
                firestore.set_document(
                    "account_documents", account_id, doc_data, merge=True
                )
        except Exception as e:
            logger.warning(f"Failed to store document metadata in Firestore: {e}")

        return {
            "success": True,
            "message": f"Uploaded {len([f for f in uploaded_files if 'error' not in f])} files successfully",
            "account_id": account_id,
            "files": uploaded_files,
            "total_files": len(files),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error uploading documents for account {account_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error uploading documents: {e!s}"
        ) from e


@router.get("/{account_id}/documents")
async def list_business_documents(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    storage: StorageService = Depends(get_storage_service),
) -> dict[str, Any]:
    """
    List business strategy documents for an account.

    **Parameters:**
    - `account_id` (path): Account ID

    **Returns:**
    - List of uploaded documents
    """
    try:
        # Check access and get account data_region
        account_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
        RETURN org.organization_id as organization_id, acc.data_region as data_region
        """
        account_result = await db.execute_query(
            account_query, {"account_id": account_id}
        )

        if not account_result:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        organization_id = account_result[0]["organization_id"]
        data_region = account_result[0]["data_region"] or "US"

        # Check user access
        if not user.is_super_admin:
            if not user.has_organization_access(organization_id):
                raise HTTPException(status_code=403, detail="Access denied to account")

            if user.organization_permissions.get(organization_id) == "view":
                if account_id not in user.account_permissions:
                    raise HTTPException(
                        status_code=403, detail="Access denied to account"
                    )

        # List documents from GCS
        documents = await storage.list_account_documents(account_id, data_region)

        return {
            "success": True,
            "account_id": account_id,
            "documents": documents,
            "total_documents": len(documents),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error listing documents for account {account_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error listing documents: {e!s}"
        ) from e
