"""Integration tests for the per-account agent-config CRUD API.

Covers ``/api/v1/accounts/{account_id}/agent-configs`` (``account_router``).

Two test classes:

* ``TestAccountAgentConfigsAuth`` — authorization tests; no Firestore emulator
  needed; run on every CI invocation.
* ``TestAccountAgentConfigsEmulator`` — full round-trip tests against the
  Firestore emulator; skipped when ``FIRESTORE_EMULATOR_HOST`` is unset.

Enable emulator tests:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_agent_configs_api.py -v

Acceptance criteria covered:
  AC-11 (AH-PRD-02 §6):
    - List merged configs (global auto-available + per-account overlays/customs)
    - Optional ?visible_in_frontend=true filter
    - GET /{config_id} → merged config; 404 when absent
    - POST / → custom agent; server generates custom_{uuid8} config_id; 201
    - PUT /{config_id} → upsert overlay; records based_on_version; customization_status
    - DELETE custom_* → full delete; DELETE non-custom → overlay only (revert to global)
  Authorization:
    - Reads require any account access (view-role sufficient)
    - Writes require admin role
    - Super-admin always has access
    - Users with no account access → 403 on all five endpoints
"""

from __future__ import annotations

import os
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.dependencies import get_firestore
from src.kene_api.main import app

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

ACCOUNT_ID = "acc_test_001"
BASE_URL = f"/api/v1/accounts/{ACCOUNT_ID}/agent-configs"

_VALID_GLOBAL_DOC: dict[str, Any] = {
    "name": "Test Researcher",
    "instruction": "You are a test researcher assistant.",
    "model": "gemini-2.5-flash",
    "description": "A test agent for integration tests.",
    "automatically_available": True,
    "visible_in_frontend": True,
    "metadata": {
        "version": "v3.2.1",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "updated_by": "seed@test.com",
        "notes": "",
    },
}


def _super_admin() -> UserContext:
    return UserContext(
        user_id="super-uid",
        email="ops@ken-e.ai",
        organization_permissions={},
        account_permissions={},
    )


def _account_admin() -> UserContext:
    """Org admin — has_account_access returns True for any account."""
    return UserContext(
        user_id="admin-uid",
        email="admin@example.com",
        organization_permissions={"org_abc": "admin"},
        account_permissions={},
    )


def _view_only_user() -> UserContext:
    """Explicit view-role account member; no org admin rights."""
    return UserContext(
        user_id="viewer-uid",
        email="viewer@example.com",
        organization_permissions={},
        account_permissions={ACCOUNT_ID: "view"},
    )


