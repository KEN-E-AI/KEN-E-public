"""Metrics router for CRUD operations on metric entities."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..superset import SupersetClient, SupersetClientError, get_superset_client
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    Metric,
    MetricListResponse,
    MetricRequest,
    SuccessResponse,
)

router = APIRouter(tags=["metrics"])

# Logger
logger = logging.getLogger(__name__)

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
    
    **Parameters (query parameter):**
    - `account_id` (required): The unique identifier for the account
    
    **Returns:**
    - `metrics`: List of metric objects with their properties and dataset information
    - `total`: Total number of metrics found
    
    **Example:**
    ```
    GET /api/v1/metrics/?account_id=a000001
    ```
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
        currency=metric_data.get("currency") or "",
        account_components=account_components,
        related_dataset_id=dataset_data.get("dataset_id") if dataset_data else 0,
        related_dataset_name=dataset_data.get("dataset_name") if dataset_data else "",
        related_dataset_products=dataset_products,
        description=metric_data.get("description") or "",
        below_zero=metric_data.get("below_zero", False),
        is_kpi=metric_data.get("is_kpi", False),
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


async def _create_metric_node(db: Neo4jService, request: MetricRequest, superset_metric_id: Optional[int] = None) -> str:
    """Create the Metric node with BELONGS_TO relationship to Account.

    Args:
        db: Neo4j service instance
        request: Metric creation request
        superset_metric_id: Optional superset metric ID to store on the metric node

    Returns:
        str: The generated metric ID for the created metric node
    """
    # Generate unique ID for the metric node
    metric_id = str(uuid.uuid4())

    # Generate metric_name if not provided
    metric_name = (
        request.metric_name or request.verbose_name or f"metric_{metric_id[:8]}"
    )

    # Create the base metric creation query
    if request.related_dataset_name:
        # Create metric with dataset relationship
        create_metric_query = """
        MATCH (account:Account {account_id: $account_id})
        MATCH (dataset:Dataset {dataset_name: $related_dataset_name})-[:BELONGS_TO]->(account)
        CREATE (metric:Metric {
            metric_id: $metric_id,
            account_components: $account_components,
            d3_format: $d3_format,
            description: $description,
            expression: $expression,
            metric_name: $metric_name,
            verbose_name: $verbose_name,
            currency: $currency,
            superset_metric_id: $superset_metric_id,
            below_zero: $below_zero,
            is_kpi: $is_kpi
        })
        CREATE (metric)-[:BELONGS_TO]->(account)
        CREATE (metric)-[:CALCULATED_FROM]->(dataset)
        RETURN metric
        """
    else:
        # Create metric without dataset relationship
        create_metric_query = """
        MATCH (account:Account {account_id: $account_id})
        CREATE (metric:Metric {
            metric_id: $metric_id,
            account_components: $account_components,
            d3_format: $d3_format,
            description: $description,
            expression: $expression,
            metric_name: $metric_name,
            verbose_name: $verbose_name,
            currency: $currency,
            superset_metric_id: $superset_metric_id,
            below_zero: $below_zero,
            is_kpi: $is_kpi
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
        "currency": request.currency or "",
        "superset_metric_id": superset_metric_id,
        "below_zero": request.below_zero if request.below_zero is not None else False,
        "is_kpi": request.is_kpi if request.is_kpi is not None else False,
        "related_dataset_name": request.related_dataset_name or "",
    }

    metric_result = await db.execute_write_query(create_metric_query, metric_params)

    if not metric_result:
        raise HTTPException(status_code=500, detail="Failed to create metric")

    return metric_id


async def _sync_metric_to_superset(
    superset_client: SupersetClient, 
    dataset_id: int, 
    superset_metric_id: int, 
    request: MetricRequest
) -> bool:
    """Sync metric updates to Superset. Returns True if successful."""
    try:
        superset_metric_data = {}
        
        # Only include fields that are being updated and are relevant to Superset
        if request.metric_name is not None:
            superset_metric_data["metric_name"] = request.metric_name
        if request.verbose_name is not None:
            superset_metric_data["verbose_name"] = request.verbose_name
        if request.expression is not None:
            superset_metric_data["expression"] = request.expression
        if request.description is not None:
            superset_metric_data["description"] = request.description
        if request.d3_format is not None:
            superset_metric_data["d3_format"] = request.d3_format
        if request.currency is not None:
            superset_metric_data["currency"] = request.currency
        
        if superset_metric_data:
            await superset_client.update_metric(
                dataset_id, 
                superset_metric_id, 
                superset_metric_data
            )
            return True
        return False
                
    except SupersetClientError as e:
        logger.warning(f"Failed to update metric in Superset: {e}")
        return False


async def _build_neo4j_update_params(request: MetricRequest) -> tuple[List[str], Dict[str, Any]]:
    """Build update parameters for Neo4j query."""
    set_clauses = []
    params: Dict[str, Any] = {"metric_id": request.metric_id}

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

    if request.currency is not None:
        set_clauses.append("metric.currency = $currency")
        params["currency"] = request.currency

    if request.below_zero is not None:
        set_clauses.append("metric.below_zero = $below_zero")
        params["below_zero"] = request.below_zero

    if request.is_kpi is not None:
        set_clauses.append("metric.is_kpi = $is_kpi")
        params["is_kpi"] = request.is_kpi

    return set_clauses, params


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
    request: MetricRequest, 
    db: Neo4jService = Depends(get_neo4j_service),
    superset_client: SupersetClient = Depends(get_superset_client)
) -> SuccessResponse:
    """
    Create a new metric.

    Creates a new Metric node in Neo4j with a BELONGS_TO relationship to the Account node.
    Also creates a CALCULATED_FROM relationship to an existing Dataset node if related_dataset_id is provided.
    Additionally, creates the metric in Apache Superset if dataset information is available.
    
    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `d3_format` (optional): The d3 formatting guidelines for metric presentation
    - `verbose_name` (optional): The friendly name of the metric
    - `expression` (optional): The SQL expression used to calculate the metric
    - `metric_name` (optional): The snake_case representation of the metric name
    - `currency` (optional): The currency code for the metric (e.g., USD, EUR, GBP)
    - `account_components` (optional): List of components the metric assists with in analysis
    - `related_dataset_id` (optional): Unique identifier for the dataset used to calculate the metric
    - `related_dataset_name` (optional): Name of the dataset used to calculate the metric
    - `related_dataset_products` (optional): List of martech products used to calculate the metric
    - `description` (optional): Friendly description of the metric and its usage
    - `below_zero` (optional): Boolean indicating whether the metric can return a result below 0 (default: false)
    - `is_kpi` (optional): Boolean indicating whether the metric has been flagged as a Key Performance Indicator (default: false)
    
    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains the generated metric ID
    
    **Example:**
    ```json
    POST /api/v1/metrics/
    {
        "account_id": "a000001",
        "verbose_name": "Total Revenue",
        "metric_name": "total_revenue",
        "expression": "sum(revenue)",
        "d3_format": "$,.2f",
        "currency": "USD",
        "account_components": ["ecommerce"],
        "related_dataset_id": 28,
        "description": "Total revenue from all transactions",
        "below_zero": false,
        "is_kpi": true
    }
    ```
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

        superset_metric_id = None
        
        # TODO: Create metric in Superset if dataset information is provided
        # Temporarily commented out due to API payload format issues
        # if request.related_dataset_id and request.metric_name and request.expression:
        #
        #     superset_metric_data = {
        #         "metric_name": request.metric_name,
        #         "verbose_name": request.verbose_name or request.metric_name,
        #         "expression": request.expression,
        #         "description": request.description or "",
        #         "d3_format": request.d3_format or "",
        #         "currency": request.currency or ""
        #     }
        #     
        #     superset_result = await superset_client.create_metric(
        #         request.related_dataset_id, 
        #         superset_metric_data
        #     )
        #     superset_metric_id = superset_result.get("id")
                

        # Create Metric node in Neo4j
        generated_metric_id = await _create_metric_node(db, request, superset_metric_id)

        # Create CALCULATED_FROM relationship to Dataset if dataset_id provided
        if request.related_dataset_id:
            await _create_dataset_relationship(
                db, generated_metric_id, request.related_dataset_id
            )

        response_data = {"metric_id": generated_metric_id}

        return SuccessResponse(
            success=True,
            data=response_data,
            message="Metric created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating metric: {str(e)}")


@router.put("/", response_model=SuccessResponse)
async def update_metric(
    request: MetricRequest, 
    db: Neo4jService = Depends(get_neo4j_service),
    superset_client: SupersetClient = Depends(get_superset_client)
) -> SuccessResponse:
    """
    Update an existing metric.

    Updates Metric node properties in Neo4j and syncs changes with Apache Superset.
    Does not modify relationships to other nodes.
    
    **Parameters (in request body):**
    - `metric_id` (required): The unique identifier of the metric to update
    - `account_id` (required): The unique identifier for the account
    - `d3_format` (optional): Updated d3 formatting guidelines for metric presentation
    - `verbose_name` (optional): Updated friendly name of the metric
    - `expression` (optional): Updated SQL expression used to calculate the metric
    - `metric_name` (optional): Updated snake_case representation of the metric name
    - `currency` (optional): Updated currency code for the metric (e.g., USD, EUR, GBP)
    - `account_components` (optional): Updated list of components the metric assists with in analysis
    - `related_dataset_id` (optional): Updated unique identifier for the dataset used to calculate the metric
    - `related_dataset_name` (optional): Updated name of the dataset used to calculate the metric
    - `related_dataset_products` (optional): Updated list of martech products used to calculate the metric
    - `description` (optional): Updated friendly description of the metric and its usage
    - `below_zero` (optional): Updated boolean indicating whether the metric can return a result below 0
    - `is_kpi` (optional): Updated boolean indicating whether the metric has been flagged as a Key Performance Indicator
    
    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message (includes Superset sync status)
    - `data`: null
    
    **Example:**
    ```json
    PUT /api/v1/metrics/
    {
        "metric_id": "888ttt",
        "account_id": "a000001",
        "verbose_name": "Updated Total Revenue",
        "expression": "sum(revenue * 1.1)",
        "description": "Total revenue with 10% markup"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.metric_id:
            raise HTTPException(
                status_code=400, detail="metric_id is required for update operation"
            )

        # Check if metric exists and get current data
        metric_check_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        OPTIONAL MATCH (metric)-[:CALCULATED_FROM]->(dataset:Dataset)
        RETURN metric, dataset, metric.superset_metric_id as superset_metric_id
        """
        metric_result = await db.execute_query(metric_check_query, {"metric_id": request.metric_id})
        if not metric_result:
            raise HTTPException(
                status_code=404, detail=f"Metric {request.metric_id} not found"
            )

        current_dataset = metric_result[0]["dataset"]
        superset_metric_id = metric_result[0]["superset_metric_id"]
        
        # Build update parameters for Neo4j
        set_clauses, params = await _build_neo4j_update_params(request)

        if not set_clauses:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # TODO: Try to update in Superset
        # Temporarily commented out due to API payload format issues
        superset_updated = False
        # dataset_id = current_dataset.get("dataset_id") if current_dataset else None
        # 
        # if superset_metric_id and dataset_id:
        #     superset_updated = await _sync_metric_to_superset(
        #         superset_client, dataset_id, superset_metric_id, request
        #     )

        # Execute update query in Neo4j
        update_query = f"""
        MATCH (metric:Metric {{metric_id: $metric_id}})
        SET {', '.join(set_clauses)}
        RETURN metric
        """

        await db.execute_write_query(update_query, params)

        # Generate response message
        response_message = "Metric updated successfully"
        # TODO: Re-enable Superset sync status when integration is fixed
        # if superset_updated:
        #     response_message += " (synced with Superset)"
        # elif superset_metric_id and dataset_id:
        #     response_message += " (Superset sync failed - check logs)"

        return SuccessResponse(
            success=True, data=None, message=response_message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating metric: {str(e)}")


@router.delete("/", response_model=SuccessResponse)
async def delete_metric(
    request: MetricRequest, 
    db: Neo4jService = Depends(get_neo4j_service),
    superset_client: SupersetClient = Depends(get_superset_client)
) -> SuccessResponse:
    """
    Delete a metric.

    Removes Metric node from Neo4j along with all its relationships, and also 
    deletes the corresponding metric from Apache Superset if it exists.
    Does not modify connected Account or Dataset nodes.
    
    **Parameters (in request body):**
    - `metric_id` (required): The unique identifier of the metric to delete
    - `account_id` (required): The unique identifier for the account
    
    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message (includes Superset deletion status)
    - `data`: null
    
    **Example:**
    ```json
    DELETE /api/v1/metrics/
    {
        "metric_id": "888ttt",
        "account_id": "a000001"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.metric_id:
            raise HTTPException(
                status_code=400, detail="metric_id is required for delete operation"
            )

        # Check if metric exists and get Superset information
        metric_check_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        OPTIONAL MATCH (metric)-[:CALCULATED_FROM]->(dataset:Dataset)
        RETURN metric, dataset, metric.superset_metric_id as superset_metric_id
        """
        metric_result = await db.execute_query(metric_check_query, {"metric_id": request.metric_id})
        if not metric_result:
            raise HTTPException(
                status_code=404, detail=f"Metric {request.metric_id} not found"
            )

        current_dataset = metric_result[0]["dataset"]
        superset_metric_id = metric_result[0]["superset_metric_id"]
        
        # TODO: Delete from Superset if superset_metric_id exists
        # Temporarily commented out due to API payload format issues
        superset_deleted = False
        # dataset_id = current_dataset.get("dataset_id") if current_dataset else None
        # 
        # if superset_metric_id and dataset_id:
        #     try:
        #         success = await superset_client.delete_metric(dataset_id, superset_metric_id)
        #         superset_deleted = success
        #         
        #     except SupersetClientError as e:
        #         # Log the error but don't fail the entire operation
        #         logger.warning(f"Failed to delete metric from Superset: {e}")

        # Delete metric node and all its relationships from Neo4j
        delete_query = """
        MATCH (metric:Metric {metric_id: $metric_id})
        DETACH DELETE metric
        """

        await db.execute_write_query(delete_query, {"metric_id": request.metric_id})

        response_message = "Metric deleted successfully"
        # TODO: Re-enable Superset deletion status when integration is fixed
        # if superset_deleted:
        #     response_message += " (removed from Superset)"
        # elif superset_metric_id and dataset_id:
        #     response_message += " (Superset deletion failed - check logs)"

        return SuccessResponse(
            success=True, data=None, message=response_message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting metric: {str(e)}")
