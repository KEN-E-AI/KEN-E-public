"""
Pydantic models for strategy generation parameters and responses.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategyParameters(BaseModel):
    """Parameters for strategy generation."""

    company_name: str = Field(..., description="Company name", min_length=1)
    industry: str = Field(..., description="Industry sector", min_length=1)
    websites: str = Field(default="", description="Company websites (comma-separated)")
    customer_regions: str = Field(
        default="", description="Customer regions (comma-separated)"
    )
    account_id: str = Field(..., description="Account identifier", min_length=1)
    user_id: str = Field(..., description="User identifier", min_length=1)
    annual_ad_budget: float = Field(
        default=0.0, description="Annual advertising budget", ge=0.0
    )
    project_id: Optional[str] = Field(
        default=None, description="GCP project ID for resources"
    )
    uploaded_documents: List[str] = Field(
        default_factory=list, description="URLs of uploaded documents"
    )

    @field_validator("annual_ad_budget", mode="before")
    @classmethod
    def parse_budget(cls, v: Any) -> float:
        """Parse budget from various formats."""
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                # Remove common currency symbols and commas
                cleaned = v.replace("$", "").replace(",", "").strip()
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0
        return 0.0

    @field_validator("project_id", mode="before")
    @classmethod
    def set_default_project(cls, v: Optional[str]) -> str:
        """Set default project ID if not provided."""
        if not v:
            return os.getenv("VERTEX_AI_PROJECT_ID", "ken-e-dev")
        return v

    @field_validator("uploaded_documents", mode="before")
    @classmethod
    def parse_documents(cls, v: Any) -> List[str]:
        """Parse uploaded documents from various formats."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Split comma-separated URLs
            if v.strip():
                return [url.strip() for url in v.split(",") if url.strip()]
            return []
        return []

    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class StrategyResponse(BaseModel):
    """Response from strategy generation."""

    status: str = Field(..., description="Status of the operation")
    query: str = Field(..., description="Original query")
    result: Any = Field(..., description="Strategy generation result")
    source: str = Field(default="strategy_specialist", description="Source agent")
    agent: str = Field(default="strategy", description="Agent type")
    account_id: str = Field(..., description="Account ID for the strategy")
    error: Optional[str] = Field(default=None, description="Error message if any")

    model_config = ConfigDict(
        use_enum_values=True,
    )


def parse_strategy_query(query: str) -> Dict[str, Any]:
    """
    Parse a formatted strategy query string into a dictionary.

    This function extracts parameters from the formatted message
    that comes from the supervisor agent.

    Args:
        query: Formatted query string with parameters

    Returns:
        Dictionary of parsed parameters
    """
    import re

    params = {}

    # Define parameter patterns
    param_patterns = {
        "company_name": r"[-•]\s*company_name:\s*(.+?)(?:\n|$)",
        "industry": r"[-•]\s*industry:\s*(.+?)(?:\n|$)",
        "websites": r"[-•]\s*websites:\s*(.+?)(?:\n|$)",
        "customer_regions": r"[-•]\s*customer_regions:\s*(.+?)(?:\n|$)",
        "account_id": r"[-•]\s*account_id:\s*(.+?)(?:\n|$)",
        "user_id": r"[-•]\s*user_id:\s*(.+?)(?:\n|$)",
        "annual_ad_budget": r"[-•]\s*annual_ad_budget:\s*(.+?)(?:\n|$)",
        "project_id": r"[-•]\s*project_id:\s*(.+?)(?:\n|$)",
        "uploaded_documents": r"[-•]\s*uploaded_documents:\s*(.+?)(?:\n|$)",
    }

    for param_name, pattern in param_patterns.items():
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            params[param_name] = value

    return params
