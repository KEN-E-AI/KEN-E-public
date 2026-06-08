"""Unit tests for api/scripts/seed_feature_flags.py — registry invariants.

Tests assert the shape of FLAGS_TO_REGISTER without any I/O or mocked services.
The key invariant for the invite_only_signup flag is that it has NO targeting
rules (targeting_rules == TargetingRules()) — a matching targeting rule would
invert the flag's meaning by enabling invite-only for matched users, the exact
opposite of a bypass (see DM-PRD-11 §4.4 and feature-flags/README.md §7.6).
"""

from __future__ import annotations

from src.kene_api.models.feature_flag_models import (
    FeatureFlagWriteRequest,
    TargetingRules,
)

from api.scripts.seed_feature_flags import FLAGS_TO_REGISTER


def _flag(key: str) -> FeatureFlagWriteRequest:
    matches = [f for f in FLAGS_TO_REGISTER if f.key == key]
    assert len(matches) == 1, f"Expected exactly one entry for {key!r}, got {len(matches)}"
    return matches[0]


class TestRegistryInvariants:
    def test_invite_only_signup_present(self) -> None:
        keys = [f.key for f in FLAGS_TO_REGISTER]
        assert "invite_only_signup" in keys

    def test_invite_only_signup_default_enabled_false(self) -> None:
        flag = _flag("invite_only_signup")
        assert flag.default_enabled is False

    def test_invite_only_signup_is_active_true(self) -> None:
        flag = _flag("invite_only_signup")
        assert flag.is_active is True

    def test_invite_only_signup_bucketing_entity_account(self) -> None:
        flag = _flag("invite_only_signup")
        assert flag.bucketing_entity == "account"

    def test_invite_only_signup_no_targeting_rules(self) -> None:
        """Critical invariant: no targeting rules — a matching rule would invert meaning."""
        flag = _flag("invite_only_signup")
        assert flag.targeting_rules == TargetingRules()

    def test_invite_only_signup_owner_set(self) -> None:
        flag = _flag("invite_only_signup")
        assert flag.owner, "owner must be a non-empty string"

    def test_rate_limit_backend_override_unchanged(self) -> None:
        """Existing rate-limiter entry must remain intact after the rename."""
        flag = _flag("rate_limit_backend_override")
        assert flag.is_active is False
        assert flag.default_enabled is False
        assert flag.bucketing_entity == "account"
        assert flag.targeting_rules == TargetingRules()
