"""GCS artifact blob orphan reconciliation job for KEN-E chat.

Reconciles GCS artifact blobs against ChatArtifactIndex Firestore documents.
Two orphan classes are detected:

  missing_metadata — a side-table row for the session exists, but no artifact
                     doc exists at the expected Firestore path.  Caused by a
                     failed Firestore write after GCS save, or lint-rule bypass.
                     Report only; ops manually adopts or deletes the orphan blob.

  missing_session  — no chat_sessions side-table row matches the session_id
                     encoded in the blob path.  Caused by a session that was
                     never written to Firestore (data-integrity anomaly).
                     Report only; ops investigates.

Both classes are reported via a single pageable ops alert per class (up to
_MAX_SAMPLE_PATHS sample paths, plus total_count).  No GCS or Firestore
mutations are made — this is a report-only scan.

Exit codes:
  0 — success (errored == 0)
  1 — verification failed (errored > 0)
  2 — usage error (bad args / missing env)
  3 — runtime error (unexpected exception)

The chat_v2_enabled feature flag does NOT gate this script.
Cloud Scheduler binding (05:30 UTC daily) is configured by a separate change.

Usage:
    python -m kene_api.chat.artifact_orphan_scan [--dry-run] [--account-id ID]
                                                 [--limit N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from google.cloud.firestore_v1 import FieldFilter

# ---------------------------------------------------------------------------
# Optional Weave instrumentation
# ---------------------------------------------------------------------------
try:
    import weave  # type: ignore[import-untyped]

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False

from shared.structured_logging import (
    configure_logging,
    get_structured_logger,
    log_context,
)

from .artifacts import _artifact_id, _resolve_bucket, parse_gcs_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_NAME = "ken_e_chatbot"
_MAX_SAMPLE_PATHS = 20

EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_RUNTIME_ERROR = 3

_FIRESTORE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,255}$")

# Explicit bucket override — set via ARTIFACT_GCS_BUCKET env var in production
# to avoid deriving the bucket name from the ENVIRONMENT variable, which is
# unvalidated and could redirect the scan to the wrong GCS bucket if misconfigured.
_ARTIFACT_GCS_BUCKET: str = os.environ.get("ARTIFACT_GCS_BUCKET", "")

# Orphan classification constants
CLASS_MISSING_METADATA = "missing_metadata"
CLASS_MISSING_SESSION = "missing_session"
CLASS_ALL_CLEAN = "all_clean"

logger = get_structured_logger(__name__)


# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------


def _load_env() -> tuple[str, str]:
    """Return (project_id, database_id) from environment variables."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if not project_id:
        print(
            "ERROR: GOOGLE_CLOUD_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")
    return project_id, database_id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile GCS artifact blobs against ChatArtifactIndex Firestore docs. "
            "Reports orphan blobs without making any GCS or Firestore mutations."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "No-op marker: this script is report-only and never mutates state. "
            "Flag is accepted for operational consistency and future use."
        ),
    )
    parser.add_argument(
        "--account-id",
        default=None,
        metavar="ACCOUNT_ID",
        help="Limit scan to blobs belonging to a single account.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap the total number of GCS blobs enumerated (useful for targeted scans).",
    )
    return parser


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _classify_blob(
    account_id: str | None,
    artifact_doc_exists: bool,
) -> str:
    """Classify one GCS blob based on its Firestore state.

    Args:
        account_id: Resolved account_id from the chat_sessions side-table,
            or None if no side-table row was found for the blob's session_id.
        artifact_doc_exists: Whether the ChatArtifactIndex doc exists in
            Firestore at the expected path.

    Returns:
        One of CLASS_MISSING_SESSION, CLASS_MISSING_METADATA, CLASS_ALL_CLEAN.
    """
    if account_id is None:
        return CLASS_MISSING_SESSION
    if not artifact_doc_exists:
        return CLASS_MISSING_METADATA
    return CLASS_ALL_CLEAN


def _emit_orphan_alert(
    orphan_class: str,
    sample_paths: list[str],
    total_count: int,
    log: logging.Logger | None = None,
) -> None:
    """Emit a single pageable ops alert for one orphan class.

    One call per orphan class (not per blob).  sample_paths contains up to
    _MAX_SAMPLE_PATHS representative blob names; total_count is the full
    population count (may exceed len(sample_paths)).
    """
    _log = log or logger
    _log.error(
        "GCS artifact blobs have no matching Firestore document",
        extra=log_context(
            component="chat_artifact_orphan_scan",
            action="gcs_blob_orphan_alert",
            extra={
                "pageable": True,
                "alert_kind": "chat.orphan_scan.gcs_blob_orphan",
                "orphan_class": orphan_class,
                "total_count": total_count,
                "sample_paths": sample_paths[:_MAX_SAMPLE_PATHS],
            },
        ),
    )


