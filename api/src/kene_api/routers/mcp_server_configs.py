"""MCP server configuration admin endpoints (Story 1.1.4-3).

Mirrors ``routers/agent_configs.py`` shape. All endpoints require super-admin
(``@ken-e.ai`` email). PUT writes an audit entry per Decision C and, when the
underlying connection changes, triggers ``MCPServerManager.reload()`` so the
next agent invocation picks up the new tool definitions (Sprint 6 AC-6.11).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import firestore
from pydantic import ValidationError

from shared.trace_metadata import parse_semver, validate_semver

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore
from ..models.agent_config_models import ConfigAuditEntry
from ..models.mcp_server_models import (
    MCPServerConfigUpdate,
    MCPServerFirestoreConfig,
)
from ..services.audit_service import log_config_action
from ..services.config_versioning import increment_version, sanitize_updated_by

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp-server-configs", tags=["mcp-server-configs"])

MCP_COLLECTION = "mcp_server_configs"

# Server IDs are Firestore doc IDs plus a runtime key in MCPServerManager.
# Allow lowercase alphanumerics, hyphens, and underscores. This also guards
# against path-traversal (``/`` and ``..``).
_SERVER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")

# Field changes that invalidate the cached runtime toolset. Changes to
# description, keywords, specialist_categories, metadata etc. don't force a
# reconnect — the McpToolset binding keeps working unchanged.
_RELOAD_TRIGGER_FIELDS: frozenset[str] = frozenset(
    {"connection", "auth_type", "enabled", "kind"}
)


# Note: GET and PUT deliberately use ``response_model=None`` and return the
# raw Firestore dict. Wrapping the payload in ``MCPServerFirestoreConfig``
# would run ``SseConnectionConfig`` / ``StdioConnectionConfig`` field
# validators, which resolve ``${VAR}`` patterns via ``get_env_or_secret`` —
# leaking every secret into the response body, the audit trail, and (for
# PUT) Firestore itself. By keeping the admin path on raw dicts, literal
# ``${VAR}`` strings are preserved end-to-end.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_admin(user: UserContext, action: str) -> None:
    if not user.is_super_admin:
        logger.warning(
            f"Unauthorized MCP config {action} by user {user.user_id} ({user.email})"
        )
        raise HTTPException(
            status_code=403,
            detail="Only super administrators can access MCP server configurations",
        )


def _validate_server_id(server_id: str) -> None:
    if not _SERVER_ID_RE.match(server_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid server_id {server_id!r}. Must match "
                f"^[a-z0-9][a-z0-9_-]{{1,63}}$ (no dots, slashes, or uppercase)."
            ),
        )


def _merge_update_into_doc(
    current: dict[str, Any],
    update: MCPServerConfigUpdate,
    new_version: str,
    safe_updated_by: str,
    now_iso: str,
) -> dict[str, Any]:
    """Apply non-None fields from ``update`` onto ``current`` and refresh metadata.

    The connection sub-object is replaced atomically if provided (per
    ``MCPServerConfigUpdate`` docstring).
    """
    merged = dict(current)
    dumped = update.model_dump(exclude_unset=True, exclude_none=False)

    # Fields that set the server config itself.
    settable = {
        "description",
        "integration_type",
        "hosting",
        "specialist_categories",
        "tool_count",
        "estimated_tokens",
        "keywords",
        "kind",
        "enabled",
    }
    for key in settable:
        if key in dumped and dumped[key] is not None:
            merged[key] = dumped[key]

    # auth_type: ``None`` from the request is indistinguishable from "not set"
    # in Pydantic today (Sprint 6 limitation). Only overwrite when the caller
    # actually provided a non-None auth_type.
    if dumped.get("auth_type") is not None:
        merged["auth_type"] = dumped["auth_type"]

    if update.connection is not None:
        merged["connection"] = update.connection.model_dump()

    metadata = dict(merged.get("metadata") or {})
    metadata["version"] = new_version
    metadata["updated_at"] = now_iso
    metadata["updated_by"] = safe_updated_by
    if update.variant_name is not None:
        metadata["variant_name"] = update.variant_name
    if update.experiment_id is not None:
        metadata["experiment_id"] = update.experiment_id
    metadata["notes"] = update.notes
    merged["metadata"] = metadata

    return merged


def _diff_mcp_fields(
    pre: dict[str, Any],
    post: dict[str, Any],
    update: MCPServerConfigUpdate,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Compare pre and post for every field the caller actually set."""
    fields_changed: list[str] = []
    changes: dict[str, dict[str, Any]] = {}

    dumped = update.model_dump(exclude_unset=True)
    trackable = {
        "description",
        "integration_type",
        "hosting",
        "specialist_categories",
        "tool_count",
        "estimated_tokens",
        "keywords",
        "auth_type",
        "kind",
        "enabled",
        "connection",
    }

    for key in trackable:
        if key not in dumped:
            continue
        before = pre.get(key)
        after = post.get(key)
        if before != after:
            fields_changed.append(key)
            changes[key] = {"before": before, "after": after}

    return fields_changed, changes


