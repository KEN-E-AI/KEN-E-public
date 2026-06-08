"""Unit tests for the admin early-release router.

Coverage: DM-PRD-11 §7 — GET /early-release-code, PUT /early-release-code,
GET /early-release-code/redemptions auth gates, response shape, service routing
rules, audit emission, and pagination.

Uses FastAPI TestClient + dependency_overrides — no Firestore emulator needed.

Scenarios:
  (a) Super-admin GET returns 200 with merged response shape
  (b) GET returns 404 when service.get_config() returns None
  (c) Non-super-admin GET returns 403 with {"error": "super_admin_required"}
  (d) Missing token returns 401
  (e) PUT {code, expires_at} → service.set_code called with right args + one audit event
      (details must NOT contain "code" key)
  (f) PUT {code, is_active=False} → set_code then set_active(False); action="rotate_with_disable"
  (g) PUT {is_active: false} only → set_active called only; action="set_active"
  (h) PUT {expires_at only} → 422
  (i) PUT {} empty body → 422
  (j) EarlyReleaseConfigNotFoundError from set_active → 404
  (k) GET /redemptions paginates across two synthetic pages
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import (
    SuperAdminRequiredError,
    UserContext,
    require_super_admin,
)
from src.kene_api.dependencies import get_early_release_service
from src.kene_api.main import app
from src.kene_api.models.early_release_models import (
    EarlyReleaseConfig,
    EarlyReleaseRedemption,
)
from src.kene_api.services.early_release_service import (
    EarlyReleaseConfigNotFoundError,
)

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_EXPIRES = datetime(2026, 12, 31, tzinfo=timezone.utc)

_BASE_URL = "/api/v1/admin/early-release-code"
_REDEMPTIONS_URL = f"{_BASE_URL}/redemptions"


def _make_super_admin() -> UserContext:
    return UserContext(
        user_id="admin_uid",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _make_config(**overrides: object) -> EarlyReleaseConfig:
    base: dict[str, object] = {
        "code": "EARLY2026",
        "is_active": True,
        "expires_at": _EXPIRES,
        "updated_by": "admin_uid",
        "updated_at": _NOW,
    }
    base.update(overrides)
    return EarlyReleaseConfig(**base)


def _make_redemption(user_id: str = "user_1") -> EarlyReleaseRedemption:
    return EarlyReleaseRedemption(
        user_id=user_id,
        email=f"{user_id}@example.com",
        org_id="org_abc",
        redeemed_at=_NOW,
    )


def _make_service_stub() -> MagicMock:
    """Full service stub with all async methods needed by the router."""
    svc = MagicMock()
    svc.get_config = AsyncMock(return_value=_make_config())
    svc.count_redemptions = AsyncMock(return_value=0)
    svc.set_code = AsyncMock(return_value=_make_config())
    svc.set_active = AsyncMock(return_value=_make_config())
    svc.list_redemptions = AsyncMock(return_value=([], None))
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
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
# Helper: install super-admin override
# ---------------------------------------------------------------------------


def _override_admin() -> None:
    async def _admin() -> UserContext:
        return _make_super_admin()

    app.dependency_overrides[require_super_admin] = _admin


def _override_non_admin() -> None:
    async def _non_admin() -> UserContext:
        raise SuperAdminRequiredError()

    app.dependency_overrides[require_super_admin] = _non_admin


# ---------------------------------------------------------------------------
# (a) Super-admin GET returns 200 with merged response shape
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_super_admin_get_returns_200_with_full_shape(
        self, client: TestClient
    ) -> None:
        """200 with code, is_active, expires_at, updated_by, updated_at, redemption_count."""
        stub = _make_service_stub()
        stub.count_redemptions = AsyncMock(return_value=7)

        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        resp = client.get(_BASE_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "EARLY2026"
        assert body["is_active"] is True
        assert body["updated_by"] == "admin_uid"
        assert body["redemption_count"] == 7
        assert "expires_at" in body
        assert "updated_at" in body

    # ------------------------------------------------------------------
    # (b) GET returns 404 when service.get_config() returns None
    # ------------------------------------------------------------------

    def test_get_returns_404_when_config_absent(self, client: TestClient) -> None:
        """404 with detail 'early_release_config_not_found' when no config doc exists."""
        stub = _make_service_stub()
        stub.get_config = AsyncMock(return_value=None)

        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        resp = client.get(_BASE_URL)

        assert resp.status_code == 404
        assert resp.json()["detail"] == "early_release_config_not_found"

    # ------------------------------------------------------------------
    # (c) Non-super-admin GET returns 403
    # ------------------------------------------------------------------

    def test_non_super_admin_get_returns_403(self, client: TestClient) -> None:
        """Non-super-admin receives flat 403 with {'error': 'super_admin_required'}."""
        _override_non_admin()

        resp = client.get(_BASE_URL)

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    # ------------------------------------------------------------------
    # (d) Missing token returns 401
    # ------------------------------------------------------------------

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401 (real auth chain runs)."""
        resp = client.get(_BASE_URL)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# (e) PUT {code, expires_at} → set_code called, one audit event, no "code" in details
