"""Conftest for MCP manager tests.

Pre-mocks ADK/MCP modules to prevent circular import chain:
  google.adk.__init__ -> google.adk.agents -> mcp_instruction_provider -> from mcp import ...
This chain fails in the test environment due to the local app/adk/mcp_config/ package
(formerly app/adk/mcp/) conflicting with the installed mcp library during Python's
import resolution.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock


@dataclass
class MockSseConnectionParams:
    """Stand-in for google.adk.tools.mcp_tool.mcp_session_manager.SseConnectionParams."""

    url: str = ""
    headers: dict[str, str] | None = None
    timeout: float = 30.0


@dataclass
class MockStdioConnectionParams:
    """Stand-in for google.adk.tools.mcp_tool.mcp_session_manager.StdioConnectionParams."""

    server_params: Any = None
    timeout: float = 5.0


@dataclass
class MockStdioServerParameters:
    """Stand-in for mcp.client.stdio.StdioServerParameters."""

    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


# Build mock modules with real dataclass stand-ins
_mock_session_mgr = MagicMock()
_mock_session_mgr.SseConnectionParams = MockSseConnectionParams
_mock_session_mgr.StdioConnectionParams = MockStdioConnectionParams

_mock_toolset_mod = MagicMock()

_mock_stdio_mod = MagicMock()
_mock_stdio_mod.StdioServerParameters = MockStdioServerParameters

# Pre-populate sys.modules BEFORE test files import anything.
# setdefault preserves already-imported modules (safe for broader test runs).
sys.modules.setdefault(
    "google.adk.tools.mcp_tool.mcp_session_manager", _mock_session_mgr
)
sys.modules.setdefault("google.adk.tools.mcp_tool.mcp_toolset", _mock_toolset_mod)
sys.modules.setdefault("mcp.client.stdio", _mock_stdio_mod)
