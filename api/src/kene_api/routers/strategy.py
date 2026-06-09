"""
Strategy documents API router with access control and audit logging.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext
from ..auth.user_context import check_account_access
from ..models.strategy_models import (
    StrategyAuditEntry,
    StrategyAuditLogResponse,
    StrategyDocument,
    StrategyDocumentListResponse,
    StrategyDocumentRequest,
    StrategyDocumentResponse,
    StrategyGenerationRequest,
    StrategyGenerationResponse,
    StrategyTemplateResponse,
)
from ..services.audit_service import log_strategy_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategy", tags=["strategy"])

# Initialize Firestore client
db = firestore.Client()


async def check_strategy_access(
    account_id: str, user: UserContext, required_level: str = "view"
) -> UserContext:
    """Check if user has required access level for strategy documents.

    Delegates account membership to the shared check_account_access helper,
    then layers the edit-role gate on top when required_level == "edit".
    """
    await check_account_access(account_id, user)

    if required_level == "edit" and not user.has_account_access(account_id, ["edit"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions for edit access to account {account_id}",
        )

    return user


@router.get("/{account_id}/documents", response_model=StrategyDocumentListResponse)
async def list_strategy_documents(
    account_id: str,
    doc_type: str | None = Query(None, description="Filter by document type"),
    is_active: bool = Query(True, description="Filter by active status"),
    request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> StrategyDocumentListResponse:
    """
    List all strategy documents for an account.
    Requires view permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "view")

    try:
        # Query Firestore using account-specific collection
        docs_ref = db.collection(f"accounts/{account_id}/strategy_docs")
        query = docs_ref.where(filter=FieldFilter("is_active", "==", is_active))

        if doc_type:
            query = query.where(filter=FieldFilter("doc_type", "==", doc_type))

        docs = query.stream()

        # Convert to models
        documents = []
        for doc in docs:
            doc_data = doc.to_dict()
            doc_data["doc_id"] = doc.id
            documents.append(StrategyDocument(**doc_data))

        # Log view action
        await log_strategy_action(
            account_id=account_id,
            doc_type="all",
            action="viewed",
            user=user,
            request=request,
        )

        # Determine user's access level
        access_level = "admin" if user.is_super_admin else "edit"
        if not user.has_account_access(account_id, ["edit"]):
            access_level = "view"

        return StrategyDocumentListResponse(
            documents=documents, total_count=len(documents), access_level=access_level
        )

    except Exception as e:
        logger.error(f"Error listing strategy documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve strategy documents",
        )


