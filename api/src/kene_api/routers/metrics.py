"""Metrics router for CRUD operations on metric entities."""

import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    Metric,
    MetricListResponse,
    MetricRequest,
    SuccessResponse,
)

router = APIRouter(tags=["metrics"])

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."


@router.get("/", response_model=MetricListResponse)
async def get_metrics(
    account_id: str = Query(..., description=ACCOUNT_ID_DESCRIPTION),
    db: Neo4jService = Depends(get_neo4j_service),
) -> MetricListResponse:
    """
    Get all metrics for an account.

    Returns a list of all metrics that have been created for the account,
    along with all properties. Also includes related Dataset information
    through the CALCULATED_FROM relationship.
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch metrics and their related dataset information for the account
        metrics_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(metric:Metric)
        OPTIONAL MATCH (metric)-[:CALCULATED_FROM]->(dataset:Dataset)
        RETURN metric, dataset
        ORDER BY metric.metric_name
        """

        result = await db.execute_query(metrics_query, {"account_id": account_id})

        metrics = []
        for record in result:
            metric_data = record.get("metric")
            if metric_data:
                metric = await _create_metric_from_record(record, account_id)
                metrics.append(metric)

        return MetricListResponse(metrics=metrics, total=len(metrics))

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")


def _parse_list_field(field_value: Any) -> List[Any]:
    """Parse a field that might be a string representation of a list."""
    import ast

    if isinstance(field_value, list):
        return field_value
    elif isinstance(field_value, str):
        try:
            return ast.literal_eval(field_value)
        except (ValueError, SyntaxError):
            return []
    else:
        return []


def _parse_comma_separated_field(field_value: Any) -> List[str]:
    """Parse a field that is a comma-separated string into a list of strings."""
    if isinstance(field_value, list):
        return [str(item).strip() for item in field_value]
    elif isinstance(field_value, str):
        if not field_value.strip():
            return []
        # Split by comma and strip whitespace from each item
        return [item.strip() for item in field_value.split(",") if item.strip()]
    else:
        return []


async def _create_metric_from_record(record: Dict[str, Any], account_id: str) -> Metric:
    """Create a Metric object from a database record."""
    metric_data = record.get("metric")
    dataset_data = record.get("dataset")

    if not metric_data:
        raise ValueError("No metric data found in record")

    # Parse account_components - handle string representation of list
    account_components = _parse_list_field(metric_data.get("account_components", []))

    # Parse dataset products - handle comma-separated string
    dataset_products = []
    if dataset_data:
        dataset_products = _parse_comma_separated_field(dataset_data.get("product", ""))

    return Metric(
        id=metric_data.get("metric_id"),
        account_id=account_id,
        d3_format=metric_data.get("d3_format") or "",
        verbose_name=metric_data.get("verbose_name") or "",
        expression=metric_data.get("expression") or "",
        metric_name=metric_data.get("metric_name") or "",
        account_components=account_components,
        related_dataset_id=dataset_data.get("dataset_id") if dataset_data else 0,
        related_dataset_name=dataset_data.get("dataset_name") if dataset_data else "",
        related_dataset_products=dataset_products,
        description=metric_data.get("description") or "",
    )


async def _verify_account_exists(db: Neo4jService, account_id: str) -> None:
    """Verify that the Account node exists."""
    account_check_query = """
    MATCH (account:Account {account_id: $account_id})
    RETURN account
    """
    account_result = await db.execute_query(
        account_check_query, {"account_id": account_id}
    )
    if not account_result:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")


async def _verify_dataset_exists(db: Neo4jService, dataset_id: int) -> None:
    """Verify that the Dataset node exists."""
    dataset_check_query = """
    MATCH (dataset:Dataset {dataset_id: $dataset_id})
    RETURN dataset
    """
    dataset_result = await db.execute_query(
        dataset_check_query, {"dataset_id": dataset_id}
    )
    if not dataset_result:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")


async def _create_metric_node(db: Neo4jService, request: MetricRequest) -> str:
    """Create the Metric node with BELONGS_TO relationship to Account.

    Returns:
        str: The generated metric ID for the created metric node
    """
    # Generate unique ID for the metric node
    metric_id = str(uuid.uuid4())

    # Generate metric_name if not provided
    metric_name = (
        request.metric_name or request.verbose_name or f"metric_{metric_id[:8]}"
    )

    create_metric_query = """
    MATCH (account:Account {account_id: $account_id})
    CREATE (metric:Metric {
        metric_id: $metric_id,
        account_components: $account_components,
        d3_format: $d3_format,
        description: $description,
        expression: $expression,
        metric_name: $metric_name,
        verbose_name: $verbose_name
    })
    CREATE (metric)-[:BELONGS_TO]->(account)
    RETURN metric
    """

    metric_params = {
        "account_id": request.account_id,
        "metric_id": metric_id,
        "account_components": request.account_components or [],
        "d3_format": request.d3_format or "",
        "description": request.description or "",
        "expression": request.expression or "",
        "metric_name": metric_name,
        "verbose_name": request.verbose_name or "",
    }

    metric_result = await db.execute_write_query(create_metric_query, metric_params)

    if not metric_result:
        raise HTTPException(status_code=500, detail="Failed to create metric")

    return metric_id


