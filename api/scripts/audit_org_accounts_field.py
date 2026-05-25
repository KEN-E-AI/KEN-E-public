#!/usr/bin/env python3
"""audit_org_accounts_field.py — Audit (and optionally delete) the dead ``accounts`` field
from ``organizations/{org_id}`` Firestore docs.

Background
----------
DM-61 Phase-6 staging verification (check #8) surfaced 3 staging org docs that carried
a dead, pre-Shape-D ``accounts`` **list** of denormalized account objects.  The app reads
accounts from a Neo4j Cypher ``collect(acc)`` call (``routers/organizations.py:218/353``),
never from this Firestore field, so the list is pure legacy residue.  Ken's 2026-05-23
decision (DM-61 comment) confirmed it safe to delete.  This script encapsulates the
audit + cleanup operation so it can be run reproducibly against any environment.

Modes
-----
**Audit-only (default, read-only):** scans every ``organizations/{org_id}`` doc and
reports whether it carries an ``accounts`` field, along with the captured account IDs
(or document count if the value is a list of objects rather than IDs).  Exits 0 if no
offenders; exits 1 if any offender is found.

**Delete-pass (``--confirm-delete``):** re-audits and then issues
``update({"accounts": DELETE_FIELD})`` on every offender.  Idempotent: an org doc that
already has no ``accounts`` field is reported as ``already_clean``.  Exits 0 if all
offenders were deleted (or were already clean); exits 1 on any error.

Environment
-----------
  GOOGLE_CLOUD_PROJECT_ID  (required) — target GCP project.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Usage
-----
  # Audit-only (read-only smoke test)
  GOOGLE_CLOUD_PROJECT_ID=ken-e-dev \\
    python api/scripts/audit_org_accounts_field.py --env=dev

  # Audit staging
  GOOGLE_CLOUD_PROJECT_ID=ken-e-staging \\
    python api/scripts/audit_org_accounts_field.py --env=staging

  # Delete residue from staging
  GOOGLE_CLOUD_PROJECT_ID=ken-e-staging \\
    python api/scripts/audit_org_accounts_field.py --env=staging --confirm-delete

  # Preview delete (dry-run)
  GOOGLE_CLOUD_PROJECT_ID=ken-e-staging \\
    python api/scripts/audit_org_accounts_field.py --env=staging --confirm-delete --dry-run

Exit codes
----------
  0  success (audit-only: no offenders found; delete-pass: all offenders deleted or already_clean)
  1  failure  (audit-only: offenders found; delete-pass: one or more errors)
  2  usage error (missing / mismatched env vars or flags)
  3  runtime error (unexpected exception)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
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
# Valid environments and expected project-id mapping
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


class OrgAuditRecord(BaseModel):
    """Per-org audit record emitted to stdout as a JSON line."""

    org_id: str
    has_accounts_field: bool
    field_type: str | None = None  # "list" | "dict" | "other" | None
    account_ids: list[str] = []  # extracted IDs when field is a list/dict of strings
    item_count: int = 0  # total items when field_type is not a plain ID list
    action: Literal["clean", "found", "deleted", "already_clean", "error"] = "clean"
    error: str | None = None


class AuditSummary(BaseModel):
    total_orgs: int
    orgs_with_accounts_field: int
    orgs_already_clean: int
    orgs_deleted: int
    orgs_errors: int
    pass_fail: Literal["PASS", "FAIL"]


# ---------------------------------------------------------------------------
# Pure-logic helpers (no Firestore dependency — testable in unit tests)
# ---------------------------------------------------------------------------


def build_org_audit_record(org_id: str, doc_dict: dict[str, Any]) -> OrgAuditRecord:
    """Parse a Firestore org-doc dict into an :class:`OrgAuditRecord`.

    Handles the three production shapes seen in staging:
    - A list of string account IDs: ``["acc_abc", "acc_def"]``
    - A list of account-object dicts: ``[{"account_id": "acc_abc", ...}, ...]``
    - A dict (the Shape D map shape): ``{"acc_abc": {...}, ...}``

    Any other truthy value is captured as type ``"other"`` with ``item_count=1``.
    If the ``accounts`` field is absent the record has ``has_accounts_field=False``.
    """
    if "accounts" not in doc_dict:
        return OrgAuditRecord(org_id=org_id, has_accounts_field=False, action="clean")

    raw = doc_dict["accounts"]

    if isinstance(raw, list):
        # Extract string IDs where possible; objects are counted but not ID-extracted.
        extracted_ids: list[str] = []
        for item in raw:
            if isinstance(item, str):
                extracted_ids.append(item)
        return OrgAuditRecord(
            org_id=org_id,
            has_accounts_field=True,
            field_type="list",
            account_ids=extracted_ids,
            item_count=len(raw),
            action="found",
        )

    if isinstance(raw, dict):
        return OrgAuditRecord(
            org_id=org_id,
            has_accounts_field=True,
            field_type="dict",
            account_ids=list(raw.keys()),
            item_count=len(raw),
            action="found",
        )

    return OrgAuditRecord(
        org_id=org_id,
        has_accounts_field=True,
        field_type="other",
        account_ids=[],
        item_count=1,
        action="found",
    )


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
            "  export GOOGLE_CLOUD_PROJECT_ID=ken-e-staging",
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
# Main runners
# ---------------------------------------------------------------------------


def run_audit(client: Any, *, dry_run: bool, confirm_delete: bool) -> AuditSummary:
    """Stream all org docs, audit for ``accounts`` field, optionally delete.

    Parameters
    ----------
    client:
        An initialised ``google.cloud.firestore.Client``.
    dry_run:
        When True (with ``confirm_delete=True``), preview what would be deleted
        without issuing any writes.
    confirm_delete:
        When True, issue ``DELETE_FIELD`` on every offender doc.

    Returns
    -------
    AuditSummary
        Aggregate counts across all org docs.
    """
    if confirm_delete:
        from google.cloud.firestore_v1 import DELETE_FIELD  # type: ignore[import]

    total_orgs = 0
    orgs_with_accounts_field = 0
    orgs_already_clean = 0
    orgs_deleted = 0
    orgs_errors = 0

    for snapshot in client.collection("organizations").stream():
        total_orgs += 1
        org_id: str = snapshot.id
        doc_dict: dict[str, Any] = snapshot.to_dict() or {}

        record = build_org_audit_record(org_id, doc_dict)

        if not record.has_accounts_field:
            if confirm_delete:
                record.action = "already_clean"
                orgs_already_clean += 1
            # audit-only mode: already clean — no output needed for clean orgs to keep output terse
            logger.debug("org %s: no accounts field — clean", org_id)
            print(record.model_dump_json())
            continue

        orgs_with_accounts_field += 1
        logger.info(
            "org %s: has_accounts_field=True type=%s item_count=%d account_ids=%s",
            org_id,
            record.field_type,
            record.item_count,
            record.account_ids,
        )

        if not confirm_delete:
            # Audit-only — report and continue
            print(record.model_dump_json())
            continue

        # Delete-pass
        if dry_run:
            record.action = "found"
            logger.info("org %s: [DRY RUN] would delete accounts field", org_id)
            print(record.model_dump_json())
            continue

        org_ref = client.collection("organizations").document(org_id)
        try:
            org_ref.update({"accounts": DELETE_FIELD})
            record.action = "deleted"
            orgs_deleted += 1
            logger.info("org %s: accounts field deleted", org_id)
        except Exception as exc:
            record.action = "error"
            record.error = str(exc)
            orgs_errors += 1
            logger.error("org %s: failed to delete accounts field: %s", org_id, exc)

        print(record.model_dump_json())

    if confirm_delete:
        pass_fail: Literal["PASS", "FAIL"] = "PASS" if orgs_errors == 0 else "FAIL"
    else:
        pass_fail = "PASS" if orgs_with_accounts_field == 0 else "FAIL"

    return AuditSummary(
        total_orgs=total_orgs,
        orgs_with_accounts_field=orgs_with_accounts_field,
        orgs_already_clean=orgs_already_clean,
        orgs_deleted=orgs_deleted,
        orgs_errors=orgs_errors,
        pass_fail=pass_fail,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_org_accounts_field",
        description=(
            "Audit organizations/{org_id} Firestore docs for a dead pre-Shape-D\n"
            "`accounts` field and optionally delete it.\n\n"
            "Default (no --confirm-delete): READ-ONLY. Reports every org that has\n"
            "an accounts field; exits 1 if any offender is found, 0 if clean.\n\n"
            "--confirm-delete: DESTRUCTIVE. Issues DELETE_FIELD on every offender.\n"
            "Combine with --dry-run to preview which orgs would be affected.\n\n"
            "The --env flag must match GOOGLE_CLOUD_PROJECT_ID (safety guard):\n"
            "  --env=dev         → GOOGLE_CLOUD_PROJECT_ID=ken-e-dev\n"
            "  --env=staging     → GOOGLE_CLOUD_PROJECT_ID=ken-e-staging\n"
            "  --env=production  → GOOGLE_CLOUD_PROJECT_ID=ken-e-production"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        choices=_VALID_ENVS,
        required=True,
        help="Target environment. Must match GOOGLE_CLOUD_PROJECT_ID.",
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help=(
            "DESTRUCTIVE: delete the `accounts` field from every offending org doc. "
            "Idempotent: orgs without the field are skipped (already_clean). "
            "Combine with --dry-run to preview."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Preview what would happen without making any Firestore writes. "
            "Only meaningful with --confirm-delete."
        ),
    )
    return parser


def main() -> int:
    """Entry point. Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args()

    if args.dry_run and not args.confirm_delete:
        print(
            "WARNING: --dry-run has no effect without --confirm-delete "
            "(audit-only mode is already read-only).",
            file=sys.stderr,
        )

    project_id, database_id = _load_env()
    _validate_env_flag(args.env, project_id)

    logger.info(
        "audit_org_accounts_field: env=%s project_id=%s database_id=%s "
        "confirm_delete=%s dry_run=%s",
        args.env,
        project_id,
        database_id,
        args.confirm_delete,
        args.dry_run,
    )

    try:
        from google.cloud import firestore  # type: ignore[import]

        client = firestore.Client(project=project_id, database=database_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialise Firestore client: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    try:
        summary = run_audit(
            client, dry_run=args.dry_run, confirm_delete=args.confirm_delete
        )
    except Exception:
        logger.exception("Unexpected error during audit run")
        return EXIT_RUNTIME_ERROR

    print("\n=== JSON SUMMARY ===\n")
    print(summary.model_dump_json(indent=2))

    if summary.pass_fail == "PASS":
        if args.confirm_delete:
            if args.dry_run:
                print(
                    f"\n[DRY RUN] Would delete accounts field from "
                    f"{summary.orgs_with_accounts_field} org(s).",
                    file=sys.stderr,
                )
            else:
                print(
                    f"\nPASS: accounts field deleted from "
                    f"{summary.orgs_deleted} org(s); "
                    f"{summary.orgs_already_clean} already clean.",
                    file=sys.stderr,
                )
        else:
            print(
                "\nPASS: no org doc has an accounts field",
                file=sys.stderr,
            )
        return EXIT_SUCCESS

    if args.confirm_delete:
        logger.error(
            "DELETE PASS COMPLETED WITH %d ERROR(S) — re-run to retry failed orgs.",
            summary.orgs_errors,
        )
    else:
        logger.error(
            "AUDIT FAILED: %d org(s) carry a dead accounts field. "
            "Re-run with --confirm-delete to remove them.",
            summary.orgs_with_accounts_field,
        )
    return EXIT_VERIFICATION_FAILED


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("Unexpected top-level error")
        sys.exit(EXIT_RUNTIME_ERROR)
