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

  AC-13 (per-evaluation structured log, no PII):
    14. TestEvaluatorLogging — caplog-based assertions on the INFO log emitted by evaluate().
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
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

# Standard LogRecord attribute names present on every record regardless of the
# ``extra`` dict.  Captured against CPython 3.12 (which added ``taskName``).
# If Python adds a new standard attribute in a future version the test that
# uses this set will fail, prompting an update here.
_STANDARD_LOG_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }
)


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


def _nonstandard_attrs(record: logging.LogRecord) -> dict[str, object]:
    """Return only the non-standard extra attributes injected via ``extra={}``."""
    return {
        k: v for k, v in record.__dict__.items() if k not in _STANDARD_LOG_RECORD_ATTRS
    }


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

    def test_test_flag_acc_001_is_16(self) -> None:
        # python3 -c "import hashlib; print(int(hashlib.sha256(b'test_flag:acc_001').hexdigest()[:8],16)%100)"
        assert hash_bucket("test_flag", "acc_001") == 16


# ---------------------------------------------------------------------------
# AC-4 branch 1 — Kill switch
# ---------------------------------------------------------------------------


class TestKillSwitch:
    """is_active=False returns default_enabled with reason='kill_switch'."""

    def test_kill_switch_default_enabled_false(self) -> None:
        flag = _flag(is_active=False, default_enabled=False)
        result = evaluate(flag, _ctx(), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="kill_switch"
        )

    def test_kill_switch_default_enabled_true(self) -> None:
        flag = _flag(is_active=False, default_enabled=True)
        result = evaluate(flag, _ctx(), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="kill_switch"
        )


# ---------------------------------------------------------------------------
# AC-4 branch 2 — Email allowlist (case-insensitive)
# ---------------------------------------------------------------------------


