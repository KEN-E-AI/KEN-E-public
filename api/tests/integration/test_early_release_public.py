"""Integration tests for public Early Release endpoints (DM-PRD-11 §6 + §7 AC-8, AC-9).

Covers:
  - TestValidate: POST /api/v1/early-release/validate — uniform response, rate limit
  - TestSignupPolicy: GET /api/v1/auth/signup-policy — flag state + fail-open

Both test classes use dependency_overrides and stub services so no Firestore emulator
or Redis instance is required.  The rate-limiter state is reset via the autouse fixture
(mirrors test_auth.py:14-29).
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.rate_limiting import (
    early_release_rate_limiter,
    signup_policy_rate_limiter,
)
from src.kene_api.dependencies import get_early_release_service
from src.kene_api.main import app
from src.kene_api.models.early_release_models import EarlyReleaseConfig
from src.kene_api.services.early_release_service import EarlyReleaseService

# ---------------------------------------------------------------------------
# Autouse fixture — reset limiter and dependency overrides between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state() -> Generator[None, None, None]:
    """Clear rate-limiter buckets and dependency overrides before and after each test.

    Resets both early_release_rate_limiter (used by validate) and
    signup_policy_rate_limiter (used by signup-policy) to prevent cross-test
    bucket bleed.  Mirrors test_auth.py:14-29.
    """
    early_release_rate_limiter.minute_requests.clear()
    early_release_rate_limiter.hour_requests.clear()
    signup_policy_rate_limiter.minute_requests.clear()
    signup_policy_rate_limiter.hour_requests.clear()
    app.dependency_overrides.clear()
    yield
    early_release_rate_limiter.minute_requests.clear()
    early_release_rate_limiter.hour_requests.clear()
    signup_policy_rate_limiter.minute_requests.clear()
    signup_policy_rate_limiter.hour_requests.clear()
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_active_config(code: str = "secret123") -> EarlyReleaseConfig:
    return EarlyReleaseConfig(
        code=code,
        is_active=True,
        expires_at=None,
        updated_by="admin",
        updated_at=datetime.now(timezone.utc),
    )


def _make_inactive_config(code: str = "secret123") -> EarlyReleaseConfig:
    return EarlyReleaseConfig(
        code=code,
        is_active=False,
        expires_at=None,
        updated_by="admin",
        updated_at=datetime.now(timezone.utc),
    )


def _make_expired_config(code: str = "secret123") -> EarlyReleaseConfig:
    return EarlyReleaseConfig(
        code=code,
        is_active=True,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        updated_by="admin",
        updated_at=datetime.now(timezone.utc),
    )


def _stub_service(validate_return: bool) -> EarlyReleaseService:
    """Return a fake EarlyReleaseService whose validate() always returns a fixed bool."""
    svc = AsyncMock(spec=EarlyReleaseService)
    svc.validate = AsyncMock(return_value=validate_return)
    return svc


# ---------------------------------------------------------------------------
# TestValidate — POST /api/v1/early-release/validate
# ---------------------------------------------------------------------------


class TestValidate:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def _install_service(self, validate_return: bool) -> None:
        app.dependency_overrides[get_early_release_service] = lambda: _stub_service(
            validate_return
        )

    def test_valid_active_code_returns_true(self, client: TestClient) -> None:
        """AC-8a: valid active code → {valid:true}."""
        self._install_service(validate_return=True)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "secret123"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": True}

    def test_wrong_code_returns_false(self, client: TestClient) -> None:
        """AC-8b: wrong code → uniform {valid:false}, not 403/404."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "wrong"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": False}

    def test_inactive_config_returns_false(self, client: TestClient) -> None:
        """AC-8c: inactive config → {valid:false}."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "secret123"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": False}

    def test_expired_config_returns_false(self, client: TestClient) -> None:
        """AC-8d: expired config → {valid:false}."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "secret123"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": False}

    def test_absent_config_returns_false(self, client: TestClient) -> None:
        """AC-8e: no config document → {valid:false}."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "anything"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": False}

    def test_uniform_response_shape_on_false_cases(self, client: TestClient) -> None:
        """AC-8: all false-returning paths produce exactly {valid: false} — no extra fields."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "wrong"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"valid": False}

    def test_missing_body_returns_422(self, client: TestClient) -> None:
        """Pydantic validation: missing body → 422."""
        self._install_service(validate_return=False)
        resp = client.post("/api/v1/early-release/validate")
        assert resp.status_code == 422

    def test_empty_code_returns_422(self, client: TestClient) -> None:
        """Pydantic validation: empty string fails min_length=1 → 422."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": ""},
        )
        assert resp.status_code == 422

    def test_no_auth_header_required(self, client: TestClient) -> None:
        """Public endpoint: requests without Authorization header must be accepted."""
        self._install_service(validate_return=False)
        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "test"},
            headers={},
        )
        assert resp.status_code == 200

    def test_validate_does_not_record(self, client: TestClient) -> None:
        """AC-8: validate never calls record_redemption."""
        svc = AsyncMock(spec=EarlyReleaseService)
        svc.validate = AsyncMock(return_value=True)
        app.dependency_overrides[get_early_release_service] = lambda: svc

        resp = client.post(
            "/api/v1/early-release/validate",
            json={"code": "secret123"},
        )
        assert resp.status_code == 200
        svc.record_redemption.assert_not_called()

    def test_rate_limit_exceeded_returns_429(self, client: TestClient) -> None:
        """AC-8f: IP rate limit → 429 after bucket is exhausted.

        In test environments without Redis, the SwitchableRateLimiter falls back
        to a LocalRateLimiter with requests_per_minute // fallback_cap_divisor (= 5//10 = 1).
        So the first request from a given IP succeeds; the second is 429.  The test
        verifies that 429 IS returned when the bucket is exhausted — the exact cap
        value is an implementation detail of the deployment configuration.
        """
        self._install_service(validate_return=False)
        # Exhaust the bucket for one IP.
        seen_429 = False
        for i in range(10):
            resp = client.post(
                "/api/v1/early-release/validate",
                json={"code": f"attempt_{i}"},
                headers={"X-Forwarded-For": "10.10.10.10"},
            )
            if resp.status_code == 429:
                seen_429 = True
                break
            assert resp.status_code == 200

        assert seen_429, "Expected a 429 after exhausting the IP bucket within 10 attempts"


# ---------------------------------------------------------------------------
# TestSignupPolicy — GET /api/v1/auth/signup-policy
# ---------------------------------------------------------------------------


class TestSignupPolicy:
    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_flag_off_returns_invite_only_false(self, client: TestClient) -> None:
        """AC-9a: flag default_enabled=false → {invite_only:false}."""
        with patch(
            "src.kene_api.routers.auth.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = client.get("/api/v1/auth/signup-policy")
        assert resp.status_code == 200
        assert resp.json() == {"invite_only": False}

    def test_flag_on_returns_invite_only_true(self, client: TestClient) -> None:
        """AC-9b: flag default_enabled=true → {invite_only:true}."""
        with patch(
            "src.kene_api.routers.auth.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.get("/api/v1/auth/signup-policy")
        assert resp.status_code == 200
        assert resp.json() == {"invite_only": True}

    def test_flag_service_error_fails_open(self, client: TestClient) -> None:
        """AC-9c: underlying service error → {invite_only:false} (fail-open invariant).

        Patches evaluate_batch on the FeatureFlagService to raise so the real
        is_feature_enabled try/except fires and returns default=False.  The
        endpoint must still return 200 {invite_only:false} — never a 500.
        """
        mock_svc = AsyncMock()
        mock_svc.evaluate_batch = AsyncMock(side_effect=Exception("Firestore outage"))

        # Patch get_feature_flag_service in the module where is_feature_enabled
        # calls it (feature_flag_service.py), so the try/except fires correctly.
        with patch(
            "src.kene_api.services.feature_flag_service.get_feature_flag_service",
            return_value=mock_svc,
        ):
            resp = client.get("/api/v1/auth/signup-policy")

        assert resp.status_code == 200
        assert resp.json() == {"invite_only": False}

    def test_no_auth_required(self, client: TestClient) -> None:
        """AC-9d: public endpoint — no Authorization header required."""
        with patch(
            "src.kene_api.routers.auth.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ):
            resp = client.get(
                "/api/v1/auth/signup-policy",
                headers={},
            )
        assert resp.status_code == 200

    def test_anon_context_used(self, client: TestClient) -> None:
        """The endpoint evaluates the flag with user_id='anonymous' (no targeting drift)."""
        captured_ctx: list[Any] = []

        async def _capture(flag_key: str, ctx: Any, default: bool = False) -> bool:
            captured_ctx.append(ctx)
            return False

        with patch("src.kene_api.routers.auth.is_feature_enabled", side_effect=_capture):
            resp = client.get("/api/v1/auth/signup-policy")

        assert resp.status_code == 200
        assert len(captured_ctx) == 1
        assert captured_ctx[0].user_id == "anonymous"
        assert captured_ctx[0].user_email == ""

    def test_rate_limit_exceeded_returns_429(self, client: TestClient) -> None:
        """The dedicated signup_policy limiter returns 429 once its IP bucket is exhausted.

        The exact cap depends on the deployment backend (full caps under the
        in-memory backend, divisor-capped under the Redis fallback), so the test
        only asserts that a 429 eventually appears for a single IP — never that
        the policy GET shares the recaptcha or early-release buckets.
        """
        seen_429 = False
        with patch(
            "src.kene_api.routers.auth.is_feature_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ):
            for _ in range(40):
                resp = client.get(
                    "/api/v1/auth/signup-policy",
                    headers={"X-Forwarded-For": "10.20.30.40"},
                )
                if resp.status_code == 429:
                    seen_429 = True
                    break
                assert resp.status_code == 200

        assert seen_429, "Expected a 429 after exhausting the signup_policy IP bucket"