def _emit_completion_log(
    summary: dict[str, int],
    log: logging.Logger | None = None,
) -> None:
    """Emit a structured INFO entry with the final summary counts."""
    _log = log or logger
    _log.info(
        "GCS artifact orphan scan complete",
        extra=log_context(
            component="chat_artifact_orphan_scan",
            action="scan_complete",
            success=summary.get("errored", 0) == 0,
            extra={
                "scanned_blobs": summary.get("scanned_blobs", 0),
                "missing_metadata": summary.get("missing_metadata", 0),
                "missing_session": summary.get("missing_session", 0),
                "malformed_paths": summary.get("malformed_paths", 0),
                "duration_ms": summary.get("duration_ms", 0),
                "errored": summary.get("errored", 0),
            },
        ),
    )


# ---------------------------------------------------------------------------
# Firestore session-resolution helper
# ---------------------------------------------------------------------------


def _resolve_session_account_id(
    db: Any,
    session_id: str,
    cache: dict[str, str | None],
) -> str | None:
    """Resolve session_id → account_id via a collection_group query and in-memory cache.

    The GCS blob path does not encode account_id, so we look it up via
    collection_group("chat_sessions").where("session_id", "==", session_id).
    Results are cached per-scan to avoid redundant Firestore reads for blobs
    within the same session.

    Returns None if no side-table row exists for the given session_id.
    """
    if session_id in cache:
        return cache[session_id]

    results = (
        db.collection_group("chat_sessions")
        .where(filter=FieldFilter("session_id", "==", session_id))
        .limit(1)
        .stream()
    )
    account_id: str | None = None
    for doc in results:
        # Prefer the account_id field; fall back to parsing the document path.
        data = doc.to_dict() or {}
        account_id = data.get("account_id") or None
        if account_id is None:
            # Derive from canonical path: accounts/{account_id}/chat_sessions/...
            path_parts = doc.reference.path.split("/")
            if (
                len(path_parts) >= 4
                and path_parts[0] == "accounts"
                and path_parts[2] == "chat_sessions"
                and _FIRESTORE_ID_RE.match(path_parts[1])
            ):
                account_id = path_parts[1]
        break

    cache[session_id] = account_id
    return account_id


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def scan_for_gcs_blob_orphans(
    db: Any,
    storage_client: Any,
    *,
    account_id: str | None = None,
    limit: int | None = None,
    bucket_name: str | None = None,
    _now: datetime | None = None,
) -> dict[str, int]:
    """Reconcile GCS artifact blobs against ChatArtifactIndex Firestore docs.

    Lists every blob under gs://{artifact-bucket}/{APP_NAME}/, resolves each
    session_id → account_id via the Firestore side-table, and checks for the
    corresponding artifact doc.  No GCS or Firestore mutations are made.

    Args:
        db: Firestore client.
        storage_client: GCS storage.Client.
        account_id: If given, only report orphans whose session resolves to
            this account; blobs from other accounts are skipped silently.
            Note: ``missing_session`` blobs (session_id not found in Firestore)
            cannot be attributed to any account and are also excluded when this
            filter is active — the output reflects only classifiable orphans.
        limit: Cap the total number of GCS blobs enumerated (including
            malformed and cross-account blobs; limits GCS API calls).
        bucket_name: Override the resolved artifact bucket name (for tests).
        _now: Injectable wall-clock time (reserved for future tombstone-aware
            logic; not used in the current report-only implementation).

    Returns a summary dict::

        {
            "scanned_blobs": int,    # blobs fully classified (post-filter)
            "missing_metadata": int, # blobs with no artifact doc
            "missing_session": int,  # blobs with no side-table row
            "malformed_paths": int,  # blobs whose GCS path failed to parse
            "duration_ms": int,      # wall-clock time in milliseconds
            "errored": int,          # blobs that raised an exception
        }
    """
    start_time = time.monotonic()
    summary: dict[str, int] = {
        "scanned_blobs": 0,
        "missing_metadata": 0,
        "missing_session": 0,
        "malformed_paths": 0,
        "duration_ms": 0,
        "errored": 0,
    }

    missing_metadata_paths: list[str] = []
    missing_session_paths: list[str] = []
    session_account_cache: dict[str, str | None] = {}

    resolved_bucket = bucket_name or _ARTIFACT_GCS_BUCKET or _resolve_bucket(None)
    blobs = storage_client.list_blobs(resolved_bucket, prefix=f"{APP_NAME}/")

    loop_count = 0
    for blob in blobs:
        if limit is not None and loop_count >= limit:
            break
        loop_count += 1

        gcs_uri = f"gs://{resolved_bucket}/{blob.name}"
        parsed = parse_gcs_path(gcs_uri)
        if parsed is None:
            summary["malformed_paths"] += 1
            continue

        # Validate all path components before using any in Firestore paths or logs.
        if not _FIRESTORE_ID_RE.match(parsed.session_id):
            logger.warning(
                "GCS blob has invalid session_id; skipping",
                extra=log_context(
                    component="chat_artifact_orphan_scan",
                    action="skip_invalid_session_id",
                    extra={"blob_name": blob.name},
                ),
            )
            summary["errored"] += 1
            continue

        if not _FIRESTORE_ID_RE.match(parsed.user_id):
            logger.warning(
                "GCS blob has invalid user_id; skipping",
                extra=log_context(
                    component="chat_artifact_orphan_scan",
                    action="skip_invalid_user_id",
                    extra={"blob_name": blob.name},
                ),
            )
            summary["errored"] += 1
            continue

        if not _FILENAME_RE.match(parsed.filename):
            logger.warning(
                "GCS blob has invalid filename; skipping",
                extra=log_context(
                    component="chat_artifact_orphan_scan",
                    action="skip_invalid_filename",
                    extra={"blob_name": blob.name},
                ),
            )
            summary["errored"] += 1
            continue

        try:
            resolved_account_id = _resolve_session_account_id(
                db, parsed.session_id, session_account_cache
            )

            # Skip blobs from other accounts when --account-id filter is set.
            # Blobs whose session has no side-table row (missing_session) are
            # also excluded — ownership cannot be confirmed without a Firestore row.
            if account_id is not None and resolved_account_id != account_id:
                continue

            summary["scanned_blobs"] += 1

            # Validate resolved account_id before building Firestore paths.
            if resolved_account_id is not None and not _FIRESTORE_ID_RE.match(
                resolved_account_id
            ):
                logger.warning(
                    "Resolved account_id failed validation; skipping",
                    extra=log_context(
                        component="chat_artifact_orphan_scan",
                        action="skip_invalid_account_id",
                        extra={
                            "session_id": parsed.session_id,
                            "blob_name": blob.name,
                        },
                    ),
                )
                summary["errored"] += 1
                continue

            artifact_doc_exists = False
            if resolved_account_id is not None:
                art_id = _artifact_id(
                    parsed.session_id, parsed.filename, parsed.version
                )
                art_path = (
                    f"accounts/{resolved_account_id}/chat_sessions/"
                    f"{parsed.session_id}/artifacts/{art_id}"
                )
                artifact_doc_exists = db.document(art_path).get().exists

            classification = _classify_blob(resolved_account_id, artifact_doc_exists)

            if classification == CLASS_MISSING_METADATA:
                summary["missing_metadata"] += 1
                if len(missing_metadata_paths) < _MAX_SAMPLE_PATHS:
                    missing_metadata_paths.append(blob.name)
            elif classification == CLASS_MISSING_SESSION:
                summary["missing_session"] += 1
                if len(missing_session_paths) < _MAX_SAMPLE_PATHS:
                    missing_session_paths.append(blob.name)

        except Exception:
            logger.exception(
                "Error processing GCS blob",
                extra=log_context(
                    component="chat_artifact_orphan_scan",
                    action="blob_processing_error",
                    extra={"blob_name": blob.name},
                ),
            )
            summary["errored"] += 1

    if missing_metadata_paths:
        _emit_orphan_alert(
            CLASS_MISSING_METADATA,
            missing_metadata_paths,
            summary["missing_metadata"],
        )
    if missing_session_paths:
        _emit_orphan_alert(
            CLASS_MISSING_SESSION,
            missing_session_paths,
            summary["missing_session"],
        )

    summary["duration_ms"] = int((time.monotonic() - start_time) * 1000)
    _emit_completion_log(summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, initialise clients, run the scan, return an exit code."""
    configure_logging()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.account_id is not None and not _FIRESTORE_ID_RE.match(args.account_id):
        print(
            f"ERROR: --account-id {args.account_id!r} contains invalid characters.",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR

    if args.limit is not None and args.limit <= 0:
        print(
            f"ERROR: --limit must be a positive integer (got {args.limit!r}).",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR

    project_id, database_id = _load_env()

    try:
        from google.cloud import firestore  # type: ignore[import-untyped]
        from google.cloud import storage as gcs  # type: ignore[import-untyped]

        db = firestore.Client(project=project_id, database=database_id)
        storage_client = gcs.Client(project=project_id)

    except Exception as exc:
        logger.exception("Failed to initialise clients: %s", exc)
        return EXIT_RUNTIME_ERROR

    if WEAVE_AVAILABLE:
        weave_project = os.environ.get("WEAVE_PROJECT", "ken-e")
        try:
            weave.init(weave_project)
        except Exception:
            logger.warning(
                "Weave init failed; continuing without tracing",
                extra=log_context(
                    component="chat_artifact_orphan_scan", action="weave_init_warning"
                ),
            )

    try:
        summary = scan_for_gcs_blob_orphans(
            db=db,
            storage_client=storage_client,
            account_id=args.account_id,
            limit=args.limit,
        )
    except Exception as exc:
        logger.exception("Unexpected error during orphan scan: %s", exc)
        return EXIT_RUNTIME_ERROR

    print(json.dumps(summary))
    return EXIT_VERIFICATION_FAILED if summary.get("errored", 0) > 0 else EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME_ERROR)
