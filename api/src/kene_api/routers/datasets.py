"""Datasets router for CRUD operations on dataset entities."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    Dataset,
    DatasetListResponse,
    DatasetRequest,
    SuccessResponse,
)

router = APIRouter(tags=["datasets"])

# Logger
logger = logging.getLogger(__name__)

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."


@router.get("/", response_model=DatasetListResponse)
async def get_datasets(
    account_id: str = Query(..., description=ACCOUNT_ID_DESCRIPTION),
    db: Neo4jService = Depends(get_neo4j_service),
) -> DatasetListResponse:
    """
    Get all datasets for an account.

    Returns a list of all datasets that have been created for the account,
    along with all properties.

    **Parameters (query parameter):**
    - `account_id` (required): The unique identifier for the account

    **Returns:**
    - `datasets`: List of dataset objects with their properties
    - `total`: Total number of datasets found

    **Example:**
    ```
    GET /api/v1/datasets/?account_id=a000001
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch datasets for the account
        datasets_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(dataset:Dataset)
        RETURN dataset
        ORDER BY dataset.dataset_name
        """

        result = await db.execute_query(datasets_query, {"account_id": account_id})

        datasets = []
        for record in result:
            dataset_data = record.get("dataset")
            if dataset_data:
                dataset = await _create_dataset_from_record(dataset_data, account_id)
                datasets.append(dataset)

        return DatasetListResponse(datasets=datasets, total=len(datasets))

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from e
        raise HTTPException(status_code=500, detail=f"Error fetching datasets: {e!s}")


async def _create_dataset_from_record(
    dataset_data: dict[str, Any], account_id: str
) -> Dataset:
    """Create a Dataset object from a database record."""
    if not dataset_data:
        raise ValueError("No dataset data found in record")

    # Parse products - handle string representation of list
    products = dataset_data.get("products", [])
    if isinstance(products, str):
        try:
            import ast

            products = ast.literal_eval(products)
        except (ValueError, SyntaxError):
            products = []

    return Dataset(
        id=dataset_data.get("dataset_id", ""),
        account_id=account_id,
        dataset_id=dataset_data.get("dataset_id", ""),
        dataset_name=dataset_data.get("dataset_name", ""),
        products=products,
        default_datetime=dataset_data.get("default_datetime", ""),
        description=dataset_data.get("description", ""),
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


@router.post("/", response_model=SuccessResponse)
async def create_dataset(
    request: DatasetRequest,
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Create a new dataset.

    Creates a new Dataset node in Neo4j with a BELONGS_TO relationship to the Account node.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `dataset_id` (required): A unique identifier for the dataset
    - `dataset_name` (required): A unique name for the dataset
    - `products` (required): List of products that collect the data used in this dataset
    - `default_datetime` (required): Name of the datetime column used to aggregate data by date
    - `description` (required): Description of the dataset and its usefulness

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains the dataset ID

    **Example:**
    ```json
    POST /api/v1/datasets/
    {
        "account_id": "a000001",
        "dataset_id": "ds_001",
        "dataset_name": "ga4_sessions",
        "products": ["google_analytics"],
        "default_datetime": "session_start",
        "description": "Google Analytics 4 session data"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Validate required fields
        if not request.dataset_id:
            raise HTTPException(status_code=400, detail="dataset_id is required")
        if not request.dataset_name:
            raise HTTPException(status_code=400, detail="dataset_name is required")
        if not request.products:
            raise HTTPException(status_code=400, detail="products is required")
        if not request.default_datetime:
            raise HTTPException(status_code=400, detail="default_datetime is required")
        if not request.description:
            raise HTTPException(status_code=400, detail="description is required")

        # Verify Account exists
        await _verify_account_exists(db, request.account_id)

        # Check if dataset already exists
        dataset_check_query = """
        MATCH (dataset:Dataset {dataset_id: $dataset_id})
        RETURN dataset
        """
        existing_dataset = await db.execute_query(
            dataset_check_query, {"dataset_id": request.dataset_id}
        )
        if existing_dataset:
            raise HTTPException(
                status_code=409,
                detail=f"Dataset with ID {request.dataset_id} already exists",
            )

        # Create Dataset node with BELONGS_TO relationship to Account
        create_dataset_query = """
        MATCH (account:Account {account_id: $account_id})
        CREATE (dataset:Dataset {
            dataset_id: $dataset_id,
            dataset_name: $dataset_name,
            products: $products,
            default_datetime: $default_datetime,
            description: $description
        })
        CREATE (dataset)-[:BELONGS_TO]->(account)
        RETURN dataset
        """

        dataset_params = {
            "account_id": request.account_id,
            "dataset_id": request.dataset_id,
            "dataset_name": request.dataset_name,
            "products": request.products,
            "default_datetime": request.default_datetime,
            "description": request.description,
        }

        dataset_result = await db.execute_write_query(
            create_dataset_query, dataset_params
        )

        if not dataset_result:
            raise HTTPException(status_code=500, detail="Failed to create dataset")

        response_data = {"dataset_id": request.dataset_id}

        return SuccessResponse(
            success=True,
            data=response_data,
            message="Dataset created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating dataset: {e!s}"
        ) from e


@router.put("/", response_model=SuccessResponse)
async def update_dataset(
    request: DatasetRequest,
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Update an existing dataset.

    Updates Dataset node properties in Neo4j.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `dataset_name` (required): The unique name of the dataset to update
    - `dataset_id` (optional): Updated unique identifier for the dataset
    - `products` (optional): Updated list of products
    - `default_datetime` (optional): Updated default datetime column name
    - `description` (optional): Updated description

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: null

    **Example:**
    ```json
    PUT /api/v1/datasets/
    {
        "account_id": "a000001",
        "dataset_name": "ga4_sessions",
        "description": "Updated description for GA4 sessions"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.dataset_name:
            raise HTTPException(
                status_code=400, detail="dataset_name is required for update operation"
            )

        # Check if dataset exists
        dataset_check_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(dataset:Dataset {dataset_name: $dataset_name})
        RETURN dataset
        """
        dataset_result = await db.execute_query(
            dataset_check_query,
            {"account_id": request.account_id, "dataset_name": request.dataset_name},
        )
        if not dataset_result:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {request.dataset_name} not found for account {request.account_id}",
            )

        # Build update parameters
        set_clauses = []
        params = {
            "account_id": request.account_id,
            "dataset_name": request.dataset_name,
        }

        if request.dataset_id is not None:
            set_clauses.append("dataset.dataset_id = $dataset_id")
            params["dataset_id"] = request.dataset_id

        if request.products is not None:
            set_clauses.append("dataset.products = $products")
            params["products"] = request.products

        if request.default_datetime is not None:
            set_clauses.append("dataset.default_datetime = $default_datetime")
            params["default_datetime"] = request.default_datetime

        if request.description is not None:
            set_clauses.append("dataset.description = $description")
            params["description"] = request.description

        if not set_clauses:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        # Execute update query
        update_query = f"""
        MATCH (account:Account {{account_id: $account_id}})<-[:BELONGS_TO]-(dataset:Dataset {{dataset_name: $dataset_name}})
        SET {", ".join(set_clauses)}
        RETURN dataset
        """

        await db.execute_write_query(update_query, params)

        return SuccessResponse(
            success=True, data=None, message="Dataset updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating dataset: {e!s}"
        ) from e


@router.delete("/", response_model=SuccessResponse)
async def delete_dataset(
    request: DatasetRequest,
    db: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Delete a dataset.

    Removes Dataset node from Neo4j along with all Metric nodes that have a
    CALCULATED_FROM relationship to the dataset.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `dataset_name` (required): The unique name of the dataset to delete

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message including count of deleted metrics
    - `data`: null

    **Example:**
    ```json
    DELETE /api/v1/datasets/
    {
        "account_id": "a000001",
        "dataset_name": "ga4_sessions"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        if not request.dataset_name:
            raise HTTPException(
                status_code=400, detail="dataset_name is required for delete operation"
            )

        # Check if dataset exists and count related metrics
        dataset_check_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(dataset:Dataset {dataset_name: $dataset_name})
        OPTIONAL MATCH (metric:Metric)-[:CALCULATED_FROM]->(dataset)
        RETURN dataset, count(metric) as metric_count
        """
        dataset_result = await db.execute_query(
            dataset_check_query,
            {"account_id": request.account_id, "dataset_name": request.dataset_name},
        )
        if not dataset_result or not dataset_result[0]["dataset"]:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {request.dataset_name} not found for account {request.account_id}",
            )

        metric_count = dataset_result[0]["metric_count"]

        # Delete dataset and all related metrics
        delete_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(dataset:Dataset {dataset_name: $dataset_name})
        OPTIONAL MATCH (metric:Metric)-[:CALCULATED_FROM]->(dataset)
        DETACH DELETE metric, dataset
        """

        await db.execute_write_query(
            delete_query,
            {"account_id": request.account_id, "dataset_name": request.dataset_name},
        )

        response_message = "Dataset deleted successfully"
        if metric_count > 0:
            response_message += f" (also deleted {metric_count} related metrics)"

        return SuccessResponse(success=True, data=None, message=response_message)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting dataset: {e!s}"
        ) from e
