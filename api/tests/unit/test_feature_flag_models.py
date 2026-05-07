"""Unit tests for ``models.feature_flag_models``.

Covers Pydantic model shape validation and regex enforcement for the Feature
Flags component.  These tests exercise models directly — no HTTP layer, no
database, no external services.

AC-1  All six models construct with valid inputs.
AC-2  FLAG_KEY_REGEX enforcement on FeatureFlag.key.
AC-3  _lowercase field_validator on TargetingRules.user_emails / email_domains.
AC-4  FeatureFlag.bucketing_entity Literal validation.
AC-5  FlagEvaluation.reason Literal validation.
AC-6  EvaluateRequest.flag_keys min/max length.
AC-7  TargetingRules.rollout_percentage bounds.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from src.kene_api.models.feature_flag_models import (
    EvaluateRequest,
    EvaluateResponse,
    EvaluationContext,
    FeatureFlag,
    FlagEvaluation,
    TargetingRules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_flag(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "key": "test_flag",
        "description": "A test flag",
        "default_enabled": False,
        "owner": "dev@ken-e.ai",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


def _valid_evaluation(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "key": "test_flag",
        "enabled": True,
        "reason": "default",
    }
    base.update(overrides)
    return base


def _valid_context(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "user_id": "uid_123",
        "user_email": "alice@ken-e.ai",
        "organization_id": None,
        "account_id": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-1: All six models construct with valid inputs
# ---------------------------------------------------------------------------


class TestAllModelsConstructWithValidInputs:
    """AC-1: Every model accepts well-formed data."""

    def test_targeting_rules_default_construction(self) -> None:
        rules = TargetingRules()

        assert rules.user_emails == []
        assert rules.email_domains == []
        assert rules.organization_ids == []
        assert rules.account_ids == []
        assert rules.rollout_percentage == 0

    def test_feature_flag_construction(self) -> None:
        flag = FeatureFlag(**_valid_flag())

        assert flag.key == "test_flag"
        assert flag.default_enabled is False
        assert flag.is_active is True
        assert flag.bucketing_entity == "account"

    def test_evaluation_context_construction(self) -> None:
        ctx = EvaluationContext(**_valid_context())

        assert ctx.user_id == "uid_123"
        assert ctx.organization_id is None
        assert ctx.account_id is None

    def test_evaluation_context_optional_ids_default_to_none(self) -> None:
        ctx = EvaluationContext(user_id="uid_123", user_email="alice@ken-e.ai")

        assert ctx.organization_id is None
        assert ctx.account_id is None

    def test_evaluation_context_with_ids(self) -> None:
        ctx = EvaluationContext(
            **_valid_context(organization_id="org_abc", account_id="acc_xyz")
        )

        assert ctx.organization_id == "org_abc"
        assert ctx.account_id == "acc_xyz"

    def test_flag_evaluation_construction(self) -> None:
        ev = FlagEvaluation(**_valid_evaluation())

        assert ev.key == "test_flag"
        assert ev.enabled is True
        assert ev.reason == "default"

    def test_evaluate_request_construction(self) -> None:
        req = EvaluateRequest(flag_keys=["flag_one", "flag_two"])

        assert req.flag_keys == ["flag_one", "flag_two"]

    def test_evaluate_response_construction(self) -> None:
        ev = FlagEvaluation(**_valid_evaluation())
        resp = EvaluateResponse(evaluations={"test_flag": ev})

        assert "test_flag" in resp.evaluations
        assert resp.evaluations["test_flag"].enabled is True


# ---------------------------------------------------------------------------
# AC-2: FLAG_KEY_REGEX enforcement on FeatureFlag.key
# ---------------------------------------------------------------------------


class TestFlagKeyRegex:
    """AC-2: Only keys matching FLAG_KEY_REGEX are accepted."""

    @pytest.mark.parametrize(
        "bad_key",
        [
            "Foo",           # uppercase
            "_foo_bar",      # leading underscore
            "ab",            # too short (only 2 chars; minimum valid is 3)
            "a" * 65,        # too long (65 chars; max is 64)
            "foo-bar",       # hyphen not in allowed chars
            "foo bar",       # whitespace
            "foo@bar",       # special char
        ],
    )
    def test_invalid_key_raises(self, bad_key: str) -> None:
        with pytest.raises(ValidationError):
            FeatureFlag(**_valid_flag(key=bad_key))

    def test_minimum_valid_key(self) -> None:
        flag = FeatureFlag(**_valid_flag(key="abc"))

        assert flag.key == "abc"

    def test_maximum_valid_key(self) -> None:
        key = "a" + "b" * 63  # 64 chars
        flag = FeatureFlag(**_valid_flag(key=key))

        assert flag.key == key

    def test_digit_leading_with_underscore(self) -> None:
        flag = FeatureFlag(**_valid_flag(key="1_foo"))

        assert flag.key == "1_foo"


# ---------------------------------------------------------------------------
# AC-3: _lowercase validator on TargetingRules
# ---------------------------------------------------------------------------


class TestTargetingRulesLowercaseValidator:
    """AC-3: user_emails and email_domains are lowercased; other list fields
    are preserved verbatim."""

    def test_user_emails_lowercased(self) -> None:
        rules = TargetingRules(user_emails=["Foo@KEN-E.ai"])

        assert rules.user_emails == ["foo@ken-e.ai"]

    def test_email_domains_lowercased(self) -> None:
        rules = TargetingRules(email_domains=["KEN-E.AI"])

        assert rules.email_domains == ["ken-e.ai"]

    def test_both_lowercased_together(self) -> None:
        rules = TargetingRules(
            user_emails=["Foo@KEN-E.ai"],
            email_domains=["KEN-E.AI"],
        )

        assert rules.user_emails == ["foo@ken-e.ai"]
        assert rules.email_domains == ["ken-e.ai"]

    def test_whitespace_stripped_from_emails(self) -> None:
        rules = TargetingRules(user_emails=[" Foo@KEN-E.ai "])

        assert rules.user_emails == ["foo@ken-e.ai"]

    def test_whitespace_stripped_from_domains(self) -> None:
        rules = TargetingRules(email_domains=[" KEN-E.AI "])

        assert rules.email_domains == ["ken-e.ai"]

    def test_organization_ids_preserved_verbatim(self) -> None:
        rules = TargetingRules(organization_ids=["Org_ABC", "ORG_XYZ"])

        assert rules.organization_ids == ["Org_ABC", "ORG_XYZ"]

    def test_account_ids_preserved_verbatim(self) -> None:
        rules = TargetingRules(account_ids=["Acc_001", "ACC_002"])

        assert rules.account_ids == ["Acc_001", "ACC_002"]


# ---------------------------------------------------------------------------
# AC-4: bucketing_entity Literal validation
# ---------------------------------------------------------------------------


class TestBucketingEntity:
    """AC-4: Only the three enumerated bucketing entities are accepted."""

    def test_invalid_bucketing_entity_raises(self) -> None:
        with pytest.raises(ValidationError):
            FeatureFlag(**_valid_flag(bucketing_entity="team"))

    def test_default_is_account(self) -> None:
        flag = FeatureFlag(**_valid_flag())

        assert flag.bucketing_entity == "account"

    @pytest.mark.parametrize("entity", ["account", "organization", "user"])
    def test_all_valid_entities_accepted(self, entity: str) -> None:
        flag = FeatureFlag(**_valid_flag(bucketing_entity=entity))

        assert flag.bucketing_entity == entity


# ---------------------------------------------------------------------------
# AC-5: FlagEvaluation.reason Literal validation
# ---------------------------------------------------------------------------


class TestFlagEvaluationReason:
    """AC-5: Only the eight enumerated reasons are accepted."""

    def test_bogus_reason_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlagEvaluation(**_valid_evaluation(reason="bogus"))

    @pytest.mark.parametrize(
        "reason",
        [
            "kill_switch",
            "email_match",
            "domain_match",
            "org_match",
            "account_match",
            "rollout",
            "default",
            "unknown_flag",
        ],
    )
    def test_all_valid_reasons_accepted(self, reason: str) -> None:
        ev = FlagEvaluation(**_valid_evaluation(reason=reason))

        assert ev.reason == reason


# ---------------------------------------------------------------------------
# AC-6: EvaluateRequest.flag_keys min/max length
# ---------------------------------------------------------------------------


class TestEvaluateRequestFlagKeys:
    """AC-6: flag_keys must contain 1-100 entries."""

    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvaluateRequest(flag_keys=[])

    def test_101_keys_raises(self) -> None:
        with pytest.raises(ValidationError):
            EvaluateRequest(flag_keys=["a"] * 101)

    def test_exactly_100_keys_accepted(self) -> None:
        req = EvaluateRequest(flag_keys=["a"] * 100)

        assert len(req.flag_keys) == 100

    def test_single_key_accepted(self) -> None:
        req = EvaluateRequest(flag_keys=["my_flag"])

        assert req.flag_keys == ["my_flag"]


# ---------------------------------------------------------------------------
# AC-7: TargetingRules.rollout_percentage bounds
# ---------------------------------------------------------------------------


class TestRolloutPercentageBounds:
    """AC-7: rollout_percentage must be in [0, 100]."""

    def test_negative_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            TargetingRules(rollout_percentage=-1)

    def test_101_raises(self) -> None:
        with pytest.raises(ValidationError):
            TargetingRules(rollout_percentage=101)

    def test_zero_is_valid(self) -> None:
        rules = TargetingRules(rollout_percentage=0)

        assert rules.rollout_percentage == 0

    def test_100_is_valid(self) -> None:
        rules = TargetingRules(rollout_percentage=100)

        assert rules.rollout_percentage == 100

    def test_midpoint_is_valid(self) -> None:
        rules = TargetingRules(rollout_percentage=50)

        assert rules.rollout_percentage == 50
