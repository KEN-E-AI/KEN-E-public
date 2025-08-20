"""Intuitions router for CRUD operations on intuition relationships."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    MISSING_REQUIRED_IDS_ERROR,
    DirectionType,
    Intuition,
    IntuitionListResponse,
    IntuitionRequest,
    SuccessResponse,
)

router = APIRouter(tags=["intuitions"])

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."


async def _create_intuition_from_record(record) -> Intuition:
    """Create an Intuition object from a Neo4j record."""
    activity_data = record.get("activity") or {}
    metric_data = record.get("metric") or {}
    relationship_data = record.get("relationship") or {}

    # Parse direction from relationship properties
    direction_str = relationship_data.get("direction", "positive")
    direction = (
        DirectionType.POSITIVE
        if direction_str == "positive"
        else DirectionType.NEGATIVE
    )

    return Intuition(
        activity_id=activity_data.get("activity_id", ""),
        metric_id=metric_data.get("metric_id", ""),
        direction=direction,
    )


@router.get("/", response_model=IntuitionListResponse)
async def get_intuitions(
    account_id: str = Query(..., description=ACCOUNT_ID_DESCRIPTION),
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> IntuitionListResponse:
    """
    Get all intuitions for an account.

    Returns intuition relationships for the account.
    Fetches Activities for an account, then finds INFLUENCE_LIKELY relationships from Activity to Metric nodes.

    **Parameters (query parameter):**
    - `account_id` (required): The unique identifier for the account

    **Returns:**
    - `intuitions`: List of intuition objects showing likely influences
    - `total`: Total number of intuitions found

    **Example:**
    ```
    GET /api/v1/intuitions/?account_id=a000001
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch intuitions: Account → Activity → Metric relationships with INFLUENCE_LIKELY
        intuitions_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)
        MATCH (activity)-[intuition_rel:INFLUENCE_LIKELY]->(metric:Metric)
        RETURN activity, properties(intuition_rel) as relationship, metric
        ORDER BY activity.activity_description, metric.metric_name
        """

        # Execute intuitions query
        intuitions_result = await neo4j.execute_query(
            intuitions_query, {"account_id": account_id}
        )

        # Process intuitions
        intuitions = []
        for record in intuitions_result:
            try:
                intuition = await _create_intuition_from_record(record)
                intuitions.append(intuition)
            except Exception as e:
                # Log error but continue processing other records
                print(f"Error processing intuition record: {e}")
                continue

        return IntuitionListResponse(
            intuitions=intuitions,
            total=len(intuitions),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(status_code=500, detail=f"Error fetching intuitions: {e!s}")


@router.post("/", response_model=SuccessResponse)
async def create_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new intuition.

    Creates an intuition record linking an activity and metric with descriptive text.
    Prevents creation of duplicate relationships between the same activity and metric.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity
    - `metric_id` (required): The unique identifier of the metric
    - `account_id` (required): The unique identifier for the account (ensures both metric and activity belong to this account)
    - `direction` (optional): Direction of influence (positive or negative)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: null

    **Example:**
    ```json
    POST /api/v1/intuitions/
    {
        "activity_id": "act123",
        "metric_id": "metric456",
        "account_id": "a000001",
        "direction": "positive"
    }
    ```
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for creating intuitions"
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # First, check if the relationship already exists with account validation
        check_query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (account)<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (account)<-[:BELONGS_TO]-(metric:Metric {metric_id: $metric_id})
        MATCH (activity)-[r:INFLUENCE_LIKELY]->(metric)
        RETURN r
        """

        check_result = await neo4j.execute_query(
            check_query,
            {
                "account_id": request.account_id,
                "activity_id": request.activity_id,
                "metric_id": request.metric_id,
            },
        )

        if check_result:
            raise HTTPException(
                status_code=409,
                detail=f"Intuition relationship already exists between activity {request.activity_id} and metric {request.metric_id}",
            )

        # Neo4j query to create intuition relationship with account validation
        query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (account)<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (account)<-[:BELONGS_TO]-(metric:Metric {metric_id: $metric_id})
        CREATE (activity)-[r:INFLUENCE_LIKELY {
            direction: $direction
        }]->(metric)
        RETURN r
        """

        parameters = {
            "account_id": request.account_id,
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if the relationship was actually created
        if result.get("relationships_created", 0) == 0:
            raise HTTPException(
                status_code=404,
                detail="Activity or Metric not found for the specified account, or they don't belong to the same account",
            )

        return SuccessResponse(
            success=True, data=None, message="Intuition created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle database connection issues specifically
        if (
            "Database connection failed" in str(e)
            or "Neo4j" in str(e)
            or "connect" in str(e).lower()
        ):
            raise HTTPException(status_code=500, detail="Database error") from e
        raise HTTPException(status_code=500, detail=f"Error creating intuition: {e!s}")


@router.put("/", response_model=SuccessResponse)
async def update_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing intuition.

    Updates intuition properties in neo4j.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity
    - `metric_id` (required): The unique identifier of the metric
    - `account_id` (required): The unique identifier for the account (ensures both metric and activity belong to this account)
    - `direction` (optional): Updated direction of influence (positive or negative)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: null

    **Example:**
    ```json
    PUT /api/v1/intuitions/
    {
        "activity_id": "act123",
        "metric_id": "metric456",
        "account_id": "a000001",
        "direction": "negative"
    }
    ```
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for updating intuitions"
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Neo4j query to update intuition relationship with account validation
        query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (account)<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (account)<-[:BELONGS_TO]-(metric:Metric {metric_id: $metric_id})
        MATCH (activity)-[r:INFLUENCE_LIKELY]->(metric)
        SET r.direction = $direction
        RETURN r
        """

        parameters = {
            "account_id": request.account_id,
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if any properties were actually set (meaning the relationship was found)
        if result.get("properties_set", 0) == 0:
            raise HTTPException(
                status_code=404,
                detail="Intuition relationship not found for the specified account, or the Activity and Metric don't belong to the same account",
            )

        return SuccessResponse(
            success=True, data=None, message="Intuition updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle database connection issues specifically
        if (
            "Database connection failed" in str(e)
            or "Neo4j" in str(e)
            or "connect" in str(e).lower()
        ):
            raise HTTPException(status_code=500, detail="Database error") from e
        raise HTTPException(status_code=500, detail=f"Error updating intuition: {e!s}")


@router.delete("/", response_model=SuccessResponse)
async def delete_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an intuition.

    Removes an intuition record from neo4j.

    **Parameters (in request body):**
    - `activity_id` (required): The unique identifier of the activity
    - `metric_id` (required): The unique identifier of the metric
    - `account_id` (required): The unique identifier for the account (ensures both metric and activity belong to this account)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: null

    **Example:**
    ```json
    DELETE /api/v1/intuitions/
    {
        "activity_id": "act123",
        "metric_id": "metric456",
        "account_id": "a000001"
    }
    ```
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)
        if not request.account_id:
            raise HTTPException(
                status_code=400, detail="account_id is required for deleting intuitions"
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Neo4j query to delete intuition relationship with account validation
        query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (account)<-[:BELONGS_TO]-(activity:Activity {activity_id: $activity_id})
        MATCH (account)<-[:BELONGS_TO]-(metric:Metric {metric_id: $metric_id})
        MATCH (activity)-[r:INFLUENCE_LIKELY]->(metric)
        DELETE r
        RETURN count(r) as deleted_count
        """

        parameters = {
            "account_id": request.account_id,
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if any relationships were actually deleted
        if result.get("relationships_deleted", 0) == 0:
            raise HTTPException(
                status_code=404,
                detail="Intuition relationship not found for the specified account, or the Activity and Metric don't belong to the same account",
            )

        return SuccessResponse(
            success=True, data=None, message="Intuition deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle database connection issues specifically
        if (
            "Database connection failed" in str(e)
            or "Neo4j" in str(e)
            or "connect" in str(e).lower()
        ):
            raise HTTPException(status_code=500, detail="Database error") from e
        raise HTTPException(status_code=500, detail=f"Error deleting intuition: {e!s}")
