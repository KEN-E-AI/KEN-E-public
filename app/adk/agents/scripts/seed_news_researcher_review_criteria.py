#!/usr/bin/env python3
"""
Seed ``default_acceptance_criteria`` on the ``company_news_agent`` Firestore
document in ``ken-e-dev`` to exercise the Generator-Critic review loop.

.. warning::

   **Dev-only.** This script refuses to run against any project other than
   ``ken-e-dev``.  It performs an UPDATE (not a CREATE): the
   ``company_news_agent`` doc must already exist.  Run
   ``migrate_news_agent_to_firestore.py`` first if it doesn't.

   **Only ``default_acceptance_criteria`` is written.**  Every other field
   on the existing doc is preserved by ``set(..., merge=True)``.  Safe to
   re-run.

Usage:
    python seed_news_researcher_review_criteria.py [--project-id ken-e-dev] [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

# Make ``app`` importable when this file is executed as a script.
_repo_root = Path(__file__).resolve().parent
while _repo_root != _repo_root.parent and not (_repo_root / ".git").exists():
    _repo_root = _repo_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.adk.agents.scripts._seed_helpers import upsert_agent_config  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REVIEW_CRITERIA_TEXT = (
    "Response cites at least 3 distinct sources, each with a publication date;"
    " the summary is at most 200 words; no factual claim is made without a cited source."
)
TARGET_DOC_ID = "company_news_agent"
DEV_PROJECT_ID = "ken-e-dev"


def main() -> int:
    """Seed ``default_acceptance_criteria`` on the ``company_news_agent`` doc.

    Returns:
        0 on success, 1 on failure.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Seed default_acceptance_criteria on the company_news_agent "
            "Firestore document (dev-only)."
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
        help="Dry run mode - show what would be done without making changes",
    )

    args = parser.parse_args()

    # Hard guard: refuse to run against any project other than ken-e-dev.
    if args.project_id != DEV_PROJECT_ID:
        logger.error(
            "This script is dev-only and refuses to run against"
            " '%s'. Allowed: 'ken-e-dev'.",
            args.project_id,
        )
        sys.exit(2)

    logger.info("Seeding default_acceptance_criteria on company_news_agent")
    logger.info(f"Project: {args.project_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("-" * 60)

    # Read-before-write precondition: verify the doc exists before writing.
    if not args.dry_run:
        from google.cloud import firestore

        db = firestore.Client(project=args.project_id)
        doc_ref = db.collection("agent_configs").document(TARGET_DOC_ID)
        if not doc_ref.get().exists:
            logger.error(
                f"Document 'agent_configs/{TARGET_DOC_ID}' does not exist in"
                f" project '{args.project_id}'. Run"
                " migrate_news_agent_to_firestore.py first to create it."
            )
            return 1
    else:
        db = None

    payload = {"default_acceptance_criteria": REVIEW_CRITERIA_TEXT}

    success = upsert_agent_config(
        payload,
        TARGET_DOC_ID,
        args.project_id,
        dry_run=args.dry_run,
        db=db,
    )

    logger.info("-" * 60)
    if success:
        logger.info("Seed completed successfully!")
        logger.info("\nNext steps:")
        logger.info("1. Verify the field in Firestore console")
        logger.info("2. Trigger a chat session with the company_news_agent")
        logger.info("3. Confirm the Generator-Critic review loop enforces the criteria")
    else:
        logger.error("Seed failed!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
