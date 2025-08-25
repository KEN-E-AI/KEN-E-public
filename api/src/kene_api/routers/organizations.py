"""Organizations router for CRUD operations on organization entities."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import UserContext, get_current_user_context
from ..config import settings
from ..database import Neo4jService, get_neo4j_service
from ..firestore import get_firestore_service
from ..models.kene_models import (
    Billing,
    ChangeSubscriptionRequest,
    Organization,
    OrganizationListResponse,
    OrganizationRequest,
    PaymentMethod,
    Subscription,
    SuccessResponse,
    Team,
)

router = APIRouter(tags=["organizations"])

# Logger
logger = logging.getLogger(__name__)


def generate_unique_organization_id() -> str:
    """
    Generate a unique organization ID using UUID4.

    Returns:
        str: A unique organization ID in the format 'org_<uuid>'

    Example:
        'org_550e8400e29b41d4a716446655440000'
    """
    # Generate UUID4 and remove hyphens for cleaner format
    unique_id = str(uuid.uuid4()).replace("-", "")
    return f"org_{unique_id}"


def generate_timestamp_organization_id() -> str:
    """
    Generate a unique organization ID using timestamp and UUID.

    Returns:
        str: A unique organization ID in the format 'org_<timestamp>_<uuid_suffix>'

    Example:
        'org_1705123456789_a1b2c3d4'
    """
    timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    uuid_suffix = str(uuid.uuid4()).replace("-", "")[:8]
    return f"org_{timestamp}_{uuid_suffix}"


# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."
ORGANIZATION_NOT_FOUND_MESSAGE = "Organization not found"


@router.get("/", response_model=OrganizationListResponse)
async def get_organizations(
    request: Request,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> OrganizationListResponse:
    """
    Get organizations accessible to the current user.

    Returns a list of organizations the user has access to with their properties
    including subscription, billing, and team information.

    **Returns:**
    - `organizations`: List of organization objects with all properties
    - `total`: Total number of organizations found

    **Example:**
    ```
    GET /api/v1/organizations/
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Get organization IDs the user has access to
        if user.is_super_admin:
            # Super admins can see all organizations
            organizations_query = """
            MATCH (org:Organization)
            RETURN org
            ORDER BY org.organization_name
            """
            result = await db.execute_query(organizations_query, {})
        else:
            # Regular users see only their organizations
            accessible_org_ids = list(user.organization_permissions.keys())

            if not accessible_org_ids:
                # User has no organization access
                return OrganizationListResponse(organizations=[], total=0)

            # Query to fetch only organizations the user has access to
            organizations_query = """
            MATCH (org:Organization)
            WHERE org.organization_id IN $org_ids
            RETURN org
            ORDER BY org.organization_name
            """

            result = await db.execute_query(
                organizations_query, {"org_ids": accessible_org_ids}
            )

        organizations = []
        for record in result:
            org_data = record.get("org")
            if org_data:
                organization = _create_organization_from_record(org_data)
                organizations.append(organization)

        return OrganizationListResponse(
            organizations=organizations, total=len(organizations)
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error fetching organizations: {e!s}"
        )


@router.get("/{organization_id}", response_model=Organization)
async def get_organization(
    organization_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Organization:
    """
    Get a specific organization by ID.

    **Parameters:**
    - `organization_id` (path): The unique identifier for the organization

    **Returns:**
    - Organization object with all properties

    **Example:**
    ```
    GET /api/v1/organizations/healthway
    ```

    **Note:** User must have access to the organization.
    """
    # Check if user has access to this organization
    if not user.has_organization_access(organization_id):
        raise HTTPException(
            status_code=403, detail=f"Access denied to organization {organization_id}"
        )

    # Use internal helper to fetch organization
    return await _get_organization_by_id(organization_id, db)


@router.post("/", response_model=Organization)
async def create_organization(
    request: OrganizationRequest,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Organization:
    """
    Create a new organization.

    **Request Body:**
    - `organization_name` (required): Name of the organization
    - `plan` (required): Subscription plan tier
    - `website` (optional): Organization website URL
    - `company_size` (optional): Size category of the company
    - `agency` (required): Whether the organization is an agency
    - `child_organizations` (optional): List of child organization IDs
    - `subscription` (required): Subscription details object
    - `billing` (required): Billing information object
    - `team` (required): Team information object

    **Returns:**
    - Created organization object with generated organization_id

    **Example:**
    ```
    POST /api/v1/organizations/
    {
        "organization_name": "New Company",
        "plan": "Professional",
        "website": "https://newcompany.com",
        "company_size": "medium",
        "agency": false,
        "subscription": {...},
        "billing": {...},
        "team": {...}
    }
    ```
    """
    try:
        # Check if user has permission to create organizations based on configuration
        permission_level = settings.organization_creation_permission

        if permission_level == "none":
            raise HTTPException(
                status_code=403, detail="Organization creation is currently disabled"
            )
        elif permission_level == "super_admin" and not user.is_super_admin:
            raise HTTPException(
                status_code=403,
                detail="Only super administrators can create organizations",
            )
        # If permission_level == "all", any authenticated user can create

        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Validate required fields
        if not request.organization_name:
            raise HTTPException(status_code=400, detail="organization_name is required")
        if not request.plan:
            raise HTTPException(status_code=400, detail="plan is required")
        if request.agency is None:
            raise HTTPException(status_code=400, detail="agency is required")
        if not request.subscription:
            raise HTTPException(status_code=400, detail="subscription is required")
        if not request.billing:
            raise HTTPException(status_code=400, detail="billing is required")
        if not request.team:
            raise HTTPException(status_code=400, detail="team is required")

        # Generate unique organization_id using UUID
        organization_id = generate_unique_organization_id()

        # Check if organization already exists (extremely unlikely with UUID4)
        existing_org = await _check_organization_exists(db, organization_id)
        if existing_org:
            logger.warning(
                f"UUID collision detected for organization_id: {organization_id}"
            )
            # Generate a new UUID if collision occurs (extremely rare)
            organization_id = generate_unique_organization_id()
            existing_org = await _check_organization_exists(db, organization_id)
            if existing_org:
                raise HTTPException(
                    status_code=500,
                    detail="Unable to generate unique organization ID. Please try again.",
                )

        # Create organization node
        create_query = """
        CREATE (org:Organization {
            organization_id: $organization_id,
            organization_name: $organization_name,
            plan: $plan,
            website: $website,
            company_size: $company_size,
            agency: $agency,
            child_organizations: $child_organizations,
            subscription: $subscription,
            billing: $billing,
            team: $team
        })
        RETURN org
        """

        params = {
            "organization_id": organization_id,
            "organization_name": request.organization_name,
            "plan": request.plan,
            "website": request.website or "",
            # Neo4j doesn't distinguish between NULL and empty string for string properties,
            # so we convert None to empty string to avoid potential query issues
            "company_size": request.company_size or "",
            "agency": request.agency,
            "child_organizations": request.child_organizations or [],
            "subscription": json.dumps(request.subscription.model_dump()),
            "billing": json.dumps(request.billing.model_dump()),
            "team": json.dumps(request.team.model_dump()),
        }

        await db.execute_write_query(create_query, params)

        # Grant the creating user admin permissions on the new organization
        firestore_service = get_firestore_service()
        try:
            success = firestore_service.set_nested_field(
                collection="users",
                document_id=user.user_id,
                field_path=f"permissions.organizations.{organization_id}",
                value="admin",
            )
            if not success:
                # If we can't grant permissions, rollback the organization creation
                logger.error(
                    f"Failed to grant permissions to user {user.user_id} for organization {organization_id}. "
                    "Rolling back organization creation."
                )

                # Attempt to delete the created organization
                try:
                    delete_query = """
                    MATCH (org:Organization {organization_id: $organization_id})
                    DELETE org
                    """
                    await db.execute_write_operation(
                        delete_query, {"organization_id": organization_id}
                    )
                    logger.info(
                        f"Successfully rolled back organization {organization_id}"
                    )
                except Exception as rollback_error:
                    logger.critical(
                        f"Failed to rollback organization {organization_id} after permission grant failure: {rollback_error}"
                    )

                raise HTTPException(
                    status_code=500,
                    detail="Failed to complete organization setup. Please try again.",
                )

            logger.info(
                f"Granted admin permissions to user {user.user_id} for organization {organization_id}"
            )

            # Invalidate the creating user's cache to ensure their context includes the new organization
            from ..auth.cached_user_context import get_cached_user_context_service

            cached_user_service = get_cached_user_context_service()
            cached_user_service.invalidate_user_context(user.user_id)
            logger.info(
                f"Invalidated cache for user {user.user_id} after creating organization {organization_id}"
            )

        except HTTPException:
            raise
        except Exception as e:
            # If Firestore is down or there's a critical error, rollback
            logger.error(
                f"Critical error granting permissions to user {user.user_id} for organization {organization_id}: {e}. "
                "Rolling back organization creation."
            )

            # Attempt to delete the created organization
            try:
                delete_query = """
                MATCH (org:Organization {organization_id: $organization_id})
                DELETE org
                """
                await db.execute_write_operation(
                    delete_query, {"organization_id": organization_id}
                )
                logger.info(f"Successfully rolled back organization {organization_id}")
            except Exception as rollback_error:
                logger.critical(
                    f"Failed to rollback organization {organization_id} after permission grant failure: {rollback_error}"
                )

            raise HTTPException(
                status_code=500,
                detail="Failed to complete organization setup due to permission system error.",
            )

        # Fetch the created organization
        return await _get_organization_by_id(organization_id, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error creating organization: {e!s}"
        )


@router.put("/{organization_id}", response_model=Organization)
async def update_organization(
    organization_id: str,
    request: OrganizationRequest,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Organization:
    """
    Update an existing organization.

    **Parameters:**
    - `organization_id` (path): The unique identifier for the organization

    **Request Body:**
    - All fields are optional, only provided fields will be updated

    **Returns:**
    - Updated organization object

    **Example:**
    ```
    PUT /api/v1/organizations/healthway
    {
        "plan": "Enterprise",
        "team": {
            "members_used": 10,
            "members_limit": 50,
            "pending_invitations": 2
        }
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Check if user has access to this organization
        if not user.has_organization_access(organization_id):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to organization {organization_id}",
            )

        # Check if organization exists
        existing_org = await _check_organization_exists(db, organization_id)
        if not existing_org:
            raise HTTPException(status_code=404, detail=ORGANIZATION_NOT_FOUND_MESSAGE)

        # Build update query dynamically based on provided fields
        update_clauses = []
        params = {"organization_id": organization_id}

        if request.organization_name is not None:
            update_clauses.append("org.organization_name = $organization_name")
            params["organization_name"] = request.organization_name

        if request.plan is not None:
            update_clauses.append("org.plan = $plan")
            params["plan"] = request.plan

        if request.website is not None:
            update_clauses.append("org.website = $website")
            params["website"] = request.website

        if request.company_size is not None:
            update_clauses.append("org.company_size = $company_size")
            params["company_size"] = request.company_size

        if request.agency is not None:
            update_clauses.append("org.agency = $agency")
            params["agency"] = request.agency

        if request.child_organizations is not None:
            update_clauses.append("org.child_organizations = $child_organizations")
            params["child_organizations"] = request.child_organizations

        if request.subscription is not None:
            update_clauses.append("org.subscription = $subscription")
            params["subscription"] = request.subscription.model_dump()

        if request.billing is not None:
            update_clauses.append("org.billing = $billing")
            params["billing"] = request.billing.model_dump()

        if request.team is not None:
            update_clauses.append("org.team = $team")
            params["team"] = request.team.model_dump()

        if not update_clauses:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Execute update query
        update_query = f"""
        MATCH (org:Organization {{organization_id: $organization_id}})
        SET {", ".join(update_clauses)}
        RETURN org
        """

        await db.execute_write_query(update_query, params)

        # Return updated organization
        return await get_organization(organization_id, user, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error updating organization: {e!s}"
        )


