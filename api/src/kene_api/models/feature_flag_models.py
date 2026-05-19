"""Pydantic models for the Feature Flags component.

Spec: docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md §4
      docs/design/components/feature-flags/projects/FF-PRD-02-admin-api-and-ui.md §4
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

FLAG_KEY_REGEX = r"^[a-z0-9][a-z0-9_]{2,63}$"


class TargetingRules(BaseModel):
    user_emails: list[str] = Field(default_factory=list)
    email_domains: list[str] = Field(default_factory=list)
    organization_ids: list[str] = Field(default_factory=list)
    account_ids: list[str] = Field(default_factory=list)
    rollout_percentage: int = Field(default=0, ge=0, le=100)

    @field_validator("user_emails", "email_domains")
    @classmethod
    def _lowercase(cls, v: list[str]) -> list[str]:
        return [s.strip().lower() for s in v]


class FeatureFlag(BaseModel):
    key: str = Field(pattern=FLAG_KEY_REGEX)
    description: str
    default_enabled: bool
    is_active: bool = True
    targeting_rules: TargetingRules = Field(default_factory=TargetingRules)
    bucketing_entity: Literal["account", "organization", "user"] = "account"
    owner: str
    expected_ga_release: str | None = None
    created_at: datetime
    updated_at: datetime


class EvaluationContext(BaseModel):
    user_id: str = Field(min_length=1)
    user_email: EmailStr
    organization_id: str | None = None
    account_id: str | None = None


class FlagEvaluation(BaseModel):
    key: str
    enabled: bool
    reason: Literal[
        "kill_switch",
        "email_match",
        "domain_match",
        "org_match",
        "account_match",
        "rollout",
        "default",
        "unknown_flag",
    ]


FlagKeyStr = Annotated[str, Field(pattern=FLAG_KEY_REGEX)]


class EvaluateRequest(BaseModel):
    flag_keys: list[FlagKeyStr] = Field(min_length=1, max_length=100)


class EvaluateResponse(BaseModel):
    evaluations: dict[str, FlagEvaluation]


# ---------------------------------------------------------------------------
# FF-15: Audit read models (FF-PRD-02 §4)
# ---------------------------------------------------------------------------

# Action values that produce an audit row. Mirrors AuditAction in
# feature_flag_audit.py — defined here to avoid a circular import since
# feature_flag_audit.py imports FeatureFlag from this module.
AuditActionLiteral = Literal["create", "update", "delete", "toggle_active"]


class FeatureFlagAuditEntry(BaseModel):
    """A single audit log entry for a feature flag mutation.

    Produced by record_audit (feature_flag_audit.py) and returned by
    GET /api/v1/admin/feature-flags/{key}/audit.

    Spec: FF-PRD-02 §4 (FeatureFlagAuditEntry shape).
    created_at is an ISO-8601 string — stored as a string by record_audit
    and passed through without server-side datetime parsing (pure pass-through).
    """

    audit_id: str
    flag_key: str
    actor_email: EmailStr
    action: AuditActionLiteral
    diff: dict[str, dict[str, Any]]
    created_at: str  # ISO-8601


class FlagAuditResponse(BaseModel):
    """Paginated response envelope for GET /{key}/audit.

    next_cursor is None when no further pages exist; otherwise it equals
    the audit_id of the last entry on the current page (opaque to callers).

    Spec: FF-PRD-02 §4 — { entries: FeatureFlagAuditEntry[], next_cursor: string | null }
    """

    entries: list[FeatureFlagAuditEntry]
    next_cursor: str | None
