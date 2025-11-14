"""Firestore router for CRUD operations on Google Firestore."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..email_service import get_email_service
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import BaseRequest, SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["firestore"])

# Constants
FIRESTORE_UNAVAILABLE_MESSAGE = "Firestore service unavailable. Please try again later."
ACCOUNT_ID_VALIDATION_DESCRIPTION = "Account ID for validation"
DOCUMENT_NOT_FOUND_MESSAGE = "Document not found"


# Pydantic models for Firestore operations


class FirestoreDocumentRequest(BaseRequest):
    """Request model for Firestore document operations."""

    collection: str = Field(..., description="Firestore collection name")
    document_id: str | None = Field(
        None, description="Document ID (auto-generated if not provided)"
    )
    data: dict[str, Any] = Field(..., description="Document data")


class FirestoreDocumentResponse(BaseModel):
    """Response model for Firestore document operations."""

    success: bool = Field(..., description="Operation success status")
    document_id: str = Field(..., description="Document ID")
    data: dict[str, Any] | None = Field(None, description="Document data")


class FirestoreDocumentListResponse(BaseModel):
    """Response model for Firestore document list operations."""

    documents: list[dict[str, Any]] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")


class FirestoreQueryRequest(BaseRequest):
    """Request model for Firestore document queries."""

    collection: str = Field(..., description="Firestore collection name")
    field: str | None = Field(None, description="Field to query")
    operator: str | None = Field(
        None,
        description="Query operator (==, !=, <, <=, >, >=, in, not-in, array-contains, array-contains-any)",
    )
    value: Any | None = Field(None, description="Value to compare against")
    limit: int | None = Field(None, description="Maximum number of documents to return")


class KPISettingRequest(BaseRequest):
    """Request model for KPI setting operations."""

    organization_id: str = Field(
        ..., description="The unique identifier for the organization"
    )
    account_id: str = Field(..., description="The unique identifier for the account")
    kpi_name: str = Field(
        ..., description="KPI name: income_kpi, marketing_cost_kpi, or net_income_kpi"
    )
    metric_id: str = Field(..., description="The unique identifier for the metric")


class KPISettingResponse(BaseModel):
    """Response model for KPI setting operations."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    kpi_name: str = Field(..., description="KPI name")
    metric_id: str | None = Field(None, description="Metric ID associated with the KPI")


class KPISettingsResponse(BaseModel):
    """Response model for all KPI settings."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    kpi_settings: dict[str, str] = Field(
        ..., description="Dictionary of KPI names to metric IDs"
    )


class FunnelStepRequest(BaseRequest):
    """Request model for funnel step operations."""

    organization_id: str = Field(
        ..., description="Unique identifier for the organization"
    )
    account_id: str = Field(..., description="Unique identifier for the account")
    funnel_type: str = Field(
        ..., description="Type of funnel: 'organization' or 'big_bet'"
    )
    big_bet_name: str | None = Field(
        None, description="Name of the big bet (required if funnel_type is 'big_bet')"
    )
    funnel_step_num: int = Field(
        ..., description="Step number in the conversion funnel", ge=1
    )
    funnel_step_name: str = Field(
        ...,
        description="Name of the funnel step: 'awareness', 'consideration', 'conversion', or 'loyalty'",
    )
    effectiveness_kpi: str = Field(
        ..., description="Metric ID for effectiveness calculation"
    )
    efficiency_kpi: str = Field(..., description="Metric ID for efficiency calculation")
    objective: str = Field(..., description="Text of the funnel step objective")


class FunnelStepResponse(BaseModel):
    """Response model for funnel step operations."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: str | None = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    funnel_step_data: dict[str, Any] | None = Field(
        None, description="Funnel step data"
    )


class FunnelStepsListResponse(BaseModel):
    """Response model for listing funnel steps."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: str | None = Field(None, description="Big bet name (if applicable)")
    funnel_steps: list[dict[str, Any]] = Field(..., description="List of funnel steps")
    total: int = Field(..., description="Total number of funnel steps")


class ChannelRequest(BaseModel):
    """Request model for channel operations."""

    channel_name: str = Field(
        ..., description="Name of the channel as defined by the user"
    )
    effectiveness_kpi: str = Field(
        ..., description="Metric ID for effectiveness calculation within the channel"
    )
    efficiency_kpi: str = Field(
        ...,
        description="Metric ID for efficiency calculation within the channel and funnel step",
    )
    supporting_metrics: list[str] = Field(
        ..., description="List of metrics for evaluating channel performance"
    )


class ChannelUpdateRequest(BaseModel):
    """Request model for updating channel operations."""

    channel_name: str | None = Field(
        None, description="Name of the channel as defined by the user"
    )
    effectiveness_kpi: str | None = Field(
        None, description="Metric ID for effectiveness calculation within the channel"
    )
    efficiency_kpi: str | None = Field(
        None,
        description="Metric ID for efficiency calculation within the channel and funnel step",
    )
    supporting_metrics: list[str] | None = Field(
        None, description="List of metrics for evaluating channel performance"
    )


class ChannelResponse(BaseModel):
    """Response model for channel operations."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: str | None = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    channel_name: str = Field(..., description="Channel name")
    channel_data: dict[str, Any] | None = Field(None, description="Channel data")


class ChannelListResponse(BaseModel):
    """Response model for listing channels."""

    channels: list[dict[str, Any]] = Field(..., description="List of channels")
    total: int = Field(..., description="Total number of channels")


class TacticRequest(BaseModel):
    """Request model for tactic operations."""

    tactic_name: str = Field(
        ..., description="Name of the tactic as defined by the user"
    )
    effectiveness_kpi: str = Field(
        ..., description="Metric ID for effectiveness calculation within the tactic"
    )
    efficiency_kpi: str = Field(
        ..., description="Metric ID for efficiency calculation within the tactic"
    )
    supporting_metrics: list[str] = Field(
        ..., description="List of metrics for evaluating tactic performance"
    )


class TacticUpdateRequest(BaseModel):
    """Request model for updating tactic operations."""

    tactic_name: str | None = Field(
        None, description="Name of the tactic as defined by the user"
    )
    effectiveness_kpi: str | None = Field(
        None, description="Metric ID for effectiveness calculation within the tactic"
    )
    efficiency_kpi: str | None = Field(
        None, description="Metric ID for efficiency calculation within the tactic"
    )
    supporting_metrics: list[str] | None = Field(
        None, description="List of metrics for evaluating tactic performance"
    )


class TacticResponse(BaseModel):
    """Response model for tactic operations."""

    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: str | None = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    channel_name: str = Field(..., description="Channel name")
    tactic_name: str = Field(..., description="Tactic name")
    tactic_data: dict[str, Any] | None = Field(None, description="Tactic data")


class TacticListResponse(BaseModel):
    """Response model for listing tactics."""

    tactics: list[dict[str, Any]] = Field(..., description="List of tactics")
    total: int = Field(..., description="Total number of tactics")


# Valid KPI names
VALID_KPI_NAMES = ["income_kpi", "marketing_cost_kpi", "net_income_kpi"]

