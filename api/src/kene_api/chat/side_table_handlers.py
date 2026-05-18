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

import google.api_core.exceptions
from google.cloud import firestore

from .side_table import get_chat_side_table_service

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

    Uses idem_ref.create() as an atomic compare-and-swap gate: if two concurrent
    requests race, only one will succeed the create; the other receives
    AlreadyExists and returns "duplicate" without re-applying the delta.

    Returns {"status": "applied"} or {"status": "duplicate", "applied_at": ...}.
    """
    key_hash = _sha256_hex(idempotency_key)
    idem_ref = db.collection(_IDEMPOTENCY_COLLECTION).document(key_hash)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=_IDEMPOTENCY_TTL_HOURS)

    try:
        idem_ref.create(
            {
                "key_hash": key_hash,
                "applied_at": now,
                "expires_at": expires_at,
            }
        )
    except google.api_core.exceptions.AlreadyExists:
        idem_doc = idem_ref.get()
        data = idem_doc.to_dict() if idem_doc.exists else {}
        stored_expires: datetime | None = data.get("expires_at")
        if stored_expires is None or stored_expires > now:
            return {"status": "duplicate", "applied_at": data.get("applied_at")}
        # TTL already passed on the stored doc but Firestore hasn't cleaned it yet;
        # overwrite and apply the delta.
        idem_ref.set(
            {
                "key_hash": key_hash,
                "applied_at": now,
                "expires_at": expires_at,
            }
        )

    reconstructed = _reconstruct_increments(delta)
    svc = get_chat_side_table_service()
    svc.update_from_delta(account_id=account_id, session_id=session_id, delta=reconstructed)

    return {"status": "applied"}
