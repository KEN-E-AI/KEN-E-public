#!/usr/bin/env python3
"""migrate_shape_d_split.py — Shape D split: organizations/{org_id}.accounts.* → accounts/{account_id} docs.

Phase 2.2 of DM-PRD-03: writes the safe side of the field-tree split.  Reads each
``organizations/{org_id}`` doc's ``accounts`` map field and merges the nested
``account_settings`` and ``funnels`` payloads into per-account ``accounts/{account_id}``
docs with an ``organization_id`` back-reference.

**This script writes only to the ``accounts`` collection.  It never modifies
``organizations/{org_id}`` documents.**  The destructive ``DELETE_FIELD`` step on the
org doc is owned by the companion script (DM-44) and runs only after this write-side
has been verified.

Storage style
-------------
Style A (map fields on ``accounts/{account_id}``) per DM-38.  The payload written to
each account doc is::

    {
        "organization_id":      <org_id: str>,
        "account_settings":     <dict>,
        "funnels":              <dict>,
        "shape_d_migrated_at":  <ISO-8601 UTC string>,
        "updated_at":           <ISO-8601 UTC string>,
    }

Written via ``.set(..., merge=True)`` so any unrelated fields already on the destination
doc (from other migrations or feature code) are preserved.

Idempotency
-----------
Before writing each account, the runner reads the destination doc.  If the doc already
has ``organization_id == <org_id>`` **and** ``account_settings`` + ``funnels`` compare
equal to the source payload, the account is logged as ``skipped`` and no write is issued.

Usage
-----
  python api/scripts/migrate_shape_d_split.py --env=dev --dry-run
  python api/scripts/migrate_shape_d_split.py --env=dev
  python api/scripts/migrate_shape_d_split.py --env=staging
  python api/scripts/migrate_shape_d_split.py --env=production

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID  (required) — GCP project that holds the Firestore database.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Output
------
  Per-account records are printed to stdout as individual JSON lines.
  A ``=== JSON SUMMARY ===`` delimiter is printed, followed by an aggregate JSON block.
  All log messages go to stderr.

Exit codes
----------
  0  success
  1  verification failed (reserved for future use)
  2  usage error (missing/mismatched env var or flag)
  3  runtime error (unexpected exception)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_RUNTIME_ERROR = 3

# ---------------------------------------------------------------------------
# Valid environments and the project-id pattern they imply
# ---------------------------------------------------------------------------
_VALID_ENVS = ("dev", "staging", "production")
_ENV_PROJECT_PATTERNS: dict[str, str] = {
    "dev": "ken-e-dev",
    "staging": "ken-e-staging",
    "production": "ken-e-production",
}


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------


class AccountRecord(BaseModel):
    org_id: str
    account_id: str
    action: str  # "copied" | "skipped" | "empty" | "error"
    source_byte_size: int
    before_dest_present: bool
    after_dest_present: bool
    shape_d_migrated_at: str | None = None
    error: str | None = None


class MigrationSummary(BaseModel):
    total_orgs: int
    total_accounts: int
    copied: int
    skipped: int
    empty: int
    errors: int


# ---------------------------------------------------------------------------
# Pure-logic helpers (no Firestore dependency)
# ---------------------------------------------------------------------------


def extract_account_payload(
    nested: dict[str, Any],
    org_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Build the Style-A write-payload for a single account.

    Parameters
    ----------
    nested:
        The per-account value from the org doc's ``accounts`` map field
        (i.e. ``org_doc["accounts"][account_id]``).
    org_id:
        The Firestore document ID of the parent organization.
    now:
        UTC timestamp to use for ``shape_d_migrated_at`` and ``updated_at``.

    Returns
    -------
    dict
        A new dict containing ``organization_id``, ``account_settings``,
        ``funnels``, ``shape_d_migrated_at``, and ``updated_at``.  The
        source ``nested`` dict is not mutated.
    """
    iso_now = now.isoformat()
    account_settings = nested.get("account_settings")
    if not isinstance(account_settings, dict):
        account_settings = {}
    funnels = nested.get("funnels")
    if not isinstance(funnels, dict):
        funnels = {}
    return {
        "organization_id": org_id,
        "account_settings": account_settings,
        "funnels": funnels,
        "shape_d_migrated_at": iso_now,
        "updated_at": iso_now,
    }


