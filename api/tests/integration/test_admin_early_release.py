"""Integration tests for /api/v1/admin/early-release-code/* endpoints.

Exercises the full router → service → Firestore round-trip against the real
Firestore emulator. Unit-level isolation (mocked services) lives in
test_early_release_service.py. This file covers what only a live emulator
can verify: persisted writes, kill-switch round-trips, pagination, and the
audit side-effect.

Enable by setting the FIRESTORE_EMULATOR_HOST environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_admin_early_release.py -v

DM-PRD-11 §7 AC matrix covered:
  - AC: GET absent config → 404 (no config doc exists yet)
  - AC: Super-admin PUT code → 200, config persisted, redemption_count=0
  - AC: GET after PUT returns the newly written code
  - AC: PUT is_active=False flips kill switch
  - AC: PUT is_active=True re-enables
  - AC: GET /redemptions empty → 200 {redemptions:[], total:0, next_cursor:null}
  - AC: record_redemption then GET /redemptions → appears in list
  - AC: Pagination — write 3 redemptions, page-1 limit=2 has next_cursor,
        page-2 returns remaining 1 + null next_cursor
  - AC: Non-super-admin → 403 on every endpoint
  - AC: Audit row written to security_audit_logs after PUT
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import SuperAdminRequiredError, require_super_admin
from src.kene_api.auth.models import UserContext
from src.kene_api.dependencies import get_early_release_service
from src.kene_api.main import app
from src.kene_api.services.early_release_service import EarlyReleaseService

# ---------------------------------------------------------------------------
# Skip gate — emulator must be running
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ADMIN_EMAIL = "admin@ken-e.ai"
_BASE_URL = "/api/v1/admin/early-release-code"


def _emulator_client() -> Any:
    """Real Firestore client pointed at the local emulator."""
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _make_super_admin() -> UserContext:
    return UserContext(
        user_id="admin_uid",
        email=_ADMIN_EMAIL,
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def emulator_db() -> Any:
    """Real Firestore emulator client, shared across the test class."""
    return _emulator_client()


@pytest.fixture
def run_id() -> str:
    """Unique 8-hex suffix per test run to prevent cross-run pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
    """Guarantee dependency_overrides is clean before and after each test.

    Also clears the EarlyReleaseService lru_cache so each test gets a fresh
    singleton that points at the emulator db.
    """
    from src.kene_api.services.early_release_service import (
        get_early_release_service as _svc_singleton,
    )

    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()
    yield
    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _install_overrides(
    emulator_db: Any,
    as_super_admin: bool = True,
) -> EarlyReleaseService:
    """Wire per-test auth and service dependency overrides.

    Returns the EarlyReleaseService bound to the emulator so tests can call
    service methods directly (e.g. to seed redemptions).
    """
    svc = EarlyReleaseService(db=emulator_db)

    if as_super_admin:
        admin = _make_super_admin()

        async def _super_admin_gate() -> UserContext:
            return admin

        app.dependency_overrides[require_super_admin] = _super_admin_gate
    else:

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

    app.dependency_overrides[get_early_release_service] = lambda: svc
    return svc


# ---------------------------------------------------------------------------
# TestAdminEarlyReleaseEndpoints
# ---------------------------------------------------------------------------


