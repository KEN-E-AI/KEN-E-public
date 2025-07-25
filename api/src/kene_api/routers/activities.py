"""Activities router for CRUD operations on activity and activity log entities."""

import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..bigquery import BigQueryService, get_bigquery_service
from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    Activity,
    ActivityListResponse,
    ActivityLog,
    ActivityLogRequest,
    ActivityRequest,
    SuccessResponse,
)

router = APIRouter(tags=["activities"])

# Logger
logger = logging.getLogger(__name__)


@router.get("/", response_model=ActivityListResponse)
async def get_activities(
    account_id: str = Query(..., description=ACCOUNT_ID_DESCRIPTION),
    db: Neo4jService = Depends(get_neo4j_service),
) -> ActivityListResponse:
    """
    Get all activities for an account.

    Returns a list of all Activity nodes that have been created with a BELONGS_TO
    relationship to the Account node in neo4j, along with all properties and
    ActivityLog notes with a LOGGED relationship.

    **Parameters:**
    - `account_id` (required): The unique identifier for the account

    **Returns:**
    - `activities`: List of Activity objects with their associated logs
    - `total`: Total number of activities found

    **Example:**
    ```
    GET /api/v1/activities/?account_id=a000001
    ```
    """
    try:
        # Verify Neo4j connectivity
        await db.health_check()

        # Query to fetch activities and their logs for the account
        activities_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)
        OPTIONAL MATCH (activity)-[:LOGGED]->(log:ActivityLog)
        RETURN activity, collect(log) as logs
        ORDER BY activity.activity_id
        """

        result = await db.execute_query(activities_query, {"account_id": account_id})

        activities = []

        for record in result:
            activity_data = record.get("activity", {})
            logs_data = record.get("logs", [])

            # Process activity logs
            activity_logs = []
            for log_data in logs_data:
                if log_data:  # Skip null logs
                    # Convert Neo4j Date objects to strings
                    start_date = log_data.get("start_date")
                    end_date = log_data.get("end_date")

                    # Handle Neo4j Date objects
                    if hasattr(start_date, "iso_format"):
                        start_date = start_date.iso_format()
                    elif start_date and not isinstance(start_date, str):
                        start_date = str(start_date)

                    if hasattr(end_date, "iso_format"):
                        end_date = end_date.iso_format()
                    elif end_date and not isinstance(end_date, str):
                        end_date = str(end_date)

                    activity_log = ActivityLog(
                        id=log_data.get("activity_log_id"),
                        account_id=account_id,
                        start_date=start_date,
                        end_date=end_date,
                        description=log_data.get("description"),
                        evidence=None,  # Evidence parsing can be added later
                    )
                    activity_logs.append(activity_log)

            # Create activity object
            if activity_data:
                activity = Activity(
                    id=activity_data.get("activity_id", ""),
                    account_id=account_id,
                    activity_name=activity_data.get("activity_name", ""),
                    activity_description=activity_data.get("activity_description", ""),
                    expected_impact=activity_data.get("expected_impact", ""),
                    internal=activity_data.get("internal", False),
                    known_activity=activity_data.get("known_activity", False),
                    logs=activity_logs,
                )
                activities.append(activity)

        return ActivityListResponse(
            activities=activities,
            total=len(activities),
        )

    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Database service unavailable. Please try again later.",
            ) from e
        raise HTTPException(
            status_code=500, detail=f"Error fetching activities: {e!s}"
        ) from e


@router.post("/", response_model=SuccessResponse)
async def create_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new activity.

    Creates an Activity node in neo4j. All new nodes will have a BELONGS_TO
    relationship to the Account node.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `activity_name` (optional): The name of the activity
    - `activity_description` (required): A description of the activity
    - `expected_impact` (optional): Expected impact of the activity
    - `internal` (optional): Boolean indicating if activity is internal (default: false)
    - `known_activity` (optional): Boolean indicating if activity is known (default: false)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains the generated activity ID

    **Example:**
    ```json
    POST /api/v1/activities/
    {
        "account_id": "a000001",
        "activity_name": "Q4 Product Launch",
        "activity_description": "Launch new product campaign",
        "expected_impact": "Increase brand awareness and sales",
        "internal": true,
        "known_activity": false
    }
    ```
    """
    try:
        # Validate required fields
        if not request.activity_description:
            raise HTTPException(
                status_code=400,
                detail="activity_description is required for create action",
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for create action"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # First, check if the Account node exists
        account_check_query = """
        MATCH (a:Account {account_id: $account_id})
        RETURN a
        """
        account_result = await db.execute_query(
            account_check_query, {"account_id": request.account_id}
        )

        if not account_result:
            raise HTTPException(
                status_code=404,
                detail=f"Account with account_id '{request.account_id}' not found",
            )

        # Generate unique ID
        activity_id = str(uuid.uuid4())

        # Create Activity node and relationship to Account
        create_activity_query = """
        MATCH (account:Account {account_id: $account_id})
        CREATE (activity:Activity {
            activity_id: $activity_id,
            activity_name: $activity_name,
            activity_description: $activity_description,
            expected_impact: $expected_impact,
            internal: $internal,
            known_activity: $known_activity
        })
        CREATE (activity)-[:BELONGS_TO]->(account)
        RETURN activity
        """

        parameters = {
            "account_id": request.account_id,
            "activity_id": activity_id,
            "activity_name": request.activity_name or "",
            "activity_description": request.activity_description,
            "expected_impact": request.expected_impact or "",
            "internal": request.internal if request.internal is not None else False,
            "known_activity": (
                request.known_activity if request.known_activity is not None else False
            ),
        }

        result = await db.execute_write_query(create_activity_query, parameters)

        return SuccessResponse(
            success=True,
            message="Activity created successfully",
            data={"id": activity_id, "summary": result},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating activity: {e!s}"
        ) from e


@router.put("/", response_model=SuccessResponse)
async def update_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing activity.

    Edit an Activity node in neo4j.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity to update
    - `account_id` (required): The unique identifier for the account (ensures activity belongs to this account)
    - `activity_name` (optional): Updated name of the activity
    - `activity_description` (optional): Updated description of the activity
    - `expected_impact` (optional): Updated expected impact of the activity
    - `internal` (optional): Updated boolean indicating if activity is internal
    - `known_activity` (optional): Updated boolean indicating if activity is known

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains summary of the update operation

    **Example:**
    ```json
    PUT /api/v1/activities/
    {
        "activity_id": "ccc333",
        "account_id": "a000001",
        "activity_name": "Holiday Email Campaign",
        "activity_description": "Updated promotional email campaign",
        "expected_impact": "Enhanced customer engagement and retention",
        "internal": true
    }
    ```
    """
    try:
        if not request.activity_id:
            raise HTTPException(
                status_code=400, detail="activity_id is required for update operation"
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for update operation"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the Activity node exists and belongs to the specified account
        check_activity_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        RETURN activity
        """
        activity_result = await db.execute_query(
            check_activity_query,
            {"activity_id": request.activity_id, "account_id": request.account_id},
        )

        if not activity_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity with id '{request.activity_id}' not found for account '{request.account_id}'",
            )

        # Build update query dynamically based on provided fields
        update_fields = []
        parameters: dict[str, Any] = {
            "activity_id": request.activity_id,
            "account_id": request.account_id,
        }

        if request.activity_name is not None:
            update_fields.append("activity.activity_name = $activity_name")
            parameters["activity_name"] = request.activity_name

        if request.activity_description is not None:
            update_fields.append(
                "activity.activity_description = $activity_description"
            )
            parameters["activity_description"] = request.activity_description

        if request.expected_impact is not None:
            update_fields.append("activity.expected_impact = $expected_impact")
            parameters["expected_impact"] = request.expected_impact

        if request.internal is not None:
            update_fields.append("activity.internal = $internal")
            parameters["internal"] = request.internal

        if request.known_activity is not None:
            update_fields.append("activity.known_activity = $known_activity")
            parameters["known_activity"] = request.known_activity

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Execute update query with account validation
        update_query = f"""
        MATCH (account:Account {{account_id: $account_id}})<-[:BELONGS_TO]-(activity:Activity {{activity_id: $activity_id}})
        SET {", ".join(update_fields)}
        RETURN activity
        """

        result = await db.execute_write_query(update_query, parameters)

        return SuccessResponse(
            success=True,
            data={"summary": result},
            message="Activity updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating activity: {e!s}"
        ) from e


