"""Firestore router for CRUD operations on Google Firestore."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import BaseRequest, SuccessResponse

router = APIRouter(tags=["firestore"])

# Constants
FIRESTORE_UNAVAILABLE_MESSAGE = "Firestore service unavailable. Please try again later."
ACCOUNT_ID_VALIDATION_DESCRIPTION = "Account ID for validation"
DOCUMENT_NOT_FOUND_MESSAGE = "Document not found"


# Pydantic models for Firestore operations

class FirestoreDocumentRequest(BaseRequest):
    """Request model for Firestore document operations."""
    
    collection: str = Field(..., description="Firestore collection name")
    document_id: Optional[str] = Field(None, description="Document ID (auto-generated if not provided)")
    data: Dict[str, Any] = Field(..., description="Document data")


class FirestoreDocumentResponse(BaseModel):
    """Response model for Firestore document operations."""
    
    success: bool = Field(..., description="Operation success status")
    document_id: str = Field(..., description="Document ID")
    data: Optional[Dict[str, Any]] = Field(None, description="Document data")


class FirestoreDocumentListResponse(BaseModel):
    """Response model for Firestore document list operations."""
    
    documents: List[Dict[str, Any]] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")


class FirestoreQueryRequest(BaseRequest):
    """Request model for Firestore document queries."""
    
    collection: str = Field(..., description="Firestore collection name")
    field: Optional[str] = Field(None, description="Field to query")
    operator: Optional[str] = Field(None, description="Query operator (==, !=, <, <=, >, >=, in, not-in, array-contains, array-contains-any)")
    value: Optional[Any] = Field(None, description="Value to compare against")
    limit: Optional[int] = Field(None, description="Maximum number of documents to return")


class KPISettingRequest(BaseRequest):
    """Request model for KPI setting operations."""
    
    organization_id: str = Field(..., description="The unique identifier for the organization")
    account_id: str = Field(..., description="The unique identifier for the account")
    kpi_name: str = Field(..., description="KPI name: income_kpi, marketing_cost_kpi, or net_income_kpi")
    metric_id: str = Field(..., description="The unique identifier for the metric")


class KPISettingResponse(BaseModel):
    """Response model for KPI setting operations."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    kpi_name: str = Field(..., description="KPI name")
    metric_id: Optional[str] = Field(None, description="Metric ID associated with the KPI")


class KPISettingsResponse(BaseModel):
    """Response model for all KPI settings."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    kpi_settings: Dict[str, str] = Field(..., description="Dictionary of KPI names to metric IDs")


class FunnelStepRequest(BaseRequest):
    """Request model for funnel step operations."""
    
    organization_id: str = Field(..., description="Unique identifier for the organization")
    account_id: str = Field(..., description="Unique identifier for the account")
    funnel_type: str = Field(..., description="Type of funnel: 'organization' or 'big_bet'")
    big_bet_name: Optional[str] = Field(None, description="Name of the big bet (required if funnel_type is 'big_bet')")
    funnel_step_num: int = Field(..., description="Step number in the conversion funnel", ge=1)
    funnel_step_name: str = Field(..., description="Name of the funnel step: 'awareness', 'consideration', 'conversion', or 'loyalty'")
    effectiveness_kpi: str = Field(..., description="Metric ID for effectiveness calculation")
    efficiency_kpi: str = Field(..., description="Metric ID for efficiency calculation")
    objective: str = Field(..., description="Text of the funnel step objective")


class FunnelStepResponse(BaseModel):
    """Response model for funnel step operations."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: Optional[str] = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    funnel_step_data: Optional[Dict[str, Any]] = Field(None, description="Funnel step data")