@router.get(
    "/{account_id}/documents/{doc_type}", response_model=StrategyDocumentResponse
)
async def get_strategy_document(
    account_id: str,
    doc_type: str,
    version: int | None = Query(None, description="Specific version to retrieve"),
    request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> StrategyDocumentResponse:
    """
    Get a specific strategy document.
    Requires view permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "view")

    try:
        # Query Firestore using account-specific collection
        if version:
            # Get specific version from history
            doc_ref = db.document(
                f"accounts/{account_id}/strategy_docs/{doc_type}/versions/{version}"
            )
        else:
            # Get current version
            doc_ref = db.document(f"accounts/{account_id}/strategy_docs/{doc_type}")

        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy document '{doc_type}' not found",
            )

        doc_data = doc.to_dict()
        document = StrategyDocument(**doc_data)

        # Log view action
        await log_strategy_action(
            account_id=account_id,
            doc_type=doc_type,
            action="viewed",
            user=user,
            request=request,
            doc_id=doc.id,
            version=document.version,
        )

        # Determine permissions
        can_edit = user.is_super_admin or user.has_account_access(account_id, ["edit"])
        can_delete = user.is_super_admin
        access_level = (
            "admin" if user.is_super_admin else ("edit" if can_edit else "view")
        )

        return StrategyDocumentResponse(
            document=document,
            access_level=access_level,
            can_edit=can_edit,
            can_delete=can_delete,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving strategy document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve strategy document",
        )


@router.post(
    "/{account_id}/documents/{doc_type}", response_model=StrategyDocumentResponse
)
async def create_or_update_strategy_document(
    account_id: str,
    doc_type: str,
    document_request: StrategyDocumentRequest,
    request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> StrategyDocumentResponse:
    """
    Create or update a strategy document.
    Requires edit permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "edit")

    try:
        # Check if document exists in account-specific collection
        doc_ref = db.document(f"accounts/{account_id}/strategy_docs/{doc_type}")
        existing_doc = doc_ref.get()

        # Prepare document data
        now = datetime.utcnow()

        if existing_doc.exists:
            # Update existing document
            existing_data = existing_doc.to_dict()
            old_version = existing_data.get("version", 1)

            # Archive current version
            version_ref = db.document(
                f"accounts/{account_id}/strategy_docs/{doc_type}/versions/{old_version}"
            )
            version_ref.set(existing_data)

            # Prepare updated document
            doc_data = {
                "doc_type": doc_type,
                "content": document_request.content,
                "version": old_version + 1,
                "created_at": existing_data.get("created_at", now),
                "created_by": existing_data.get("created_by", user.user_id),
                "updated_at": now,
                "updated_by": user.user_id,
                "account_id": account_id,
                "title": document_request.title or existing_data.get("title"),
                "description": document_request.description
                or existing_data.get("description"),
                "tags": document_request.tags or existing_data.get("tags", []),
                "is_active": True,
            }

            # Track changes
            changes = {
                "before": existing_data.get("content"),
                "after": document_request.content,
            }
            action = "updated"

        else:
            # Create new document
            doc_data = {
                "doc_type": doc_type,
                "content": document_request.content,
                "version": 1,
                "created_at": now,
                "created_by": user.user_id,
                "updated_at": now,
                "updated_by": user.user_id,
                "account_id": account_id,
                "title": document_request.title,
                "description": document_request.description,
                "tags": document_request.tags or [],
                "is_active": True,
            }
            changes = None
            action = "created"

        # Save document
        doc_ref.set(doc_data)
        document = StrategyDocument(**doc_data)

        # Log action
        await log_strategy_action(
            account_id=account_id,
            doc_type=doc_type,
            action=action,
            user=user,
            request=request,
            doc_id=doc_ref.id,
            version=document.version,
            changes=changes,
        )

        # Determine permissions
        can_edit = user.is_super_admin or user.has_account_access(account_id, ["edit"])
        can_delete = user.is_super_admin
        access_level = "admin" if user.is_super_admin else "edit"

        return StrategyDocumentResponse(
            document=document,
            access_level=access_level,
            can_edit=can_edit,
            can_delete=can_delete,
        )

    except Exception as e:
        logger.error(f"Error creating/updating strategy document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save strategy document",
        )


@router.delete("/{account_id}/documents/{doc_type}")
async def delete_strategy_document(
    account_id: str,
    doc_type: str,
    request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Delete a strategy document (soft delete).
    Requires admin permission.
    """
    # Only super admins can delete
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete strategy documents",
        )

    try:
        # Get document from account-specific collection
        doc_ref = db.document(f"accounts/{account_id}/strategy_docs/{doc_type}")
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy document '{doc_type}' not found",
            )

        # Soft delete by marking inactive
        doc_ref.update(
            {
                "is_active": False,
                "deleted_at": datetime.utcnow(),
                "deleted_by": user.user_id,
            }
        )

        # Log action
        await log_strategy_action(
            account_id=account_id,
            doc_type=doc_type,
            action="deleted",
            user=user,
            request=request,
            doc_id=doc.id,
        )

        return {"success": True, "message": f"Strategy document '{doc_type}' deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting strategy document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete strategy document",
        )


@router.get(
    "/{account_id}/templates/{doc_type}", response_model=StrategyTemplateResponse
)
async def get_strategy_template(
    account_id: str, doc_type: str, user: UserContext = Depends(get_current_user)
) -> StrategyTemplateResponse:
    """
    Get best practices template for a strategy document type.
    Requires view permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "view")

    try:
        # Get template from Firestore
        template_ref = db.document(f"strategy_templates/{doc_type}")
        template_doc = template_ref.get()

        if not template_doc.exists:
            # Return default template
            template = get_default_template(doc_type)
        else:
            template_data = template_doc.to_dict()
            template = template_data.get("template", {})

        # Get reviewer guidelines
        guidelines_ref = db.document(f"strategy_guidelines/{doc_type}")
        guidelines_doc = guidelines_ref.get()
        guidelines = (
            guidelines_doc.to_dict().get("guidelines")
            if guidelines_doc.exists
            else None
        )

        return StrategyTemplateResponse(
            doc_type=doc_type,
            template=template,
            guidelines=guidelines,
            examples=[],  # TODO: Add example documents
        )

    except Exception as e:
        logger.error(f"Error retrieving strategy template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve strategy template",
        )