@router.delete("/", response_model=SuccessResponse)
async def delete_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an activity and all associated activity logs.

    Delete an Activity node in neo4j along with its relationships and any ActivityLog
    nodes that have a LOGGED relationship with this activity.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity to delete
    - `account_id` (required): The unique identifier for the account (ensures activity belongs to this account)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains summary of the delete operation including activity logs deleted

    **Example:**
    ```json
    DELETE /api/v1/activities/
    {
        "activity_id": "ccc333",
        "account_id": "a000001"
    }
    ```
    """
    try:
        if not request.activity_id:
            raise HTTPException(
                status_code=400, detail="activity_id is required for delete operation"
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for delete operation"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the Activity node exists and belongs to the specified account
        check_activity_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        RETURN activity
        """
        activity_result = await db.execute_query(
            check_activity_query,
            {"activity_id": request.activity_id, "account_id": request.account_id},
        )

        if not activity_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity with activity_id '{request.activity_id}' not found for account '{request.account_id}'",
            )

        # First, delete all ActivityLog nodes that have LOGGED relationship with this activity
        delete_logs_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})-[:LOGGED]->(log:ActivityLog)
        DETACH DELETE log
        """

        logs_summary = await db.execute_write_query(
            delete_logs_query,
            {"activity_id": request.activity_id, "account_id": request.account_id},
        )
        logs_deleted = logs_summary.get("nodes_deleted", 0) if logs_summary else 0

        # Delete the Activity node and all its relationships
        delete_activity_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        DETACH DELETE activity
        """

        result = await db.execute_write_query(
            delete_activity_query,
            {"activity_id": request.activity_id, "account_id": request.account_id},
        )

        return SuccessResponse(
            success=True,
            message="Activity and associated logs deleted successfully",
            data={
                "summary": result,
                "activity_logs_deleted": logs_deleted,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting activity: {e!s}"
        ) from e


# Activity Log endpoints
@router.post("/logs", response_model=SuccessResponse)
async def create_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new activity log.

    Creates an ActivityLog node in neo4j with a LOGGED relationship to the
    provided Activity node and a BELONGS_TO relationship to the Account node.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity to log
    - `account_id` (required): The unique identifier for the account
    - `start_date` (optional): Start date of the activity log
    - `end_date` (optional): End date of the activity log
    - `description` (optional): Description of the activity log entry

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains the generated activity log ID

    **Example:**
    ```json
    POST /api/v1/activities/logs
    {
        "activity_id": "ccc333",
        "account_id": "a000001",
        "start_date": "2025-01-15",
        "end_date": "2025-01-16",
        "description": "Email campaign execution with improved targeting"
    }
    ```
    """
    try:
        if not request.activity_id:
            raise HTTPException(
                status_code=400,
                detail="activity_id is required for create operation",
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for create operation"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Verify that the Activity node exists
        activity_check_query = """
        MATCH (activity:Activity {activity_id: $activity_id})
        RETURN activity
        """
        activity_result = await db.execute_query(
            activity_check_query, {"activity_id": request.activity_id}
        )

        if not activity_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity with id '{request.activity_id}' not found",
            )

        # Generate unique ID for the activity log
        activity_log_id = str(uuid.uuid4())

        # Create ActivityLog node with relationships
        create_log_query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (activity:Activity {activity_id: $activity_id})
        CREATE (log:ActivityLog {
            activity_log_id: $activity_log_id,
            start_date: $start_date,
            end_date: $end_date,
            description: $description
        })
        CREATE (activity)-[:LOGGED]->(log)
        CREATE (log)-[:BELONGS_TO]->(account)
        RETURN log
        """

        parameters = {
            "account_id": request.account_id,
            "activity_id": request.activity_id,
            "activity_log_id": activity_log_id,
            "start_date": request.start_date or "",
            "end_date": request.end_date or "",
            "description": request.description or "",
        }

        result = await db.execute_write_query(create_log_query, parameters)

        return SuccessResponse(
            success=True,
            data={"activity_log_id": activity_log_id, "summary": result},
            message="Activity log created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating activity log: {e!s}"
        ) from e


@router.put("/logs", response_model=SuccessResponse)
async def update_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing activity log.

    Edit an ActivityLog node in neo4j.

    **Parameters (in request body):**
    - `activity_log_id` (required): The unique identifier of the activity log to update
    - `activity_id` (required): The unique identifier of the activity (ensures log belongs to this activity)
    - `account_id` (required): The unique identifier for the account (ensures activity belongs to this account)
    - `start_date` (optional): Updated start date of the activity log
    - `end_date` (optional): Updated end date of the activity log
    - `description` (optional): Updated description of the activity log entry

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains summary of the update operation

    **Example:**
    ```json
    PUT /api/v1/activities/logs
    {
        "activity_log_id": "bzbzbz",
        "activity_id": "ccc333",
        "account_id": "a000001",
        "start_date": "2025-01-08",
        "end_date": "2025-01-09",
        "description": "Updated email campaign with A/B testing results"
    }
    ```
    """
    try:
        if not request.activity_log_id:
            raise HTTPException(
                status_code=400,
                detail="activity_log_id is required for update operation",
            )
        if not request.activity_id:
            raise HTTPException(
                status_code=400,
                detail="activity_id is required for update operation",
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400,
                detail="account_id is required for update operation",
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the ActivityLog node exists and belongs to the specified activity and account
        check_log_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (activity)-[:LOGGED]->(log:ActivityLog {activity_log_id: $activity_log_id})
        RETURN log
        """
        log_result = await db.execute_query(
            check_log_query,
            {
                "activity_log_id": request.activity_log_id,
                "activity_id": request.activity_id,
                "account_id": request.account_id,
            },
        )

        if not log_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity log with activity_log_id '{request.activity_log_id}' not found for activity '{request.activity_id}' and account '{request.account_id}'",
            )

        # Build update query dynamically based on provided fields
        update_fields = []
        parameters: dict[str, Any] = {
            "activity_log_id": request.activity_log_id,
            "activity_id": request.activity_id,
            "account_id": request.account_id,
        }

        if request.start_date is not None:
            update_fields.append("log.start_date = $start_date")
            parameters["start_date"] = request.start_date

        if request.end_date is not None:
            update_fields.append("log.end_date = $end_date")
            parameters["end_date"] = request.end_date

        if request.description is not None:
            update_fields.append("log.description = $description")
            parameters["description"] = request.description

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Execute update query with account and activity validation
        update_query = f"""
        MATCH (account:Account {{account_id: $account_id}})<-[:BELONGS_TO]-(activity:Activity {{activity_id: $activity_id}})
        MATCH (activity)-[:LOGGED]->(log:ActivityLog {{activity_log_id: $activity_log_id}})
        SET {", ".join(update_fields)}
        RETURN log
        """

        result = await db.execute_write_query(update_query, parameters)

        return SuccessResponse(
            success=True,
            data={"summary": result},
            message="Activity log updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating activity log: {e!s}"
        ) from e


