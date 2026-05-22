"""Integration tests for /api/v1/admin/feature-flags/* (super-admin CRUD + audit).

Exercises the full router → service → Firestore round-trip against the real
Firestore emulator. Unit-level isolation (mocked services) lives in
test_admin_feature_flags_router.py. This file covers what only a live emulator
can verify: atomic creates, 409/404 conflicts, audit-row side-effects, and
cursor-based pagination.

Enable by setting the FIRESTORE_EMULATOR_HOST environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_admin_feature_flags_endpoints.py -v

PRD §8 Backend scenarios all covered here:
  - Super-admin CRUD happy paths (AC-1)
  - Non-super-admin receives 403 on every endpoint (AC-1)
  - Duplicate-create returns 409 (AC-2)
  - Delete-then-get returns 404 (AC-3)
  - Audit written for each mutation with actor email (AC-4 integration side)
  - GET /{key}/audit paginates correctly: 3 pages, verify order + cursor (AC-5)
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import SuperAdminRequiredError, require_super_admin
from src.kene_api.auth.models import UserContext
from src.kene_api.dependencies import get_feature_flag_service
from src.kene_api.main import app
from src.kene_api.services.feature_flag_service import FeatureFlagService

# ---------------------------------------------------------------------------
# Skip gate — identical to test_feature_flag_evaluate_endpoint.py:47-54
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ADMIN_EMAIL = "admin@ken-e.ai"


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


def _valid_write_payload(**overrides: Any) -> dict[str, Any]:
    """Minimal valid FeatureFlagWriteRequest payload."""
    base: dict[str, Any] = {
        "key": "new_flag",
        "description": "Integration test flag",
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


@pytest.fixture
def flag_key(run_id: str) -> str:
    return f"test_flag_{run_id}"


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
    """Guarantee dependency_overrides is clean and the service singleton is reset.

    Calls get_feature_flag_service.cache_clear() belt-and-braces so even if an
    earlier test warmed the module-level singleton, this test starts fresh.
    Mirrors test_feature_flag_evaluate_endpoint.py:140-156.
    """
    from src.kene_api.services.feature_flag_service import (
        get_feature_flag_service as _svc_singleton,
    )

    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()
    yield
    app.dependency_overrides.clear()
    _svc_singleton.cache_clear()


@pytest.fixture(autouse=True)
def cleanup_emulator(
    emulator_db: Any,
    flag_key: str,
) -> Generator[None, None, None]:
    """Best-effort cleanup of the flag doc and all its audit rows before and after each test.

    Pre-test pass removes stale data from a prior failed run; post-test pass removes
    data from the current run. Audit cleanup queries by flag_key (not audit_id) because
    audit IDs are not predictable in advance — the per-test run_id suffix makes flag_key
    a unique selector for that test's emitted rows (Shape C, README §7.5).

    Mirrors test_feature_flag_evaluate_endpoint.py:159-179.
    """

    def _delete_flag_and_audit() -> None:
        try:
            emulator_db.collection("feature_flags").document(flag_key).delete()
        except Exception:
            pass
        try:
            for doc in (
                emulator_db.collection("feature_flag_audit")
                .where("flag_key", "==", flag_key)
                .stream()
            ):
                doc.reference.delete()
        except Exception:
            pass

    _delete_flag_and_audit()
    yield
    _delete_flag_and_audit()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared install helper (method-level, used inside test classes)
# ---------------------------------------------------------------------------


def _install_overrides(
    emulator_db: Any,
    as_super_admin: bool = True,
) -> FeatureFlagService:
    """Wire per-test auth and service dependency overrides.

    When as_super_admin=True  → require_super_admin returns a real super-admin
                                 UserContext (happy-path tests).
    When as_super_admin=False → require_super_admin raises SuperAdminRequiredError
                                 (403 cases).

    Returns the live FeatureFlagService bound to the emulator so callers can
    interrogate the cache or call service methods directly.
    """
    svc = FeatureFlagService(db=emulator_db)

    if as_super_admin:
        admin = _make_super_admin()

        async def _super_admin_gate() -> UserContext:
            return admin

        app.dependency_overrides[require_super_admin] = _super_admin_gate
    else:

        async def _non_admin_gate() -> UserContext:
            raise SuperAdminRequiredError()

        app.dependency_overrides[require_super_admin] = _non_admin_gate

    app.dependency_overrides[get_feature_flag_service] = lambda: svc
    return svc


# ---------------------------------------------------------------------------
# TestAdminAuth — AC-1: every endpoint returns 403 for non-super-admins
# ---------------------------------------------------------------------------


class TestAdminAuth:
    """Non-super-admin receives flat 403 on every admin endpoint.

    One test per endpoint verifies the SuperAdminRequiredError → 403 contract
    across all six routes (PRD §7 AC-1, FF-PRD-02 §7.6).
    """

    def test_list_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.get("/api/v1/admin/feature-flags")
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_get_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.get(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_post_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.post(
            "/api/v1/admin/feature-flags",
            json=_valid_write_payload(key=flag_key),
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_put_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.put(
            f"/api/v1/admin/feature-flags/{flag_key}",
            json=_valid_write_payload(key=flag_key),
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_delete_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.delete(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}

    def test_audit_returns_403_for_non_super_admin(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=False)
        resp = client.get(f"/api/v1/admin/feature-flags/{flag_key}/audit")
        assert resp.status_code == 403
        assert resp.json() == {"error": "super_admin_required"}


# ---------------------------------------------------------------------------
# TestSuperAdminCrudHappyPath — AC-1 (mutating half): full lifecycle in one test
# ---------------------------------------------------------------------------


class TestSuperAdminCrudHappyPath:
    """POST → GET → list → PUT → DELETE against the real emulator.

    Consolidated into one test method per AC-8 rationale (plan architecture
    decision 4): a single class-scoped emulator_db + one lifecycle test avoids
    O(N) TCP setup overhead and keeps the full suite under ~12 methods.
    """

    def test_full_crud_lifecycle(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """End-to-end CRUD: create → read → list → update → delete, all against the emulator."""
        _install_overrides(emulator_db, as_super_admin=True)

        # --- POST: create ---
        create_payload = _valid_write_payload(key=flag_key)
        resp_create = client.post("/api/v1/admin/feature-flags", json=create_payload)
        assert resp_create.status_code == 201
        body = resp_create.json()
        assert body["key"] == flag_key
        assert body["description"] == "Integration test flag"
        assert "created_at" in body and "updated_at" in body

        # Verify the doc actually landed in Firestore (not just returned from cache).
        doc_after_create = (
            emulator_db.collection("feature_flags").document(flag_key).get()
        )
        assert doc_after_create.exists, "flag doc must exist in Firestore after POST"

        # --- GET /{key}: read single ---
        resp_get = client.get(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp_get.status_code == 200
        assert resp_get.json()["key"] == flag_key

        # --- GET /: list includes the new flag ---
        resp_list = client.get("/api/v1/admin/feature-flags")
        assert resp_list.status_code == 200
        keys_in_list = {f["key"] for f in resp_list.json()["flags"]}
        assert flag_key in keys_in_list, (
            f"Expected {flag_key!r} in list response; got {keys_in_list!r}"
        )

        # --- PUT /{key}: update description ---
        updated_payload = _valid_write_payload(key=flag_key, description="Updated desc")
        resp_put = client.put(
            f"/api/v1/admin/feature-flags/{flag_key}", json=updated_payload
        )
        assert resp_put.status_code == 200
        put_body = resp_put.json()
        assert put_body["description"] == "Updated desc"
        # updated_at must advance (server-stamped)
        assert datetime.fromisoformat(put_body["updated_at"]) >= datetime.fromisoformat(
            body["updated_at"]
        )

        # Verify description written to Firestore.
        doc_after_put = emulator_db.collection("feature_flags").document(flag_key).get()
        assert doc_after_put.to_dict()["description"] == "Updated desc"

        # --- DELETE /{key} ---
        resp_delete = client.delete(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp_delete.status_code == 204
        assert resp_delete.content == b""

        # Verify doc is gone from Firestore.
        doc_after_delete = (
            emulator_db.collection("feature_flags").document(flag_key).get()
        )
        assert not doc_after_delete.exists, "flag doc must be absent after DELETE"


# ---------------------------------------------------------------------------
# TestErrorPaths — AC-2 (409 duplicate) + AC-3 (404 after delete/missing)
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """Error path coverage: duplicate create (409), delete-then-get (404), missing PUT (404)."""

    def test_duplicate_create_returns_409(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """POST same key twice → 201 then 409 with detail containing the key (AC-2)."""
        _install_overrides(emulator_db, as_super_admin=True)
        payload = _valid_write_payload(key=flag_key)

        resp1 = client.post("/api/v1/admin/feature-flags", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/admin/feature-flags", json=payload)
        assert resp2.status_code == 409
        assert flag_key in resp2.json()["detail"]

    def test_delete_then_get_returns_404(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """POST → DELETE → GET → 404 with detail containing the key (AC-3)."""
        _install_overrides(emulator_db, as_super_admin=True)
        payload = _valid_write_payload(key=flag_key)

        resp_create = client.post("/api/v1/admin/feature-flags", json=payload)
        assert resp_create.status_code == 201

        resp_delete = client.delete(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp_delete.status_code == 204

        resp_get = client.get(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp_get.status_code == 404
        assert flag_key in resp_get.json()["detail"]

    def test_put_missing_flag_returns_404(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """PUT on a key that was never created → 404 with detail containing the key."""
        _install_overrides(emulator_db, as_super_admin=True)
        payload = _valid_write_payload(key=flag_key)

        resp = client.put(f"/api/v1/admin/feature-flags/{flag_key}", json=payload)
        assert resp.status_code == 404
        assert flag_key in resp.json()["detail"]


# ---------------------------------------------------------------------------
# TestAuditWritten — AC-4 (integration side): audit row written per mutation
# ---------------------------------------------------------------------------


class TestAuditWritten:
    """For each of POST / PUT / DELETE: verify one audit row is written to Firestore.

    Directly queries feature_flag_audit collection by flag_key (not audit_id) so
    the check does not depend on knowing the generated audit_id in advance.
    """

    def _read_audit_rows(self, emulator_db: Any, flag_key: str) -> list[dict[str, Any]]:
        from google.cloud import firestore as _fs

        docs = (
            emulator_db.collection("feature_flag_audit")
            .where("flag_key", "==", flag_key)
            .order_by("created_at", direction=_fs.Query.DESCENDING)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def test_create_writes_audit_row(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """POST creates exactly one audit row with action='create' and actor email (AC-4)."""
        _install_overrides(emulator_db, as_super_admin=True)

        resp = client.post(
            "/api/v1/admin/feature-flags", json=_valid_write_payload(key=flag_key)
        )
        assert resp.status_code == 201

        rows = self._read_audit_rows(emulator_db, flag_key)
        assert len(rows) == 1, f"Expected 1 audit row after POST; got {len(rows)}"
        row = rows[0]
        assert row["flag_key"] == flag_key
        assert row["actor_email"] == _ADMIN_EMAIL
        assert row["action"] == "create"
        assert row["diff"], "diff must be non-empty for a create"
        assert "created_at" not in row["diff"], "timestamps must be excluded from diff"
        assert "updated_at" not in row["diff"], "timestamps must be excluded from diff"

    def test_update_writes_audit_row(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """PUT writes exactly one audit row with action='update' (AC-4)."""
        _install_overrides(emulator_db, as_super_admin=True)

        # First create the flag so PUT has something to update.
        resp_create = client.post(
            "/api/v1/admin/feature-flags", json=_valid_write_payload(key=flag_key)
        )
        assert resp_create.status_code == 201

        resp_put = client.put(
            f"/api/v1/admin/feature-flags/{flag_key}",
            json=_valid_write_payload(key=flag_key, description="Changed description"),
        )
        assert resp_put.status_code == 200

        rows = self._read_audit_rows(emulator_db, flag_key)
        # Assert total row count first so a spurious extra audit row surfaces the root
        # cause before the filter narrows to the 'update' action (CLAUDE.md T-8).
        assert len(rows) == 2, (
            f"Expected 2 audit rows total (1 create + 1 update); got {len(rows)}"
        )
        update_rows = [r for r in rows if r["action"] == "update"]
        assert len(update_rows) == 1, (
            f"Expected 1 update audit row; got {len(update_rows)} (total rows: {len(rows)})"
        )
        row = update_rows[0]
        assert row["actor_email"] == _ADMIN_EMAIL
        assert "description" in row["diff"], "diff must contain the changed field"

    def test_delete_writes_audit_row(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        """DELETE writes exactly one audit row with action='delete' (AC-4)."""
        _install_overrides(emulator_db, as_super_admin=True)

        resp_create = client.post(
            "/api/v1/admin/feature-flags", json=_valid_write_payload(key=flag_key)
        )
        assert resp_create.status_code == 201

        resp_delete = client.delete(f"/api/v1/admin/feature-flags/{flag_key}")
        assert resp_delete.status_code == 204

        rows = self._read_audit_rows(emulator_db, flag_key)
        delete_rows = [r for r in rows if r["action"] == "delete"]
        assert len(delete_rows) == 1, (
            f"Expected 1 delete audit row; got {len(delete_rows)} (total rows: {len(rows)})"
        )
        row = delete_rows[0]
        assert row["actor_email"] == _ADMIN_EMAIL
        assert row["diff"], "diff must be non-empty for a delete"


# ---------------------------------------------------------------------------
# TestAuditPagination — AC-5: GET /{key}/audit paginates with cursor
# ---------------------------------------------------------------------------


class TestAuditPagination:
    """Verify 3-page cursor pagination over 6 audit rows (1 create + 5 updates).

    Rationale (plan architecture decision 5):
    - 5 update calls + 1 create = 6 audit rows total.
    - limit=2 → 3 pages (2, 2, 2) — smallest count that exercises both the
      has_next=True (pages 1, 2) and has_next=False (page 3 terminal) branches in
      FeatureFlagService.get_flag_audit (service.py:395-397).
    - Ordering is created_at-descending (newest-first per PRD §4).
    - No audit_id must appear on more than one page.
    """

    def test_audit_paginates_with_cursor_over_three_pages(
        self, client: TestClient, emulator_db: Any, flag_key: str
    ) -> None:
        _install_overrides(emulator_db, as_super_admin=True)

        # Seed: 1 create + 5 updates = 6 total audit rows.
        resp_create = client.post(
            "/api/v1/admin/feature-flags", json=_valid_write_payload(key=flag_key)
        )
        assert resp_create.status_code == 201

        for i in range(5):
            # 10 ms sleep guarantees strictly increasing created_at values for the
            # ordering assertion below (plan risk mitigation — 2 ms is below typical
            # emulator write latency; 10 ms exceeds any realistic clock resolution).
            time.sleep(0.01)
            resp_put = client.put(
                f"/api/v1/admin/feature-flags/{flag_key}",
                json=_valid_write_payload(key=flag_key, description=f"Update {i}"),
            )
            assert resp_put.status_code == 200

        # --- Page 1 ---
        resp_p1 = client.get(f"/api/v1/admin/feature-flags/{flag_key}/audit?limit=2")
        assert resp_p1.status_code == 200
        body_p1 = resp_p1.json()
        assert len(body_p1["entries"]) == 2
        assert body_p1["next_cursor"] is not None, "Page 1 must have a next_cursor"
        ids_p1 = {e["audit_id"] for e in body_p1["entries"]}

        # --- Page 2 ---
        # Use params= so TestClient (requests) percent-encodes the cursor value.
        # Embedding the cursor in an f-string URL is unsafe because the cursor format
        # is "{iso_datetime}_{uuid8}" — the "+" in "+00:00" would be decoded as a
        # space by the query-string parser, causing the Firestore lookup to fail.
        cursor_1 = body_p1["next_cursor"]
        resp_p2 = client.get(
            f"/api/v1/admin/feature-flags/{flag_key}/audit",
            params={"limit": 2, "cursor": cursor_1},
        )
        assert resp_p2.status_code == 200
        body_p2 = resp_p2.json()
        assert len(body_p2["entries"]) == 2
        assert body_p2["next_cursor"] is not None, "Page 2 must have a next_cursor"
        ids_p2 = {e["audit_id"] for e in body_p2["entries"]}

        # --- Page 3 (terminal) ---
        cursor_2 = body_p2["next_cursor"]
        resp_p3 = client.get(
            f"/api/v1/admin/feature-flags/{flag_key}/audit",
            params={"limit": 2, "cursor": cursor_2},
        )
        assert resp_p3.status_code == 200
        body_p3 = resp_p3.json()
        assert len(body_p3["entries"]) == 2
        assert body_p3["next_cursor"] is None, "Page 3 must be the terminal page"
        ids_p3 = {e["audit_id"] for e in body_p3["entries"]}

        # All 6 audit rows covered, no duplicates across pages (AC-5).
        all_ids = ids_p1 | ids_p2 | ids_p3
        assert len(all_ids) == 6, (
            f"Expected 6 distinct audit_ids across 3 pages; got {len(all_ids)}: {all_ids}"
        )
        assert ids_p1.isdisjoint(ids_p2), "Page 1 and 2 must not share audit_ids"
        assert ids_p1.isdisjoint(ids_p3), "Page 1 and 3 must not share audit_ids"
        assert ids_p2.isdisjoint(ids_p3), "Page 2 and 3 must not share audit_ids"

        # Each page is in newest-first order (created_at descending) — page 1
        # entries must be newer than page 3 entries.
        p1_newest = body_p1["entries"][0]["created_at"]
        p3_oldest = body_p3["entries"][-1]["created_at"]
        assert p1_newest >= p3_oldest, (
            f"Page 1 newest ({p1_newest!r}) must be >= page 3 oldest ({p3_oldest!r}) "
            "— audit list must be newest-first"
        )
