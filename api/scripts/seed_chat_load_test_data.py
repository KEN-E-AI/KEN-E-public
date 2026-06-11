#!/usr/bin/env python3
"""Seed synthetic load-test data for the KEN-E Chat sidebar polling load test (CH-PRD-02 AC-16).

Creates a dedicated load-test account with 200 ChatSessionMetadata documents whose
`updated_at` timestamps are spread evenly across the last 30 days — exactly the
data shape the sidebar polling load test needs to exercise pagination, ordering, and
Firestore read throughput without touching real user data.

It also creates the Neo4j `(:Account)-[:BELONGS_TO]->(:Organization)` edge that
`require_account_access_for` (IN-2) resolves: without it, GET /chat/conversations
returns 404 "Account not found" for every request and the sidebar load test's
failure-ratio gate fails the staging deploy. See the "Neo4j owning-org edge"
section below for the full rationale.

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
script against a project that already has the data is safe — existing session
docs are counted as `already_present` and skipped.  The user-permissions write
uses `set(merge=True)` and will re-stamp `granted_at` on every run; that's
intentional for a load-test fixture and has no effect on the sidebar polling
behaviour.

Cleanup
-------
--cleanup removes the 200 session docs, the accounts/acc_load_test document, the
nested user-permissions field at users/{uid} → permissions.account_permissions.acc_load_test,
and the Neo4j load-test Account/Organization nodes (and their BELONGS_TO edge).
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
# parent.parent = api/ (for src.kene_api.*); parent.parent.parent = repo root
# (for shared.*, which holds the canonical Secret Manager resolver used to
# resolve NEO4J_PASSWORD below).
# ---------------------------------------------------------------------------
for _p in (
    str(Path(__file__).parent.parent),
    str(Path(__file__).parent.parent.parent),
):
    if _p not in sys.path:
        sys.path.append(_p)

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


def _ensure_firebase_app(project_id: str) -> None:
    """Initialize Firebase Admin SDK bound to ``project_id`` if not already done.

    Why explicit projectId: ``firebase_admin.initialize_app()`` with no args
    infers the project from ADC / the metadata server. On Cloud Build that
    returns the build project (``ken-e-cicd``), not the target Firestore
    project — Identity Toolkit calls then 403 against the wrong project.
    """
    import firebase_admin

    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": project_id})


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
        logger.info(
            "Firebase Auth user already exists: uid=%s email=%s", user.uid, email
        )
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
    dry_run: bool,
) -> None:
    """Grant the load-test user edit access to acc_load_test.

    Writes a nested field on the user document — matches the schema in
    `routers/admin.py` (super-admin seed) and `firestore.py` (which uses the
    dot-path `permissions.account_permissions.<accountId>` as an update field
    path, not a Firestore document path).

    The leaf value must be the literal string "edit" or "view" — `UserContext`
    treats `account_permissions` as `dict[str, str]` and `CachedUserContextService`
    JSON-encodes that dict on every cache write. A nested `{role, granted_at}`
    map silently broke Redis caching during the CH-24 sidebar load test for
    weeks because `granted_at` is a Firestore Timestamp and json.dumps raised
    on it — every request fell through to Firestore on auth, blowing the p90
    gate. Keep this value as a string.

    Target: users/{uid} doc, field permissions.account_permissions.acc_load_test
    """
    field_target = (
        f"users/{uid} field permissions.account_permissions.{LOAD_TEST_ACCOUNT_ID}"
    )
    if dry_run:
        logger.info("DRY-RUN: would set %s", field_target)
        return
    user_ref = db.collection("users").document(uid)
    user_ref.set(
        {
            "uid": uid,
            "permissions": {
                "account_permissions": {
                    LOAD_TEST_ACCOUNT_ID: "edit",
                },
            },
        },
        merge=True,
    )
    logger.info("Wrote %s", field_target)


# ---------------------------------------------------------------------------
# Neo4j owning-org edge
# ---------------------------------------------------------------------------
#
# IN-2 (#983) migrated account-scoped endpoints — including
# GET /api/v1/chat/conversations, which the sidebar load test hammers — from
# the Firestore-only `UserContext.has_account_access` check to
# `require_account_access_for`. That guard resolves the account's *owning org*
# via a Neo4j lookup:
#     MATCH (acc:Account {account_id: $id})-[:BELONGS_TO]->(org:Organization)
# and returns HTTP 404 "Account not found" when no such edge exists
# (auth/account_org.py). The Firestore fixtures above do NOT create that edge,
# so without this step every load-test request 404s and the
# `chat-sidebar-p95-check` failure-ratio gate fails the staging deploy.


def _neo4j_connection_params() -> tuple[str, str, str, str]:
    """Return (uri, username, password, database) for Neo4j, resolving secrets.

    NEO4J_PASSWORD may be a Secret Manager reference (e.g.
    ``projects/.../secrets/neo4j-password/versions/latest``) — resolved via the
    shared resolver, same as the API config.

    Raises RuntimeError when NEO4J_URI is unset, or when the password fails to
    resolve to a non-empty value while a URI IS set. ``get_env_or_secret``
    swallows Secret Manager fetch errors and returns its default (""), so an
    empty resolved password almost always means a secretAccessor gap on the
    build SA — fail loudly here rather than letting it surface downstream as a
    confusing Neo4j auth error.
    """
    uri = os.environ.get("NEO4J_URI", "")
    if not uri:
        raise RuntimeError(
            "NEO4J_URI is not set — cannot seed the Neo4j owning-org edge that "
            "require_account_access_for (IN-2) requires. GET /chat/conversations "
            "will 404 'Account not found' and the load test will fail without it."
        )
    from shared.secrets import get_env_or_secret

    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = get_env_or_secret("NEO4J_PASSWORD", "") or ""
    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD did not resolve to a non-empty value while NEO4J_URI "
            "is set. get_env_or_secret returns its empty default on a Secret "
            "Manager fetch failure — check the build SA has "
            "secretmanager.secretAccessor on the neo4j-password secret. Failing "
            "loudly rather than attempting a Neo4j connection with an empty "
            "password (which would surface as a confusing auth error)."
        )
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    return uri, username, password, database


def _seed_neo4j_owning_org(dry_run: bool) -> None:
    """MERGE the (:Account)-[:BELONGS_TO]->(:Organization) edge IN-2's guard needs.

    Idempotent. Property names match auth/account_org.py's resolver query
    (``Account.account_id`` → ``Organization.organization_id``). Raises on
    failure so the seed step fails loudly rather than letting the load test 404.

    Both nodes also carry the strings their Pydantic models require — the org's
    ``organization_name``/``plan``/``website`` and the account's
    ``organization_id``/``industry``/``status``/``timezone`` (plus ``account_name``).
    Without them the super-admin list paths (``MATCH (org:Organization) RETURN
    org`` and ``MATCH (acc:Account) RETURN acc`` over *every* node) 500 on this
    fixture. The unconditional ``SET`` (not ``ON CREATE SET``) heals an
    already-MERGEd node missing them.
    """
    if dry_run:
        logger.info(
            "DRY-RUN: would MERGE (:Account {account_id:%r})-[:BELONGS_TO]->"
            "(:Organization {organization_id:%r}) in Neo4j",
            LOAD_TEST_ACCOUNT_ID,
            _ORGANIZATION_ID,
        )
        return

    from neo4j import GraphDatabase

    uri, username, password, database = _neo4j_connection_params()
    driver = GraphDatabase.driver(
        uri, auth=(username, password), connection_timeout=15.0
    )
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            session.run(
                """
                MERGE (org:Organization {organization_id: $org_id})
                  SET org.organization_name = 'Load Test Organization',
                      org.plan = 'Free',
                      org.website = '',
                      org.is_load_test_fixture = true
                MERGE (acc:Account {account_id: $account_id})
                  SET acc.account_name = 'Load Test Account',
                      acc.organization_id = $org_id,
                      acc.industry = 'Load Test',
                      acc.status = 'Active',
                      acc.timezone = 'UTC',
                      acc.is_load_test_fixture = true
                MERGE (acc)-[:BELONGS_TO]->(org)
                """,
                org_id=_ORGANIZATION_ID,
                account_id=LOAD_TEST_ACCOUNT_ID,
            )
        logger.info(
            "Neo4j: MERGEd (:Account {account_id:%r})-[:BELONGS_TO]->"
            "(:Organization {organization_id:%r})",
            LOAD_TEST_ACCOUNT_ID,
            _ORGANIZATION_ID,
        )
    finally:
        driver.close()


def _cleanup_neo4j_owning_org() -> tuple[int, int]:
    """Delete the load-test Account/Organization nodes and their edge.

    Returns ``(deleted, errored)`` node counts so the caller can fold them into
    the cleanup summary. Both deletes are guarded on ``is_load_test_fixture`` so
    a real Account/Organization accidentally sharing the id is never touched.
    """
    if not os.environ.get("NEO4J_URI"):
        logger.warning(
            "NEO4J_URI not set — skipping Neo4j cleanup of the load-test owning-org edge."
        )
        return 0, 0
    try:
        from neo4j import GraphDatabase

        uri, username, password, database = _neo4j_connection_params()
        driver = GraphDatabase.driver(
            uri, auth=(username, password), connection_timeout=15.0
        )
        try:
            with driver.session(database=database) as session:
                # DETACH DELETE the account (drops the BELONGS_TO edge too), then
                # the org — both guarded on is_load_test_fixture so a real node
                # accidentally sharing the id is never deleted.
                acc_summary = session.run(
                    "MATCH (acc:Account {account_id: $account_id}) "
                    "WHERE coalesce(acc.is_load_test_fixture, false) = true "
                    "DETACH DELETE acc",
                    account_id=LOAD_TEST_ACCOUNT_ID,
                ).consume()
                org_summary = session.run(
                    "MATCH (org:Organization {organization_id: $org_id}) "
                    "WHERE coalesce(org.is_load_test_fixture, false) = true "
                    "DETACH DELETE org",
                    org_id=_ORGANIZATION_ID,
                ).consume()
                deleted = (
                    acc_summary.counters.nodes_deleted
                    + org_summary.counters.nodes_deleted
                )
            logger.info("Neo4j: deleted %d load-test node(s)", deleted)
            return deleted, 0
        finally:
            driver.close()
    except Exception as exc:
        logger.error("Error during Neo4j cleanup: %s", exc, exc_info=True)
        return 0, 1


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
      - the nested field permissions.account_permissions.acc_load_test on
        users/{uid}  (if uid known)

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

    # Delete the user permissions entry — a nested field on users/{uid},
    # not a subcollection doc.  Uses the dot-path field-delete shape.
    if uid:
        from google.cloud import firestore as gcf

        field_target = (
            f"users/{uid} field permissions.account_permissions.{LOAD_TEST_ACCOUNT_ID}"
        )
        try:
            db.collection("users").document(uid).update(
                {
                    f"permissions.account_permissions.{LOAD_TEST_ACCOUNT_ID}": gcf.DELETE_FIELD,
                }
            )
            deleted += 1
            logger.info("Deleted %s", field_target)
        except Exception as exc:
            logger.error("Error deleting %s: %s", field_target, exc, exc_info=True)
            errored += 1
    else:
        logger.warning(
            "No uid available — skipping deletion of user permissions field. "
            "Delete manually: users/<uid> permissions.account_permissions.%s",
            LOAD_TEST_ACCOUNT_ID,
        )

    return {"deleted": deleted, "errored": errored}


def _resolve_uid_for_cleanup(db: Any, project_id: str) -> str | None:
    """Look up the UID of the load-test user from Firebase Auth (for cleanup path).

    Returns None if the user does not exist or Firebase Admin SDK is unavailable.
    """
    try:
        from firebase_admin import auth as fb_auth

        _ensure_firebase_app(project_id)
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
        uid = _resolve_uid_for_cleanup(db, project_id)
        print(f"Cleaning up load-test fixtures for account {LOAD_TEST_ACCOUNT_ID!r}...")
        cleanup_summary = _cleanup(db, uid)
        neo4j_deleted, neo4j_errored = _cleanup_neo4j_owning_org()
        cleanup_summary["deleted"] += neo4j_deleted
        cleanup_summary["errored"] += neo4j_errored
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
    _ensure_firebase_app(project_id)
    uid = _get_or_create_auth_user(LOAD_TEST_USER_EMAIL, dry_run=args.dry_run)

    # For dry-run we use a placeholder UID so the rest of the flow can proceed.
    effective_uid = uid or "uid_dry_run_placeholder"

    now = datetime.now(timezone.utc)

    # 2. Account doc (Firestore)
    _seed_account_doc(db, now, dry_run=args.dry_run)

    # 2b. Neo4j owning-org edge — required by require_account_access_for (IN-2);
    # without it GET /chat/conversations 404s and the load test fails (see the
    # Neo4j section above for the full rationale).
    try:
        _seed_neo4j_owning_org(dry_run=args.dry_run)
    except Exception as exc:
        print(
            f"ERROR: failed to seed the Neo4j owning-org edge: {exc}\n"
            "GET /api/v1/chat/conversations will 404 'Account not found' without "
            "it (require_account_access_for / IN-2), failing the sidebar load test.",
            file=sys.stderr,
        )
        logger.exception("Neo4j owning-org seed failed")
        return EXIT_ERRORS

    # 3. User permissions
    _seed_user_permissions(db, effective_uid, dry_run=args.dry_run)

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