async def check_user_organization_permission(
    account_id: str,
    organization_id: str,
    required_roles: list[str],
    firestore_service,
) -> bool:
    """
    Check if a user has the required permission for an organization.

    Args:
        account_id: The user's account ID
        organization_id: The organization ID
        required_roles: List of acceptable roles (e.g., ["admin", "view"])
        firestore_service: Firestore service instance

    Returns:
        bool: True if user has permission, False otherwise

    Raises:
        HTTPException: If there's an error accessing Firestore
    """
    try:
        user_doc = firestore_service.get_document("users", account_id)
        if not user_doc:
            logger.warning(f"User document not found for account_id: {account_id}")
            return False

        permissions = user_doc.get("permissions", {})
        org_permissions = permissions.get("organizations", {})
        user_role = org_permissions.get(organization_id)

        has_permission = user_role in required_roles
        if not has_permission:
            logger.info(
                f"User {account_id} lacks required permission for org {organization_id}. "
                f"User role: {user_role}, Required: {required_roles}"
            )

        return has_permission
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error checking user permissions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to verify user permissions")


async def validate_plan_change(
    existing_org: Organization,
    new_plan: dict[str, Any],
) -> None:
    """
    Validate that a plan change is allowed.

    Args:
        existing_org: Current organization data
        new_plan: New subscription plan data

    Raises:
        HTTPException: If validation fails
    """
    # Check if downgrading would violate current usage
    max_users = new_plan["features"]["max_users"]
    current_users = existing_org.team.members_used

    if max_users < current_users:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change to this plan: Plan supports {max_users} users but organization has {current_users} active members. Please remove users before downgrading.",
        )

    # Check if reports usage would be exceeded
    max_reports = new_plan["features"]["max_reports"]
    current_reports = existing_org.subscription.usage.get("reports_generated", 0)

    if max_reports < current_reports:
        logger.warning(
            f"Organization {existing_org.organization_id} changing to plan with lower report limit. "
            f"Current usage: {current_reports}, new limit: {max_reports}"
        )


