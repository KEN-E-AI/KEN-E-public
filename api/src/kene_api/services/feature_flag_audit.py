"""Audit-entry writer for the Feature Flags component.

Exposes:
  - AuditAction       — Literal type alias for the four mutation action values.
  - compute_flag_diff — Pure-logic shallow diff between two FeatureFlag states.
  - record_audit      — Async writer that persists one audit row to Firestore.

Spec: docs/design/components/feature-flags/projects/FF-PRD-02-admin-api-and-ui.md
      §5.1 (diff rules), §7 AC-4, §4 (FeatureFlagAuditEntry shape).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from google.cloud import firestore

from ..models.feature_flag_models import FeatureFlag

logger = logging.getLogger(__name__)

# Action values that produce an audit row. Exported so callers (B2) can import
# this alias for type-safe action arguments rather than repeating the Literal.
AuditAction = Literal["create", "update", "delete", "toggle_active"]

# Top-level FeatureFlag fields that carry auto-managed timestamps. Excluded from
# the diff so a no-op PUT (only timestamps change) produces an empty diff and
# correctly skips the audit write.
_EXCLUDED_FIELDS: frozenset[str] = frozenset({"created_at", "updated_at"})

# Sentinel that distinguishes "key absent from dict" from "key present with value None".
# Needed so a create (before=None → before_dict={}) correctly records fields that the
# new flag sets to None — both "absent" and "None" hash differently via object identity.
_ABSENT = object()


def compute_flag_diff(
    before: FeatureFlag | None,
    after: FeatureFlag | None,
) -> dict[str, dict[str, Any]]:
    """Return a shallow diff between two FeatureFlag states.

    Semantics (per PRD §5.1):
    - Only top-level changed keys appear in the result.
    - Nested ``targeting_rules`` changes produce a single ``targeting_rules``
      entry (the whole sub-dict) — not a recursive diff.
    - ``created_at`` and ``updated_at`` are always excluded.
    - An unchanged doc (or both None) returns an empty dict.

    Args:
        before: The flag state before the mutation, or None for a create.
        after:  The flag state after the mutation, or None for a delete.

    Returns:
        ``{field: {"before": old_value, "after": new_value}}`` for every
        changed top-level field (timestamps excluded).
    """
    if before is None and after is None:
        return {}

    before_dict: dict[str, Any] = (
        {k: v for k, v in before.model_dump(mode="json").items()
         if k not in _EXCLUDED_FIELDS}
        if before is not None
        else {}
    )
    after_dict: dict[str, Any] = (
        {k: v for k, v in after.model_dump(mode="json").items()
         if k not in _EXCLUDED_FIELDS}
        if after is not None
        else {}
    )

    all_keys = set(before_dict) | set(after_dict)
    diff: dict[str, dict[str, Any]] = {}
    for key in all_keys:
        old_val = before_dict.get(key, _ABSENT)
        new_val = after_dict.get(key, _ABSENT)
        # Sentinel presence is checked separately from value equality so that
        # the "one side absent" case (create/delete) is always caught regardless
        # of the field's value type (including types where __eq__ is irregular).
        old_is_absent = old_val is _ABSENT
        new_is_absent = new_val is _ABSENT
        if old_is_absent != new_is_absent:
            changed = True
        else:
            changed = old_val != new_val
        if changed:
            diff[key] = {
                "before": None if old_is_absent else old_val,
                "after": None if new_is_absent else new_val,
            }

    return diff


async def record_audit(
    db: firestore.Client,
    flag_key: str,
    actor_email: str,
    action: AuditAction,
    diff: dict[str, dict[str, Any]],
) -> str | None:
    """Write one audit row to ``feature_flag_audit/{audit_id}``.

    Skips the write and returns ``None`` when ``diff`` is empty (unchanged-doc
    rule — PRD §5.1).

    On Firestore failure the exception is caught, logged at ERROR with the
    fixed payload ``{flag_key, action, error_type}`` (no PII — actor_email is
    intentionally excluded from the log per FF-PRD-02 §5.1 no-PII convention), and
    ``None`` is returned. Audit failures must never propagate to the caller's
    main mutation path.

    Args:
        db:          Firestore client (injected; do not use module-level client).
        flag_key:    The snake_case key of the flag being mutated.
        actor_email: Email of the super-admin performing the mutation.
        action:      One of "create", "update", "delete", "toggle_active".
        diff:        Shallow diff produced by compute_flag_diff.

    Returns:
        The audit document ID (``{iso_ts}_{uuid8}``) on success, or ``None``
        when the diff is empty or when the Firestore write fails.
    """
    if not diff:
        return None

    now = datetime.now(timezone.utc)
    iso_now = now.isoformat()
    audit_id = f"{iso_now}_{uuid4().hex[:8]}"

    body: dict[str, Any] = {
        "audit_id": audit_id,
        "flag_key": flag_key,
        "actor_email": actor_email,
        "action": action,
        "diff": diff,
        "created_at": iso_now,
    }

    # feature_flag_audit is a Shape C global collection (not account-scoped) —
    # feature flags are platform-admin tooling with no per-tenant scoping.
    # See docs/design/components/feature-flags/README.md §7.5 for rationale.
    try:
        await asyncio.to_thread(
            db.collection("feature_flag_audit").document(audit_id).set,
            body,
        )
        return audit_id
    except Exception as exc:
        logger.error(
            "feature_flag_audit_write_error",
            extra={
                "flag_key": flag_key,
                "action": action,
                "error_type": type(exc).__name__,
            },
        )
        return None
