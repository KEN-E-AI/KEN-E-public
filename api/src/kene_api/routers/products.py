"""Products router for managing product-based dataset and metric creation/deletion."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..database import Neo4jService, get_neo4j_service
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import (
    DatasetRequest,
    MetricRequest,
    ProductAddResponse,
    ProductDeleteResponse,
    ProductRequest,
)
from ..superset import SupersetClient, get_superset_client
from .datasets import create_dataset, delete_dataset
from .metrics import create_metric

router = APIRouter(tags=["products"])

# Logger
logger = logging.getLogger(__name__)

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."
FIRESTORE_UNAVAILABLE_MESSAGE = "Firestore service unavailable. Please try again later."


@router.post("/", response_model=ProductAddResponse)
async def add_product(
    request: ProductRequest,
    db: Neo4jService = Depends(get_neo4j_service),
    firestore: FirestoreService = Depends(get_firestore_service),
    superset_client: SupersetClient = Depends(get_superset_client),
) -> ProductAddResponse:
    """
    Add a product by creating datasets and metrics from Firestore configuration.

    Fetches the product configuration from the 'product-metrics' collection in Firestore,
    then creates Dataset nodes and associated Metric nodes in Neo4j for each dataset
    defined in the product configuration.

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `product` (required): Name of the product (document ID in Firestore product-metrics collection)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains processing results including datasets and metrics created

    **Example:**
    ```json
    POST /api/v1/products/
    {
        "account_id": "a000001",
        "product": "google-analytics"
    }
    ```
    """
    try:
        # Check service availability
        is_neo4j_healthy = await db.health_check()
        if not is_neo4j_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        is_firestore_healthy = firestore.health_check()
        if not is_firestore_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Fetch product configuration from Firestore
        try:
            product_doc = firestore.get_document("product-metrics", request.product)
            if not product_doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product '{request.product}' not found in product-metrics collection",
                )
        except Exception as e:
            logger.error(f"Error fetching product from Firestore: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching product configuration: {e!s}",
            )

        # Extract datasets from product configuration
        datasets_dict = product_doc.get("datasets", {})
        if not datasets_dict:
            raise HTTPException(
                status_code=400,
                detail=f"No datasets found in product '{request.product}' configuration",
            )

        # Convert datasets dictionary to list with dataset_name and dataset_id
        datasets = []
        for dataset_name, dataset_config in datasets_dict.items():
            # Add dataset_name and dataset_id to the config
            dataset_config["dataset_name"] = dataset_name
            # Use a hash of the dataset name as the dataset_id if not provided
            if "dataset_id" not in dataset_config:
                import hashlib

                dataset_config["dataset_id"] = int(
                    hashlib.md5(dataset_name.encode()).hexdigest()[:8], 16
                )
            datasets.append(dataset_config)

        created_datasets = []
        created_metrics = []
        errors = []

        # Process each dataset
        for dataset_config in datasets:
            try:
                # Create dataset request
                dataset_request = DatasetRequest(
                    account_id=request.account_id,
                    dataset_id=dataset_config.get("dataset_id"),
                    dataset_name=dataset_config.get("dataset_name"),
                    products=[
                        request.product
                    ],  # Add the current product to the products array
                    default_datetime=dataset_config.get("default_datetime"),
                    description=dataset_config.get("description"),
                )

                # Create dataset
                dataset_response = await create_dataset(dataset_request, db)
                if dataset_response.success:
                    created_datasets.append(
                        {
                            "dataset_id": dataset_config.get("dataset_id"),
                            "dataset_name": dataset_config.get("dataset_name"),
                        }
                    )

                    # Process metrics for this dataset
                    metrics = dataset_config.get("metrics", [])
                    for metric_config in metrics:
                        # Handle account_components if it's a string representation of a list
                        if isinstance(metric_config.get("account_components"), str):
                            import ast

                            try:
                                metric_config["account_components"] = ast.literal_eval(
                                    metric_config["account_components"]
                                )
                            except (ValueError, SyntaxError):
                                metric_config["account_components"] = ["generic"]
                        try:
                            # Create metric request
                            metric_request = MetricRequest(
                                account_id=request.account_id,
                                d3_format=metric_config.get("d3_format"),
                                verbose_name=metric_config.get("verbose_name"),
                                expression=metric_config.get("expression"),
                                metric_name=metric_config.get("metric_name"),
                                currency=metric_config.get("currency"),
                                account_components=metric_config.get(
                                    "account_components"
                                ),
                                related_dataset_id=dataset_config.get("dataset_id"),
                                related_dataset_name=dataset_config.get("dataset_name"),
                                related_dataset_products=[request.product],
                                description=metric_config.get("description"),
                                below_zero=metric_config.get("below_zero", False),
                                is_kpi=metric_config.get("is_kpi", False),
                            )

                            # Create metric
                            metric_response = await create_metric(
                                metric_request, db, superset_client
                            )
                            if metric_response.success:
                                created_metrics.append(
                                    {
                                        "metric_id": metric_response.data.get(
                                            "metric_id"
                                        ),
                                        "metric_name": metric_config.get("metric_name"),
                                        "dataset_id": dataset_config.get("dataset_id"),
                                    }
                                )
                            else:
                                errors.append(
                                    f"Failed to create metric '{metric_config.get('metric_name')}': {metric_response.message}"
                                )

                        except Exception as e:
                            logger.error(
                                f"Error creating metric {metric_config.get('metric_name')}: {e}"
                            )
                            errors.append(
                                f"Error creating metric '{metric_config.get('metric_name')}': {e!s}"
                            )

                else:
                    errors.append(
                        f"Failed to create dataset '{dataset_config.get('dataset_name')}': {dataset_response.message}"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing dataset {dataset_config.get('dataset_name')}: {e}"
                )
                errors.append(
                    f"Error processing dataset '{dataset_config.get('dataset_name')}': {e!s}"
                )

        # Generate response
        response_data = {
            "product": request.product,
            "datasets_created": len(created_datasets),
            "metrics_created": len(created_metrics),
            "datasets": created_datasets,
            "metrics": created_metrics,
            "errors": errors,
        }

        success_message = f"Product '{request.product}' processed successfully"
        if errors:
            success_message += f" with {len(errors)} errors"

        return ProductAddResponse(
            success=True, message=success_message, data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_product: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding product: {e!s}")


@router.delete("/", response_model=ProductDeleteResponse)
async def delete_product(
    request: ProductRequest,
    db: Neo4jService = Depends(get_neo4j_service),
) -> ProductDeleteResponse:
    """
    Delete a product by removing all datasets that contain the product.

    Finds all Dataset nodes in Neo4j that contain the specified product in their
    'products' array property, then deletes each dataset (which cascades to delete
    related metrics via the delete_dataset endpoint).

    **Parameters (in request body):**
    - `account_id` (required): The unique identifier for the account
    - `product` (required): Name of the product to remove from datasets

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    - `data`: Contains deletion results including datasets and metrics removed

    **Example:**
    ```json
    DELETE /api/v1/products/
    {
        "account_id": "a000001",
        "product": "google-analytics"
    }
    ```
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await db.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Find all datasets that contain this product
        find_datasets_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(dataset:Dataset)
        WHERE $product IN dataset.products
        RETURN dataset.dataset_id as dataset_id, dataset.dataset_name as dataset_name
        ORDER BY dataset.dataset_name
        """

        datasets_result = await db.execute_query(
            find_datasets_query,
            {"account_id": request.account_id, "product": request.product},
        )

        if not datasets_result:
            return ProductDeleteResponse(
                success=True,
                message=f"No datasets found containing product '{request.product}'",
                data={
                    "product": request.product,
                    "datasets_deleted": 0,
                    "metrics_deleted": 0,
                    "datasets": [],
                    "errors": [],
                },
            )

        deleted_datasets = []
        total_metrics_deleted = 0
        errors = []

        # Delete each dataset found
        for record in datasets_result:
            dataset_name = record["dataset_name"]
            try:
                # Create delete request for dataset
                dataset_delete_request = DatasetRequest(
                    account_id=request.account_id, dataset_name=dataset_name
                )

                # Delete dataset (which cascades to delete metrics)
                delete_response = await delete_dataset(dataset_delete_request, db)
                if delete_response.success:
                    deleted_datasets.append(
                        {
                            "dataset_id": record["dataset_id"],
                            "dataset_name": dataset_name,
                        }
                    )

                    # Extract metrics count from response message
                    if (
                        "deleted" in delete_response.message
                        and "related metrics" in delete_response.message
                    ):
                        import re

                        metrics_match = re.search(
                            r"deleted (\d+) related metrics", delete_response.message
                        )
                        if metrics_match:
                            total_metrics_deleted += int(metrics_match.group(1))
                else:
                    errors.append(
                        f"Failed to delete dataset '{dataset_name}': {delete_response.message}"
                    )

            except Exception as e:
                logger.error(f"Error deleting dataset {dataset_name}: {e}")
                errors.append(f"Error deleting dataset '{dataset_name}': {e!s}")

        # Generate response
        response_data = {
            "product": request.product,
            "datasets_deleted": len(deleted_datasets),
            "metrics_deleted": total_metrics_deleted,
            "datasets": deleted_datasets,
            "errors": errors,
        }

        success_message = f"Product '{request.product}' deletion completed"
        if deleted_datasets:
            success_message += f" - removed {len(deleted_datasets)} datasets"
            if total_metrics_deleted > 0:
                success_message += f" and {total_metrics_deleted} metrics"
        if errors:
            success_message += f" with {len(errors)} errors"

        return ProductDeleteResponse(
            success=True, message=success_message, data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_product: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting product: {e!s}")
