"""API models for tool discovery and usage endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class ToolBreakdownResponse(BaseModel):
    """Per-tool usage breakdown."""

    calls: int
    success: int
    failure: int
    success_rate: float
    avg_duration_ms: float | None = None


class UserBreakdownResponse(BaseModel):
    """Per-user usage breakdown."""

    calls: int
    success: int
    failure: int
    success_rate: float


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


# ─── Account tool inventory (AH-PRD-06) ─────────────────────────────────────
#
# The inventory enumerates the tools an account can attach to its agents:
#   * every tool tagged ``default_global: true`` in the YAML's
#     ``function_tools:`` section (source ``"global_default"``)
#   * every tool whose owning MCP server corresponds to a connected platform
#     integration for this account (source ``"integration"``)
# Spec: docs/design/components/agentic-harness/projects/AH-PRD-06-tool-mapping.md §4.


class AccountToolEntry(BaseModel):
    """One tool surfaced by ``GET /api/v1/accounts/{account_id}/tools``."""

    tool_id: str = Field(
        ...,
        description=(
            "Namespaced ID used as the agent's ``tool_ids`` value: "
            "``<mcp_server>.<tool_name>`` for MCP tools, "
            "``function.<tool_name>`` for built-in function tools."
        ),
    )
    name: str = Field(..., description="The bare tool name (no namespace)")
    description: str = Field(..., description="Human-readable tool description")
    category: str = Field(..., description="Tool category for UI grouping")
    source: Literal["global_default", "integration"] = Field(
        ...,
        description=(
            "``global_default`` for built-in function tools always available; "
            "``integration`` for tools gated on a connected platform integration."
        ),
    )
    mcp_server: str | None = Field(
        default=None,
        description="The MCP server ID this tool belongs to; null for function tools.",
    )
    integration_platform: str | None = Field(
        default=None,
        description=(
            "The integration platform ID (e.g. ``google_analytics``) whose "
            "connection makes this tool available; null for function tools."
        ),
    )


class AccountToolsResponse(BaseModel):
    """Response body for ``GET /api/v1/accounts/{account_id}/tools``."""

    tools: list[AccountToolEntry] = Field(default_factory=list)
