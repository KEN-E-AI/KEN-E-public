"""Tool management module for KEN-E agents.

This module provides:
- Tool Registry: Central registration and validation of tool definitions
- Tool Discovery: Search and filter available tools by capability
"""

from .registry.tool_registry import ToolRegistry
from .registry.tool_schema import (
    ToolDefinition,
    ToolParameter,
    ToolPermission,
)

__all__ = [
    "ToolDefinition",
    "ToolParameter",
    "ToolPermission",
    "ToolRegistry",
]
