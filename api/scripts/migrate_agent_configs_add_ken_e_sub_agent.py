#!/usr/bin/env python3
"""Set ``ken_e_sub_agent=False`` on strategy-pipeline and workflow-only agents.

AH-82 — introduces the explicit ``ken_e_sub_agent`` delegation gate that
decouples "show in Workflows UI" (``visible_in_frontend``) from "attach as
sub-agent to root agent for chat delegation" (``ken_e_sub_agent``).

The new field defaults to ``True``, so existing Firestore docs that lack it
are treated as delegatable — the correct fail-open default for a fresh flag
rollout.  This script flips the small set of known workflow-only agents to
``False`` so they are excluded from ``root.sub_agents`` and from the
"Available Specialists" prompt block in chat.

Target agents (hardcoded)
--------------------------
Strategy-pipeline specialists that exist only to be called by another agent
inside an automated workflow and must never be a direct chat-delegation target:

    business_researcher, business_formatter,
    competitive_researcher, competitive_formatter,
    marketing_researcher, marketing_formatter,
    brand_researcher, brand_formatter

``--enumerate-other-formatters`` mode
--------------------------------------
Run with ``--enumerate-other-formatters`` to scan the live ``agent_configs``
collection and print any doc whose ID ends in ``_formatter`` that is NOT
already in the explicit list above.  Use this as a pre-flight check before
flipping to ensure no undiscovered workflow-only formatters are left behind.

Idempotency
-----------
A doc whose ``ken_e_sub_agent`` is already ``False`` is logged as unchanged
and not rewritten.  A doc that does not exist in Firestore is logged under
the ``missing`` counter and skipped.  Re-running on an already-migrated
collection produces zero writes.

Ops sequence (IMPORTANT)
------------------------
Run the migration BEFORE deploying the new API image in each environment.
The migration writes a field the old code ignores, so it is safe to run
pre-deploy.  The deployment sequence is:

    1. ``uv run python api/scripts/migrate_agent_configs_add_ken_e_sub_agent.py --project-id <env>``
    2. ``make deploy-api``  (or equivalent for the target environment)

If the new image deploys before the migration runs, the 8 strategy-pipeline
agents will momentarily default to ``True`` (delegatable) for the window
until the migration completes.  That window is transient and safe for a
pre-production system; the fix is to re-run the migration after deploy.

Usage
-----
::

    # Pre-flight: check for unlisted formatters
    uv run python api/scripts/migrate_agent_configs_add_ken_e_sub_agent.py \\
        --project-id ken-e-dev --enumerate-other-formatters

    # Dry run — no writes; inspect the output
    uv run python api/scripts/migrate_agent_configs_add_ken_e_sub_agent.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/migrate_agent_configs_add_ken_e_sub_agent.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "agent_configs"

# Eight strategy-pipeline agents that exist only to be called by another agent
# inside an automated workflow.  They must never be direct chat-delegation
# targets; set ken_e_sub_agent=False on each.
STRATEGY_PIPELINE_AGENTS: tuple[str, ...] = (
    "business_researcher",
    "business_formatter",
    "competitive_researcher",
    "competitive_formatter",
    "marketing_researcher",
    "marketing_formatter",
    "brand_researcher",
    "brand_formatter",
)

# Extension point: operators may extend this tuple after running
# ``--enumerate-other-formatters`` if additional workflow-only agents are
# found in a specific environment.  Set to an empty tuple by default; the
# migration touches STRATEGY_PIPELINE_AGENTS regardless of this value.
OTHER_WORKFLOW_ONLY_AGENTS: tuple[str, ...] = ()

_ALL_TARGET_AGENTS: frozenset[str] = frozenset(
    STRATEGY_PIPELINE_AGENTS + OTHER_WORKFLOW_ONLY_AGENTS
)


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _needs_ken_e_sub_agent_backfill(doc: dict[str, Any]) -> bool:
    """Return True when the doc needs ``ken_e_sub_agent`` set to ``False``.

    A doc needs a patch when ``ken_e_sub_agent`` is absent, ``None``, or
    ``True``.  A doc with ``ken_e_sub_agent: False`` is already correct.
    """
    val = doc.get("ken_e_sub_agent")
    return val is not False


def _is_unlisted_formatter(doc_id: str) -> bool:
    """Return True when *doc_id* ends with ``_formatter`` and is NOT in the
    explicit target list.  Used by ``--enumerate-other-formatters`` mode."""
    return doc_id.endswith("_formatter") and doc_id not in _ALL_TARGET_AGENTS


# ---------------------------------------------------------------------------
# Core backfill function
# ---------------------------------------------------------------------------


def backfill(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
    enumerate_other_formatters: bool = False,
) -> dict[str, int]:
    """Run the backfill.

    Returns counts: {patched, would_patch, unchanged, missing, errors}.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing).  When ``None``
            a client is created lazily — avoids requiring GCP creds on
            ``--dry-run`` when the caller already has a fake db.
        enumerate_other_formatters: When ``True``, scan the full collection
            and log any doc whose ID ends in ``_formatter`` that is not in the
            explicit target list.  Informational only; does not write.

    Returns:
        A dict with integer counts for ``patched``, ``would_patch``,
        ``unchanged``, ``missing``, and ``errors``.
    """
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    collection = db.collection(COLLECTION)
    counts: dict[str, int] = {
        "patched": 0,
        "would_patch": 0,
        "unchanged": 0,
        "missing": 0,
        "errors": 0,
    }

    # --- enumerate-other-formatters pre-flight scan ---------------------------
    if enumerate_other_formatters:
        logger.info(
            "[PRE-FLIGHT] Scanning %s for unlisted _formatter docs ...", COLLECTION
        )
        found_unlisted: list[str] = []
        for snapshot in collection.stream():
            if _is_unlisted_formatter(snapshot.id):
                found_unlisted.append(snapshot.id)
        if found_unlisted:
            logger.warning(
                "[PRE-FLIGHT] Unlisted _formatter docs found (consider adding to "
                "OTHER_WORKFLOW_ONLY_AGENTS if workflow-only): %s",
                sorted(found_unlisted),
            )
        else:
            logger.info(
                "[PRE-FLIGHT] No unlisted _formatter docs found. "
                "Explicit list covers all formatter agents."
            )

    # --- main pass: process explicit target list only -------------------------
    for agent_id in sorted(_ALL_TARGET_AGENTS):
        doc_ref = collection.document(agent_id)
        try:
            snapshot = doc_ref.get()
        except Exception as exc:
            logger.error("Failed to read %s/%s: %s", COLLECTION, agent_id, exc)
            counts["errors"] += 1
            continue

        if not snapshot.exists:
            logger.warning(
                "Doc %s/%s not found — skipping (missing counter).",
                COLLECTION,
                agent_id,
            )
            counts["missing"] += 1
            continue

        doc: dict[str, Any] = snapshot.to_dict() or {}

        if not _needs_ken_e_sub_agent_backfill(doc):
            logger.debug(
                "Doc %s/%s already has ken_e_sub_agent=False — no change.",
                COLLECTION,
                agent_id,
            )
            counts["unchanged"] += 1
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch %s/%s: ken_e_sub_agent=False "
                "(current value: %r)",
                COLLECTION,
                agent_id,
                doc.get("ken_e_sub_agent", "<absent>"),
            )
            counts["would_patch"] += 1
            continue

        try:
            doc_ref.update({"ken_e_sub_agent": False})
            logger.info(
                "Patched %s/%s: ken_e_sub_agent=False",
                COLLECTION,
                agent_id,
            )
            counts["patched"] += 1
        except Exception as exc:
            logger.error(
                "Failed to patch %s/%s: %s",
                COLLECTION,
                agent_id,
                exc,
            )
            counts["errors"] += 1

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Set ken_e_sub_agent=False on strategy-pipeline and other workflow-only "
            "agent_configs docs (AH-82).  Idempotent: re-running on an already-migrated "
            "collection produces zero writes."
        )
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="GCP project ID (e.g. ken-e-dev, ken-e-staging, ken-e-production)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be patched without writing to Firestore",
    )
    parser.add_argument(
        "--enumerate-other-formatters",
        action="store_true",
        help=(
            "Scan the full agent_configs collection and print any doc whose ID "
            "ends in _formatter that is NOT in the explicit target list. "
            "Informational only — no writes."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("AH-82: ken_e_sub_agent=False backfill for strategy-pipeline agents")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("Enumerate other formatters: %s", args.enumerate_other_formatters)
    logger.info("Target agents: %s", sorted(_ALL_TARGET_AGENTS))
    logger.info("-" * 60)

    counts = backfill(
        project_id=args.project_id,
        dry_run=args.dry_run,
        enumerate_other_formatters=args.enumerate_other_formatters,
    )

    logger.info("-" * 60)
    if args.dry_run:
        logger.info(
            "Done (dry-run). would_patch=%d, unchanged=%d, missing=%d",
            counts["would_patch"],
            counts["unchanged"],
            counts["missing"],
        )
    else:
        logger.info(
            "Done. patched=%d, unchanged=%d, missing=%d, errors=%d",
            counts["patched"],
            counts["unchanged"],
            counts["missing"],
            counts["errors"],
        )

    return 1 if counts["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
