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

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import UserContext, require_super_admin
from src.kene_api.dependencies import get_feature_flag_service
from src.kene_api.main import app
from src.kene_api.models.feature_flag_models import (
    FeatureFlag,
    TargetingRules,
)
from src.kene_api.services.feature_flag_service import (
    DuplicateFeatureFlagError,
    FeatureFlagNotFoundError,
)

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
        # Assert set membership, not order — ordering is the service's contract.
        assert {f["key"] for f in body["flags"]} == {"aaa_flag", "bbb_flag"}

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

    def test_super_admin_get_invalid_key_returns_422(self, client: TestClient) -> None:
        """Key not matching FLAG_KEY_REGEX → 422 (validated by FlagKeyStr before handler)."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.get("/api/v1/admin/feature-flags/INVALID-KEY!")
        assert resp.status_code == 422


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


# ---------------------------------------------------------------------------
# Helpers for mutating endpoint tests (FF-13)
# ---------------------------------------------------------------------------


def _valid_write_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "key": "new_flag",
        "description": "A brand new flag",
        "default_enabled": False,
        "is_active": True,
        "owner": "dev@ken-e.ai",
        "targeting_rules": {
            "user_emails": [],
            "email_domains": [],
            "organization_ids": [],
            "account_ids": [],
            "rollout_percentage": 0,
        },
        "bucketing_entity": "account",
        "expected_ga_release": None,
    }
    base.update(overrides)
    return base


def _stub_service_for_create(
    result_flag: FeatureFlag | None = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    """Service stub for POST tests."""
    svc = MagicMock()
    if raise_exc is not None:
        svc.create_flag = AsyncMock(side_effect=raise_exc)
    else:
        svc.create_flag = AsyncMock(
            return_value=result_flag or _make_flag(key="new_flag")
        )
    return svc


def _stub_service_for_update(
    result_flag: FeatureFlag | None = None,
    raise_exc: Exception | None = None,
) -> MagicMock:
    """Service stub for PUT tests."""
    svc = MagicMock()
    if raise_exc is not None:
        svc.update_flag = AsyncMock(side_effect=raise_exc)
    else:
        svc.update_flag = AsyncMock(
            return_value=result_flag or _make_flag(key="upd_flag")
        )
    return svc


def _stub_service_for_delete(
    raise_exc: Exception | None = None,
) -> MagicMock:
    """Service stub for DELETE tests."""
    svc = MagicMock()
    if raise_exc is not None:
        svc.delete_flag = AsyncMock(side_effect=raise_exc)
    else:
        svc.delete_flag = AsyncMock(return_value=None)
    return svc


# ---------------------------------------------------------------------------
# TestCreateFlag — POST /api/v1/admin/feature-flags
# ---------------------------------------------------------------------------


class TestCreateFlag:
    """AC-1 (mutating half) and AC-2: POST auth gate, validation, and success."""

    def test_super_admin_post_valid_payload_returns_201(
        self, client: TestClient
    ) -> None:
        """Super-admin POST with valid payload returns 201 with the created flag."""
        stub = _stub_service_for_create()

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post("/api/v1/admin/feature-flags", json=_valid_write_payload())

        assert resp.status_code == 201
        assert resp.json()["key"] == "new_flag"

    def test_post_non_super_admin_returns_403(self, client: TestClient) -> None:
        """Non-super-admin POST returns flat 403."""
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.post("/api/v1/admin/feature-flags", json=_valid_write_payload())

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_post_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.post("/api/v1/admin/feature-flags", json=_valid_write_payload())
        assert resp.status_code == 401

    def test_post_invalid_key_regex_returns_422(self, client: TestClient) -> None:
        """Key violating FLAG_KEY_REGEX → 422 from Pydantic before handler runs."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.post(
            "/api/v1/admin/feature-flags",
            json=_valid_write_payload(key="INVALID-KEY!"),
        )

        assert resp.status_code == 422

    def test_post_duplicate_key_returns_409(self, client: TestClient) -> None:
        """Duplicate key → 409 Conflict."""
        stub = _stub_service_for_create(raise_exc=DuplicateFeatureFlagError("new_flag"))

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.post("/api/v1/admin/feature-flags", json=_valid_write_payload())

        assert resp.status_code == 409
        assert "new_flag" in resp.json()["detail"]

    def test_post_extra_timestamp_fields_are_ignored(self, client: TestClient) -> None:
        """Sending created_at / updated_at in the body is silently ignored (extra='ignore')."""
        stub = _stub_service_for_create()

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        payload = _valid_write_payload()
        payload["created_at"] = "2020-01-01T00:00:00Z"
        payload["updated_at"] = "2020-01-01T00:00:00Z"

        resp = client.post("/api/v1/admin/feature-flags", json=payload)

        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# TestUpdateFlag — PUT /api/v1/admin/feature-flags/{key}
