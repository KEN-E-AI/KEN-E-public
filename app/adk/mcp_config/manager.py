"""MCP Server Manager with lazy loading and lifecycle management.

This module provides the core MCP server management functionality:
- Lazy initialization: Servers start only when first tool is requested
- Hard connection cap: RuntimeError when max_loaded_servers is exceeded
- Health monitoring: Periodic health checks with auto-reconnection

Toolset construction is delegated to ``app.adk.agents.agent_factory.mcp``
(imported lazily inside ``_connect_server`` to avoid circular imports).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from shared.structured_logging import get_structured_logger, log_context

from .config import (
    MCPServerConfig,
    get_mcp_config_loader,
)

logger = get_structured_logger(__name__)


@dataclass
class LoadedServer:
    """Tracks a loaded MCP server's state.

    Attributes:
        name: Server identifier
        config: Server configuration
        tools: List of tools provided by the server
        loaded_at: When the server was loaded
        last_used: Last time the server was accessed
        token_estimate: Estimated context tokens for this server
        health_status: Current health status (healthy, degraded, unhealthy)
        consecutive_failures: Number of consecutive health check failures
    """

    name: str
    config: MCPServerConfig
    tools: list[dict[str, Any]] = field(default_factory=list)
    loaded_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    token_estimate: int = 0
    health_status: str = "healthy"
    consecutive_failures: int = 0
    _connection: Any = None  # Store the actual MCP connection
    _toolset: Any = None  # McpToolset instance for agent use


class MCPServerManager:
    """Manages MCP server connections with lazy-loading.

    Features:
    - On-demand initialization (servers start when first tool is requested)
    - Hard cap on concurrent connections (RuntimeError when exceeded)
    - Health monitoring with automatic reconnection
    - Graceful shutdown

    Usage:
        manager = get_mcp_manager()
        tools = await manager.load_server("google_analytics_mcp")

        # Get status
        status = manager.get_status()

        # Unload when done
        await manager.unload_server("google_analytics_mcp")
    """

    def __init__(
        self,
        max_loaded_servers: int = 10,
        init_timeout_seconds: float = 30.0,
        health_check_interval_seconds: int = 30,
        max_consecutive_failures: int = 3,
    ):
        """Initialize the MCP server manager.

        Args:
            max_loaded_servers: Hard cap on concurrent server connections;
                raises RuntimeError when exceeded (no LRU eviction).
            init_timeout_seconds: Timeout for server initialization
            health_check_interval_seconds: Interval between health checks
            max_consecutive_failures: Failures before marking unhealthy
        """
        self.max_loaded_servers = max_loaded_servers
        self.init_timeout = init_timeout_seconds
        self.health_check_interval = health_check_interval_seconds
        self.max_consecutive_failures = max_consecutive_failures

        self._config_loader = get_mcp_config_loader()
        self._loaded_servers: dict[str, LoadedServer] = {}
        self._lock = asyncio.Lock()

        # Background task handle for health monitoring
        self._health_check_task: asyncio.Task[None] | None = None

    async def load_server(self, server_name: str) -> list[dict[str, Any]]:
        """Load an MCP server and return its tools.

        Implements lazy-loading: servers only start when first tool is requested.
        If server is already loaded, updates last_used and returns cached tools.

        Args:
            server_name: Name of the MCP server to load

        Returns:
            List of tool definitions from the server

        Raises:
            ValueError: If server is unknown or disabled
            TimeoutError: If server fails to initialize within timeout
            ConnectionError: If connection to server fails
        """
        async with self._lock:
            # Return cached if already loaded
            if server_name in self._loaded_servers:
                loaded = self._loaded_servers[server_name]
                loaded.last_used = datetime.now(timezone.utc)
                logger.info(
                    "MCP server cache hit",
                    extra=log_context(
                        component="mcp_manager",
                        action="cache_hit",
                        extra={
                            "server_name": server_name,
                            "tool_count": len(loaded.tools),
                        },
                    ),
                )
                return loaded.tools

            # Get server configuration
            config = self._config_loader.get_server(server_name)
            if config is None:
                raise ValueError(f"Unknown MCP server: {server_name}")
            if not config.enabled:
                raise ValueError(f"MCP server '{server_name}' is disabled")

            # Hard cap — no LRU eviction; callers must unload before loading more.
            if len(self._loaded_servers) >= self.max_loaded_servers:
                raise RuntimeError(
                    f"MCP server capacity reached ({self.max_loaded_servers}); "
                    "unload a server before loading another"
                )

            # Initialize the server
            logger.info(
                "Initializing MCP server",
                extra=log_context(
                    component="mcp_manager",
                    action="init_start",
                    extra={
                        "server_name": server_name,
                        "connection_type": config.connection.connection_type,
                    },
                ),
            )

            start_time = datetime.now(timezone.utc)
            try:
                tools, toolset = await asyncio.wait_for(
                    self._connect_server(config),
                    timeout=self.init_timeout,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"MCP server init timeout after {self.init_timeout}s",
                    extra=log_context(
                        component="mcp_manager",
                        action="init_timeout",
                        extra={"server_name": server_name},
                    ),
                )
                raise TimeoutError(
                    f"Server '{server_name}' failed to initialize "
                    f"within {self.init_timeout}s"
                ) from None

            init_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Store loaded server
            now = datetime.now(timezone.utc)
            self._loaded_servers[server_name] = LoadedServer(
                name=server_name,
                config=config,
                tools=tools,
                loaded_at=now,
                last_used=now,
                token_estimate=config.estimated_tokens,
                _connection=toolset,
                _toolset=toolset,
            )

            logger.info(
                "MCP server initialized successfully",
                extra=log_context(
                    component="mcp_manager",
                    action="init_complete",
                    extra={
                        "server_name": server_name,
                        "tool_count": len(tools),
                        "init_duration_seconds": init_duration,
                    },
                ),
            )

            return tools

    async def _connect_server(
        self, config: MCPServerConfig
    ) -> tuple[list[dict[str, Any]], Any]:
        """Create connection to MCP server via the agent factory.

        Delegates toolset construction (connection params + header provider) to
        ``build_toolset_for_config`` so that logic is not duplicated here.

        Args:
            config: Server configuration

        Returns:
            Tuple of (tools metadata list, McpToolset instance)
        """
        from app.adk.agents.agent_factory.mcp import build_toolset_for_config

        toolset = build_toolset_for_config(config)
        adk_tools = await toolset.get_tools()
        tools_metadata = [
            {
                "name": t.name,
                "description": t.description,
                "server": config.name,
            }
            for t in adk_tools
        ]
        return tools_metadata, toolset

    async def reload(self) -> dict[str, Any]:
        """Re-read configs from the underlying loader and evict stale servers.

        Preserves lazy-load semantics: evicted servers are simply removed from
        ``_loaded_servers`` — the next ``load_server`` call re-initializes them
        from the fresh config. Servers whose config is byte-for-byte identical
        to the cached version are left loaded.

        Servers removed from Firestore entirely are unloaded.

        Returns:
            ``{"unloaded": [server_name, ...], "kept": int}`` — caller can
            surface as an admin response or audit record.
        """
        async with self._lock:
            self._config_loader.reload()
            new_configs = self._config_loader.configs

            unloaded: list[str] = []
            for server_name in list(self._loaded_servers.keys()):
                loaded = self._loaded_servers[server_name]
                new_cfg = new_configs.get(server_name)
                if new_cfg is None or new_cfg != loaded.config:
                    await self._unload_server_unlocked(server_name)
                    unloaded.append(server_name)

            kept = len(self._loaded_servers)
            logger.info(
                "MCP config reloaded",
                extra=log_context(
                    component="mcp_manager",
                    action="reload",
                    extra={
                        "unloaded_count": len(unloaded),
                        "kept_count": kept,
                        "total_configs": len(new_configs),
                    },
                ),
            )
            return {"unloaded": unloaded, "kept": kept}

    async def unload_server(self, server_name: str) -> None:
        """Unload an MCP server and free resources.

        Args:
            server_name: Name of the server to unload
        """
        async with self._lock:
            await self._unload_server_unlocked(server_name)

    async def _unload_server_unlocked(self, server_name: str) -> None:
        """Unload server without acquiring lock (for internal use).

        Args:
            server_name: Name of the server to unload
        """
        if server_name not in self._loaded_servers:
            return

        loaded = self._loaded_servers[server_name]

        try:
            if loaded._toolset is not None:
                await loaded._toolset.close()
            elif loaded._connection and hasattr(loaded._connection, "close"):
                await loaded._connection.close()
        except Exception as e:
            logger.warning(
                f"Error closing MCP server: {e}",
                extra=log_context(
                    component="mcp_manager",
                    action="unload_error",
                    error_message=str(e),
                    extra={"server_name": server_name},
                ),
            )

        del self._loaded_servers[server_name]

        logger.info(
            "MCP server unloaded",
            extra=log_context(
                component="mcp_manager",
                action="unload",
                extra={"server_name": server_name},
            ),
        )

    def get_loaded_tools(self, server_name: str) -> list[dict[str, Any]]:
        """Get tools for a loaded server (no loading, returns empty if not loaded).

        Args:
            server_name: Name of the server

        Returns:
            List of tools or empty list if not loaded
        """
        if server_name not in self._loaded_servers:
            return []
        return self._loaded_servers[server_name].tools

    def get_all_loaded_tools(self) -> list[dict[str, Any]]:
        """Get all tools from all currently loaded servers.

        Returns:
            Combined list of all tools from all loaded servers
        """
        all_tools: list[dict[str, Any]] = []
        for loaded in self._loaded_servers.values():
            all_tools.extend(loaded.tools)
        return all_tools

    def get_toolset(self, server_name: str) -> Any:
        """Get the McpToolset instance for a loaded server.

        Used by agents to include the toolset in their tool list.

        Args:
            server_name: Name of the server

        Returns:
            McpToolset instance or None if not loaded
        """
        if server_name in self._loaded_servers:
            return self._loaded_servers[server_name]._toolset
        return None

    def get_status(self) -> dict[str, Any]:
        """Get current server loading status for monitoring.

        Returns:
            Status dictionary with counts and server details
        """
        return {
            "loaded_count": len(self._loaded_servers),
            "max_servers": self.max_loaded_servers,
            "servers": [
                {
                    "name": name,
                    "tool_count": len(loaded.tools),
                    "tokens": loaded.token_estimate,
                    "loaded_at": loaded.loaded_at.isoformat(),
                    "last_used": loaded.last_used.isoformat(),
                    "health_status": loaded.health_status,
                }
                for name, loaded in self._loaded_servers.items()
            ],
        }

    def is_loaded(self, server_name: str) -> bool:
        """Check if a server is currently loaded.

        Args:
            server_name: Name of the server

        Returns:
            True if server is loaded
        """
        return server_name in self._loaded_servers

    # === Health Monitoring ===

    async def start_health_monitor(self) -> None:
        """Start background health monitoring."""
        if self._health_check_task is not None:
            return

        self._health_check_task = asyncio.create_task(self._health_monitor_loop())
        logger.info("MCP health monitor started")

    async def stop_health_monitor(self) -> None:
        """Stop health monitoring."""
        if self._health_check_task is not None:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("MCP health monitor stopped")

    async def _health_monitor_loop(self) -> None:
        """Background loop for health checks."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_servers_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _check_all_servers_health(self) -> None:
        """Check health of all loaded servers."""
        async with self._lock:
            for name, loaded in list(self._loaded_servers.items()):
                try:
                    healthy = await self._check_server_health(loaded)

                    if healthy:
                        loaded.health_status = "healthy"
                        loaded.consecutive_failures = 0
                    else:
                        loaded.consecutive_failures += 1
                        if loaded.consecutive_failures >= self.max_consecutive_failures:
                            loaded.health_status = "unhealthy"
                            logger.warning(
                                f"Server '{name}' unhealthy after {loaded.consecutive_failures} failures",
                                extra=log_context(
                                    component="mcp_manager",
                                    action="health_alert",
                                    extra={
                                        "server_name": name,
                                        "failures": loaded.consecutive_failures,
                                    },
                                ),
                            )
                            # Attempt reconnection (release lock first)
                            # Task is fire-and-forget; we don't need the result
                            _reconnect_task = asyncio.create_task(
                                self._attempt_reconnection(name)
                            )
                            del _reconnect_task  # Explicitly release reference
                        else:
                            loaded.health_status = "degraded"

                except Exception as e:
                    logger.error(f"Health check failed for '{name}': {e}")
                    loaded.consecutive_failures += 1

    async def _check_server_health(self, loaded: LoadedServer) -> bool:
        """Check if a single server is healthy by listing its tools.

        Args:
            loaded: The loaded server to check

        Returns:
            True if server is healthy
        """
        if loaded._toolset is None:
            return False

        try:
            tools = await asyncio.wait_for(loaded._toolset.get_tools(), timeout=5.0)
            return len(tools) > 0
        except Exception:
            return False

    async def _attempt_reconnection(self, server_name: str) -> None:
        """Attempt to reconnect an unhealthy server.

        Args:
            server_name: Name of the server to reconnect
        """
        logger.info(f"Attempting reconnection for '{server_name}'")

        # Unload the unhealthy server
        await self.unload_server(server_name)

        # Try to reload with exponential backoff
        for attempt in range(3):
            try:
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s backoff
                await self.load_server(server_name)
                logger.info(f"Reconnection successful for '{server_name}'")
                return
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")

        logger.error(f"All reconnection attempts failed for '{server_name}'")

    # === Shutdown ===

    async def shutdown(self) -> None:
        """Gracefully shutdown all servers and background tasks."""
        logger.info("Shutting down MCP server manager")

        # Stop background monitor
        await self.stop_health_monitor()

        # Unload all servers
        async with self._lock:
            for server_name in list(self._loaded_servers.keys()):
                await self._unload_server_unlocked(server_name)

        logger.info("MCP server manager shutdown complete")


# Singleton instance
_manager: MCPServerManager | None = None


def get_mcp_manager() -> MCPServerManager:
    """Get the singleton MCP server manager.

    Returns:
        Shared MCPServerManager instance
    """
    global _manager
    if _manager is None:
        _manager = MCPServerManager()
    return _manager


async def reset_mcp_manager() -> None:
    """Reset the MCP manager singleton (for testing).

    Shuts down any existing manager and clears the singleton.
    """
    global _manager
    if _manager is not None:
        await _manager.shutdown()
        _manager = None