class TestEmailMatch:
    """Exact email match fires even when user_email has mixed case."""

    def test_lowercase_email_matches(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(user_emails=["alice@ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="alice@ken-e.ai"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="email_match"
        )

    def test_mixed_case_email_matches(self) -> None:
        # TargetingRules._lowercase stores "foo@ken-e.ai"; ctx.user_email is
        # lowercased in evaluate() before comparison.
        flag = _flag(targeting_rules=TargetingRules(user_emails=["Foo@KEN-E.AI"]))
        result = evaluate(flag, _ctx(user_email="Foo@KEN-E.AI"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="email_match"
        )

    def test_nonmatching_email_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(user_emails=["other@ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="alice@ken-e.ai"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )


# ---------------------------------------------------------------------------
# AC-4 branch 3 — Email domain match
# ---------------------------------------------------------------------------


class TestDomainMatch:
    """Domain extracted from user_email matches email_domains list."""

    def test_domain_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email="bob@ken-e.ai"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="domain_match"
        )

    def test_mixed_case_domain_in_email_matches(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["KEN-E.AI"]))
        result = evaluate(flag, _ctx(user_email="bob@KEN-E.AI"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="domain_match"
        )

    def test_nonmatching_domain_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(email_domains=["other.ai"]))
        result = evaluate(flag, _ctx(user_email="bob@ken-e.ai"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )


# ---------------------------------------------------------------------------
# AC-4 branch 4 — Organisation ID match
# ---------------------------------------------------------------------------


class TestOrgMatch:
    """ctx.organization_id in targeting_rules.organization_ids fires org_match."""

    def test_org_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(organization_ids=["org_abc"]))
        result = evaluate(flag, _ctx(organization_id="org_abc"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="org_match"
        )

    def test_nonmatching_org_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(organization_ids=["org_xyz"]))
        result = evaluate(flag, _ctx(organization_id="org_abc"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )


# ---------------------------------------------------------------------------
# AC-4 branch 5 — Account ID match
# ---------------------------------------------------------------------------


class TestAccountMatch:
    """ctx.account_id in targeting_rules.account_ids fires account_match."""

    def test_account_match_fires(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(account_ids=["acc_001"]))
        result = evaluate(flag, _ctx(account_id="acc_001"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="account_match"
        )

    def test_nonmatching_account_does_not_fire(self) -> None:
        flag = _flag(targeting_rules=TargetingRules(account_ids=["acc_999"]))
        result = evaluate(flag, _ctx(account_id="acc_001"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )


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
        result = evaluate(flag, _ctx(user_id="user_001"), cache_hit=False)

        assert result == FlagEvaluation(key="demo_flag", enabled=True, reason="rollout")

    def test_rollout_miss_user_bucketing(self) -> None:
        # bucket=33, rollout_percentage=20 → 33 < 20 = False
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(rollout_percentage=20),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001"), cache_hit=False)

        assert result == FlagEvaluation(
            key="demo_flag", enabled=False, reason="default"
        )

    def test_rollout_hit_org_bucketing(self) -> None:
        # hash_bucket("billing_enabled", "org_42") == 98; 98 < 99 = True
        flag = _flag(
            key="billing_enabled",
            targeting_rules=TargetingRules(rollout_percentage=99),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id="org_42"), cache_hit=False)

        assert result == FlagEvaluation(
            key="billing_enabled", enabled=True, reason="rollout"
        )

    def test_rollout_miss_org_bucketing(self) -> None:
        # hash_bucket("billing_enabled", "org_42") == 98; 98 < 97 = False
        flag = _flag(
            key="billing_enabled",
            targeting_rules=TargetingRules(rollout_percentage=97),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id="org_42"), cache_hit=False)

        assert result == FlagEvaluation(
            key="billing_enabled", enabled=False, reason="default"
        )

    def test_rollout_hit_account_bucketing(self) -> None:
        # hash_bucket("test_flag", "acc_001") == 16; 16 < 50 = True
        flag = _flag(
            key="test_flag",
            targeting_rules=TargetingRules(rollout_percentage=50),
            bucketing_entity="account",
        )
        result = evaluate(flag, _ctx(account_id="acc_001"), cache_hit=False)

        assert result == FlagEvaluation(key="test_flag", enabled=True, reason="rollout")

    def test_rollout_miss_account_bucketing(self) -> None:
        # hash_bucket("test_flag", "acc_001") == 16; 16 < 10 = False
        flag = _flag(
            key="test_flag",
            targeting_rules=TargetingRules(rollout_percentage=10),
            bucketing_entity="account",
        )
        result = evaluate(flag, _ctx(account_id="acc_001"), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )

    def test_rollout_zero_percent_never_fires(self) -> None:
        flag = _flag(
            key="demo_flag",
            targeting_rules=TargetingRules(rollout_percentage=0),
            bucketing_entity="user",
        )
        result = evaluate(flag, _ctx(user_id="user_001"), cache_hit=False)

        assert result == FlagEvaluation(
            key="demo_flag", enabled=False, reason="default"
        )


# ---------------------------------------------------------------------------
# AC-4 branch 8 — Default fallback
# ---------------------------------------------------------------------------


class TestDefaultFallback:
    """No rule fires → result reflects flag.default_enabled."""

    def test_default_false_when_no_rules_match(self) -> None:
        flag = _flag(default_enabled=False)
        result = evaluate(flag, _ctx(), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )

    def test_default_true_when_no_rules_match(self) -> None:
        flag = _flag(default_enabled=True)
        result = evaluate(flag, _ctx(), cache_hit=False)

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
        result = evaluate(
            flag, _ctx(user_id="user_001", user_email="alice@ken-e.ai"), cache_hit=False
        )

        assert result == FlagEvaluation(
            key="demo_flag", enabled=True, reason="email_match"
        )


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
        result = evaluate(flag, _ctx(account_id=None), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )

    def test_organization_none_with_100pct_rollout_returns_default(self) -> None:
        flag = _flag(
            targeting_rules=TargetingRules(rollout_percentage=100),
            bucketing_entity="organization",
        )
        result = evaluate(flag, _ctx(organization_id=None), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=False, reason="default"
        )

    def test_user_empty_string_rejected_by_model_validation(self) -> None:
        # EvaluationContext.user_id has Field(min_length=1) — an empty string is
        # rejected at construction time, before the evaluator is ever called.
        with pytest.raises(ValidationError):
            _ctx(user_id="")


# ---------------------------------------------------------------------------
# Extra — degenerate email with no "@"
# ---------------------------------------------------------------------------


class TestDegenerateEmail:
    """Degenerate email address edge cases in domain extraction."""

    def test_no_at_sign_email_rejected_by_email_validation(self) -> None:
        # EmailStr (FF-6 hardening) rejects strings without "@" at model
        # construction time.  The evaluator never receives such an email —
        # the input is now caught at the boundary.
        with pytest.raises(ValidationError):
            _ctx(user_email="no-at-sign")

    def test_empty_local_part_rejected_by_email_validation(self) -> None:
        # EmailStr (FF-6 hardening) rejects "@ken-e.ai" at model construction time —
        # the empty local part is invalid per RFC 5322.  EvaluationContext can no
        # longer be constructed with this value, so the evaluator never sees it.
        with pytest.raises(ValidationError):
            _ctx(user_email="@ken-e.ai")

    def test_whitespace_padded_email_normalised_then_matches(self) -> None:
        # EmailStr strips leading/trailing whitespace and normalises the value to
        # "alice@ken-e.ai" before storing it.  The evaluator then matches it
        # against the allowlist entry exactly as expected.
        flag = _flag(targeting_rules=TargetingRules(user_emails=["alice@ken-e.ai"]))
        result = evaluate(flag, _ctx(user_email=" alice@ken-e.ai "), cache_hit=False)

        assert result == FlagEvaluation(
            key="test_flag", enabled=True, reason="email_match"
        )


# ---------------------------------------------------------------------------
# AC-13 — Structured per-evaluation log, no PII (FF-PRD-01 §5.3 / §7.13)
# ---------------------------------------------------------------------------

_SERVICE_LOGGER = "src.kene_api.services.feature_flag_service"


class TestEvaluatorLogging:
    """caplog-based assertions verifying the INFO log emitted by evaluate().

    Each call to evaluate() MUST emit exactly one INFO record with the fixed
    field set {flag_key, reason, cache_hit} and no PII fields.
    """

    def test_emits_exactly_one_info_record_with_required_field_set(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        flag = _flag()
        ctx = _ctx()
        with caplog.at_level(logging.INFO, logger=_SERVICE_LOGGER):
            result = evaluate(flag, ctx, cache_hit=False)

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1, (
            f"Expected 1 INFO record, got {len(info_records)}"
        )

        record = info_records[0]
        assert record.levelname == "INFO"
        non_std = _nonstandard_attrs(record)
        assert set(non_std.keys()) == {"flag_key", "reason", "cache_hit"}
        assert non_std["flag_key"] == result.key
        assert non_std["reason"] == result.reason
        assert non_std["cache_hit"] is False

    def test_cache_hit_true_flows_through(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        flag = _flag()
        ctx = _ctx()
        with caplog.at_level(logging.INFO, logger=_SERVICE_LOGGER):
            evaluate(flag, ctx, cache_hit=True)

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1
        record = info_records[0]
        non_std = _nonstandard_attrs(record)
        assert non_std["cache_hit"] is True

    def test_no_pii_field_names_in_any_record(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        pii_field_names = {"user_id", "user_email", "organization_id", "account_id"}
        pii_values = {
            "uid_secret",
            "secret@example.com",
            "org_secret",
            "acc_secret",
        }
        ctx = _ctx(
            user_id="uid_secret",
            user_email="secret@example.com",
            organization_id="org_secret",
            account_id="acc_secret",
        )
        flag = _flag(
            targeting_rules=TargetingRules(
                user_emails=["secret@example.com"],
                organization_ids=["org_secret"],
                account_ids=["acc_secret"],
            )
        )
        with caplog.at_level(logging.INFO, logger=_SERVICE_LOGGER):
            evaluate(flag, ctx, cache_hit=False)

        for record in caplog.records:
            record_dict = record.__dict__
            # No PII field names as attribute keys
            assert not pii_field_names & set(record_dict.keys()), (
                f"PII field name found in log record: {pii_field_names & set(record_dict.keys())}"
            )
            # No PII values in the message or args
            msg = record.getMessage()
            assert not any(v in msg for v in pii_values), (
                f"PII value found in log message: {msg!r}"
            )
            # No PII values in any non-standard attribute value
            for val in _nonstandard_attrs(record).values():
                assert str(val) not in pii_values, (
                    f"PII value found in log extra field: {val!r}"
                )

    def test_log_uses_fixed_message_string(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        flag = _flag()
        ctx = _ctx()
        with caplog.at_level(logging.INFO, logger=_SERVICE_LOGGER):
            evaluate(flag, ctx, cache_hit=False)

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 1
        record = info_records[0]
        # getMessage() resolves %-style formatting; for our fixed string with no
        # args it equals record.msg verbatim.
        assert record.getMessage() == "feature_flag_evaluated"
        assert record.msg == "feature_flag_evaluated"

    def test_calling_without_cache_hit_raises_type_error(self) -> None:
        flag = _flag()
        ctx = _ctx()
        with pytest.raises(TypeError):
            evaluate(flag, ctx)

    def test_all_precedence_branches_emit_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One INFO record is emitted regardless of which branch fires."""
        cases = [
            # kill_switch
            (_flag(is_active=False), _ctx(), "kill_switch"),
            # email_match
            (
                _flag(targeting_rules=TargetingRules(user_emails=["alice@ken-e.ai"])),
                _ctx(user_email="alice@ken-e.ai"),
                "email_match",
            ),
            # domain_match
            (
                _flag(targeting_rules=TargetingRules(email_domains=["ken-e.ai"])),
                _ctx(user_email="bob@ken-e.ai"),
                "domain_match",
            ),
            # org_match
            (
                _flag(targeting_rules=TargetingRules(organization_ids=["org_abc"])),
                _ctx(organization_id="org_abc"),
                "org_match",
            ),
            # account_match
            (
                _flag(targeting_rules=TargetingRules(account_ids=["acc_001"])),
                _ctx(account_id="acc_001"),
                "account_match",
            ),
            # rollout (hash_bucket("test_flag", "acc_001") == 16; 16 < 50)
            (
                _flag(
                    targeting_rules=TargetingRules(rollout_percentage=50),
                    bucketing_entity="account",
                ),
                _ctx(account_id="acc_001"),
                "rollout",
            ),
            # default
            (_flag(), _ctx(), "default"),
        ]
        for flag, ctx, expected_reason in cases:
            caplog.clear()
            with caplog.at_level(logging.INFO, logger=_SERVICE_LOGGER):
                result = evaluate(flag, ctx, cache_hit=False)
            info_records = [r for r in caplog.records if r.levelno == logging.INFO]
            assert len(info_records) == 1, (
                f"Expected 1 INFO record for reason={expected_reason!r}, "
                f"got {len(info_records)}"
            )
            non_std = _nonstandard_attrs(info_records[0])
            assert non_std["reason"] == expected_reason
            assert non_std["reason"] == result.reason