def _no_access_user() -> UserContext:
    """User with no permissions at all."""
    return UserContext(
        user_id="stranger-uid",
        email="stranger@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _noop_firestore() -> MagicMock:
    """Minimal Firestore mock that won't crash on collection().stream() calls.

    Returns empty iterables so list endpoints return [] rather than 500.
    """
    db = MagicMock()
    # stream() returns an empty iterable by default from MagicMock, but
    # explicitly set it to be safe.
    db.collection.return_value.stream.return_value = iter([])
    db.collection.return_value.document.return_value.collection.return_value.stream.return_value = iter([])
    return db


# ---------------------------------------------------------------------------
# Category A — Authorization tests (no emulator; always run)
# ---------------------------------------------------------------------------


class TestAccountAgentConfigsAuth:
    """Authorization tests for the per-account agent-config endpoints.

    Uses TestClient + mocked Firestore + mocked user context.  No emulator
    required.  Covers the four user-context scenarios for every HTTP verb.
    """

    @pytest.fixture(autouse=True)
    def _reset_overrides(self):
        """Guarantee ``dependency_overrides`` is clean before and after each test."""
        app.dependency_overrides.clear()
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _install_user(self, user: UserContext) -> None:
        async def _get_user():
            return user

        app.dependency_overrides[get_current_user_context] = _get_user

    def _install_db(self, db: MagicMock | None = None) -> None:
        mock = db or _noop_firestore()
        app.dependency_overrides[get_firestore] = lambda: mock

    # ------------------------------------------------------------------
    # No-access user → 403 on all five endpoints
    # ------------------------------------------------------------------

    def test_no_access_user_get_list_is_403(self, client: TestClient) -> None:
        """User with no permissions cannot list configs."""
        self._install_user(_no_access_user())
        self._install_db()
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 403

    def test_no_access_user_get_single_is_403(self, client: TestClient) -> None:
        """User with no permissions cannot read a specific config."""
        self._install_user(_no_access_user())
        self._install_db()
        resp = client.get(BASE_URL + "/some_agent")
        assert resp.status_code == 403

    def test_no_access_user_post_is_403(self, client: TestClient) -> None:
        """User with no permissions cannot create a custom agent."""
        self._install_user(_no_access_user())
        self._install_db()
        body = {
            "name": "My Agent",
            "instruction": "You are a helpful assistant for testing.",
            "model": "gemini-2.5-flash",
        }
        resp = client.post(BASE_URL + "/", json=body)
        assert resp.status_code == 403

    def test_no_access_user_put_is_403(self, client: TestClient) -> None:
        """User with no permissions cannot upsert an overlay."""
        self._install_user(_no_access_user())
        self._install_db()
        resp = client.put(BASE_URL + "/some_agent", json={})
        assert resp.status_code == 403

    def test_no_access_user_delete_is_403(self, client: TestClient) -> None:
        """User with no permissions cannot delete a config."""
        self._install_user(_no_access_user())
        self._install_db()
        resp = client.delete(BASE_URL + "/some_agent")
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # View-only user — reads allowed; writes denied (403)
    # ------------------------------------------------------------------

    def test_view_only_user_get_list_is_allowed(self, client: TestClient) -> None:
        """View-role account member can list configs (returns 200 with empty list)."""
        self._install_user(_view_only_user())
        self._install_db()
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_view_only_user_post_is_403(self, client: TestClient) -> None:
        """View-role user cannot create a custom agent (admin required for writes)."""
        self._install_user(_view_only_user())
        self._install_db()
        body = {
            "name": "My Agent",
            "instruction": "You are a helpful assistant for testing.",
            "model": "gemini-2.5-flash",
        }
        resp = client.post(BASE_URL + "/", json=body)
        assert resp.status_code == 403

    def test_view_only_user_put_is_403(self, client: TestClient) -> None:
        """View-role user cannot upsert an overlay (admin required for writes)."""
        self._install_user(_view_only_user())
        self._install_db()
        resp = client.put(BASE_URL + "/some_agent", json={})
        assert resp.status_code == 403

    def test_view_only_user_delete_is_403(self, client: TestClient) -> None:
        """View-role user cannot delete a config (admin required for writes)."""
        self._install_user(_view_only_user())
        self._install_db()
        resp = client.delete(BASE_URL + "/some_agent")
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # Super-admin → 200/201 on all endpoints (auth passes; data may be empty)
    # ------------------------------------------------------------------

    def test_super_admin_get_list_is_200(self, client: TestClient) -> None:
        """Super-admin can list configs (returns 200)."""
        self._install_user(_super_admin())
        self._install_db()
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200

    def test_super_admin_post_is_201(self, client: TestClient) -> None:
        """Super-admin can create a custom agent (201)."""
        self._install_user(_super_admin())

        # Wire up a Firestore mock that survives the set() + _load_merged path.
        db = MagicMock()

        # The POST endpoint calls:
        #   db.collection("accounts").document(account_id)
        #     .collection("agent_configs").document(custom_id).set(data)
        # Then _load_merged calls:
        #   db.collection("agent_configs").document(custom_id).get()  → no global
        #   db.collection("accounts")... .get()  → returns the just-created doc

        no_global_doc = MagicMock()
        no_global_doc.exists = False
        no_global_doc.to_dict.return_value = None

        created_doc = MagicMock()
        created_doc.exists = True
        created_doc.to_dict.return_value = {
            "name": "My Agent",
            "instruction": "You are a helpful assistant for testing.",
            "model": "gemini-2.5-flash",
            "customization_status": "custom_agent",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "created_by": "ops@ken-e.ai",
        }

        # Make global collection return "not found"
        global_col = MagicMock()
        global_col.document.return_value.get.return_value = no_global_doc

        # Make accounts collection return a doc ref that:
        # - .set() succeeds silently
        # - sub-collection .document().get() returns created_doc
        account_doc_ref = MagicMock()
        agent_configs_sub = MagicMock()
        custom_doc_ref = MagicMock()
        custom_doc_ref.get.return_value = created_doc
        custom_doc_ref.set.return_value = None
        agent_configs_sub.document.return_value = custom_doc_ref
        account_doc_ref.collection.return_value = agent_configs_sub

        accounts_col = MagicMock()
        accounts_col.document.return_value = account_doc_ref

        def _collection_router(name: str):
            if name == "agent_configs":
                return global_col
            if name == "accounts":
                return accounts_col
            return MagicMock()

        db.collection.side_effect = _collection_router

        self._install_db(db)

        body = {
            "name": "My Agent",
            "instruction": "You are a helpful assistant for testing.",
            "model": "gemini-2.5-flash",
        }
        resp = client.post(BASE_URL + "/", json=body)
        assert resp.status_code == 201

    def test_account_admin_get_list_is_200(self, client: TestClient) -> None:
        """Org admin (account_admin) can list configs (200)."""
        self._install_user(_account_admin())
        self._install_db()
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200

    def test_account_admin_put_is_200(self, client: TestClient) -> None:
        """Org admin can upsert an overlay (200 with merged config returned)."""
        self._install_user(_account_admin())

        # Wire Firestore for PUT → upsert overlay → _load_merged
        config_id = "company_news_agent"

        global_doc = MagicMock()
        global_doc.exists = True
        global_doc.to_dict.return_value = dict(_VALID_GLOBAL_DOC)

        overlay_doc_after = MagicMock()
        overlay_doc_after.exists = True
        overlay_doc_after.to_dict.return_value = {
            "based_on_version": 3,
            "updated_at": "2026-01-02T00:00:00+00:00",
            "updated_by": "admin@example.com",
        }

        # Global lookup doc ref
        global_doc_ref = MagicMock()
        global_doc_ref.get.return_value = global_doc
        global_col = MagicMock()
        global_col.document.return_value = global_doc_ref

        # Account overlay doc ref — .set() + .get() after overlay write
        overlay_ref = MagicMock()
        overlay_ref.get.return_value = overlay_doc_after
        overlay_ref.set.return_value = None
        agent_cfg_sub = MagicMock()
        agent_cfg_sub.document.return_value = overlay_ref
        account_doc = MagicMock()
        account_doc.collection.return_value = agent_cfg_sub
        accounts_col = MagicMock()
        accounts_col.document.return_value = account_doc

        def _col(name: str):
            if name == "agent_configs":
                return global_col
            if name == "accounts":
                return accounts_col
            return MagicMock()

        db = MagicMock()
        db.collection.side_effect = _col
        self._install_db(db)

        resp = client.put(BASE_URL + f"/{config_id}", json={})
        assert resp.status_code == 200

    def test_account_admin_delete_overlay_is_204(self, client: TestClient) -> None:
        """Org admin can delete a non-custom overlay (reverts to global, returns 204)."""
        self._install_user(_account_admin())

        config_id = "company_news_agent"

        overlay_doc = MagicMock()
        overlay_doc.exists = True
        overlay_ref = MagicMock()
        overlay_ref.get.return_value = overlay_doc
        overlay_ref.delete.return_value = None
        agent_cfg_sub = MagicMock()
        agent_cfg_sub.document.return_value = overlay_ref
        account_doc = MagicMock()
        account_doc.collection.return_value = agent_cfg_sub
        accounts_col = MagicMock()
        accounts_col.document.return_value = account_doc

        db = MagicMock()
        db.collection.return_value = accounts_col
        self._install_db(db)

        resp = client.delete(BASE_URL + f"/{config_id}")
        assert resp.status_code == 204

    def test_account_admin_delete_custom_missing_is_404(self, client: TestClient) -> None:
        """Deleting a nonexistent custom_* config returns 404."""
        self._install_user(_account_admin())

        overlay_doc = MagicMock()
        overlay_doc.exists = False
        overlay_ref = MagicMock()
        overlay_ref.get.return_value = overlay_doc
        agent_cfg_sub = MagicMock()
        agent_cfg_sub.document.return_value = overlay_ref
        account_doc = MagicMock()
        account_doc.collection.return_value = agent_cfg_sub
        accounts_col = MagicMock()
        accounts_col.document.return_value = account_doc

        db = MagicMock()
        db.collection.return_value = accounts_col
        self._install_db(db)

        resp = client.delete(BASE_URL + "/custom_deadbeef")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Category B — Emulator tests (skipped without FIRESTORE_EMULATOR_HOST)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator required. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)
