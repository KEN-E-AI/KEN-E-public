"""Request-level handler for the internal side-table update endpoint.

Provides idempotency via a Firestore `chat_idempotency_keys` collection:
  chat_idempotency_keys/{sha256(idempotency_key)}

TurnDelta-typed payloads (from chat_after_agent_callback) are converted to
Firestore-native types via TurnDelta.to_firestore_delta(). Legacy dict payloads
(from chat_before_agent_callback and the in-process streaming path) undergo
inline sentinel reconstruction.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import google.api_core.exceptions
from google.cloud import firestore

from .side_table import get_chat_side_table_service

# TurnDelta lives in app/adk/ (cross-package).
_ADK_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "app", "adk")
)
if _ADK_PATH not in sys.path:
    sys.path.insert(0, _ADK_PATH)

from turn_delta import TurnDelta as _TurnDelta  # noqa: E402

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL_HOURS = 24
_IDEMPOTENCY_COLLECTION = "chat_idempotency_keys"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def apply_side_table_update(
    db: firestore.Client,
    session_id: str,
    account_id: str,
    delta: _TurnDelta | dict[str, Any],
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

    if isinstance(delta, _TurnDelta):
        firestore_delta = delta.to_firestore_delta()
    else:
        # Legacy dict path: reconstruct wire sentinels to Firestore-native types.
        # Handles chat_before_agent_callback ({"_isoformat": "..."} values) and
        # the in-process streaming path (already-native datetime / Increment values,
        # which pass through the isinstance checks unchanged).
        firestore_delta = {}
        for k, v in delta.items():
            if isinstance(v, dict) and set(v.keys()) == {"_increment"}:
                firestore_delta[k] = firestore.Increment(v["_increment"])
            elif isinstance(v, dict) and set(v.keys()) == {"_isoformat"}:
                firestore_delta[k] = datetime.fromisoformat(v["_isoformat"])
            else:
                firestore_delta[k] = v

    if not firestore_delta:
        return {"status": "applied"}

    try:
        idem_ref.create(
            {
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
                "applied_at": now,
                "expires_at": expires_at,
            }
        )

    svc = get_chat_side_table_service()
    svc.update_from_delta(account_id=account_id, session_id=session_id, delta=firestore_delta)

    return {"status": "applied"}
