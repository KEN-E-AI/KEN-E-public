"""Admin Early Release router — super-admin CRUD for the shared Early Release code.

Spec: docs/design/components/data-management/projects/DM-PRD-11-early-release-signup-gate.md §6, §4.5

Security model:
- All endpoints require the caller to hold the super_admin role.
- Non-super-admins receive a flat 403 {"error": "super_admin_required"} from the
  global SuperAdminRequiredError handler registered in main.py.
- Unauthenticated requests receive a 401 from the upstream get_current_user dep.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.audit_logger import SecurityEventType, get_audit_logger
from ..auth.dependencies import require_super_admin
from ..dependencies import get_early_release_service
from ..models.early_release_models import (
    EarlyReleaseAdminConfigResponse,
    EarlyReleaseAdminUpdateRequest,
    EarlyReleaseRedemptionsListResponse,
)
from ..services.early_release_service import (
    EarlyReleaseConfigNotFoundError,
    EarlyReleaseService,
)

if TYPE_CHECKING:
    from ..auth.dependencies import UserContext

router = APIRouter(
    prefix="/api/v1/admin/early-release-code",
    tags=["admin-early-release"],
)


@router.get("", response_model=EarlyReleaseAdminConfigResponse)
async def get_early_release_config(
    _admin: UserContext = Depends(require_super_admin),
    service: EarlyReleaseService = Depends(get_early_release_service),
) -> EarlyReleaseAdminConfigResponse:
    """Return the current Early Release code config with a live redemption count.

    Returns 404 when no config document exists yet (``set_code`` has never been called).
    """
    config = await service.get_config()
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="early_release_config_not_found",
        )
    redemption_count = await service.count_redemptions()
    return EarlyReleaseAdminConfigResponse(
        code=config.code,
        is_active=config.is_active,
        expires_at=config.expires_at,
        updated_by=config.updated_by,
        updated_at=config.updated_at,
        redemption_count=redemption_count,
    )


@router.put("", response_model=EarlyReleaseAdminConfigResponse)
async def update_early_release_config(
    body: EarlyReleaseAdminUpdateRequest,
    _admin: UserContext = Depends(require_super_admin),
    service: EarlyReleaseService = Depends(get_early_release_service),
) -> EarlyReleaseAdminConfigResponse:
    """Update the Early Release code config.

    Routing rules (per DM-PRD-11 §4.6 and the approved implementation plan):

    - ``code`` provided → rotate the code via ``set_code`` in a single write.  An
      explicit ``is_active=False`` in the same body rotates the code straight into
      a disabled state (``set_code(..., is_active=False)``) — one atomic write, so
      a failure can never leave a freshly-rotated code live.
    - ``code`` absent, ``is_active`` provided → flip the kill switch via ``set_active``.
    - ``code`` absent, only ``expires_at`` provided → 422 (no standalone set-expiry
      primitive in the service layer at v1).
    - Empty body ({}) → 422.

    Every mutation emits a ``EARLY_RELEASE_CODE_CHANGED`` audit event with
    ``severity="CRITICAL"``.  The plaintext code is **never** written into the
    audit details.
    """
    # Reject expires_at without code — there is no standalone set-expiry primitive
    # in the service layer at v1.  The admin can always rotate with the current code
    # to update expiry (the GET reveals the current code).  Checked before any
    # service call so a bad request never touches Firestore.
    if body.expires_at is not None and body.code is None:
        raise HTTPException(
            status_code=422,
            detail="'expires_at' requires 'code' to be provided; rotate the code to update expiry.",
        )

    actor_id = _admin.user_id

    if body.code is not None:
        # Rotate the code in a single write.  is_active defaults to True; an
        # explicit False disables the rotated code in the same atomic write.
        disable = body.is_active is False
        before = await service.get_config()
        updated = await service.set_code(
            body.code,
            actor_id=actor_id,
            expires_at=body.expires_at,
            is_active=not disable,
        )
        action = "rotate_with_disable" if disable else "set_code"
    elif body.is_active is not None:
        # Kill-switch-only update (no code rotation).
        before = await service.get_config()
        try:
            updated = await service.set_active(body.is_active, actor_id=actor_id)
        except EarlyReleaseConfigNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="early_release_config_not_found",
            ) from exc
        action = "set_active"
    else:
        # Empty body — no actionable field. Raised before any service call.
        raise HTTPException(
            status_code=422,
            detail="At least one of 'code' or 'is_active' must be provided.",
        )

    before_snapshot = (
        {"is_active": before.is_active, "expires_at": before.expires_at}
        if before is not None
        else {"is_active": None, "expires_at": None}
    )
    after_snapshot = {"is_active": updated.is_active, "expires_at": updated.expires_at}

    await get_audit_logger().log_event(
        event_type=SecurityEventType.EARLY_RELEASE_CODE_CHANGED,
        user_id=actor_id,
        email=_admin.email,
        details={
            "action": action,
            "code_changed": action != "set_active",
            "before": before_snapshot,
            "after": after_snapshot,
        },
        severity="CRITICAL",
    )

    redemption_count = await service.count_redemptions()
    return EarlyReleaseAdminConfigResponse(
        code=updated.code,
        is_active=updated.is_active,
        expires_at=updated.expires_at,
        updated_by=updated.updated_by,
        updated_at=updated.updated_at,
        redemption_count=redemption_count,
    )


@router.get("/redemptions", response_model=EarlyReleaseRedemptionsListResponse)
async def list_redemptions(
    limit: int = Query(50, ge=1, le=50, description="Max redemptions per page"),
    cursor: str | None = Query(
        None, description="user_id of the last entry from the prior page"
    ),
    _admin: UserContext = Depends(require_super_admin),
    service: EarlyReleaseService = Depends(get_early_release_service),
) -> EarlyReleaseRedemptionsListResponse:
    """Return a paginated list of Early Release redemptions, newest-first.

    The ``cursor`` is the opaque ``user_id`` of the last entry from the prior
    page.  A stale cursor (user whose redemption doc was deleted) returns an
    empty list with ``next_cursor=null``.
    """
    redemptions, next_cursor = await service.list_redemptions(limit, cursor)
    total = await service.count_redemptions()
    return EarlyReleaseRedemptionsListResponse(
        redemptions=redemptions,
        total=total,
        next_cursor=next_cursor,
    )
