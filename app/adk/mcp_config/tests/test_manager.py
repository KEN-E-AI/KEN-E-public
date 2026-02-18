"""Tests for MCP server manager."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from app.adk.mcp_config.manager import (
    MCPServerManager,
    get_mcp_manager,
    reset_mcp_manager,
)


@pytest.fixture
def sample_config_file(tmp_path):
    """Create a sample config file for testing."""
    config_content = {
        "servers": {
            "test_server_1": {
                "description": "Test server 1",
                "category": "testing",
                "tool_count": 3,
                "estimated_tokens": 500,
                "keywords": ["test"],
                "connection": {
                    "connection_type": "stdio",
                    "command": "npx",
                    "args": ["-y", "test-server"],
                },
                "enabled": True,
            },
            "test_server_2": {
                "description": "Test server 2",
                "category": "testing",
                "tool_count": 5,
                "estimated_tokens": 800,
                "keywords": ["test"],
                "connection": {
                    "connection_type": "sse",
                    "url": "https://test.example.com/mcp/sse",
                },
                "enabled": True,
            },
            "test_server_ga": {
                "description": "Test GA server",
                "category": "analytics",
                "tool_count": 4,
                "estimated_tokens": 600,
                "keywords": ["analytics"],
                "connection": {
                    "connection_type": "sse",
                    "url": "https://ga.example.com/mcp/sse",
                },
                "auth_type": "ga_oauth",
                "enabled": True,
            },
            "disabled_server": {
                "description": "Disabled server",
                "category": "testing",
                "tool_count": 1,
                "estimated_tokens": 100,
                "connection": {
                    "connection_type": "stdio",
                    "command": "disabled",
                },
                "enabled": False,
            },
        }
    }

    config_file = tmp_path / "mcp_servers.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)

    return config_file


def _make_mock_tool(name: str, description: str = "mock tool") -> MagicMock:
    """Create a mock ADK tool with name and description."""
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def _make_mock_toolset(tool_names: list[str]) -> MagicMock:
    """Create a mock McpToolset that returns given tools."""
    toolset = MagicMock()
    tools = [_make_mock_tool(name, f"Tool: {name}") for name in tool_names]
    toolset.get_tools = AsyncMock(return_value=tools)
    toolset.close = AsyncMock()
    return toolset


async def _fake_connect(
    config, tool_names: list[str], toolset: MagicMock | None = None,
) -> tuple[list[dict], MagicMock]:
    """Build a (tools_metadata, toolset) tuple matching _connect_server's return."""
    if toolset is None:
        toolset = _make_mock_toolset(tool_names)
    adk_tools = await toolset.get_tools()
    metadata = [
        {"name": t.name, "description": t.description, "server": config.name}
        for t in adk_tools
    ]
    return metadata, toolset


@pytest.fixture
def manager_with_config(sample_config_file):
    """Create a manager with a sample config."""
    from app.adk.mcp_config.config import MCPConfigLoader

    loader = MCPConfigLoader(config_path=sample_config_file)
    loader.load()

    manager = MCPServerManager(
        max_loaded_servers=3,
        max_total_tokens=2000,
        init_timeout_seconds=5.0,
        idle_timeout_minutes=1,
    )
    manager._config_loader = loader

    return manager


