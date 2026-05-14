#!/usr/bin/env python3
"""One-off migration: hide strategy-pipeline researchers from the picker.

AH-PRD-08 — closes the AH-PRD-06 §2 known-limitation for the eight
strategy-pipeline specialists. The four formatters
(``business_formatter``, ``competitive_formatter``,
``marketing_formatter``, ``brand_formatter``) are already hidden today
via ``AUDIT_FIELDS_FORMATTER`` in ``_seed_helpers.py``. The four
researchers (``business_researcher``, ``competitive_researcher``,
``marketing_researcher``, ``brand_researcher``) historically shared the
user-facing researcher profile and are visible-but-broken in the picker
on already-deployed Firestore data.

This script flips ``visible_in_frontend`` and ``available_to_copy`` to
``False`` on those four documents to match the new
``AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER`` profile. Fresh
environments seeded after the AH-PRD-08 change land with the correct
values directly; this script exists only to bring environments seeded
before the change in line.

Idempotency rules
-----------------
1. Both flags already ``False`` → **no write** (already correct).
2. One or both flags absent / ``None`` / ``True`` → **patch** only the
   keys whose values are not already ``False``.

The script is idempotent: re-running on an already-migrated collection
produces zero writes.

Usage
-----
::

    # Dry run — no writes; inspect the output
    uv run python api/scripts/migrate_strategy_pipeline_visibility.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/migrate_strategy_pipeline_visibility.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "agent_configs"

# The four strategy-pipeline researchers. The formatters are already
# hidden via AUDIT_FIELDS_FORMATTER and are not touched by this script.
STRATEGY_PIPELINE_RESEARCHERS: tuple[str, ...] = (
    "business_researcher",
    "competitive_researcher",
    "marketing_researcher",
    "brand_researcher",
)

# Fields this script enforces. Both must be ``False`` on the four target
# docs to match AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER.
FIELDS_TO_HIDE: tuple[str, ...] = ("visible_in_frontend", "available_to_copy")


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _fields_needing_patch(doc: dict[str, Any]) -> list[str]:
    """Return the list of FIELDS_TO_HIDE whose value is not already ``False``.

    A field needs a patch when it is absent, ``None``, or ``True``. A
    field whose value is already ``False`` is left alone.
    """
    return [field for field in FIELDS_TO_HIDE if doc.get(field) is not False]


# ---------------------------------------------------------------------------
# Core migration function
# ---------------------------------------------------------------------------


def migrate(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Run the migration. Returns counts.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing). When
            ``None`` a client is created lazily — avoids requiring GCP
            credentials when a fake db is injected.

    Returns:
        Dict with integer counts for ``patched``, ``would_patch``,
        ``unchanged``, ``missing``, and ``errors``. ``missing`` counts
        target docs not present in Firestore — a non-fatal signal that
        the environment hasn't been seeded yet.
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
    failed_ids: list[str] = []

    for doc_id in STRATEGY_PIPELINE_RESEARCHERS:
        doc_ref = collection.document(doc_id)
        snapshot = doc_ref.get()

        if not snapshot.exists:
            logger.warning(
                "Target doc %s/%r is absent — skipping. Run "
                "upload_baseline_configs.py to seed it.",
                COLLECTION,
                doc_id,
            )
            counts["missing"] += 1
            continue

        doc = snapshot.to_dict() or {}
        needs_patch = _fields_needing_patch(doc)

        if not needs_patch:
            logger.info(
                "Doc %s/%r already has correct values — no change.",
                COLLECTION,
                doc_id,
            )
            counts["unchanged"] += 1
            continue

        patch = dict.fromkeys(needs_patch, False)

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch %s/%r: %s",
                COLLECTION,
                doc_id,
                patch,
            )
            counts["would_patch"] += 1
            continue

        try:
            doc_ref.update(patch)
            logger.info("Patched %s/%r: %s", COLLECTION, doc_id, patch)
            counts["patched"] += 1
        except Exception as exc:
            logger.error("Failed to patch %s/%r: %s", COLLECTION, doc_id, exc)
            counts["errors"] += 1
            failed_ids.append(doc_id)

    if failed_ids:
        logger.error(
            "Migration incomplete — %d document(s) failed to patch: %s",
            len(failed_ids),
            failed_ids,
        )

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Hide the 4 strategy-pipeline researchers from the Workflows "
            "picker by setting visible_in_frontend=False and "
            "available_to_copy=False (AH-PRD-08). Idempotent."
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
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    raw_level = args.log_level.upper()
    if raw_level not in valid_levels:
        parser.error(
            f"Invalid --log-level {args.log_level!r}. "
            f"Choose from: {', '.join(sorted(valid_levels))}"
        )
    logging.basicConfig(
        level=getattr(logging, raw_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("AH-PRD-08 strategy-pipeline visibility migration")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("Targets:  %s", list(STRATEGY_PIPELINE_RESEARCHERS))
    logger.info("-" * 60)

    counts = migrate(project_id=args.project_id, dry_run=args.dry_run)

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
