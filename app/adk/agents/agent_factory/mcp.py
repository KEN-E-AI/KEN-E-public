"""MCP toolset construction for the agent factory (AH-PRD-02 Phase 2).

Reads ``mcp_server_configs/{server_id}`` Firestore documents and materialises
ADK ``McpToolset`` instances ready for specialist construction.  The three
public entry points are:

* ``build_toolset_for_doc(server_id, doc)`` — pure function; creates one
  ``McpToolset`` from a raw Firestore document dict.  No Firestore dependency.
* ``build_toolset_for_config(config)`` — thin wrapper for callers that already
  hold a validated ``MCPServerConfig`` Pydantic model; delegates to
  ``build_toolset_for_doc`` after converting to doc-shape dict.
* ``load_all_mcp_toolsets(db, ...)`` — loads every *enabled* doc from the
  ``mcp_server_configs`` collection and returns a ``{server_id: McpToolset}``
  dict.  Callers that want to group toolsets by specialist can iterate over
  each doc's ``specialist_categories`` field themselves.
* ``load_toolsets_for_specialist(category, *, db, ...)`` — convenience wrapper
  that filters to docs whose ``specialist_categories`` list contains *category*.

Design notes
------------
* ADK's ``McpToolset`` is imported lazily (inside function bodies) to keep the
  module importable in test environments that do not have a live ADK install.
* Connection params are built from the raw ``connection`` sub-dict using the
  same two-branch (sse / stdio) logic as ``MCPServerManager._build_connection_params``
  (`app/adk/mcp_config/manager.py:260-293`), now extracted as a stateless
  function with no manager dependency.
* Header providers are delegated entirely to ``make_header_provider`` from
  AH-12.  When ``auth_type`` is ``None`` the toolset is built with
  ``header_provider=None`` (unauthenticated server).
* ``auth_type`` values not recognised by AH-12's ``CREDENTIAL_KEYS`` raise
  ``ValueError`` at factory build time (fail-fast, not at request time).
* Enabled semantics: only documents with ``enabled`` explicitly set to ``True``
  are loaded.  Absent or non-True values are treated as disabled (fail-closed).
* SSE URLs must use https and must not target known internal/metadata hosts.
* stdio ``command``, ``args``, and ``env`` are type-validated at build time.
  The mcp_server_configs collection is operator-controlled; these checks catch
  configuration typos rather than untrusted input.

Future (IN-PRD-06): ``make_header_provider`` will be rewritten to fetch
credentials from the Integrations internal endpoint rather than ADK session
state.  The public surface of this module is unaffected by that migration.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlparse

from app.adk.agents.agent_factory.header_provider import make_header_provider
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# Production Firestore collection (populated by Sprint 6 Story 1.1.4-2).
# The PRD uses the informal alias "mcp_servers/" to reference the same data;
# the actual collection that migrate_mcp_to_firestore.py wrote to is
# "mcp_server_configs/".  See AH-11 Decisions & Assumptions #1.
MCP_COLLECTION = "mcp_server_configs"

# SSE URLs must not target internal GCP metadata or loopback addresses.
_BLOCKED_SSE_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "localhost",
        "127.0.0.1",
        "::1",
    }
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MCPFactoryError(Exception):
    """Base class for errors raised during MCP toolset construction."""


class MCPSchemaError(MCPFactoryError):
    """Raised when a Firestore MCP server document is missing required fields
    or carries an unrecognised ``connection_type``."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(project_id: str | None) -> str:
    # TODO: extract alongside config_loader.py copy to a shared _firestore.py
    if project_id:
        return project_id
    return os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")


def _build_firestore_client(project_id: str) -> Any:
    # TODO: extract alongside config_loader.py copy to a shared _firestore.py
    from google.auth import default as google_auth_default
    from google.cloud import firestore

    credentials, _ = google_auth_default()
    return firestore.Client(project=project_id, credentials=credentials)


