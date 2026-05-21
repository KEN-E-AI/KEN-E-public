#!/usr/bin/env python3
"""Seed synthetic load-test data for the KEN-E Chat sidebar polling load test (CH-PRD-02 AC-16).

Creates a dedicated load-test account with 200 ChatSessionMetadata documents whose
`updated_at` timestamps are spread evenly across the last 30 days — exactly the
data shape the sidebar polling load test needs to exercise pagination, ordering, and
Firestore read throughput without touching real user data.

Usage
-----
  python api/scripts/seed_chat_load_test_data.py --dry-run
  python api/scripts/seed_chat_load_test_data.py
  python api/scripts/seed_chat_load_test_data.py --cleanup
  python api/scripts/seed_chat_load_test_data.py --yes-i-know-its-not-dev   # bypass dev guard
  python api/scripts/seed_chat_load_test_data.py --project-id my-gcp-project

Exit codes
----------
  0  success (all writes/deletes completed, no errors)
  1  one or more errors during write/delete (check output for details)
  2  usage error (bad args, missing env vars, production guard tripped)

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID   GCP project holding Firestore (overridden by --project-id).
  FIRESTORE_DATABASE_ID     Firestore database ID (default: "(default)").
  ENVIRONMENT               development | staging | production.
                            production refuses without --yes-i-know-its-not-dev.
                            staging warns but proceeds.

Idempotency
-----------
Each session document is checked for existence before writing.  Re-running the
script against a project that already has the data is safe — existing docs are
counted as `already_present` and skipped.

Cleanup
-------
--cleanup removes the 200 session docs, the accounts/acc_load_test document, and
the user-permissions doc at users/{uid}/permissions/account_permissions/acc_load_test.
The Firebase Auth user (chat-loadtest@ken-e-loadtest.local) is NOT deleted by
--cleanup because Firebase Auth deletions require a separate Admin SDK call and are
harder to undo in a load-test recovery scenario.  To delete the Auth user manually:

  from firebase_admin import auth as fb_auth
  fb_auth.delete_user(uid)

Notes
-----
- Does NOT use async — all Firestore I/O is synchronous (google-cloud-firestore
  synchronous client), matching the pattern in other seed scripts in this directory.
- Firebase Admin SDK uses Application Default Credentials (ADC); ensure
  `gcloud auth application-default login` has been run locally.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path bootstrap — allows running as a script without package install.
# ---------------------------------------------------------------------------
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOAD_TEST_ACCOUNT_ID = "acc_load_test"
LOAD_TEST_USER_EMAIL = "chat-loadtest@ken-e-loadtest.local"
LOAD_TEST_SESSION_COUNT = 200

_ORGANIZATION_ID = "org_load_test"
_MODEL_ID = "gemini-2.5-flash"
_CONTEXT_WINDOW_MAX = 1_048_576  # gemini-2.5-flash per MODEL_CONTEXT_WINDOW_REGISTRY
_ADK_APP_NAME = "ken_e_chatbot"
_SPREAD_DAYS = 30  # updated_at timestamps spread across this many days

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ERRORS = 1
EXIT_USAGE_ERROR = 2

# Project IDs that are permitted to receive load-test seed data.
# Production project IDs must never appear here.
_ALLOWED_SEED_PROJECTS: frozenset[str] = frozenset(
    {
        "ken-e-dev",
        "ken-e-staging",
        "ken-e-ci",
        "ken-e-staging-391472102753",  # legacy alias
    }
)


# ---------------------------------------------------------------------------
# Environment / project helpers
# ---------------------------------------------------------------------------


def _resolve_project_id(cli_project_id: str | None) -> str:
    """Return project ID from CLI arg or GOOGLE_CLOUD_PROJECT_ID env var."""
    pid = cli_project_id or os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "")
    if not pid:
        print(
            "ERROR: No project ID supplied. Either pass --project-id or set "
            "GOOGLE_CLOUD_PROJECT_ID.",
            file=sys.stderr,
        )
        sys.exit(EXIT_USAGE_ERROR)
    return pid


def _check_project_guard(project_id: str, bypass: bool) -> None:
    """Refuse to seed into projects outside the known-safe allowlist.

    This is a secondary safeguard on top of the ENVIRONMENT check: even if
    ENVIRONMENT is set incorrectly, an unexpected project ID is rejected.
    """
    if project_id not in _ALLOWED_SEED_PROJECTS:
        if not bypass:
            print(
                f"ERROR: project '{project_id}' is not in the load-test allowlist "
                f"({', '.join(sorted(_ALLOWED_SEED_PROJECTS))}).\n"
                "Pass --yes-i-know-its-not-dev to override (use with extreme caution).",
                file=sys.stderr,
            )
            sys.exit(EXIT_USAGE_ERROR)
        print(
            f"WARNING: project '{project_id}' is not in the allowlist — "
            "--yes-i-know-its-not-dev was passed. Proceeding.",
            file=sys.stderr,
        )


def _check_environment_guard(bypass: bool) -> None:
    """Enforce dev/staging/production guard.

    - production: refuse unless bypass is True.
    - staging: warn but proceed.
    - anything else (development, empty, test): proceed silently.
    """
    env = os.environ.get("ENVIRONMENT", "").lower()
    if env == "production":
        if not bypass:
            print(
                "ERROR: ENVIRONMENT=production. Refusing to write load-test fixtures "
                "to production.\n"
                "Pass --yes-i-know-its-not-dev to override (use with extreme caution).",
                file=sys.stderr,
            )
            sys.exit(EXIT_USAGE_ERROR)
        print(
            "WARNING: ENVIRONMENT=production and --yes-i-know-its-not-dev was passed. "
            "Proceeding.",
            file=sys.stderr,
        )
    elif env == "staging":
        print(
            "WARNING: ENVIRONMENT=staging. Writing load-test fixtures to staging. "
            "Proceeding.",
            file=sys.stderr,
        )


def _warn_if_chat_v2_disabled(db: Any) -> None:
    """Print a warning if the chat_v2_enabled flag is not active in Firestore.

    GET /api/v1/chat/conversations branches on chat_v2_enabled: when the flag
    is off (default=False), the endpoint falls back to the legacy ADK path and
    ignores the seeded Firestore sessions, making the load test measure the
    wrong code path.

    This is a non-blocking warning because the flag state may be unknown (e.g.
    when running in a fresh CI environment) or because the caller knows the
    flag is enabled at the account level.
    """
    try:
        flag_doc = db.collection("feature_flags").document("chat_v2_enabled").get()
        if not flag_doc.exists:
            print(
                "WARNING: feature_flags/chat_v2_enabled document not found in Firestore. "
                "Run api/scripts/seed_chat_feature_flags.py to register flags, then enable "
                "chat_v2_enabled so the load test exercises the Firestore path.",
                file=sys.stderr,
            )
            return
        data = flag_doc.to_dict() or {}
        if not data.get("is_active", False) and not data.get("default_enabled", False):
            print(
                "WARNING: chat_v2_enabled flag is not active (is_active=False, "
                "default_enabled=False). GET /api/v1/chat/conversations will use the "
                "legacy ADK path and will NOT read the seeded Firestore sessions. "
                "Enable the flag in the Feature Flags admin UI before running the "
                "load test to exercise the correct code path.",
                file=sys.stderr,
            )
    except Exception as exc:
        logger.warning("Could not read chat_v2_enabled flag from Firestore: %s", exc)


# ---------------------------------------------------------------------------
# Firebase Auth helpers
# ---------------------------------------------------------------------------


def _ensure_firebase_app() -> None:
    """Initialize Firebase Admin SDK if not already initialized."""
    import firebase_admin

    if not firebase_admin._apps:
        firebase_admin.initialize_app()


def _get_or_create_auth_user(email: str, dry_run: bool) -> str | None:
    """Return the UID of the load-test Firebase Auth user, creating if missing.

    Returns None on dry-run (no real UID is available).
    """
    from firebase_admin import auth as fb_auth

    if dry_run:
        logger.info("DRY-RUN: would ensure Firebase Auth user exists for %s", email)
        return None

    try:
        user = fb_auth.get_user_by_email(email)
        logger.info("Firebase Auth user already exists: uid=%s email=%s", user.uid, email)
        return user.uid
    except fb_auth.UserNotFoundError:
        pass

    user = fb_auth.create_user(
        email=email,
        email_verified=True,
        display_name="Chat Load Test User",
    )
    logger.info("Created Firebase Auth user: uid=%s email=%s", user.uid, email)
    return user.uid


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


def _session_updated_at(n: int, now: datetime) -> datetime:
    """Return the updated_at timestamp for session N (1-indexed).

    Sessions are spread evenly across the last 30 days:
      updated_at = now - 30 days + (30 / LOAD_TEST_SESSION_COUNT * N) days
    Session 1 is near the start of the window; session 200 is near `now`.
    """
    offset_days = (_SPREAD_DAYS / LOAD_TEST_SESSION_COUNT) * n
    return now - timedelta(days=_SPREAD_DAYS) + timedelta(days=offset_days)


# ---------------------------------------------------------------------------
# Firestore write helpers
# ---------------------------------------------------------------------------


def _build_session_payload(
    n: int,
    user_id: str,
    now: datetime,
) -> dict[str, Any]:
    """Build the Firestore dict for session N (1-indexed)."""
    updated_at = _session_updated_at(n, now)
    return {
        "session_id": f"load_test_session_{n:03d}",
        "user_id": user_id,
        "account_id": LOAD_TEST_ACCOUNT_ID,
        "organization_id": _ORGANIZATION_ID,
        "adk_app_name": _ADK_APP_NAME,
        "title": None,
        "category_id": None,
        "latest_summary": None,
        "summary_updated_at": None,
        "compaction_count": 0,
        "search_text": "",
        "created_at": updated_at,
        "updated_at": updated_at,
        "first_message_at": None,
        "last_user_message_at": None,
        "last_agent_message_at": None,
        "last_viewed_at": None,
        "last_agent_started_at": None,
        "last_agent_stopped_at": None,
        "input_tokens_total": 0,
        "output_tokens_total": 0,
        "reasoning_tokens_total": 0,
        "current_context_tokens": 0,
        "context_window_max": _CONTEXT_WINDOW_MAX,
        "model_id": _MODEL_ID,
        "tool_call_count": 0,
        "artifact_count": 0,
        "message_count": 0,
        "last_message_preview": f"Synthetic load test session {n:03d}",
        "auto_title_attempted_at": None,
        "deleted_at": None,
    }


def _seed_account_doc(
    db: Any,
    now: datetime,
    dry_run: bool,
) -> None:
    """Write the accounts/acc_load_test document."""
    doc_ref = db.collection("accounts").document(LOAD_TEST_ACCOUNT_ID)
    if dry_run:
        logger.info("DRY-RUN: would write accounts/%s", LOAD_TEST_ACCOUNT_ID)
        return
    existing = doc_ref.get()
    if existing.exists:
        logger.info("accounts/%s already exists — skipping", LOAD_TEST_ACCOUNT_ID)
        return
    doc_ref.set(
        {
            "display_name": "Load Test Account",
            "created_at": now,
            "is_load_test_fixture": True,
            "organization_id": _ORGANIZATION_ID,
        }
    )
    logger.info("Wrote accounts/%s", LOAD_TEST_ACCOUNT_ID)


def _seed_user_permissions(
    db: Any,
    uid: str,
    now: datetime,
    dry_run: bool,
) -> None:
    """Grant the load-test user member access to acc_load_test.

    Path: users/{uid}/permissions/account_permissions/acc_load_test
    """
    perm_path = (
        f"users/{uid}/permissions/account_permissions/{LOAD_TEST_ACCOUNT_ID}"
    )
    if dry_run:
        logger.info("DRY-RUN: would write %s", perm_path)
        return
    doc_ref = db.document(perm_path)
    existing = doc_ref.get()
    if existing.exists:
        logger.info("%s already exists — skipping", perm_path)
        return
    doc_ref.set({"role": "member", "granted_at": now})
    logger.info("Wrote %s", perm_path)


def _seed_sessions(
    db: Any,
    user_id: str,
    now: datetime,
    dry_run: bool,
) -> dict[str, int]:
    """Write LOAD_TEST_SESSION_COUNT session documents.

    Returns counts: {processed, created, already_present, errored}.
    """
    processed = 0
    created = 0
    already_present = 0
    errored = 0

    sessions_collection = f"accounts/{LOAD_TEST_ACCOUNT_ID}/chat_sessions"

    for n in range(1, LOAD_TEST_SESSION_COUNT + 1):
        session_id = f"load_test_session_{n:03d}"
        doc_path = f"{sessions_collection}/{session_id}"
        processed += 1

        try:
            if dry_run:
                logger.debug("DRY-RUN: would write %s", doc_path)
                created += 1
                continue

            doc_ref = db.document(doc_path)
            existing = doc_ref.get()
            if existing.exists:
                logger.debug("%s already exists — skipping", doc_path)
                already_present += 1
                continue

            payload = _build_session_payload(n, user_id, now)
            doc_ref.set(payload)
            logger.debug("Wrote %s", doc_path)
            created += 1

        except Exception as exc:
            logger.error("Error writing %s: %s", doc_path, exc, exc_info=True)
            errored += 1

    return {
        "processed": processed,
        "created": created,
        "already_present": already_present,
        "errored": errored,
    }


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------


def _cleanup(db: Any, uid: str | None) -> dict[str, int]:
    """Delete all seeded documents (reverse of seed).

    Deletes:
      - accounts/acc_load_test/chat_sessions/load_test_session_001..200
      - accounts/acc_load_test (the account doc itself)
      - users/{uid}/permissions/account_permissions/acc_load_test  (if uid known)

    Does NOT delete the Firebase Auth user.  See module docstring for rationale.

    Returns {deleted, errored}.
    """
    deleted = 0
    errored = 0

    # Delete session docs
    for n in range(1, LOAD_TEST_SESSION_COUNT + 1):
        session_id = f"load_test_session_{n:03d}"
        doc_path = f"accounts/{LOAD_TEST_ACCOUNT_ID}/chat_sessions/{session_id}"
        try:
            db.document(doc_path).delete()
            deleted += 1
            logger.debug("Deleted %s", doc_path)
        except Exception as exc:
            logger.error("Error deleting %s: %s", doc_path, exc, exc_info=True)
            errored += 1

    # Delete account doc
    account_path = f"accounts/{LOAD_TEST_ACCOUNT_ID}"
    try:
        db.document(account_path).delete()
        deleted += 1
        logger.info("Deleted %s", account_path)
    except Exception as exc:
        logger.error("Error deleting %s: %s", account_path, exc, exc_info=True)
        errored += 1

    # Delete user permissions doc (only if we have a UID)
    if uid:
        perm_path = (
            f"users/{uid}/permissions/account_permissions/{LOAD_TEST_ACCOUNT_ID}"
        )
        try:
            db.document(perm_path).delete()
            deleted += 1
            logger.info("Deleted %s", perm_path)
        except Exception as exc:
            logger.error("Error deleting %s: %s", perm_path, exc, exc_info=True)
            errored += 1
    else:
        logger.warning(
            "No uid available — skipping deletion of user permissions doc. "
            "Delete manually: users/<uid>/permissions/account_permissions/%s",
            LOAD_TEST_ACCOUNT_ID,
        )

    return {"deleted": deleted, "errored": errored}


def _resolve_uid_for_cleanup(db: Any) -> str | None:
    """Look up the UID of the load-test user from Firebase Auth (for cleanup path).

    Returns None if the user does not exist or Firebase Admin SDK is unavailable.
    """
    try:
        from firebase_admin import auth as fb_auth

        _ensure_firebase_app()
        user = fb_auth.get_user_by_email(LOAD_TEST_USER_EMAIL)
        return user.uid
    except Exception as exc:
        logger.warning(
            "Could not resolve UID for cleanup (Firebase Auth lookup failed): %s", exc
        )
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seed_chat_load_test_data",
        description=(
            "Seed 200 synthetic ChatSessionMetadata documents for the Chat sidebar "
            "polling load test (CH-PRD-02 AC-16).  Idempotent — safe to re-run."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print planned writes without touching Firestore or Firebase Auth. Exit 0.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=False,
        help=(
            "Delete the seeded session docs, account doc, and user permissions doc. "
            "Does NOT delete the Firebase Auth user (see module docstring)."
        ),
    )
    parser.add_argument(
        "--yes-i-know-its-not-dev",
        action="store_true",
        default=False,
        help="Bypass the production-environment guard (use with extreme caution).",
    )
    parser.add_argument(
        "--project-id",
        metavar="GCP_PROJECT_ID",
        default=None,
        help="Override GOOGLE_CLOUD_PROJECT_ID env var.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point — returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.dry_run and args.cleanup:
        print("ERROR: --dry-run and --cleanup are mutually exclusive.", file=sys.stderr)
        return EXIT_USAGE_ERROR

    _check_environment_guard(bypass=args.yes_i_know_its_not_dev)

    project_id = _resolve_project_id(args.project_id)
    _check_project_guard(project_id, bypass=args.yes_i_know_its_not_dev)
    database_id = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")

    print("=== seed_chat_load_test_data ===")
    print(f"project_id         : {project_id}")
    print(f"database_id        : {database_id}")
    print(f"account_id         : {LOAD_TEST_ACCOUNT_ID}")
    print(f"session_count      : {LOAD_TEST_SESSION_COUNT}")
    print(f"dry_run            : {args.dry_run}")
    print(f"cleanup            : {args.cleanup}")
    print()

    # Initialise Firestore client (synchronous, ADC)
    try:
        from google.cloud import firestore as _fs  # type: ignore[import]

        db = _fs.Client(project=project_id, database=database_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialise Firestore client: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    # ------------------------------------------------------------------
    # Cleanup path
    # ------------------------------------------------------------------
    if args.cleanup:
        uid = _resolve_uid_for_cleanup(db)
        print(
            f"Cleaning up load-test fixtures for account {LOAD_TEST_ACCOUNT_ID!r}..."
        )
        cleanup_summary = _cleanup(db, uid)
        print()
        print(json.dumps(cleanup_summary))
        if cleanup_summary["errored"] > 0:
            print(
                f"WARNING: {cleanup_summary['errored']} error(s) during cleanup — "
                "check logs above.",
                file=sys.stderr,
            )
            return EXIT_ERRORS
        print(
            f"Cleanup complete: deleted={cleanup_summary['deleted']}  "
            f"errored={cleanup_summary['errored']}"
        )
        print(
            "\nNOTE: Firebase Auth user has NOT been deleted.  "
            f"To remove it, look up the UID for {LOAD_TEST_USER_EMAIL!r} "
            "and call firebase_admin.auth.delete_user(uid)."
        )
        return EXIT_SUCCESS

    # ------------------------------------------------------------------
    # Seed path
    # ------------------------------------------------------------------

    # Warn early if chat_v2_enabled flag is not active — the load test will
    # exercise the wrong code path if the flag is off.
    if not args.dry_run:
        _warn_if_chat_v2_disabled(db)

    # 1. Firebase Auth user
    _ensure_firebase_app()
    uid = _get_or_create_auth_user(LOAD_TEST_USER_EMAIL, dry_run=args.dry_run)

    # For dry-run we use a placeholder UID so the rest of the flow can proceed.
    effective_uid = uid or "uid_dry_run_placeholder"

    now = datetime.now(timezone.utc)

    # 2. Account doc
    _seed_account_doc(db, now, dry_run=args.dry_run)

    # 3. User permissions
    _seed_user_permissions(db, effective_uid, now, dry_run=args.dry_run)

    # 4. Session documents
    session_summary = _seed_sessions(db, effective_uid, now, dry_run=args.dry_run)

    print()
    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(
        f"{prefix}Seed complete:\n"
        f"  processed      : {session_summary['processed']:,}\n"
        f"  created        : {session_summary['created']:,}\n"
        f"  already_present: {session_summary['already_present']:,}\n"
        f"  errored        : {session_summary['errored']:,}\n"
    )
    print(json.dumps(session_summary))

    if session_summary["errored"] > 0:
        return EXIT_ERRORS
    return EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: unexpected exception: {exc}", file=sys.stderr)
        logger.exception("Unexpected top-level exception")
        sys.exit(EXIT_ERRORS)