def is_already_migrated(
    dest: dict[str, Any] | None,
    source_nested: dict[str, Any],
    org_id: str,
) -> bool:
    """Return True iff the destination doc already contains an up-to-date migration.

    Conditions (all must hold):
    - ``dest`` is non-None (destination doc exists).
    - ``dest["organization_id"] == org_id``.
    - ``dest.get("account_settings")`` equals ``source_nested.get("account_settings")``.
    - ``dest.get("funnels")`` equals ``source_nested.get("funnels")``.

    The ``shape_d_migrated_at`` marker is a secondary signal: its presence implies
    a prior run wrote successfully, but the canonical idempotency gate is the content
    equality check above (the marker alone could exist from a dry-run stub or a
    partial write).
    """
    if dest is None:
        return False
    if dest.get("organization_id") != org_id:
        return False

    src_settings = source_nested.get("account_settings")
    if not isinstance(src_settings, dict):
        src_settings = {}
    dst_settings = dest.get("account_settings")
    if not isinstance(dst_settings, dict):
        dst_settings = {}
    if src_settings != dst_settings:
        return False

    src_funnels = source_nested.get("funnels")
    if not isinstance(src_funnels, dict):
        src_funnels = {}
    dst_funnels = dest.get("funnels")
    if not isinstance(dst_funnels, dict):
        dst_funnels = {}
    return src_funnels == dst_funnels


def approx_bytes(d: dict[str, Any]) -> int:
    """Approximate UTF-8 byte size of a dict via JSON serialisation."""
    return len(json.dumps(d, default=str).encode("utf-8"))


# ---------------------------------------------------------------------------
# Firestore wiring
# ---------------------------------------------------------------------------


def _iter_org_accounts(
    client: Any,
) -> Generator[tuple[str, str, dict[str, Any]], None, None]:
    """Stream the ``organizations`` collection, yielding per-account tuples.

    Yields
    ------
    tuple[str, str, dict]
        ``(org_id, account_id, nested_payload)`` for every entry in every org
        doc's ``accounts`` map field.  Org docs with a missing, empty, or
        non-dict ``accounts`` field are skipped (logged at DEBUG level).
    """
    for snapshot in client.collection("organizations").stream():
        org_id: str = snapshot.id
        doc_dict: dict[str, Any] = snapshot.to_dict() or {}
        accounts_map = doc_dict.get("accounts")
        if not isinstance(accounts_map, dict) or not accounts_map:
            logger.debug("org %s: no accounts map — skipping", org_id)
            continue
        for account_id, nested in accounts_map.items():
            if not account_id or "/" in account_id or account_id in (".", ".."):
                logger.error(
                    "org %s: account_id %r is not a valid Firestore document ID — skipping",
                    org_id,
                    account_id,
                )
                continue
            if not isinstance(nested, dict):
                nested = {}
            yield org_id, account_id, nested


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------