class FunnelStepsListResponse(BaseModel):
    """Response model for listing funnel steps."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: Optional[str] = Field(None, description="Big bet name (if applicable)")
    funnel_steps: List[Dict[str, Any]] = Field(..., description="List of funnel steps")
    total: int = Field(..., description="Total number of funnel steps")


class ChannelRequest(BaseModel):
    """Request model for channel operations."""
    
    channel_name: str = Field(..., description="Name of the channel as defined by the user")
    effectiveness_kpi: str = Field(..., description="Metric ID for effectiveness calculation within the channel")
    efficiency_kpi: str = Field(..., description="Metric ID for efficiency calculation within the channel and funnel step")
    supporting_metrics: List[str] = Field(..., description="List of metrics for evaluating channel performance")


class ChannelUpdateRequest(BaseModel):
    """Request model for updating channel operations."""
    
    channel_name: Optional[str] = Field(None, description="Name of the channel as defined by the user")
    effectiveness_kpi: Optional[str] = Field(None, description="Metric ID for effectiveness calculation within the channel")
    efficiency_kpi: Optional[str] = Field(None, description="Metric ID for efficiency calculation within the channel and funnel step")
    supporting_metrics: Optional[List[str]] = Field(None, description="List of metrics for evaluating channel performance")


class ChannelResponse(BaseModel):
    """Response model for channel operations."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: Optional[str] = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    channel_name: str = Field(..., description="Channel name")
    channel_data: Optional[Dict[str, Any]] = Field(None, description="Channel data")


class ChannelListResponse(BaseModel):
    """Response model for listing channels."""
    
    channels: List[Dict[str, Any]] = Field(..., description="List of channels")
    total: int = Field(..., description="Total number of channels")


class TacticRequest(BaseModel):
    """Request model for tactic operations."""
    
    tactic_name: str = Field(..., description="Name of the tactic as defined by the user")
    effectiveness_kpi: str = Field(..., description="Metric ID for effectiveness calculation within the tactic")
    efficiency_kpi: str = Field(..., description="Metric ID for efficiency calculation within the tactic")
    supporting_metrics: List[str] = Field(..., description="List of metrics for evaluating tactic performance")


class TacticUpdateRequest(BaseModel):
    """Request model for updating tactic operations."""
    
    tactic_name: Optional[str] = Field(None, description="Name of the tactic as defined by the user")
    effectiveness_kpi: Optional[str] = Field(None, description="Metric ID for effectiveness calculation within the tactic")
    efficiency_kpi: Optional[str] = Field(None, description="Metric ID for efficiency calculation within the tactic")
    supporting_metrics: Optional[List[str]] = Field(None, description="List of metrics for evaluating tactic performance")


class TacticResponse(BaseModel):
    """Response model for tactic operations."""
    
    success: bool = Field(..., description="Operation success status")
    account_id: str = Field(..., description="Account ID")
    funnel_type: str = Field(..., description="Type of funnel")
    big_bet_name: Optional[str] = Field(None, description="Big bet name (if applicable)")
    funnel_step_num: int = Field(..., description="Step number")
    channel_name: str = Field(..., description="Channel name")
    tactic_name: str = Field(..., description="Tactic name")
    tactic_data: Optional[Dict[str, Any]] = Field(None, description="Tactic data")


class TacticListResponse(BaseModel):
    """Response model for listing tactics."""
    
    tactics: List[Dict[str, Any]] = Field(..., description="List of tactics")
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
            detail=f"Invalid kpi_name. Must be one of: {', '.join(VALID_KPI_NAMES)}"
        )


def validate_funnel_type(funnel_type: str) -> None:
    """Validate that the funnel type is one of the allowed values."""
    if funnel_type not in VALID_FUNNEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid funnel_type. Must be one of: {', '.join(VALID_FUNNEL_TYPES)}"
        )


def validate_funnel_step_name(funnel_step_name: str) -> None:
    """Validate that the funnel step name is one of the allowed values."""
    if funnel_step_name not in VALID_FUNNEL_STEP_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid funnel_step_name. Must be one of: {', '.join(VALID_FUNNEL_STEP_NAMES)}"
        )


def validate_big_bet_requirement(funnel_type: str, big_bet_name: Optional[str]) -> None:
    """Validate that big_bet_name is provided when funnel_type is 'big_bet'."""
    if funnel_type == "big_bet" and not big_bet_name:
        raise HTTPException(
            status_code=400,
            detail="big_bet_name is required when funnel_type is 'big_bet'"
        )
    elif funnel_type == "organization" and big_bet_name:
        raise HTTPException(
            status_code=400,
            detail="big_bet_name should not be provided when funnel_type is 'organization'"
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
            data=request.data
        )

        return FirestoreDocumentResponse(
            success=True,
            document_id=document_id,
            data=request.data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating document: {str(e)}"
        )


@router.get("/documents/{collection}/{document_id}", response_model=FirestoreDocumentResponse)
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
        doc_data = firestore.get_document(collection=collection, document_id=document_id)
        
        if doc_data is None:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_MESSAGE)

        return FirestoreDocumentResponse(
            success=True,
            document_id=document_id,
            data=doc_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving document: {str(e)}"
        )