async def verify_subscription_prerequisites(
    db: Neo4jService,
    firestore_service,
    account_id: str,
    organization_id: str,
) -> Organization:
    """
    Verify all prerequisites for changing subscription.

    Args:
        db: Neo4j service instance
        firestore_service: Firestore service instance
        account_id: User's account ID
        organization_id: Organization ID

    Returns:
        Organization: The existing organization

    Raises:
        HTTPException: If any prerequisite check fails
    """
    # Check database health
    is_healthy = await db.health_check()
    if not is_healthy:
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

    # Check Firestore health
    if not firestore_service.health_check():
        raise HTTPException(status_code=503, detail="Firestore service unavailable")

    # Check user permissions
    has_permission = await check_user_organization_permission(
        account_id, organization_id, ["admin"], firestore_service
    )
    if not has_permission:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to change this organization's subscription",
        )

    # Verify organization exists - using internal helper since we already verified permissions
    existing_org = await _get_organization_by_id(organization_id, db)
    if not existing_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return existing_org


async def fetch_and_validate_plan(
    firestore_service,
    plan_id: str,
) -> dict[str, Any]:
    """
    Fetch and validate a subscription plan.

    Args:
        firestore_service: Firestore service instance
        plan_id: The plan ID to fetch

    Returns:
        dict: The plan data

    Raises:
        HTTPException: If plan not found or invalid
    """
    plan_data = firestore_service.get_document(
        collection="subscription-plans",
        document_id=plan_id,
    )

    if not plan_data:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    if not plan_data.get("is_active", True):
        raise HTTPException(status_code=400, detail="Subscription plan is not active")

    return plan_data


