"""Unit tests for the API_TEST_BYPASS_TOKEN startup guard.

The bypass short-circuits Firebase auth + rate-limiting + revocation + audit
logging, so the guard must be fail-closed: a non-empty token may only run in
ENVIRONMENT ∈ {development, test, ci}. Anything else — including an empty or
misspelled ENVIRONMENT — must refuse to start.
"""

from __future__ import annotations

import pytest
from src.kene_api.main import _assert_bypass_token_safe


class TestBypassTokenSafeWhenTokenEmpty:
    """An empty token must always pass, regardless of ENVIRONMENT."""

    @pytest.mark.parametrize(
        "environment",
        ["", "development", "test", "ci", "staging", "production", "prod", "PROD"],
    )
    def test_empty_token_never_raises(self, environment: str) -> None:
        _assert_bypass_token_safe("", environment)


class TestBypassTokenAllowedEnvironments:
    """A non-empty token in an allowed environment must pass."""

    @pytest.mark.parametrize("environment", ["development", "test", "ci"])
    def test_allowed_environment_passes(self, environment: str) -> None:
        _assert_bypass_token_safe("e2e-test-bypass-secret", environment)


class TestBypassTokenForbiddenEnvironments:
    """A non-empty token outside the allowed set must raise RuntimeError."""

    @pytest.mark.parametrize(
        "environment",
        [
            "",  # unset / fail-closed against missing config
            "staging",  # explicitly out per reviewer finding
            "production",
            "prod",  # common typo
            "PROD",  # casing typo
            "Development",  # casing typo on an otherwise-allowed value
            "unknown-env",
        ],
    )
    def test_forbidden_environment_raises(self, environment: str) -> None:
        with pytest.raises(RuntimeError, match="API_TEST_BYPASS_TOKEN"):
            _assert_bypass_token_safe("e2e-test-bypass-secret", environment)

    def test_error_message_includes_actual_environment_value(self) -> None:
        with pytest.raises(RuntimeError, match=r"'staging'"):
            _assert_bypass_token_safe("e2e-test-bypass-secret", "staging")
