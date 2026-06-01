#!/usr/bin/env python3
"""
Migrate Google Analytics Specialist configuration to Firestore.

This script writes two Firestore documents that together give the AH-PRD-09
per-turn runtime resolver everything it needs to construct the GA Specialist
on the next chat turn (no redeploy required; the ``config_cache`` TTL is
≤60 s):

1. **``agent_configs/google_analytics_specialist``** — the new specialist doc
   (doc_id = ``google_analytics_specialist``, the routing key used by
   ``transfer_to_agent``).

2. **``mcp_server_configs/google_analytics_mcp`` patch** — idempotently
   ensures ``kind="cloud_run"`` (required by ``McpToolsetPool``),
   ``specialist_categories=["analytics"]``, ``auth_type="ga_oauth"``, and
   ``enabled=True`` are present on the existing MCP server doc.

.. warning::

   **Re-running this script overwrites** the fields it manages on both
   Firestore documents (``set(..., merge=True)`` semantics — only keys present
   in the seed dict are written; everything else on the existing doc is
   preserved). **Treat this file as the source of truth for the seeded
   fields**: if you change ``instruction`` or ``default_acceptance_criteria``
   via the Admin UI, reconcile back to this file before re-running, or you
   will lose the admin edit on the next seed.

The ``kind`` patch is idempotent on ``"cloud_run"`` and ``"zapier"``: those
values are left unchanged. Missing, ``None``, empty, or unrecognised ``kind``
values are set to ``"cloud_run"`` — mirroring the behaviour of
``api/scripts/migrate_mcp_servers_add_kind.py``.

Usage:
    python migrate_ga_specialist_to_firestore.py [--project-id PROJECT_ID] [--dry-run]

Examples:
    # Development environment
    python migrate_ga_specialist_to_firestore.py --project-id ken-e-dev

    # Staging environment
    python migrate_ga_specialist_to_firestore.py --project-id ken-e-staging

    # Production environment
    python migrate_ga_specialist_to_firestore.py --project-id ken-e-production

    # Dry run (no actual changes)
    python migrate_ga_specialist_to_firestore.py --project-id ken-e-dev --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Make ``app`` importable when this file is executed as a script.
_repo_root = Path(__file__).resolve().parent
while _repo_root != _repo_root.parent and not (_repo_root / ".git").exists():
    _repo_root = _repo_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.adk.agents.scripts._seed_helpers import (  # noqa: E402
    AUDIT_FIELDS_USER_FACING_RESEARCHER,
    upsert_agent_config,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent config document
# ---------------------------------------------------------------------------

GA_SPECIALIST_INSTRUCTION = """You are Aria, a Google Analytics specialist. \
You help users analyse website and app data from their GA4 properties.

**Authentication:**
OAuth credentials are handled automatically via headers. You do NOT need to
pass tenant_id or credentials parameters - they are injected for you.

**Available tools (discovered dynamically from the GA MCP server):**
- get_account_summaries_mt - list all GA accounts and properties
- run_report_mt - run analytics reports with date ranges, metrics,
  dimensions, and filters
- run_realtime_report_mt - get live data from the last 30 minutes
- get_property_details_mt - get GA4 property configuration details

**Numerical analysis - use Gemini code execution for everything:**
Use Gemini code execution for ALL numerical analysis: percentages, trend
calculations, averages, sorting, and comparisons. Never perform arithmetic
in-context. Show the executed formula in your reply so the reviewer can
verify the calculation.

Example:
  - Retrieve raw metric values via the GA MCP tools.
  - Write and execute a short Python snippet to compute the result.
  - Present the output table together with the code/formula you ran.

This applies to: percentage changes, growth rates, session averages,
bounce-rate comparisons, ranking by metric, and any other calculation.

**Tool usage guide:**

1. get_account_summaries_mt - no required parameters; use when the user
   asks to see their GA accounts or properties.

2. get_property_details_mt - required: property_id; use when the
   user asks about a specific property's settings.

3. run_report_mt - required: property_id, date_ranges; optional:
   metrics, dimensions, filters, limit.
   Common metrics: activeUsers, sessions, screenPageViews, bounceRate.
   Common dimensions: country, city, deviceCategory, pagePath.
   Date format examples: "7daysAgo", "yesterday", "today".

4. run_realtime_report_mt - required: property_id; optional:
   metrics, dimensions; shows data from the last 30 minutes.

**Best practices:**
- If the user's property ID is available in context, use it directly;
  otherwise call get_account_summaries_mt first.
