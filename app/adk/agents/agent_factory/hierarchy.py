"""Hierarchy builder for the KEN-E agent factory (AH-PRD-02 Phase 2 / AH-17).

`build_hierarchy()` is the deploy-time orchestration entry point that composes
every specialist and the root agent from Firestore configuration:

  config_loader   (AH-10) — loads + merges MergedAgentConfig documents
  mcp             (AH-11) — builds McpToolset instances from mcp_server_configs
  header_provider (AH-12) — OAuth header-provider closures per auth_type
  roster          (AH-13) — validates the ≤30-tool cap
  dispatch        (AH-14) — generates dispatch_to_<name>() + Available Specialists block
  builder         (AH-15) — constructs LlmAgent with standard ADK callbacks

Deploy-time only: call once in ``deploy_ken_e.py``.  Not intended for
per-request use — the function performs N+1 Firestore reads.
"""

from __future__ import annotations

import os
import re
from typing import Any

from google.adk.agents import LlmAgent

from app.adk.agents.agent_factory.builder import build_agent

# _load_and_merge is imported directly (not load_agent_config) so we can inject
# a pre-built db= client; load_agent_config() creates its own client internally
# and does not accept a db parameter.
from app.adk.agents.agent_factory.config_loader import (
    ConfigNotFoundError,
    ConfigValidationError,
    FirestoreConnectionError,
    MergedAgentConfig,
    _load_and_merge,
)
from app.adk.agents.agent_factory.dispatch import (
    assemble_available_specialists_block,
    generate_dispatch_functions,
)
from app.adk.agents.agent_factory.mcp import MCP_COLLECTION, build_toolset_for_doc
from app.adk.agents.agent_factory.roster import resolve_specialist_roster
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

ROOT_CONFIG_ID: str = "ken_e_chatbot"

# Firestore document IDs must not contain "/" and must be well-formed strings.
# This allowlist prevents path-manipulation bugs if account_id is ever
# sourced from caller input in a multi-tenant deployment.
_VALID_ACCOUNT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(project_id: str | None) -> str:
    """Resolve the GCP project ID from the argument or environment.

    Resolution order:
    1. Explicit ``project_id`` argument.
    2. ``GOOGLE_CLOUD_PROJECT_ID`` environment variable.
    3. Hard-coded default ``"ken-e-dev"``.

    Args:
        project_id: Caller-supplied project ID, or ``None`` to use env/default.

    Returns:
        Non-empty project ID string.
    """
    return project_id or os.getenv("GOOGLE_CLOUD_PROJECT_ID") or "ken-e-dev"


def _build_firestore_client(project_id: str) -> Any:
    """Create and return a Firestore client for the given project.

    Lazy-imports ``google.auth`` and ``google.cloud.firestore`` so the module
    remains importable in environments where neither package is installed
    (mirrors the pattern in ``mcp.py``).

    Args:
        project_id: GCP project ID.

    Returns:
        ``google.cloud.firestore.Client`` instance.

    Raises:
        Any exception raised by ``google.auth.default()`` or
        ``firestore.Client()`` — callers should wrap in
        ``FirestoreConnectionError``.
    """
    from google.auth import default as google_auth_default
    from google.cloud import firestore

    credentials, _ = google_auth_default()
    return firestore.Client(project=project_id, credentials=credentials)


