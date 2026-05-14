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
import os
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


# Relative path of the catalogue under the repo root. Kept as a constant so
# the resolver below can probe it without a hardcoded ``parents[N]`` depth
# (review item #6: a parents[4] hardcode silently empties the inventory if
# anyone restructures api/src/kene_api/).
_CATALOGUE_RELATIVE = Path("app/adk/tools/registry/config/tools.yaml")
_TOOLS_YAML_ENV_VAR = "KENE_TOOLS_YAML_PATH"


def _resolve_tools_yaml_path() -> Path:
    """Locate the catalogue YAML by env override, then by walking up.

    Resolution order:
      1. ``KENE_TOOLS_YAML_PATH`` env var, when set to a non-empty path.
      2. Walk up from this file looking for the first ancestor that contains
         ``app/adk/tools/registry/config/tools.yaml``. This adapts to either
         the canonical repo layout or any future restructure where the
         catalogue's parent shifts.

    Raises ``FileNotFoundError`` when neither resolves — the inventory
    composer turns this into an empty catalogue with a logged warning so the
    endpoint stays up, but the lookup itself fails loudly so a misconfigured
    deploy is visible rather than silently empty.
    """
    override = os.environ.get(_TOOLS_YAML_ENV_VAR)
    if override:
        path = Path(override).expanduser()
        if path.exists():
            return path
        # Env var was set but points at nothing — fail loudly rather than
        # silently fall through to the walk-up.
        raise FileNotFoundError(
            f"{_TOOLS_YAML_ENV_VAR}={override!r} does not exist"
        )

    here = Path(__file__).resolve()
    for ancestor in (here, *here.parents):
        candidate = ancestor / _CATALOGUE_RELATIVE
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate {_CATALOGUE_RELATIVE} walking up from {here}. "
        f"Set {_TOOLS_YAML_ENV_VAR} to override."
    )


_TOOLS_YAML: Path | None
try:
    _TOOLS_YAML = _resolve_tools_yaml_path()
except FileNotFoundError as _exc:
    # Cache the failure rather than raising at import — the inventory composer
    # surfaces this as an empty response with a logged warning so the API
    # stays up even in odd layouts (test harnesses, partial repos). Resolution
    # is retried on each ``_load_catalogue(None)`` call so a moved file is
    # picked up without a process restart.
    logger.warning("Tool catalogue not located at import time: %s", _exc)
    _TOOLS_YAML = None


# Integration platform ID -> MCP server ID. Today every shipped integration
# maps 1:1 to one MCP server (Integrations README §2.1). When a future
# integration ships with a different mapping, add an entry here.
_INTEGRATION_TO_MCP_SERVER: dict[str, str] = {
    "google_analytics": "google_analytics_mcp",
}


def _load_catalogue(
    path: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load the raw catalogue from the YAML file.

    Returns a dict with ``tools`` and ``function_tools`` lists; either may
    be empty if the section is absent. The schema deliberately mirrors
    ``tools.yaml`` so callers can iterate by source.

    When ``path`` is ``None`` the canonical catalogue is resolved on each
    call (via :func:`_resolve_tools_yaml_path`) so a moved file or a
    runtime env-var change takes effect without an import-time restart.
    Missing-file paths still degrade to an empty catalogue + a warning so
    the endpoint stays up; mirrors the read-error tolerance the inventory
    composer applies elsewhere.

    Note: this parser is intentionally a slim alternative to
    ``app.adk.tools.registry.tool_registry.ToolRegistry.load_from_config``.
    The API keeps its runtime import graph independent of the agent runtime
    package (per AH-PRD-06 §5.2). The two parsers must agree on the YAML
    schema — keep them in sync when ``tools.yaml`` grows a new section.
    """
    if path is None:
        try:
            path = _resolve_tools_yaml_path()
        except FileNotFoundError as exc:
            logger.warning("Tool catalogue lookup failed: %s", exc)
            return {"tools": [], "function_tools": []}

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


def list_known_tool_ids(
    catalogue: dict[str, list[dict[str, Any]]] | None = None,
) -> set[str]:
    """Return every tool_id present in the catalogue.

    Used by the agent-config router to reject ``tool_ids`` containing entries
    that don't reference a real tool. The catalogue is the same one the
    inventory endpoint reads, so what the picker shows and what the API
    accepts stay in sync.

    Format mirrors ``AccountToolEntry.tool_id``:
      * ``<mcp_server>.<tool_name>`` for tools in ``tools:``
      * ``function.<tool_name>`` for tools in ``function_tools:``
    """
    raw = catalogue if catalogue is not None else _load_catalogue()
    known: set[str] = set()
    for tool in raw["tools"]:
        server = tool.get("mcp_server")
        name = tool.get("name")
        if server and name:
            known.add(f"{server}.{name}")
    for tool in raw["function_tools"]:
        name = tool.get("name")
        if name:
            known.add(f"function.{name}")
    return known


__all__ = ["compose_inventory", "list_known_tool_ids"]