def build_subscription_from_plan(
    plan_data: dict[str, Any],
    existing_subscription: Subscription,
) -> dict[str, Any]:
    """
    Build a subscription object from plan data.

    Args:
        plan_data: Subscription plan data from Firestore
        existing_subscription: Current subscription to preserve some fields

    Returns:
        dict: New subscription data
    """
    return {
        "plan_name": plan_data["plan_name"],
        "plan_description": plan_data["plan_description"],
        "price": plan_data["price"],
        "currency": plan_data["currency"],
        "billing_cycle": plan_data["billing_cycle"],
        "next_billing_date": existing_subscription.next_billing_date,  # Preserve billing date
        "features": plan_data["features"]["features"],
        "usage": {
            "reports_generated": existing_subscription.usage.get(
                "reports_generated", 0
            ),  # Preserve usage
            "reports_limit": plan_data["features"]["max_reports"],
        },
    }


@router.put("/{organization_id}/subscription", response_model=Organization)
async def change_organization_subscription(
    organization_id: str,
    request: ChangeSubscriptionRequest,
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Organization:
    """
    Change an organization's subscription plan.

    **Parameters:**
    - `organization_id` (path): The unique identifier for the organization
    - `plan_id` (body): The ID of the new subscription plan
    - `account_id` (query): The account ID of the user making the request

    **Returns:**
    - Updated organization object with new subscription details

    **Authorization:**
    - User must have admin permissions for the organization
    """
    try:
        # Get Firestore service
        firestore_service = get_firestore_service()

        # Verify all prerequisites
        existing_org = await verify_subscription_prerequisites(
            db, firestore_service, account_id, organization_id
        )

        # Fetch and validate the new plan
        plan_data = await fetch_and_validate_plan(firestore_service, request.plan_id)

        # Validate the plan change is allowed
        await validate_plan_change(existing_org, plan_data)

        # Build the new subscription
        new_subscription = build_subscription_from_plan(
            plan_data, existing_org.subscription
        )

        # Update organization in database
        await update_organization_subscription_in_db(
            db, organization_id, new_subscription, plan_data
        )

        # Log the change
        logger.info(
            f"Organization {organization_id} subscription changed to {request.plan_id} "
            f"by account {account_id}"
        )

        # Return updated organization
        return await get_organization(organization_id, user, db)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error changing subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while changing the subscription",
        )


