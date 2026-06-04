#!/usr/bin/env python3
"""Targeted rollout migration: apply the AH-149 numerical_analyst split to
the already-deployed GA specialist Firestore document.

This script writes EXACTLY FOUR fields to
``agent_configs/google_analytics_specialist`` via ``set(..., merge=True)``
so that:

  1. ``code_execution_enabled`` → ``False`` (code execution now lives in the
     ``numerical_analyst`` leaf AgentTool — combining code execution with
     function tools on a single LlmAgent causes Gemini 2.5+ to return HTTP
     400 "Multiple tools are supported only when they are all search tools").
  2. ``model`` → ``gemini-2.5-flash`` (unblocked by removing code_execution
     from the parent; ``gemini-2.0-flash`` 404s on ``ken-e-production``).
  3. ``tool_ids`` → explicit list of the 4 live GA MCP tool ids plus
     ``agent.numerical_analyst``.
  4. ``instruction`` → the rewritten parent instruction that delegates all
     arithmetic to the ``numerical_analyst`` tool.

.. note::

   **This script intentionally does NOT re-run the full seed** (i.e. it does
   not call ``migrate_ga_specialist_to_firestore.main()``). Re-running the
   full seed would also overwrite fields like ``temperature``, ``description``,
   and ``reviewer_model`` that admins may have customised via the Workflows UI.
   Only the four fields owned by the AH-149 split are written. Non-targeted
   fields on the existing document survive untouched.

.. warning::

   ``instruction`` IS overwritten by this script (field 4 above). The new
   instruction is required because it tells the parent to delegate arithmetic
   to the ``numerical_analyst`` tool; without it the parent would still attempt
   in-context arithmetic and never call the new tool. If your production GA
   doc has a custom instruction, reconcile it back to
   ``migrate_ga_specialist_to_firestore.GA_SPECIALIST_INSTRUCTION`` before
   re-running, or the custom text will be lost.

   This migration is intended as a **one-shot per environment**. Re-running it
   after admins have edited the instruction via the UI will overwrite their edits.

Usage::

    python migrate_ga_split_numerical_analyst.py [--project-id PROJECT_ID] [--dry-run]

Examples::

    # Development environment
    python migrate_ga_split_numerical_analyst.py --project-id ken-e-dev

    # Staging environment
    python migrate_ga_split_numerical_analyst.py --project-id ken-e-staging

    # Production environment
    python migrate_ga_split_numerical_analyst.py --project-id ken-e-production

    # Dry run (no actual changes)
    python migrate_ga_split_numerical_analyst.py --project-id ken-e-dev --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

# Make ``app`` importable when run as a script.
_repo_root = Path(__file__).resolve().parent
while _repo_root != _repo_root.parent and not (_repo_root / ".git").exists():
    _repo_root = _repo_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Import the four AH-149 values from the seed module (single source of truth).
from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (  # noqa: E402
    _GA_MCP_TOOL_IDS,
    GA_SPECIALIST_INSTRUCTION,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_CONFIGS_COLLECTION = "agent_configs"
GA_SPECIALIST_DOC_ID = "google_analytics_specialist"

# The four fields this migration owns.  Keys match Firestore field names exactly.
_SPLIT_PATCH: dict[str, Any] = {
    "code_execution_enabled": False,
    "model": "gemini-2.5-flash",
    "tool_ids": _GA_MCP_TOOL_IDS,
    "instruction": GA_SPECIALIST_INSTRUCTION,
}


def apply_split_patch(
    project_id: str,
    *,
    dry_run: bool = False,
    db: Any | None = None,
) -> bool:
    """Write the four AH-149 fields to ``agent_configs/google_analytics_specialist``.

    Uses ``set(..., merge=True)`` so only the four targeted keys are written;
    all other fields on the existing document are preserved.

    Args:
        project_id: GCP project ID (used only when ``db`` is ``None``).
        dry_run: When ``True``, log the intended patch without writing.
        db: Pre-built Firestore client (for testing / dependency injection).
            When ``None``, a real client is created from ``project_id``.

    Returns:
        ``True`` on success (or successful dry-run); ``False`` on error.
    """
    if dry_run:
        logger.info(
            "[DRY RUN] Would write to '%s/%s': %s",
            AGENT_CONFIGS_COLLECTION,
            GA_SPECIALIST_DOC_ID,
            sorted(_SPLIT_PATCH.keys()),
        )
        logger.info("[DRY RUN] Values: model=%r, code_execution_enabled=%r, "
                    "tool_ids length=%d, instruction length=%d",
                    _SPLIT_PATCH["model"],
                    _SPLIT_PATCH["code_execution_enabled"],
                    len(_SPLIT_PATCH["tool_ids"]),
                    len(_SPLIT_PATCH["instruction"]))
        return True

    try:
        if db is None:
            from google.cloud import firestore
            db = firestore.Client(project=project_id)

        doc_ref = db.collection(AGENT_CONFIGS_COLLECTION).document(GA_SPECIALIST_DOC_ID)
        existing_snap = doc_ref.get()
        action = "Updated" if existing_snap.exists else "Created"

        doc_ref.set(_SPLIT_PATCH, merge=True)
        logger.info(
            "%s %s/%s with fields: %s",
            action,
            AGENT_CONFIGS_COLLECTION,
            GA_SPECIALIST_DOC_ID,
            sorted(_SPLIT_PATCH.keys()),
        )
        return True

    except Exception as exc:
        logger.error(
            "Failed to patch %s/%s: %s",
            AGENT_CONFIGS_COLLECTION,
            GA_SPECIALIST_DOC_ID,
            exc,
        )
        return False


def main() -> int:
    """Main CLI entry point.

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Apply the AH-149 numerical_analyst split to the GA specialist "
            "Firestore document. Writes exactly four fields: "
            "code_execution_enabled, model, tool_ids, instruction."
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

    logger.info("Starting AH-149 GA specialist split migration")
    logger.info("Project: %s", args.project_id)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("Target doc: %s/%s", AGENT_CONFIGS_COLLECTION, GA_SPECIALIST_DOC_ID)
    logger.info("Fields to write: %s", sorted(_SPLIT_PATCH.keys()))
    logger.info("-" * 60)

    ok = apply_split_patch(project_id=args.project_id, dry_run=args.dry_run)

    logger.info("-" * 60)
    if ok:
        logger.info("Migration completed successfully!")
        if not args.dry_run:
            logger.info("")
            logger.info("Next steps:")
            logger.info(
                "1. Verify agent_configs/google_analytics_specialist in the Firestore console"
            )
            logger.info(
                "   Expected: model='gemini-2.5-flash', code_execution_enabled=False,"
            )
            logger.info(
                "   tool_ids=[<4 live GA MCP ids>, 'agent.numerical_analyst']"
            )
            logger.info(
                "2. Wait <=60 s for the AH-PRD-09 config_cache TTL to expire,"
                " then send a GA query in chat to verify the specialist responds"
                " without a 400 or 404 error."
            )
    else:
        logger.error("Migration failed — see errors above")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
