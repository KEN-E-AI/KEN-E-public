#!/usr/bin/env python3
"""Backfill ``specialist_categories`` on existing MCP server config docs.

Every document in the ``mcp_server_configs`` Firestore collection must have a
non-empty ``specialist_categories`` list for the agent factory's
``load_toolsets_for_specialist()`` (AH-11) to group servers by specialist.

The original migration script (``migrate_mcp_to_firestore.py``, Sprint 6
Story 1.1.4-2) already writes ``specialist_categories`` from the YAML
``category`` field.  This script is a safety net for docs that were written
before that convention was established, or were updated out-of-band.

Backfill rules
--------------
1. Doc has non-empty ``specialist_categories`` list → **no write** (already
   correct).
2. Doc has empty or missing ``specialist_categories`` *and* a non-empty
   ``category`` string → **patch** ``specialist_categories = [category]``.
3. Doc has empty/missing ``specialist_categories`` *and* empty/missing
   ``category`` → **log WARNING, skip** (no write; human review required).

The script is **idempotent**: re-running on an already-migrated collection
produces zero writes.

Usage
-----
    # Dry run — no writes; inspect the output
    uv run python api/scripts/backfill_mcp_servers_specialist_categories.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/backfill_mcp_servers_specialist_categories.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "mcp_server_configs"


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _needs_backfill(doc: dict[str, Any]) -> bool:
    """Return True when the doc is missing or has an empty ``specialist_categories``."""
    cats = doc.get("specialist_categories")
    return not cats  # None, [], or missing


def _derive_categories(doc: dict[str, Any]) -> list[str] | None:
    """Derive the backfill value from ``category``.

    Returns:
        ``[category]`` when ``category`` is a non-empty string; ``None`` when
        the fallback field is also absent or empty (signals "skip" to the
        caller).
    """
    category = doc.get("category")
    if isinstance(category, str) and category.strip():
        return [category.strip()]
    return None


# ---------------------------------------------------------------------------
# Core backfill function
# ---------------------------------------------------------------------------


def backfill(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Run the backfill.  Returns counts: {patched, skipped, unchanged, errors}.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing).  When ``None``
            a client is created lazily — avoids requiring GCP creds on
            ``--dry-run`` when the caller already has a fake db.

    Returns:
        A dict with integer counts for ``patched``, ``skipped``,
        ``unchanged``, and ``errors``.
    """
    # Lazy import so --dry-run works in environments without GCP creds (unless
    # a fake db is injected).
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    collection = db.collection(COLLECTION)
    counts = {"patched": 0, "would_patch": 0, "skipped": 0, "unchanged": 0, "errors": 0}

    for snapshot in collection.stream():
        server_id: str = snapshot.id
        doc: dict[str, Any] = snapshot.to_dict() or {}

        if not _needs_backfill(doc):
            logger.debug("Server %r already has specialist_categories — no change", server_id)
            counts["unchanged"] += 1
            continue

        new_categories = _derive_categories(doc)
        if new_categories is None:
            logger.warning(
                "Server %r: missing both 'specialist_categories' and 'category' — "
                "cannot backfill automatically; manual review required",
                server_id,
            )
            counts["skipped"] += 1
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch %s/%s: specialist_categories=%s",
                COLLECTION,
                server_id,
                new_categories,
            )
            counts["would_patch"] += 1
            continue

        try:
            collection.document(server_id).update(
                {"specialist_categories": new_categories}
            )
            logger.info(
                "Patched %s/%s: specialist_categories=%s",
                COLLECTION,
                server_id,
                new_categories,
            )
            counts["patched"] += 1
        except Exception as exc:
            logger.error(
                "Failed to patch %s/%s: %s",
                COLLECTION,
                server_id,
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
            "Backfill specialist_categories on existing mcp_server_configs Firestore docs. "
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
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("MCP server specialist_categories backfill")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("-" * 60)

    counts = backfill(project_id=args.project_id, dry_run=args.dry_run)

    logger.info("-" * 60)
    if args.dry_run:
        logger.info(
            "Done (dry-run). would_patch=%d, unchanged=%d, skipped=%d",
            counts["would_patch"],
            counts["unchanged"],
            counts["skipped"],
        )
    else:
        logger.info(
            "Done. patched=%d, unchanged=%d, skipped=%d, errors=%d",
            counts["patched"],
            counts["unchanged"],
            counts["skipped"],
            counts["errors"],
        )

    return 1 if counts["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
