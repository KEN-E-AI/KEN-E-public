"""
Pydantic models for strategy documents.
"""

from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class StrategySection(BaseModel):
    """A section within a strategy document."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    subsections: Optional[List["StrategySection"]] = Field(default=None, description="Optional subsections")


class StrategyDocument(BaseModel):
    """A complete strategy document."""
    doc_type: Literal["business_strategy", "competitive_strategy", "channel_strategies"] = Field(
        ..., description="Type of strategy document"
    )
    title: str = Field(..., description="Document title")
    executive_summary: str = Field(..., description="Executive summary")
    sections: List[StrategySection] = Field(..., description="Document sections")
    key_recommendations: List[str] = Field(default_factory=list, description="Key recommendations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Tracking fields
    version: int = Field(default=1, description="Document version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_by: Optional[str] = Field(default=None, description="User ID who created the document")
    updated_by: Optional[str] = Field(default=None, description="User ID who last updated the document")
    account_id: Optional[str] = Field(default=None, description="Associated account ID")


class ReviewFeedback(BaseModel):
    """Feedback from the reviewer agent."""
    overall_quality: Literal["excellent", "good", "needs_improvement", "poor"] = Field(
        ..., description="Overall quality assessment"
    )
    strengths: List[str] = Field(..., description="Document strengths")
    areas_for_improvement: List[str] = Field(..., description="Areas needing improvement")
    specific_suggestions: List[str] = Field(..., description="Specific improvement suggestions")
    is_ready: bool = Field(..., description="Whether document is ready or needs more work")


class EditRequest(BaseModel):
    """Request for the editor agent."""
    document: StrategyDocument = Field(..., description="Current document")
    feedback: ReviewFeedback = Field(..., description="Reviewer feedback")
    iteration: int = Field(default=1, description="Current iteration number")


class StrategyRequest(BaseModel):
    """Request to create or update a strategy document."""
    doc_type: Literal["business_strategy", "competitive_strategy", "channel_strategies"] = Field(
        ..., description="Type of strategy document"
    )
    context: str = Field(..., description="Context or requirements for the strategy")
    existing_document: Optional[StrategyDocument] = Field(
        default=None, description="Existing document to update (if any)"
    )
    account_id: Optional[str] = Field(default=None, description="Account ID for scoping")
    user_id: Optional[str] = Field(default=None, description="User ID for attribution")
    max_iterations: int = Field(default=3, description="Maximum refinement iterations")


# Allow forward references in models
StrategySection.model_rebuild()