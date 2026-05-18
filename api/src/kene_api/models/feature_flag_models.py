"""Pydantic models for the Feature Flags component.

Spec: docs/design/components/feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md §4
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

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