async def get_organization_team(
    db: Neo4jService,
    organization_id: str,
) -> dict[str, Any]:
    """
    Get the current team data for an organization.

    Args:
        db: Neo4j service instance
        organization_id: Organization ID

    Returns:
        dict: Team data

    Raises:
        ValueError: If organization not found
    """
    query = """
    MATCH (o:Organization {organization_id: $organization_id})
    RETURN o.team as team
    """

    result = await db.execute_query(query, {"organization_id": organization_id})
    if not result:
        raise ValueError(f"Organization {organization_id} not found")

    # Parse team data
    team_data = result[0]["team"]
    if isinstance(team_data, str):
        team_data = json.loads(team_data)

    return team_data


def update_team_member_limit(
    team_data: dict[str, Any],
    new_member_limit: int,
) -> dict[str, Any]:
    """
    Update the member limit in team data.

    Args:
        team_data: Existing team data
        new_member_limit: New member limit

    Returns:
        dict: Updated team data
    """
    updated_team = team_data.copy()
    updated_team["members_limit"] = new_member_limit
    return updated_team


async def save_organization_subscription_updates(
    db: Neo4jService,
    organization_id: str,
    subscription_data: dict[str, Any],
    team_data: dict[str, Any],
    plan_name: str,
) -> None:
    """
    Save organization updates to the database.

    Args:
        db: Neo4j service instance
        organization_id: Organization ID
        subscription_data: New subscription data
        team_data: Updated team data
        plan_name: New plan name
    """
    query = """
    MATCH (o:Organization {organization_id: $organization_id})
    SET o.subscription = $subscription,
        o.team = $team,
        o.plan = $plan_name,
        o.updated_at = datetime()
    RETURN o
    """

    await db.execute_write_query(
        query,
        parameters={
            "organization_id": organization_id,
            "subscription": json.dumps(subscription_data),
            "team": json.dumps(team_data),
            "plan_name": plan_name,
        },
    )


async def update_organization_subscription_in_db(
    db: Neo4jService,
    organization_id: str,
    subscription_data: dict[str, Any],
    plan_data: dict[str, Any],
) -> None:
    """
    Update organization subscription in the database.

    Args:
        db: Neo4j service instance
        organization_id: Organization ID
        subscription_data: New subscription data
        plan_data: Plan data for additional fields
    """
    # Get current team data
    existing_team = await get_organization_team(db, organization_id)

    # Update team with new member limit
    updated_team = update_team_member_limit(
        existing_team, plan_data["features"]["max_users"]
    )

    # Save all updates to database
    await save_organization_subscription_updates(
        db, organization_id, subscription_data, updated_team, plan_data["plan_name"]
    )


