"""Organizations router for CRUD operations on organization entities."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    Organization,
    OrganizationListResponse,
    OrganizationRequest,
    SuccessResponse,
    Billing,
    PaymentMethod,
    Subscription,
    Team,
)

router = APIRouter(tags=["organizations"])

# Logger
logger = logging.getLogger(__name__)

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."
ORGANIZATION_NOT_FOUND_MESSAGE = "Organization not found"


@router.get("/", response_model=OrganizationListResponse)
async def get_organizations(
    db: Neo4jService = Depends(get_neo4j_service),
) -> OrganizationListResponse:
    """
    Get all organizations.

    Returns a list of all organizations with their properties including
    subscription, billing, and team information.

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

        # Query to fetch all organizations
        organizations_query = """
        MATCH (org:Organization)
        RETURN org
        ORDER BY org.organization_name
        """

        result = await db.execute_query(organizations_query)

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
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error fetching organizations: {str(e)}"
        )


@router.get("/{organization_id}", response_model=Organization)
async def get_organization(
    organization_id: str,
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
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error fetching organization: {str(e)}"
        )


@router.post("/", response_model=Organization)
async def create_organization(
    request: OrganizationRequest,
    db: Neo4jService = Depends(get_neo4j_service),
) -> Organization:
    """
    Create a new organization.

    **Request Body:**
    - `organization_name` (required): Name of the organization
    - `plan` (required): Subscription plan tier
    - `website` (optional): Organization website URL
    - `company_size` (required): Size category of the company
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
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Validate required fields
        if not request.organization_name:
            raise HTTPException(status_code=400, detail="organization_name is required")
        if not request.plan:
            raise HTTPException(status_code=400, detail="plan is required")
        if not request.company_size:
            raise HTTPException(status_code=400, detail="company_size is required")
        if request.agency is None:
            raise HTTPException(status_code=400, detail="agency is required")
        if not request.subscription:
            raise HTTPException(status_code=400, detail="subscription is required")
        if not request.billing:
            raise HTTPException(status_code=400, detail="billing is required")
        if not request.team:
            raise HTTPException(status_code=400, detail="team is required")

        # Generate organization_id from name
        organization_id = (
            request.organization_name.lower().replace(" ", "-").replace("_", "-")
        )

        # Check if organization already exists
        existing_org = await _check_organization_exists(db, organization_id)
        if existing_org:
            raise HTTPException(
                status_code=409,
                detail=f"Organization with ID {organization_id} already exists",
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
            "company_size": request.company_size,
            "agency": request.agency,
            "child_organizations": request.child_organizations or [],
            "subscription": json.dumps(request.subscription.model_dump()),
            "billing": json.dumps(request.billing.model_dump()),
            "team": json.dumps(request.team.model_dump()),
        }

        await db.execute_write_query(create_query, params)

        # Fetch the created organization
        return await get_organization(organization_id, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error creating organization: {str(e)}"
        )


@router.put("/{organization_id}", response_model=Organization)
async def update_organization(
    organization_id: str,
    request: OrganizationRequest,
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
        return await get_organization(organization_id, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error updating organization: {str(e)}"
        )


@router.delete("/{organization_id}", response_model=SuccessResponse)
async def delete_organization(
    organization_id: str,
    db: Neo4jService = Depends(get_neo4j_service),
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
    """
    try:
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

        summary = await db.execute_write_query(
            delete_query, {"organization_id": organization_id}
        )

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
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error deleting organization: {str(e)}"
        )


async def _check_organization_exists(db: Neo4jService, organization_id: str) -> bool:
    """Check if an organization exists in the database."""
    query = """
    MATCH (org:Organization {organization_id: $organization_id})
    RETURN count(org) > 0 as exists
    """
    result = await db.execute_query(query, {"organization_id": organization_id})
    return result[0]["exists"] if result else False


def _create_organization_from_record(org_data: Dict[str, Any]) -> Organization:
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
            expires=payment_method_data.get("expires", "")
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
        usage=subscription_data.get("usage", {"reports_generated": 0, "reports_limit": 0})
    )
    
    # Handle team with defaults
    team = Team(
        members_used=team_data.get("members_used", 0),
        members_limit=team_data.get("members_limit", 1),
        pending_invitations=team_data.get("pending_invitations", 0)
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