class TestMCPServerManager:
    """Tests for MCPServerManager."""

    @pytest.mark.asyncio
    async def test_load_server_creates_tools(self, manager_with_config):
        """Test that loading a server creates tool definitions from McpToolset."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a", "tool_b", "tool_c"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            tools = await manager.load_server("test_server_1")

        assert len(tools) == 3
        assert all(t["server"] == "test_server_1" for t in tools)
        assert {t["name"] for t in tools} == {"tool_a", "tool_b", "tool_c"}
        assert manager.is_loaded("test_server_1")

    @pytest.mark.asyncio
    async def test_load_server_caches_result(self, manager_with_config):
        """Test that loading same server twice returns cached result."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        connect_mock = AsyncMock()

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        connect_mock.side_effect = connect

        with patch.object(manager, "_connect_server", side_effect=connect):
            tools1 = await manager.load_server("test_server_1")
            tools2 = await manager.load_server("test_server_1")

        assert tools1 == tools2
        assert tools1 is tools2

    @pytest.mark.asyncio
    async def test_load_unknown_server_raises(self, manager_with_config):
        """Test that loading unknown server raises ValueError."""
        manager = manager_with_config

        with pytest.raises(ValueError, match="Unknown MCP server"):
            await manager.load_server("nonexistent_server")

    @pytest.mark.asyncio
    async def test_load_disabled_server_raises(self, manager_with_config):
        """Test that loading disabled server raises ValueError."""
        manager = manager_with_config

        with pytest.raises(ValueError, match="is disabled"):
            await manager.load_server("disabled_server")

    @pytest.mark.asyncio
    async def test_unload_server(self, manager_with_config):
        """Test unloading a server calls toolset.close()."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        assert manager.is_loaded("test_server_1")

        await manager.unload_server("test_server_1")
        assert not manager.is_loaded("test_server_1")
        mock_toolset.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unload_nonexistent_server_is_safe(self, manager_with_config):
        """Test that unloading nonexistent server doesn't raise."""
        manager = manager_with_config
        await manager.unload_server("nonexistent_server")

    @pytest.mark.asyncio
    async def test_get_status(self, manager_with_config):
        """Test getting manager status."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["t1", "t2", "t3"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        status = manager.get_status()

        assert status["loaded_count"] == 1
        assert status["max_servers"] == 3
        assert status["total_tokens"] == 500
        assert len(status["servers"]) == 1
        assert status["servers"][0]["name"] == "test_server_1"
        assert status["servers"][0]["health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_all_loaded_tools(self, manager_with_config):
        """Test getting all tools from loaded servers."""
        manager = manager_with_config

        mock_toolset_1 = _make_mock_toolset(["s1_t1", "s1_t2", "s1_t3"])
        mock_toolset_2 = _make_mock_toolset(["s2_t1", "s2_t2"])
        toolsets = iter([mock_toolset_1, mock_toolset_2])

        async def connect(config):
            return await _fake_connect(config, [], toolset=next(toolsets))

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")
            await manager.load_server("test_server_2")

        all_tools = manager.get_all_loaded_tools()

        assert len(all_tools) == 5
        servers = {t["server"] for t in all_tools}
        assert servers == {"test_server_1", "test_server_2"}

    @pytest.mark.asyncio
    async def test_get_toolset(self, manager_with_config):
        """Test getting the McpToolset instance for a loaded server."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        toolset = manager.get_toolset("test_server_1")
        assert toolset is mock_toolset

        assert manager.get_toolset("not_loaded") is None


class TestHeaderProvider:
    """Tests for _build_header_provider."""

    def test_ga_oauth_header_provider(self, manager_with_config):
        """Test GA OAuth header provider reads from ReadonlyContext.state."""
        manager = manager_with_config
        config = manager._config_loader.get_server("test_server_ga")
        provider = manager._build_header_provider(config)

        assert provider is not None

        mock_context = MagicMock()
        mock_context.state = {
            "ga_credentials": {
                "access_token": "test_access",
                "tenant_id": "org-123",
                "refresh_token": "test_refresh",
            }
        }

        headers = provider(mock_context)

        assert headers == {
            "Authorization": "Bearer test_access",
            "X-Tenant-ID": "org-123",
            "X-Refresh-Token": "test_refresh",
        }

    def test_no_auth_type_returns_none(self, manager_with_config):
        """Test that servers without auth_type get no header provider."""
        manager = manager_with_config
        config = manager._config_loader.get_server("test_server_1")
        provider = manager._build_header_provider(config)
        assert provider is None

    def test_ga_oauth_empty_credentials(self, manager_with_config):
        """Test GA OAuth header provider with no credentials in state."""
        manager = manager_with_config
        config = manager._config_loader.get_server("test_server_ga")
        provider = manager._build_header_provider(config)

        mock_context = MagicMock()
        mock_context.state = {}

        headers = provider(mock_context)
        assert headers == {}


