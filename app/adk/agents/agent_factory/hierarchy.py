"""Hierarchy builder for the KEN-E agent factory (AH-PRD-09 Phase 2 + AH-75).

`build_hierarchy()` is the deploy-time entry point that builds the root agent
from Firestore configuration. Specialist agents are resolved per-turn by
``specialist_runtime`` rather than baked into the deploy artifact, reducing
deploy-time Firestore reads from N+1 to 1.

AH-75 (Approach 1) replaced the ``delegate_to_specialist`` function tool with
ADK's native ``transfer_to_agent`` + dynamically-managed ``sub_agents``. The
root carries no specialist-dispatch tool; a ``before_agent_callback`` wires
each turn's visible specialists into ``root.sub_agents`` before the LLM is
invoked, so ``transfer_to_agent(agent_name=<doc_id>)`` resolves natively.

  config_loader   (AH-10) — loads + merges the root MergedAgentConfig document
  builder         (AH-15) — constructs LlmAgent with standard ADK callbacks
  specialist_runtime (AH-59) — available_specialists_provider per-turn provider
  sub_agent_attacher (AH-75) — runtime sub_agents sync via before_agent_callback

Deploy-time only: call once in ``deploy_ken_e.py``.
"""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import LlmAgent

import app.adk.tools.todo_list_tools  # noqa: F401  # default_global registration
from app.adk.agents.agent_factory.builder import build_agent
from app.adk.agents.agent_factory.config_loader import (
    FirestoreConnectionError,
    _load_and_merge,
)
from shared.account_id_utils import validate_account_id
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

ROOT_CONFIG_ID: str = "ken_e_chatbot"


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_hierarchy(
    account_id: str | None = None,
    *,
    project_id: str | None = None,
    db: Any | None = None,
) -> LlmAgent:
    """Build the KEN-E root agent from Firestore configuration.

    Per AH-PRD-09 + AH-75, the root agent carries **no** specialist-dispatch
    tool. Specialist agents are resolved per-turn by ``specialist_runtime`` and
    attached to ``root.sub_agents`` by ``attach_specialists_before_agent_callback``
    so ADK's built-in ``transfer_to_agent`` finds them via ``root.find_agent``.
    This preserves the AH-PRD-09 wins (Firestore-resolved-per-turn, ≤60s
    admin-edit propagation, no redeploy) while routing specialist events
    through ADK's native transfer mechanism so they propagate to the outer
    Runner's event stream (and to Chat + Billing consumers).

    Args:
        account_id: When provided, per-account overlay documents are merged on
            top of the global base config (same semantics as
            ``_load_and_merge``).  Must match ``[a-zA-Z0-9_-]{1,128}``; a
            ``ValueError`` is raised if the format is invalid.
        project_id: GCP project ID used when creating a Firestore client.
            Resolved via argument → ``GOOGLE_CLOUD_PROJECT_ID`` env var →
            ``"ken-e-dev"``.
        db: Pre-built Firestore client (for testing / dependency injection).
            When ``None`` a real client is created from ``project_id`` / env.

    Returns:
        Root ``LlmAgent`` (name ``"ken_e"``) with no specialist-dispatch tool;
        the per-turn Available Specialists block is wired via
        ``instruction_suffix_provider`` and the sub_agents list is populated
        per turn by ``attach_specialists_before_agent_callback``.

    Raises:
        ValueError: When ``account_id`` does not match the required format.
        FirestoreConnectionError: When ``db is None`` and a Firestore client
            cannot be created, or when a Firestore read fails unexpectedly.
        ConfigNotFoundError: When the ``ROOT_CONFIG_ID`` document is absent
            from both the global and account collections.
    """
    # Step 0 — validate account_id format before touching Firestore.
    if account_id is not None:
        account_id = validate_account_id(account_id)

    # Step 1 — resolve Firestore client.
    if db is None:
        resolved_project_id = _resolve_project_id(project_id)
        try:
            db = _build_firestore_client(resolved_project_id)
        except Exception as exc:
            raise FirestoreConnectionError(
                f"Failed to connect to Firestore for project {resolved_project_id!r}: {exc}"
            ) from exc

    # Step 2 — load root config only. Specialists are resolved per-turn by
    # specialist_runtime; no N+1 read at deploy time.
    root_config = _load_and_merge(db, ROOT_CONFIG_ID, account_id)
    logger.info("Loaded root agent config %r.", ROOT_CONFIG_ID)

    # Step 3 — build the root agent.
    #
    # * instruction_suffix_provider renders the Available Specialists block
    #   per-turn from the TTL-cached Firestore data so admin edits propagate
    #   within 60 s without a redeploy.
    # * additional_before_agent_callbacks wires the same per-turn data into
    #   root.sub_agents via attach_specialists_before_agent_callback. The
    #   "Available Specialists" block and the transfer-target set stay in
    #   sync because both walk the same list_account_agent_configs +
    #   resolve_config(visible_in_frontend) pipeline.
    #
    # Lazy import: avoids circular import at module-load time since
    # agent_factory/__init__.py imports both hierarchy and specialist_runtime,
    # and specialist_runtime imports config_cache which imports agent_factory.
    from app.adk.agents.agent_factory.specialist_runtime import (
        available_specialists_provider,
    )
    from app.adk.agents.agent_factory.sub_agent_attacher import (
        attach_specialists_before_agent_callback,
    )

    root_agent = build_agent(
        root_config,
        name="ken_e",
        account_id=account_id,
        tools=[],
        config_doc_id=ROOT_CONFIG_ID,
        instruction_suffix_provider=available_specialists_provider,
        additional_before_agent_callbacks=[
            attach_specialists_before_agent_callback,
        ],
    )
    logger.info("Built root agent %r.", "ken_e")

    return root_agent