@router.get("/{account_id}/history/{doc_type}", response_model=StrategyAuditLogResponse)
async def get_strategy_audit_log(
    account_id: str,
    doc_type: str,
    date_from: datetime | None = Query(None, description="Start date"),
    date_to: datetime | None = Query(None, description="End date"),
    action: str | None = Query(None, description="Filter by action type"),
    limit: int = Query(100, description="Maximum entries to return"),
    user: UserContext = Depends(get_current_user),
) -> StrategyAuditLogResponse:
    """
    Get audit log for strategy document changes.
    Requires view permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "view")

    try:
        # Set date range
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()

        # Query audit log from the account's Shape B subcollection (audit_service.log_strategy_action
        # writes to accounts/{account_id}/strategy_audit/{audit_id}).
        audit_ref = db.collection(f"accounts/{account_id}/strategy_audit")
        query = audit_ref.where(filter=FieldFilter("doc_type", "==", doc_type))
        query = query.where(filter=FieldFilter("timestamp", ">=", date_from))
        query = query.where(filter=FieldFilter("timestamp", "<=", date_to))

        if action:
            query = query.where(filter=FieldFilter("action", "==", action))

        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)

        # Get entries
        entries = []
        for doc in query.stream():
            entry_data = doc.to_dict()
            entries.append(StrategyAuditEntry(**entry_data))

        return StrategyAuditLogResponse(
            entries=entries,
            total_count=len(entries),
            date_from=date_from,
            date_to=date_to,
        )

    except Exception as e:
        logger.error(f"Error retrieving audit log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log",
        )


@router.post("/{account_id}/generate", response_model=StrategyGenerationResponse)
async def generate_strategy_document(
    account_id: str,
    generation_request: StrategyGenerationRequest,
    request: Request = None,
    user: UserContext = Depends(get_current_user),
) -> StrategyGenerationResponse:
    """
    Generate a strategy document using AI agent.
    Requires edit permission.
    """
    # Check access
    await check_strategy_access(account_id, user, "edit")

    try:
        # TODO: Call the strategy agent via the chat API
        # For now, return a mock response
        return StrategyGenerationResponse(
            success=False,
            document=None,
            iterations_used=0,
            generation_time=0.0,
            error="Strategy generation not yet implemented",
        )

    except Exception as e:
        logger.error(f"Error generating strategy document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate strategy document",
        )


def get_default_template(doc_type: str) -> dict[str, Any]:
    """Get default template for a document type."""
    templates = {
        "business_strategy": {
            "executive_summary": "High-level summary",
            "company_overview": {
                "history_and_background": "",
                "mission_vision_values": "",
                "leadership_and_organization": "",
                "brand_and_customer_base": "",
            },
            "products_and_services": {},
            "market_and_industry_analysis": {},
            "swot_analysis": {
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": [],
            },
            "strategic_recommendations": {},
        },
        "competitive_strategy": {
            "executive_summary": {},
            "competitive_landscape": {},
            "comparative_analysis": {},
            "strategic_recommendations": {},
        },
        "customer_strategy": {
            "executive_summary": {},
            "customer_segments": {},
            "value_propositions": {},
            "customer_journey": {},
            "retention_strategies": {},
            "growth_strategies": {},
        },
        "marketing_strategy": {
            "executive_summary": {},
            "marketing_objectives": {},
            "target_markets": {},
            "marketing_mix": {},
            "channel_strategies": {},
            "budget_allocation": {},
            "performance_metrics": {},
        },
        "measurement_plan": {
            "executive_summary": {},
            "kpis_and_metrics": {},
            "data_collection": {},
            "reporting_framework": {},
            "analysis_methodology": {},
            "optimization_process": {},
        },
        "brand_strategy": {
            "executive_summary": {},
            "brand_positioning": {},
            "brand_identity": {},
            "brand_architecture": {},
            "brand_messaging": {},
            "brand_experience": {},
            "brand_governance": {},
        },
    }
    return templates.get(doc_type, {})
