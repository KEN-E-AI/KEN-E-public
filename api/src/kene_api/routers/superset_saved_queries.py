"""Superset saved queries router for CRUD operations on Superset saved queries."""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..superset import SupersetClient, SupersetClientError, get_superset_client
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    SavedQueryRequest,
    SavedQueryResponse,
    SavedQueryListResponse,
    QueryExecutionResponse,
    SuccessResponse,
)

router = APIRouter(tags=["superset-saved-queries"])

# Logger
logger = logging.getLogger(__name__)

# Constants
SUPERSET_UNAVAILABLE_MESSAGE = "Superset service unavailable. Please try again later."
INTERNAL_SERVER_ERROR_MESSAGE = "Internal server error"


@router.get("/by-schema/{account_id}", response_model=SavedQueryListResponse)
async def get_saved_queries_by_account(
    account_id: str,
    superset: SupersetClient = Depends(get_superset_client),
) -> SavedQueryListResponse:
    """
    Get all saved queries where the schema name matches the pattern '<account_id>_output'.

    This endpoint retrieves all saved queries in Superset that belong to a specific account
    based on the schema naming convention.
    """
    try:
        # Check Superset connectivity
        is_healthy = await superset.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=SUPERSET_UNAVAILABLE_MESSAGE)

        # Get saved queries matching the account pattern
        schema_pattern = f"{account_id}_output"
        saved_queries_data = await superset.get_saved_queries_by_schema_pattern(
            schema_pattern
        )

        # Convert to response model
        saved_queries = []
        for query_data in saved_queries_data:
            saved_query = SavedQueryResponse(
                id=query_data.get("id", 0),
                label=query_data.get("label", ""),
                description=query_data.get("description"),
                database_id=query_data.get("db_id", 0),  # Superset returns 'db_id'
                schema_name=query_data.get("schema", ""),
                sql=query_data.get("sql", ""),
                created_on=query_data.get("created_on"),
                changed_on=query_data.get("changed_on"),
            )
            saved_queries.append(saved_query)

        logger.info(
            f"Retrieved {len(saved_queries)} saved queries for account {account_id}"
        )

        return SavedQueryListResponse(
            saved_queries=saved_queries, total=len(saved_queries)
        )

    except SupersetClientError as e:
        logger.error(
            f"Superset error while getting saved queries for account {account_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error while getting saved queries for account {account_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_MESSAGE)


@router.post("/", response_model=SavedQueryResponse)
async def create_saved_query(
    request: SavedQueryRequest,
    superset: SupersetClient = Depends(get_superset_client),
) -> SavedQueryResponse:
    """
    Create a new saved query in Superset.

    Creates a new saved query with the provided SQL, schema, and metadata.
    """
    try:
        # Check Superset connectivity
        is_healthy = await superset.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=SUPERSET_UNAVAILABLE_MESSAGE)

        # Prepare query data for Superset
        query_data = {
            "label": request.label,
            "description": request.description,
            "db_id": request.database_id,  # Superset expects 'db_id' not 'database_id'
            "schema": request.schema_name,  # Convert back to 'schema' for Superset API
            "sql": request.sql,
        }

        # Create the saved query
        created_query = await superset.create_saved_query(query_data)

        logger.info(
            f"Created saved query '{request.label}' with ID {created_query.get('id')}"
        )

        return SavedQueryResponse(
            id=created_query.get("id", 0),
            label=created_query.get("label", ""),
            description=created_query.get("description"),
            database_id=created_query.get("db_id", 0),  # Superset returns 'db_id'
            schema_name=created_query.get("schema", ""),
            sql=created_query.get("sql", ""),
            created_on=created_query.get("created_on"),
            changed_on=created_query.get("changed_on"),
        )

    except SupersetClientError as e:
        logger.error(
            f"Superset error while creating saved query '{request.label}': {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error while creating saved query '{request.label}': {e}"
        )
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_MESSAGE)


