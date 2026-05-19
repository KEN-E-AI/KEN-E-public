#!/usr/bin/env python3
"""migrate_chat_side_table_backfill.py — mirror existing ADK sessions into the chat_sessions side-table.

Usage
-----
  python api/scripts/migrate_chat_side_table_backfill.py --dry-run
  python api/scripts/migrate_chat_side_table_backfill.py --dry-run --account-id=<account_id>
  python api/scripts/migrate_chat_side_table_backfill.py
  python api/scripts/migrate_chat_side_table_backfill.py --account-id=<account_id>
  python api/scripts/migrate_chat_side_table_backfill.py --user-id=<user_id>

Exit codes
----------
  0  success
  1  verification failed (one or more sessions errored; check logs)
  2  usage error (missing required env var, invalid flag)
  3  runtime error (unexpected exception at the orchestration level)

Environment variables
---------------------
  GOOGLE_CLOUD_PROJECT_ID  (required) — GCP project holding the Firestore database.
  FIRESTORE_DATABASE_ID    (optional, default "(default)") — Firestore database ID.

Algorithm (CH-PRD-01 §5.3)
---------------------------
1. Iterate all users from the top-level `users/*` Firestore collection.
   When --account-id is provided, filter to users with a key set in
   `permissions.account_permissions.{account_id}`.
2. For each (account_id, user_id) pair: call list_sessions(app_name, user_id).
   ALWAYS use the iteration-loop user_id — never Session.user_id (ADK Issue #3154).
3. For each returned session:
   a. If the side-table row already exists → skip (already_present++).
   b. Validate session.state["account_id"] matches the scoped account_id.
      Skip with warning if mismatched (skipped_account_mismatch++).
   c. Write a minimal ChatSessionMetadata row.
4. Report {processed, created, already_present, skipped_account_mismatch, errored}.

Dry-run mode
------------
With --dry-run the script emits what it *would* write but makes zero Firestore writes.
Re-running after a real run is safe: idempotency is enforced by an existence check.
"""

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import re
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — allows running from the repo root without installing.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent
_API_SRC = _SCRIPTS_DIR.parent / "src"
for _p in (str(_API_SRC), str(_SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

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

# ADK app name (must match the live system)
APP_NAME = "ken_e_chatbot"

# Default model for historical sessions that don't record model_id in state.
_DEFAULT_MODEL_ID = "gemini-2.5-pro"

# Max preview length for last_message_preview (matches CH-12 accumulator).
_PREVIEW_MAX = 160

# Valid Firestore document-ID pattern: alphanumeric, underscore, hyphen, 1-128 chars.
_FIRESTORE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


# ---------------------------------------------------------------------------
# Environment contract
# ---------------------------------------------------------------------------


def _load_env() -> tuple[str, str]:
    """Read required env vars; exit 2 if missing."""
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


# ---------------------------------------------------------------------------
# Pure helpers — no I/O
# ---------------------------------------------------------------------------


def _normalize_list_sessions_response(sessions: Any) -> list[Any]:
    """Normalise the return value of VertexAiSessionService.list_sessions.

    ADK returns either:
      - A ListSessionsResponse object with a `.sessions` attribute (current shape).
      - A plain iterable of Session-like objects (older shape / test fakes).

    If a future ADK release introduces pagination (`.next_page_token`), the
    assertion below will fire as a detectable signal to revisit this helper.
    """
    if hasattr(sessions, "sessions"):
        result = list(sessions.sessions)
        if getattr(sessions, "next_page_token", None):
            raise RuntimeError(
                "ADK list_sessions returned a paginated response — back-fill must be "
                "updated to iterate pages. Observed next_page_token is set."
            )
        return result
    return list(sessions)


def _count_user_model_messages(session: Any) -> int:
    """Count events authored by 'user' or 'model'.

    Matches the CH-12 accumulator rule exactly: author ∈ {"user", "model"};
    system and tool events are excluded.
    """
    events = getattr(session, "events", []) or []
    count = 0
    for event in events:
        author = getattr(event, "author", None)
        if author in ("user", "model"):
            count += 1
    return count


def _last_message_preview(session: Any, limit: int = _PREVIEW_MAX) -> str | None:
    """Extract a preview string from the last non-internal event.

    Skips events whose text starts with [ORGANIZATION CONTEXT] (same filter
    used in app/adk/session/recovery.py:231).
    Truncates to `limit` characters.
    """
    events = getattr(session, "events", []) or []
    for event in reversed(events):
        content_obj = getattr(event, "content", None)
        if not content_obj:
            continue
        parts = getattr(content_obj, "parts", None)
        if not parts:
            continue
        for part in parts:
            text = getattr(part, "text", None)
            if not text:
                continue
            text = text.strip()
            if text.startswith("[ORGANIZATION CONTEXT]"):
                continue
            return text[:limit]
    return None


def _resolve_model_id(session: Any) -> str:
    """Resolve model_id for a historical session.

    Precedence:
      1. session.state["model_id"] — if any future code writes it there.
      2. _DEFAULT_MODEL_ID ("gemini-2.5-pro") — current root-agent default.

    Always returns a value registered in MODEL_CONTEXT_WINDOW_REGISTRY.
    """
    state = getattr(session, "state", {}) or {}
    return state.get("model_id") or _DEFAULT_MODEL_ID


def _parse_timestamp(value: Any) -> datetime | None:
    """Coerce ADK timestamp fields to an aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _build_metadata(
    session: Any,
    *,
    account_id: str,
    user_id: str,
    organization_id: str,
    context_window_max: int,
    model_id: str,
) -> Any:
    """Assemble a ChatSessionMetadata for a back-filled session.

    Raises ValueError if session.state["account_id"] is missing (caller decides
    whether to skip or error).
    """
    from kene_api.models.chat import ChatSessionMetadata

    state = getattr(session, "state", {}) or {}
    state_account_id = state.get("account_id")
    if not state_account_id:
        raise ValueError(
            f"session {getattr(session, 'id', '?')!r} has no state.account_id — "
            "cannot route to a Firestore parent"
        )

    session_id = str(getattr(session, "id", None) or getattr(session, "session_id", ""))
    if not session_id:
        raise ValueError("session has no id field")

    now = datetime.now(timezone.utc)
    created_at = _parse_timestamp(getattr(session, "create_time", None)) or now
    updated_at = _parse_timestamp(getattr(session, "update_time", None)) or created_at

    message_count = _count_user_model_messages(session)
    last_message_preview = _last_message_preview(session)
    title = state.get("conversation_name") or None

    return ChatSessionMetadata(
        session_id=session_id,
        user_id=user_id,  # ALWAYS from iteration loop — never session.user_id (ADK #3154)
        account_id=account_id,
        organization_id=organization_id,
        model_id=model_id,
        context_window_max=context_window_max,
        title=title,
        message_count=message_count,
        last_message_preview=last_message_preview,
        created_at=created_at,
        updated_at=updated_at,
        last_agent_started_at=None,
        last_agent_stopped_at=None,
        deleted_at=None,
    )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _iter_users(
    db: Any,
    account_id: str | None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (user_id, user_doc_dict) from the top-level users/* collection.

    When account_id is provided, only yield users whose
    permissions.account_permissions.<account_id> key is present (explicit grants).
    Super-admins / org-admins without explicit account_permissions entries are
    not excluded; per-session state["account_id"] is the ground truth for routing.
    """
    users_ref = db.collection("users")
    for user_doc in users_ref.stream():
        user_data = user_doc.to_dict() or {}
        if account_id is not None:
            account_permissions = (
                user_data.get("permissions", {}).get("account_permissions", {})
            )
            if account_id not in account_permissions:
                continue
        yield user_doc.id, user_data


def _resolve_organization_id(
    db: Any,
    account_id: str,
    cache: dict[str, str | None],
) -> str | None:
    """Return organization_id for an account, caching per run (one read per account)."""
    if account_id in cache:
        return cache[account_id]
    doc = db.collection("accounts").document(account_id).get()
    org_id: str | None = None
    if doc.exists:
        org_id = (doc.to_dict() or {}).get("organization_id")
    cache[account_id] = org_id
    return org_id


def _list_sessions_for_user(session_service: Any, user_id: str) -> list[Any]:
    """Call VertexAiSessionService.list_sessions in a dedicated event loop.

    Mirrors routers/chat.py:980-991: ADK's list_sessions blocks the event loop,
    so we run it in a thread with its own loop.
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


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def run_backfill(
    db: Any,
    session_service: Any,
    *,
    dry_run: bool,
    account_id: str | None = None,
    user_id_filter: str | None = None,
) -> dict[str, int]:
    """Execute the back-fill and return a summary dict.

    Keys: processed, created, already_present, skipped_account_mismatch, errored.
    """
    from kene_api.chat.context_windows import get_model_context_window

    processed = 0
    created = 0
    already_present = 0
    skipped_account_mismatch = 0
    errored = 0

    org_id_cache: dict[str, str | None] = {}

    # Enumerate users to iterate
    if user_id_filter:
        users: list[tuple[str, dict[str, Any]]] = [(user_id_filter, {})]
    else:
        users = list(_iter_users(db, account_id))

    logger.info("Starting back-fill: users_to_process=%d dry_run=%s", len(users), dry_run)

    for uid, _user_data in users:
        logger.debug("Listing sessions for user_id=%s", uid)
        try:
            sessions = _list_sessions_for_user(session_service, uid)
        except Exception as exc:
            logger.error(
                "Failed to list sessions for user_id=%s: %s", uid, exc, exc_info=True
            )
            errored += 1
            continue

        for session in sessions:
            processed += 1
            raw_session_id = str(
                getattr(session, "id", None) or getattr(session, "session_id", "")
            )
            log_prefix = f"session_id={raw_session_id!r} user_id={uid!r}"
            try:
                state = getattr(session, "state", {}) or {}
                session_account_id = state.get("account_id")

                if not session_account_id:
                    logger.warning("%s: missing state.account_id — skipping", log_prefix)
                    skipped_account_mismatch += 1
                    continue

                # When --account-id is set, enforce the filter at the session level too.
                if account_id and session_account_id != account_id:
                    logger.debug(
                        "%s: state.account_id=%r != filter account_id=%r — skipping",
                        log_prefix,
                        session_account_id,
                        account_id,
                    )
                    skipped_account_mismatch += 1
                    continue

                dest_account_id = session_account_id

                # Guard against Firestore path injection from untrusted ADK state.
                if not _FIRESTORE_ID_RE.match(dest_account_id):
                    logger.error(
                        "%s: dest_account_id=%r fails ID validation — skipping",
                        log_prefix,
                        dest_account_id,
                    )
                    errored += 1
                    continue
                if not _FIRESTORE_ID_RE.match(raw_session_id):
                    logger.error(
                        "%s: session_id=%r fails ID validation — skipping",
                        log_prefix,
                        raw_session_id,
                    )
                    errored += 1
                    continue

                doc_path = (
                    f"accounts/{dest_account_id}/chat_sessions/{raw_session_id}"
                )

                # Idempotency: skip if the row already exists.
                existing_doc = db.document(doc_path).get()
                if existing_doc.exists:
                    logger.debug("%s: side-table row already exists — skipping", log_prefix)
                    already_present += 1
                    continue

                # Resolve organization_id from account doc (cached).
                org_id = _resolve_organization_id(db, dest_account_id, org_id_cache)
                if not org_id:
                    logger.error(
                        "%s: accounts/%s has no organization_id — skipping (fix the "
                        "account doc and re-run)",
                        log_prefix,
                        dest_account_id,
                    )
                    errored += 1
                    continue

                model_id = _resolve_model_id(session)
                try:
                    context_window_entry = get_model_context_window(model_id)
                except KeyError:
                    logger.warning(
                        "%s: model_id=%r not in registry, falling back to %r",
                        log_prefix,
                        model_id,
                        _DEFAULT_MODEL_ID,
                    )
                    model_id = _DEFAULT_MODEL_ID
                    context_window_entry = get_model_context_window(model_id)

                metadata = _build_metadata(
                    session,
                    account_id=dest_account_id,
                    user_id=uid,  # ALWAYS iteration-loop uid — never session.user_id
                    organization_id=org_id,
                    context_window_max=context_window_entry.context_window_max,
                    model_id=model_id,
                )

                if dry_run:
                    logger.debug(
                        "DRY-RUN would write: %s (title=%r message_count=%d)",
                        doc_path,
                        metadata.title,
                        metadata.message_count,
                    )
                    logger.info("DRY-RUN would write: %s", doc_path)
                    created += 1
                else:
                    db.document(doc_path).set(metadata.model_dump())
                    logger.info("Wrote: %s", doc_path)
                    created += 1

            except Exception as exc:
                logger.error(
                    "%s: unexpected error — %s", log_prefix, exc, exc_info=True
                )
                errored += 1

    return {
        "processed": processed,
        "created": created,
        "already_present": already_present,
        "skipped_account_mismatch": skipped_account_mismatch,
        "errored": errored,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate_chat_side_table_backfill",
        description=(
            "Mirror existing ADK sessions into the chat_sessions Firestore side-table. "
            "Idempotent — safe to re-run. Use --dry-run to preview without writing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be written without touching Firestore or ADK.",
    )
    parser.add_argument(
        "--account-id",
        metavar="ACCOUNT_ID",
        default=None,
        help=(
            "Scope to a single account. When set, only sessions whose "
            "state.account_id matches this value are written."
        ),
    )
    parser.add_argument(
        "--user-id",
        metavar="USER_ID",
        default=None,
        help=(
            "Debug aide: scope to a single user. Useful for testing against a "
            "known user before running fleet-wide."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    project_id, database_id = _load_env()
    logger.info(
        "project_id=%s database_id=%s dry_run=%s account_id=%s user_id=%s",
        project_id,
        database_id,
        args.dry_run,
        args.account_id,
        args.user_id,
    )

    try:
        from google.cloud import firestore as _fs  # type: ignore[import]

        db = _fs.Client(project=project_id, database=database_id)
    except Exception as exc:
        print(f"ERROR: Failed to initialise Firestore client: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR

    # Import ADK dependencies; guard against missing optional package.
    try:
        from google.adk.sessions import VertexAiSessionService  # type: ignore[import]

        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        session_service = VertexAiSessionService(project=project_id, location=location)
    except ImportError:
        print(
            "ERROR: google-adk package not installed. "
            "Install it with: pip install google-adk",
            file=sys.stderr,
        )
        return EXIT_RUNTIME_ERROR

    try:
        summary = run_backfill(
            db,
            session_service,
            dry_run=args.dry_run,
            account_id=args.account_id,
            user_id_filter=args.user_id,
        )
    except Exception as exc:
        logger.exception("Unexpected error during back-fill: %s", exc)
        return EXIT_RUNTIME_ERROR

    # Human-readable summary
    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(
        f"\n{prefix}Back-fill complete:\n"
        f"  processed:               {summary['processed']:,}\n"
        f"  created:                 {summary['created']:,}\n"
        f"  already_present:         {summary['already_present']:,}\n"
        f"  skipped_account_mismatch:{summary['skipped_account_mismatch']:,}\n"
        f"  errored:                 {summary['errored']:,}\n"
    )
    # Machine-readable JSON on stdout (for piping / log parsing)
    print(json.dumps(summary))

    return EXIT_VERIFICATION_FAILED if summary["errored"] > 0 else EXIT_SUCCESS


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(EXIT_RUNTIME_ERROR)
