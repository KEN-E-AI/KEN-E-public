"""Funnel reports router for analysis workflows and reporting operations."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    AnalysisSearchRequest,
    DirectionType,
    Insight,
    InsightSearchResponse,
)
from .search_insight_util import main as search_main

router = APIRouter(tags=["funnel-reports"])

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."


@router.post("/analysis", response_model=InsightSearchResponse)
async def run_insight_analysis(
    request: AnalysisSearchRequest,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> InsightSearchResponse:
    """
    Execute an insight analysis workflow.

    Search insights with filters using the search insight utility.
    This endpoint has been moved from the insights router and adapted for funnel analysis.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `metric_id` (required): The unique identifier for the metric to analyze
    - `direction` (required): Direction of influence ("positive" or "negative")
    - `evaluation_date_start` (required): Start date for evaluation period (YYYY-MM-DD)
    - `evaluation_date_end` (required): End date for evaluation period (YYYY-MM-DD)
    - `comparison_date_start` (required): Start date for comparison period (YYYY-MM-DD)
    - `comparison_date_end` (required): End date for comparison period (YYYY-MM-DD)

    **Returns:**
    - `insights`: List of insights from the analysis
    - `total`: Total number of insights found

    **Example:**
    ```json
    POST /api/v1/funnel-reports/analysis
    {
        "account_id": "a000001",
        "metric_id": "m001",
        "direction": "positive",
        "evaluation_date_start": "2025-01-01",
        "evaluation_date_end": "2025-01-31",
        "comparison_date_start": "2024-12-01",
        "comparison_date_end": "2024-12-31"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Convert date strings to datetime.date objects for the main function
        try:
            evaluation_start_date = datetime.strptime(
                request.evaluation_date_start, "%Y-%m-%d"
            ).date()
            evaluation_end_date = datetime.strptime(
                request.evaluation_date_end, "%Y-%m-%d"
            ).date()
            comparison_start_date = datetime.strptime(
                request.comparison_date_start, "%Y-%m-%d"
            ).date()
            comparison_end_date = datetime.strptime(
                request.comparison_date_end, "%Y-%m-%d"
            ).date()
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format. Expected YYYY-MM-DD: {str(e)}",
            )

        # Call the main function from search_insight_util without activity_id
        result = search_main(
            account_id=request.account_id,
            activity_id=None,  # Removed activity_id parameter
            evaluation_start_date=evaluation_start_date,
            evaluation_end_date=evaluation_end_date,
            comparison_start_date=comparison_start_date,
            comparison_end_date=comparison_end_date,
            input_metric_id=request.metric_id,
            input_direction=request.direction.value,
        )

        # The result is a dictionary of activities with their analysis data
        # For now, return the raw result - you may want to transform this to match your Insight model
        insights = []  # Transform result into Insight objects as needed

        return InsightSearchResponse(
            insights=insights, total=len(result) if result else 0
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error running analysis workflow: {str(e)}"
        )