async def _create_dataset_relationship(
    db: Neo4jService, metric_id: str, dataset_id: int
) -> None:
    """Create CALCULATED_FROM relationship between Metric and Dataset."""
    relationship_query = """
    MATCH (metric:Metric {metric_id: $metric_id})
    MATCH (dataset:Dataset {dataset_id: $dataset_id})
    CREATE (metric)-[:CALCULATED_FROM]->(dataset)
    """
    await db.execute_write_query(
        relationship_query,
        {"metric_id": metric_id, "dataset_id": dataset_id},
    )


@router.post("/", response_model=SuccessResponse)
async def create_metric(
    request: MetricRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Create a new metric.

    Creates a new Metric node in Neo4j with a BELONGS_TO relationship to the Account node.
    Also creates a CALCULATED_FROM relationship to an existing Dataset node if related_dataset_id is provided.
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Verify Account exists
        await _verify_account_exists(db, request.account_id)

        # Verify Dataset exists if related_dataset_id is provided
        if request.related_dataset_id:
            await _verify_dataset_exists(db, request.related_dataset_id)

        # Create Metric node
        generated_metric_id = await _create_metric_node(db, request)

        # Create CALCULATED_FROM relationship to Dataset if dataset_id provided
        if request.related_dataset_id:
            await _create_dataset_relationship(
                db, generated_metric_id, request.related_dataset_id
            )

        return SuccessResponse(
            success=True,
            data={"metric_id": generated_metric_id},
            message="Metric created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating metric: {str(e)}")


@router.put("/", response_model=SuccessResponse)
async def update_metric(
    request: MetricRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Update an existing metric.

    Updates Metric node properties in Neo4j. Does not modify relationships to other nodes.
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.id:
            raise HTTPException(
                status_code=400, detail="id is required for update operation"
            )

        # Check if metric exists
        metric_check_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        RETURN metric
        """
        metric_result = await db.execute_query(metric_check_query, {"metric_id": request.id})
        if not metric_result:
            raise HTTPException(
                status_code=404, detail=f"Metric {request.id} not found"
            )

        # Build dynamic update query for provided fields
        set_clauses = []
        params: Dict[str, Any] = {"metric_id": request.id}

        if request.account_components is not None:
            set_clauses.append("metric.account_components = $account_components")
            params["account_components"] = request.account_components

        if request.d3_format is not None:
            set_clauses.append("metric.d3_format = $d3_format")
            params["d3_format"] = request.d3_format

        if request.description is not None:
            set_clauses.append("metric.description = $description")
            params["description"] = request.description

        if request.expression is not None:
            set_clauses.append("metric.expression = $expression")
            params["expression"] = request.expression

        if request.metric_name is not None:
            set_clauses.append("metric.metric_name = $metric_name")
            params["metric_name"] = request.metric_name

        if request.verbose_name is not None:
            set_clauses.append("metric.verbose_name = $verbose_name")
            params["verbose_name"] = request.verbose_name

        if not set_clauses:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Execute update query
        update_query = f"""
        MATCH (metric:Metric {{metric_id: $metric_id}})
        SET {', '.join(set_clauses)}
        RETURN metric
        """

        await db.execute_write_query(update_query, params)

        return SuccessResponse(
            success=True, data=None, message="Metric updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating metric: {str(e)}")


@router.delete("/", response_model=SuccessResponse)
async def delete_metric(
    request: MetricRequest, db: Neo4jService = Depends(get_neo4j_service)
) -> SuccessResponse:
    """
    Delete a metric.

    Removes Metric node from Neo4j along with all its relationships.
    Does not modify connected Account or Dataset nodes.
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.id:
            raise HTTPException(
                status_code=400, detail="id is required for delete operation"
            )

        # Check if metric exists
        metric_check_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        RETURN metric
        """
        metric_result = await db.execute_query(metric_check_query, {"metric_id": request.id})
        if not metric_result:
            raise HTTPException(
                status_code=404, detail=f"Metric {request.id} not found"
            )

        # Delete metric node and all its relationships
        delete_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        DETACH DELETE metric
        """

        await db.execute_write_query(delete_query, {"metric_id": request.id})

        return SuccessResponse(
            success=True, data=None, message="Metric deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting metric: {str(e)}")
