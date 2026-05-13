#!/usr/bin/env python3
"""Backfill ``title`` and normalise ``name`` on existing ``agent_configs`` docs.

Sweeps both:
* ``agent_configs/{config_id}`` — global agent configs
* ``accounts/{account_id}/agent_configs/{config_id}`` — per-account overlays
  and custom agents

Identity model after this migration:
* ``config_id`` (Firestore document ID) — the immutable identifier.
* ``title`` — role description ("Business Researcher"). User-editable.
* ``name`` — human name ("Dave"). Optional, user-editable.

Before this migration, a single ``name`` field on the document held a
snake_case string mirroring ``config_id`` (e.g., ``"ken_e_chatbot"``). The
factory stripped that field via ``_STORAGE_INTERNAL_FIELDS``; it was
storage-only. This script:

1. If ``title`` is already set on the doc, leaves it alone.
2. Otherwise derives ``title`` from the legacy ``name`` (or, when ``name``
   is missing, from the ``config_id``) by replacing underscores with spaces
   and Title-Casing the result.
3. If the legacy ``name`` looks like a snake_case config_id pattern
   (``^[a-z][a-z0-9_]*$``), sets ``name`` to ``None`` — admins fill in a
   human name later via the UI.
4. If the legacy ``name`` contains spaces or uppercase letters, treats it as
   a human-set value and preserves it.

The script is idempotent: a doc that already has a non-empty ``title`` and a
non-snake-case ``name`` (or null name) is unchanged.

Usage
-----
    # Dry run — no writes; inspect the output
    uv run python api/scripts/migrate_agent_config_title.py \\
        --project-id ken-e-dev --dry-run

    # Live run (idempotent)
    uv run python api/scripts/migrate_agent_config_title.py \\
        --project-id ken-e-dev
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from typing import Any

logger = logging.getLogger(__name__)

GLOBAL_COLLECTION = "agent_configs"
ACCOUNTS_COLLECTION = "accounts"
ACCOUNT_AGENT_CONFIGS_SUBCOLLECTION = "agent_configs"

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# ---------------------------------------------------------------------------
# Pure helpers (testable without Firestore)
# ---------------------------------------------------------------------------


def _title_case_from_identifier(identifier: str) -> str:
    """Turn ``business_researcher`` into ``Business Researcher``.

    Replaces underscores with spaces and capitalises the first letter of each
    word. Used as the fallback title when neither the legacy ``name`` field
    nor the explicit ``title`` field is set.
    """
    cleaned = identifier.replace("_", " ").strip()
    return cleaned.title() if cleaned else identifier


def _looks_like_snake_case_id(value: str) -> bool:
    """True if ``value`` matches the snake_case config_id pattern.

    Used to distinguish legacy storage-only ``name`` values (which mirror
    the config_id) from human-set ``name`` values that should be preserved.
    """
    return bool(_SNAKE_CASE_RE.match(value))


def compute_patch(
    config_id: str,
    doc: dict[str, Any],
) -> dict[str, Any]:
    """Return the field patch needed to bring ``doc`` to the new identity model.

    Empty dict ⇒ doc is already correct (idempotent no-op).

    Strategy:
      * ``title`` defaults to ``TitleCase(name OR config_id)`` if missing.
      * ``name`` is cleared to ``None`` if its current value looks like a
        snake_case config_id (legacy storage form); otherwise preserved.
    """
    patch: dict[str, Any] = {}

    current_title = doc.get("title")
    current_name = doc.get("name")

    # Pick the source for the new title: the existing name (if any) first,
    # falling back to the config_id. If the existing name doesn't look like
    # a config_id (e.g., already a human name like "Dave"), we still derive
    # a title from the config_id to avoid stamping "Dave" into the title slot.
    if not current_title:
        if isinstance(current_name, str) and current_name and _looks_like_snake_case_id(
            current_name
        ):
            patch["title"] = _title_case_from_identifier(current_name)
        else:
            patch["title"] = _title_case_from_identifier(config_id)

    if isinstance(current_name, str) and current_name:
        if _looks_like_snake_case_id(current_name):
            # Legacy storage form — clear it so the new "name" slot is
            # empty for the admin to fill in.
            patch["name"] = None
        # else: human-set name, preserve it.

    return patch


# ---------------------------------------------------------------------------
# Core migration function
# ---------------------------------------------------------------------------


def _migrate_collection(
    *,
    db: Any,
    docs_path: list[str],
    dry_run: bool,
    counts: dict[str, int],
    failed_ids: list[str],
) -> None:
    """Apply the migration to a single Firestore collection path.

    ``docs_path`` is the sequence of segments (e.g., ``["agent_configs"]`` or
    ``["accounts", "acc_abc", "agent_configs"]``). The function streams every
    document in that collection and applies ``compute_patch``.
    """
    collection: Any = db
    for i, segment in enumerate(docs_path):
        if i % 2 == 0:
            collection = collection.collection(segment)
        else:
            collection = collection.document(segment)
    # ``collection`` is now a CollectionReference (even-length path).

    for snapshot in collection.stream():
        doc_id: str = snapshot.id
        doc: dict[str, Any] = snapshot.to_dict() or {}
        full_path = "/".join([*docs_path, doc_id])

        patch = compute_patch(doc_id, doc)

        if not patch:
            logger.debug("Doc %r already migrated — no change", full_path)
            counts["unchanged"] += 1
            continue

        if dry_run:
            logger.info("[DRY RUN] Would patch %s: %s", full_path, patch)
            counts["would_patch"] += 1
            continue

        try:
            collection.document(doc_id).update(patch)
            logger.info("Patched %s: %s", full_path, patch)
            counts["patched"] += 1
        except Exception as exc:
            logger.error("Failed to patch %s: %s", full_path, exc)
            counts["errors"] += 1
            failed_ids.append(full_path)


def migrate(
    project_id: str,
    dry_run: bool,
    *,
    db: Any | None = None,
) -> dict[str, int]:
    """Run the migration over global + per-account agent_configs collections.

    Args:
        project_id: GCP project ID (e.g. ``"ken-e-dev"``).
        dry_run: When ``True``, log what would change but issue no writes.
        db: Optional pre-built Firestore client (for testing).

    Returns:
        A dict with integer counts for ``patched``, ``would_patch``,
        ``unchanged``, and ``errors``.
    """
    if db is None:
        from google.cloud import firestore

        db = firestore.Client(project=project_id)

    counts: dict[str, int] = {
        "patched": 0,
        "would_patch": 0,
        "unchanged": 0,
        "errors": 0,
    }
    failed_paths: list[str] = []

    # Global agent_configs
    logger.info("Scanning global collection: %s", GLOBAL_COLLECTION)
    _migrate_collection(
        db=db,
        docs_path=[GLOBAL_COLLECTION],
        dry_run=dry_run,
        counts=counts,
        failed_ids=failed_paths,
    )

    # Per-account overlays and custom agents
    logger.info("Scanning per-account overlays under: %s/*", ACCOUNTS_COLLECTION)
    for account_ref in db.collection(ACCOUNTS_COLLECTION).list_documents():
        account_id = account_ref.id
        _migrate_collection(
            db=db,
            docs_path=[
                ACCOUNTS_COLLECTION,
                account_id,
                ACCOUNT_AGENT_CONFIGS_SUBCOLLECTION,
            ],
            dry_run=dry_run,
            counts=counts,
            failed_ids=failed_paths,
        )

    if failed_paths:
        logger.error(
            "Migration incomplete — %d document(s) failed to patch: %s",
            len(failed_paths),
            failed_paths,
        )

    return counts


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill 'title' on agent_configs Firestore docs and clear "
            "legacy snake_case 'name' values. Sweeps both the global "
            "agent_configs collection and every accounts/*/agent_configs "
            "subcollection. Idempotent."
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

    logger.info("agent_configs title backfill migration")
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
