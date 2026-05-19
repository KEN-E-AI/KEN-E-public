"""Admin Feature Flags router — super-admin CRUD for feature flag management.

Spec: docs/design/components/feature-flags/projects/FF-PRD-02-admin-api-and-ui.md §4, §6

Security model (README §7.6):
- All endpoints require the caller to hold the super_admin role.
- Non-super-admins receive a flat 403 {"error": "super_admin_required"} from the
  global SuperAdminRequiredError handler registered in main.py.
- Unauthenticated requests receive a 401 from the upstream get_current_user dep.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth.dependencies import require_super_admin
from ..dependencies import get_feature_flag_service
from ..models.feature_flag_models import FeatureFlag, FlagKeyStr
from ..services.feature_flag_service import FeatureFlagService

if TYPE_CHECKING:
    from ..auth.dependencies import UserContext

router = APIRouter(
    prefix="/api/v1/admin/feature-flags",
    tags=["admin-feature-flags"],
)


class AdminFeatureFlagListResponse(BaseModel):
    """Response envelope for GET / (list all flags).

    Wraps the list rather than returning a bare array so a future `total` /
    `next_cursor` field can be added without a breaking API change (PRD §4).
    """

    flags: list[FeatureFlag]


@router.get("", response_model=AdminFeatureFlagListResponse)
async def list_flags(
    _admin: UserContext = Depends(require_super_admin),
    service: FeatureFlagService = Depends(get_feature_flag_service),
) -> AdminFeatureFlagListResponse:
    """List all feature flags sorted by updated_at descending (super-admin only)."""
    flags = await service.list_flags()
    return AdminFeatureFlagListResponse(flags=flags)


@router.get("/{key}", response_model=FeatureFlag)
async def get_flag(
    key: FlagKeyStr,
    _admin: UserContext = Depends(require_super_admin),
    service: FeatureFlagService = Depends(get_feature_flag_service),
) -> FeatureFlag:
    """Get a single feature flag by key (super-admin only).

    Returns 404 when the flag does not exist.
    Key is validated against FLAG_KEY_REGEX before the handler executes.
    """
    flag = await service.get_flag(key)
    if flag is None:
        raise HTTPException(
            status_code=404,
            detail=f"Feature flag '{key}' not found",
        )
    return flag


# FF-13: mutating endpoints (POST / PUT / DELETE) land here.