@router.delete("/logs", response_model=SuccessResponse)
async def delete_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an activity log.

    Delete an ActivityLog node in neo4j.

    **Parameters (in request body):**
    - `activity_log_id` (required): The unique identifier of the activity log to delete
    - `activity_id` (required): The unique identifier of the activity (ensures log belongs to this activity)
    - `account_id` (required): The unique identifier for the account (ensures activity belongs to this account)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains summary of the delete operation

    **Example:**
    ```json
    DELETE /api/v1/activities/logs
    {
        "activity_log_id": "bzbzbz",
        "activity_id": "ccc333",
        "account_id": "a000001"
    }
    ```
    """
    try:
        if not request.activity_log_id:
            raise HTTPException(
                status_code=400,
                detail="activity_log_id is required for delete operation",
            )
        if not request.activity_id:
            raise HTTPException(
                status_code=400,
                detail="activity_id is required for delete operation",
            )
        if not request.account_id:
            raise HTTPException(
                status_code=400,
                detail="account_id is required for delete operation",
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the ActivityLog node exists and belongs to the specified activity and account
        check_log_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (activity)-[:LOGGED]->(log:ActivityLog {activity_log_id: $activity_log_id})
        RETURN log
        """
        log_result = await db.execute_query(
            check_log_query,
            {
                "activity_log_id": request.activity_log_id,
                "activity_id": request.activity_id,
                "account_id": request.account_id,
            },
        )

        if not log_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity log with activity_log_id '{request.activity_log_id}' not found for activity '{request.activity_id}' and account '{request.account_id}'",
            )

        # Delete the ActivityLog node and all its relationships with account and activity validation
        delete_log_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (activity)-[:LOGGED]->(log:ActivityLog {activity_log_id: $activity_log_id})
        DETACH DELETE log
        """

        result = await db.execute_write_query(
            delete_log_query,
            {
                "activity_log_id": request.activity_log_id,
                "activity_id": request.activity_id,
                "account_id": request.account_id,
            },
        )

        return SuccessResponse(
            success=True,
            data={"summary": result},
            message="Activity log deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting activity log: {e!s}"
        ) from e


# Helper functions for sync_holiday_activity_logs
async def _validate_account_and_get_regions(
    db: Neo4jService, account_id: str
) -> dict[str, Any]:
    """Validate account exists and get its regions."""
    account_query = """
    MATCH (acc:Account {account_id: $account_id})
    RETURN acc.region as regions
    """
    account_result = await db.execute_query(account_query, {"account_id": account_id})
    if not account_result:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    regions = account_result[0].get("regions", [])
    if not regions:
        return {"regions": [], "has_regions": False}

    # Verify act_00 exists
    activity_query = """
    MATCH (a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    RETURN a
    """
    activity_result = await db.execute_query(activity_query, {"account_id": account_id})
    if not activity_result:
        raise HTTPException(
            status_code=404,
            detail=f"Activity act_00 not found for account {account_id}",
        )

    return {"regions": regions, "has_regions": True}


async def _fetch_existing_activity_logs(
    db: Neo4jService, account_id: str
) -> tuple[dict[tuple, str], set[str]]:
    """Fetch existing logs and identify protected ones."""
    existing_logs_query = """
    MATCH (a:Activity {activity_id: "act_00"})-[:BELONGS_TO]->(acc:Account {account_id: $account_id})
    MATCH (a)-[:LOGGED]->(al:ActivityLog)
    OPTIONAL MATCH (al)-[r:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(m:Metric)
    RETURN al.activity_log_id as log_id,
           al.description as description,
           al.start_date as start_date,
           al.end_date as end_date,
           count(m) > 0 as has_metric_relationship
    """
    existing_logs = await db.execute_query(
        existing_logs_query, {"account_id": account_id}
    )

    existing_holidays = {}  # (description, start_date, end_date) -> log_id
    protected_logs = set()  # log_ids that have metric relationships

    for log in existing_logs:
        key = (log["description"], log["start_date"], log["end_date"])
        existing_holidays[key] = log["log_id"]
        if log["has_metric_relationship"]:
            protected_logs.add(log["log_id"])

    logger.info(
        f"Found {len(existing_logs)} existing logs, {len(protected_logs)} protected"
    )
    return existing_holidays, protected_logs


async def _fetch_bigquery_holidays(
    bigquery: BigQueryService, project_id: str, regions: list[str]
) -> list[dict[str, Any]]:
    """Fetch holidays from BigQuery for given regions."""
    try:
        if not bigquery.health_check():
            logger.error("BigQuery service is not healthy")
            raise HTTPException(
                status_code=503,
                detail="BigQuery service is not available. Please try again later.",
            )

        holidays = bigquery.query_holiday_activities(project_id, regions)
        logger.info(f"BigQuery returned {len(holidays)} holidays for regions {regions}")
        return holidays
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying BigQuery: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error querying holiday activities from BigQuery: {str(e)}",
        )


def _calculate_sync_operations(
    existing_holidays: dict[tuple, str],
    bigquery_holidays: list[dict[str, Any]],
    protected_logs: set[str],
    account_id: str,
) -> dict[str, Any]:
    """Calculate what operations need to be performed."""
    # Create set of BigQuery holiday keys
    bigquery_holiday_keys = {
        (holiday["description"], holiday["start_date"], holiday["end_date"])
        for holiday in bigquery_holidays
    }

    # Find holidays to create
    new_logs_data = []
    for holiday in bigquery_holidays:
        holiday_key = (
            holiday["description"],
            holiday["start_date"],
            holiday["end_date"],
        )
        if holiday_key not in existing_holidays:
            log_id = str(uuid.uuid4())
            new_logs_data.append(
                {
                    "activity_log_id": f"log_{log_id}",
                    "activity_id": "act_00",
                    "account_id": account_id,
                    "start_date": holiday["start_date"],
                    "end_date": holiday["end_date"],
                    "description": holiday["description"],
                }
            )

    # Find logs to delete
    logs_to_delete = []
    protected_from_deletion = []
    for key, log_id in existing_holidays.items():
        if key not in bigquery_holiday_keys:
            if log_id in protected_logs:
                protected_from_deletion.append(log_id)
            else:
                logs_to_delete.append(log_id)

    return {
        "to_create": new_logs_data,
        "to_delete": logs_to_delete,
        "protected": protected_from_deletion,
    }


async def _create_activity_logs_batch(
    db: Neo4jService, logs_batch: list[dict[str, Any]]
) -> int:
    """Create a batch of activity logs."""
    if not logs_batch:
        return 0

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
    CREATE (activity)-[:LOGGED]->(al)
    CREATE (al)-[:BELONGS_TO]->(account)
    RETURN count(al) as created_count
    """

    result = await db.execute_write_query(create_query, {"logs": logs_batch})
    return result.get("nodes_created", 0) if result else 0


async def _delete_activity_logs_batch(
    db: Neo4jService, log_ids_batch: list[str]
) -> int:
    """Delete a batch of activity logs."""
    if not log_ids_batch:
        return 0

    # First count deletable logs
    count_query = """
    UNWIND $log_ids AS log_id
    MATCH (al:ActivityLog {activity_log_id: log_id})
    WHERE NOT EXISTS((al)-[:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(:Metric))
    RETURN count(al) as to_delete_count
    """

    count_result = await db.execute_query(count_query, {"log_ids": log_ids_batch})
    to_delete = count_result[0]["to_delete_count"] if count_result else 0

    if to_delete == 0:
        return 0

    # Delete the logs
    delete_query = """
    UNWIND $log_ids AS log_id
    MATCH (al:ActivityLog {activity_log_id: log_id})
    WHERE NOT EXISTS((al)-[:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(:Metric))
    DETACH DELETE al
    """

    delete_result = await db.execute_write_query(
        delete_query, {"log_ids": log_ids_batch}
    )
    return delete_result.get("nodes_deleted", 0) if delete_result else 0


async def _execute_sync_operations(
    db: Neo4jService, operations: dict[str, Any]
) -> dict[str, Any]:
    """Execute sync operations with batching."""
    BATCH_SIZE = 50
    results = {
        "created": 0,
        "deleted": 0,
        "errors": [],
    }

    # Create logs in batches
    logs_to_create = operations["to_create"]
    for i in range(0, len(logs_to_create), BATCH_SIZE):
        batch = logs_to_create[i : i + BATCH_SIZE]
        try:
            created = await _create_activity_logs_batch(db, batch)
            results["created"] += created
        except Exception as e:
            error_msg = f"Create batch {i // BATCH_SIZE + 1} failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

    # Delete logs in batches
    logs_to_delete = operations["to_delete"]
    for i in range(0, len(logs_to_delete), BATCH_SIZE):
        batch = logs_to_delete[i : i + BATCH_SIZE]
        try:
            deleted = await _delete_activity_logs_batch(db, batch)
            results["deleted"] += deleted
        except Exception as e:
            error_msg = f"Delete batch {i // BATCH_SIZE + 1} failed: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

    return results


@router.post("/logs/sync", response_model=SuccessResponse)
async def sync_holiday_activity_logs(
    account_id: str = Query(
        ..., description="Account ID to sync holiday activities for"
    ),
    db: Neo4jService = Depends(get_neo4j_service),
    bigquery: BigQueryService = Depends(get_bigquery_service),
) -> SuccessResponse:
    """
    Sync holiday activity logs from BigQuery for an account.

    This endpoint:
    1. Creates ActivityLog nodes for holidays that exist in BigQuery but not in Neo4j
    2. Deletes ActivityLog nodes that exist in Neo4j but not in BigQuery
    3. Protects ActivityLog nodes that have INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED relationships to Metric nodes

    **Parameters (query parameter):**
    - `account_id` (required): The account ID to sync holiday activities for

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message with counts of logs created and deleted
    - `data`: Contains details about the sync operation

    **Example:**
    ```
    POST /api/v1/activities/logs/sync?account_id=acc_123456
    ```
    """
    try:
        # Step 1: Get project ID
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if not project_id:
            raise HTTPException(
                status_code=503,
                detail="BigQuery configuration missing. Check GOOGLE_CLOUD_PROJECT_ID",
            )

        # Step 2: Validate account and get regions
        account_data = await _validate_account_and_get_regions(db, account_id)
        if not account_data["has_regions"]:
            return SuccessResponse(
                success=True,
                message="No regions configured for account",
                data={
                    "account_id": account_id,
                    "regions": [],
                    "total_holidays_in_bigquery": 0,
                    "existing_logs_before_sync": 0,
                    "new_logs_created": 0,
                    "logs_deleted": 0,
                    "logs_protected_from_deletion": 0,
                },
            )

        # Step 3: Fetch existing logs
        existing_holidays, protected_logs = await _fetch_existing_activity_logs(
            db, account_id
        )

        # Step 4: Fetch holidays from BigQuery
        holidays = await _fetch_bigquery_holidays(
            bigquery, project_id, account_data["regions"]
        )

        # Step 5: Calculate sync operations
        operations = _calculate_sync_operations(
            existing_holidays, holidays, protected_logs, account_id
        )

        # Step 6: Execute sync operations
        sync_results = await _execute_sync_operations(db, operations)

        # Step 7: Build response
        return SuccessResponse(
            success=True,
            message=f"Synced holiday activities. Created {sync_results['created']} new logs, deleted {sync_results['deleted']} outdated logs.",
            data={
                "account_id": account_id,
                "regions": account_data["regions"],
                "total_holidays_in_bigquery": len(holidays),
                "existing_logs_before_sync": len(existing_holidays),
                "new_logs_created": sync_results["created"],
                "logs_deleted": sync_results["deleted"],
                "logs_protected_from_deletion": len(operations["protected"]),
                "errors": sync_results.get("errors", []),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed for account {account_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error syncing holiday activity logs: {str(e)}"
        ) from e


# Helper endpoint for testing - Create Account nodes
@router.post("/test/create-account", response_model=SuccessResponse)
async def create_test_account(
    account_id: str = Query(..., description="Account ID to create"),
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Create a test Account node for testing activity operations.
    This is a helper endpoint for development and testing.

    **Parameters (query parameter):**
    - `account_id` (required): The unique identifier for the account to create

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains the created account ID

    **Example:**
    ```
    POST /api/v1/activities/test/create-account?account_id=a000001
    ```
    """
    try:
        # Verify Neo4j connectivity
        await db.health_check()

        # Check if account already exists
        check_query = """
        MATCH (a:Account {account_id: $account_id})
        RETURN a
        """
        existing = await db.execute_query(check_query, {"account_id": account_id})

        if existing:
            return SuccessResponse(
                success=True,
                message=f"Account {account_id} already exists",
                data={"account_id": account_id},
            )

        # Create new account
        create_query = """
        CREATE (a:Account {
            account_id: $account_id,
            id: $id,
            name: $name
        })
        RETURN a
        """

        result = await db.execute_write_query(
            create_query,
            {
                "account_id": account_id,
                "id": str(uuid.uuid4()),
                "name": f"Test Account {account_id}",
            },
        )

        return SuccessResponse(
            success=True,
            message=f"Test account {account_id} created successfully",
            data={"account_id": account_id, "summary": result},
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating test account: {e!s}"
        ) from e
