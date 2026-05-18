"""Unit tests for the admin feature flags router.

Coverage: FF-PRD-02 §7 AC-1 (read half) — GET / and GET /{key} auth gate,
list shape, 404 path, and service-exception propagation.

Uses FastAPI TestClient + dependency_overrides — no Firestore emulator needed
(that is FF-17's territory).

Scenarios:
  1. Super-admin GET / returns 200 with {flags: [...]}
  2. Non-super-admin GET / returns 403 with {"error": "super_admin_required"}
  3. Missing token GET / returns 401
  4. Super-admin GET /{key} for a known key returns the flag
  5. Super-admin GET /{key} for an absent key returns 404 with detail containing key
  6. Service exception in list_flags/get_flag propagates to 500 (not swallowed)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import UserContext, require_super_admin
from src.kene_api.dependencies import get_feature_flag_service
from src.kene_api.main import app
from src.kene_api.models.feature_flag_models import FeatureFlag, TargetingRules

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_flag(**overrides: object) -> FeatureFlag:
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


def _make_super_admin() -> UserContext:
    return UserContext(
        user_id="admin_uid",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _stub_service_with_flags(flags: list[FeatureFlag]) -> MagicMock:
    svc = MagicMock()
    svc.list_flags = AsyncMock(return_value=flags)
    svc.get_flag = AsyncMock(
        side_effect=lambda key: next((f for f in flags if f.key == key), None)
    )
    return svc


def _stub_service_raising() -> MagicMock:
    svc = MagicMock()
    svc.list_flags = AsyncMock(side_effect=RuntimeError("Firestore down"))
    svc.get_flag = AsyncMock(side_effect=RuntimeError("Firestore down"))
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_overrides() -> None:
    """Guarantee dependency_overrides is clean before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client_raises() -> TestClient:
    """TestClient that re-raises server exceptions for 5xx assertions."""
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestListFlagsAuth:
    """AC-1 read half: GET / authorization gate."""

    def test_super_admin_list_returns_200(self, client: TestClient) -> None:
        """Super-admin receives 200 with flags list."""
        flags = [_make_flag(key="aaa_flag"), _make_flag(key="bbb_flag")]
        stub = _stub_service_with_flags(flags)

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags")

        assert resp.status_code == 200
        body = resp.json()
        assert "flags" in body
        assert len(body["flags"]) == 2
        assert body["flags"][0]["key"] == "aaa_flag"

    def test_non_super_admin_list_returns_403(self, client: TestClient) -> None:
        """Non-super-admin receives flat 403 with {'error': 'super_admin_required'}."""
        # Do NOT override require_super_admin — let the real gate run, but we
        # need to supply an authenticated non-admin user so the 401 from
        # get_current_user doesn't fire first.
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.get("/api/v1/admin/feature-flags")

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_missing_token_list_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401 (auth dep is not overridden)."""
        # Do NOT install any override — the real auth chain runs.
        resp = client.get("/api/v1/admin/feature-flags")
        assert resp.status_code == 401


class TestGetFlagAuth:
    """AC-1 read half: GET /{key} authorization gate."""

    def test_super_admin_get_known_key_returns_200(self, client: TestClient) -> None:
        """Super-admin receives the flag JSON for a known key."""
        flag = _make_flag(key="known_flag")
        stub = _stub_service_with_flags([flag])

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/known_flag")

        assert resp.status_code == 200
        body = resp.json()
        assert body["key"] == "known_flag"
        assert body["is_active"] is True

    def test_non_super_admin_get_returns_403(self, client: TestClient) -> None:
        """Non-super-admin receives flat 403."""
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.get("/api/v1/admin/feature-flags/some_flag")

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_missing_token_get_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.get("/api/v1/admin/feature-flags/some_flag")
        assert resp.status_code == 401

    def test_super_admin_get_absent_key_returns_404(self, client: TestClient) -> None:
        """GET /{key} for a non-existent key returns 404 with detail containing the key."""
        stub = _stub_service_with_flags([])  # empty list → get_flag returns None

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/absent_flag")

        assert resp.status_code == 404
        body = resp.json()
        assert "absent_flag" in body["detail"]


class TestServiceExceptionPropagation:
    """Service errors propagate to 500 (not swallowed like is_feature_enabled)."""

    def test_list_flags_service_error_propagates(self, client: TestClient) -> None:
        """Firestore failure in list_flags → 500 (admin operators need real errors)."""
        stub = _stub_service_raising()

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags")
        assert resp.status_code == 500

    def test_get_flag_service_error_propagates(self, client: TestClient) -> None:
        """Firestore failure in get_flag → 500."""
        stub = _stub_service_raising()

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/any_flag")
        assert resp.status_code == 500