def _list_config_ids(db: Any, account_id: str | None) -> list[str]:
    """Return the sorted union of global and (optionally) account-scoped config IDs.

    Args:
        db: Firestore client (real or test double).
        account_id: When provided, the ``accounts/{account_id}/agent_configs``
            sub-collection is also scanned and its IDs merged with the global set.

    Returns:
        Sorted list of unique document IDs from ``agent_configs`` (and the
        optional per-account overlay collection).
    """
    global_ids: set[str] = {
        ref.id for ref in db.collection("agent_configs").list_documents()
    }

    if account_id is None:
        return sorted(global_ids)

    account_ids: set[str] = {
        ref.id
        for ref in db.collection("accounts")
        .document(account_id)
        .collection("agent_configs")
        .list_documents()
    }
    return sorted(global_ids | account_ids)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_hierarchy(
    account_id: str | None = None,
    *,
    project_id: str | None = None,
    db: Any | None = None,
) -> LlmAgent:
    """Build the full KEN-E agent hierarchy from Firestore configuration.

    Reads every document from ``agent_configs`` (plus optional account overlays),
    constructs one ``LlmAgent`` per specialist, assembles an Available Specialists
    block, and returns the root agent with dispatch functions wired as tools.

    This is a **deploy-time-only** entry point — it performs N+1 Firestore reads
    and should be called once during ``deploy_ken_e.py``, not per-request.

    Args:
        account_id: When provided, per-account overlay documents are merged on
            top of global base configs (same semantics as
            ``_load_and_merge``).  Must match ``[a-zA-Z0-9_-]{1,128}``; a
            ``ValueError`` is raised if the format is invalid.
        project_id: GCP project ID used when creating a Firestore client.
            Resolved via argument → ``GOOGLE_CLOUD_PROJECT_ID`` env var →
            ``"ken-e-dev"``.
        db: Pre-built Firestore client (for testing / dependency injection).
            When ``None`` a real client is created from ``project_id`` / env.

    Returns:
        Root ``LlmAgent`` (name ``"ken_e"``) with dispatch functions as tools
        and the Available Specialists block appended to its instruction.

    Raises:
        ValueError: When ``account_id`` does not match the required format, or
            when an MCP server document carries an unrecognised ``auth_type``
            (propagated from ``build_toolset_for_doc`` / ``make_header_provider``).
            ``MCPSchemaError`` from ``build_toolset_for_doc`` (e.g. missing
            ``connection`` field) also propagates — this is intentional
            fail-fast behaviour at deploy time so misconfigured servers are
            caught before going live.
        FirestoreConnectionError: When ``db is None`` and a Firestore client
            cannot be created, or when a Firestore read fails unexpectedly.
        ConfigNotFoundError: When the ``ROOT_CONFIG_ID`` document is absent
            from both the global and account collections.
    """
    # Step 0 — validate account_id format before touching Firestore.
    if account_id is not None and not _VALID_ACCOUNT_ID_RE.match(account_id):
        raise ValueError(
            f"account_id {account_id!r} contains invalid characters. "
            "Must match [a-zA-Z0-9_-]{1,128}."
        )

    # Step 1 — resolve Firestore client.
    if db is None:
        resolved_project_id = _resolve_project_id(project_id)
        try:
            db = _build_firestore_client(resolved_project_id)
        except Exception as exc:
            raise FirestoreConnectionError(
                f"Failed to connect to Firestore for project {resolved_project_id!r}: {exc}"
            ) from exc

    # Step 2 — discover all config IDs (global + optional account).
    config_ids = _list_config_ids(db, account_id)
    logger.info("Discovered %d agent config IDs", len(config_ids))
    logger.debug("Config IDs: %s", config_ids)

    # Step 3 — load and merge every config document.
    configs: dict[str, MergedAgentConfig] = {}
    for config_id in config_ids:
        try:
            configs[config_id] = _load_and_merge(db, config_id, account_id)
            logger.debug("Loaded agent config %r", config_id)
        except (ConfigNotFoundError, ConfigValidationError) as exc:
            # An account-scoped overlay ID may reference a document that no
            # longer exists globally, or a document may fail Pydantic validation.
            # Skip the bad document rather than aborting the entire hierarchy build.
            logger.warning(
                "Config ID %r could not be loaded (%s); skipping.",
                config_id,
                type(exc).__name__,
            )

    # Step 4 — pop root config; raise if absent.
    root_config = configs.pop(ROOT_CONFIG_ID, None)
    if root_config is None:
        raise ConfigNotFoundError(
            f"Root agent config {ROOT_CONFIG_ID!r} was not found in agent_configs. "
            "Deploy cannot proceed without the root agent definition."
        )

    # Step 4½ — filter out global specialists that are not automatically available.
    # A default-status config with automatically_available=False is excluded from
    # the hierarchy. Customized and custom_agent configs always pass — the account
    # opted in explicitly. The root config was already popped above.
    assert ROOT_CONFIG_ID not in configs, (
        f"Root config {ROOT_CONFIG_ID!r} must be popped before the filter step; "
        "ordering invariant violated."
    )
    excluded = [
        cid
        for cid, cfg in configs.items()
        if cfg.customization_status == "default" and not cfg.automatically_available
    ]
    for cid in excluded:
        del configs[cid]
    if excluded:
        logger.info(
            "Filtered %d specialist(s) with automatically_available=False: %s",
            len(excluded),
            excluded,
        )

    # Step 5 — build specialists in deterministic alphabetical order.
    specialists: dict[str, LlmAgent] = {}

    for spec_name in sorted(configs):
        spec_config = configs[spec_name]

        # Step 6a — build MCP toolsets for this specialist's declared servers.
        mcp_toolsets: dict[str, Any] = {}
        for server_id in spec_config.mcp_servers:
            server_snap = db.collection(MCP_COLLECTION).document(server_id).get()
            if not server_snap.exists:
                logger.warning(
                    "MCP server %r referenced by specialist %r not found in "
                    "%r; skipping.",
                    server_id,
                    spec_name,
                    MCP_COLLECTION,
                )
                continue

            doc_data: dict[str, Any] = server_snap.to_dict() or {}

            if doc_data.get("enabled") is not True:
                logger.debug(
                    "MCP server %r is disabled; skipping for specialist %r.",
                    server_id,
                    spec_name,
                )
                continue

            # ValueError (unknown auth_type) and MCPSchemaError (malformed doc)
            # both propagate — intentional fail-fast at deploy time.
            toolset = build_toolset_for_doc(server_id, doc_data)
            mcp_toolsets[server_id] = toolset
            logger.debug(
                "Built McpToolset %r for specialist %r.", server_id, spec_name
            )

        # Step 6b — warn when config declared servers but none were loaded.
        if not mcp_toolsets and spec_config.mcp_servers:
            logger.warning(
                "Specialist %r declares MCP servers %s but zero toolsets were "
                "built (all missing or disabled).",
                spec_name,
                spec_config.mcp_servers,
            )

        # Step 6c — validate cap and assemble ordered tools list.
        tools = resolve_specialist_roster(
            spec_name,
            mcp_toolsets=mcp_toolsets,
            function_tools=[],
            mcp_server_ids=list(mcp_toolsets.keys()),
        )

        # Step 6d — construct the specialist LlmAgent.
        specialist = build_agent(spec_config, name=spec_name, tools=tools)
        specialists[spec_name] = specialist
        logger.info("Built specialist agent %r.", spec_name)

    # Step 7 — generate dispatch callables (insertion order is already alphabetical
    # from Step 5, so dispatch tool order is deterministic).
    dispatchers = generate_dispatch_functions(specialists)

    # Step 8 — assemble the root instruction with the Available Specialists block.
    specialists_block = assemble_available_specialists_block(specialists)
    combined_instruction = root_config.instruction.rstrip() + "\n\n" + specialists_block

    # Step 9 — create a modified root config carrying the assembled instruction.
    root_config_assembled = root_config.model_copy(
        update={"instruction": combined_instruction}
    )

    # Step 10 — build the root agent with dispatcher functions as tools.
    root_agent = build_agent(
        root_config_assembled,
        name="ken_e",
        tools=list(dispatchers.values()),
    )
    logger.info(
        "Built root agent %r with %d specialist(s).", "ken_e", len(specialists)
    )

    # Step 11 — return.
    return root_agent