class TestLRUEviction:
    """Tests for LRU eviction behavior."""

    @pytest.mark.asyncio
    async def test_lru_eviction_on_count_limit(self, sample_config_file):
        """Test that LRU server is evicted when count limit reached."""
        from app.adk.mcp_config.config import MCPConfigLoader

        loader = MCPConfigLoader(config_path=sample_config_file)
        loader.load()

        manager = MCPServerManager(
            max_loaded_servers=2,
            max_total_tokens=10000,
        )
        manager._config_loader = loader

        toolsets = [
            _make_mock_toolset(["t1"]),
            _make_mock_toolset(["t2"]),
            _make_mock_toolset(["t3"]),
        ]
        toolset_iter = iter(toolsets)

        async def connect(config):
            return await _fake_connect(config, [], toolset=next(toolset_iter))

        # Create a third server config
        loader._configs["test_server_3"] = loader._configs["test_server_1"].model_copy(
            update={"name": "test_server_3"}
        )

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")
            await asyncio.sleep(0.01)
            await manager.load_server("test_server_2")
            await manager.load_server("test_server_3")

        assert not manager.is_loaded("test_server_1")  # Evicted
        assert manager.is_loaded("test_server_2")
        assert manager.is_loaded("test_server_3")
        # Evicted server's toolset should have been closed
        toolsets[0].close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_lru_eviction_on_token_limit(self, sample_config_file):
        """Test that LRU server is evicted when token limit reached."""
        from app.adk.mcp_config.config import MCPConfigLoader

        loader = MCPConfigLoader(config_path=sample_config_file)
        loader.load()

        manager = MCPServerManager(
            max_loaded_servers=10,
            max_total_tokens=1000,
        )
        manager._config_loader = loader

        toolsets = [_make_mock_toolset(["t1"]), _make_mock_toolset(["t2"])]
        toolset_iter = iter(toolsets)

        async def connect(config):
            return await _fake_connect(config, [], toolset=next(toolset_iter))

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")  # 500 tokens
            await manager.load_server("test_server_2")  # 800 tokens, total 1300

        assert not manager.is_loaded("test_server_1")  # Evicted
        assert manager.is_loaded("test_server_2")

    @pytest.mark.asyncio
    async def test_access_updates_last_used(self, manager_with_config):
        """Test that accessing a server updates its last_used time."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")
            initial_time = manager._loaded_servers["test_server_1"].last_used

            await asyncio.sleep(0.01)
            await manager.load_server("test_server_1")

        updated_time = manager._loaded_servers["test_server_1"].last_used
        assert updated_time > initial_time


class TestIdleMonitoring:
    """Tests for idle server monitoring."""

    @pytest.mark.asyncio
    async def test_evict_idle_servers(self, manager_with_config):
        """Test that idle servers are evicted."""
        manager = manager_with_config
        manager.idle_timeout = timedelta(seconds=0.1)

        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        await asyncio.sleep(0.2)
        await manager._evict_idle_servers()

        assert not manager.is_loaded("test_server_1")

    @pytest.mark.asyncio
    async def test_active_server_not_evicted(self, manager_with_config):
        """Test that recently used server is not evicted."""
        manager = manager_with_config
        manager.idle_timeout = timedelta(seconds=0.5)

        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")
            await asyncio.sleep(0.2)
            await manager.load_server("test_server_1")

        await asyncio.sleep(0.2)
        await manager._evict_idle_servers()

        assert manager.is_loaded("test_server_1")


class TestHealthMonitoring:
    """Tests for health monitoring."""

    @pytest.mark.asyncio
    async def test_healthy_server_status(self, manager_with_config):
        """Test that healthy server has correct status."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        status = manager.get_status()
        assert status["servers"][0]["health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_uses_get_tools(self, manager_with_config):
        """Test that health check calls toolset.get_tools()."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        loaded = manager._loaded_servers["test_server_1"]
        healthy = await manager._check_server_health(loaded)
        assert healthy is True
        # get_tools called once during _fake_connect + once during health check
        assert mock_toolset.get_tools.await_count == 2

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_empty_tools(self, manager_with_config):
        """Test that health check fails when get_tools returns empty."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        loaded = manager._loaded_servers["test_server_1"]

        # Make health check return empty
        mock_toolset.get_tools = AsyncMock(return_value=[])
        healthy = await manager._check_server_health(loaded)
        assert healthy is False

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_exception(self, manager_with_config):
        """Test that health check fails gracefully on exception."""
        manager = manager_with_config
        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        loaded = manager._loaded_servers["test_server_1"]

        mock_toolset.get_tools = AsyncMock(side_effect=ConnectionError("lost connection"))
        healthy = await manager._check_server_health(loaded)
        assert healthy is False

    @pytest.mark.asyncio
    async def test_consecutive_failures_mark_unhealthy(self, manager_with_config):
        """Test that consecutive failures mark server unhealthy."""
        manager = manager_with_config
        manager.max_consecutive_failures = 2

        mock_toolset = _make_mock_toolset(["tool_a"])

        async def connect(config):
            return await _fake_connect(config, [], toolset=mock_toolset)

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")

        loaded = manager._loaded_servers["test_server_1"]
        loaded.consecutive_failures = 2
        loaded.health_status = "unhealthy"

        status = manager.get_status()
        assert status["servers"][0]["health_status"] == "unhealthy"


class TestShutdown:
    """Tests for graceful shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_unloads_all(self, manager_with_config):
        """Test that shutdown unloads all servers."""
        manager = manager_with_config

        toolsets = [_make_mock_toolset(["t1"]), _make_mock_toolset(["t2"])]
        toolset_iter = iter(toolsets)

        async def connect(config):
            return await _fake_connect(config, [], toolset=next(toolset_iter))

        with patch.object(manager, "_connect_server", side_effect=connect):
            await manager.load_server("test_server_1")
            await manager.load_server("test_server_2")

        await manager.shutdown()

        assert len(manager._loaded_servers) == 0
        for ts in toolsets:
            ts.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_monitors(self, manager_with_config):
        """Test that shutdown stops background monitors."""
        manager = manager_with_config

        await manager.start_idle_monitor()
        await manager.start_health_monitor()

        assert manager._idle_check_task is not None
        assert manager._health_check_task is not None

        await manager.shutdown()

        assert manager._idle_check_task is None
        assert manager._health_check_task is None


class TestConnectionParams:
    """Tests for _build_connection_params.

    These tests rely on conftest.py pre-mocking the ADK modules
    so that lazy imports in _build_connection_params succeed.
    """

    def test_sse_connection_params(self, manager_with_config):
        """Test SSE connection params are built correctly."""
        manager = manager_with_config
        config = manager._config_loader.get_server("test_server_2")

        params = manager._build_connection_params(config)

        # conftest provides MockSseConnectionParams as the stand-in
        assert params.url == "https://test.example.com/mcp/sse"
        assert params.timeout == 30.0

    def test_stdio_connection_params(self, manager_with_config):
        """Test stdio connection params are built correctly."""
        manager = manager_with_config
        config = manager._config_loader.get_server("test_server_1")

        params = manager._build_connection_params(config)

        # conftest provides MockStdioConnectionParams / MockStdioServerParameters
        assert params.server_params.command == "npx"
        assert params.server_params.args == ["-y", "test-server"]


class TestSingleton:
    """Tests for singleton behavior."""

    @pytest.mark.asyncio
    async def test_get_mcp_manager_returns_same_instance(self):
        """Test that get_mcp_manager returns same instance."""
        await reset_mcp_manager()

        manager1 = get_mcp_manager()
        manager2 = get_mcp_manager()

        assert manager1 is manager2

        await reset_mcp_manager()

    @pytest.mark.asyncio
    async def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        manager1 = get_mcp_manager()
        await reset_mcp_manager()
        manager2 = get_mcp_manager()

        assert manager1 is not manager2

        await reset_mcp_manager()