# Valid funnel types and step names
VALID_FUNNEL_TYPES = ["organization", "big_bet"]
VALID_FUNNEL_STEP_NAMES = ["awareness", "consideration", "conversion", "loyalty"]


def validate_kpi_name(kpi_name: str) -> None:
    """Validate that the KPI name is one of the allowed values."""
    if kpi_name not in VALID_KPI_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid kpi_name. Must be one of: {', '.join(VALID_KPI_NAMES)}",
        )


def validate_funnel_type(funnel_type: str) -> None:
    """Validate that the funnel type is one of the allowed values."""
    if funnel_type not in VALID_FUNNEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid funnel_type. Must be one of: {', '.join(VALID_FUNNEL_TYPES)}",
        )


def validate_funnel_step_name(funnel_step_name: str) -> None:
    """Validate that the funnel step name is one of the allowed values."""
    if funnel_step_name not in VALID_FUNNEL_STEP_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid funnel_step_name. Must be one of: {', '.join(VALID_FUNNEL_STEP_NAMES)}",
        )


def validate_big_bet_requirement(funnel_type: str, big_bet_name: str | None) -> None:
    """Validate that big_bet_name is provided when funnel_type is 'big_bet'."""
    if funnel_type == "big_bet" and not big_bet_name:
        raise HTTPException(
            status_code=400,
            detail="big_bet_name is required when funnel_type is 'big_bet'",
        )
    elif funnel_type == "organization" and big_bet_name:
        raise HTTPException(
            status_code=400,
            detail="big_bet_name should not be provided when funnel_type is 'organization'",
        )


# Firestore Document Operations


