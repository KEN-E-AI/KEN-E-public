"""Unit tests for ``evaluate`` — the pure flag evaluation function.

Covers FF-PRD-01 AC-4 (precedence ladder) and AC-5 (missing entity id):

  AC-4 branches:
    1.  Kill switch — is_active=False returns default_enabled regardless.
    2.  Email allowlist — case-insensitive exact match on user_email.
    3.  Email domain match — domain extracted from lowercased user_email.
    4.  Organisation ID match.
    5.  Account ID match.
    6.  Rollout hit — hash_bucket("demo_flag", "user_001") == 33; 33 < 50 → enabled.
    7.  Rollout miss — 33 < 20 is False → falls through to default.
    8.  Default fallback — no rule fires, returns default_enabled.
    9.  Precedence: email_match wins over rollout (both apply simultaneously).

  AC-5 (missing entity id):
    10. bucketing_entity="account", account_id=None, rollout_percentage=100 → default.
    11. bucketing_entity="organization", organization_id=None, rollout_percentage=100 → default.
    12. bucketing_entity="user", user_id="" (empty string), rollout_percentage=100 → default.

  Extra:
    13. Email with no "@" character produces empty domain → no domain match.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.kene_api.models.feature_flag_models import (
    EvaluationContext,
    FeatureFlag,
    FlagEvaluation,
    TargetingRules,
)
from src.kene_api.services.feature_flag_service import evaluate, hash_bucket

# ---------------------------------------------------------------------------
# Helpers — test fixture builders
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _flag(**overrides: object) -> FeatureFlag:
    base: dict[str, object] = {
        "key": "test_flag",
        "description": "A test flag",
        "default_enabled": False,
        "is_active": True,
        "owner": "dev@ken-e.ai",
        "targeting_rules": TargetingRules(),
        "bucketing_entity": "account",
        "created_at": _NOW,
        "updated_at": _NOW,
    }
    base.update(overrides)
    return FeatureFlag(**base)


def _ctx(**overrides: object) -> EvaluationContext:
    base: dict[str, object] = {
        "user_id": "uid_123",
        "user_email": "alice@ken-e.ai",
        "organization_id": None,
        "account_id": None,
    }
    base.update(overrides)
    return EvaluationContext(**base)


# ---------------------------------------------------------------------------
# Prerequisite: confirm golden hash values used throughout these tests
# ---------------------------------------------------------------------------


class TestGoldenHashPreconditions:
    """Sanity-check the hash_bucket values that the rollout tests rely on.

    These are NOT testing hash_bucket itself (that lives in
    test_feature_flag_hash_bucket.py) — they guard against accidentally
    using the wrong entity/flag pair in the rollout branches below.
    """

    def test_demo_flag_user_001_is_33(self) -> None:
        assert hash_bucket("demo_flag", "user_001") == 33

    def test_billing_enabled_org_42_is_98(self) -> None:
        assert hash_bucket("billing_enabled", "org_42") == 98


# ---------------------------------------------------------------------------
# AC-4 branch 1 — Kill switch
# ---------------------------------------------------------------------------


class TestKillSwitch:
    """is_active=False returns default_enabled with reason='kill_switch'."""

    def test_kill_switch_default_enabled_false(self) -> None:
        flag = _flag(is_active=False, default_enabled=False)
        result = evaluate(flag, _ctx())

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="kill_switch")

    def test_kill_switch_default_enabled_true(self) -> None:
        flag = _flag(is_active=False, default_enabled=True)
        result = evaluate(flag, _ctx())

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="kill_switch")


# ---------------------------------------------------------------------------
# AC-4 branch 2 — Email allowlist (case-insensitive)
# ---------------------------------------------------------------------------


class TestEmailMatch:
    """Exact email match fires even when user_email has mixed case."""

    def test_lowercase_email_matches(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(user_emails=["alice@ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="alice@ken-e.ai"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="email_match")

    def test_mixed_case_email_matches(self) -> None:
        # TargetingRules._lowercase stores "foo@ken-e.ai"; ctx.user_email is
        # lowercased in evaluate() before comparison.
        flag = _flag(targeting_rules=TargetingRules(user_emails=["Foo@KEN-E.AI"]))
        result = evaluate(flag, _ctx(user_email="Foo@KEN-E.AI"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="email_match")

    def test_nonmatching_email_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(user_emails=["other@ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="alice@ken-e.ai"))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branch 3 — Email domain match
# ---------------------------------------------------------------------------


class TestDomainMatch:
    """Domain extracted from user_email matches email_domains list."""

    def test_domain_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="bob@ken-e.ai"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="domain_match")

    def test_mixed_case_domain_in_email_matches(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["KEN-E.AI"]))
        result = evaluate(flag, _ctx(user_email="bob@KEN-E.AI"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="domain_match")

    def test_nonmatching_domain_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["other.ai"]))
        result = evaluate(flag, _ctx(user_email="bob@ken-e.ai"))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branch 4 — Organisation ID match
# ---------------------------------------------------------------------------


class TestOrgMatch:
    """ctx.organization_id in targeting_rules.organization_ids fires org_match."""

    def test_org_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(organization_ids=["org_abc"]))
        result = evaluate(flag, _ctx(organization_id="org_abc"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="org_match")

    def test_nonmatching_org_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(organization_ids=["org_xyz"]))
        result = evaluate(flag, _ctx(organization_id="org_abc"))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branch 5 — Account ID match
# ---------------------------------------------------------------------------


class TestAccountMatch:
    """ctx.account_id in targeting_rules.account_ids fires account_match."""

    def test_account_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(account_ids=["acc_001"]))
        result = evaluate(flag, _ctx(account_id="acc_001"))

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="account_match")

    def test_nonmatching_account_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(account_ids=["acc_999"]))
        result = evaluate(flag, _ctx(account_id="acc_001"))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branches 6 & 7 — Percentage rollout hit and miss
# ---------------------------------------------------------------------------


class TestRollout:
    """Rollout uses hash_bucket(flag.key, entity_id) < rollout_percentage.

    Golden values (from test_feature_flag_hash_bucket.py):
      hash_bucket("demo_flag", "user_001") == 33
        → rollout_percentage=50: 33 < 50 = True  (HIT)
        → rollout_percentage=20: 33 < 20 = False (MISS)
    """

    def test_rollout_hit_user_bucketing(self) -> None:
        # bucket=33, rollout_percentage=50 → 33 < 50 = True
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(rollout_percentage=50),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001"))

        assert result == FlagEvaluation(key="demo_flag", enabled=True, reason="rollout")

    def test_rollout_miss_user_bucketing(self) -> None:
        # bucket=33, rollout_percentage=20 → 33 < 20 = False
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(rollout_percentage=20),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001"))

        assert result == FlagEvaluation(key="demo_flag", enabled=False, reason="default")

    def test_rollout_hit_org_bucketing(self) -> None:
        # hash_bucket("billing_enabled", "org_42") == 98; 98 < 99 = True
        flag = _flag(
            key="billing_enabled",
            targeting_rules=TargetingRules(rollout_percentage=99),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id="org_42"))

        assert result == FlagEvaluation(key="billing_enabled", enabled=True, reason="rollout")

    def test_rollout_miss_org_bucketing(self) -> None:
        # hash_bucket("billing_enabled", "org_42") == 98; 98 < 97 = False
        flag = _flag(
            key="billing_enabled",
            targeting_rules=TargetingRules(rollout_percentage=97),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id="org_42"))

        assert result == FlagEvaluation(key="billing_enabled", enabled=False, reason="default")

    def test_rollout_zero_percent_never_fires(self) -> None:
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(rollout_percentage=0),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001"))

        assert result == FlagEvaluation(key="demo_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branch 8 — Default fallback
# ---------------------------------------------------------------------------


class TestDefaultFallback:
    """No rule fires → result reflects flag.default_enabled."""

    def test_default_false_when_no_rules_match(self) -> None:
        flag = _flag(default_enabled=False)
        result = evaluate(flag, _ctx())

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")

    def test_default_true_when_no_rules_match(self) -> None:
        flag = _flag(default_enabled=True)
        result = evaluate(flag, _ctx())

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="default")


# ---------------------------------------------------------------------------
# AC-4 branch 9 — Precedence: email_match wins over rollout
# ---------------------------------------------------------------------------


class TestPrecedenceEmailOverRollout:
    """email_match fires before rollout even when rollout_percentage=100."""

    def test_email_match_wins_over_100pct_rollout(self) -> None:
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(
                user_emails=["alice@ken-e.ai"],
                rollout_percentage=100,
            ),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001", user_email="alice@ken-e.ai"))

        assert result == FlagEvaluation(key="demo_flag", enabled=True, reason="email_match")


# ---------------------------------------------------------------------------
# AC-5 — Missing entity id → rollout is skipped, falls through to default
# ---------------------------------------------------------------------------


class TestMissingEntityId:
    """When the bucketing entity is absent, rollout is skipped entirely."""

    def test_account_none_with_100pct_rollout_returns_default(self) -> None:
        flag = _flag(
            targeting_rules=TargetingRules(rollout_percentage=100),
            bucketing_entity="account",
        )
        result = evaluate(flag, _ctx(account_id=None))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")

    def test_organization_none_with_100pct_rollout_returns_default(self) -> None:
        flag = _flag(
            targeting_rules=TargetingRules(rollout_percentage=100),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id=None))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")

    def test_user_empty_string_with_100pct_rollout_returns_default(self) -> None:
        # user_id="" is a non-None but falsy value — evaluate() guards with `if entity_id`.
        flag = _flag(
            targeting_rules=TargetingRules(rollout_percentage=100),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id=""))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")


# ---------------------------------------------------------------------------
# Extra — degenerate email with no "@"
# ---------------------------------------------------------------------------


class TestDegenerateEmail:
    """Email address without '@' produces an empty domain → no domain match."""

    def test_no_at_sign_email_skips_domain_match(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["no-at-sign"]))
        result = evaluate(flag, _ctx(user_email="no-at-sign"))

        assert result == FlagEvaluation(key="test_flag", enabled=False, reason="default")
