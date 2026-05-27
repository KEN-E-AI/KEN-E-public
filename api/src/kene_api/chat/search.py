"""Cursor-paginated Firestore collection-group search for chat_sessions.

Queried on the COLLECTION_GROUP index (CH-PRD-01 §4.3).
Account-id isolation is enforced post-fetch because Firestore collection-group
queries cannot filter by parent document ID without a custom field index.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

from ..models.chat import ChatSessionMetadata

logger = logging.getLogger(__name__)

CHAT_LIST_WINDOW_DAYS = 30


def list_sessions(
    db: firestore.Client,
    user_id: str,
    account_id: str,
    cursor: str | None = None,
    category_id: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> tuple[list[ChatSessionMetadata], str | None]:
    """Return up to `limit` sessions for the user, newest first.

    Returns (sessions, next_cursor). next_cursor is None when exhausted.

    Post-fetch filters applied:
    - account_id must match (collection-group cannot filter by parent doc ID)
    - query is a casefold substring match against search_text
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CHAT_LIST_WINDOW_DAYS)

    coll_group: Any = db.collection_group("chat_sessions")
    q: Any = (
        coll_group.where(filter=firestore.FieldFilter("user_id", "==", user_id))
        .where(filter=firestore.FieldFilter("deleted_at", "==", None))
        .where(filter=firestore.FieldFilter("updated_at", ">=", cutoff))
        .order_by("updated_at", direction=firestore.Query.DESCENDING)
    )

    if category_id is not None:
        q = q.where(filter=firestore.FieldFilter("category_id", "==", category_id))

    if cursor is not None:
        try:
            ref_path, _updated_at = decode_cursor(cursor)
            # Validate the path is within the expected account/collection to
            # prevent an attacker from forcing the server to resolve arbitrary
            # Firestore paths via a crafted cursor value.
            expected_prefix = f"accounts/{account_id}/chat_sessions/"
            if ref_path.startswith(expected_prefix):
                cursor_doc = db.document(ref_path).get()
                if cursor_doc.exists:
                    q = q.start_after(cursor_doc)
            else:
                logger.debug(
                    "cursor path rejected (unexpected prefix): %s", ref_path[:80]
                )
        except Exception as exc:
            logger.debug("Ignoring malformed pagination cursor: %s", exc)

    # Over-fetch to find enough after post-fetch filtering.
    # Limit is multiplied by a small factor so short pages from account filtering
    # don't require extra round-trips in the common case.
    fetch_limit = (limit + 1) * 4
    docs = q.limit(fetch_limit).stream()

    results: list[ChatSessionMetadata] = []
    last_doc = None

    for doc in docs:
        data = doc.to_dict()
        if data.get("account_id") != account_id:
            continue
        if query:
            search_text: str = data.get("search_text", "")
            if query.casefold() not in search_text.casefold():
                continue
        results.append(ChatSessionMetadata(**data))
        last_doc = doc
        if len(results) == limit:
            break

    next_cursor: str | None = None
    if len(results) == limit and last_doc is not None:
        next_cursor = encode_cursor(last_doc)

    return results, next_cursor


def encode_cursor(doc_snapshot: Any) -> str:
    """Encode a Firestore document snapshot as an opaque page cursor."""
    updated_at: datetime | None = None
    data = doc_snapshot.to_dict()
    if data and "updated_at" in data:
        updated_at = data["updated_at"]

    raw = (
        f"{doc_snapshot.reference.path}|{updated_at.isoformat() if updated_at else ''}"
    )
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, datetime | None]:
    """Decode a page cursor into (doc_path, updated_at).

    Returns ("", None) for any malformed input so callers can safely ignore
    bad cursors without raising.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"==").decode()
    except Exception:
        return "", None
    parts = raw.split("|", 1)
    ref_path = parts[0]
    updated_at: datetime | None = None
    if len(parts) == 2 and parts[1]:
        try:
            updated_at = datetime.fromisoformat(parts[1])
        except ValueError:
            pass
    return ref_path, updated_at
