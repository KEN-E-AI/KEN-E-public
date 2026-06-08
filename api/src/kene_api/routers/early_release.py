"""Public Early Release code validation endpoint.

Spec: docs/design/components/data-management/projects/DM-PRD-11-early-release-signup-gate.md §6
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..auth.rate_limiting import early_release_rate_limiter
from ..dependencies import get_early_release_service

if TYPE_CHECKING:
    from ..services.early_release_service import EarlyReleaseService

router = APIRouter(prefix="/api/v1/early-release", tags=["early-release"])


class ValidateCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class ValidateCodeResponse(BaseModel):
    valid: bool


@router.post("/validate", response_model=ValidateCodeResponse)
async def validate_early_release_code(
    request: Request,
    body: ValidateCodeRequest,
    service: EarlyReleaseService = Depends(get_early_release_service),
) -> ValidateCodeResponse:
    """Validate a shared Early Release code without consuming or recording it.

    Returns a uniform ``{valid: false}`` for wrong, missing, inactive, or
    expired codes — never raises 403/404 so callers cannot enumerate whether
    a config exists.  Rate-limited per IP to resist brute-force attempts.
    """
    await early_release_rate_limiter.check_rate_limit(request, ctx=None)
    result = await service.validate(body.code)
    return ValidateCodeResponse(valid=result)