@router.put("/{query_id}", response_model=SavedQueryResponse)
async def update_saved_query(
    query_id: int,
    request: SavedQueryRequest,
    superset: SupersetClient = Depends(get_superset_client),
) -> SavedQueryResponse:
    """
    Update an existing saved query in Superset.

    Updates the saved query with the provided ID using the new data.
    """
    try:
        # Check Superset connectivity
        is_healthy = await superset.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=SUPERSET_UNAVAILABLE_MESSAGE)

        # Prepare query data for Superset
        query_data = {
            "label": request.label,
            "description": request.description,
            "db_id": request.database_id,  # Superset expects 'db_id' not 'database_id'
            "schema": request.schema_name,  # Convert back to 'schema' for Superset API
            "sql": request.sql,
        }

        # Update the saved query
        updated_query = await superset.update_saved_query(query_id, query_data)

        logger.info(f"Updated saved query {query_id} with label '{request.label}'")

        return SavedQueryResponse(
            id=updated_query.get("id", query_id),
            label=updated_query.get("label", ""),
            description=updated_query.get("description"),
            database_id=updated_query.get("db_id", 0),  # Superset returns 'db_id'
            schema_name=updated_query.get("schema", ""),
            sql=updated_query.get("sql", ""),
            created_on=updated_query.get("created_on"),
            changed_on=updated_query.get("changed_on"),
        )

    except SupersetClientError as e:
        logger.error(f"Superset error while updating saved query {query_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error while updating saved query {query_id}: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_MESSAGE)


@router.delete("/{query_id}", response_model=SuccessResponse)
async def delete_saved_query(
    query_id: int,
    superset: SupersetClient = Depends(get_superset_client),
) -> SuccessResponse:
    """
    Delete a saved query from Superset.

    Permanently removes the saved query with the specified ID.
    """
    try:
        # Check Superset connectivity
        is_healthy = await superset.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=SUPERSET_UNAVAILABLE_MESSAGE)

        # Delete the saved query
        success = await superset.delete_saved_query(query_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Saved query {query_id} not found"
            )

        logger.info(f"Deleted saved query {query_id}")

        return SuccessResponse(
            success=True, message=f"Saved query {query_id} deleted successfully"
        )

    except SupersetClientError as e:
        logger.error(f"Superset error while deleting saved query {query_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error while deleting saved query {query_id}: {e}")
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_MESSAGE)


@router.post("/execute/{query_label}", response_model=QueryExecutionResponse)
async def execute_saved_query(
    query_label: str,
    superset: SupersetClient = Depends(get_superset_client),
) -> QueryExecutionResponse:
    """
    Execute a saved query and return the results.

    Finds the saved query by label and executes it, returning the query results.
    """
    try:
        # Check Superset connectivity
        is_healthy = await superset.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=SUPERSET_UNAVAILABLE_MESSAGE)

        # Execute the saved query
        execution_result = await superset.execute_saved_query(query_label)

        logger.info(f"Executed saved query '{query_label}'")

        return QueryExecutionResponse(
            query_id=execution_result.get("query_id"),
            status=execution_result.get("status", "unknown"),
            data=execution_result.get("data"),
            columns=execution_result.get("columns"),
            error=execution_result.get("error"),
            query=execution_result.get("query"),
        )

    except SupersetClientError as e:
        logger.error(f"Superset error while executing saved query '{query_label}': {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error while executing saved query '{query_label}': {e}"
        )
        raise HTTPException(status_code=500, detail=INTERNAL_SERVER_ERROR_MESSAGE)


@router.get("/execute/{query_label}", response_model=QueryExecutionResponse)
async def execute_saved_query_get(
    query_label: str,
    superset: SupersetClient = Depends(get_superset_client),
) -> QueryExecutionResponse:
    """
    Execute a saved query and return the results (GET method).

    Alternative GET endpoint for executing saved queries by label.
    """
    return await execute_saved_query(query_label, superset)