- Format data clearly in tables.
- Provide insights alongside raw data.
- Round all displayed numbers to at most 2 decimal places.
- Always state the absolute date range you queried (e.g. "1 Jan 2025 -
  31 Jan 2025") so the user and the reviewer can verify scope.
- Always report the GA property identifier that was queried.

**Important:**
- NEVER ask for credentials or tokens - they are handled automatically.
- If a property_id is provided in context, use it without asking again.
"""

# Three format-bound, verifiable-from-draft acceptance criteria.
# Per the planning decision (D4): ASCII-only; sanitise_criteria() is a no-op;
# each criterion is independently verifiable from the draft text alone.
GA_SPECIALIST_ACCEPTANCE_CRITERIA = (
    "Response includes the queried GA property identifier and the absolute date range;"
    " numerical aggregates (totals, averages, percentage changes) are produced via"
    " code execution and the formula is shown to the user;"
    " per-metric values are reported with their metric name and rounded to"
    " at most 2 decimal places."
)

GA_SPECIALIST_CONFIG: dict[str, Any] = {
    # AH-84: human-readable identity surfaced in the Available Specialists block.
    "name": "Aria",
    "title": "Analytics Specialist",

    "model": "gemini-2.0-flash",
    "instruction": GA_SPECIALIST_INSTRUCTION,
    "temperature": 0.2,
    "description": (
        "Google Analytics 4 specialist. Use for any query about website or app"
        " traffic: sessions, users, pageviews, bounce rate, engagement, traffic"
        " sources, conversion events, real-time data, or custom GA4 reports."
        " Performs accurate numerical analysis (percentages, trends, averages)"
        " using Gemini code execution."
    ),

    # AH-PRD-06: tool_ids=None → all tools from google_analytics_mcp.
    "tool_ids": None,

    # AH-75 / AH-PRD-09: resolve_agent wraps GA in a review LoopAgent
    # because this field is set (non-empty string).
    "default_acceptance_criteria": GA_SPECIALIST_ACCEPTANCE_CRITERIA,

    # AH-92: None → DEFAULT_REVIEWER_MODEL (gemini-2.5-pro).
    "reviewer_model": None,

    # AH-82: delegation gate — MUST be True to be reachable from chat.
    "ken_e_sub_agent": True,

    # AH-41: explicit audit fields per AUDIT_FIELDS_USER_FACING_RESEARCHER.
    # GA-specific overrides: code_execution_enabled=True (instead of False)
    # and mcp_servers populated (instead of []). Spread last so GA-specific
    # values are the final source of truth for these two fields.
    **{
        **AUDIT_FIELDS_USER_FACING_RESEARCHER,
        "code_execution_enabled": True,
        "mcp_servers": ["google_analytics_mcp"],
    },

    "metadata": {
        "version": "v1.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": (
            "AH-25 / AH-PRD-03 Phase 1: initial GA Specialist config. "
            "Replaces the deprecated google_analytics_agent_v4.py dispatch path. "
            "Resolved by the AH-PRD-09 per-turn runtime resolver via "
            "specialist_runtime.resolve_agent('google_analytics_specialist')."
        ),
    },
}


# ---------------------------------------------------------------------------
# MCP server patch
# ---------------------------------------------------------------------------

MCP_COLLECTION = "mcp_server_configs"
MCP_DOC_ID = "google_analytics_mcp"

# Valid ``kind`` values — mirrors api/scripts/migrate_mcp_servers_add_kind.py.
_VALID_KINDS: frozenset[str] = frozenset({"cloud_run", "zapier"})

GA_MCP_PATCH: dict[str, Any] = {
    "kind": "cloud_run",
    "specialist_categories": ["analytics"],
    "auth_type": "ga_oauth",
    "enabled": True,
}


def _needs_kind_backfill(doc: dict[str, Any]) -> bool:
    """Return True when the MCP doc needs its ``kind`` field set.

    Mirrors the logic in ``api/scripts/migrate_mcp_servers_add_kind.py``
    so the patch behaviour is consistent with the AH-PRD-09 Phase 3 backfill.

    Args:
        doc: The existing Firestore MCP server document payload.

    Returns:
        True when ``kind`` is missing, ``None``, empty, or unrecognised.
        False when ``kind`` is already a valid value (``"cloud_run"`` /
        ``"zapier"``).
    """
    kind = doc.get("kind")
    if kind is None:
        return True
    if isinstance(kind, str) and not kind.strip():
        return True
    if isinstance(kind, str) and kind.strip() not in _VALID_KINDS:
        logger.warning(
            "Unrecognised kind value %r on mcp_server_configs/%s — "
            "will overwrite with 'cloud_run'",
            kind,
            MCP_DOC_ID,
        )
        return True
    return False


def upsert_mcp_patch(
    project_id: str,
    *,
    dry_run: bool = False,
    db: Any | None = None,
) -> bool:
    """Idempotently patch ``mcp_server_configs/google_analytics_mcp``.

    Writes ``GA_MCP_PATCH`` via ``set(..., merge=True)``.  When ``kind`` is
    already ``"cloud_run"`` or ``"zapier"``, that value is **preserved** (the
    patch still writes the other fields in ``GA_MCP_PATCH``).

    Args:
        project_id: GCP project ID (used only when ``db`` is ``None``).
        dry_run: When ``True``, log the intended action without writing.
        db: Pre-built Firestore client (for testing / dependency injection).
            When ``None``, a real client is created from ``project_id``.

    Returns:
        ``True`` on successful upsert (or successful dry-run); ``False`` if a
        Firestore exception was raised.
    """
    if dry_run:
        logger.info(
            "[DRY RUN] Would patch '%s/%s': %s",
            MCP_COLLECTION,
            MCP_DOC_ID,
            sorted(GA_MCP_PATCH.keys()),
        )
        return True

    try:
        if db is None:
            from google.cloud import firestore

            db = firestore.Client(project=project_id)

        doc_ref = db.collection(MCP_COLLECTION).document(MCP_DOC_ID)
        existing_snap = doc_ref.get()
        existing_doc: dict[str, Any] = existing_snap.to_dict() or {} if existing_snap.exists else {}

        # Build effective patch: if kind is already valid, don't overwrite it.
        patch: dict[str, Any] = dict(GA_MCP_PATCH)
        if not _needs_kind_backfill(existing_doc):
            existing_kind = str(existing_doc.get("kind", "")).strip()
            patch["kind"] = existing_kind
            logger.debug(
                "mcp_server_configs/%s already has kind=%r — preserving",
                MCP_DOC_ID,
                existing_kind,
            )

        doc_ref.set(patch, merge=True)
        action = "Updated" if existing_snap.exists else "Created"
        logger.info("MCP patch applied: %s mcp_server_configs/%s", action, MCP_DOC_ID)
        return True

    except Exception as exc:
        logger.error("Failed to patch mcp_server_configs/%s: %s", MCP_DOC_ID, exc)
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main script entry point.

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Migrate Google Analytics Specialist configuration to Firestore. "
            "Writes agent_configs/google_analytics_specialist and patches "
            "mcp_server_configs/google_analytics_mcp. Idempotent."
        )
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default="ken-e-dev",
        help="GCP project ID (default: ken-e-dev)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode — show what would be done without making changes",
    )

    args = parser.parse_args()

    logger.info("Starting GA Specialist migration to Firestore")
    logger.info("Project: %s", args.project_id)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("-" * 60)

    # 1. Write agent_configs/google_analytics_specialist
    logger.info("Step 1/2 — Writing agent_configs/google_analytics_specialist ...")
    agent_ok = upsert_agent_config(
        config=GA_SPECIALIST_CONFIG,
        doc_id="google_analytics_specialist",
        project_id=args.project_id,
        dry_run=args.dry_run,
    )

    # 2. Patch mcp_server_configs/google_analytics_mcp
    logger.info("Step 2/2 — Patching mcp_server_configs/google_analytics_mcp ...")
    mcp_ok = upsert_mcp_patch(project_id=args.project_id, dry_run=args.dry_run)

    logger.info("-" * 60)
    if agent_ok and mcp_ok:
        logger.info("Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info(
            "1. Verify agent_configs/google_analytics_specialist in the Firestore console"
        )
        logger.info(
            "2. Verify mcp_server_configs/google_analytics_mcp shows kind=cloud_run"
        )
        logger.info(
            "3. On the next chat turn the runtime resolver picks up the new config"
            " via config_cache (<=60 s TTL) — no redeploy required"
        )
        logger.info(
            "4. The root agent will delegate to google_analytics_specialist via"
            " transfer_to_agent once the specialist appears in the Available Specialists block"
        )
    else:
        failed = [
            name
            for name, ok in [("agent_config", agent_ok), ("mcp_patch", mcp_ok)]
            if not ok
        ]
        logger.error("Migration failed for: %s", failed)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
