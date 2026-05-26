"""Unit tests for auth/internal_oidc.verify_internal_oidc_caller (CH-PRD-01 §7 AC-16)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.internal_oidc import verify_internal_oidc_caller


def _make_request(authorization: str = "Bearer token123") -> MagicMock:
    req = MagicMock()
    req.headers = {"Authorization": authorization}
    return req


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "CHAT_INTERNAL_OIDC_AUDIENCE": "https://api.example.com",
        "CHAT_INTERNAL_SA_ALLOWLIST": "svc@project.iam.gserviceaccount.com",
    }
    base.update(overrides)
    return base


def _id_info(email: str = "svc@project.iam.gserviceaccount.com", verified: bool = True) -> dict:
    return {"email": email, "email_verified": verified}


class TestSkipMode:
    def test_skip_returns_fixed_email(self) -> None:
        with patch.dict(os.environ, {"CHAT_INTERNAL_OIDC_SKIP": "true", "ENVIRONMENT": "test"}):
            result = verify_internal_oidc_caller(_make_request())
        assert result == "oidc-skip@local"

    def test_skip_case_insensitive(self) -> None:
        with patch.dict(os.environ, {"CHAT_INTERNAL_OIDC_SKIP": "TRUE", "ENVIRONMENT": "development"}):
            result = verify_internal_oidc_caller(_make_request())
        assert result == "oidc-skip@local"

    def test_skip_blocked_in_staging(self) -> None:
        with patch.dict(os.environ, {"CHAT_INTERNAL_OIDC_SKIP": "true", "ENVIRONMENT": "staging"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 500

    def test_skip_blocked_in_production(self) -> None:
        with patch.dict(os.environ, {"CHAT_INTERNAL_OIDC_SKIP": "true", "ENVIRONMENT": "production"}):
            with pytest.raises(HTTPException) as exc_info:
                verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 500


class TestMissingOrInvalidHeader:
    def test_no_bearer_header_raises_401(self) -> None:
        with patch.dict(os.environ, _env(), clear=True):
            with pytest.raises(HTTPException) as exc_info:
                verify_internal_oidc_caller(_make_request(authorization=""))
        assert exc_info.value.status_code == 401

    def test_non_bearer_auth_raises_401(self) -> None:
        with patch.dict(os.environ, _env(), clear=True):
            with pytest.raises(HTTPException) as exc_info:
                verify_internal_oidc_caller(_make_request(authorization="Basic abc"))
        assert exc_info.value.status_code == 401


class TestMisconfiguration:
    def test_missing_audience_raises_500(self) -> None:
        env = _env()
        del env["CHAT_INTERNAL_OIDC_AUDIENCE"]  # type: ignore[misc]
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 500

    def test_empty_allowlist_raises_500(self) -> None:
        env = _env(CHAT_INTERNAL_SA_ALLOWLIST="")
        with patch.dict(os.environ, env, clear=True):
            with patch("src.kene_api.auth.internal_oidc.id_token.verify_oauth2_token"):
                with pytest.raises(HTTPException) as exc_info:
                    verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 500


class TestTokenVerification:
    def test_invalid_token_raises_401(self) -> None:
        with patch.dict(os.environ, _env(), clear=True):
            with patch(
                "src.kene_api.auth.internal_oidc.id_token.verify_oauth2_token",
                side_effect=ValueError("bad token"),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 401

    def test_unverified_email_raises_401(self) -> None:
        with patch.dict(os.environ, _env(), clear=True):
            with patch(
                "src.kene_api.auth.internal_oidc.id_token.verify_oauth2_token",
                return_value=_id_info(verified=False),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 401

    def test_caller_not_in_allowlist_raises_403(self) -> None:
        with patch.dict(os.environ, _env(), clear=True):
            with patch(
                "src.kene_api.auth.internal_oidc.id_token.verify_oauth2_token",
                return_value=_id_info(email="other@attacker.com"),
            ):
                with pytest.raises(HTTPException) as exc_info:
                    verify_internal_oidc_caller(_make_request())
        assert exc_info.value.status_code == 403

    def test_valid_token_in_allowlist_returns_email(self) -> None:
        email = "svc@project.iam.gserviceaccount.com"
        with patch.dict(os.environ, _env(), clear=True):
            with patch(
                "src.kene_api.auth.internal_oidc.id_token.verify_oauth2_token",
                return_value=_id_info(email=email),
            ):
                result = verify_internal_oidc_caller(_make_request())
        assert result == email
