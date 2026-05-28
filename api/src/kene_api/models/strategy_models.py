"""
Pydantic models for strategy documents with audit trail support.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StrategySection(BaseModel):
    """A section within a strategy document."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    subsections: list["StrategySection"] | None = Field(
        default=None, description="Optional subsections"
    )


class StrategyDocument(BaseModel):
    """A complete strategy document stored in Firestore."""

    doc_type: Literal[
        "business_strategy",
        "competitive_strategy",
        "customer_strategy",
        "marketing_strategy",
        "measurement_plan",
        "brand_strategy",
    ] = Field(..., description="Type of strategy document")
    content: dict[str, Any] = Field(
        ..., description="Document content following best practices schema"
    )
    version: int = Field(default=1, description="Document version")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    created_by: str = Field(..., description="User ID who created the document")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    updated_by: str = Field(..., description="User ID who last updated the document")
    account_id: str = Field(..., description="Associated account ID")

    # Optional metadata
    title: str | None = Field(default=None, description="Document title")
    description: str | None = Field(default=None, description="Brief description")
    tags: list[str] = Field(default_factory=list, description="Document tags")
    is_active: bool = Field(default=True, description="Whether document is active")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class StrategyAuditEntry(BaseModel):
    """Audit log entry for strategy document operations."""

    action: Literal["created", "updated", "deleted", "viewed", "exported"] = Field(
        ..., description="Action performed"
    )
    user_id: str = Field(..., description="User ID who performed the action")
    user_email: str = Field(..., description="User email for audit clarity")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When action occurred"
    )
    ip_address: str | None = Field(default=None, description="Client IP address")
    user_agent: str | None = Field(default=None, description="Client user agent")

    # Document details
    doc_type: str = Field(..., description="Type of strategy document")
    doc_id: str | None = Field(default=None, description="Document ID if applicable")
    version: int = Field(..., description="Document version at time of action")

    # Change tracking
    changes: dict[str, Any] | None = Field(
        default=None, description="Before/after for updates"
    )
    fields_modified: list[str] | None = Field(
        default=None, description="List of modified fields"
    )

    # Session tracking
    session_id: str | None = Field(
        default=None, description="Chat session ID if from chatbot"
    )
    request_id: str | None = Field(
        default=None, description="API request ID for tracing"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class StrategyDocumentRequest(BaseModel):
    """Request to create or update a strategy document."""

    doc_type: Literal[
        "business_strategy",
        "competitive_strategy",
        "customer_strategy",
        "marketing_strategy",
        "measurement_plan",
        "brand_strategy",
    ] = Field(..., description="Type of strategy document")
    content: dict[str, Any] = Field(..., description="Document content")
    title: str | None = Field(default=None, description="Document title")
    description: str | None = Field(default=None, description="Brief description")
    tags: list[str] | None = Field(default=None, description="Document tags")


class StrategyDocumentResponse(BaseModel):
    """Response containing a strategy document."""

    document: StrategyDocument = Field(..., description="The strategy document")
    access_level: Literal["view", "edit", "admin"] = Field(
        ..., description="User's access level"
    )
    can_edit: bool = Field(..., description="Whether user can edit this document")
    can_delete: bool = Field(..., description="Whether user can delete this document")


class StrategyDocumentListResponse(BaseModel):
    """Response for listing strategy documents."""

    documents: list[StrategyDocument] = Field(
        ..., description="List of strategy documents"
    )
    total_count: int = Field(..., description="Total number of documents")
    access_level: Literal["view", "edit", "admin"] = Field(
        ..., description="User's access level"
    )


class StrategyTemplateResponse(BaseModel):
    """Response containing a strategy template/best practices."""

    doc_type: str = Field(..., description="Type of strategy document")
    template: dict[str, Any] = Field(
        ..., description="Template or best practices schema"
    )
    guidelines: str | None = Field(default=None, description="Reviewer guidelines")
    examples: list[dict[str, Any]] | None = Field(
        default=None, description="Example documents"
    )


class StrategyAuditLogResponse(BaseModel):
    """Response for audit log queries."""

    entries: list[StrategyAuditEntry] = Field(..., description="Audit log entries")
    total_count: int = Field(..., description="Total number of entries")
    date_from: datetime = Field(..., description="Start date of audit range")
    date_to: datetime = Field(..., description="End date of audit range")


class StrategyGenerationRequest(BaseModel):
    """Request to generate a strategy document via AI agent."""

    doc_type: Literal[
        "business_strategy",
        "competitive_strategy",
        "customer_strategy",
        "marketing_strategy",
        "measurement_plan",
        "brand_strategy",
    ] = Field(..., description="Type of strategy document to generate")
    context: str = Field(..., description="Context or requirements for the strategy")
    company_info: dict[str, Any] | None = Field(
        default=None, description="Company information for strategy creation"
    )
    existing_document_id: str | None = Field(
        default=None, description="ID of existing document to update"
    )
    max_iterations: int = Field(
        default=3, description="Maximum refinement iterations", ge=1, le=5
    )


class StrategyGenerationResponse(BaseModel):
    """Response from strategy generation."""

    success: bool = Field(..., description="Whether generation succeeded")
    document: StrategyDocument | None = Field(
        default=None, description="Generated document"
    )
    iterations_used: int = Field(..., description="Number of refinement iterations")
    generation_time: float = Field(..., description="Time taken in seconds")
    error: str | None = Field(default=None, description="Error message if failed")


# Allow forward references in models
StrategySection.model_rebuild()