def _resolve_version(current_version_str: str | None, requested: str | None) -> str:
    """Derive the new semver version. Block downgrades."""
    if requested:
        new_version = validate_semver(requested)
        if current_version_str:
            try:
                current_parsed = parse_semver(validate_semver(current_version_str))
                new_parsed = parse_semver(new_version)
                if new_parsed < current_parsed:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Version downgrade not allowed: {new_version} < "
                            f"{validate_semver(current_version_str)}."
                        ),
                    )
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot compare versions: current stored version "
                        f"{current_version_str!r} is not valid semver. {e}"
                    ),
                ) from e
        return new_version

    if not current_version_str:
        raise HTTPException(
            status_code=400,
            detail="No version found in metadata. Set one manually (e.g., v1.0.0).",
        )
    try:
        return increment_version(current_version_str)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot auto-increment version: {e}",
        ) from e


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[str])
async def list_mcp_server_configs(
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> list[str]:
    _require_admin(user, "list")

    try:
        docs = db.collection(MCP_COLLECTION).stream()
        return sorted(doc.id for doc in docs)
    except Exception as e:
        logger.error(f"Failed to list MCP server configs: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to list MCP server configurations"
        ) from e


@router.get("/{server_id}", response_model=None)
async def get_mcp_server_config(
    server_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> dict[str, Any]:
    """Return the raw Firestore doc for one MCP server config.

    ``response_model=None`` is deliberate — see module docstring. Wrapping
    the doc in ``MCPServerFirestoreConfig`` would resolve ``${VAR}``
    secrets via the connection validators and leak them in the response
    body. The raw dict preserves literal secret references.
    """
    _require_admin(user, "get")
    _validate_server_id(server_id)

    try:
        doc = db.collection(MCP_COLLECTION).document(server_id).get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="MCP server config not found")
        return doc.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server config {server_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve MCP server configuration"
        ) from e


@router.put("/{server_id}", response_model=None)
async def update_mcp_server_config(
    server_id: str,
    update: MCPServerConfigUpdate,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> dict[str, Any]:
    """Write an update to a Firestore MCP server config.

    **Preserves literal ``${VAR}`` patterns end-to-end**: the incoming
    ``merged`` dict is what lands in Firestore, and the response echoes
    that same dict (plus operator warnings). The validator-bearing
    ``MCPServerFirestoreConfig`` is constructed once as a throwaway to
    enforce cross-field invariants (hosting↔connection-type, SSE URL
    non-empty, auth_type allowlist) — we discard its resolved-secret
    output immediately.
    """
    _require_admin(user, "update")
    _validate_server_id(server_id)

    try:
        doc_ref = db.collection(MCP_COLLECTION).document(server_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="MCP server config not found")

        current = doc.to_dict()
        current_metadata = current.get("metadata", {}) or {}
        current_version_str = current_metadata.get("version")

        new_version = _resolve_version(current_version_str, update.version)
        safe_updated_by = sanitize_updated_by(update.updated_by)
        now_iso = datetime.now(timezone.utc).isoformat()

        merged = _merge_update_into_doc(
            current=current,
            update=update,
            new_version=new_version,
            safe_updated_by=safe_updated_by,
            now_iso=now_iso,
        )

        # Invariant check only. The validated instance is discarded — its
        # `connection` sub-object has resolved secrets that must NEVER be
        # written back to Firestore.
        try:
            MCPServerFirestoreConfig(**merged)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors()) from e

        # Write the raw merged dict (literal `${VAR}` strings preserved).
        doc_ref.set(merged)

        fields_changed, changes = _diff_mcp_fields(current, merged, update)
        await log_config_action(
            db=db,
            doc_type="mcp_server_config",
            doc_id=server_id,
            action="updated",
            user=user,
            version_before=current_version_str,
            version_after=new_version,
            fields_changed=fields_changed,
            changes=changes,
        )

        warnings = await _maybe_reload(fields_changed)

        logger.info(
            f"User {user.email} updated MCP server config {server_id} "
            f"to version {new_version} (fields_changed={fields_changed})"
        )

        return {**merged, "warnings": warnings}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP server config {server_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to update MCP server configuration"
        ) from e


async def _maybe_reload(fields_changed: list[str]) -> list[str]:
    """Trigger MCPServerManager.reload() if a runtime-affecting field changed.

    Reload failures are surfaced as warnings, not exceptions — the config
    write has already succeeded and subsequent requests will pick up the new
    config on their next ``load_server`` call anyway (lazy-load).
    """
    if not any(field in _RELOAD_TRIGGER_FIELDS for field in fields_changed):
        return []

    # Lazy: ``app.adk.*`` is not packaged in the API image, so importing
    # here keeps module load clean and defers any failure to handler
    # invocation (where it surfaces as a warning, not a 5xx on startup).
    from app.adk.mcp_config.manager import get_mcp_manager

    try:
        manager = get_mcp_manager()
        result = await manager.reload()
        unloaded = result.get("unloaded", [])
        if unloaded:
            return [
                f"MCPServerManager reloaded; unloaded runtime servers: "
                f"{', '.join(unloaded)}"
            ]
        return ["MCPServerManager reload succeeded (no servers needed reconnect)."]
    except Exception as e:
        logger.error(f"MCPServerManager.reload() failed: {e!s}")
        return [
            f"MCPServerManager reload failed (config write succeeded): {e!s}. "
            f"Next agent invocation will load the fresh config on demand."
        ]


@router.get("/{server_id}/history", response_model=list[ConfigAuditEntry])
async def get_mcp_server_config_history(
    server_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
    limit: int = Query(20, ge=1, le=100, description="Max entries to return"),
) -> list[ConfigAuditEntry]:
    _require_admin(user, "history")
    _validate_server_id(server_id)

    # FastAPI enforces `le=100` on the query-param, but that guard only
    # runs at the HTTP boundary; in-process callers could pass a wider
    # value, so keep the explicit check here too.
    if limit > 100:
        raise HTTPException(status_code=400, detail="limit must be <= 100")

    try:
        history_ref = (
            db.collection(MCP_COLLECTION)
            .document(server_id)
            .collection("history")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [ConfigAuditEntry(**doc.to_dict()) for doc in history_ref.stream()]
    except Exception as e:
        logger.error(f"Failed to fetch MCP server history for {server_id}: {e!s}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve MCP server config history"
        ) from e


@router.post("/reload")
async def reload_mcp_server_configs(
    user: UserContext = Depends(get_current_user_context),
) -> dict[str, Any]:
    """Force a manager-level reload independent of any config PUT.

    Used by operators to pick up out-of-band Firestore edits or to clear a
    stuck server. Returns the counts of unloaded vs. kept servers.
    """
    _require_admin(user, "reload")

    # Lazy import: see ``_maybe_reload`` for rationale.
    from app.adk.mcp_config.manager import get_mcp_manager

    try:
        manager = get_mcp_manager()
        result = await manager.reload()
        return {"status": "ok", **result}
    except Exception as e:
        logger.error(f"Manual MCP reload failed: {e!s}")
        raise HTTPException(status_code=500, detail=f"MCP reload failed: {e!s}") from e
