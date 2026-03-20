"""GA MCP Server health ping service.

Provides proactive reachability checks for the Google Analytics MCP server
used by the Agent Engine. This complements GCP's built-in tracing dashboards
(which only show data when tools are actively called) by detecting "server down"
scenarios even when no GA queries are in flight.
"""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 5.0


async def check_ga_mcp_health(
    url: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict[str, object]:
    """Ping the GA MCP server and return health status with latency.

    Args:
        url: Full base URL of the GA MCP server (e.g. ``https://…a.run.app``).
            Falls back to the ``GA_MCP_SERVER_URL`` environment variable.
        timeout: HTTP request timeout in seconds.

    Returns:
        Dict with ``reachable`` (bool), ``latency_ms`` (float | None),
        ``url`` (str), and ``error`` (str | None) keys.
    """
    resolved_url = url or os.getenv("GA_MCP_SERVER_URL", "")
    if not resolved_url:
        return {
            "reachable": False,
            "latency_ms": None,
            "url": "",
            "error": "GA_MCP_SERVER_URL not configured",
        }

    ping_url = resolved_url.rstrip("/")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(ping_url)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

        reachable = response.status_code < 500
        return {
            "reachable": reachable,
            "latency_ms": elapsed_ms,
            "url": ping_url,
            "error": None if reachable else f"HTTP {response.status_code}",
        }
    except httpx.TimeoutException:
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        return {
            "reachable": False,
            "latency_ms": elapsed_ms,
            "url": ping_url,
            "error": "Connection timed out",
        }
    except httpx.ConnectError as exc:
        return {
            "reachable": False,
            "latency_ms": None,
            "url": ping_url,
            "error": f"Connection failed: {exc}",
        }
    except Exception as exc:
        logger.exception("Unexpected error pinging GA MCP server")
        return {
            "reachable": False,
            "latency_ms": None,
            "url": ping_url,
            "error": str(exc),
        }