@router.put(
    "/{organization_id}/move-account/{account_id}", response_model=SuccessResponse
)
async def move_account_to_organization(
    organization_id: str,
    account_id: str,
    request: dict[str, str],
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Move an account from one organization to another.

    **Parameters:**
    - `organization_id` (path): The current organization ID that owns the account
    - `account_id` (path): The account ID to move
    - `new_organization_id` (body): The target organization ID to move the account to

    **Request Body:**
    ```json
    {
        "new_organization_id": "target-org-id"
    }
    ```

    **Returns:**
    - Success response with move details

    **Example:**
    ```
    PUT /api/v1/organizations/current-org/move-account/acc-123
    {
        "new_organization_id": "target-org"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Get new organization ID from request body
        new_organization_id = request.get("new_organization_id")
        if not new_organization_id:
            raise HTTPException(
                status_code=400,
                detail="new_organization_id is required in request body",
            )

        # Validate that source and target organizations are different
        if organization_id == new_organization_id:
            raise HTTPException(
                status_code=400, detail="Cannot move account to the same organization"
            )

        # Check if current organization exists
        current_org_exists = await _check_organization_exists(db, organization_id)
        if not current_org_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Current organization {organization_id} not found",
            )

        # Check if target organization exists
        target_org_exists = await _check_organization_exists(db, new_organization_id)
        if not target_org_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Target organization {new_organization_id} not found",
            )

        # Check if account exists and belongs to current organization
        account_check_query = """
        MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization {organization_id: $organization_id})
        RETURN count(acc) > 0 as account_exists
        """
        result = await db.execute_query(
            account_check_query,
            {"account_id": account_id, "organization_id": organization_id},
        )
        account_exists = result[0]["account_exists"] if result else False

        if not account_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Account {account_id} not found in organization {organization_id}",
            )

        # Move the account by updating the BELONGS_TO relationship
        move_query = """
        MATCH (acc:Account {account_id: $account_id})-[old_rel:BELONGS_TO]->(old_org:Organization {organization_id: $old_organization_id})
        MATCH (new_org:Organization {organization_id: $new_organization_id})
        DELETE old_rel
        CREATE (acc)-[:BELONGS_TO]->(new_org)
        SET acc.organization_id = $new_organization_id
        RETURN acc, old_org.organization_name as old_org_name, new_org.organization_name as new_org_name
        """

        result = await db.execute_write_query(
            move_query,
            {
                "account_id": account_id,
                "old_organization_id": organization_id,
                "new_organization_id": new_organization_id,
            },
        )

        # Check if the result is a list of records or a summary
        if isinstance(result, list) and len(result) > 0:
            # Get organization names from the returned records
            record = result[0]
            old_org_name = record.get("old_org_name", organization_id)
            new_org_name = record.get("new_org_name", new_organization_id)
        elif isinstance(result, dict):
            # Result is a summary (when no changes made), get org names separately
            # Check if any changes were actually made
            changes_made = (
                result.get("relationships_created", 0) > 0
                or result.get("relationships_deleted", 0) > 0
                or result.get("properties_set", 0) > 0
            )

            if not changes_made:
                # Account might already be in the target organization or doesn't exist
                # Verify the current state
                verify_query = """
                MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
                RETURN org.organization_id as current_org_id, org.organization_name as current_org_name
                """
                verify_result = await db.execute_query(
                    verify_query, {"account_id": account_id}
                )

                if verify_result:
                    current_org_id = verify_result[0].get("current_org_id")
                    current_org_name = verify_result[0].get("current_org_name")

                    if current_org_id == new_organization_id:
                        # Account is already in the target organization
                        raise HTTPException(
                            status_code=400,
                            detail=f"Account {account_id} is already in organization {current_org_name or new_organization_id}",
                        )
                    else:
                        # Account is in a different organization than expected
                        raise HTTPException(
                            status_code=400,
                            detail=f"Account {account_id} is currently in organization {current_org_name or current_org_id}, not {organization_id}",
                        )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Account {account_id} not found or has no organization relationship",
                    )

            # If changes were made, get organization names separately
            old_org_query = "MATCH (org:Organization {organization_id: $org_id}) RETURN org.organization_name as name"
            new_org_query = "MATCH (org:Organization {organization_id: $org_id}) RETURN org.organization_name as name"

            old_result = await db.execute_query(
                old_org_query, {"org_id": organization_id}
            )
            new_result = await db.execute_query(
                new_org_query, {"org_id": new_organization_id}
            )

            old_org_name = old_result[0]["name"] if old_result else organization_id
            new_org_name = new_result[0]["name"] if new_result else new_organization_id
        else:
            raise HTTPException(status_code=500, detail="Failed to move account")

        return SuccessResponse(
            message=f"Account {account_id} moved successfully from {old_org_name} to {new_org_name}",
            data={
                "account_id": account_id,
                "old_organization_id": organization_id,
                "new_organization_id": new_organization_id,
                "old_organization_name": old_org_name,
                "new_organization_name": new_org_name,
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
            status_code=500, detail=f"Error moving account: {e!s}"
        ) from e


@router.delete("/{organization_id}", response_model=SuccessResponse)
async def delete_organization(
    organization_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
    firestore_service=Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete an organization.

    **Parameters:**
    - `organization_id` (path): The unique identifier for the organization

    **Returns:**
    - Success response with deletion details

    **Example:**
    ```
    DELETE /api/v1/organizations/healthway
    ```
    
    **Note:** User must have admin permissions for the organization.
    """
    try:
        # Check if user has permission to delete this organization
        if not user.is_super_admin:
            # Check if user has admin role for this organization
            user_role = user.organization_permissions.get(organization_id)
            if user_role != "admin":
                raise HTTPException(
                    status_code=403,
                    detail=f"You do not have permission to delete organization {organization_id}",
                )
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Check if organization exists
        existing_org = await _check_organization_exists(db, organization_id)
        if not existing_org:
            raise HTTPException(status_code=404, detail=ORGANIZATION_NOT_FOUND_MESSAGE)

        # Check if organization has accounts
        check_accounts_query = """
        MATCH (org:Organization {organization_id: $organization_id})<-[:BELONGS_TO]-(acc:Account)
        RETURN count(acc) as account_count
        """
        result = await db.execute_query(
            check_accounts_query, {"organization_id": organization_id}
        )
        account_count = result[0]["account_count"] if result else 0

        if account_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete organization with {account_count} associated accounts. Delete accounts first.",
            )

        # Delete organization and any PARENT_OF relationships
        delete_query = """
        MATCH (org:Organization {organization_id: $organization_id})
        DETACH DELETE org
        """

        summary = await db.execute_write_operation(
            delete_query, {"organization_id": organization_id}
        )

        # Remove organization permissions from all users in Firestore
        await remove_organization_from_all_users(organization_id, firestore_service)

        return SuccessResponse(
            message=f"Organization {organization_id} deleted successfully",
            data={
                "organization_id": organization_id,
                "nodes_deleted": summary.get("nodes_deleted", 0),
                "relationships_deleted": summary.get("relationships_deleted", 0),
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
            status_code=500, detail=f"Error deleting organization: {e!s}"
        )


async def _check_organization_exists(db: Neo4jService, organization_id: str) -> bool:
    """Check if an organization exists in the database."""
    query = """
    MATCH (org:Organization {organization_id: $organization_id})
    RETURN count(org) > 0 as exists
    """
    result = await db.execute_query(query, {"organization_id": organization_id})
    return result[0]["exists"] if result else False


async def _get_organization_by_id(
    organization_id: str,
    db: Neo4jService,
) -> Organization:
    """
    Get a specific organization by ID without authentication.
    Internal helper function for use within the router.

    Args:
        organization_id: The unique identifier for the organization
        db: Neo4j service instance

    Returns:
        Organization object

    Raises:
        HTTPException: If organization not found or database error
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch specific organization
        organization_query = """
        MATCH (org:Organization {organization_id: $organization_id})
        RETURN org
        """

        result = await db.execute_query(
            organization_query, {"organization_id": organization_id}
        )

        if not result:
            raise HTTPException(status_code=404, detail=ORGANIZATION_NOT_FOUND_MESSAGE)

        org_data = result[0].get("org")
        organization = _create_organization_from_record(org_data)

        return organization

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error fetching organization: {e!s}"
        )


async def remove_organization_from_all_users(
    organization_id: str, firestore_service
) -> None:
    """
    Remove organization permissions from all users in Firestore.

    This function queries all users and removes the specified organization
    from their permissions.organizations field.

    Args:
        organization_id: The organization ID to remove
        firestore_service: Firestore service instance
    """
    try:
        # Get Firestore client
        firestore_db = firestore_service.get_client()

        # Query all users who have permissions for this organization
        users_collection = firestore_db.collection("users")

        # In Firestore, we need to get all users and check their permissions
        # since we can't directly query nested fields with dynamic keys
        all_users = users_collection.stream()

        batch_count = 0
        for user_doc in all_users:
            user_data = user_doc.to_dict()
            permissions = user_data.get("permissions", {})
            org_permissions = permissions.get("organizations", {})

            # Check if this user has access to the organization
            if organization_id in org_permissions:
                # Remove the organization from user's permissions
                del org_permissions[organization_id]

                # Update the user document
                user_doc.reference.update(
                    {"permissions.organizations": org_permissions}
                )

                batch_count += 1
                logger.info(
                    f"Removed organization {organization_id} from user {user_doc.id} permissions"
                )

        logger.info(
            f"Removed organization {organization_id} permissions from {batch_count} users"
        )

    except Exception as e:
        logger.error(
            f"Failed to remove organization {organization_id} from user permissions: {e}",
            exc_info=True,
        )
        # Don't raise the exception - we still want to complete the deletion
        # even if we fail to clean up permissions


def _create_organization_from_record(org_data: dict[str, Any]) -> Organization:
    """Create an Organization object from a Neo4j record."""
    # Parse nested objects
    subscription_data = org_data.get("subscription", {})
    if isinstance(subscription_data, str):
        import json

        subscription_data = json.loads(subscription_data)

    billing_data = org_data.get("billing", {})
    if isinstance(billing_data, str):
        import json

        billing_data = json.loads(billing_data)

    team_data = org_data.get("team", {})
    if isinstance(team_data, str):
        import json

        team_data = json.loads(team_data)

    # Create nested objects
    payment_method_data = billing_data.get("payment_method", {})
    if isinstance(payment_method_data, dict):
        # Ensure all required fields have defaults
        payment_method = PaymentMethod(
            last_four=payment_method_data.get("last_four", ""),
            brand=payment_method_data.get("brand", ""),
            expires=payment_method_data.get("expires", ""),
        )
    else:
        # Handle case where payment_method might be a string or other type
        payment_method = PaymentMethod(last_four="", brand="", expires="")

    billing = Billing(
        payment_method=payment_method,
        address=billing_data.get("address", ""),
        tax_id=billing_data.get("tax_id", ""),
    )

    # Handle subscription with defaults
    subscription = Subscription(
        plan_name=subscription_data.get("plan_name", "Unknown"),
        plan_description=subscription_data.get("plan_description", ""),
        price=subscription_data.get("price", 0.0),
        currency=subscription_data.get("currency", "USD"),
        billing_cycle=subscription_data.get("billing_cycle", "monthly"),
        next_billing_date=subscription_data.get("next_billing_date", ""),
        features=subscription_data.get("features", []),
        usage=subscription_data.get(
            "usage", {"reports_generated": 0, "reports_limit": 0}
        ),
    )

    # Handle team with defaults
    team = Team(
        members_used=team_data.get("members_used", 0),
        members_limit=team_data.get("members_limit", 1),
        pending_invitations=team_data.get("pending_invitations", 0),
    )

    # Create organization object
    return Organization(
        organization_id=org_data.get("organization_id"),
        organization_name=org_data.get("organization_name"),
        plan=org_data.get("plan"),
        website=org_data.get("website"),
        company_size=org_data.get("company_size"),
        agency=org_data.get("agency", False),
        child_organizations=org_data.get("child_organizations", []),
        subscription=subscription,
        billing=billing,
        team=team,
    )
