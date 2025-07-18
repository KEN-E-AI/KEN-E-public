"""Accounts router for CRUD operations on account entities."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    Account,
    AccountListResponse,
    AccountRequest,
    SuccessResponse,
)

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
    organization_id: Optional[str] = Query(
        None, description="Filter accounts by organization ID"
    ),
    db: Neo4jService = Depends(get_neo4j_service),
) -> AccountListResponse:
    """
    Get all accounts, optionally filtered by organization.

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
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Build query based on filter
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

        result = await db.execute_query(accounts_query, params)

        accounts = []
        for record in result:
            acc_data = record.get("acc")
            if acc_data:
                account = _create_account_from_record(acc_data)
                accounts.append(account)

        return AccountListResponse(accounts=accounts, total=len(accounts))

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error fetching accounts: {str(e)}"
        )


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: str,
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
    """
    try:
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
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error fetching account: {str(e)}")


@router.post("/", response_model=Account)
async def create_account(
    request: AccountRequest,
    db: Neo4jService = Depends(get_neo4j_service),
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
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
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
        org_exists = await _check_organization_exists(db, request.organization_id)
        if not org_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Organization {request.organization_id} not found",
            )

        # Generate unique account_id using UUID
        account_id = generate_unique_account_id()

        # Check if account already exists (extremely unlikely with UUID4)
        existing_acc = await _check_account_exists(db, account_id)
        if existing_acc:
            logger.warning(f"UUID collision detected for account_id: {account_id}")
            # Generate a new UUID if collision occurs (extremely rare)
            account_id = generate_unique_account_id()
            existing_acc = await _check_account_exists(db, account_id)
            if existing_acc:
                raise HTTPException(
                    status_code=500,
                    detail="Unable to generate unique account ID. Please try again.",
                )

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
            region: $region
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
        }

        await db.execute_write_query(create_query, params)

        # Fetch the created account
        return await get_account(account_id, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error creating account: {str(e)}")


@router.put("/{account_id}", response_model=Account)
async def update_account(
    account_id: str,
    request: AccountRequest,
    db: Neo4jService = Depends(get_neo4j_service),
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

        if not update_clauses:
            raise HTTPException(status_code=400, detail="No fields provided to update")

        # Execute update query
        update_query = f"""
        MATCH (acc:Account {{account_id: $account_id}})
        SET {", ".join(update_clauses)}
        RETURN acc
        """

        await db.execute_write_query(update_query, params)

        # Return updated account
        return await get_account(account_id, db)

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error updating account: {str(e)}")


@router.delete("/{account_id}", response_model=SuccessResponse)
async def delete_account(
    account_id: str,
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Delete an account.

    **Parameters:**
    - `account_id` (path): The unique identifier for the account

    **Returns:**
    - Success response with deletion details

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

        # Check if account exists
        existing_acc = await _check_account_exists(db, account_id)
        if not existing_acc:
            raise HTTPException(status_code=404, detail=ACCOUNT_NOT_FOUND_MESSAGE)

        # Check if account has related entities (metrics, activities, etc.)
        check_related_query = """
        MATCH (acc:Account {account_id: $account_id})
        OPTIONAL MATCH (acc)<-[:BELONGS_TO]-(entity)
        WHERE entity:Metric OR entity:Activity OR entity:Dataset
        RETURN count(entity) as related_count
        """
        result = await db.execute_query(check_related_query, {"account_id": account_id})
        related_count = result[0]["related_count"] if result else 0

        if related_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete account with {related_count} related entities. Delete related entities first.",
            )

        # Delete account and BELONGS_TO relationship
        delete_query = """
        MATCH (acc:Account {account_id: $account_id})
        DETACH DELETE acc
        """

        summary = await db.execute_write_query(delete_query, {"account_id": account_id})

        return SuccessResponse(
            message=f"Account {account_id} deleted successfully",
            data={
                "account_id": account_id,
                "nodes_deleted": summary.get("nodes_deleted", 0),
                "relationships_deleted": summary.get("relationships_deleted", 0),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error deleting account: {str(e)}")


@router.get(
    "/organization/{organization_id}/accounts", response_model=AccountListResponse
)
async def get_accounts_by_organization(
    organization_id: str,
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
    return await get_accounts(organization_id=organization_id, db=db)


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


def _create_account_from_record(acc_data: Dict[str, Any]) -> Account:
    """Create an Account object from a Neo4j record."""
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
    )
