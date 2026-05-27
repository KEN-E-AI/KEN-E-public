#!/usr/bin/env python3
"""Backfill ``kind`` on existing MCP server config docs.

Every document in the ``mcp_server_configs`` Firestore collection must have
a ``kind`` field so the forthcoming ``McpToolsetPool`` (AH-62) can dispatch
correctly. All current servers are Cloud Run sidecars, so the safe default
is ``"cloud_run"``.

Backfill rules
--------------
1. Doc already has a non-empty ``kind`` value → **no write** (already
   correct; preserves any manually-set value such as ``"zapier"``).
2. Doc has ``kind`` missing, ``None``, or empty string → **patch**
   ``kind = "cloud_run"``.

The script is **idempotent**: re-running on an already-migrated collection
produces zero writes.

Usage
-----
    # Dry run — no writes; inspect the output
    uv run python api/scripts/migrate_mcp_servers_add_kind.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/migrate_mcp_servers_add_kind.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION = "mcp_server_configs"
DEFAULT_KIND = "cloud_run"


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _needs_kind_backfill(doc: dict[str, Any]) -> bool:
    """Return True when the doc is missing or has an empty/None ``kind``."""
    kind = doc.get("kind")
    if kind is None:
        return True
    if isinstance(kind, str) and not kind.strip():
        return True
    return False


# ---------------------------------------------------------------------------
# Core backfill function
# ---------------------------------------------------------------------------


def backfill(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Run the backfill.  Returns counts: {patched, would_patch, unchanged, errors}.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing).  When ``None``
            a client is created lazily — avoids requiring GCP creds on
            ``--dry-run`` when the caller already has a fake db.

    Returns:
        A dict with integer counts for ``patched``, ``would_patch``,
        ``unchanged``, and ``errors``.
    """
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    collection = db.collection(COLLECTION)
    counts = {"patched": 0, "would_patch": 0, "unchanged": 0, "errors": 0}

    for snapshot in collection.stream():
        server_id: str = snapshot.id
        doc: dict[str, Any] = snapshot.to_dict() or {}

        if not _needs_kind_backfill(doc):
            logger.debug("Server %r already has kind=%r — no change", server_id, doc.get("kind"))
            counts["unchanged"] += 1
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch %s/%s: kind=%r",
                COLLECTION,
                server_id,
                DEFAULT_KIND,
            )
            counts["would_patch"] += 1
            continue

        try:
            collection.document(server_id).update({"kind": DEFAULT_KIND})
            logger.info(
                "Patched %s/%s: kind=%r",
                COLLECTION,
                server_id,
                DEFAULT_KIND,
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
            "Backfill kind='cloud_run' on existing mcp_server_configs Firestore docs. "
            "Idempotent: re-running on an already-migrated collection produces zero writes."
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
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("MCP server kind backfill (adds kind='cloud_run' where missing)")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("-" * 60)

    counts = backfill(project_id=args.project_id, dry_run=args.dry_run)

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
