"""Request-level handler for the internal side-table update endpoint.

Provides idempotency via a Firestore `chat_idempotency_keys` collection:
  chat_idempotency_keys/{sha256(idempotency_key)}

Wire-protocol convention for firestore.Increment fields:
  {"_increment": n}  →  firestore.Increment(n)
  (used when the ADK callback serialises delta fields over HTTP)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL_HOURS = 24
_IDEMPOTENCY_COLLECTION = "chat_idempotency_keys"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _reconstruct_increments(delta: dict[str, Any]) -> dict[str, Any]:
    """Convert {"_increment": n} wire values to firestore.Increment(n) sentinels."""
    result: dict[str, Any] = {}
    for k, v in delta.items():
        if isinstance(v, dict) and set(v.keys()) == {"_increment"}:
            result[k] = firestore.Increment(v["_increment"])
        else:
            result[k] = v
    return result


def apply_side_table_update(
    db: firestore.Client,
    session_id: str,
    account_id: str,
    delta: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Apply a delta to the side-table with at-most-once idempotency.

    Returns {"status": "applied"} or {"status": "duplicate", "applied_at": ...}.
    """
    key_hash = _sha256_hex(idempotency_key)
    idem_ref = db.collection(_IDEMPOTENCY_COLLECTION).document(key_hash)
    now = datetime.now(timezone.utc)

    idem_doc = idem_ref.get()
    if idem_doc.exists:
        data = idem_doc.to_dict()
        expires_at: datetime | None = data.get("expires_at")
        if expires_at is None or expires_at > now:
            return {"status": "duplicate", "applied_at": data.get("applied_at")}

    reconstructed = _reconstruct_increments(delta)

    from kene_api.chat.side_table import get_chat_side_table_service

    svc = get_chat_side_table_service()
    svc.update_from_delta(account_id=account_id, session_id=session_id, delta=reconstructed)

    expires_at = now + timedelta(hours=_IDEMPOTENCY_TTL_HOURS)
    idem_ref.set(
        {
            "key_hash": key_hash,
            "session_id_hint": session_id,
            "applied_at": now,
            "expires_at": expires_at,
        }
    )

    return {"status": "applied"}