@router.put("/documents/{collection}/{document_id}", response_model=SuccessResponse)
async def update_document(
    collection: str,
    document_id: str,
    data: Dict[str, Any],
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a document in Firestore.
    
    Updates an existing document with the provided data. Supports three modes:
    
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
                
                if not field or value is None:
                    raise HTTPException(
                        status_code=400, 
                        detail="arrayUnion operation requires 'field' and 'value' parameters"
                    )
                    
            elif operator == "replaceOne":
                # Validate replaceOne parameters
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")
                
                if not all([field, match_field, match_value is not None, value is not None]):
                    raise HTTPException(
                        status_code=400,
                        detail="replaceOne operation requires 'field', 'matchField', 'matchValue', and 'value' parameters"
                    )
                    
            elif operator and operator not in ["arrayUnion", "replaceOne"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne"
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
                    value=value
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
                    new_value=value
                )
                
                operation_desc = f"Replace operation on field '{field}' where {match_field}={match_value}"
                
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne"
                )
        else:
            # Handle standard document update (existing functionality)
            success = firestore.update_document(
                collection=collection,
                document_id=document_id,
                data=data
            )
            operation_desc = "Document update"
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or operation failed")

        return SuccessResponse(
            success=True,
            message=f"Document {document_id} updated successfully - {operation_desc}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating document: {str(e)}"
        )


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
        success = firestore.delete_document(collection=collection, document_id=document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return SuccessResponse(
            success=True,
            message=f"Document {document_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting document: {str(e)}"
        )


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
                limit=request.limit
            )
        else:
            documents = firestore.list_documents(
                collection=request.collection,
                limit=request.limit
            )

        return FirestoreDocumentListResponse(
            documents=documents,
            total=len(documents)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying documents: {str(e)}"
        )


@router.get("/collections/{collection}/documents", response_model=FirestoreDocumentListResponse)
async def list_collection_documents(
    collection: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    limit: Optional[int] = Query(None, description="Maximum number of documents to return"),
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

        return FirestoreDocumentListResponse(
            documents=documents,
            total=len(documents)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing documents: {str(e)}"
        )


# Subcollection Document Operations

@router.post("/documents/{collection}/{document_id}/{subcollection}", response_model=FirestoreDocumentResponse)
async def create_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    data: Dict[str, Any],
    subdocument_id: Optional[str] = Query(None, description="Subdocument ID (auto-generated if not provided)"),
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
            data=data
        )

        return FirestoreDocumentResponse(
            success=True,
            document_id=created_subdocument_id,
            data=data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating subcollection document: {str(e)}"
        )


@router.get("/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}", response_model=FirestoreDocumentResponse)
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
            subdocument_id=subdocument_id
        )
        
        if doc_data is None:
            raise HTTPException(status_code=404, detail=DOCUMENT_NOT_FOUND_MESSAGE)

        return FirestoreDocumentResponse(
            success=True,
            document_id=subdocument_id,
            data=doc_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving subcollection document: {str(e)}"
        )