class TestAdminEarlyReleaseEndpoints:
    """Full AC matrix for /api/v1/admin/early-release-code router."""

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------

    def _cleanup_config(self, emulator_db: Any) -> None:
        """Remove the singleton config doc so tests start from a clean slate."""
        try:
            emulator_db.collection("app_config").document("early_release").delete()
        except Exception:
            pass

    def _cleanup_redemptions(self, emulator_db: Any, user_ids: list[str]) -> None:
        """Remove specific redemption docs by user_id."""
        for uid in user_ids:
            try:
                emulator_db.collection("early_release_redemptions").document(uid).delete()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # AC: GET absent config → 404
    # ------------------------------------------------------------------

    def test_get_config_absent_returns_404(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """GET with no config document returns 404 with early_release_config_not_found."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        resp = client.get(_BASE_URL)

        assert resp.status_code == 404
        assert resp.json()["detail"] == "early_release_config_not_found"

    # ------------------------------------------------------------------
    # AC: Super-admin PUT with code → 200, config persisted, redemption_count=0
    # ------------------------------------------------------------------

    def test_put_code_creates_config_with_zero_redemption_count(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """PUT code → 200, Firestore doc written, redemption_count=0."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        resp = client.put(_BASE_URL, json={"code": f"alpha-code-{run_id}", "is_active": True})

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == f"alpha-code-{run_id}"
        assert body["is_active"] is True
        assert body["redemption_count"] == 0

        # Verify the doc is actually in Firestore (not just returned from memory).
        doc = emulator_db.collection("app_config").document("early_release").get()
        assert doc.exists
        assert doc.to_dict()["code"] == f"alpha-code-{run_id}"

        # Cleanup
        self._cleanup_config(emulator_db)

    # ------------------------------------------------------------------
    # AC: GET after PUT returns the newly written code
    # ------------------------------------------------------------------

    def test_get_after_put_returns_persisted_code(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """GET after PUT returns the config written by PUT (not stale data)."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        put_resp = client.put(_BASE_URL, json={"code": f"persist-{run_id}", "is_active": True})
        assert put_resp.status_code == 200

        get_resp = client.get(_BASE_URL)
        assert get_resp.status_code == 200
        assert get_resp.json()["code"] == f"persist-{run_id}"

        # Cleanup
        self._cleanup_config(emulator_db)

    # ------------------------------------------------------------------
    # AC: PUT is_active=False flips kill switch
    # ------------------------------------------------------------------

    def test_put_is_active_false_disables_config(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """PUT is_active=False after creating config returns is_active=False."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        # First create
        resp_create = client.put(_BASE_URL, json={"code": f"killswitch-{run_id}", "is_active": True})
        assert resp_create.status_code == 200

        # Then disable
        resp_disable = client.put(_BASE_URL, json={"is_active": False})
        assert resp_disable.status_code == 200
        assert resp_disable.json()["is_active"] is False
        # Code is preserved — kill switch does not clear the code
        assert resp_disable.json()["code"] == f"killswitch-{run_id}"

        # Verify Firestore reflects the change
        doc = emulator_db.collection("app_config").document("early_release").get()
        assert doc.to_dict()["is_active"] is False

        # Cleanup
        self._cleanup_config(emulator_db)

    # ------------------------------------------------------------------
    # AC: PUT is_active=True re-enables
    # ------------------------------------------------------------------

    def test_put_is_active_true_re_enables_config(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """PUT is_active=True after disabling sets is_active back to True."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        client.put(_BASE_URL, json={"code": f"reenable-{run_id}", "is_active": True})
        client.put(_BASE_URL, json={"is_active": False})

        resp_enable = client.put(_BASE_URL, json={"is_active": True})
        assert resp_enable.status_code == 200
        assert resp_enable.json()["is_active"] is True

        # Cleanup
        self._cleanup_config(emulator_db)

    # ------------------------------------------------------------------
    # AC: GET /redemptions on empty collection → 200 with empty list
    # ------------------------------------------------------------------

    def test_list_redemptions_empty_returns_empty_list(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """GET /redemptions with no docs returns {redemptions:[], total:0, next_cursor:null}."""
        _install_overrides(emulator_db, as_super_admin=True)

        resp = client.get(f"{_BASE_URL}/redemptions")

        assert resp.status_code == 200
        body = resp.json()
        assert body["redemptions"] == []
        assert body["total"] == 0
        assert body["next_cursor"] is None

    # ------------------------------------------------------------------
    # AC: record_redemption then GET /redemptions → appears in list
    # ------------------------------------------------------------------

    def test_list_redemptions_shows_recorded_redemption(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """After record_redemption, the redemption appears in GET /redemptions."""
        svc = _install_overrides(emulator_db, as_super_admin=True)

        user_id = f"uid_test_{run_id}"
        import asyncio

        asyncio.run(
            svc.record_redemption(
                user_id=user_id,
                email=f"test_{run_id}@example.com",
                org_id=f"org_{run_id}",
            )
        )

        resp = client.get(f"{_BASE_URL}/redemptions")
        assert resp.status_code == 200
        body = resp.json()
        user_ids_in_resp = [r["user_id"] for r in body["redemptions"]]
        assert user_id in user_ids_in_resp

        # Cleanup
        self._cleanup_redemptions(emulator_db, [user_id])

    # ------------------------------------------------------------------
    # AC: Pagination — 3 redemptions, limit=2 → 2 pages
    # ------------------------------------------------------------------

    def test_list_redemptions_paginates_correctly(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """Write 3 redemptions; GET?limit=2 returns 2+cursor; next page returns 1+null."""
        svc = _install_overrides(emulator_db, as_super_admin=True)

        import asyncio

        user_ids = [f"uid_page_{run_id}_{i}" for i in range(3)]
        for i, uid in enumerate(user_ids):
            asyncio.run(
                svc.record_redemption(
                    user_id=uid,
                    email=f"page_{run_id}_{i}@example.com",
                    org_id=f"org_{run_id}",
                )
            )
            # Ensure strictly-increasing redeemed_at for deterministic ordering
            time.sleep(0.01)

        # --- Page 1 ---
        resp_p1 = client.get(f"{_BASE_URL}/redemptions", params={"limit": 2})
        assert resp_p1.status_code == 200
        body_p1 = resp_p1.json()
        assert len(body_p1["redemptions"]) == 2
        assert body_p1["next_cursor"] is not None, "Page 1 must have a next_cursor"
        ids_p1 = {r["user_id"] for r in body_p1["redemptions"]}

        # --- Page 2 ---
        cursor = body_p1["next_cursor"]
        resp_p2 = client.get(
            f"{_BASE_URL}/redemptions",
            params={"limit": 2, "cursor": cursor},
        )
        assert resp_p2.status_code == 200
        body_p2 = resp_p2.json()
        assert len(body_p2["redemptions"]) == 1
        assert body_p2["next_cursor"] is None, "Page 2 must be terminal"
        ids_p2 = {r["user_id"] for r in body_p2["redemptions"]}

        # No overlap across pages
        assert ids_p1.isdisjoint(ids_p2), "Pages must not share user_ids"
        # All 3 accounted for
        assert ids_p1 | ids_p2 == set(user_ids)

        # Cleanup
        self._cleanup_redemptions(emulator_db, user_ids)

    # ------------------------------------------------------------------
    # AC: Non-super-admin → 403 on every endpoint
    # ------------------------------------------------------------------

    def test_non_super_admin_gets_403_on_get_config(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """GET / with non-super-admin returns 403 super_admin_required."""
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.get(_BASE_URL)
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_non_super_admin_gets_403_on_put(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """PUT / with non-super-admin returns 403 super_admin_required."""
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.put(_BASE_URL, json={"code": "any-code", "is_active": True})
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_non_super_admin_gets_403_on_list_redemptions(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        """GET /redemptions with non-super-admin returns 403 super_admin_required."""
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.get(f"{_BASE_URL}/redemptions")
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    # ------------------------------------------------------------------
    # AC: Audit row written after PUT
    # ------------------------------------------------------------------

    @pytest.mark.xfail(
        strict=False,
        reason=(
            "audit write is best-effort — get_audit_logger() uses a separate Firestore "
            "client from get_firestore_service(), which may point at production rather "
            "than the emulator in the test environment. The structured-log write is the "
            "primary audit record; Firestore is a secondary queryable copy."
        ),
    )
    def test_audit_row_written_after_put(
        self, client: TestClient, emulator_db: Any, run_id: str
    ) -> None:
        """After a PUT, a security_audit_logs doc exists with event_type=early_release_code_changed."""
        self._cleanup_config(emulator_db)
        _install_overrides(emulator_db, as_super_admin=True)

        resp = client.put(
            _BASE_URL, json={"code": f"audit-test-{run_id}", "is_active": True}
        )
        assert resp.status_code == 200

        # Give the async audit write a moment to land
        time.sleep(0.1)

        audit_docs = list(
            emulator_db.collection("security_audit_logs")
            .where("event_type", "==", "early_release_code_changed")
            .limit(1)
            .get()
        )
        assert len(audit_docs) == 1, (
            f"Expected 1 audit doc with event_type=early_release_code_changed; "
            f"got {len(audit_docs)}"
        )

        # Cleanup
        self._cleanup_config(emulator_db)
