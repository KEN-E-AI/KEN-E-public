"""ADK-session orphan reconciliation job for KEN-E chat.

Reconciles Vertex AI ADK sessions against the chat_sessions Firestore
side-table.  Two orphan classes are detected and handled differently:

  tombstoned — side-table row has deleted_at set > grace_window ago; the
               chat delete-cleanup task never removed the ADK session.
               Auto-delete: ADK session → GCS blobs → artifact docs → row.

  missing    — no side-table row exists at all; data-integrity anomaly.
               Page ops via structured-log alert; do NOT auto-delete.

Exit codes:
  0 — success (errored == 0)
  1 — verification failed (errored > 0)
  2 — usage error (bad args / missing env)
  3 — runtime error (unexpected exception)

The chat_v2_enabled feature flag does NOT gate this script.
Cloud Scheduler binding (04:30 UTC daily) is configured by a separate scheduler
change.

Usage:
    python chat_adk_session_orphan_scan.py [--dry-run] [--account-id ID]
                                           [--grace-hours N]
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

# ---------------------------------------------------------------------------
# Path bootstrap — makes kene_api and shared importable without install
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent
_API_SRC = _SCRIPTS_DIR.parent / "src"
_REPO_ROOT = _SCRIPTS_DIR.parent.parent
for _p in (str(_API_SRC), str(_SCRIPTS_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Optional Weave instrumentation
# ---------------------------------------------------------------------------
try:
    import weave  # type: ignore[import-untyped]

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False

from shared.structured_logging import (  # noqa: E402
    configure_logging,
    get_structured_logger,
    log_context,
)

if TYPE_CHECKING:
    from kene_api.models.chat import ChatSessionMetadata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
APP_NAME = "ken_e_chatbot"
DEFAULT_GRACE_WINDOW = timedelta(hours=1)

EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_RUNTIME_ERROR = 3

_FIRESTORE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_MAX_RAW_LOG_LEN = 64
# Restrict GCS deletions to the declared artifact bucket.  Set via environment
# variable; empty string disables the check (logs a warning per deletion).
_ARTIFACT_GCS_BUCKET: str = os.environ.get("ARTIFACT_GCS_BUCKET", "")

CLASS_TOMBSTONED = "tombstoned"
CLASS_TOMBSTONED_IN_GRACE = "tombstoned_in_grace"
CLASS_MISSING = "missing"
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
            "Reconcile ADK sessions against the chat_sessions Firestore side-table. "
            "Tombstoned sessions older than the grace window are auto-deleted; "
            "sessions with no side-table row trigger a pageable ops alert."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report what would be done without making any state changes.",
    )
    parser.add_argument(
        "--account-id",
        default=None,
        metavar="ACCOUNT_ID",
        help="Limit scan to a single account (useful for targeted remediation).",
    )
    parser.add_argument(
        "--grace-hours",
        type=float,
        default=1.0,
        metavar="HOURS",
        help=(
            "Grace period in hours before tombstoned sessions are auto-deleted. "
            "Exists to avoid racing the chat delete-cleanup task still in flight. "
            "Default: 1.0."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _classify_session(
    session_state_account_id: str,
    session_id: str,
    side_table_meta: ChatSessionMetadata | None,
    now: datetime,
    grace_window: timedelta = DEFAULT_GRACE_WINDOW,
) -> str:
    """Classify one ADK session against its Firestore side-table record.

    Returns one of CLASS_TOMBSTONED, CLASS_TOMBSTONED_IN_GRACE, CLASS_MISSING,
    or CLASS_ALL_CLEAN.  Uses a strict ``>`` comparison for the grace window so
    that sessions deleted exactly at the boundary are kept in the grace bucket.
    """
    if side_table_meta is None:
        return CLASS_MISSING

    deleted_at = side_table_meta.deleted_at
    if deleted_at is None:
        return CLASS_ALL_CLEAN

    if deleted_at.tzinfo is None:
        deleted_at = deleted_at.replace(tzinfo=timezone.utc)

    if (now - deleted_at) > grace_window:
        return CLASS_TOMBSTONED

    return CLASS_TOMBSTONED_IN_GRACE


def _normalize_list_sessions_response(sessions: Any) -> list[Any]:
    """Normalise the return value of ``VertexAiSessionService.list_sessions()``.

    The ADK returns either a plain list or an object with a ``.sessions``
    attribute and an optional ``.next_page_token``.  Pagination is not yet
    supported — RuntimeError is raised if a page token is present.

    ADK issue #3154: ``Session.user_id`` can be empty on the returned objects.
    Always use the iteration-loop ``user_id`` rather than ``session.user_id``
    to route sessions back to their owner.

    Raises ``RuntimeError`` when the response includes a ``next_page_token``
    (pagination is not yet implemented).  The caller logs this at exception
    level so ops is alerted to the data-completeness gap.
    """
    if hasattr(sessions, "sessions"):
        result = list(sessions.sessions)
        if getattr(sessions, "next_page_token", None):
            raise RuntimeError(
                "ADK list_sessions returned a paginated response; "
                "pagination is not yet supported by this script."
            )
        return result
    return list(sessions)


def _alert_missing_orphan_ops(
    orphans: list[dict[str, str]],
    log: logging.Logger | None = None,
) -> None:
    """Emit a pageable ops alert for every missing-side-table orphan.

    Missing orphans are NOT auto-deleted; this structured-log alert is the
    only action taken.  Each entry in *orphans* must contain ``account_id``
    and ``session_id`` keys.
    """
    _log = log or logger
    for entry in orphans:
        _log.error(
            "ADK session has no chat_sessions side-table row",
            extra=log_context(
                component="chat_orphan_scan",
                action="missing_side_table_alert",
                account_id=entry.get("account_id", ""),
                session_id=entry.get("session_id", ""),
                extra={
                    "pageable": True,
                    "alert_kind": "chat.orphan_scan.missing_side_table",
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
        "ADK orphan scan complete",
        extra=log_context(
            component="chat_orphan_scan",
            action="scan_complete",
            success=summary.get("errored", 0) == 0,
            extra={
                "tombstoned_cleaned": summary.get("tombstoned_cleaned", 0),
                "tombstoned_in_grace": summary.get("tombstoned_in_grace", 0),
                "missing_orphans": summary.get("missing_orphans", 0),
                "all_clean": summary.get("all_clean", 0),
                "errored": summary.get("errored", 0),
            },
        ),
    )


# ---------------------------------------------------------------------------
# ADK async helpers (synchronous wrappers for blocking SDK calls)
# ---------------------------------------------------------------------------


def _list_sessions_for_user(session_service: Any, user_id: str) -> list[Any]:
    """Call ``session_service.list_sessions`` from a synchronous context.

    VertexAiSessionService is async; we spin up a fresh event loop in a
    ThreadPoolExecutor so we never block the main thread's loop.
    """

    def _run() -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                session_service.list_sessions(app_name=APP_NAME, user_id=user_id)
            )
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(_run).result()
    return _normalize_list_sessions_response(result)


def _delete_adk_session(session_service: Any, user_id: str, session_id: str) -> None:
    """Call ``session_service.delete_session`` from a synchronous context.

    ADK ``NotFound`` / 404 responses are treated as success — a concurrent
    cleanup pass may have already removed the session.

    ``user_id`` is required: ``VertexAiSessionService.delete_session`` takes it as
    a keyword-only argument alongside ``app_name`` / ``session_id``; omitting it
    raises ``TypeError`` and the deletion never runs.
    """
    from google.api_core.exceptions import NotFound  # type: ignore[import-untyped]

    def _run() -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                session_service.delete_session(
                    app_name=APP_NAME, user_id=user_id, session_id=session_id
                )
            )
        finally:
            loop.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_run).result()
    except NotFound:
        pass


# ---------------------------------------------------------------------------
# Firestore iteration helper
# ---------------------------------------------------------------------------


def _iter_users(db: Any, account_id: str | None) -> Any:
    """Yield ``(user_id, user_data)`` pairs from the top-level ``users`` collection.

    When *account_id* is given, only users who have a permission entry for
    that account are yielded.
    """
    for user_doc in db.collection("users").stream():
        user_data = user_doc.to_dict() or {}
        if account_id is not None:
            account_permissions = user_data.get("permissions", {}).get(
                "account_permissions", {}
            )
            if account_id not in account_permissions:
                continue
        yield user_doc.id, user_data


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def scan_for_adk_session_orphans(
    db: Any,
    session_service: Any,
    storage_client: Any | None = None,
    *,
    dry_run: bool = False,
    account_id: str | None = None,
    grace_window: timedelta = DEFAULT_GRACE_WINDOW,
    _now: datetime | None = None,
) -> dict[str, int]:
    """Reconcile all ADK sessions against the chat_sessions side-table.

    Iterates ``users/*``, lists each user's ADK sessions, and classifies each
    session via ``_classify_session``.  Tombstoned sessions outside the grace
    window are deleted (ADK → GCS blobs → artifact docs → side-table row).
    Missing sessions trigger a pageable ops alert without any deletion.

    ``_now`` is injectable for tests; production code omits it (defaults to
    ``datetime.now(tz=timezone.utc)`` at call time).

    Returns a summary dict::

        {
            "tombstoned_cleaned": int,   # deleted (or would-delete if dry_run)
            "tombstoned_in_grace": int,  # skipped — still in grace window
            "missing_orphans": int,      # alerted but not deleted
            "all_clean": int,            # no action needed
            "errored": int,              # sessions that raised an exception
        }
    """
    from kene_api.chat.side_table import ChatSessionSideTableService

    summary: dict[str, int] = {
        "tombstoned_cleaned": 0,
        "tombstoned_in_grace": 0,
        "missing_orphans": 0,
        "all_clean": 0,
        "errored": 0,
    }
    missing_orphans: list[dict[str, str]] = []
    now = _now if _now is not None else datetime.now(tz=timezone.utc)
    side_table_svc = ChatSessionSideTableService(db)

    for user_id, _user_data in _iter_users(db, account_id):
        try:
            sessions = _list_sessions_for_user(session_service, user_id)
        except Exception:
            logger.exception(
                "Failed to list ADK sessions for user",
                extra=log_context(
                    component="chat_orphan_scan",
                    action="list_sessions_error",
                    extra={"user_id": user_id},
                ),
            )
            summary["errored"] += 1
            continue

        for session in sessions:
            session_id: str = session.id
            # ADK issue #3154: session.user_id may be empty — use loop user_id.
            # Use getattr so a non-dict State object (ADK may return a custom type)
            # is handled safely; fall back to {} so .get() is always valid.
            session_account_id: str = (getattr(session, "state", None) or {}).get(
                "account_id", ""
            )

            if not session_account_id or not _FIRESTORE_ID_RE.match(session_account_id):
                logger.warning(
                    "ADK session missing or invalid account_id in state; skipping",
                    extra=log_context(
                        component="chat_orphan_scan",
                        action="skip_invalid_account_id",
                        session_id=session_id,
                        extra={
                            "user_id": user_id,
                            # Truncate to avoid reflecting arbitrary ADK state payloads.
                            "raw_account_id": str(session_account_id)[
                                :_MAX_RAW_LOG_LEN
                            ],
                        },
                    ),
                )
                summary["errored"] += 1
                continue

            if not _FIRESTORE_ID_RE.match(session_id):
                logger.warning(
                    "ADK session has invalid session_id; skipping",
                    extra=log_context(
                        component="chat_orphan_scan",
                        action="skip_invalid_session_id",
                        session_id=session_id,
                        extra={"user_id": user_id},
                    ),
                )
                summary["errored"] += 1
                continue

            try:
                meta = side_table_svc.get(session_account_id, session_id)
                classification = _classify_session(
                    session_account_id, session_id, meta, now, grace_window
                )

                if classification == CLASS_ALL_CLEAN:
                    summary["all_clean"] += 1

                elif classification == CLASS_TOMBSTONED_IN_GRACE:
                    summary["tombstoned_in_grace"] += 1

                elif classification == CLASS_MISSING:
                    summary["missing_orphans"] += 1
                    missing_orphans.append(
                        {"account_id": session_account_id, "session_id": session_id}
                    )

                elif classification == CLASS_TOMBSTONED:
                    if not dry_run:
                        _cleanup_tombstoned_session(
                            db=db,
                            session_service=session_service,
                            storage_client=storage_client,
                            account_id=session_account_id,
                            user_id=user_id,
                            session_id=session_id,
                        )
                        # Increment only after successful cleanup so the counter
                        # is never inflated by a partially-failed deletion.
                        summary["tombstoned_cleaned"] += 1
                        logger.info(
                            "Deleted tombstoned ADK session",
                            extra=log_context(
                                component="chat_orphan_scan",
                                action="tombstone_deleted",
                                account_id=session_account_id,
                                session_id=session_id,
                            ),
                        )
                    else:
                        # Dry-run: count what would be cleaned without mutating state.
                        summary["tombstoned_cleaned"] += 1
                        logger.info(
                            "Dry-run: would delete tombstoned ADK session",
                            extra=log_context(
                                component="chat_orphan_scan",
                                action="tombstone_dry_run",
                                account_id=session_account_id,
                                session_id=session_id,
                            ),
                        )

            except Exception:
                logger.exception(
                    "Error processing ADK session",
                    extra=log_context(
                        component="chat_orphan_scan",
                        action="session_processing_error",
                        account_id=session_account_id,
                        session_id=session_id,
                    ),
                )
                summary["errored"] += 1

    if missing_orphans:
        _alert_missing_orphan_ops(missing_orphans)

    _emit_completion_log(summary)
    return summary


def _cleanup_tombstoned_session(
    db: Any,
    session_service: Any,
    storage_client: Any | None,
    account_id: str,
    user_id: str,
    session_id: str,
) -> None:
    """Delete a tombstoned session in dependency order.

    Order: GCS blobs → ADK session → artifact subcollection docs → side-table row.
    The artifact subcollection is streamed once and reused for both GCS blob
    deletion and Firestore document deletion to avoid a double-read race window.

    GCS blobs are deleted FIRST. If any blob cannot be removed (a delete error, an
    unexpected bucket, or there are blobs to remove but no storage client), this
    raises before the ADK session is deleted — so the session stays listed and the
    next run reclassifies it as tombstoned and retries. Deleting the ADK session
    first would de-list it on an abort, stranding the row + blob beyond any future
    scan. (Artifacts with no ``gcs_path`` have no blob, so they don't require a
    storage client.)
    """
    # 1. Stream artifact docs once; reuse the list for the GCS and Firestore steps.
    artifacts_ref = db.collection(
        f"accounts/{account_id}/chat_sessions/{session_id}/artifacts"
    )
    artifact_docs = list(artifacts_ref.stream())

    # 2. Delete GCS blobs first. Refuse to proceed if there are real blobs to
    #    purge but no storage client (they'd be orphaned). _delete_gcs_blobs raises
    #    if any blob could not be removed, aborting the steps below (before the ADK
    #    session is deleted) so nothing is half-deleted in a non-retryable way.
    has_blobs = any((doc.to_dict() or {}).get("gcs_path") for doc in artifact_docs)
    if has_blobs and storage_client is None:
        raise RuntimeError(
            f"artifact blob(s) to purge for {account_id}/{session_id} but no GCS "
            "client is available; aborting before any deletion to avoid orphaning"
        )
    if storage_client is not None:
        _delete_gcs_blobs(
            storage_client, artifact_docs, account_id=account_id, session_id=session_id
        )

    # 3. Delete the ADK session (NotFound treated as success).
    _delete_adk_session(session_service, user_id, session_id)

    # 4. Delete artifact subcollection documents.
    for artifact_doc in artifact_docs:
        artifact_doc.reference.delete()

    # 5. Delete the side-table row.
    db.document(f"accounts/{account_id}/chat_sessions/{session_id}").delete()


def _delete_gcs_blobs(
    storage_client: Any,
    artifact_docs: list[Any],
    *,
    account_id: str,
    session_id: str,
) -> None:
    """Delete GCS blobs for a pre-fetched list of artifact documents.

    Validates each blob's bucket against ``_ARTIFACT_GCS_BUCKET`` (set via the
    ``ARTIFACT_GCS_BUCKET`` environment variable) to prevent deletion of blobs
    in unintended buckets.  A bucket mismatch is logged and counted as a failure.

    Raises ``RuntimeError`` if any blob could not be removed (delete error or
    bucket mismatch), so the caller aborts before deleting the artifact docs and
    side-table row — keeping the cleanup retryable on the next run rather than
    leaving an unreferenced (orphaned) blob behind.
    """
    from google.api_core.exceptions import NotFound  # type: ignore[import-untyped]

    unremoved = 0
    for artifact_doc in artifact_docs:
        artifact_data = artifact_doc.to_dict() or {}
        gcs_path: str = artifact_data.get("gcs_path") or ""
        if not gcs_path:
            continue
        try:
            raw_path = gcs_path[5:] if gcs_path.startswith("gs://") else gcs_path
            bucket_name, _, blob_name = raw_path.partition("/")
            if not bucket_name or not blob_name:
                continue
            if _ARTIFACT_GCS_BUCKET and bucket_name != _ARTIFACT_GCS_BUCKET:
                logger.error(
                    "gcs_path references unexpected bucket; refusing GCS deletion",
                    extra=log_context(
                        component="chat_orphan_scan",
                        action="gcs_unexpected_bucket",
                        account_id=account_id,
                        session_id=session_id,
                        extra={
                            "artifact_id": artifact_doc.id,
                            "bucket_name": bucket_name,
                            "expected_bucket": _ARTIFACT_GCS_BUCKET,
                        },
                    ),
                )
                unremoved += 1
                continue
            storage_client.bucket(bucket_name).blob(blob_name).delete()
        except NotFound:
            # Blob already gone (a prior run removed it before failing on a later
            # step). Treat as success so the session is not stuck retrying forever
            # on an already-deleted blob.
            continue
        except Exception:
            logger.error(
                "Failed to delete GCS blob for artifact",
                extra=log_context(
                    component="chat_orphan_scan",
                    action="gcs_blob_delete_error",
                    account_id=account_id,
                    session_id=session_id,
                    extra={"artifact_id": artifact_doc.id, "gcs_path": gcs_path},
                ),
            )
            unremoved += 1
    if unremoved:
        raise RuntimeError(
            f"{unremoved} artifact blob(s) could not be deleted from GCS for "
            f"{account_id}/{session_id}"
        )


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

    if args.grace_hours <= 0:
        print(
            "ERROR: --grace-hours must be a positive number (got "
            f"{args.grace_hours!r}).",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR

    project_id, database_id = _load_env()
    grace_window = timedelta(hours=args.grace_hours)

    try:
        from google.adk.sessions import (
            VertexAiSessionService,  # type: ignore[import-untyped]
        )
        from google.cloud import firestore  # type: ignore[import-untyped]
        from google.cloud import storage as gcs  # type: ignore[import-untyped]
        from vertexai.preview.reasoning_engines import (
            AdkApp,  # noqa: F401 — triggers auth
        )

        db = firestore.Client(project=project_id, database=database_id)

        vertex_project = os.environ.get("VERTEX_AI_PROJECT_ID", project_id)
        vertex_location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        engine_id_full = os.environ.get("KEN_E_ENGINE_ID") or os.environ.get(
            "VERTEX_AI_AGENT_ENGINE_ID"
        )
        if not engine_id_full:
            print(
                "ERROR: KEN_E_ENGINE_ID or VERTEX_AI_AGENT_ENGINE_ID must be set",
                file=sys.stderr,
            )
            return EXIT_USAGE_ERROR
        agent_engine_id = engine_id_full.split("/")[-1]
        session_service = VertexAiSessionService(
            project=vertex_project,
            location=vertex_location,
            agent_engine_id=agent_engine_id,
        )

        try:
            storage_client: gcs.Client | None = gcs.Client(project=project_id)
        except Exception:
            logger.warning(
                "GCS client init failed; artifact blobs will not be deleted",
                extra=log_context(
                    component="chat_orphan_scan", action="gcs_init_warning"
                ),
            )
            storage_client = None

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
                    component="chat_orphan_scan", action="weave_init_warning"
                ),
            )

    try:
        summary = scan_for_adk_session_orphans(
            db=db,
            session_service=session_service,
            storage_client=storage_client,
            dry_run=args.dry_run,
            account_id=args.account_id,
            grace_window=grace_window,
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
