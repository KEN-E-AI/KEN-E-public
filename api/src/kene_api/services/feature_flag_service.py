"""Feature Flags evaluation primitives.

This module is the home for all Feature Flags evaluation logic as defined in
FF-PRD-01. hash_bucket is landed in FF-2; the evaluator is now landed by FF-3;
the service class and is_feature_enabled helper are appended by FF-4 and FF-5
respectively.
"""

import hashlib

from ..models.feature_flag_models import EvaluationContext, FeatureFlag, FlagEvaluation


def hash_bucket(flag_key: str, entity_id: str) -> int:
    """Return a deterministic bucket in [0, 99] for a (flag_key, entity_id) pair.

    Uses sha256(f"{flag_key}:{entity_id}") truncated to 8 hex chars, parsed as
    base-16, reduced modulo 100.  This algorithm is pinned by FF-PRD-01 §4 —
    any change to the byte sequence or modulus breaks cross-process
    determinism and silently shuffles users between rollout cohorts.

    Salting on flag_key gives each flag an independent hash distribution per
    entity.  entity_id MUST be an opaque identifier (ULID, UUID, branded
    string) — never an email address or any PII-bearing field (feature-flags
    README §7.3).
    """
    digest = hashlib.sha256(f"{flag_key}:{entity_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def evaluate(flag: FeatureFlag, ctx: EvaluationContext) -> FlagEvaluation:
    """Evaluate a feature flag against an evaluation context.

    Applies the precedence ladder defined in component README §7.2 and FF-PRD-01 §4
    (highest precedence first):
      1. Kill switch — flag.is_active is False → return default_enabled.
      2. Email allowlist — exact match on lowercased user_email. (grant only)
      3. Email domain — domain extracted from user_email. (grant only)
      4. Organisation ID — exact match on ctx.organization_id. (grant only)
      5. Account ID — exact match on ctx.account_id. (grant only)
      6. Percentage rollout — hash_bucket(flag.key, entity_id) < rollout_percentage.
      7. Default — flag.default_enabled.

    Note: all allowlist rules (steps 2-5) unconditionally grant enabled=True. They
    cannot be used to deny access. If both an allowlist rule and the rollout percentage
    would fire, the allowlist rule wins (higher precedence).

    Note: kill switch (step 1) returns default_enabled, which may be True if the flag
    was already at GA. To guarantee the feature is off, set both is_active=False and
    default_enabled=False.

    This function is pure: no I/O, no logging, no side effects.
    Logging is FF-8's concern (AC-13/§5.3).
    """
    # AC-13/§5.3: logging is FF-8's concern; do NOT log from this function.
    if not flag.is_active:
        return FlagEvaluation(key=flag.key, enabled=flag.default_enabled, reason="kill_switch")

    rules = flag.targeting_rules
    email = ctx.user_email.strip().lower()

    if email in rules.user_emails:
        return FlagEvaluation(key=flag.key, enabled=True, reason="email_match")

    domain = email.split("@", 1)[-1] if "@" in email else ""
    if domain and domain in rules.email_domains:
        return FlagEvaluation(key=flag.key, enabled=True, reason="domain_match")

    if ctx.organization_id and ctx.organization_id in rules.organization_ids:
        return FlagEvaluation(key=flag.key, enabled=True, reason="org_match")

    if ctx.account_id and ctx.account_id in rules.account_ids:
        return FlagEvaluation(key=flag.key, enabled=True, reason="account_match")

    if rules.rollout_percentage > 0:
        entity_id = {
            "account": ctx.account_id,
            "organization": ctx.organization_id,
            "user": ctx.user_id,
        }[flag.bucketing_entity]
        if entity_id and hash_bucket(flag.key, entity_id) < rules.rollout_percentage:
            return FlagEvaluation(key=flag.key, enabled=True, reason="rollout")

    return FlagEvaluation(key=flag.key, enabled=flag.default_enabled, reason="default")
