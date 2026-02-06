"""Tests for MCP server manager."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
import yaml

from app.adk.mcp.manager import (
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
                    "url": "https://test.example.com",
                },
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


@pytest.fixture
def manager_with_config(sample_config_file):
    """Create a manager with a sample config."""
    from app.adk.mcp.config import MCPConfigLoader

    loader = MCPConfigLoader(config_path=sample_config_file)
    loader.load()

    manager = MCPServerManager(
        max_loaded_servers=3,
        max_total_tokens=2000,
        init_timeout_seconds=1.0,
        idle_timeout_minutes=1,
    )
    manager._config_loader = loader

    return manager


class TestMCPServerManager:
    """Tests for MCPServerManager."""

    @pytest.mark.asyncio
    async def test_load_server_creates_tools(self, manager_with_config):
        """Test that loading a server creates tool definitions."""
        manager = manager_with_config

        tools = await manager.load_server("test_server_1")

        assert len(tools) == 3
        assert all(t["server"] == "test_server_1" for t in tools)
        assert manager.is_loaded("test_server_1")

    @pytest.mark.asyncio
    async def test_load_server_caches_result(self, manager_with_config):
        """Test that loading same server twice returns cached result."""
        manager = manager_with_config

        tools1 = await manager.load_server("test_server_1")
        tools2 = await manager.load_server("test_server_1")

        assert tools1 == tools2
        # Should be the same object (cached)
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
        """Test unloading a server."""
        manager = manager_with_config

        await manager.load_server("test_server_1")
        assert manager.is_loaded("test_server_1")

        await manager.unload_server("test_server_1")
        assert not manager.is_loaded("test_server_1")

    @pytest.mark.asyncio
    async def test_unload_nonexistent_server_is_safe(self, manager_with_config):
        """Test that unloading nonexistent server doesn't raise."""
        manager = manager_with_config

        # Should not raise
        await manager.unload_server("nonexistent_server")

    @pytest.mark.asyncio
    async def test_get_status(self, manager_with_config):
        """Test getting manager status."""
        manager = manager_with_config

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

        await manager.load_server("test_server_1")
        await manager.load_server("test_server_2")

        all_tools = manager.get_all_loaded_tools()

        assert len(all_tools) == 8  # 3 + 5
        servers = {t["server"] for t in all_tools}
        assert servers == {"test_server_1", "test_server_2"}


class TestLRUEviction:
    """Tests for LRU eviction behavior."""

    @pytest.mark.asyncio
    async def test_lru_eviction_on_count_limit(self, sample_config_file):
        """Test that LRU server is evicted when count limit reached."""
        from app.adk.mcp.config import MCPConfigLoader

        loader = MCPConfigLoader(config_path=sample_config_file)
        loader.load()

        # Create manager with max 2 servers
        manager = MCPServerManager(
            max_loaded_servers=2,
            max_total_tokens=10000,  # High token limit
        )
        manager._config_loader = loader

        # Load first two servers
        await manager.load_server("test_server_1")
        await asyncio.sleep(0.01)  # Ensure different timestamps
        await manager.load_server("test_server_2")

        assert manager.is_loaded("test_server_1")
        assert manager.is_loaded("test_server_2")

        # Create a third server config
        loader._configs["test_server_3"] = loader._configs["test_server_1"].model_copy(
            update={"name": "test_server_3"}
        )

        # Load third server - should evict test_server_1 (LRU)
        await manager.load_server("test_server_3")

        assert not manager.is_loaded("test_server_1")  # Evicted
        assert manager.is_loaded("test_server_2")
        assert manager.is_loaded("test_server_3")

    @pytest.mark.asyncio
    async def test_lru_eviction_on_token_limit(self, sample_config_file):
        """Test that LRU server is evicted when token limit reached."""
        from app.adk.mcp.config import MCPConfigLoader

        loader = MCPConfigLoader(config_path=sample_config_file)
        loader.load()

        # Create manager with low token limit
        manager = MCPServerManager(
            max_loaded_servers=10,
            max_total_tokens=1000,  # Low - only test_server_1 fits
        )
        manager._config_loader = loader

        # Load test_server_1 (500 tokens)
        await manager.load_server("test_server_1")

        # Load test_server_2 (800 tokens) - total would be 1300, exceeds 1000
        # Should evict test_server_1 first
        await manager.load_server("test_server_2")

        assert not manager.is_loaded("test_server_1")  # Evicted
        assert manager.is_loaded("test_server_2")

    @pytest.mark.asyncio
    async def test_access_updates_last_used(self, manager_with_config):
        """Test that accessing a server updates its last_used time."""
        manager = manager_with_config

        await manager.load_server("test_server_1")
        initial_time = manager._loaded_servers["test_server_1"].last_used

        await asyncio.sleep(0.01)  # Small delay
        await manager.load_server("test_server_1")  # Access again

        updated_time = manager._loaded_servers["test_server_1"].last_used
        assert updated_time > initial_time


class TestIdleMonitoring:
    """Tests for idle server monitoring."""

    @pytest.mark.asyncio
    async def test_evict_idle_servers(self, manager_with_config):
        """Test that idle servers are evicted."""
        manager = manager_with_config
        manager.idle_timeout = timedelta(seconds=0.1)  # Very short for testing

        await manager.load_server("test_server_1")

        # Wait for idle timeout
        await asyncio.sleep(0.2)

        # Manually trigger eviction check
        await manager._evict_idle_servers()

        assert not manager.is_loaded("test_server_1")

    @pytest.mark.asyncio
    async def test_active_server_not_evicted(self, manager_with_config):
        """Test that recently used server is not evicted."""
        manager = manager_with_config
        manager.idle_timeout = timedelta(seconds=0.5)

        await manager.load_server("test_server_1")

        # Keep accessing to stay active
        await asyncio.sleep(0.2)
        await manager.load_server("test_server_1")
        await asyncio.sleep(0.2)

        # Trigger eviction check
        await manager._evict_idle_servers()

        # Should still be loaded (accessed recently)
        assert manager.is_loaded("test_server_1")


class TestHealthMonitoring:
    """Tests for health monitoring."""

    @pytest.mark.asyncio
    async def test_healthy_server_status(self, manager_with_config):
        """Test that healthy server has correct status."""
        manager = manager_with_config

        await manager.load_server("test_server_1")

        status = manager.get_status()
        assert status["servers"][0]["health_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_consecutive_failures_mark_unhealthy(self, manager_with_config):
        """Test that consecutive failures mark server unhealthy."""
        manager = manager_with_config
        manager.max_consecutive_failures = 2

        await manager.load_server("test_server_1")
        loaded = manager._loaded_servers["test_server_1"]

        # Simulate failures
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

        await manager.load_server("test_server_1")
        await manager.load_server("test_server_2")

        await manager.shutdown()

        assert len(manager._loaded_servers) == 0

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
