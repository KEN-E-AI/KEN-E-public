"""Unit tests for _make_header_provider (AH-PRD-02 §5.3, AC-4)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.adk.agents.agent_factory.header_provider import (
    CREDENTIAL_KEYS,
    _make_header_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(state: dict) -> MagicMock:
    """Build a minimal ReadonlyContext mock with the given state dict."""
    ctx = MagicMock()
    ctx.state = state
    return ctx


# ---------------------------------------------------------------------------
# Tests: known auth_type happy paths
# ---------------------------------------------------------------------------


class TestMakeHeaderProvider:
    """Tests for _make_header_provider covering all AH-PRD-02 §5.3 + AC-4 cases."""

    @pytest.mark.parametrize("auth_type,state_key", list(CREDENTIAL_KEYS.items()))
    def test_known_auth_type_returns_callable(self, auth_type: str, state_key: str) -> None:
        """Each known auth_type constructs a closure without raising."""
        provider = _make_header_provider(auth_type)
        assert callable(provider)

    @pytest.mark.parametrize("auth_type,state_key", list(CREDENTIAL_KEYS.items()))
    def test_known_auth_type_reads_correct_state_key(
        self, auth_type: str, state_key: str
    ) -> None:
        """Each closure reads its own credential key, ignoring the others."""
        provider = _make_header_provider(auth_type)

        # Populate ONLY this auth type's credentials; all others absent.
        ctx = _make_context(
            {
                state_key: {
                    "access_token": f"tok_{auth_type}",
                    "tenant_id": f"tenant_{auth_type}",
                }
            }
        )

        headers = provider(ctx)

        assert headers == {
            "Authorization": f"Bearer tok_{auth_type}",
            "X-Tenant-ID": f"tenant_{auth_type}",
        }

    def test_ga_oauth_full_credentials(self) -> None:
        """ga_oauth closure returns Authorization + X-Tenant-ID for full creds."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context(
            {
                "ga_credentials": {
                    "access_token": "test_access",
                    "tenant_id": "org-123",
                    "refresh_token": "test_refresh",
                }
            }
        )

        assert provider(ctx) == {
            "Authorization": "Bearer test_access",
            "X-Tenant-ID": "org-123",
        }

    def test_google_ads_oauth_full_credentials(self) -> None:
        """google_ads_oauth closure returns correct headers."""
        provider = _make_header_provider("google_ads_oauth")
        ctx = _make_context(
            {
                "google_ads_credentials": {
                    "access_token": "ads_token",
                    "tenant_id": "ads-tenant",
                }
            }
        )

        assert provider(ctx) == {
            "Authorization": "Bearer ads_token",
            "X-Tenant-ID": "ads-tenant",
        }

    def test_meta_ads_oauth_full_credentials(self) -> None:
        """meta_ads_oauth closure returns correct headers."""
        provider = _make_header_provider("meta_ads_oauth")
        ctx = _make_context(
            {
                "meta_ads_credentials": {
                    "access_token": "meta_token",
                    "tenant_id": "meta-tenant",
                }
            }
        )

        assert provider(ctx) == {
            "Authorization": "Bearer meta_token",
            "X-Tenant-ID": "meta-tenant",
        }

    def test_mailchimp_oauth_full_credentials(self) -> None:
        """mailchimp_oauth closure returns correct headers."""
        provider = _make_header_provider("mailchimp_oauth")
        ctx = _make_context(
            {
                "mailchimp_credentials": {
                    "access_token": "mc_token",
                    "tenant_id": "mc-tenant",
                }
            }
        )

        assert provider(ctx) == {
            "Authorization": "Bearer mc_token",
            "X-Tenant-ID": "mc-tenant",
        }

    # -----------------------------------------------------------------------
    # Tests: fail-fast on unknown auth_type
    # -----------------------------------------------------------------------

    def test_unknown_auth_type_raises_at_build_time(self) -> None:
        """Unknown auth_type raises ValueError synchronously — before any closure is returned."""
        with pytest.raises(ValueError, match="Unknown auth_type"):
            _make_header_provider("bogus_oauth")

    def test_unknown_auth_type_does_not_return_closure(self) -> None:
        """_make_header_provider raises, not the closure (no closure is created)."""
        raised = False
        try:
            _make_header_provider("totally_unknown")
        except ValueError:
            raised = True

        assert raised, "Expected ValueError at _make_header_provider() call time"

    # -----------------------------------------------------------------------
    # Tests: missing / empty credentials (defensive defaults, AC-4 §3)
    # -----------------------------------------------------------------------

    def test_missing_credential_key_returns_empty_headers(self) -> None:
        """When the expected credential key is absent from state, returns {}."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context({})  # ga_credentials absent entirely

        assert provider(ctx) == {}

    def test_empty_credential_dict_returns_empty_headers(self) -> None:
        """When the credential dict is present but empty, returns {}."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context({"ga_credentials": {}})

        assert provider(ctx) == {}

    def test_empty_access_token_omits_authorization_header(self) -> None:
        """Empty-string access_token is treated as missing — no Authorization header."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context(
            {"ga_credentials": {"access_token": "", "tenant_id": "org-123"}}
        )

        assert provider(ctx) == {"X-Tenant-ID": "org-123"}

    def test_empty_tenant_id_omits_x_tenant_id_header(self) -> None:
        """Empty-string tenant_id is treated as missing — no X-Tenant-ID header."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context(
            {"ga_credentials": {"access_token": "tok", "tenant_id": ""}}
        )

        assert provider(ctx) == {"Authorization": "Bearer tok"}

    def test_access_token_only_no_tenant_id(self) -> None:
        """When access_token is set but tenant_id is absent, only Authorization is returned."""
        provider = _make_header_provider("ga_oauth")
        ctx = _make_context({"ga_credentials": {"access_token": "tok"}})

        assert provider(ctx) == {"Authorization": "Bearer tok"}

    # -----------------------------------------------------------------------
    # Tests: cross-key isolation
    # -----------------------------------------------------------------------

    def test_meta_ads_closure_ignores_ga_credentials(self) -> None:
        """meta_ads_oauth closure must not fall back to ga_credentials."""
        provider = _make_header_provider("meta_ads_oauth")
        ctx = _make_context(
            {
                "ga_credentials": {
                    "access_token": "should_be_ignored",
                    "tenant_id": "should_be_ignored",
                }
                # meta_ads_credentials absent
            }
        )

        assert provider(ctx) == {}

    def test_google_ads_closure_ignores_mailchimp_credentials(self) -> None:
        """google_ads_oauth closure must not fall back to mailchimp_credentials."""
        provider = _make_header_provider("google_ads_oauth")
        ctx = _make_context(
            {
                "mailchimp_credentials": {
                    "access_token": "should_be_ignored",
                    "tenant_id": "should_be_ignored",
                }
                # google_ads_credentials absent
            }
        )

        assert provider(ctx) == {}

    # -----------------------------------------------------------------------
    # Tests: CREDENTIAL_KEYS completeness
    # -----------------------------------------------------------------------

    def test_credential_keys_covers_all_four_auth_types(self) -> None:
        """CREDENTIAL_KEYS must contain exactly the four R1/R5 auth types from the PRD."""
        expected = {
            "ga_oauth",
            "google_ads_oauth",
            "meta_ads_oauth",
            "mailchimp_oauth",
        }
        assert set(CREDENTIAL_KEYS.keys()) == expected

    def test_credential_keys_maps_to_correct_state_keys(self) -> None:
        """Each auth_type maps to the correct session-state credential key."""
        assert CREDENTIAL_KEYS["ga_oauth"] == "ga_credentials"
        assert CREDENTIAL_KEYS["google_ads_oauth"] == "google_ads_credentials"
        assert CREDENTIAL_KEYS["meta_ads_oauth"] == "meta_ads_credentials"
        assert CREDENTIAL_KEYS["mailchimp_oauth"] == "mailchimp_credentials"
