"""Integration tests for ADK-compatible before_tool_callback adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.adk.security.hooks import adk_before_tool_callback
from app.adk.security.permissions import PermissionCheckResult


@dataclass
class MockBaseTool:
    """Minimal mock of ADK BaseTool (only needs .name)."""

    name: str


@dataclass
class MockState:
    """Mock of ADK state with dict-like access."""

    _data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


@dataclass
class MockToolContext:
    """Minimal mock of ADK ToolContext (needs .state and .user_content)."""

    state: MockState = field(default_factory=MockState)
    user_content: Any = None


def _make_context(
    user_id: str = "user1",
    account_id: str = "acct1",
) -> MockToolContext:
    ctx = MockToolContext()
    ctx.state["user_id"] = user_id
    ctx.state["account_id"] = account_id
    return ctx


class TestAdkBeforeToolCallback:
    """Tests for adk_before_tool_callback adapter."""

    @pytest.mark.asyncio
    async def test_allows_when_permission_granted(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        allowed = PermissionCheckResult(allowed=True, reason="Scopes valid")

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=allowed,
        ):
            result = await adk_before_tool_callback(tool, {"query": "test"}, ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_blocks_when_token_expired(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        denied = PermissionCheckResult(
            allowed=False,
            reason="Token expired",
            requires_reauth=True,
            missing_scopes=[],
        )

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=denied,
        ):
            result = await adk_before_tool_callback(tool, {}, ctx)

        assert result == {
            "error": "authentication_required",
            "message": "Token expired",
            "requires_reauth": True,
            "missing_scopes": [],
        }

    @pytest.mark.asyncio
    async def test_blocks_when_no_token(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        denied = PermissionCheckResult(
            allowed=False,
            reason="No OAuth token found",
            requires_reauth=True,
            missing_scopes=["analytics.readonly"],
        )

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=denied,
        ):
            result = await adk_before_tool_callback(tool, {}, ctx)

        assert result is not None
        assert result["requires_reauth"] is True
        assert result["missing_scopes"] == ["analytics.readonly"]

    @pytest.mark.asyncio
    async def test_allows_unregistered_tools(self):
        tool = MockBaseTool(name="internal_adk_tool")
        ctx = _make_context()
        allowed = PermissionCheckResult(allowed=True, reason="Tool not in registry")

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=allowed,
        ):
            result = await adk_before_tool_callback(tool, {}, ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_missing_scopes(self):
        tool = MockBaseTool(name="get_ga4_report")
        ctx = _make_context()
        denied = PermissionCheckResult(
            allowed=False,
            reason="Missing required scopes",
            requires_reauth=True,
            missing_scopes=["analytics.readonly", "analytics.edit"],
        )

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=denied,
        ):
            result = await adk_before_tool_callback(tool, {}, ctx)

        assert result is not None
        assert result["missing_scopes"] == [
            "analytics.readonly",
            "analytics.edit",
        ]

    @pytest.mark.asyncio
    async def test_stores_tool_start_time(self):
        tool = MockBaseTool(name="some_tool")
        ctx = _make_context()
        allowed = PermissionCheckResult(allowed=True, reason="OK")

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=allowed,
        ):
            await adk_before_tool_callback(tool, {}, ctx)

        assert "_tool_start_time" in ctx.state._data
        assert isinstance(ctx.state["_tool_start_time"], float)

    @pytest.mark.asyncio
    async def test_permission_denied_without_reauth(self):
        tool = MockBaseTool(name="restricted_tool")
        ctx = _make_context()
        denied = PermissionCheckResult(
            allowed=False,
            reason="Insufficient role",
            requires_reauth=False,
        )

        with patch(
            "app.adk.security.hooks.before_tool_execution_hook",
            new_callable=AsyncMock,
            return_value=denied,
        ):
            result = await adk_before_tool_callback(tool, {}, ctx)

        assert result == {
            "error": "permission_denied",
            "message": "Insufficient role",
        }