@router.post("/documents", response_model=FirestoreDocumentResponse)
async def create_document(
    request: FirestoreDocumentRequest,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentResponse:
    """
    Create a document in Firestore.

    Creates a new document in the specified collection with the provided data.

    **Parameters (in request body):**
    - `collection` (required): Firestore collection name
    - `document_id` (optional): Document ID (auto-generated if not provided)
    - `data` (required): Document data as key-value pairs

    **Returns:**
    - `success`: Boolean indicating operation success
    - `document_id`: ID of the created document
    - `data`: Document data that was stored

    **Example:**
    ```json
    POST /api/v1/firestore/documents
    {
        "collection": "users",
        "document_id": "user123",
        "data": {
            "name": "John Doe",
            "email": "john@example.com"
        }
    }
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Create document
        document_id = firestore.create_document(
            collection=request.collection,
            document_id=request.document_id,
            data=request.data,
        )

        return FirestoreDocumentResponse(
            success=True, document_id=document_id, data=request.data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {e!s}")


@router.get(
    "/documents/{collection}/{document_id}", response_model=FirestoreDocumentResponse
)
async def get_document(
    collection: str,
    document_id: str,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentResponse:
    """
    Get a document from Firestore.

    Retrieves a document by its ID from the specified collection.

    **Parameters (in URL path):**
    - `collection` (required): Firestore collection name
    - `document_id` (required): Document ID to retrieve

    **Returns:**
    - `success`: Boolean indicating operation success
    - `document_id`: ID of the retrieved document
    - `data`: Document data

    **Example:**
    ```
    GET /api/v1/firestore/documents/users/user123
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get document
        doc_data = firestore.get_document(
            collection=collection, document_id=document_id
        )

        if doc_data is None:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_MESSAGE)

        return FirestoreDocumentResponse(
            success=True, document_id=document_id, data=doc_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document: {e!s}")


@router.put("/documents/{collection}/{document_id}", response_model=SuccessResponse)
async def update_document(
    collection: str,
    document_id: str,
    data: dict[str, Any],
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a document in Firestore.

    Updates an existing document with the provided data. Supports four modes:

    **Parameters (in URL path):**
    - `collection` (required): Firestore collection name
    - `document_id` (required): Document ID to update

    **Parameters (query parameter):**
    - `account_id` (required): Account ID for validation

    **Parameters (in request body):**
    Mode 1 - Direct update:
    ```json
    {"field1": "value1", "field2": "value2"}
    ```

    Mode 2 - Array union operation:
    ```json
    {
      "update": {
        "field": "field_name",
        "operator": "arrayUnion",
        "value": {...object_to_add...}
      }
    }
    ```

    Mode 3 - Replace array element:
    ```json
    {
      "update": {
        "field": "field_name",
        "operator": "replaceOne",
        "matchField": "id_field",
        "matchValue": "id_value",
        "value": {...replacement_object...}
      }
    }
    ```

    Mode 4 - Set nested field:
    ```json
    {
      "update": {
        "field": "permissions.account_permissions.newAccountId",
        "operator": "set",
        "value": "admin"
      }
    }
    ```

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message with operation details

    **Example:**
    ```
    PUT /api/v1/firestore/documents/users/user123?account_id=a000001
    ```
    """
    try:
        # First validate the request payload structure before checking Firestore
        if "update" in data and isinstance(data["update"], dict):
            update_config = data["update"]
            operator = update_config.get("operator")

            if operator == "arrayUnion":
                # Validate arrayUnion parameters
                field = update_config.get("field")
                value = update_config.get("value")

                if not field or "value" not in update_config:
                    raise HTTPException(
                        status_code=400,
                        detail="arrayUnion operation requires 'field' and 'value' parameters",
                    )

            elif operator == "replaceOne":
                # Validate replaceOne parameters
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")

                if not all(
                    [field, match_field, match_value is not None, value is not None]
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="replaceOne operation requires 'field', 'matchField', 'matchValue', and 'value' parameters",
                    )

            elif operator == "set":
                # Validate set parameters
                field = update_config.get("field")
                value = update_config.get("value")

                if not field or "value" not in update_config:
                    raise HTTPException(
                        status_code=400,
                        detail="set operation requires 'field' and 'value' parameters",
                    )

            elif operator and operator not in ["arrayUnion", "replaceOne", "set"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne, set",
                )

        # Check Firestore connectivity after parameter validation
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Process the validated operation
        if "update" in data and isinstance(data["update"], dict):
            update_config = data["update"]
            operator = update_config.get("operator")

            if operator == "arrayUnion":
                # Handle array union operation
                field = update_config.get("field")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None and value is not None

                success = firestore.array_union_document(
                    collection=collection,
                    document_id=document_id,
                    field=field,
                    value=value,
                )

                operation_desc = f"Array union operation on field '{field}'"

            elif operator == "replaceOne":
                # Handle replace one operation
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None and match_field is not None
                assert match_value is not None and value is not None

                success = firestore.replace_array_element(
                    collection=collection,
                    document_id=document_id,
                    field=field,
                    match_field=match_field,
                    match_value=match_value,
                    new_value=value,
                )

                operation_desc = f"Replace operation on field '{field}' where {match_field}={match_value}"

            elif operator == "set":
                # Handle set nested field operation
                field = update_config.get("field")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None

                success = firestore.set_nested_field(
                    collection=collection,
                    document_id=document_id,
                    field_path=field,
                    value=value,
                )

                operation_desc = f"Set nested field operation on '{field}'"

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne, set",
                )
        else:
            # Handle standard document update (existing functionality)
            success = firestore.update_document(
                collection=collection, document_id=document_id, data=data
            )
            operation_desc = "Document update"

        if not success:
            raise HTTPException(
                status_code=404, detail="Document not found or operation failed"
            )

        return SuccessResponse(
            success=True,
            message=f"Document {document_id} updated successfully - {operation_desc}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating document: {e!s}")


@router.delete("/documents/{collection}/{document_id}", response_model=SuccessResponse)
async def delete_document(
    collection: str,
    document_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete a document from Firestore.

    Deletes a document by its ID from the specified collection.

    **Parameters (in URL path):**
    - `collection` (required): Firestore collection name
    - `document_id` (required): Document ID to delete

    **Parameters (query parameter):**
    - `account_id` (required): Account ID for validation

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message

    **Example:**
    ```
    DELETE /api/v1/firestore/documents/users/user123?account_id=a000001
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Delete document
        success = firestore.delete_document(
            collection=collection, document_id=document_id
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return SuccessResponse(
            success=True, message=f"Document {document_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {e!s}")


@router.post("/documents/query", response_model=FirestoreDocumentListResponse)
async def query_documents(
    request: FirestoreQueryRequest,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentListResponse:
    """
    Query documents from Firestore.

    Retrieves documents from a collection based on query parameters.

    **Parameters (in request body):**
    - `collection` (required): Firestore collection name
    - `field` (optional): Field to query
    - `operator` (optional): Query operator (==, !=, <, <=, >, >=, in, not-in, array-contains, array-contains-any)
    - `value` (optional): Value to compare against
    - `limit` (optional): Maximum number of documents to return

    **Returns:**
    - `documents`: List of matching documents
    - `total`: Total number of documents found

    **Example:**
    ```json
    POST /api/v1/firestore/documents/query
    {
        "collection": "users",
        "field": "email",
        "operator": "==",
        "value": "john@example.com",
        "limit": 10
    }
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Query documents
        if request.field and request.operator and request.value is not None:
            documents = firestore.query_documents(
                collection=request.collection,
                field=request.field,
                operator=request.operator,
                value=request.value,
                limit=request.limit,
            )
        else:
            documents = firestore.list_documents(
                collection=request.collection, limit=request.limit
            )

        return FirestoreDocumentListResponse(documents=documents, total=len(documents))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying documents: {e!s}")


@router.get(
    "/collections/{collection}/documents", response_model=FirestoreDocumentListResponse
)
async def list_collection_documents(
    collection: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    limit: int | None = Query(
        None, description="Maximum number of documents to return"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentListResponse:
    """
    List all documents in a collection.

    Retrieves all documents from the specified collection.
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # List documents
        documents = firestore.list_documents(collection=collection, limit=limit)

        return FirestoreDocumentListResponse(documents=documents, total=len(documents))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {e!s}")


# Subcollection Document Operations


@router.post(
    "/documents/{collection}/{document_id}/{subcollection}",
    response_model=FirestoreDocumentResponse,
)
async def create_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    data: dict[str, Any],
    subdocument_id: str | None = Query(
        None, description="Subdocument ID (auto-generated if not provided)"
    ),
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentResponse:
    """
    Create a document in a subcollection.

    Creates a new document in the specified subcollection within a parent document.
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Create subcollection document
        created_subdocument_id = firestore.create_subcollection_document(
            collection=collection,
            document_id=document_id,
            subcollection=subcollection,
            subdocument_id=subdocument_id,
            data=data,
        )

        return FirestoreDocumentResponse(
            success=True, document_id=created_subdocument_id, data=data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating subcollection document: {e!s}"
        )


@router.get(
    "/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}",
    response_model=FirestoreDocumentResponse,
)
async def get_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    subdocument_id: str,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FirestoreDocumentResponse:
    """
    Get a document from a subcollection.

    Retrieves a document by its ID from the specified subcollection within a parent document.
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get subcollection document
        doc_data = firestore.get_subcollection_document(
            collection=collection,
            document_id=document_id,
            subcollection=subcollection,
            subdocument_id=subdocument_id,
        )

        if doc_data is None:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_MESSAGE)

        return FirestoreDocumentResponse(
            success=True, document_id=subdocument_id, data=doc_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving subcollection document: {e!s}"
        )


@router.put(
    "/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}",
    response_model=SuccessResponse,
)
async def update_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    subdocument_id: str,
    data: dict[str, Any],
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a document in a subcollection.

    Updates an existing document in the specified subcollection with the provided data. Supports four modes:

    1. Direct update (standard functionality):
       data = {"field1": "value1", "field2": "value2"}

    2. Array union operation:
       data = {
         "update": {
           "field": "field_name",
           "operator": "arrayUnion",
           "value": {...object_to_add...}
         }
       }

    3. Replace array element:
       data = {
         "update": {
           "field": "field_name",
           "operator": "replaceOne",
           "matchField": "id_field",
           "matchValue": "id_value",
           "value": {...replacement_object...}
         }
       }

    4. Set nested field:
       data = {
         "update": {
           "field": "set_name.subset_name.field_name",
           "operator": "set",
           "value": "admin"
         }
       }
    """
    try:
        # First validate the request payload structure before checking Firestore
        if "update" in data and isinstance(data["update"], dict):
            update_config = data["update"]
            operator = update_config.get("operator")

            if operator == "arrayUnion":
                # Validate arrayUnion parameters
                field = update_config.get("field")
                value = update_config.get("value")

                if not field or "value" not in update_config:
                    raise HTTPException(
                        status_code=400,
                        detail="arrayUnion operation requires 'field' and 'value' parameters",
                    )

            elif operator == "replaceOne":
                # Validate replaceOne parameters
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")

                if not all(
                    [field, match_field, match_value is not None, value is not None]
                ):
                    raise HTTPException(
                        status_code=400,
                        detail="replaceOne operation requires 'field', 'matchField', 'matchValue', and 'value' parameters",
                    )

            elif operator == "set":
                # Validate set parameters
                field = update_config.get("field")
                value = update_config.get("value")

                if not field or "value" not in update_config:
                    raise HTTPException(
                        status_code=400,
                        detail="set operation requires 'field' and 'value' parameters",
                    )

            elif operator and operator not in ["arrayUnion", "replaceOne", "set"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne, set",
                )

        # Check Firestore connectivity after parameter validation
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Process the validated operation
        if "update" in data and isinstance(data["update"], dict):
            update_config = data["update"]
            operator = update_config.get("operator")

            if operator == "arrayUnion":
                # Handle array union operation
                field = update_config.get("field")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None and value is not None

                success = firestore.array_union_subcollection_document(
                    collection=collection,
                    document_id=document_id,
                    subcollection=subcollection,
                    subdocument_id=subdocument_id,
                    field=field,
                    value=value,
                )

                operation_desc = f"Array union operation on field '{field}'"

            elif operator == "replaceOne":
                # Handle replace one operation
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None and match_field is not None
                assert match_value is not None and value is not None

                success = firestore.replace_array_element_subcollection(
                    collection=collection,
                    document_id=document_id,
                    subcollection=subcollection,
                    subdocument_id=subdocument_id,
                    field=field,
                    match_field=match_field,
                    match_value=match_value,
                    new_value=value,
                )

                operation_desc = f"Replace operation on field '{field}' where {match_field}={match_value}"

            elif operator == "set":
                # Handle set nested field operation
                field = update_config.get("field")
                value = update_config.get("value")

                # Type assertion: we've already validated these are not None
                assert field is not None

                success = firestore.set_nested_field_subcollection(
                    collection=collection,
                    document_id=document_id,
                    subcollection=subcollection,
                    subdocument_id=subdocument_id,
                    field_path=field,
                    value=value,
                )

                operation_desc = f"Set nested field operation on '{field}'"

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne, set",
                )
        else:
            # Handle standard document update (existing functionality)
            success = firestore.update_subcollection_document(
                collection=collection,
                document_id=document_id,
                subcollection=subcollection,
                subdocument_id=subdocument_id,
                data=data,
            )
            operation_desc = "Subcollection document update"

        if not success:
            raise HTTPException(
                status_code=404, detail="Document not found or operation failed"
            )

        return SuccessResponse(
            success=True,
            message=f"Subcollection document {subdocument_id} updated successfully - {operation_desc}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating subcollection document: {e!s}"
        )


@router.delete(
    "/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}",
    response_model=SuccessResponse,
)
async def delete_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    subdocument_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete a document from a subcollection.

    Deletes a document by its ID from the specified subcollection within a parent document.
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Delete subcollection document
        success = firestore.delete_subcollection_document(
            collection=collection,
            document_id=document_id,
            subcollection=subcollection,
            subdocument_id=subdocument_id,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return SuccessResponse(
            success=True,
            message=f"Subcollection document {subdocument_id} deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting subcollection document: {e!s}"
        )


@router.get("/health", response_model=SuccessResponse)
async def firestore_health_check(
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Check Firestore service health.

    Verifies that the Firestore service is available and responsive.
    """
    try:
        is_healthy = firestore.health_check()

        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        return SuccessResponse(success=True, message="Firestore service is healthy")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking Firestore health: {e!s}"
        )


# KPI Settings Endpoints


@router.get(
    "/kpi-settings/{organization_id}/{account_id}/{kpi_name}",
    response_model=KPISettingResponse,
)
async def get_kpi_setting(
    organization_id: str,
    account_id: str,
    kpi_name: str,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> KPISettingResponse:
    """
    Get a specific KPI setting for an account.

    Retrieves the metric ID associated with the specified KPI for the given account.
    """
    try:
        # Validate KPI name
        validate_kpi_name(kpi_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get KPI setting
        metric_id = firestore.get_kpi_setting(
            organization_id=organization_id, account_id=account_id, kpi_name=kpi_name
        )

        if metric_id is None:
            raise HTTPException(
                status_code=404,
                detail=f"KPI setting not found for account {account_id} and KPI {kpi_name}",
            )

        return KPISettingResponse(
            success=True, account_id=account_id, kpi_name=kpi_name, metric_id=metric_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving KPI setting: {e!s}"
        )


@router.put("/kpi-settings", response_model=SuccessResponse)
async def update_kpi_setting(
    request: KPISettingRequest,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a specific KPI setting for an account.

    Updates the metric ID associated with the specified KPI for the given account.
    """
    try:
        # Validate KPI name
        validate_kpi_name(request.kpi_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Update KPI setting
        success = firestore.update_kpi_setting(
            organization_id=request.organization_id,
            account_id=request.account_id,
            kpi_name=request.kpi_name,
            metric_id=request.metric_id,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update KPI setting")

        return SuccessResponse(
            success=True,
            message=f"KPI setting updated: {request.kpi_name} for account {request.account_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating KPI setting: {e!s}"
        )


@router.get(
    "/kpi-settings/{organization_id}/{account_id}", response_model=KPISettingsResponse
)
async def get_all_kpi_settings(
    organization_id: str,
    account_id: str,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> KPISettingsResponse:
    """
    Get all KPI settings for an account.

    Retrieves all KPI settings and their associated metric IDs for the given account.
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get all KPI settings
        kpi_settings = firestore.get_all_kpi_settings(
            organization_id=organization_id, account_id=account_id
        )

        if kpi_settings is None:
            # Return empty settings if account doesn't exist
            kpi_settings = {}

        return KPISettingsResponse(
            success=True, account_id=account_id, kpi_settings=kpi_settings
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving KPI settings: {e!s}"
        )


# Funnel Step Endpoints


@router.post("/funnel-steps", response_model=SuccessResponse)
async def create_funnel_step(
    request: FunnelStepRequest,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Create a funnel step.

    Creates a new funnel step. If the step number already exists,
    all subsequent steps will be incremented by 1.
    """
    try:
        # Validate inputs
        validate_funnel_type(request.funnel_type)
        validate_funnel_step_name(request.funnel_step_name)
        validate_big_bet_requirement(request.funnel_type, request.big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Prepare funnel step data
        funnel_step_data = {
            "funnel_step_name": request.funnel_step_name,
            "effectiveness_kpi": request.effectiveness_kpi,
            "efficiency_kpi": request.efficiency_kpi,
            "objective": request.objective,
        }

        # Create funnel step
        success = firestore.create_funnel_step(
            organization_id=request.organization_id,
            account_id=request.account_id,
            funnel_type=request.funnel_type,
            big_bet_name=request.big_bet_name,
            funnel_step_num=request.funnel_step_num,
            funnel_step_data=funnel_step_data,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to create funnel step")

        return SuccessResponse(
            success=True,
            message=f"Funnel step {request.funnel_step_num} created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating funnel step: {e!s}"
        )


@router.get(
    "/funnel-steps/{organization_id}/{account_id}/{funnel_type}",
    response_model=FunnelStepsListResponse,
)
async def list_funnel_steps(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FunnelStepsListResponse:
    """
    List all funnel steps for a specific funnel.

    Retrieves all funnel steps for the specified account and funnel type.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get funnel steps
        funnel_steps = firestore.list_funnel_steps(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
        )

        return FunnelStepsListResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_steps=funnel_steps,
            total=len(funnel_steps),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing funnel steps: {e!s}"
        )


@router.get(
    "/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}",
    response_model=FunnelStepResponse,
)
async def get_funnel_step(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> FunnelStepResponse:
    """
    Get a specific funnel step.

    Retrieves the details of a specific funnel step by its number.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get funnel step
        funnel_step = firestore.get_funnel_step(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
        )

        if funnel_step is None:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return FunnelStepResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            funnel_step_data=funnel_step,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving funnel step: {e!s}"
        )


@router.put(
    "/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}",
    response_model=SuccessResponse,
)
async def update_funnel_step(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    request: FunnelStepRequest,
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a funnel step.

    Updates the details of an existing funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_funnel_step_name(request.funnel_step_name)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Prepare funnel step data
        funnel_step_data = {
            "funnel_step_name": request.funnel_step_name,
            "effectiveness_kpi": request.effectiveness_kpi,
            "efficiency_kpi": request.efficiency_kpi,
            "objective": request.objective,
        }

        # Update funnel step
        success = firestore.update_funnel_step(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            funnel_step_data=funnel_step_data,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return SuccessResponse(
            success=True, message=f"Funnel step {funnel_step_num} updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating funnel step: {e!s}"
        )


@router.delete(
    "/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}",
    response_model=SuccessResponse,
)
async def delete_funnel_step(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet'"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete a funnel step.

    Deletes a funnel step and shifts all subsequent steps down by 1.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Delete funnel step
        success = firestore.delete_funnel_step(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return SuccessResponse(
            success=True, message=f"Funnel step {funnel_step_num} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting funnel step: {e!s}"
        )


# Channel Endpoints


@router.post("/channels/{organization_id}", response_model=ChannelResponse)
async def create_channel(
    organization_id: str,
    channel_data: ChannelRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> ChannelResponse:
    """
    Create a new channel within a funnel step.

    Creates a channel in the specified funnel step. The channel is stored at:
    - Organization funnel: accounts[account_id].funnels.organization[step_num].channels[channel_name]
    - Big bet funnel: accounts[account_id].funnels.big_bets[big_bet_name][step_num].channels[channel_name]
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Create channel
        channel = firestore.create_channel(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_data.channel_name,
            channel_data=channel_data.model_dump(),
        )

        if not channel:
            raise HTTPException(status_code=400, detail="Channel already exists")

        return ChannelResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_data.channel_name,
            channel_data=channel,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating channel: {e!s}"
        ) from e


@router.get(
    "/channels/{organization_id}/{channel_name}", response_model=ChannelResponse
)
async def get_channel(
    organization_id: str,
    channel_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> ChannelResponse:
    """
    Get a channel by name within a funnel step.

    Retrieves the channel from the specified funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get channel
        channel = firestore.get_channel(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
        )

        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        return ChannelResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            channel_data=channel,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting channel: {e!s}"
        ) from e


@router.get("/channels/{organization_id}", response_model=ChannelListResponse)
async def list_channels(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> ChannelListResponse:
    """
    List all channels within a funnel step.

    Retrieves all channels from the specified funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # List channels
        channels = firestore.list_channels(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
        )

        return ChannelListResponse(channels=channels, total=len(channels))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing channels: {e!s}"
        ) from e


@router.put(
    "/channels/{organization_id}/{channel_name}", response_model=ChannelResponse
)
async def update_channel(
    organization_id: str,
    channel_name: str,
    channel_data: ChannelUpdateRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> ChannelResponse:
    """
    Update a channel within a funnel step.

    Updates the specified channel with the provided data.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Update channel
        channel = firestore.update_channel(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            channel_data=channel_data.model_dump(exclude_unset=True),
        )

        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        return ChannelResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            channel_data=channel,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating channel: {e!s}"
        ) from e


@router.delete(
    "/channels/{organization_id}/{channel_name}", response_model=SuccessResponse
)
async def delete_channel(
    organization_id: str,
    channel_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete a channel within a funnel step.

    Deletes the specified channel from the funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Delete channel
        success = firestore.delete_channel(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")

        return SuccessResponse(
            success=True, message=f"Channel '{channel_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting channel: {e!s}"
        ) from e


# Tactic Endpoints


@router.post("/tactics/{organization_id}", response_model=TacticResponse)
async def create_tactic(
    organization_id: str,
    tactic_data: TacticRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TacticResponse:
    """
    Create a new tactic within a channel.

    Creates a tactic in the specified channel within a funnel step. The tactic is stored at:
    - Organization funnel: accounts[account_id].funnels.organization[step_num].channels[channel_name].tactics[tactic_name]
    - Big bet funnel: accounts[account_id].funnels.big_bets[big_bet_name][step_num].channels[channel_name].tactics[tactic_name]
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Create tactic
        tactic = firestore.create_tactic(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_data.tactic_name,
            tactic_data=tactic_data.model_dump(),
        )

        if not tactic:
            raise HTTPException(
                status_code=400, detail="Tactic already exists or channel not found"
            )

        return TacticResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_data.tactic_name,
            tactic_data=tactic,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating tactic: {e!s}"
        ) from e


@router.get("/tactics/{organization_id}/{tactic_name}", response_model=TacticResponse)
async def get_tactic(
    organization_id: str,
    tactic_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TacticResponse:
    """
    Get a tactic by name within a channel.

    Retrieves the tactic from the specified channel within a funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get tactic
        tactic = firestore.get_tactic(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_name,
        )

        if not tactic:
            raise HTTPException(status_code=404, detail="Tactic not found")

        return TacticResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_name,
            tactic_data=tactic,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting tactic: {e!s}"
        ) from e


@router.get("/tactics/{organization_id}", response_model=TacticListResponse)
async def list_tactics(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TacticListResponse:
    """
    List all tactics within a channel.

    Retrieves all tactics from the specified channel within a funnel step.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # List tactics
        tactics = firestore.list_tactics(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
        )

        return TacticListResponse(tactics=tactics, total=len(tactics))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing tactics: {e!s}"
        ) from e


@router.put("/tactics/{organization_id}/{tactic_name}", response_model=TacticResponse)
async def update_tactic(
    organization_id: str,
    tactic_name: str,
    tactic_data: TacticUpdateRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> TacticResponse:
    """
    Update a tactic within a channel.

    Updates the specified tactic with the provided data.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Update tactic
        tactic = firestore.update_tactic(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_name,
            tactic_data=tactic_data.model_dump(exclude_unset=True),
        )

        if not tactic:
            raise HTTPException(status_code=404, detail="Tactic not found")

        return TacticResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_name,
            tactic_data=tactic,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating tactic: {e!s}"
        ) from e


@router.delete(
    "/tactics/{organization_id}/{tactic_name}", response_model=SuccessResponse
)
async def delete_tactic(
    organization_id: str,
    tactic_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(
        ..., description="Funnel type ('organization' or 'big_bet')"
    ),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: str | None = Query(
        None, description="Big bet name (required if funnel_type is 'big_bet')"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Delete a tactic within a channel.

    Deletes the specified tactic from the channel.
    """
    try:
        # Validate inputs
        validate_funnel_type(funnel_type)
        validate_big_bet_requirement(funnel_type, big_bet_name)

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Delete tactic
        success = firestore.delete_tactic(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_name,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Tactic not found")

        return SuccessResponse(
            success=True, message=f"Tactic '{tactic_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting tactic: {e!s}"
        ) from e


# Organization Member Management Endpoints


class OrganizationMember(BaseModel):
    """Response model for organization member."""

    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: str | None = Field(None, description="User first name")
    last_name: str | None = Field(None, description="User last name")
    access_level: str = Field(..., description="Access level: admin, view, or owner")
    added_date: str | None = Field(None, description="Date when user was added")


class OrganizationMembersResponse(BaseModel):
    """Response model for organization members list."""

    members: list[OrganizationMember] = Field(..., description="List of members")
    total: int = Field(..., description="Total number of members")


class InviteMemberRequest(BaseModel):
    """Request model for inviting a member to organization."""

    email: str = Field(..., description="Email of user to invite")
    access_level: str = Field(..., description="Access level to grant: admin or view")
    account_permissions: dict[str, str] | None = Field(
        None,
        description="Account permissions to grant (only for view-role users). Keys are account IDs, values are 'edit' or 'view'",
    )


class UpdateMemberAccessRequest(BaseModel):
    """Request model for updating member access level."""

    access_level: str = Field(..., description="New access level: admin or view")


@router.get(
    "/organizations/{organization_id}/members",
    response_model=OrganizationMembersResponse,
)
async def get_organization_members(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> OrganizationMembersResponse:
    """
    Get all members of an organization.

    Retrieves all users who have access to the specified organization.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `account_id` (query): Account ID for validation

    **Returns:**
    - `members`: List of organization members with their details
    - `total`: Total number of members

    **Example:**
    ```
    GET /api/v1/firestore/organizations/org_123/members?account_id=a000001
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Query all users and filter those with access to this organization
        all_users = firestore.list_documents(collection="users")

        members = []
        for user_doc in all_users:
            user_id = user_doc.get("id", "")
            permissions = user_doc.get("permissions", {})
            org_permissions = permissions.get("organizations", {})

            if organization_id in org_permissions:
                access_level = org_permissions[organization_id]
                member = OrganizationMember(
                    user_id=user_id,
                    email=user_doc.get("profile", {}).get("email", ""),
                    first_name=user_doc.get("profile", {}).get("first_name"),
                    last_name=user_doc.get("profile", {}).get("last_name"),
                    access_level=access_level,
                    added_date=user_doc.get("created_at"),
                )
                members.append(member)

        return OrganizationMembersResponse(members=members, total=len(members))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving organization members: {e!s}"
        )


@router.post(
    "/organizations/{organization_id}/members/invite", response_model=SuccessResponse
)
async def invite_member_to_organization(
    organization_id: str,
    request: InviteMemberRequest,
    current_user_id: str = Query(..., description="ID of the user sending invitation"),
    current_user_name: str = Query(
        ..., description="Name of the user sending invitation"
    ),
    organization_name: str = Query(..., description="Name of the organization"),
    firestore: FirestoreService = Depends(get_firestore_service),
    email_service=Depends(get_email_service),
) -> SuccessResponse:
    """
    Invite a member to an organization.

    Grants the specified user access to the organization with the given access level.
    The user must already exist in the system.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `email` (body): Email of the user to invite
    - `access_level` (body): Access level to grant (admin or view)

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message

    **Example:**
    ```json
    POST /api/v1/firestore/organizations/org_123/members/invite
    {
        "email": "newuser@example.com",
        "access_level": "view"
    }
    ```
    """
    try:
        # Validate access level
        if request.access_level not in ["admin", "view"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid access_level. Must be 'admin' or 'view'",
            )

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Find user by email
        users = firestore.query_documents(
            collection="users", field="email", operator="==", value=request.email
        )

        if not users:
            # User doesn't exist - create an invitation
            invitation_id = str(uuid.uuid4())
            invitation_token = str(uuid.uuid4())
            now = datetime.utcnow()
            expires_at = now + timedelta(days=7)

            invitation_data = {
                "id": invitation_id,
                "email": request.email,
                "organization_id": organization_id,
                "access_level": request.access_level,
                "invited_by": current_user_id,
                "invited_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "status": "pending",
                "invitation_token": invitation_token,
                "inviter_name": current_user_name,
                "organization_name": organization_name,
            }

            # Add account permissions if provided for view-role users
            if request.access_level == "view" and request.account_permissions:
                invitation_data["account_permissions"] = request.account_permissions

            # Create invitation in Firestore
            firestore.create_document(
                collection="invitations",
                document_id=invitation_id,
                data=invitation_data,
            )

            # Send invitation email
            email_sent = email_service.send_invitation_email(
                to_email=request.email,
                inviter_name=current_user_name,
                organization_name=organization_name,
                access_level=request.access_level,
                invitation_token=invitation_token,
            )

            if not email_sent:
                # Log the error but don't fail the invitation creation
                logger.error(
                    f"Failed to send invitation email to {request.email} for organization {organization_id}. "
                    f"Invitation was created but email was not sent."
                )

            return SuccessResponse(
                success=True,
                message=f"Invitation sent to {request.email}. They will receive an email to join the organization.",
            )

        user_doc = users[0]
        user_id = user_doc.get("id")

        if not user_id:
            raise HTTPException(
                status_code=500, detail="User document missing ID field"
            )

        # Update user's permissions to include this organization
        success = firestore.set_nested_field(
            collection="users",
            document_id=user_id,
            field_path=f"permissions.organizations.{organization_id}",
            value=request.access_level,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update user permissions"
            )

        # Invalidate user cache after granting organization permissions
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user_id)
        logger.info(
            f"Invalidated cache for user {user_id} after granting organization {organization_id} permissions"
        )

        # If access level is view and account permissions are provided, grant them
        if request.access_level == "view" and request.account_permissions:
            for account_id, access_level in request.account_permissions.items():
                if access_level not in ["edit", "view"]:
                    continue  # Skip invalid access levels

                firestore.set_nested_field(
                    collection="users",
                    document_id=user_id,
                    field_path=f"permissions.account_permissions.{account_id}",
                    value=access_level,
                )

            # Cache was already invalidated above after organization permission grant

        return SuccessResponse(
            success=True,
            message=f"User {request.email} added to organization with {request.access_level} access",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error inviting member: {e!s}"
        ) from e


@router.put(
    "/organizations/{organization_id}/members/{user_id}",
    response_model=SuccessResponse,
)
async def update_member_access_level(
    organization_id: str,
    user_id: str,
    request: UpdateMemberAccessRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a member's access level in an organization.

    Changes the access level of an existing member in the organization.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `user_id` (path): User ID to update
    - `access_level` (body): New access level (admin or view)
    - `account_id` (query): Account ID for validation

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message

    **Example:**
    ```json
    PUT /api/v1/firestore/organizations/org_123/members/user_456?account_id=a000001
    {
        "access_level": "admin"
    }
    ```
    """
    try:
        # Validate access level
        if request.access_level not in ["admin", "view"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid access_level. Must be 'admin' or 'view'",
            )

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get current user permissions to check if we're changing from admin to view
        user_doc = firestore.get_document("users", user_id)
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if target user is a super admin (cannot modify their permissions)
        user_email = user_doc.get("email", "") or user_doc.get("profile", {}).get(
            "email", ""
        )
        if user_email.lower().endswith("@ken-e.ai"):
            raise HTTPException(
                status_code=403,
                detail="Cannot modify permissions for KEN-E support team members",
            )

        current_permissions = user_doc.get("permissions", {})
        current_org_role = current_permissions.get("organizations", {}).get(
            organization_id
        )

        # Update user's permission level for this organization
        success = firestore.set_nested_field(
            collection="users",
            document_id=user_id,
            field_path=f"permissions.organizations.{organization_id}",
            value=request.access_level,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="User not found or update failed"
            )

        # Invalidate user cache after updating organization permissions
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(user_id)
        logger.info(
            f"Invalidated cache for user {user_id} after updating organization {organization_id} permissions"
        )

        # If changing from admin to view, remove all account permissions (they need to be re-granted)
        # If changing from view to admin, remove explicit account permissions (they now have implicit access)
        if (current_org_role == "admin" and request.access_level == "view") or (
            current_org_role == "view" and request.access_level == "admin"
        ):
            account_permissions = current_permissions.get("account_permissions", {})

            # Remove account permissions for accounts in this organization
            # Note: This is a simplified implementation - ideally we'd check which accounts belong to this org
            firestore_db = firestore.get_client()
            user_ref = firestore_db.collection("users").document(user_id)

            # Remove the entire account_permissions field if changing to admin
            if request.access_level == "admin" and account_permissions:
                from google.cloud.firestore_v1 import DELETE_FIELD

                updates = {}
                for account_id in account_permissions:
                    updates[f"permissions.account_permissions.{account_id}"] = (
                        DELETE_FIELD
                    )
                if updates:
                    user_ref.update(updates)

            # Invalidate user cache
            from ..auth.cached_user_context import get_cached_user_context_service

            cached_user_service = get_cached_user_context_service()
            cached_user_service.invalidate_user_context(user_id)

        return SuccessResponse(
            success=True,
            message=f"User access level updated to {request.access_level}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating member access: {e!s}"
        )


@router.delete(
    "/organizations/{organization_id}/members/{user_id}",
    response_model=SuccessResponse,
)
async def remove_member_from_organization(
    organization_id: str,
    user_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Remove a member from an organization.

    Revokes the user's access to the organization.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `user_id` (path): User ID to remove
    - `account_id` (query): Account ID for validation

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message

    **Example:**
    ```
    DELETE /api/v1/firestore/organizations/org_123/members/user_456?account_id=a000001
    ```
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get the user document
        user_doc = firestore.get_document(collection="users", document_id=user_id)

        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if target user is a super admin (cannot remove them)
        user_email = user_doc.get("email", "") or user_doc.get("profile", {}).get(
            "email", ""
        )
        if user_email.lower().endswith("@ken-e.ai"):
            raise HTTPException(
                status_code=403,
                detail="Cannot remove KEN-E support team members from organizations",
            )

        # Remove the organization from user's permissions
        permissions = user_doc.get("permissions", {})
        organizations = permissions.get("organizations", {})

        if organization_id in organizations:
            del organizations[organization_id]

            # Update the user document
            success = firestore.update_document(
                collection="users",
                document_id=user_id,
                data={"permissions": permissions},
            )

            if not success:
                raise HTTPException(
                    status_code=500, detail="Failed to update user permissions"
                )

            return SuccessResponse(
                success=True, message="User removed from organization successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="User does not have access to this organization",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error removing member: {e!s}"
        ) from e


# Invitation Management Endpoints


class Invitation(BaseModel):
    """Model for an invitation."""

    id: str = Field(..., description="Unique invitation ID")
    email: str = Field(..., description="Email of invited user")
    organization_id: str = Field(..., description="Organization ID")
    access_level: str = Field(..., description="Access level: admin or view")
    invited_by: str = Field(..., description="User ID who sent the invitation")
    invited_at: str = Field(..., description="Invitation timestamp")
    expires_at: str = Field(..., description="Expiration timestamp")
    status: str = Field(..., description="Status: pending, accepted, or expired")
    invitation_token: str = Field(
        ..., description="Unique token for accepting invitation"
    )
    inviter_name: str | None = Field(None, description="Name of the inviter")
    organization_name: str | None = Field(None, description="Name of the organization")
    account_permissions: dict[str, str] | None = Field(
        None, description="Account permissions for view-role users"
    )


class InvitationListResponse(BaseModel):
    """Response model for invitation list."""

    invitations: list[Invitation] = Field(..., description="List of invitations")
    total: int = Field(..., description="Total number of invitations")


class AcceptInvitationRequest(BaseModel):
    """Request model for accepting an invitation."""

    user_id: str = Field(..., description="ID of the user accepting the invitation")
    user_email: str = Field(
        ..., description="Email of the user accepting the invitation"
    )
    user_name: str | None = Field(None, description="Name of the user accepting")


@router.post(
    "/organizations/{organization_id}/invitations", response_model=SuccessResponse
)
async def create_invitation(
    organization_id: str,
    request: InviteMemberRequest,
    current_user_id: str = Query(
        ..., description="ID of the user creating the invitation"
    ),
    current_user_name: str = Query(
        ..., description="Name of the user creating the invitation"
    ),
    organization_name: str = Query(..., description="Name of the organization"),
    firestore: FirestoreService = Depends(get_firestore_service),
    email_service=Depends(get_email_service),
) -> SuccessResponse:
    """
    Create an invitation for a new user to join the organization.

    Creates a pending invitation and sends an email to the user.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `email` (body): Email of the user to invite
    - `access_level` (body): Access level to grant (admin or view)
    - `current_user_id` (query): ID of the user creating the invitation
    - `current_user_name` (query): Name of the user creating the invitation
    - `organization_name` (query): Name of the organization

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    """
    try:
        # Validate access level
        if request.access_level not in ["admin", "view"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid access_level. Must be 'admin' or 'view'",
            )

        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Generate invitation data
        invitation_id = str(uuid.uuid4())
        invitation_token = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=7)

        invitation_data = {
            "id": invitation_id,
            "email": request.email,
            "organization_id": organization_id,
            "access_level": request.access_level,
            "invited_by": current_user_id,
            "invited_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "pending",
            "invitation_token": invitation_token,
            "inviter_name": current_user_name,
            "organization_name": organization_name,
        }

        # Create invitation in Firestore
        firestore.create_document(
            collection="invitations",
            document_id=invitation_id,
            data=invitation_data,
        )

        # Send invitation email
        email_sent = email_service.send_invitation_email(
            to_email=request.email,
            inviter_name=current_user_name,
            organization_name=organization_name,
            access_level=request.access_level,
            invitation_token=invitation_token,
        )

        if not email_sent:
            # Log the issue but don't fail the invitation creation
            logger.error(
                f"Failed to send invitation email to {request.email} for account {account_id}. "
                f"Invitation was created but email was not sent. Consider queueing for retry."
            )

        return SuccessResponse(
            success=True,
            message=f"Invitation sent to {request.email}",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating invitation: {e!s}")


@router.get(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationListResponse,
)
async def get_organization_invitations(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    status: str | None = Query(
        None, description="Filter by status: pending, accepted, or expired"
    ),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> InvitationListResponse:
    """
    Get all invitations for an organization.

    Retrieves all invitations sent for the specified organization.

    **Parameters:**
    - `organization_id` (path): Organization ID
    - `account_id` (query): Account ID for validation
    - `status` (query): Optional status filter

    **Returns:**
    - `invitations`: List of invitations
    - `total`: Total number of invitations
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Query invitations for this organization
        invitations = firestore.query_documents(
            collection="invitations",
            field="organization_id",
            operator="==",
            value=organization_id,
        )

        # Filter by status if provided
        if status:
            invitations = [inv for inv in invitations if inv.get("status") == status]

        # Check for expired invitations and update their status
        now = datetime.utcnow()
        for invitation in invitations:
            if invitation.get("status") == "pending":
                expires_at = datetime.fromisoformat(invitation.get("expires_at", ""))
                if expires_at < now:
                    # Update status to expired
                    firestore.update_document(
                        collection="invitations",
                        document_id=invitation.get("id"),
                        data={"status": "expired"},
                    )
                    invitation["status"] = "expired"

        # Convert to Invitation models
        invitation_models = []
        for inv in invitations:
            invitation_models.append(Invitation(**inv))

        return InvitationListResponse(
            invitations=invitation_models, total=len(invitation_models)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving invitations: {e!s}"
        )


@router.get("/invitations/verify/{token}", response_model=Invitation)
async def verify_invitation_token(
    token: str,
    firestore: FirestoreService = Depends(get_firestore_service),
) -> Invitation:
    """
    Verify an invitation token.

    Checks if the invitation token is valid and returns the invitation details.

    **Parameters:**
    - `token` (path): Invitation token

    **Returns:**
    - Invitation details if valid
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Find invitation by token
        invitations = firestore.query_documents(
            collection="invitations",
            field="invitation_token",
            operator="==",
            value=token,
        )

        if not invitations:
            raise HTTPException(status_code=404, detail="Invalid invitation token")

        invitation = invitations[0]

        # Check if expired
        expires_at = datetime.fromisoformat(invitation.get("expires_at", ""))
        if expires_at < datetime.utcnow():
            # Update status to expired
            firestore.update_document(
                collection="invitations",
                document_id=invitation.get("id"),
                data={"status": "expired"},
            )
            raise HTTPException(status_code=400, detail="Invitation has expired")

        # Check if already accepted
        if invitation.get("status") == "accepted":
            raise HTTPException(
                status_code=400, detail="Invitation has already been accepted"
            )

        return Invitation(**invitation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error verifying invitation: {e!s}"
        )


@router.post("/invitations/accept/{token}", response_model=SuccessResponse)
async def accept_invitation(
    token: str,
    request: AcceptInvitationRequest,
    firestore: FirestoreService = Depends(get_firestore_service),
    email_service=Depends(get_email_service),
) -> SuccessResponse:
    """
    Accept an invitation.

    Accepts the invitation and grants the user access to the organization.

    **Parameters:**
    - `token` (path): Invitation token
    - `user_id` (body): ID of the user accepting
    - `user_email` (body): Email of the user accepting
    - `user_name` (body): Name of the user accepting

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Verify the invitation first
        invitations = firestore.query_documents(
            collection="invitations",
            field="invitation_token",
            operator="==",
            value=token,
        )

        if not invitations:
            raise HTTPException(status_code=404, detail="Invalid invitation token")

        invitation = invitations[0]

        # Verify email matches
        if invitation.get("email") != request.user_email:
            raise HTTPException(
                status_code=400,
                detail="Email does not match the invitation",
            )

        # Check status
        if invitation.get("status") == "accepted":
            raise HTTPException(
                status_code=400,
                detail="Invitation has already been accepted",
            )

        # Grant access to the organization
        success = firestore.set_nested_field(
            collection="users",
            document_id=request.user_id,
            field_path=f"permissions.organizations.{invitation['organization_id']}",
            value=invitation["access_level"],
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to grant organization access",
            )

        # Invalidate user cache after granting organization access via invitation
        from ..auth.cached_user_context import get_cached_user_context_service

        cached_user_service = get_cached_user_context_service()
        cached_user_service.invalidate_user_context(request.user_id)
        logger.info(
            f"Invalidated cache for user {request.user_id} after accepting invitation to organization {invitation['organization_id']}"
        )

        # Grant account permissions if provided for view-role users
        if invitation.get("access_level") == "view" and invitation.get(
            "account_permissions"
        ):
            for account_id, access_level in invitation["account_permissions"].items():
                if access_level not in ["edit", "view"]:
                    continue  # Skip invalid access levels

                firestore.set_nested_field(
                    collection="users",
                    document_id=request.user_id,
                    field_path=f"permissions.account_permissions.{account_id}",
                    value=access_level,
                )

            # Invalidate user cache
            from ..auth.cached_user_context import get_cached_user_context_service

            cached_user_service = get_cached_user_context_service()
            cached_user_service.invalidate_user_context(request.user_id)

        # Update invitation status
        firestore.update_document(
            collection="invitations",
            document_id=invitation["id"],
            data={
                "status": "accepted",
                "accepted_at": datetime.utcnow().isoformat(),
                "accepted_by": request.user_id,
            },
        )

        # Send notification to inviter
        inviter_email = None
        if invitation.get("invited_by"):
            inviter_doc = firestore.get_document(
                collection="users",
                document_id=invitation["invited_by"],
            )
            if inviter_doc:
                inviter_email = inviter_doc.get("profile", {}).get("email")

        if inviter_email:
            email_service.send_invitation_accepted_notification(
                to_email=inviter_email,
                to_name=invitation.get("inviter_name", inviter_email),
                accepter_name=request.user_name or request.user_email,
                accepter_email=request.user_email,
                organization_name=invitation.get(
                    "organization_name", "the organization"
                ),
                access_level=invitation.get("access_level", "member"),
            )

        return SuccessResponse(
            success=True,
            message="Invitation accepted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error accepting invitation: {e!s}"
        )


@router.delete("/invitations/{invitation_id}", response_model=SuccessResponse)
async def cancel_invitation(
    invitation_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Cancel a pending invitation.

    Cancels a pending invitation by setting its status to cancelled.

    **Parameters:**
    - `invitation_id` (path): Invitation ID
    - `account_id` (query): Account ID for validation

    **Returns:**
    - `success`: Boolean indicating operation success
    - `message`: Success message
    """
    try:
        # Check Firestore connectivity
        is_healthy = firestore.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=FIRESTORE_UNAVAILABLE_MESSAGE)

        # Get the invitation
        invitation = firestore.get_document(
            collection="invitations",
            document_id=invitation_id,
        )

        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        # Check if already accepted
        if invitation.get("status") == "accepted":
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel an accepted invitation",
            )

        # Update status to cancelled
        success = firestore.update_document(
            collection="invitations",
            document_id=invitation_id,
            data={
                "status": "cancelled",
                "cancelled_at": datetime.utcnow().isoformat(),
            },
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to cancel invitation",
            )

        return SuccessResponse(
            success=True,
            message="Invitation cancelled successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error cancelling invitation: {e!s}"
        )


@router.get("/debug/documents/{collection}/{document_id}")
async def debug_get_document(
    collection: str,
    document_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
) -> dict[str, Any]:
    """
    Debug endpoint to test document path routing.

    This is a simple endpoint to verify that the routing works correctly.
    """
    return {
        "message": "Debug endpoint working",
        "collection": collection,
        "document_id": document_id,
        "account_id": account_id,
        "method": "GET",
    }
