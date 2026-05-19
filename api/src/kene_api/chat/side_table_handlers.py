"""Request-level handler for the internal side-table update endpoint.

Provides idempotency via a Firestore `chat_idempotency_keys` collection:
  chat_idempotency_keys/{sha256(idempotency_key)}

Wire-protocol conventions for delta field values:
  {"_increment": n}        → firestore.Increment(n)
  {"_isoformat": "..."}   → datetime.fromisoformat("...")  (used for timestamp fields)
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

# Fields the internal endpoint is permitted to write. Unknown keys are stripped
# with a warning to prevent buggy or malicious callers from corrupting ownership
# fields (user_id, organization_id) or lifecycle fields (deleted_at).
_ALLOWED_DELTA_FIELDS: frozenset[str] = frozenset({
    "last_agent_started_at",
    "last_agent_stopped_at",
    "last_agent_message_at",
    "updated_at",
    "last_message_preview",
    "input_tokens_total",
    "output_tokens_total",
    "reasoning_tokens_total",
    "tool_call_count",
    "message_count",
    "current_context_tokens",
    # Compaction fields written by SessionTurnAccumulator (CH-12):
    "latest_summary",
    "summary_updated_at",
    "compaction_count",
})


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _reconstruct_increments(delta: dict[str, Any]) -> dict[str, Any]:
    """Convert wire sentinels to Firestore-native values.

    Supported sentinels:
      {"_increment": n}      → firestore.Increment(n)
      {"_isoformat": "..."}  → datetime.fromisoformat("...")
    """
    result: dict[str, Any] = {}
    for k, v in delta.items():
        if isinstance(v, dict) and set(v.keys()) == {"_increment"}:
            result[k] = firestore.Increment(v["_increment"])
        elif isinstance(v, dict) and set(v.keys()) == {"_isoformat"}:
            result[k] = datetime.fromisoformat(v["_isoformat"])
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

    # Strip disallowed fields before writing to prevent accidental or malicious
    # corruption of ownership/lifecycle fields (user_id, deleted_at, etc.).
    unknown_keys = set(delta.keys()) - _ALLOWED_DELTA_FIELDS
    if unknown_keys:
        logger.warning("Side-table update stripped disallowed delta keys: %s", unknown_keys)
        delta = {k: v for k, v in delta.items() if k in _ALLOWED_DELTA_FIELDS}

    if not delta:
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

    reconstructed = _reconstruct_increments(delta)
    svc = get_chat_side_table_service()
    svc.update_from_delta(account_id=account_id, session_id=session_id, delta=reconstructed)

    return {"status": "applied"}
