"""API models for tool discovery endpoints."""

from pydantic import BaseModel, Field


class ToolParameterResponse(BaseModel):
    """API response model for tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter data type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(..., description="Whether parameter is required")
    default: str | None = Field(default=None, description="Default value")


class ToolInfoResponse(BaseModel):
    """API response model for tool information."""

    name: str = Field(..., description="Tool identifier")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category")
    parameters: list[ToolParameterResponse] = Field(
        default_factory=list, description="Tool parameters"
    )
    permissions: list[str] = Field(
        default_factory=list, description="Required permission scopes"
    )
    examples: list[str] = Field(default_factory=list, description="Usage examples")
    estimated_tokens: int = Field(default=150, description="Estimated token usage")


class ToolSearchResultResponse(BaseModel):
    """API response model for tool search result."""

    name: str = Field(..., description="Tool identifier")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category")
    score: float = Field(..., description="Relevance score")
    match_reasons: list[str] = Field(
        default_factory=list, description="Why this tool matched"
    )
    parameters: list[ToolParameterResponse] = Field(
        default_factory=list, description="Tool parameters"
    )
    permissions: list[str] = Field(
        default_factory=list, description="Required permission scopes"
    )
    examples: list[str] = Field(default_factory=list, description="Usage examples")


class ToolDiscoveryResponse(BaseModel):
    """API response model for tool discovery endpoint."""

    query: str = Field(..., description="Original search query")
    category: str | None = Field(default=None, description="Category filter applied")
    total_results: int = Field(..., description="Total matching tools")
    results: list[ToolSearchResultResponse] = Field(
        default_factory=list, description="Matching tools"
    )


class ToolCategoryResponse(BaseModel):
    """API response model for tool category."""

    name: str = Field(..., description="Category name")
    tool_count: int = Field(..., description="Number of tools in category")


class ToolCategoriesResponse(BaseModel):
    """API response model for list of tool categories."""

    categories: list[ToolCategoryResponse] = Field(
        default_factory=list, description="Available categories"
    )
