"""Activities router for CRUD operations on activity and activity log entities."""

import uuid
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    ActiveConfidenceLevel,
    ActiveEvidence,
    Activity,
    ActivityListResponse,
    ActivityLog,
    ActivityLogRequest,
    ActivityRequest,
    Evidence,
    InfluenceEvidence,
    SuccessResponse,
)

router = APIRouter(tags=["activities"])


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
                    activity_log = ActivityLog(
                        id=log_data.get("activity_log_id"),
                        account_id=account_id,
                        start_date=log_data.get("start_date"),
                        end_date=log_data.get("end_date"),
                        description=log_data.get("description"),
                        evidence=None,  # Evidence parsing can be added later
                    )
                    activity_logs.append(activity_log)

            # Create activity object
            if activity_data:
                activity = Activity(
                    id=activity_data.get("activity_id", ""),
                    account_id=account_id,
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
            )
        raise HTTPException(
            status_code=500, detail=f"Error fetching activities: {str(e)}"
        )


@router.post("/", response_model=SuccessResponse)
async def create_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new activity.

    Creates an Activity node in neo4j. All new nodes will have a BELONGS_TO
    relationship to the Account node.
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
            status_code=500, detail=f"Error creating activity: {str(e)}"
        )


@router.put("/", response_model=SuccessResponse)
async def update_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing activity.

    Edit an Activity node in neo4j.
    """
    try:
        if not request.id:
            raise HTTPException(
                status_code=400, detail="id is required for update operation"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the Activity node exists
        check_activity_query = """
        MATCH (activity:Activity {activity_id: $id})
        RETURN activity
        """
        activity_result = await db.execute_query(
            check_activity_query, {"id": request.id}
        )

        if not activity_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity with id '{request.id}' not found",
            )

        # Build update query dynamically based on provided fields
        update_fields = []
        parameters: Dict[str, Any] = {"id": request.id}

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

        # Execute update query
        update_query = f"""
        MATCH (activity:Activity {{activity_id: $id}})
        SET {', '.join(update_fields)}
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
            status_code=500, detail=f"Error updating activity: {str(e)}"
        )


@router.delete("/", response_model=SuccessResponse)
async def delete_activity(
    request: ActivityRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an activity.

    Delete an Activity node in neo4j along with its relationships.
    """
    try:
        if not request.id:
            raise HTTPException(
                status_code=400, detail="id is required for delete operation"
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the Activity node exists
        check_activity_query = """
        MATCH (activity:Activity {activity_id: $id})
        RETURN activity
        """
        activity_result = await db.execute_query(
            check_activity_query, {"id": request.id}
        )

        if not activity_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity with id '{request.id}' not found",
            )

        # Delete the Activity node and all its relationships
        delete_activity_query = """
        MATCH (activity:Activity {activity_id: $id})
        DETACH DELETE activity
        """

        result = await db.execute_write_query(delete_activity_query, {"id": request.id})

        return SuccessResponse(
            success=True,
            message="Activity deleted successfully",
            data={"summary": result},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting activity: {str(e)}"
        )


# Activity Log endpoints
@router.post("/logs", response_model=SuccessResponse)
async def create_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new activity log.

    Creates an ActivityLog node in neo4j with a LOGGED relationship to the
    provided Activity node and a BELONGS_TO relationship to the Account node.
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
            status_code=500, detail=f"Error creating activity log: {str(e)}"
        )


@router.put("/logs", response_model=SuccessResponse)
async def update_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing activity log.

    Edit an ActivityLog node in neo4j.
    """
    try:
        if not request.id:
            raise HTTPException(
                status_code=400,
                detail="id is required for update operation",
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the ActivityLog node exists
        check_log_query = """
        MATCH (log:ActivityLog {activity_log_id: $id})
        RETURN log
        """
        log_result = await db.execute_query(check_log_query, {"id": request.id})

        if not log_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity log with id '{request.id}' not found",
            )

        # Build update query dynamically based on provided fields
        update_fields = []
        parameters: Dict[str, Any] = {"id": request.id}

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

        # Execute update query
        update_query = f"""
        MATCH (log:ActivityLog {{activity_log_id: $id}})
        SET {', '.join(update_fields)}
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
            status_code=500, detail=f"Error updating activity log: {str(e)}"
        )


@router.delete("/logs", response_model=SuccessResponse)
async def delete_activity_log(
    request: ActivityLogRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an activity log.

    Delete an ActivityLog node in neo4j.
    """
    try:
        if not request.id:
            raise HTTPException(
                status_code=400,
                detail="id is required for delete operation",
            )

        # Verify Neo4j connectivity
        await db.health_check()

        # Check if the ActivityLog node exists
        check_log_query = """
        MATCH (log:ActivityLog {activity_log_id: $id})
        RETURN log
        """
        log_result = await db.execute_query(check_log_query, {"id": request.id})

        if not log_result:
            raise HTTPException(
                status_code=404,
                detail=f"Activity log with id '{request.id}' not found",
            )

        # Delete the ActivityLog node and all its relationships
        delete_log_query = """
        MATCH (log:ActivityLog {activity_log_id: $id})
        DETACH DELETE log
        """

        result = await db.execute_write_query(delete_log_query, {"id": request.id})

        return SuccessResponse(
            success=True,
            data={"summary": result},
            message="Activity log deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting activity log: {str(e)}"
        )


# Helper endpoint for testing - Create Account nodes
@router.post("/test/create-account", response_model=SuccessResponse)
async def create_test_account(
    account_id: str = Query(..., description="Account ID to create"),
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Create a test Account node for testing activity operations.
    This is a helper endpoint for development and testing.
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
            status_code=500, detail=f"Error creating test account: {str(e)}"
        )
