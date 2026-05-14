#!/usr/bin/env python3
"""Backfill: flatten ``generate_content_config`` on agent_config docs (AH-40).

Walks every document in ``agent_configs/{id}`` (global) and
``accounts/*/agent_configs/{id}`` (per-account overlays + custom agents),
hoists the nested ``generate_content_config.temperature`` and
``.max_output_tokens`` to the top level, and deletes the
``generate_content_config`` wrapper via ``firestore.DELETE_FIELD``.

Sequencing
----------
Run this script BEFORE redeploying the API/ADK to any environment that
already holds pre-AH-40 nested docs. KEN-E's API and ADK loaders use
``extra="forbid"`` (post-AH-40), so an un-flattened doc would fail
validation at read time. In a clean environment with no pre-existing
docs the script is unnecessary.

Idempotency
-----------
- No ``generate_content_config`` field present → no write.
- Flat ``temperature`` / ``max_output_tokens`` already set on the doc →
  preserve them; do not overwrite from the nested block.
- ``generate_content_config`` present → hoist any keys that aren't
  already set flat, then delete the wrapper.

Re-running on an already-flattened collection produces zero writes.

Usage
-----
    # Dry run — no writes; inspect the output
    uv run python api/scripts/flatten_agent_config_storage.py \\
        --project-id ken-e-dev --dry-run

    # Live run
    uv run python api/scripts/flatten_agent_config_storage.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

GLOBAL_COLLECTION = "agent_configs"
# Collection-group name used by Firestore for any subcollection named
# ``agent_configs`` — picks up every ``accounts/*/agent_configs`` doc in
# one query without enumerating account IDs.
COLLECTION_GROUP = "agent_configs"


# ---------------------------------------------------------------------------
# Pure helper (testable without Firestore)
# ---------------------------------------------------------------------------


def flatten_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Compute the Firestore update needed to flatten one doc.

    Returns an update dict suitable for ``doc_ref.update(...)``. An empty
    dict means the doc is already flat — no write required (idempotent
    no-op).

    The update may contain up to three keys:

    * ``"temperature"`` — hoisted from ``generate_content_config.temperature``,
      but only when no flat ``temperature`` is already present on the doc.
    * ``"max_output_tokens"`` — same rule for ``max_output_tokens``.
    * ``"generate_content_config"`` — set to ``firestore.DELETE_FIELD`` when
      the wrapper is present on the doc (always deleted post-hoist).

    Args:
        doc: The Firestore document dict (from ``snapshot.to_dict()``).

    Returns:
        Update dict. Empty when no write is needed.
    """
    gcc = doc.get("generate_content_config")
    if not gcc:
        return {}

    # Lazy import so this module is importable in unit tests without a
    # live google-cloud-firestore install path (the import is only
    # reached when the helper actually has work to do).
    from google.cloud.firestore_v1 import DELETE_FIELD

    updates: dict[str, Any] = {"generate_content_config": DELETE_FIELD}

    if isinstance(gcc, dict):
        # Hoist only when the flat field is absent. Preserves
        # overlay-precedence: if the doc already carries a flat value
        # (e.g. an admin update overlaid before backfill), the flat
        # value wins.
        if "temperature" not in doc and "temperature" in gcc:
            updates["temperature"] = gcc["temperature"]
        if "max_output_tokens" not in doc and "max_output_tokens" in gcc:
            updates["max_output_tokens"] = gcc["max_output_tokens"]

    return updates


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------


def _process_snapshot(
    snapshot: Any,
    *,
    scope: str,
    dry_run: bool,
    counts: dict[str, int],
) -> None:
    """Apply ``flatten_doc`` to one snapshot, updating Firestore (or logging)."""
    doc_id: str = snapshot.id
    doc: dict[str, Any] = snapshot.to_dict() or {}

    updates = flatten_doc(doc)

    if not updates:
        logger.debug("[%s] %r already flat — no change", scope, doc_id)
        counts["unchanged"] += 1
        return

    if dry_run:
        logger.info("[DRY RUN] [%s] would flatten %r: %s", scope, doc_id, list(updates))
        counts["would_flatten"] += 1
        return

    try:
        snapshot.reference.update(updates)
        logger.info("[%s] flattened %r: %s", scope, doc_id, list(updates))
        counts["flattened"] += 1
    except Exception as exc:
        logger.error("[%s] failed to flatten %r: %s", scope, doc_id, exc)
        counts["errors"] += 1


def migrate(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Walk globals + per-account overlays and flatten each doc.

    Args:
        project_id: GCP project ID.
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing). When ``None``
            a real client is constructed.

    Returns:
        Counts: ``flattened``, ``would_flatten``, ``unchanged``, ``errors``.
    """
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    counts: dict[str, int] = {
        "flattened": 0,
        "would_flatten": 0,
        "unchanged": 0,
        "errors": 0,
    }

    # 1) Walk the global collection.
    for snap in db.collection(GLOBAL_COLLECTION).stream():
        _process_snapshot(snap, scope="global", dry_run=dry_run, counts=counts)

    # 2) Walk every per-account ``agent_configs`` subcollection via a
    # collection-group query — no need to enumerate accounts.
    for snap in db.collection_group(COLLECTION_GROUP).stream():
        # Skip globals already counted above. Path shape for globals is
        # ``agent_configs/{id}`` (one segment before the doc); per-account
        # docs are ``accounts/{aid}/agent_configs/{id}`` (three segments).
        path = snap.reference.path.split("/")
        if len(path) <= 2:
            continue
        _process_snapshot(snap, scope="overlay", dry_run=dry_run, counts=counts)

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _configure_logging(level_str: str) -> None:
    raw_level = level_str.upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if raw_level not in valid_levels:
        raise SystemExit(
            f"Invalid --log-level {level_str!r}. "
            f"Choose from: {', '.join(sorted(valid_levels))}"
        )

    log_path = (
        f"/tmp/flatten_agent_config_storage_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logging.basicConfig(
        level=getattr(logging, raw_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger.info("Log file: %s", log_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten the legacy nested generate_content_config block on "
            "agent_configs docs (AH-40). Idempotent — re-running on a "
            "flattened collection produces zero writes."
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
        help="Show what would be flattened without writing to Firestore",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    _configure_logging(args.log_level)

    logger.info("AH-40 agent_config flatten backfill")
    logger.info("Project:  %s", args.project_id)
    logger.info("Dry run:  %s", args.dry_run)
    logger.info("-" * 60)

    counts = migrate(project_id=args.project_id, dry_run=args.dry_run)

    logger.info("-" * 60)
    if args.dry_run:
        logger.info(
            "Done (dry-run). would_flatten=%d, unchanged=%d",
            counts["would_flatten"],
            counts["unchanged"],
        )
    else:
        logger.info(
            "Done. flattened=%d, unchanged=%d, errors=%d",
            counts["flattened"],
            counts["unchanged"],
            counts["errors"],
        )

    return 1 if counts["errors"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
