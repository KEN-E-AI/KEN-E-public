"""Intuitions router for CRUD operations on intuition relationships."""

from fastapi import APIRouter, Depends, HTTPException

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    MISSING_REQUIRED_IDS_ERROR,
    IntuitionRequest,
    SuccessResponse,
)

router = APIRouter(tags=["intuitions"])


@router.post("/", response_model=SuccessResponse)
async def create_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new intuition.

    Creates an intuition record linking an activity and metric with descriptive text.
    Prevents creation of duplicate relationships between the same activity and metric.
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)

        # First, check if the relationship already exists
        check_query = """
        MATCH (a:Activity {activity_id: $activity_id})-[r:INFLUENCE_LIKELY]->(m:Metric {metric_id: $metric_id})
        RETURN r
        """
        
        check_result = await neo4j.execute_query(check_query, {
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
        })
        
        if check_result:
            raise HTTPException(
                status_code=409, 
                detail=f"Intuition relationship already exists between activity {request.activity_id} and metric {request.metric_id}"
            )

        # Neo4j query to create intuition relationship
        query = """
        MATCH (a:Activity {activity_id: $activity_id})
        MATCH (m:Metric {metric_id: $metric_id})
        CREATE (a)-[r:INFLUENCE_LIKELY {
            direction: $direction
        }]->(m)
        RETURN r
        """

        parameters = {
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if the relationship was actually created
        if result.get("relationships_created", 0) == 0:
            raise HTTPException(status_code=404, detail="Activity or Metric not found")

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
            raise HTTPException(status_code=500, detail="Database error")
        raise HTTPException(
            status_code=500, detail=f"Error creating intuition: {str(e)}"
        )


@router.put("/", response_model=SuccessResponse)
async def update_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing intuition.

    Updates intuition properties in neo4j.
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)

        # Neo4j query to update intuition relationship
        query = """
        MATCH (a:Activity {activity_id: $activity_id})-[r:INFLUENCE_LIKELY]->(m:Metric {metric_id: $metric_id})
        SET r.direction = $direction
        RETURN r
        """

        parameters = {
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if any properties were actually set (meaning the relationship was found)
        if result.get("properties_set", 0) == 0:
            raise HTTPException(
                status_code=404, detail="Intuition relationship not found"
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
            raise HTTPException(status_code=500, detail="Database error")
        raise HTTPException(
            status_code=500, detail=f"Error updating intuition: {str(e)}"
        )


@router.delete("/", response_model=SuccessResponse)
async def delete_intuition(
    request: IntuitionRequest, neo4j: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete an intuition.

    Removes an intuition record from neo4j.
    """
    try:
        if not request.activity_id or not request.metric_id:
            raise HTTPException(status_code=400, detail=MISSING_REQUIRED_IDS_ERROR)

        # Neo4j query to delete intuition relationship
        query = """
        MATCH (a:Activity {activity_id: $activity_id})-[r:INFLUENCE_LIKELY]->(m:Metric {metric_id: $metric_id})
        DELETE r
        RETURN count(r) as deleted_count
        """

        parameters = {
            "activity_id": request.activity_id,
            "metric_id": request.metric_id,
        }

        result = await neo4j.execute_write_query(query, parameters)

        # Check if any relationships were actually deleted
        if result.get("relationships_deleted", 0) == 0:
            raise HTTPException(
                status_code=404, detail="Intuition relationship not found"
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
            raise HTTPException(status_code=500, detail="Database error")
        raise HTTPException(
            status_code=500, detail=f"Error deleting intuition: {str(e)}"
        )
