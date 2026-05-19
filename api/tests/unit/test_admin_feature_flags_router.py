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
    FeatureFlagAuditEntry,
    TargetingRules,
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


def _make_audit_entry(**overrides: object) -> FeatureFlagAuditEntry:
    base: dict[str, object] = {
        "audit_id": "2026-01-01T00:00:00+00:00_abc12345",
        "flag_key": "test_flag",
        "actor_email": "admin@ken-e.ai",
        "action": "update",
        "diff": {"description": {"before": "old desc", "after": "new desc"}},
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return FeatureFlagAuditEntry.model_validate(base)


def _stub_service_with_audit_pages(
    pages: list[tuple[list[FeatureFlagAuditEntry], str | None]],
) -> MagicMock:
    """Return a service mock whose get_flag_audit yields successive page tuples.

    ``pages`` is a list of (entries, next_cursor) pairs that are returned in
    sequence on successive calls to get_flag_audit.
    """
    svc = MagicMock()
    svc.get_flag_audit = AsyncMock(side_effect=pages)
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
# TestGetFlagAudit — FF-15 (FF-PRD-02 B4)
# ---------------------------------------------------------------------------


class TestGetFlagAudit:
    """AC-5: GET /{key}/audit authorization gate and response shape.

    Covers:
      1. Super-admin happy path — entries returned with non-null next_cursor.
      2. Super-admin terminal page — entries returned with next_cursor=None.
      3. Deleted/absent flag — empty entries list, next_cursor=None (no 404).
      4. Non-super-admin → 403.
      5. Missing token → 401.
      6. Invalid key → 422 (FLAG_KEY_REGEX rejected by FlagKeyStr path validator).
      7. limit=0 → 422 (FastAPI Query ge=1 violated).
      8. limit=51 → 422 (FastAPI Query le=50 violated).
      9. Service exception → 500.
    """

    # ------------------------------------------------------------------
    # Case 1: super-admin happy path — non-null next_cursor
    # ------------------------------------------------------------------

    def test_super_admin_gets_entries_with_next_cursor(self, client: TestClient) -> None:
        """200 response with entries list and non-null next_cursor."""
        entry1 = _make_audit_entry(audit_id="id_newer", created_at="2026-03-01T00:00:00+00:00")
        entry2 = _make_audit_entry(audit_id="id_older", created_at="2026-02-01T00:00:00+00:00")
        stub = _stub_service_with_audit_pages([([entry1, entry2], "id_older")])

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 2
        assert body["entries"][0]["audit_id"] == "id_newer"
        assert body["entries"][1]["audit_id"] == "id_older"
        assert body["next_cursor"] == "id_older"

    # ------------------------------------------------------------------
    # Case 2: super-admin terminal page — next_cursor=None
    # ------------------------------------------------------------------

    def test_super_admin_terminal_page_returns_null_next_cursor(
        self, client: TestClient
    ) -> None:
        """200 response for the last page has next_cursor=null."""
        entry = _make_audit_entry()
        stub = _stub_service_with_audit_pages([([entry], None)])

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["entries"]) == 1
        assert body["next_cursor"] is None

    # ------------------------------------------------------------------
    # Case 3: deleted/absent flag — empty entries, not 404
    # ------------------------------------------------------------------

    def test_deleted_flag_returns_empty_entries_not_404(
        self, client: TestClient
    ) -> None:
        """200 with empty entries when the flag has been deleted (no flag doc read)."""
        stub = _stub_service_with_audit_pages([([], None)])

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: stub

        resp = client.get("/api/v1/admin/feature-flags/deleted_flag/audit")

        assert resp.status_code == 200
        body = resp.json()
        assert body["entries"] == []
        assert body["next_cursor"] is None

    # ------------------------------------------------------------------
    # Case 4: non-super-admin → 403
    # ------------------------------------------------------------------

    def test_non_super_admin_returns_403(self, client: TestClient) -> None:
        """Non-super-admin receives flat 403."""
        from src.kene_api.auth.dependencies import SuperAdminRequiredError

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit")

        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    # ------------------------------------------------------------------
    # Case 5: missing token → 401
    # ------------------------------------------------------------------

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        """No Authorization header → 401."""
        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit")
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # Case 6: invalid key → 422
    # ------------------------------------------------------------------

    def test_invalid_key_returns_422(self, client: TestClient) -> None:
        """Key not matching FLAG_KEY_REGEX → 422."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.get("/api/v1/admin/feature-flags/INVALID-KEY!/audit")
        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # Case 7: limit=0 → 422
    # ------------------------------------------------------------------

    def test_limit_zero_returns_422(self, client: TestClient) -> None:
        """limit=0 violates Query(ge=1) → 422."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit?limit=0")
        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # Case 8: limit=51 → 422
    # ------------------------------------------------------------------

    def test_limit_51_returns_422(self, client: TestClient) -> None:
        """limit=51 violates Query(le=50) → 422."""

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit?limit=51")
        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # Case 9: service exception → 500
    # ------------------------------------------------------------------

    def test_service_exception_propagates_to_500(self, client: TestClient) -> None:
        """Firestore failure propagates to 500 — admin callers need real errors."""
        svc = MagicMock()
        svc.get_flag_audit = AsyncMock(side_effect=RuntimeError("Firestore down"))

        async def _admin() -> UserContext:
            return _make_super_admin()

        app.dependency_overrides[require_super_admin] = _admin
        app.dependency_overrides[get_feature_flag_service] = lambda: svc

        resp = client.get("/api/v1/admin/feature-flags/test_flag/audit")
        assert resp.status_code == 500