# ---------------------------------------------------------------------------


class TestUpdateFlag:
    """AC-1 (mutating half) and AC-3: PUT auth gate, 404, URL/body mismatch, success."""

    def test_super_admin_put_valid_payload_returns_200(
        self, client: TestClient
    ) -> None:
        """Super-admin PUT with valid payload returns 200 with the updated flag."""
        stub = _stub_service_for_update(result_flag=_make_flag(key="upd_flag"))

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.put(
            "/api/v1/admin/feature-flags/upd_flag",
            json=_valid_write_payload(key="upd_flag"),
        )

        assert resp.status_code == 200
        assert resp.json()["key"] == "upd_flag"

    def test_put_non_super_admin_returns_403(self, client: TestClient) -> None:
        """Non-super-admin PUT returns flat 403."""
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.put(
            "/api/v1/admin/feature-flags/upd_flag",
            json=_valid_write_payload(key="upd_flag"),
        )

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_put_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.put(
            "/api/v1/admin/feature-flags/upd_flag",
            json=_valid_write_payload(key="upd_flag"),
        )
        assert resp.status_code == 401

    def test_put_missing_flag_returns_404(self, client: TestClient) -> None:
        """PUT on a non-existent flag → 404 with detail containing the key."""
        stub = _stub_service_for_update(raise_exc=FeatureFlagNotFoundError("upd_flag"))

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.put(
            "/api/v1/admin/feature-flags/upd_flag",
            json=_valid_write_payload(key="upd_flag"),
        )

        assert resp.status_code == 404
        assert "upd_flag" in resp.json()["detail"]

    def test_put_url_body_key_mismatch_returns_422(self, client: TestClient) -> None:
        """Body key different from URL key → 422."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.put(
            "/api/v1/admin/feature-flags/url_key",
            json=_valid_write_payload(key="different_key"),
        )

        assert resp.status_code == 422

    def test_put_invalid_url_key_returns_422(self, client: TestClient) -> None:
        """URL key violating FLAG_KEY_REGEX → 422 before handler runs."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.put(
            "/api/v1/admin/feature-flags/INVALID-KEY!",
            json=_valid_write_payload(key="INVALID-KEY!"),
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestDeleteFlag — DELETE /api/v1/admin/feature-flags/{key}
# ---------------------------------------------------------------------------


class TestDeleteFlag:
    """AC-1 (mutating half): DELETE auth gate, 404, and success (204 No Content)."""

    def test_super_admin_delete_existing_key_returns_204(
        self, client: TestClient
    ) -> None:
        """Super-admin DELETE of an existing flag returns 204 with no body."""
        stub = _stub_service_for_delete()

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.delete("/api/v1/admin/feature-flags/del_flag")

        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_non_super_admin_returns_403(self, client: TestClient) -> None:
        """Non-super-admin DELETE returns flat 403."""
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.delete("/api/v1/admin/feature-flags/del_flag")

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_delete_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.delete("/api/v1/admin/feature-flags/del_flag")
        assert resp.status_code == 401

    def test_delete_missing_flag_returns_404(self, client: TestClient) -> None:
        """DELETE on a non-existent flag → 404 with detail containing the key."""
        stub = _stub_service_for_delete(raise_exc=FeatureFlagNotFoundError("del_flag"))

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.delete("/api/v1/admin/feature-flags/del_flag")

        assert resp.status_code == 404
        assert "del_flag" in resp.json()["detail"]

    def test_delete_invalid_key_returns_422(self, client: TestClient) -> None:
        """URL key violating FLAG_KEY_REGEX → 422 before handler runs."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.delete("/api/v1/admin/feature-flags/INVALID-KEY!")

        assert resp.status_code == 422