class TestAccountAgentConfigsEmulator:
    """Full CRUD round-trip tests against the Firestore emulator.

    Every test installs a real ``google.cloud.firestore.Client`` pointed at the
    emulator, overrides ``get_firestore`` and ``get_current_user_context`` on
    the FastAPI app, and cleans up all seeded documents after the test.

    Tests map to the implementation-plan acceptance criteria from AH-PRD-02 §7.
    """

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class")
    def emulator_db(self):
        """Real Firestore client pointed at the emulator."""
        from google.cloud import firestore as _fs

        return _fs.Client(project="test-project")

    @pytest.fixture(autouse=True)
    def _install_app_overrides(self, emulator_db):
        """Override FastAPI dependencies for every test in this class."""
        async def _super_admin_user():
            return _super_admin()

        app.dependency_overrides[get_firestore] = lambda: emulator_db
        app.dependency_overrides[get_current_user_context] = _super_admin_user
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=True)

    @pytest.fixture
    def account_id(self) -> str:
        return f"acc_emulator_{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def global_config_id(self) -> str:
        return f"test_agent_{uuid.uuid4().hex[:8]}"

    def _seed_global(
        self,
        db,
        config_id: str,
        extra: dict | None = None,
    ) -> None:
        """Write a global agent_configs/{config_id} doc."""
        data = dict(_VALID_GLOBAL_DOC)
        if extra:
            data.update(extra)
        db.collection("agent_configs").document(config_id).set(data)

    def _seed_overlay(
        self,
        db,
        account_id: str,
        config_id: str,
        overlay_data: dict,
    ) -> None:
        """Write a per-account overlay doc."""
        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
            .set(overlay_data)
        )

    def _cleanup(self, db, account_id: str, config_ids: list[str]) -> None:
        """Remove global and per-account docs created by a test."""
        for cid in config_ids:
            db.collection("agent_configs").document(cid).delete()
            (
                db.collection("accounts")
                .document(account_id)
                .collection("agent_configs")
                .document(cid)
                .delete()
            )

    # ------------------------------------------------------------------
    # AC: GET /{config_id} → 404 for nonexistent config_id
    # ------------------------------------------------------------------

    def test_get_nonexistent_config_returns_404(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """Neither global nor overlay → 404."""
        resp = client.get(
            f"/api/v1/accounts/{account_id}/agent-configs/nonexistent_xyz_abc"
        )
        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # AC: Overlay round-trip — seed global → PUT overlay → GET → DELETE → revert
    # ------------------------------------------------------------------

    def test_overlay_round_trip(
        self, client: TestClient, emulator_db, account_id: str, global_config_id: str
    ) -> None:
        """PUT creates overlay; GET shows customized; DELETE reverts to default."""
        self._seed_global(emulator_db, global_config_id)
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            # Step 1: PUT overlay with a custom instruction
            resp = client.put(
                f"{base_url}/{global_config_id}",
                json={"instruction": "You are a custom overlay researcher agent."},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["customization_status"] == "customized"
            assert body["config_id"] == global_config_id
            assert body["based_on_version"] == 3  # major from "v3.2.1"
            assert body["instruction"] == "You are a custom overlay researcher agent."

            # Step 2: GET returns the merged (customized) view
            resp = client.get(f"{base_url}/{global_config_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["customization_status"] == "customized"

            # Step 3: DELETE reverts overlay (global still exists)
            resp = client.delete(f"{base_url}/{global_config_id}")
            assert resp.status_code == 204

            # Step 4: GET now shows default (global only)
            resp = client.get(f"{base_url}/{global_config_id}")
            assert resp.status_code == 200
            assert resp.json()["customization_status"] == "default"

        finally:
            self._cleanup(emulator_db, account_id, [global_config_id])

    # ------------------------------------------------------------------
    # AC: Custom-agent round-trip — POST → list → DELETE → list (gone)
    # ------------------------------------------------------------------

    def test_custom_agent_round_trip(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """POST creates a custom agent scoped to the account; DELETE removes it entirely."""
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"
        custom_id: str | None = None

        try:
            # Step 1: POST → 201 with custom_{uuid8} config_id
            resp = client.post(
                base_url + "/",
                json={
                    "name": "My Custom Agent",
                    "instruction": "You are a custom agent for emulator testing.",
                    "model": "gemini-2.5-flash",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["customization_status"] == "custom_agent"
            custom_id = body["config_id"]
            assert custom_id.startswith("custom_")

            # Step 2: LIST includes the new custom agent
            resp = client.get(base_url + "/")
            assert resp.status_code == 200
            listed_ids = [c["config_id"] for c in resp.json()]
            assert custom_id in listed_ids

            # Step 3: DELETE removes custom doc entirely
            resp = client.delete(f"{base_url}/{custom_id}")
            assert resp.status_code == 204

            # Step 4: LIST no longer includes it
            resp = client.get(base_url + "/")
            assert resp.status_code == 200
            listed_ids = [c["config_id"] for c in resp.json()]
            assert custom_id not in listed_ids

        finally:
            if custom_id:
                self._cleanup(emulator_db, account_id, [custom_id])

    # ------------------------------------------------------------------
    # AC: GET / filter — automatically_available=False hidden by default;
    #     ?visible_in_frontend=true further restricts
    # ------------------------------------------------------------------

    def test_list_filters_automatically_available_false(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """Global config with automatically_available=False is excluded from list unless overlaid."""
        hidden_id = f"hidden_agent_{uuid.uuid4().hex[:8]}"
        self._seed_global(emulator_db, hidden_id, {"automatically_available": False})

        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.get(base_url + "/")
            assert resp.status_code == 200
            listed_ids = [c["config_id"] for c in resp.json()]
            assert hidden_id not in listed_ids
        finally:
            self._cleanup(emulator_db, account_id, [hidden_id])

    def test_list_visible_in_frontend_filter(
        self, client: TestClient, emulator_db, account_id: str, global_config_id: str
    ) -> None:
        """?visible_in_frontend=true excludes configs with visible_in_frontend=False."""
        visible_id = global_config_id
        hidden_id = f"hidden_frontend_{uuid.uuid4().hex[:8]}"

        self._seed_global(emulator_db, visible_id, {"visible_in_frontend": True})
        self._seed_global(emulator_db, hidden_id, {"visible_in_frontend": False})

        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.get(base_url + "/?visible_in_frontend=true")
            assert resp.status_code == 200
            listed_ids = [c["config_id"] for c in resp.json()]
            assert visible_id in listed_ids
            assert hidden_id not in listed_ids
        finally:
            self._cleanup(emulator_db, account_id, [visible_id, hidden_id])

    # ------------------------------------------------------------------
    # AC: PUT with empty body writes empty overlay; customization_status=customized
    # ------------------------------------------------------------------

    def test_put_empty_body_creates_overlay_with_customized_status(
        self, client: TestClient, emulator_db, account_id: str, global_config_id: str
    ) -> None:
        """PUT {} writes a minimal overlay; result has customization_status=customized."""
        self._seed_global(emulator_db, global_config_id)
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.put(f"{base_url}/{global_config_id}", json={})
            assert resp.status_code == 200
            body = resp.json()
            assert body["customization_status"] == "customized"
            assert body["based_on_version"] is not None
        finally:
            self._cleanup(emulator_db, account_id, [global_config_id])

    # ------------------------------------------------------------------
    # AC: PUT records based_on_version from global metadata.version
    # ------------------------------------------------------------------

    def test_put_records_based_on_version_from_global_metadata(
        self, client: TestClient, emulator_db, account_id: str, global_config_id: str
    ) -> None:
        """based_on_version must be the major component of the global version ("v3.2.1" → 3)."""
        # Seed with a specific version to make it deterministic
        self._seed_global(emulator_db, global_config_id)  # version = "v3.2.1"
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.put(f"{base_url}/{global_config_id}", json={})
            assert resp.status_code == 200
            assert resp.json()["based_on_version"] == 3
        finally:
            self._cleanup(emulator_db, account_id, [global_config_id])

    def test_put_based_on_version_major_only_from_semver(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """based_on_version extracts only the major component from various semver strings."""
        config_id = f"versioned_agent_{uuid.uuid4().hex[:8]}"
        doc = dict(_VALID_GLOBAL_DOC)
        doc["metadata"] = dict(doc["metadata"])
        doc["metadata"]["version"] = "v12.4.0"
        emulator_db.collection("agent_configs").document(config_id).set(doc)
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.put(f"{base_url}/{config_id}", json={})
            assert resp.status_code == 200
            assert resp.json()["based_on_version"] == 12
        finally:
            self._cleanup(emulator_db, account_id, [config_id])

    # ------------------------------------------------------------------
    # AC: DELETE custom_* deletes the custom doc entirely (not just overlay)
    # ------------------------------------------------------------------

    def test_delete_custom_removes_doc(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """Deleting a custom_* config removes the doc, not just reverts to global."""
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        # Create via POST
        resp = client.post(
            base_url + "/",
            json={
                "name": "Ephemeral Agent",
                "instruction": "You are a temporary custom agent for deletion testing.",
                "model": "gemini-2.5-flash",
            },
        )
        assert resp.status_code == 201
        custom_id = resp.json()["config_id"]
        assert custom_id.startswith("custom_")

        try:
            # Delete it
            resp = client.delete(f"{base_url}/{custom_id}")
            assert resp.status_code == 204

            # Subsequent GET must 404 (no global fallback for a custom_ id)
            resp = client.get(f"{base_url}/{custom_id}")
            assert resp.status_code == 404
        finally:
            self._cleanup(emulator_db, account_id, [custom_id])

    # ------------------------------------------------------------------
    # AC: PUT overlay over nonexistent global still writes overlay (custom_agent path)
    # ------------------------------------------------------------------

    def test_put_overlay_without_global_creates_standalone_overlay(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """PUT on a config_id with no global doc stores the overlay;
        _load_merged returns it as custom_agent status."""
        config_id = f"orphan_overlay_{uuid.uuid4().hex[:8]}"
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.put(
                f"{base_url}/{config_id}",
                json={"instruction": "Orphan overlay instruction for testing purposes."},
            )
            assert resp.status_code == 200
            body = resp.json()
            # No global → customization_status is custom_agent
            assert body["customization_status"] == "custom_agent"
            assert body["config_id"] == config_id
        finally:
            self._cleanup(emulator_db, account_id, [config_id])

    # ------------------------------------------------------------------
    # AC: LIST includes both globals and per-account overlays/customs
    # ------------------------------------------------------------------

    def test_list_includes_global_and_account_docs(
        self, client: TestClient, emulator_db, account_id: str, global_config_id: str
    ) -> None:
        """List returns global auto-available configs merged with account configs."""
        custom_id = f"custom_{uuid.uuid4().hex[:8]}"
        self._seed_global(emulator_db, global_config_id)
        self._seed_overlay(
            emulator_db,
            account_id,
            custom_id,
            {
                "name": "Custom Only",
                "instruction": "Custom instruction for listing test.",
                "model": "gemini-2.5-flash",
                "customization_status": "custom_agent",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "created_by": "ops@ken-e.ai",
            },
        )
        base_url = f"/api/v1/accounts/{account_id}/agent-configs"

        try:
            resp = client.get(base_url + "/")
            assert resp.status_code == 200
            listed_ids = [c["config_id"] for c in resp.json()]
            assert global_config_id in listed_ids
            assert custom_id in listed_ids
        finally:
            self._cleanup(emulator_db, account_id, [global_config_id, custom_id])
