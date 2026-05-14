"""Pydantic models for tool definitions.

This module defines the schema for tool registration:
- ToolPermission: Required scopes/permissions for a tool
- ToolParameter: Tool input parameter definitions
- ToolDefinition: Complete tool metadata for registry
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ToolPermission(BaseModel):
    """Permission scope required to use a tool.

    Attributes:
        scope: Permission scope identifier (e.g., "analytics:read", "ads:write")
        required: Whether this permission is mandatory (default True)
    """

    scope: str = Field(..., description="Permission scope identifier", min_length=1)
    required: bool = Field(default=True, description="Whether permission is mandatory")

    model_config = ConfigDict(str_strip_whitespace=True)


class ToolParameter(BaseModel):
    """Input parameter definition for a tool.

    Attributes:
        name: Parameter name
        type: Parameter type (string, integer, number, boolean, array, object)
        description: Human-readable description
        required: Whether parameter is mandatory
        default: Default value if not provided
    """

    name: str = Field(..., description="Parameter name", min_length=1)
    type: str = Field(..., description="Parameter data type")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(default=True, description="Whether parameter is mandatory")
    default: Any = Field(default=None, description="Default value if not provided")

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate parameter type is supported."""
        allowed_types = {"string", "integer", "number", "boolean", "array", "object"}
        if v.lower() not in allowed_types:
            raise ValueError(f"Unsupported type: {v}. Allowed: {allowed_types}")
        return v.lower()

    model_config = ConfigDict(str_strip_whitespace=True)


class ToolDefinition(BaseModel):
    """Complete tool definition for registration.

    This model represents a tool's metadata in the registry. It describes
    what a tool does, its parameters, and required permissions without
    containing the actual implementation.

    Attributes:
        name: Unique tool identifier
        description: Human-readable tool description
        category: Tool category (e.g., "analytics", "advertising", "content")
        mcp_server: Optional MCP server name that provides this tool
        source: "mcp" for tools delivered by an MCP server (the default — matches
            every entry in the legacy ``tools:`` section), "function" for built-in
            SDK function tools loaded from the YAML's ``function_tools:`` section.
        default_global: Only meaningful on function tools — when True, the tool is
            part of every account's global default inventory and shows up in the
            agent tool picker without an integration. Always False on MCP tools.
        parameters: List of input parameters
        permissions: List of required permissions
        keywords: Search keywords for tool discovery
        estimated_tokens: Estimated token usage for context budget
        examples: Optional usage examples for documentation
    """

    name: str = Field(..., description="Unique tool identifier", min_length=1)
    description: str = Field(..., description="Human-readable description")
    category: str = Field(..., description="Tool category for grouping")
    mcp_server: str | None = Field(default=None, description="MCP server name")
    source: Literal["mcp", "function"] = Field(
        default="mcp",
        description="Whether the tool is delivered by an MCP server or as a built-in function tool",
    )
    default_global: bool = Field(
        default=False,
        description="Function tools only: part of every account's default inventory",
    )
    parameters: list[ToolParameter] = Field(
        default_factory=list, description="Input parameters"
    )
    permissions: list[ToolPermission] = Field(
        default_factory=list, description="Required permissions"
    )
    keywords: list[str] = Field(default_factory=list, description="Search keywords")
    estimated_tokens: int = Field(
        default=150, description="Estimated token usage", ge=0
    )
    examples: list[str] = Field(default_factory=list, description="Usage examples")

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize tool name to lowercase with underscores."""
        return v.lower().replace("-", "_").replace(" ", "_")

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        """Normalize category to lowercase."""
        return v.lower()

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, v: list[str]) -> list[str]:
        """Normalize keywords to lowercase."""
        return [kw.lower() for kw in v]

    @model_validator(mode="after")
    def _validate_source_consistency(self) -> "ToolDefinition":
        # Catches the truly broken combinations: a `source="function"` tool that
        # also names an MCP server is contradictory; `default_global=True` is only
        # meaningful for function tools. ``source="mcp"`` with ``mcp_server=None``
        # is permitted because the existing schema has long allowed it (loose /
        # placeholder entries).
        if self.source == "function" and self.mcp_server is not None:
            raise ValueError(
                f"Tool {self.name!r}: source='function' requires mcp_server=None "
                f"(got {self.mcp_server!r})"
            )
        if self.default_global and self.source != "function":
            raise ValueError(
                f"Tool {self.name!r}: default_global=True is only allowed when source='function'"
            )
        return self

    def has_required_params(self) -> list[str]:
        """Get list of required parameter names."""
        return [p.name for p in self.parameters if p.required]

    def has_permission(self, scope: str) -> bool:
        """Check if tool requires a specific permission scope."""
        return any(p.scope == scope for p in self.permissions)

    model_config = ConfigDict(str_strip_whitespace=True)
