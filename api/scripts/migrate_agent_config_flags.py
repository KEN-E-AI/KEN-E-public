#!/usr/bin/env python3
"""Backfill three boolean flags onto existing ``agent_configs`` Firestore docs.

Every document in the ``agent_configs`` Firestore collection must have the
following boolean fields present for the agent factory (AH-18) to function
correctly:

- ``available_to_copy`` (default: ``True``)
- ``automatically_available`` (default: ``True``)
- ``visible_in_frontend`` (default: ``True``)

This script is a **one-time, idempotent migration** that backfills those flags
onto documents that were written before the fields were introduced.

Idempotency rules
-----------------
1. All three flags already present as ``bool`` values → **no write** (already
   correct).
2. One or more flags are **absent** (key missing) or ``None`` → **patch** only
   the missing keys with their default value (``True``); existing ``bool``
   values are preserved.

The script is **idempotent**: re-running on an already-migrated collection
produces zero writes.

Usage
-----
    # Dry run — no writes; inspect the output
    uv run python api/scripts/migrate_agent_config_flags.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/migrate_agent_config_flags.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "agent_configs"
FLAGS = ("available_to_copy", "automatically_available", "visible_in_frontend")


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _missing_flags(doc: dict[str, Any]) -> list[str]:
    """Return list of flag names that are absent or None in the doc.

    A key is considered missing when:
    - the key is not present in the doc dict at all, or
    - the key is present but its value is ``None``.

    A key whose value is a ``bool`` (``True`` or ``False``) is NOT missing.
    """
    missing: list[str] = []
    for flag in FLAGS:
        value = doc.get(flag)
        if not isinstance(value, bool):
            missing.append(flag)
    return missing


def _default_for_flag(name: str) -> bool:
    """Return the default value (True) for any of the three flags."""
    return True


# ---------------------------------------------------------------------------
# Core migration function
# ---------------------------------------------------------------------------


def migrate(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Run the migration. Returns counts: {patched, would_patch, unchanged, errors}.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing). When ``None``
            a client is created lazily — avoids requiring GCP creds when a
            fake db is injected.

    Returns:
        A dict with integer counts for ``patched``, ``would_patch``,
        ``unchanged``, and ``errors``.
    """
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    collection = db.collection(COLLECTION)
    counts: dict[str, int] = {"patched": 0, "would_patch": 0, "unchanged": 0, "errors": 0}
    failed_ids: list[str] = []

    for snapshot in collection.stream():
        doc_id: str = snapshot.id
        doc: dict[str, Any] = snapshot.to_dict() or {}

        missing = _missing_flags(doc)

        if not missing:
            logger.debug("Doc %r already has all flags — no change", doc_id)
            counts["unchanged"] += 1
            continue

        patch: dict[str, bool] = {flag: _default_for_flag(flag) for flag in missing}

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch %s/%r: %s",
                COLLECTION,
                doc_id,
                missing,
            )
            counts["would_patch"] += 1
            continue

        try:
            collection.document(doc_id).update(patch)
            logger.info(
                "Patched %s/%r: %s",
                COLLECTION,
                doc_id,
                missing,
            )
            counts["patched"] += 1
        except Exception as exc:
            logger.error(
                "Failed to patch %s/%r: %s",
                COLLECTION,
                doc_id,
                exc,
            )
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
            "Backfill available_to_copy, automatically_available, and "
            "visible_in_frontend onto existing agent_configs Firestore docs. "
            "Idempotent: re-running on an already-migrated collection produces zero writes."
        )
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="GCP project ID (e.g. ken-e-dev, ken-e-staging, ken-e-prod)",
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
    _VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    raw_level = args.log_level.upper()
    if raw_level not in _VALID_LOG_LEVELS:
        parser.error(
            f"Invalid --log-level {args.log_level!r}. "
            f"Choose from: {', '.join(sorted(_VALID_LOG_LEVELS))}"
        )
    logging.basicConfig(
        level=getattr(logging, raw_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("agent_configs boolean flags migration")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("-" * 60)

    counts = migrate(project_id=args.project_id, dry_run=args.dry_run)

    logger.info("-" * 60)
    if args.dry_run:
        logger.info(
            "Done (dry-run). would_patch=%d, unchanged=%d",
            counts["would_patch"],
            counts["unchanged"],
        )
    else:
        logger.info(
            "Done. patched=%d, unchanged=%d, errors=%d",
            counts["patched"],
            counts["unchanged"],
            counts["errors"],
        )

    return 1 if counts["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
