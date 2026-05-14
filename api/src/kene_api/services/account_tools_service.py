"""Account tool-inventory composition (AH-PRD-06 §5.2).

Composes the set of tools available to an account by reading:

1. The static tool catalogue (``app/adk/tools/registry/config/tools.yaml``)
   — emits every ``function_tools`` entry tagged ``default_global: true``
   unconditionally; emits MCP-attached tools only when the account has a
   matching connected integration.
2. The Firestore ``integration_credentials`` collection (today's storage —
   one doc per ``{account_id}_{integration_type}``) — presence of a doc
   signals "connected" for the purpose of gating MCP tools.

The integration ↔ MCP server mapping is hardcoded here for now (only
``google_analytics`` → ``google_analytics_mcp`` exists in production today).
Promotion to a Firestore-backed ``PlatformDefinition`` is an Integrations
follow-up (AH-PRD-06 §9).

The catalogue YAML is parsed directly here rather than imported from
``app.adk.tools.registry`` to keep the API's runtime import graph
independent of the agent runtime package.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import yaml
from google.cloud import firestore  # type: ignore[import-untyped]

from ..models.tool_models import AccountToolEntry, AccountToolsResponse

logger = logging.getLogger(__name__)

# Mirrors ``IntegrationCredentialsService.collection_name`` in
# ``services/encryption_service.py``. Hardcoded here so the inventory composer
# stays sync and doesn't have to instantiate the credentials service just to
# read the collection name. If the credentials service moves to a different
# collection (e.g. when IN-PRD-01's ``platform_connections/*`` lands) update
# both call sites.
_INTEGRATION_CREDENTIALS_COLLECTION: str = "integration_credentials"


# Walk up from this file to the repo root: api/src/kene_api/services -> repo.
# Hardcoded depth keeps the lookup explicit and cheap; tests fail loudly if the
# catalogue moves.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_TOOLS_YAML = _REPO_ROOT / "app" / "adk" / "tools" / "registry" / "config" / "tools.yaml"


# Integration platform ID -> MCP server ID. Today every shipped integration
# maps 1:1 to one MCP server (Integrations README §2.1). When a future
# integration ships with a different mapping, add an entry here.
_INTEGRATION_TO_MCP_SERVER: dict[str, str] = {
    "google_analytics": "google_analytics_mcp",
}


def _load_catalogue(path: Path = _TOOLS_YAML) -> dict[str, list[dict[str, Any]]]:
    """Load the raw catalogue from the YAML file.

    Returns a dict with ``tools`` and ``function_tools`` lists; either may
    be empty if the section is absent. The schema deliberately mirrors
    ``tools.yaml`` so callers can iterate by source.
    """
    if not path.exists():
        logger.warning("Tool catalogue not found at %s; returning empty inventory", path)
        return {"tools": [], "function_tools": []}
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return {
        "tools": list(raw.get("tools") or []),
        "function_tools": list(raw.get("function_tools") or []),
    }


def _mcp_server_for_integration(integration_type: str) -> str | None:
    return _INTEGRATION_TO_MCP_SERVER.get(integration_type)


def _connected_integrations_for_account(
    db: firestore.Client, account_id: str
) -> set[str]:
    """Return the set of integration platform IDs connected for the account.

    Lookup is by doc-ID convention (``{account_id}_{integration_type}``) in
    the ``integration_credentials`` collection. The presence of a document is
    treated as "connected" — mirrors today's
    ``IntegrationCredentialsService.check_credentials_exist`` semantics.
    """
    connected: set[str] = set()
    for integration_type in _INTEGRATION_TO_MCP_SERVER:
        doc_id = f"{account_id}_{integration_type}"
        try:
            doc = (
                db.collection(_INTEGRATION_CREDENTIALS_COLLECTION)
                .document(doc_id)
                .get()
            )
        except Exception as exc:
            logger.warning(
                "Failed to read integration_credentials/%s: %s", doc_id, exc
            )
            continue
        if doc.exists:
            connected.add(integration_type)
    return connected


def compose_inventory(
    *,
    account_id: str,
    db: firestore.Client,
    catalogue: dict[str, list[dict[str, Any]]] | None = None,
) -> AccountToolsResponse:
    """Compose the tool inventory for an account.

    Args:
        account_id: KEN-E account ID (used to look up connected integrations).
        db: Firestore client.
        catalogue: Optional pre-loaded catalogue dict (test seam); when ``None``
            the canonical ``tools.yaml`` is read from disk.

    Returns:
        ``AccountToolsResponse`` with one entry per available tool.
    """
    raw = catalogue if catalogue is not None else _load_catalogue()
    connected = _connected_integrations_for_account(db, account_id)

    entries: list[AccountToolEntry] = []

    # Global-default function tools (always available).
    for tool in raw["function_tools"]:
        if not bool(tool.get("default_global", False)):
            continue
        name = cast(str, tool["name"])
        entries.append(
            AccountToolEntry(
                tool_id=f"function.{name}",
                name=name,
                description=cast(str, tool.get("description", "")),
                category=cast(str, tool.get("category", "general")),
                source="global_default",
                mcp_server=None,
                integration_platform=None,
            )
        )

    # MCP-attached tools, gated on a connected integration. Iterate platforms
    # rather than tools so we can attribute each surfaced tool back to the
    # integration that unlocked it.
    for platform_id, mcp_server in _INTEGRATION_TO_MCP_SERVER.items():
        if platform_id not in connected:
            continue
        for tool in raw["tools"]:
            if tool.get("mcp_server") != mcp_server:
                continue
            name = cast(str, tool["name"])
            entries.append(
                AccountToolEntry(
                    tool_id=f"{mcp_server}.{name}",
                    name=name,
                    description=cast(str, tool.get("description", "")),
                    category=cast(str, tool.get("category", "general")),
                    source="integration",
                    mcp_server=mcp_server,
                    integration_platform=platform_id,
                )
            )

    return AccountToolsResponse(tools=entries)


__all__ = ["compose_inventory"]
