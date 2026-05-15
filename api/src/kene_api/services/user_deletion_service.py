"""User-data purge orchestrator and registry of user-scoped data.

This module owns:

1. ``USER_SUBCOLLECTIONS`` — canonical list of ``users/{user_id}/{name}/``
   subcollection names purged on user deletion.
2. ``USER_GCS_PREFIXES`` — user-scoped GCS prefixes purged on user deletion
   (empty in v1).
3. ``delete_user_data(user_id, *, actor)`` — the 6-step purge orchestrator
   called by ``DELETE /api/v1/users/{user_id}`` (DM-53) and covered by the
   no-orphans integration test (DM-54).

Registry-update contract (PRD §6 AC-11)
----------------------------------------
Any future PRD that adds a new ``users/{user_id}/{name}/`` subcollection write
**must** append the subcollection name to ``USER_SUBCOLLECTIONS`` in this
module.  Similarly, any user-scoped GCS prefix introduced after v1 must be
added to ``USER_GCS_PREFIXES``.

CI grep enforcement of this contract is owned by DM-PRD-06 §4.2.

Spec: docs/design/components/data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md §4.2
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from google.cloud import firestore as firestore_module

from ..auth.models import UserContext
from ..dependencies import get_firestore_client
from ..models.user_deletion import UserDeletionResult
from ..services.storage_service import get_storage_service

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentReference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Soft-import cross-component hooks not yet shipped.
# Each import block tries to load the hook; falls back to None.
# Call sites guard with ``if <hook> is not None`` so the orchestrator
# runs today and the calls light up automatically when the modules land.
# ---------------------------------------------------------------------------

try:
    from ..integrations.hooks import (
        on_user_removed as _on_user_removed,  # type: ignore[import]
    )
except ImportError:
    _on_user_removed = None  # type: ignore[assignment]

try:
    from ..services.audit_service import (
        write_audit as _write_audit,  # type: ignore[import]
    )
except ImportError:
    _write_audit = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# User-scoped Firestore subcollections
#
# Each entry is the bare subcollection name under users/{user_id}/.
# One comment per entry cites the owning PRD or source file per AC-11.
# ---------------------------------------------------------------------------

USER_SUBCOLLECTIONS: list[str] = [
    "notification_status",  # firestore_notification_repository.py
    "preferences",  # firestore_notification_repository.py + routers/users.py (default_preferences seed)
    "chat_categories",  # CH-PRD-03
    "notifications",  # routers/users.py — NotificationSettings seed on user creation
    "security",  # routers/users.py — SecuritySettings seed on user creation
]

# ---------------------------------------------------------------------------
# User-scoped GCS prefixes
#
# Empty in v1 — no user-scoped GCS data exists today.
# Add via separate PR when any future user-scoped GCS data is introduced.
# ---------------------------------------------------------------------------

USER_GCS_PREFIXES: list[str] = []


# ---------------------------------------------------------------------------
# Private step helpers
#
# Each helper is fully self-contained: it catches its own exceptions, logs
# the failure, appends to result.errors, and returns normally so the caller
# (delete_user_data) can proceed to the next step unconditionally.
# ---------------------------------------------------------------------------


async def _resolve_member_rows(
    db: firestore_module.Client,
    user_id: str,
) -> tuple[list[DocumentReference], list[DocumentReference]]:
    """Query collection-group 'members' to find all rows for this user.

    Returns (org_member_refs, account_member_refs).  Uses the
    (user_id ASC, parent_kind ASC) collection-group index shipped by
    DM-PRD-00 (deployment/firestore.indexes.json:114-126).
    """

    def _stream_all() -> tuple[list[DocumentReference], list[DocumentReference]]:
        org_refs: list[DocumentReference] = []
        account_refs: list[DocumentReference] = []
        members_group = db.collection_group("members")

        for doc in members_group.where("user_id", "==", user_id).where(
            "parent_kind", "==", "organization"
        ).stream():
            org_refs.append(doc.reference)

        for doc in members_group.where("user_id", "==", user_id).where(
            "parent_kind", "==", "account"
        ).stream():
            account_refs.append(doc.reference)

        return org_refs, account_refs

    return await asyncio.to_thread(_stream_all)


async def _fire_integrations_hook(
    account_id: str,
    user_id: str,
    result: UserDeletionResult,
) -> None:
    """Call on_user_removed for one account and record the outcome.

    Increments ``result.integrations_hook_fired`` on success, appends to
    ``result.errors`` on failure.  Never raises.
    """
    if _on_user_removed is None:
        return
    try:
        await _on_user_removed(account_id=account_id, user_id=user_id)
        result.integrations_hook_fired += 1
    except Exception as exc:
        logger.exception(
            "[user_deletion] on_user_removed failed account_id=%s user_id=%s",
            account_id,
            user_id,
        )
        result.errors.append(f"integrations_hook[{account_id}]: {exc}")


async def _delete_members(
    org_refs: list[DocumentReference],
    account_refs: list[DocumentReference],
    result: UserDeletionResult,
) -> None:
    """Delete all discovered org + account member rows.

    Increments ``result.member_rows_deleted`` per successful deletion.
    """
    all_refs = [*org_refs, *account_refs]
    for ref in all_refs:
        try:
            await asyncio.to_thread(ref.delete)
            result.member_rows_deleted += 1
        except Exception as exc:
            logger.exception(
                "[user_deletion] failed to delete member row path=%s",
                ref.path,
            )
            result.errors.append(f"member_delete[{ref.path}]: {exc}")


async def _purge_user_doc(
    db: firestore_module.Client,
    user_id: str,
    result: UserDeletionResult,
) -> None:
    """Recursively delete users/{user_id} and all its subcollections.

    Sets ``result.user_doc_deleted = True`` when the call returns without
    raising, regardless of whether the document existed beforehand (per
    PRD AC-10 idempotency contract).
    """
    try:
        user_ref = db.collection("users").document(user_id)
        await asyncio.to_thread(db.recursive_delete, user_ref)
        result.user_doc_deleted = True
    except Exception as exc:
        logger.exception(
            "[user_deletion] recursive_delete failed for users/%s", user_id
        )
        result.errors.append(f"user_doc_purge: {exc}")


async def _purge_gcs(
    user_id: str,
    result: UserDeletionResult,
) -> None:
    """Purge user-scoped GCS prefixes registered in USER_GCS_PREFIXES.

    No-op in v1 (USER_GCS_PREFIXES is empty).  Wired to
    StorageService.delete_user_prefix via getattr so a missing v1 method
    does not produce a false-positive error.
    """
    if not USER_GCS_PREFIXES:
        return
    for prefix_template in USER_GCS_PREFIXES:
        prefix = prefix_template.format(user_id=user_id)
        try:
            storage = get_storage_service()
            delete_fn = getattr(storage, "delete_user_prefix", None)
            if delete_fn is not None:
                await delete_fn(prefix)
                result.gcs_prefixes_purged += 1
        except Exception as exc:
            logger.exception(
                "[user_deletion] GCS prefix purge failed prefix=%s", prefix
            )
            result.errors.append(f"gcs_purge[{prefix}]: {exc}")


async def _write_audit_best_effort(
    actor: UserContext,
    org_refs: list[DocumentReference],
    user_id: str,
) -> None:
    """Write a best-effort audit entry to the primary org's audit subcollection.

    Skipped silently when:
    - the user had no org memberships (org_refs is empty), OR
    - write_audit has not yet shipped (_write_audit is None).

    Any exception is logged as a warning and does not propagate.
    """
    if not org_refs or _write_audit is None:
        return
    # Best-effort: pick the first org as the primary.
    # ref path is organizations/{org_id}/members/{user_id}
    # TODO: If multi-org audit is ever needed, iterate org_refs and emit one entry per org.
    primary_org_id: str = org_refs[0].parent.parent.id
    try:
        await _write_audit(
            parent_kind="organization",
            parent_id=primary_org_id,
            audit_subcollection="account_member_audit",
            resource_type="org_member",
            resource_id=user_id,
            action="remove",
            actor=actor,
            before_state={"user_id": user_id},
            after_state=None,
        )
    except Exception as exc:
        logger.warning(
            "[user_deletion] audit write failed for user_id=%s: %s",
            user_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


async def delete_user_data(
    user_id: str,
    *,
    actor: UserContext,
) -> UserDeletionResult:
    """Purge all KEN-E-side data for a user.

    Executes the 6-step sequence from DM-PRD-05 §4.2 in order.  Each step is
    wrapped so a single-step exception is logged and execution continues —
    the orchestrator never rolls back.  Re-running on an already-purged user
    is a no-op (counts stay at 0, user_doc_deleted=True).

    Args:
        user_id: The Firebase/Firestore user ID to purge.
        actor: The authenticated super-admin triggering the purge.

    Returns:
        UserDeletionResult with counts and any per-step errors.
    """
    if not actor.is_super_admin:
        raise PermissionError(
            f"delete_user_data requires a super-admin actor; got {actor.email!r}"
        )

    result = UserDeletionResult(user_id=user_id)
    db = get_firestore_client()

    # Step 1 — Discover affected org + account member rows.
    logger.info("[user_deletion] step 1:discover_members starting user_id=%s", user_id)
    org_refs: list[DocumentReference] = []
    account_refs: list[DocumentReference] = []
    try:
        org_refs, account_refs = await _resolve_member_rows(db, user_id)
        logger.info(
            "[user_deletion] step 1:discover_members completed user_id=%s "
            "org_rows=%d account_rows=%d",
            user_id,
            len(org_refs),
            len(account_refs),
        )
    except Exception as exc:
        logger.exception(
            "[user_deletion] step 1:discover_members failed user_id=%s", user_id
        )
        result.errors.append(f"discover_members: {exc}")

    # Step 2 — Fire on_user_removed hook per affected account (sequential).
    logger.info(
        "[user_deletion] step 2:fire_integrations_hook starting user_id=%s", user_id
    )
    for ref in account_refs:
        account_id: str = ref.parent.parent.id
        await _fire_integrations_hook(account_id, user_id, result)
    logger.info(
        "[user_deletion] step 2:fire_integrations_hook completed user_id=%s fired=%d",
        user_id,
        result.integrations_hook_fired,
    )

    # Step 3 — Delete all member rows (org + account).
    logger.info(
        "[user_deletion] step 3:delete_members starting user_id=%s", user_id
    )
    await _delete_members(org_refs, account_refs, result)
    logger.info(
        "[user_deletion] step 3:delete_members completed user_id=%s deleted=%d",
        user_id,
        result.member_rows_deleted,
    )

    # Step 4 — Recursively delete users/{user_id} + all subcollections.
    logger.info("[user_deletion] step 4:purge_user_doc starting user_id=%s", user_id)
    await _purge_user_doc(db, user_id, result)
    logger.info(
        "[user_deletion] step 4:purge_user_doc completed user_id=%s deleted=%s",
        user_id,
        result.user_doc_deleted,
    )

    # Step 5 — GCS prefix purge (no-op in v1).
    logger.info("[user_deletion] step 5:purge_gcs starting user_id=%s", user_id)
    await _purge_gcs(user_id, result)
    logger.info(
        "[user_deletion] step 5:purge_gcs completed user_id=%s purged=%d",
        user_id,
        result.gcs_prefixes_purged,
    )

    # Step 6 — Best-effort audit entry.
    logger.info(
        "[user_deletion] step 6:write_audit starting user_id=%s", user_id
    )
    await _write_audit_best_effort(actor, org_refs, user_id)
    logger.info(
        "[user_deletion] step 6:write_audit completed user_id=%s", user_id
    )

    return result