def _stream_enabled_docs(db: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield ``(server_id, doc)`` for every explicitly-enabled document.

    Fail-closed: only documents with ``enabled`` set to exactly ``True`` are
    yielded.  Documents with ``enabled=False`` or a missing ``enabled`` field
    are skipped silently.
    """
    for snapshot in db.collection(MCP_COLLECTION).stream():
        server_id: str = snapshot.id
        doc: dict[str, Any] = snapshot.to_dict() or {}
        if doc.get("enabled") is not True:
            logger.debug("Skipping non-enabled MCP server %r", server_id)
            continue
        yield server_id, doc


def _validate_sse_url(server_id: str, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise MCPSchemaError(
            f"MCP server {server_id!r}: SSE url must use https, "
            f"got scheme {parsed.scheme!r}"
        )
    host = (parsed.hostname or "").lower()
    if host in _BLOCKED_SSE_HOSTS:
        raise MCPSchemaError(
            f"MCP server {server_id!r}: SSE url targets a reserved/internal host {host!r}"
        )


def _build_connection_params(server_id: str, connection: dict[str, Any]) -> Any:
    """Convert the ``connection`` sub-dict from a Firestore doc into an ADK
    ``SseConnectionParams`` or ``StdioConnectionParams`` instance.

    Mirrors ``MCPServerManager._build_connection_params`` as a pure function.

    Args:
        server_id: Used in error messages only.
        connection: The raw ``connection`` mapping from the Firestore doc.

    Returns:
        ``SseConnectionParams`` or ``StdioConnectionParams``.

    Raises:
        MCPSchemaError: If ``connection_type`` is absent, empty, or not one of
            ``{"sse", "stdio"}``; or if field types/values fail validation.
    """
    connection_type = connection.get("connection_type")
    if not isinstance(connection_type, str) or not connection_type:
        raise MCPSchemaError(
            f"MCP server {server_id!r}: 'connection.connection_type' is missing or empty"
        )

    if connection_type == "sse":
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            SseConnectionParams,
        )

        url: str = connection["url"]
        _validate_sse_url(server_id, url)

        return SseConnectionParams(
            url=url,
            headers=connection.get("headers") or None,
            timeout=float(connection.get("timeout_seconds", 30)),
        )

    if connection_type == "stdio":
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StdioConnectionParams,
        )
        from mcp.client.stdio import StdioServerParameters

        command: str = connection["command"]
        if not isinstance(command, str) or not command:
            raise MCPSchemaError(
                f"MCP server {server_id!r}: stdio 'command' must be a non-empty string"
            )

        args: list[str] = connection.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise MCPSchemaError(
                f"MCP server {server_id!r}: stdio 'args' must be a list of strings"
            )

        raw_env = connection.get("env") or None
        if raw_env is not None and not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw_env.items()
        ):
            raise MCPSchemaError(
                f"MCP server {server_id!r}: stdio 'env' values must all be strings"
            )

        return StdioConnectionParams(
            server_params=StdioServerParameters(
                command=command,
                args=args,
                env=raw_env,
            ),
            timeout=5.0,
        )

    raise MCPSchemaError(
        f"MCP server {server_id!r}: unknown connection_type {connection_type!r}; "
        f"expected 'sse' or 'stdio'"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_toolset_for_doc(server_id: str, doc: dict[str, Any]) -> Any:
    """Build an ADK ``McpToolset`` from a single raw Firestore document dict.

    Pure function — no Firestore dependency.  Suitable for unit testing with
    plain dict fixtures.

    Args:
        server_id: The Firestore document ID (used in error messages and logs).
        doc: Raw ``mcp_server_configs/{server_id}`` document as returned by
            ``snapshot.to_dict()``.

    Returns:
        An ``McpToolset`` instance with ``connection_params`` and
        ``header_provider`` wired according to the document's ``connection``
        and ``auth_type`` fields.

    Raises:
        MCPSchemaError: ``connection`` sub-dict is missing or has an unknown
            ``connection_type``; or field type validation fails.
        ValueError: ``auth_type`` is a non-None value not recognised by
            ``make_header_provider`` (AH-12 fail-fast contract).
    """
    connection = doc.get("connection")
    if not connection:
        raise MCPSchemaError(
            f"MCP server {server_id!r}: required 'connection' field is missing"
        )

    connection_params = _build_connection_params(server_id, connection)

    auth_type: str | None = doc.get("auth_type")
    header_provider: Callable[..., dict[str, str]] | None = (
        make_header_provider(auth_type) if auth_type is not None else None
    )

    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

    toolset = McpToolset(
        connection_params=connection_params,
        header_provider=header_provider,
    )
    logger.debug(
        "Built McpToolset for server %r (auth_type=%r)", server_id, auth_type
    )
    return toolset


def build_toolset_for_config(config: Any) -> Any:
    """Build an ADK ``McpToolset`` from a validated runtime ``MCPServerConfig``.

    For callers that already have a validated runtime ``MCPServerConfig``; raw-doc
    callers should use ``build_toolset_for_doc``.

    Converts the Pydantic model to the equivalent Firestore doc-shape dict and
    delegates to ``build_toolset_for_doc``.  This keeps the two code paths in
    lock-step: any schema-validation or connection-params logic added to
    ``build_toolset_for_doc`` automatically applies here too.

    Args:
        config: A ``MCPServerConfig`` instance (from ``app.adk.mcp_config.config``).

    Returns:
        An ``McpToolset`` instance with ``connection_params`` and
        ``header_provider`` wired according to ``config.connection`` and
        ``config.auth_type``.

    Raises:
        MCPSchemaError: ``config.connection`` is not an ``SseConnectionConfig``
            or ``StdioConnectionConfig`` instance.
        ValueError: ``config.auth_type`` is a non-None value not recognised by
            ``make_header_provider`` (AH-12 fail-fast contract).
    """
    from app.adk.mcp_config.config import (
        MCPServerConfig,
        SseConnectionConfig,
        StdioConnectionConfig,
    )

    conn = config.connection

    if isinstance(conn, SseConnectionConfig):
        connection_dict: dict[str, Any] = {
            "connection_type": "sse",
            "url": conn.url,
            "headers": conn.headers or None,
            "timeout_seconds": conn.timeout_seconds,
        }
    elif isinstance(conn, StdioConnectionConfig):
        connection_dict = {
            "connection_type": "stdio",
            "command": conn.command,
            "args": conn.args,
            "env": conn.env or None,
        }
    else:
        raise MCPSchemaError(
            f"MCP server {config.name!r}: connection type {type(conn).__name__!r} "
            f"is not SseConnectionConfig or StdioConnectionConfig"
        )

    doc: dict[str, Any] = {
        "connection": connection_dict,
        "auth_type": config.auth_type,
    }

    return build_toolset_for_doc(config.name, doc)


def load_all_mcp_toolsets(
    db: Any | None = None,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Load every *enabled* MCP server from Firestore and return a flat
    ``{server_id: McpToolset}`` dict.

    Only documents with ``enabled`` explicitly set to ``True`` are included
    (fail-closed).  Docs that raise ``MCPSchemaError`` or ``ValueError`` during
    toolset construction are logged as errors and excluded; callers can detect
    this by comparing the returned dict size to the total number of enabled docs.

    Args:
        db: Optional pre-built Firestore client (for testing / DI).  When
            ``None`` a client is created from ``project_id`` / env.
        project_id: GCP project ID.  Resolved via argument → env var
            ``GOOGLE_CLOUD_PROJECT_ID`` → ``"ken-e-dev"``.

    Returns:
        ``{server_id: McpToolset}`` for every enabled server doc.
    """
    if db is None:
        resolved = _resolve_project_id(project_id)
        db = _build_firestore_client(resolved)

    toolsets: dict[str, Any] = {}

    for server_id, doc in _stream_enabled_docs(db):
        try:
            toolsets[server_id] = build_toolset_for_doc(server_id, doc)
        except (MCPSchemaError, ValueError) as exc:
            logger.error(
                "Failed to build toolset for MCP server %r: %s", server_id, exc
            )

    logger.info(
        "Loaded %d MCP toolsets from %r", len(toolsets), MCP_COLLECTION
    )
    return toolsets


def load_toolsets_for_specialist(
    specialist_category: str,
    *,
    db: Any | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Return a ``{server_id: McpToolset}`` dict for a specific specialist.

    Filters enabled docs to those whose ``specialist_categories`` list contains
    *specialist_category*.  A server shared across multiple specialists (e.g.
    ``specialist_categories=["google_analytics","google_ads"]``) will appear in
    the result for both ``"google_analytics"`` and ``"google_ads"`` queries.

    Args:
        specialist_category: The category string to filter by (e.g.
            ``"google_analytics"``).
        db: Optional pre-built Firestore client (for testing / DI).
        project_id: GCP project ID.  Resolved as in ``load_all_mcp_toolsets``.

    Returns:
        ``{server_id: McpToolset}`` for all enabled servers that include
        *specialist_category* in their ``specialist_categories`` list.
    """
    if db is None:
        resolved = _resolve_project_id(project_id)
        db = _build_firestore_client(resolved)

    toolsets: dict[str, Any] = {}

    for server_id, doc in _stream_enabled_docs(db):
        categories: list[str] = doc.get("specialist_categories", [])
        if specialist_category not in categories:
            continue

        try:
            toolsets[server_id] = build_toolset_for_doc(server_id, doc)
        except (MCPSchemaError, ValueError) as exc:
            logger.error(
                "Failed to build toolset for MCP server %r: %s", server_id, exc
            )

    logger.info(
        "Loaded %d MCP toolsets for specialist %r",
        len(toolsets),
        specialist_category,
    )
    return toolsets
