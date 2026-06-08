"""Pydantic models for the Early Release signup gate.

Spec: docs/design/components/data-management/projects/DM-PRD-11-early-release-signup-gate.md §4.1, §4.2
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EarlyReleaseConfig(BaseModel):
    """Singleton config document stored at ``app_config/early_release``.

    ``code`` is stored plaintext — the admin must read it to distribute it to
    early-access participants.  It is **not** a data-access boundary; brute-force
    resistance comes from the IP rate-limiter on the validate endpoint and the
    constant-time compare in ``EarlyReleaseService.validate``.
    """

    code: Annotated[str, Field(min_length=1, max_length=256)]
    is_active: bool
    expires_at: datetime | None = None
    updated_by: str
    updated_at: datetime


class EarlyReleaseRedemption(BaseModel):
    """Redemption log document stored at ``early_release_redemptions/{user_id}``.

    Keyed by ``user_id`` so repeated writes are idempotent (the first
    ``redeemed_at`` timestamp is preserved on retry via ``.create()``).
    """

    user_id: str
    email: EmailStr
    org_id: str
    redeemed_at: datetime


class EarlyReleaseWriteRequest(BaseModel):
    """Validated payload for ``EarlyReleaseService.set_code``.

    ``extra="ignore"`` so a client that sends unexpected fields does not receive
    a 422 (mirrors ``FeatureFlagWriteRequest``).
    """

    model_config = ConfigDict(extra="ignore")

    code: Annotated[str, Field(min_length=1, max_length=256)]
    is_active: bool | None = None
    expires_at: datetime | None = None


class EarlyReleaseAdminUpdateRequest(BaseModel):
    """Validated payload for a partial PUT on the early-release config.

    All fields are optional so the caller can patch only the fields that
    need to change.  ``extra="ignore"`` mirrors ``EarlyReleaseWriteRequest``.
    """

    model_config = ConfigDict(extra="ignore")

    code: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None


class EarlyReleaseAdminConfigResponse(BaseModel):
    """GET response that combines the live ``EarlyReleaseConfig`` with a
    pre-computed redemption count so the admin UI needs only one request.
    """

    code: Annotated[str, Field(min_length=1, max_length=256)]
    is_active: bool
    expires_at: datetime | None = None
    updated_by: str
    updated_at: datetime
    redemption_count: int


class EarlyReleaseRedemptionsListResponse(BaseModel):
    """Paginated list response for the redemption log endpoint."""

    redemptions: list[EarlyReleaseRedemption]
    total: int
    next_cursor: str | None = None
