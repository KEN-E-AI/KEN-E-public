"""Feature Flags public evaluation endpoint.

Spec: docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md §4, §6
API contract: POST /api/v1/feature-flags/evaluate

Security model (README §7.6):
- Any authenticated user may call this endpoint.
- EvaluationContext is built server-side from the Firebase JWT; the request body
  carries ONLY flag_keys.  Body fields named user_id / organization_id /
  account_id are silently dropped by Pydantic's default extra="ignore" — they
  never reach the evaluator.
- The response contains only {key, enabled, reason} per FlagEvaluation; the
  underlying flag config (default_enabled, targeting_rules, owner, …) is never
  returned.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from ..auth.user_context import UserContext, get_current_user_context
from ..dependencies import get_feature_flag_service
from ..models.feature_flag_models import (
    EvaluateRequest,
    EvaluateResponse,
    EvaluationContext,
)
from ..services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/feature-flags",
    tags=["feature-flags"],
)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_flags(
    req: EvaluateRequest,
    user: UserContext = Depends(get_current_user_context),
    service: FeatureFlagService = Depends(get_feature_flag_service),
) -> EvaluateResponse:
    """Evaluate a batch of feature flags for the authenticated user's context.

    EvaluationContext is derived entirely from the verified Firebase token —
    callers cannot influence which identity is evaluated by sending identity
    fields in the request body (they are silently ignored by Pydantic).

    organization_id and account_id are not populated for MVP because the
    Firebase JWT does not carry an active-account claim and no selection
    mechanism exists in the API yet (FF-PRD-01 Decision 1).  Email-domain /
    email-allowlist targeting and user-bucketed rollouts are fully functional.
    """
    # FF-6 hardening: this endpoint requires a real email claim.  Reject
    # empty / whitespace-only emails up front so an unauthenticated identity
    # cannot resolve to "everyone-default" by accident.  EvaluationContext
    # itself accepts any string (it's used internally for synthetic users
    # like the chat-sidebar load-test fixture); the strict gate lives here.
    if not (user.email or "").strip():
        logger.warning(
            "feature_flags_invalid_identity_claim",
            extra={"user_id": user.user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no valid email claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        ctx = EvaluationContext(
            user_id=user.user_id,
            user_email=user.email,
            organization_id=None,
            account_id=None,
        )
    except ValidationError:
        # Defensive: user_id has min_length=1, so a UserContext with an empty
        # uid still raises here.  Same 401 response — the token isn't usable.
        logger.warning(
            "feature_flags_invalid_identity_claim",
            extra={"user_id": user.user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no valid email claim",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    evaluations = await service.evaluate_batch(req.flag_keys, ctx)
    return EvaluateResponse(evaluations=evaluations)