@router.put("/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}", response_model=SuccessResponse)
async def update_subcollection_document(
    collection: str,
    document_id: str,
    subcollection: str,
    subdocument_id: str,
    data: Dict[str, Any],
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    firestore: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """
    Update a document in a subcollection.
    
    Updates an existing document in the specified subcollection with the provided data. Supports three modes:
    
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
                
                if not field or value is None:
                    raise HTTPException(
                        status_code=400, 
                        detail="arrayUnion operation requires 'field' and 'value' parameters"
                    )
                    
            elif operator == "replaceOne":
                # Validate replaceOne parameters
                field = update_config.get("field")
                match_field = update_config.get("matchField")
                match_value = update_config.get("matchValue")
                value = update_config.get("value")
                
                if not all([field, match_field, match_value is not None, value is not None]):
                    raise HTTPException(
                        status_code=400,
                        detail="replaceOne operation requires 'field', 'matchField', 'matchValue', and 'value' parameters"
                    )
                    
            elif operator and operator not in ["arrayUnion", "replaceOne"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne"
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
                    value=value
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
                    new_value=value
                )
                
                operation_desc = f"Replace operation on field '{field}' where {match_field}={match_value}"
                
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported update operator: {operator}. Supported operators: arrayUnion, replaceOne"
                )
        else:
            # Handle standard document update (existing functionality)
            success = firestore.update_subcollection_document(
                collection=collection,
                document_id=document_id,
                subcollection=subcollection,
                subdocument_id=subdocument_id,
                data=data
            )
            operation_desc = "Subcollection document update"
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or operation failed")

        return SuccessResponse(
            success=True,
            message=f"Subcollection document {subdocument_id} updated successfully - {operation_desc}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating subcollection document: {str(e)}"
        )


@router.delete("/documents/{collection}/{document_id}/{subcollection}/{subdocument_id}", response_model=SuccessResponse)
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
            subdocument_id=subdocument_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        return SuccessResponse(
            success=True,
            message=f"Subcollection document {subdocument_id} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting subcollection document: {str(e)}"
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

        return SuccessResponse(
            success=True,
            message="Firestore service is healthy"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking Firestore health: {str(e)}"
        )


# KPI Settings Endpoints

@router.get("/kpi-settings/{organization_id}/{account_id}/{kpi_name}", response_model=KPISettingResponse)
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
        metric_id = firestore.get_kpi_setting(organization_id=organization_id, account_id=account_id, kpi_name=kpi_name)
        
        if metric_id is None:
            raise HTTPException(
                status_code=404, 
                detail=f"KPI setting not found for account {account_id} and KPI {kpi_name}"
            )

        return KPISettingResponse(
            success=True,
            account_id=account_id,
            kpi_name=kpi_name,
            metric_id=metric_id
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving KPI setting: {str(e)}"
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
            metric_id=request.metric_id
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update KPI setting")

        return SuccessResponse(
            success=True,
            message=f"KPI setting updated: {request.kpi_name} for account {request.account_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating KPI setting: {str(e)}"
        )


@router.get("/kpi-settings/{organization_id}/{account_id}", response_model=KPISettingsResponse)
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
            organization_id=organization_id,
            account_id=account_id)
        
        if kpi_settings is None:
            # Return empty settings if account doesn't exist
            kpi_settings = {}

        return KPISettingsResponse(
            success=True,
            account_id=account_id,
            kpi_settings=kpi_settings
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving KPI settings: {str(e)}"
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
            "objective": request.objective
        }

        # Create funnel step
        success = firestore.create_funnel_step(
            organization_id=request.organization_id,
            account_id=request.account_id,
            funnel_type=request.funnel_type,
            big_bet_name=request.big_bet_name,
            funnel_step_num=request.funnel_step_num,
            funnel_step_data=funnel_step_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create funnel step")

        return SuccessResponse(
            success=True,
            message=f"Funnel step {request.funnel_step_num} created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating funnel step: {str(e)}"
        )


@router.get("/funnel-steps/{organization_id}/{account_id}/{funnel_type}", response_model=FunnelStepsListResponse)
async def list_funnel_steps(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            big_bet_name=big_bet_name
        )

        return FunnelStepsListResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_steps=funnel_steps,
            total=len(funnel_steps)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing funnel steps: {str(e)}"
        )


@router.get("/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}", response_model=FunnelStepResponse)
async def get_funnel_step(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            funnel_step_num=funnel_step_num
        )
        
        if funnel_step is None:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return FunnelStepResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            funnel_step_data=funnel_step
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving funnel step: {str(e)}"
        )


@router.put("/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}", response_model=SuccessResponse)
async def update_funnel_step(
    organization_id: str,
    account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    request: FunnelStepRequest,
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            "objective": request.objective
        }

        # Update funnel step
        success = firestore.update_funnel_step(
            organization_id=organization_id,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            funnel_step_data=funnel_step_data
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return SuccessResponse(
            success=True,
            message=f"Funnel step {funnel_step_num} updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating funnel step: {str(e)}"
        )


@router.delete("/funnel-steps/{organization_id}/{account_id}/{funnel_type}/{funnel_step_num}", response_model=SuccessResponse)
async def delete_funnel_step(
    organization_id: str,account_id: str,
    funnel_type: str,
    funnel_step_num: int,
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet'"),
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
            funnel_step_num=funnel_step_num
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Funnel step not found")

        return SuccessResponse(
            success=True,
            message=f"Funnel step {funnel_step_num} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting funnel step: {str(e)}"
        )


# Channel Endpoints

@router.post("/channels/{organization_id}", response_model=ChannelResponse)
async def create_channel(
    organization_id: str,
    channel_data: ChannelRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            channel_data=channel_data.model_dump()
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
            channel_data=channel
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating channel: {str(e)}"
        )


@router.get("/channels/{organization_id}/{channel_name}", response_model=ChannelResponse)
async def get_channel(
    organization_id: str,
    channel_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            channel_name=channel_name
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
            channel_data=channel
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting channel: {str(e)}"
        )


@router.get("/channels/{organization_id}", response_model=ChannelListResponse)
async def list_channels(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            funnel_step_num=funnel_step_num
        )

        return ChannelListResponse(
            channels=channels,
            total=len(channels)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing channels: {str(e)}"
        )


@router.put("/channels/{organization_id}/{channel_name}", response_model=ChannelResponse)
async def update_channel(
    organization_id: str,
    channel_name: str,
    channel_data: ChannelUpdateRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            channel_data=channel_data.model_dump(exclude_unset=True)
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
            channel_data=channel
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating channel: {str(e)}"
        )


@router.delete("/channels/{organization_id}/{channel_name}", response_model=SuccessResponse)
async def delete_channel(
    organization_id: str,
    channel_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            channel_name=channel_name
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Channel not found")

        return SuccessResponse(
            success=True,
            message=f"Channel '{channel_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting channel: {str(e)}"
        )


# Tactic Endpoints

@router.post("/tactics/{organization_id}", response_model=TacticResponse)
async def create_tactic(
    organization_id: str,
    tactic_data: TacticRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            tactic_data=tactic_data.model_dump()
        )
        
        if not tactic:
            raise HTTPException(status_code=400, detail="Tactic already exists or channel not found")

        return TacticResponse(
            success=True,
            account_id=account_id,
            funnel_type=funnel_type,
            big_bet_name=big_bet_name,
            funnel_step_num=funnel_step_num,
            channel_name=channel_name,
            tactic_name=tactic_data.tactic_name,
            tactic_data=tactic
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating tactic: {str(e)}"
        )


@router.get("/tactics/{organization_id}/{tactic_name}", response_model=TacticResponse)
async def get_tactic(
    organization_id: str,
    tactic_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            tactic_name=tactic_name
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
            tactic_data=tactic
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error getting tactic: {str(e)}"
        )


@router.get("/tactics/{organization_id}", response_model=TacticListResponse)
async def list_tactics(
    organization_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            channel_name=channel_name
        )

        return TacticListResponse(
            tactics=tactics,
            total=len(tactics)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error listing tactics: {str(e)}"
        )


@router.put("/tactics/{organization_id}/{tactic_name}", response_model=TacticResponse)
async def update_tactic(
    organization_id: str,
    tactic_name: str,
    tactic_data: TacticUpdateRequest,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            tactic_data=tactic_data.model_dump(exclude_unset=True)
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
            tactic_data=tactic
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating tactic: {str(e)}"
        )


@router.delete("/tactics/{organization_id}/{tactic_name}", response_model=SuccessResponse)
async def delete_tactic(
    organization_id: str,
    tactic_name: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
    funnel_type: str = Query(..., description="Funnel type ('organization' or 'big_bet')"),
    funnel_step_num: int = Query(..., description="Funnel step number"),
    channel_name: str = Query(..., description="Channel name"),
    big_bet_name: Optional[str] = Query(None, description="Big bet name (required if funnel_type is 'big_bet')"),
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
            tactic_name=tactic_name
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Tactic not found")

        return SuccessResponse(
            success=True,
            message=f"Tactic '{tactic_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting tactic: {str(e)}"
        )


@router.get("/debug/documents/{collection}/{document_id}")
async def debug_get_document(
    collection: str,
    document_id: str,
    account_id: str = Query(..., description=ACCOUNT_ID_VALIDATION_DESCRIPTION),
) -> Dict[str, Any]:
    """
    Debug endpoint to test document path routing.
    
    This is a simple endpoint to verify that the routing works correctly.
    """
    return {
        "message": "Debug endpoint working",
        "collection": collection,
        "document_id": document_id,
        "account_id": account_id,
        "method": "GET"
    }
