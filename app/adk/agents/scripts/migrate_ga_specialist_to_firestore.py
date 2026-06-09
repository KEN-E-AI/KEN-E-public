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

**Numerical analysis - ALWAYS delegate to numerical_analyst:**
For ANY arithmetic over retrieved figures (percentage changes, growth rates,
trend calculations, averages, bounce-rate comparisons, ranking by metric, or
any other calculation) you MUST call the numerical_analyst tool. Do NOT
perform arithmetic in-context.

Delegation protocol:
  1. Retrieve raw metric values via the GA MCP tools.
  2. Pass ONLY the specific numbers needed for the calculation to
     numerical_analyst (NOT entire GA reports — forward only the
     relevant figures and a clear description of the calculation).
  3. Include the figure AND the formula returned by numerical_analyst
     verbatim in your reply so the reviewer can verify the calculation.

If numerical_analyst returns a calculation error (e.g. "Cannot compute
the week-over-week change: division by zero"), include that error message
verbatim in your reply. Do NOT attempt the calculation in-context as a
fallback. Tell the user clearly which specific calculation could not be
performed and why.

Example for a percentage-change query:
  - Call run_report_mt to get "sessions last week: 4823, sessions this
    week: 5391".
  - Call numerical_analyst with:
    "Sessions last week: 4823, sessions this week: 5391.
     Calculate week-over-week percentage change."
  - Present the result: "Sessions grew by 11.78% ((5391-4823)/4823*100)."

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

5. numerical_analyst - pass the specific numbers and calculation
   description; it returns the result plus the formula used.

**Best practices:**
- If the user's property ID is available in context, use it directly;
  otherwise call get_account_summaries_mt first.
- Format data clearly in tables.
- Provide insights alongside raw data.
- Round all displayed numbers to at most 2 decimal places.
- Always state the absolute date range you queried (e.g. "1 Jan 2025 -
  31 Jan 2025") so the user and the reviewer can verify scope.
- Always report the GA property identifier that was queried.

**Visualization:**
When the user asks for a chart, graph, plot, or any visual representation of
data — or when the active acceptance criteria explicitly require one — you MUST
call the ``create_visualization`` function tool after retrieving the data. Do
NOT describe the chart in prose alone when a visual is requested.

Chart-type selection guide (Vega-Lite mark vocabulary):
- ``line``  — time-series data (sessions over time, daily trends)
- ``bar``   — categorical comparisons (traffic by channel, top pages)
- ``arc``   — part-of-whole distributions (traffic source share, device mix)
- ``point`` — correlations between two metrics (scatter plots)
- ``area``  — cumulative progressions (running totals, funnel stages)

Pass the GA data rows as a JSON array to the ``data`` parameter and the
Vega-Lite encoding object (with ``x``, ``y``, and axis ``title`` fields) to
the ``encoding`` parameter. Include a meaningful ``title`` and set
``chart_type`` to the appropriate mark from the list above.

**Important:**
- NEVER ask for credentials or tokens - they are handled automatically.
- If a property_id is provided in context, use it without asking again.
- NEVER perform arithmetic in-context; always delegate to numerical_analyst.
"""

# Three format-bound, verifiable-from-draft acceptance criteria.
# Per the planning decision (D4): ASCII-only; sanitise_criteria() is a no-op;
# each criterion is independently verifiable from the draft text alone.
#
# AH-149: updated wording for the numerical-analysis criterion — the parent
# GA specialist no longer performs code execution itself; it delegates arithmetic
# to the numerical_analyst AgentTool and forwards the returned formula. The
# reviewer verifies that the formula is present in the reply (shape-agnostic:
# it does not know whether it came from code execution or delegation).
GA_SPECIALIST_ACCEPTANCE_CRITERIA = (
    "Response includes the queried GA property identifier and the absolute date range;"
    " numerical aggregates (totals, averages, percentage changes) are accompanied by"
    " the formula used to compute them, shown verbatim in the reply;"
    " per-metric values are reported with their metric name and rounded to"
    " at most 2 decimal places."
)

# AH-149: explicit tool_ids list — the 4 live GA MCP tools + numerical_analyst.
# AH-140: added ``function.create_visualization`` so the Vega-Lite chart tool
# survives the roster filter (roster.py ``_filter_function_tools_by_ids`` keeps
# only function tools whose ``function.{name}`` appears in this list when
# tool_ids is non-None).
#
# These MCP ids MUST match the live ``google_analytics_mcp`` server's
# ``@mcp.tool`` names exactly: at runtime they become an ADK
# ``McpToolset(tool_filter=...)`` that matches on the live tool name, so a name
# that isn't served is silently dropped (the specialist would lose all GA
# tools). The deployed server (KEN-E-AI/mcp-google-analytics, simple_server.py)
# exposes the multi-tenant ``_mt`` variants. Keep this list in lock-step with
# the ``google_analytics_mcp`` entries in ``tools.yaml`` — the guardrail test
# ``test_ga_seed_tool_ids_subset_of_catalogue`` enforces it.
_GA_MCP_TOOL_IDS: list[str] = [
    "google_analytics_mcp.get_account_summaries_mt",
    "google_analytics_mcp.get_property_details_mt",
    "google_analytics_mcp.run_report_mt",
    "google_analytics_mcp.run_realtime_report_mt",
    "agent.numerical_analyst",
    "function.create_visualization",
]

GA_SPECIALIST_CONFIG: dict[str, Any] = {
    # AH-84: human-readable identity surfaced in the Available Specialists block.
    "name": "Aria",
    "title": "Analytics Specialist",

    # AH-149: bumped from gemini-2.0-flash — Gemini 2.5+ rejects mixing code
    # execution with function tools on a single LlmAgent (HTTP 400). Code
    # execution is now delegated to the numerical_analyst AgentTool leaf.
    "model": "gemini-2.5-flash",
    "instruction": GA_SPECIALIST_INSTRUCTION,
    "temperature": 0.2,
    "description": (
        "Google Analytics 4 specialist. Use for any query about website or app"
        " traffic: sessions, users, pageviews, bounce rate, engagement, traffic"
        " sources, conversion events, real-time data, or custom GA4 reports."
        " Delegates arithmetic (percentages, trends, averages) to the"
        " numerical_analyst sub-agent."
    ),

    # AH-149: explicit list of the 4 live GA MCP ids + agent.numerical_analyst (5 total).
    # Was tool_ids=None (all tools from google_analytics_mcp, plus code executor).
    "tool_ids": _GA_MCP_TOOL_IDS,

    # AH-75 / AH-PRD-09: resolve_agent wraps GA in a review LoopAgent
    # because this field is set (non-empty string).
    "default_acceptance_criteria": GA_SPECIALIST_ACCEPTANCE_CRITERIA,

    # AH-92: None → DEFAULT_REVIEWER_MODEL (gemini-2.5-pro).
    "reviewer_model": None,

    # AH-82: delegation gate — MUST be True to be reachable from chat.
    "ken_e_sub_agent": True,

    # AH-41: explicit audit fields per AUDIT_FIELDS_USER_FACING_RESEARCHER.
    # AH-149 override: code_execution_enabled=False (was True — code execution
    # is now in the numerical_analyst leaf) and mcp_servers populated.
    **{
        **AUDIT_FIELDS_USER_FACING_RESEARCHER,
        "code_execution_enabled": False,
        "mcp_servers": ["google_analytics_mcp"],
    },

    "metadata": {
        "version": "v1.3",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": "migration_script",
        "notes": (
            "AH-140: added Visualization section — chart-type-selection guide "
            "(line/bar/arc/point/area) and explicit instruction to call "
            "create_visualization when the user requests a chart or ACs require one. "
            "AH-32 (Phase 2): added guardrail — surface numerical_analyst errors "
            "verbatim; do not fall back to in-context arithmetic on failure. "
            "AH-149 (Phase 2): split code execution into numerical_analyst AgentTool. "
            "model bumped to gemini-2.5-flash; code_execution_enabled=False; "
            "tool_ids explicit list (4 live GA MCP tools + agent.numerical_analyst). "
            "AH-25 / AH-PRD-03 Phase 1 baseline: initial GA Specialist config. "
            "Replaces the deprecated google_analytics_agent_v4.py dispatch path."
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