# ---------------------------------------------------------------------------


class TestPutConfig:
    def test_put_code_and_expires_at_calls_set_code(self, client: TestClient) -> None:
        """set_code called with correct args; one audit event; code NOT in audit details."""
        stub = _make_service_stub()
        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        payload = {"code": "NEWCODE99", "expires_at": "2026-12-31T00:00:00Z"}

        with patch(
            "src.kene_api.routers.admin_early_release.get_audit_logger"
        ) as mock_logger_fn:
            mock_audit = MagicMock()
            mock_audit.log_event = AsyncMock()
            mock_logger_fn.return_value = mock_audit

            resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 200
        stub.set_code.assert_awaited_once()
        call_args = stub.set_code.call_args
        assert call_args.args[0] == "NEWCODE99"
        assert call_args.kwargs.get("actor_id") == "admin_uid"
        # set_active should NOT have been called
        stub.set_active.assert_not_awaited()

        # Audit: exactly one event emitted
        assert mock_audit.log_event.call_count == 1
        audit_kwargs = mock_audit.log_event.call_args.kwargs
        details = audit_kwargs.get("details", {})
        assert "code" not in details, f"Plaintext code must NOT appear in audit details: {details}"

    # ------------------------------------------------------------------
    # (f) PUT {code, is_active=False} → single set_code(is_active=False); action="rotate_with_disable"
    # ------------------------------------------------------------------

    def test_put_code_with_is_active_false_rotates_disabled_in_one_write(
        self, client: TestClient
    ) -> None:
        """Rotate-with-disable is a single set_code(is_active=False) write — set_active
        is NOT called, so a failure can never leave a freshly-rotated code live.
        Audit action='rotate_with_disable'.
        """
        stub = _make_service_stub()
        stub.set_code = AsyncMock(return_value=_make_config(is_active=False))
        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        payload = {"code": "NEWCODE99", "is_active": False}

        with patch(
            "src.kene_api.routers.admin_early_release.get_audit_logger"
        ) as mock_logger_fn:
            mock_audit = MagicMock()
            mock_audit.log_event = AsyncMock()
            mock_logger_fn.return_value = mock_audit

            resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 200
        # Single atomic write: set_code carries is_active=False; set_active unused.
        stub.set_code.assert_awaited_once()
        assert stub.set_code.call_args.kwargs.get("is_active") is False
        stub.set_active.assert_not_awaited()

        # Audit action
        assert mock_audit.log_event.call_count == 1
        audit_kwargs = mock_audit.log_event.call_args.kwargs
        details = audit_kwargs.get("details", {})
        assert details.get("action") == "rotate_with_disable"
        assert details.get("code_changed") is True

    # ------------------------------------------------------------------
    # (g) PUT {is_active: false} only → set_active called only; action="set_active"
    # ------------------------------------------------------------------

    def test_put_is_active_only_calls_set_active(self, client: TestClient) -> None:
        """Only is_active provided → set_active called only; audit action='set_active'."""
        stub = _make_service_stub()
        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        payload = {"is_active": False}

        with patch(
            "src.kene_api.routers.admin_early_release.get_audit_logger"
        ) as mock_logger_fn:
            mock_audit = MagicMock()
            mock_audit.log_event = AsyncMock()
            mock_logger_fn.return_value = mock_audit

            resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 200
        stub.set_code.assert_not_awaited()
        stub.set_active.assert_awaited_once()

        assert mock_audit.log_event.call_count == 1
        audit_kwargs = mock_audit.log_event.call_args.kwargs
        details = audit_kwargs.get("details", {})
        assert details.get("action") == "set_active"

    # ------------------------------------------------------------------
    # (h) PUT with only {expires_at} → 422
    # ------------------------------------------------------------------

    def test_put_expires_at_only_returns_422(self, client: TestClient) -> None:
        """Only expires_at provided (no code or is_active) → 422."""
        _override_admin()

        payload = {"expires_at": "2026-12-31T00:00:00Z"}

        resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 422

    def test_put_expires_at_with_is_active_only_returns_422(
        self, client: TestClient
    ) -> None:
        """expires_at + is_active (no code) → 422 (no standalone set-expiry primitive)."""
        _override_admin()

        payload = {"is_active": True, "expires_at": "2027-01-01T00:00:00Z"}

        resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # (i) PUT with empty body → 422
    # ------------------------------------------------------------------

    def test_put_empty_body_returns_422(self, client: TestClient) -> None:
        """Empty body {} → 422 (no actionable fields provided)."""
        _override_admin()

        resp = client.put(_BASE_URL, json={})

        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # (j) EarlyReleaseConfigNotFoundError from set_active → 404
    # ------------------------------------------------------------------

    def test_put_config_not_found_error_surfaces_as_404(
        self, client: TestClient
    ) -> None:
        """EarlyReleaseConfigNotFoundError from service.set_active → 404."""
        stub = _make_service_stub()
        stub.set_active = AsyncMock(
            side_effect=EarlyReleaseConfigNotFoundError("no config")
        )
        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        payload = {"is_active": True}

        with patch(
            "src.kene_api.routers.admin_early_release.get_audit_logger"
        ) as mock_logger_fn:
            mock_audit = MagicMock()
            mock_audit.log_event = AsyncMock()
            mock_logger_fn.return_value = mock_audit

            resp = client.put(_BASE_URL, json=payload)

        assert resp.status_code == 404
        assert resp.json()["detail"] == "early_release_config_not_found"

    # ------------------------------------------------------------------
    # PUT auth gates (non-super-admin / missing token)
    # ------------------------------------------------------------------

    def test_non_super_admin_put_returns_403(self, client: TestClient) -> None:
        """Non-super-admin PUT returns flat 403."""
        _override_non_admin()

        resp = client.put(_BASE_URL, json={"code": "X"})

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_missing_token_put_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.put(_BASE_URL, json={"code": "X"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# (k) GET /redemptions paginates across two synthetic pages
# ---------------------------------------------------------------------------


class TestListRedemptions:
    def test_first_page_has_next_cursor(self, client: TestClient) -> None:
        """First page returns redemptions and a non-null next_cursor."""
        r1 = _make_redemption("user_1")
        r2 = _make_redemption("user_2")
        stub = _make_service_stub()
        stub.list_redemptions = AsyncMock(return_value=([r1, r2], "user_2"))
        stub.count_redemptions = AsyncMock(return_value=3)

        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        resp = client.get(_REDEMPTIONS_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["redemptions"]) == 2
        assert body["next_cursor"] == "user_2"
        assert body["total"] == 3

    def test_second_page_has_null_next_cursor(self, client: TestClient) -> None:
        """Second page (cursor provided) returns remaining items and next_cursor=null."""
        r3 = _make_redemption("user_3")
        stub = _make_service_stub()
        stub.list_redemptions = AsyncMock(return_value=([r3], None))
        stub.count_redemptions = AsyncMock(return_value=3)

        _override_admin()
        app.dependency_overrides[get_early_release_service] = lambda: stub

        resp = client.get(_REDEMPTIONS_URL, params={"cursor": "user_2"})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["redemptions"]) == 1
        assert body["next_cursor"] is None
        assert body["total"] == 3
        # Verify cursor was forwarded to the service
        stub.list_redemptions.assert_awaited_once_with(50, "user_2")

    def test_non_super_admin_redemptions_returns_403(self, client: TestClient) -> None:
        """Non-super-admin GET /redemptions returns flat 403."""
        _override_non_admin()

        resp = client.get(_REDEMPTIONS_URL)

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_missing_token_redemptions_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.get(_REDEMPTIONS_URL)
        assert resp.status_code == 401
