"""Unit tests for the POST /api/v1/feature-flags/evaluate router.

Covers AC-9 (FF-PRD-01 §7.9) and AC-10 (FF-PRD-01 §7.10) via
FastAPI TestClient + dependency_overrides — no Firestore emulator needed
(that is FF-9's territory).

AC-9 scenarios:
  1. Missing token → 401.
  2. Body extras (user_id, user_email, organization_id, account_id) are
     silently ignored; the evaluator receives only the token-derived context.
  3. Invalid email claim in the JWT → 401 (not 500).

AC-10 scenarios:
  4. Empty flag_keys list → 422.
  5. flag_keys list with 101 entries → 422.

Response shape:
  6. Only {key, enabled, reason} in the response; no flag config fields.

Field-set lock:
  7. EvaluateRequest.model_fields has exactly {"flag_keys"} so any future
     addition requires a deliberate test update.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.user_context import UserContext, get_current_user_context
from src.kene_api.dependencies import get_feature_flag_service
from src.kene_api.main import app
from src.kene_api.models.feature_flag_models import (
    EvaluateRequest,
    EvaluationContext,
    FlagEvaluation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    user_id: str = "real_uid",
    email: str = "real@ken-e.ai",
    org_permissions: dict[str, str] | None = None,
    account_permissions: dict[str, str] | None = None,
) -> UserContext:
    return UserContext(
        user_id=user_id,
        email=email,
        organization_permissions=org_permissions or {},
        account_permissions=account_permissions or {},
    )


def _stub_service(
    evaluations: dict[str, FlagEvaluation] | None = None,
    *,
    captured_ctx: list[EvaluationContext],
) -> MagicMock:
    """Return a MagicMock FeatureFlagService that records the EvaluationContext it receives."""
    svc = MagicMock()

    async def _evaluate_batch(
        flag_keys: list[str], ctx: EvaluationContext
    ) -> dict[str, FlagEvaluation]:
        captured_ctx.append(ctx)
        result_map = evaluations or {}
        return {k: result_map.get(k, FlagEvaluation(key=k, enabled=False, reason="unknown_flag")) for k in flag_keys}

    svc.evaluate_batch = _evaluate_batch
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Guarantee dependency_overrides is clean before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestEvaluateFlagsAuth:
    """AC-9: authentication and spoof-resistance."""

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401 (auth dep is not overridden)."""
        # Do NOT install a user override so the real auth dep runs.
        # The session-scoped mock_firebase_auth fixture makes verify_id_token
        # return a valid token — but with no credentials at all, HTTPBearer
        # rejects before even reaching verify_id_token.
        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["foo"]},
        )
        assert resp.status_code == 401

    def test_body_extras_are_ignored_context_built_from_token(
        self, client: TestClient
    ) -> None:
        """Body fields that look like identity cannot influence EvaluationContext."""
        user = _make_user(user_id="real_uid", email="real@ken-e.ai")
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={
                "flag_keys": ["foo"],
                "user_id": "spoof_uid",           # silently dropped
                "user_email": "attacker@evil.com",  # silently dropped
                "organization_id": "spoof_org",   # silently dropped
                "account_id": "spoof_acc",        # silently dropped
            },
        )

        assert resp.status_code == 200
        assert len(captured) == 1
        ctx = captured[0]
        assert ctx.user_id == "real_uid"
        assert str(ctx.user_email) == "real@ken-e.ai"
        assert ctx.organization_id is None
        assert ctx.account_id is None

    def test_invalid_email_jwt_claim_returns_401(
        self, client: TestClient
    ) -> None:
        """A JWT with a missing/malformed email claim → 401 not 500."""
        # Simulate a JWT whose email claim is empty (fails EmailStr).
        user = _make_user(user_id="uid_no_email", email="")
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["foo"]},
        )

        assert resp.status_code == 401
        # Service should not have been called — we short-circuit on context build.
        assert len(captured) == 0

    def test_empty_user_id_in_jwt_returns_401(self, client: TestClient) -> None:
        """A JWT whose uid claim is empty → 401 not 500 (user_id min_length=1)."""
        user = _make_user(user_id="", email="valid@ken-e.ai")
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["foo"]},
        )

        assert resp.status_code == 401
        assert len(captured) == 0


class TestEvaluateFlagsValidation:
    """AC-10: flag_keys size validation."""

    def test_empty_flag_keys_returns_422(self, client: TestClient) -> None:
        """flag_keys=[] violates min_length=1 → 422."""
        user = _make_user()
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": []},
        )

        assert resp.status_code == 422

    def test_flag_keys_over_100_returns_422(self, client: TestClient) -> None:
        """flag_keys with 101 entries violates max_length=100 → 422."""
        user = _make_user()
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": [f"key_{i}" for i in range(101)]},
        )

        assert resp.status_code == 422

    def test_invalid_flag_key_format_returns_422(self, client: TestClient) -> None:
        """flag_keys with an item that doesn't match FLAG_KEY_REGEX → 422.

        Prevents Firestore path traversal (e.g., '../users/uid') and log injection.
        """
        user = _make_user()
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["INVALID_KEY_UPPER"]},
        )

        assert resp.status_code == 422

    def test_flag_key_with_slash_returns_422(self, client: TestClient) -> None:
        """flag_keys with a '/' (Firestore path traversal vector) → 422."""
        user = _make_user()
        captured: list[EvaluationContext] = []
        stub = _stub_service(captured_ctx=captured)

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["../users/target_uid"]},
        )

        assert resp.status_code == 422


class TestEvaluateFlagsResponseShape:
    """Response shape: only {key, enabled, reason} in each evaluation."""

    def test_response_contains_only_flag_evaluation_fields(
        self, client: TestClient
    ) -> None:
        """No flag config fields (default_enabled, targeting_rules, owner, …) leak."""
        user = _make_user()
        captured: list[EvaluationContext] = []
        stub = _stub_service(
            evaluations={
                "foo": FlagEvaluation(key="foo", enabled=True, reason="domain_match")
            },
            captured_ctx=captured,
        )

        async def _get_user() -> UserContext:
            return user

        app.dependency_overrides[get_current_user_context] = _get_user
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post(
            "/api/v1/feature-flags/evaluate",
            json={"flag_keys": ["foo"]},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "evaluations": {
                "foo": {"key": "foo", "enabled": True, "reason": "domain_match"}
            }
        }
        # Verify no config-level fields are present
        foo_eval = body["evaluations"]["foo"]
        assert set(foo_eval.keys()) == {"key", "enabled", "reason"}
        assert "default_enabled" not in foo_eval
        assert "targeting_rules" not in foo_eval
        assert "owner" not in foo_eval


class TestEvaluateRequestFieldSet:
    """Lock the EvaluateRequest field surface so additions are deliberate."""

    def test_evaluate_request_has_only_flag_keys_field(self) -> None:
        """EvaluateRequest must have exactly one field: flag_keys.

        If this assertion fails after adding a field, update the router's
        spoof-resistance guarantee and the comment in the module docstring.
        """
        assert set(EvaluateRequest.model_fields.keys()) == {"flag_keys"}
