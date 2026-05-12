#!/usr/bin/env python3
"""migrate_shape_d_split.py — Shape D split: organizations/{org_id}.accounts.* → accounts/{account_id} docs.

Phase 2.2 of DM-PRD-03: writes the safe side of the field-tree split.  Reads each
``organizations/{org_id}`` doc's ``accounts`` map field and merges the nested
``account_settings`` and ``funnels`` payloads into per-account ``accounts/{account_id}``
docs with an ``organization_id`` back-reference.

**Write-pass** (default): writes only to the ``accounts`` collection.  It never
modifies ``organizations/{org_id}`` documents.

**Delete-pass** (``--confirm-delete-field``): destructive follow-up step.  After the
write-pass has been run and verified in the target environment, this flag removes the
now-dead ``accounts`` map field from each ``organizations/{org_id}`` doc via
``firestore.DELETE_FIELD``.

    PREREQUISITES for ``--confirm-delete-field``:
    1. The write-pass (no flag) must have completed with zero errors.
    2. Every ``accounts/{account_id}`` doc must contain the migrated payload
       (``organization_id``, ``account_settings``, ``funnels`` matching the source).
    The delete-pass verifies this gate per-org before issuing any deletion.  If any
    account in an org's map is unverified, that org is skipped and logged — no partial
    deletion, no data loss.  Re-running after fixing the gap is safe (idempotent).

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
Write-pass: before writing each account the runner reads the destination doc.  If the
doc already has ``organization_id == <org_id>`` **and** ``account_settings`` +
``funnels`` compare equal to the source payload, the account is logged as ``skipped``
and no write is issued.

Delete-pass: an org doc whose ``accounts`` field is already absent is recorded as
``already_clean`` and skipped.

Usage
-----
  # Step 1 — write (safe, non-destructive)
  python api/scripts/migrate_shape_d_split.py --env=dev --dry-run
  python api/scripts/migrate_shape_d_split.py --env=dev

  # Step 2 — verify in dev (e.g. check summary, Firestore console, DM-45 API diff)

  # Step 3 — cut over (destructive: removes accounts.* from org docs)
  python api/scripts/migrate_shape_d_split.py --env=dev --confirm-delete-field --dry-run
  python api/scripts/migrate_shape_d_split.py --env=dev --confirm-delete-field

  # Repeat steps 1-3 for staging and production

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID  (required) — GCP project that holds the Firestore database.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Output
------
  Per-account/org records are printed to stdout as individual JSON lines.
  A ``=== JSON SUMMARY ===`` delimiter is printed, followed by an aggregate JSON block.
  All log messages go to stderr.

Exit codes
----------
  0  success (all orgs either deleted or already_clean; or write-pass completed with 0 errors)
  1  verification failed (write-pass: one or more accounts had errors;
                          delete-pass: one or more orgs were skipped due to unverified accounts)
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
from typing import Any, Literal

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


class OrgDeleteRecord(BaseModel):
    org_id: str
    action: Literal["deleted", "already_clean", "skipped_unmigrated", "would_delete"]
    account_count_in_map: int
    missing_account_ids: list[str] = []
    error: str | None = None


class MigrationSummary(BaseModel):
    # Write-pass counters
    total_orgs: int
    total_accounts: int
    copied: int
    skipped: int
    empty: int
    errors: int
    # Delete-pass counters (zero during write-pass — strict superset)
    orgs_field_deleted: int = 0
    orgs_already_clean: int = 0
    orgs_skipped_unmigrated: int = 0


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
# Delete-pass runner
# ---------------------------------------------------------------------------


def run_delete_field_pass(
    client: Any,
    *,
    dry_run: bool,
) -> MigrationSummary:
    """Remove the ``accounts`` map field from every ``organizations/{org_id}`` doc.

    This is the destructive Phase 4 step (DM-PRD-03 §5 Phase 4).  It runs as a
    separate pass, distinct from the write-pass (``run_migration``), so operators
    can verify the write-pass output before committing to deletion.

    Per-org verification gate (fail-closed)
    ----------------------------------------
    Before issuing any ``DELETE_FIELD`` on an org doc, the runner reads every
    ``accounts/{account_id}`` doc referenced in the org's ``accounts`` map and calls
    ``is_already_migrated()`` on each.  If **any** account fails this check the entire
    org is skipped with a ``skipped_unmigrated`` record — no partial deletion.

    Idempotency
    -----------
    An org doc that already has no ``accounts`` field is recorded as ``already_clean``
    and skipped silently.

    Parameters
    ----------
    client:
        An initialised ``google.cloud.firestore.Client`` instance.
    dry_run:
        When True, the runner prints what would happen but issues no ``DELETE_FIELD``
        writes.  Verified orgs are recorded as ``would_delete``.

    Returns
    -------
    MigrationSummary
        Write-pass counters are all zero; delete-pass counters reflect the run.
    """
    from google.cloud.firestore_v1 import DELETE_FIELD  # type: ignore[import]

    orgs_field_deleted = 0
    orgs_already_clean = 0
    orgs_skipped_unmigrated = 0

    try:
        for snapshot in client.collection("organizations").stream():
            org_id: str = snapshot.id
            doc_dict: dict[str, Any] = snapshot.to_dict() or {}
            accounts_map = doc_dict.get("accounts")

            # Idempotency: org already clean
            if not isinstance(accounts_map, dict) or not accounts_map:
                logger.debug("org %s: accounts field absent — already_clean", org_id)
                rec = OrgDeleteRecord(
                    org_id=org_id,
                    action="already_clean",
                    account_count_in_map=0,
                )
                print(rec.model_dump_json())
                orgs_already_clean += 1
                continue

            account_count = len(accounts_map)

            # Per-org verification gate
            missing_account_ids: list[str] = []
            for account_id, nested_payload in accounts_map.items():
                if not isinstance(nested_payload, dict):
                    nested_payload = {}
                dest_ref = client.collection("accounts").document(account_id)
                dest_snap = dest_ref.get()
                dest_data: dict[str, Any] | None = (
                    dest_snap.to_dict()
                    if (hasattr(dest_snap, "exists") and dest_snap.exists)
                    else None
                )
                if not is_already_migrated(dest_data, nested_payload, org_id):
                    missing_account_ids.append(account_id)

            if missing_account_ids:
                logger.warning(
                    "org %s: %d unverified account(s): %s — skipping field-deletion",
                    org_id,
                    len(missing_account_ids),
                    missing_account_ids,
                )
                rec = OrgDeleteRecord(
                    org_id=org_id,
                    action="skipped_unmigrated",
                    account_count_in_map=account_count,
                    missing_account_ids=missing_account_ids,
                )
                print(rec.model_dump_json())
                orgs_skipped_unmigrated += 1
                continue

            # All accounts verified — delete (or simulate)
            if dry_run:
                logger.info(
                    "org %s: verified (%d accounts); [DRY RUN] would delete accounts field",
                    org_id,
                    account_count,
                )
                rec = OrgDeleteRecord(
                    org_id=org_id,
                    action="would_delete",
                    account_count_in_map=account_count,
                )
                print(rec.model_dump_json())
                orgs_field_deleted += 1
            else:
                logger.info(
                    "org %s: verified (%d accounts); deleting accounts field",
                    org_id,
                    account_count,
                )
                org_ref = client.collection("organizations").document(org_id)
                org_ref.update({"accounts": DELETE_FIELD})
                rec = OrgDeleteRecord(
                    org_id=org_id,
                    action="deleted",
                    account_count_in_map=account_count,
                )
                print(rec.model_dump_json())
                orgs_field_deleted += 1

    except Exception as exc:
        logger.exception("Unexpected error during delete-field pass: %s", exc)
        raise

    summary = MigrationSummary(
        total_orgs=orgs_field_deleted + orgs_already_clean + orgs_skipped_unmigrated,
        total_accounts=0,
        copied=0,
        skipped=0,
        empty=0,
        errors=0,
        orgs_field_deleted=orgs_field_deleted,
        orgs_already_clean=orgs_already_clean,
        orgs_skipped_unmigrated=orgs_skipped_unmigrated,
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
            "Default (no flag): WRITES ONLY to accounts/{account_id}. "
            "Never modifies organizations docs.\n\n"
            "--confirm-delete-field: DESTRUCTIVE. Removes the accounts.* map field "
            "from organizations/{org_id} docs after verifying every account has been "
            "migrated. Run the write-pass first and verify before using this flag."
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
        help="Print what would be written/deleted without making any Firestore writes.",
    )
    parser.add_argument(
        "--confirm-delete-field",
        action="store_true",
        help=(
            "DESTRUCTIVE: remove the 'accounts' map field from every "
            "organizations/{org_id} doc via DELETE_FIELD. Runs the delete-pass "
            "only (not the write-pass). Each org is verified before deletion; "
            "any org with unverified accounts is skipped. Combine with --dry-run "
            "to preview which orgs would be cleaned."
        ),
    )
    return parser


def main() -> int:
    """Entry point.  Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args()

    project_id, database_id = _load_env()
    _validate_env_flag(args.env, project_id)

    logger.info(
        "migrate_shape_d_split: env=%s project_id=%s database_id=%s dry_run=%s confirm_delete_field=%s",
        args.env, project_id, database_id, args.dry_run,
        getattr(args, "confirm_delete_field", False),
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
        if args.confirm_delete_field:
            logger.info("Running delete-field pass (--confirm-delete-field)")
            summary = run_delete_field_pass(client, dry_run=args.dry_run)
        else:
            summary = run_migration(client, dry_run=args.dry_run)
    except Exception:
        logger.exception("Migration failed with an unexpected error")
        return EXIT_RUNTIME_ERROR

    print("\n=== JSON SUMMARY ===\n")
    print(summary.model_dump_json(indent=2))

    if args.confirm_delete_field:
        if summary.orgs_skipped_unmigrated:
            logger.error(
                "DELETE-FIELD PASS INCOMPLETE: %d org(s) skipped because not all accounts "
                "are migrated. Re-run the write-pass (no flag) and retry.",
                summary.orgs_skipped_unmigrated,
            )
            return EXIT_VERIFICATION_FAILED
        return EXIT_SUCCESS

    # Write-pass exit logic
    if summary.errors:
        logger.error(
            "MIGRATION COMPLETED WITH %d ERROR(S) — %d/%d accounts failed; "
            "DO NOT run the destructive DELETE_FIELD step (--confirm-delete-field) until "
            "every account is copied. Re-run this script to retry the failed accounts.",
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