def _load_env() -> tuple[str, str]:
    """Read and validate required environment variables.

    Returns
    -------
    tuple[str, str]
        ``(project_id, database_id)``

    Raises
    ------
    SystemExit(2)
        If ``GOOGLE_CLOUD_PROJECT_ID`` is not set.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
    if not project_id:
        print(
            "ERROR: GOOGLE_CLOUD_PROJECT_ID environment variable is not set.\n"
            "Set it before running this script, e.g.:\n"
            "  export GOOGLE_CLOUD_PROJECT_ID=ken-e-dev",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")
    return project_id, database_id


def _validate_env_flag(env: str, project_id: str) -> None:
    """Verify that ``--env`` matches the ``GOOGLE_CLOUD_PROJECT_ID`` pattern.

    Raises
    ------
    SystemExit(2)
        If the ``--env`` value does not match the expected project-id pattern.
    """
    expected = _ENV_PROJECT_PATTERNS[env]
    if project_id != expected:
        print(
            f"ERROR: --env={env} expects GOOGLE_CLOUD_PROJECT_ID={expected!r},\n"
            f"       but GOOGLE_CLOUD_PROJECT_ID is currently {project_id!r}.\n"
            f"Check that you have sourced the correct environment before running.",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)


# ---------------------------------------------------------------------------
# Main migration runner
# ---------------------------------------------------------------------------


def run_migration(
    client: Any,
    *,
    dry_run: bool,
) -> MigrationSummary:
    """Execute (or simulate) the Shape D split migration.

    Parameters
    ----------
    client:
        An initialised ``google.cloud.firestore.Client`` instance.
    dry_run:
        When True, the runner prints what would happen but performs no writes.

    Returns
    -------
    MigrationSummary
        Aggregate counts across all orgs and accounts.
    """
    now = datetime.now(tz=timezone.utc)

    total_orgs_seen: set[str] = set()
    records: list[AccountRecord] = []

    try:
        for org_id, account_id, nested in _iter_org_accounts(client):
            total_orgs_seen.add(org_id)

            src_byte_size = approx_bytes(nested)
            is_empty = not nested

            # Read current destination doc for idempotency check
            dest_ref = client.collection("accounts").document(account_id)
            try:
                dest_snap = dest_ref.get()
                before_present = dest_snap.exists if hasattr(dest_snap, "exists") else bool(dest_snap)
                dest_data: dict[str, Any] | None = (
                    dest_snap.to_dict() if (hasattr(dest_snap, "exists") and dest_snap.exists) else None
                )
            except Exception as exc:
                logger.error(
                    "org %s account %s: failed to read destination doc: %s",
                    org_id, account_id, exc,
                )
                err_record = AccountRecord(
                    org_id=org_id,
                    account_id=account_id,
                    action="error",
                    source_byte_size=src_byte_size,
                    before_dest_present=False,
                    after_dest_present=False,
                    error=str(exc),
                )
                records.append(err_record)
                print(err_record.model_dump_json())
                continue

            # Warn if a prior migration attributed this account to a different org
            if dest_data and dest_data.get("organization_id") and dest_data.get("organization_id") != org_id:
                logger.warning(
                    "org %s account %s: destination doc has organization_id=%r — will overwrite (cross-org collision)",
                    org_id,
                    account_id,
                    dest_data.get("organization_id"),
                )

            if is_empty:
                action = "empty"
                migrated_at = None
                logger.info("org %s account %s: EMPTY — no payload to migrate", org_id, account_id)
            elif is_already_migrated(dest_data, nested, org_id):
                action = "skipped"
                migrated_at = dest_data.get("shape_d_migrated_at") if dest_data else None  # type: ignore[union-attr]
                logger.info("org %s account %s: already migrated (skip)", org_id, account_id)
            else:
                action = "copied" if not dry_run else "WOULD COPY"
                payload = extract_account_payload(nested, org_id, now)
                migrated_at = payload["shape_d_migrated_at"]
                if dry_run:
                    print(
                        f"[DRY RUN] org={org_id} account={account_id} action=WOULD COPY "
                        f"source_bytes={src_byte_size}"
                    )
                else:
                    try:
                        dest_ref.set(payload, merge=True)
                        logger.info(
                            "org %s account %s: copied (%d source bytes)",
                            org_id, account_id, src_byte_size,
                        )
                    except Exception as exc:
                        logger.error(
                            "org %s account %s: write failed: %s",
                            org_id, account_id, exc,
                        )
                        err_record = AccountRecord(
                            org_id=org_id,
                            account_id=account_id,
                            action="error",
                            source_byte_size=src_byte_size,
                            before_dest_present=before_present,
                            after_dest_present=before_present,
                            error=str(exc),
                        )
                        records.append(err_record)
                        print(err_record.model_dump_json())
                        continue

            # after a successful set(), the doc is guaranteed to exist; no re-read needed
            after_present = before_present if (dry_run or action in ("skipped", "empty")) else True

            record = AccountRecord(
                org_id=org_id,
                account_id=account_id,
                action=action,
                source_byte_size=src_byte_size,
                before_dest_present=before_present,
                after_dest_present=after_present,
                shape_d_migrated_at=migrated_at,
            )
            records.append(record)
            print(record.model_dump_json())

    except Exception as exc:
        logger.exception("Unexpected error while streaming org documents: %s", exc)
        raise

    summary = MigrationSummary(
        total_orgs=len(total_orgs_seen),
        total_accounts=len(records),
        copied=sum(1 for r in records if r.action in ("copied", "WOULD COPY")),
        skipped=sum(1 for r in records if r.action == "skipped"),
        empty=sum(1 for r in records if r.action == "empty"),
        errors=sum(1 for r in records if r.action == "error"),
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate_shape_d_split",
        description=(
            "Shape D split: copy organizations/{org_id}.accounts.* fields into "
            "per-account accounts/{account_id} docs (Style A, map fields).\n\n"
            "WRITES ONLY to accounts/{account_id}. Never modifies organizations docs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        choices=_VALID_ENVS,
        required=True,
        help=(
            "Target environment. Must match GOOGLE_CLOUD_PROJECT_ID (e.g. "
            "--env=dev requires GOOGLE_CLOUD_PROJECT_ID=ken-e-dev)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without making any Firestore writes.",
    )
    return parser


def main() -> int:
    """Entry point.  Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args()

    project_id, database_id = _load_env()
    _validate_env_flag(args.env, project_id)

    logger.info(
        "migrate_shape_d_split: env=%s project_id=%s database_id=%s dry_run=%s",
        args.env, project_id, database_id, args.dry_run,
    )
    if args.dry_run:
        logger.info("DRY RUN — no writes will be made")

    try:
        from google.cloud import firestore  # type: ignore[import]

        client = firestore.Client(project=project_id, database=database_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialise Firestore client: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    try:
        summary = run_migration(client, dry_run=args.dry_run)
    except Exception:
        logger.exception("Migration failed with an unexpected error")
        return EXIT_RUNTIME_ERROR

    print("\n=== JSON SUMMARY ===\n")
    print(summary.model_dump_json(indent=2))

    if summary.errors:
        logger.error(
            "MIGRATION COMPLETED WITH %d ERROR(S) — %d/%d accounts failed; "
            "DO NOT run the destructive DELETE_FIELD step (DM-44) until every account is copied. "
            "Re-run this script to retry the failed accounts.",
            summary.errors, summary.errors, summary.total_accounts,
        )
        return EXIT_VERIFICATION_FAILED

    return EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("Unexpected top-level error")
        sys.exit(EXIT_RUNTIME_ERROR)
