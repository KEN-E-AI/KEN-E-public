"""Data models for news and social media monitoring feature."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .kene_models import BaseRequest


class CompetitorEntry(BaseModel):
    """Competitor monitoring entry."""

    name: str = Field(..., description="Competitor name")
    website: str | None = Field(None, description="Competitor website URL")
    keywords: list[str] = Field(..., description="Keywords for monitoring this competitor")


class MonitoringTopics(BaseModel):
    """Monitoring topics configuration for an account."""

    account_id: str = Field(..., description="Unique identifier for the account")
    organization_id: str = Field(
        ..., description="ID of the organization this account belongs to"
    )
    industry_keywords: list[str] = Field(
        ..., description="Auto-generated keywords based on account industry"
    )
    company_keywords: list[str] = Field(
        default_factory=list, description="Keywords describing the company"
    )
    customer_keywords: list[str] = Field(
        default_factory=list, description="Keywords related to customers"
    )
    competitor_entries: list[CompetitorEntry] = Field(
        default_factory=list, description="List of competitors to monitor"
    )
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")


class IndustryKeywords(BaseModel):
    """Industry keyword mapping for super admin management."""

    industry: str = Field(..., description="Industry name")
    keywords: list[str] = Field(..., description="Keywords associated with this industry")
    updated_by: str = Field(..., description="User ID who last updated these keywords")
    updated_at: str = Field(..., description="ISO timestamp of last update")


class MonitoringResult(BaseModel):
    """Result from daily monitoring job."""

    article_id: str = Field(..., description="Unique identifier (hash) for the article")
    url: str = Field(..., description="URL of the discovered article")
    title: str = Field(..., description="Title of the article")
    discovered_date: str = Field(..., description="Date when article was discovered (YYYY-MM-DD)")
    matched_topics: list[str] = Field(
        ..., description="Topics/keywords that matched this article"
    )
    accounts: list[str] = Field(
        ..., description="Account IDs that matched this article"
    )
    metadata: dict[str, Any] = Field(
        ..., description="Additional metadata about the article"
    )


class UpdateCompanyKeywordsRequest(BaseRequest):
    """Request to update company keywords."""

    company_keywords: list[str] = Field(
        ..., description="New list of company keywords"
    )


class UpdateCustomerKeywordsRequest(BaseRequest):
    """Request to update customer keywords."""

    customer_keywords: list[str] = Field(
        ..., description="New list of customer keywords"
    )


class AddCompetitorRequest(BaseRequest):
    """Request to add a new competitor."""

    name: str = Field(..., description="Competitor name")
    website: str | None = Field(None, description="Competitor website URL")
    keywords: list[str] = Field(
        default_factory=list, description="Keywords for monitoring this competitor"
    )


class UpdateCompetitorRequest(BaseRequest):
    """Request to update an existing competitor."""

    competitor_index: int = Field(
        ..., description="Index of the competitor in the competitor_entries array"
    )
    name: str | None = Field(None, description="Updated competitor name")
    website: str | None = Field(None, description="Updated competitor website URL")
    keywords: list[str] | None = Field(
        None, description="Updated keywords for monitoring"
    )


class UpdateIndustryKeywordsRequest(BaseModel):
    """Request to update industry keywords (super admin only)."""

    keywords: list[str] = Field(
        ..., description="New list of keywords for the industry"
    )


class MonitoringTopicsResponse(BaseModel):
    """Response containing monitoring topics for an account."""

    success: bool = Field(..., description="Operation success status")
    data: MonitoringTopics | None = Field(
        None, description="Monitoring topics data if found"
    )


class IndustryKeywordsListResponse(BaseModel):
    """Response containing all industry keywords."""

    success: bool = Field(..., description="Operation success status")
    industries: list[IndustryKeywords] = Field(
        ..., description="List of all industry keyword mappings"
    )