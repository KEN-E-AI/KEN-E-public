"""Integration tests for _load_merged helper and account-deletion recursive sweep.

Two test classes (both emulator-only) + one always-runs schema parity test:

* ``TestOverlayMerge`` — unit tests of ``_load_merged`` covering the four
  logical branches (global-only, overlay-only, both-present, neither-present)
  plus field-stripping and overlay-wins semantics.
* ``TestAccountDeletionSweep`` — end-to-end test of the recursive_delete
  sweep in ``DELETE /api/v1/accounts/{account_id}``; verifies per-account
  Firestore subcollections (including agent_configs) are removed and global
  collections at the root level are untouched.
* ``test_merged_agent_config_api_model_field_parity`` — schema parity guard
  (runs always, no emulator needed).

Enable emulator tests:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_agent_config_overlay.py -v

Acceptance criteria covered:
  DM-PRD-05 (account-deletion recursive_delete sweep)
  AH-PRD-02 §6 / AC-11 merge semantics (_load_merged helper)
"""

from __future__ import annotations

import os
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.services.storage_service import get_storage_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMULATOR_REASON = (
    "Firestore emulator integration tests skipped by default. "
    "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
    "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
)

_VALID_GLOBAL_DOC: dict[str, Any] = {
    "name": None,
    "title": "Test Researcher",
    "instruction": "You are a test researcher assistant.",
    "model": "gemini-2.5-flash",
    "description": "A test agent for overlay integration tests.",
    "automatically_available": True,
    "visible_in_frontend": True,
    "metadata": {
        "version": "v2.0.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "updated_by": "seed@test.com",
        "notes": "",
    },
}


def _emulator_client() -> Any:
    """Build a real Firestore client pointed at the emulator."""
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _super_admin_user() -> UserContext:
    return UserContext(
        user_id="super-uid",
        email="ops@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


# ---------------------------------------------------------------------------
# Always-runs schema parity test (no emulator dependency)
# ---------------------------------------------------------------------------


def test_merged_agent_config_api_model_field_parity() -> None:
    """MergedAgentConfig API model must expose all fields from the factory's model."""
    from src.kene_api.models.agent_config_models import MergedAgentConfig as ApiModel

    required_fields = {
        "instruction",
        "model",
        "name",
        "title",
        "description",
        "temperature",
        "max_output_tokens",
        "code_execution_enabled",
        "mcp_servers",
        "skill_ids",
        "sandbox_code_executor_enabled",
        "available_to_copy",
        "automatically_available",
        "visible_in_frontend",
        "customization_status",
        "based_on_version",
        "config_id",
    }
    api_fields = set(ApiModel.model_fields.keys())
    missing = required_fields - api_fields
    assert not missing, f"MergedAgentConfig is missing fields: {missing}"


# ---------------------------------------------------------------------------
# TestOverlayMerge — direct _load_merged unit tests (emulator required)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=_EMULATOR_REASON,
)
class TestOverlayMerge:
    """Direct unit tests of ``_load_merged`` against the Firestore emulator.

    Each test seeds minimal documents, calls the helper directly, and tears
    down all seeded docs in a ``finally`` block to prevent cross-test pollution.
    """

    @pytest.fixture(scope="class")
    def db(self):
        """Firestore client pointed at the emulator, shared for the class."""
        return _emulator_client()

    def _seed_global(self, db, config_id: str, data: dict) -> None:
        db.collection("agent_configs").document(config_id).set(data)

    def _seed_overlay(self, db, account_id: str, config_id: str, data: dict) -> None:
        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
            .set(data)
        )

    def _delete_global(self, db, config_id: str) -> None:
        db.collection("agent_configs").document(config_id).delete()

    def _delete_overlay(self, db, account_id: str, config_id: str) -> None:
        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
            .delete()
        )

    # ------------------------------------------------------------------
    # Branch 1: global-only
    # ------------------------------------------------------------------

    def test_global_only_returns_default_status(self, db) -> None:
        """Global doc present, no overlay → customization_status='default', based_on_version=None."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        self._seed_global(db, config_id, dict(_VALID_GLOBAL_DOC))

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.customization_status == "default"
            assert result.based_on_version is None
            assert result.config_id == config_id
        finally:
            self._delete_global(db, config_id)

    # ------------------------------------------------------------------
    # Branch 2: overlay-only (no global)
    # ------------------------------------------------------------------

    def test_overlay_only_returns_custom_agent_status(self, db) -> None:
        """Overlay present, no global → customization_status='custom_agent', based_on_version from overlay."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        self._seed_overlay(
            db,
            account_id,
            config_id,
            {
                "title": "Custom Only",
                "instruction": "You are a custom-only overlay agent for testing.",
                "model": "gemini-2.5-flash",
                "based_on_version": "v4.1.0",
            },
        )

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.customization_status == "custom_agent"
            # major of "v4.1.0" is 4
            assert result.based_on_version == 4
            assert result.config_id == config_id
        finally:
            self._delete_overlay(db, account_id, config_id)

    # ------------------------------------------------------------------
    # Branch 3: both present → customized, overlay fields win
    # ------------------------------------------------------------------

    def test_both_present_returns_customized_status(self, db) -> None:
        """Both global and overlay → customization_status='customized'."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        self._seed_global(db, config_id, dict(_VALID_GLOBAL_DOC))
        self._seed_overlay(
            db,
            account_id,
            config_id,
            {
                "instruction": "You are the overlaid instruction for testing purposes.",
                "based_on_version": "v2.0.0",
            },
        )

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.customization_status == "customized"
            assert result.based_on_version == 2  # major of "v2.0.0"
        finally:
            self._delete_global(db, config_id)
            self._delete_overlay(db, account_id, config_id)

    def test_both_present_overlay_instruction_wins(self, db) -> None:
        """When both docs present, overlay's instruction overrides global's."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        self._seed_global(db, config_id, dict(_VALID_GLOBAL_DOC))
        overlay_instruction = (
            "You are the OVERLAY instruction that should win in tests."
        )
        self._seed_overlay(
            db,
            account_id,
            config_id,
            {
                "instruction": overlay_instruction,
                "based_on_version": "v1.0.0",
            },
        )

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.instruction == overlay_instruction
        finally:
            self._delete_global(db, config_id)
            self._delete_overlay(db, account_id, config_id)

    def test_both_present_overlay_model_wins(self, db) -> None:
        """Overlay ``model`` field overrides the global ``model`` field."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        global_doc = dict(_VALID_GLOBAL_DOC)
        global_doc["model"] = "gemini-2.5-flash"
        self._seed_global(db, config_id, global_doc)
        self._seed_overlay(
            db,
            account_id,
            config_id,
            {
                "model": "gemini-2.5-pro",
                "based_on_version": "v2.0.0",
            },
        )

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.model == "gemini-2.5-pro"
        finally:
            self._delete_global(db, config_id)
            self._delete_overlay(db, account_id, config_id)

    # ------------------------------------------------------------------
    # Branch 4: neither present → returns None
    # ------------------------------------------------------------------

    def test_neither_present_returns_none(self, db) -> None:
        """No global, no overlay → _load_merged returns None."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"

        # Nothing seeded; both lookups return "not found"
        result = _load_merged(db, account_id, config_id)
        assert result is None

    # ------------------------------------------------------------------
    # Field stripping: customization_status / based_on_version not leaked
    # from Firestore data into the model discriminator logic
    # ------------------------------------------------------------------

    def test_customization_status_from_firestore_is_stripped(self, db) -> None:
        """A Firestore-stored customization_status field must NOT override the merge logic."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"

        # Deliberately plant a wrong customization_status in the global doc.
        global_doc = dict(_VALID_GLOBAL_DOC)
        global_doc["customization_status"] = "customized"  # wrong — no overlay present

        self._seed_global(db, config_id, global_doc)

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            # Merge logic says global-only → "default", not the stored "customized"
            assert result.customization_status == "default"
        finally:
            self._delete_global(db, config_id)

    def test_based_on_version_from_firestore_is_stripped_for_global_only(
        self, db
    ) -> None:
        """A based_on_version stored in a global-only doc must not bleed into the result."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"

        global_doc = dict(_VALID_GLOBAL_DOC)
        global_doc["based_on_version"] = "v5.0.0"  # irrelevant for global-only

        self._seed_global(db, config_id, global_doc)

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            # global-only → based_on_version must be None per merge semantics
            assert result.based_on_version is None
        finally:
            self._delete_global(db, config_id)

    # ------------------------------------------------------------------
    # based_on_version is parsed from overlay, not global
    # ------------------------------------------------------------------

    def test_based_on_version_parsed_from_overlay_doc(self, db) -> None:
        """based_on_version in the merged result is derived from the overlay's field."""
        from src.kene_api.routers.agent_configs import _load_merged

        account_id = f"acc_{uuid.uuid4().hex[:8]}"
        config_id = f"cfg_{uuid.uuid4().hex[:8]}"
        self._seed_global(db, config_id, dict(_VALID_GLOBAL_DOC))
        self._seed_overlay(
            db,
            account_id,
            config_id,
            {
                "instruction": "Overlay instruction for based_on_version test purposes.",
                "based_on_version": "v7.3.1",
            },
        )

        try:
            result = _load_merged(db, account_id, config_id)
            assert result is not None
            assert result.based_on_version == 7  # major of "v7.3.1"
        finally:
            self._delete_global(db, config_id)
            self._delete_overlay(db, account_id, config_id)


# ---------------------------------------------------------------------------
# TestAccountDeletionSweep — recursive_delete covers all Shape B subcollections
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=_EMULATOR_REASON,
)
class TestAccountDeletionSweep:
    """End-to-end tests for account-scoped Firestore cleanup on DELETE /api/v1/accounts/{id}.

    Verifies that ``firestore_db.recursive_delete(accounts/{account_id})`` removes all
    Shape B subcollections (including agent_configs) and that global collections at the
    root level (agent_configs/{config_id}) are untouched.

    Neo4j and GCS are mocked; Firestore is the real emulator client.
    """

    @pytest.fixture(scope="class")
    def emulator_db(self):
        """Real Firestore client pointed at the emulator, shared for the class."""
        return _emulator_client()

    @pytest.fixture(autouse=True)
    def _install_app_overrides(self, emulator_db):
        """Wire emulator Firestore + mocked Neo4j + mocked GCS into the app."""

        # --- Mock Neo4j ---
        # The endpoint calls: health_check(), execute_query() (account lookup),
        # execute_write_operation() (three times for cascade delete).
        mock_neo4j = MagicMock()
        mock_neo4j.health_check = AsyncMock(return_value=True)
        # Account lookup — return one row so the endpoint does not 404.
        mock_neo4j.execute_query = AsyncMock(return_value=[{"data_region": "US"}])
        # Cascade deletes — return empty summaries (nothing deleted in Neo4j).
        mock_neo4j.execute_write_operation = AsyncMock(
            return_value={"nodes_deleted": 0, "relationships_deleted": 0}
        )

        async def _get_neo4j():
            return mock_neo4j

        # --- Mock GCS ---
        mock_storage = MagicMock()
        mock_storage.delete_account_documents = AsyncMock(return_value=True)

        # --- Wire FirestoreService to use the emulator client ---
        # The delete_account endpoint calls firestore.get_client() on the
        # FirestoreService instance injected via Depends(get_firestore_service).
        mock_fs_service = MagicMock()
        mock_fs_service.get_client.return_value = emulator_db

        app.dependency_overrides[get_neo4j_service] = _get_neo4j
        app.dependency_overrides[get_storage_service] = lambda: mock_storage
        app.dependency_overrides[get_firestore_service] = lambda: mock_fs_service

        # Also override auth so no 401.
        async def _super_admin():
            return _super_admin_user()

        app.dependency_overrides[get_current_user_context] = _super_admin

        yield {
            "neo4j": mock_neo4j,
            "storage": mock_storage,
            "fs_service": mock_fs_service,
        }

        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=True)

    @pytest.fixture
    def account_id(self) -> str:
        return f"acc_sweep_{uuid.uuid4().hex[:8]}"

    def _seed_account_agent_config(
        self, db, account_id: str, config_id: str, data: dict | None = None
    ) -> None:
        """Seed a doc at accounts/{account_id}/agent_configs/{config_id}."""
        (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .document(config_id)
            .set(
                data
                or {
                    "instruction": f"Instruction for {config_id}.",
                    "model": "gemini-2.5-flash",
                }
            )
        )

    def _seed_global_agent_config(
        self, db, config_id: str, data: dict | None = None
    ) -> None:
        """Seed a global doc at agent_configs/{config_id}."""
        db.collection("agent_configs").document(config_id).set(
            data or dict(_VALID_GLOBAL_DOC)
        )

    def _cleanup(self, db, account_id: str, global_config_ids: list[str]) -> None:
        """Remove any documents left behind (best-effort)."""
        for cid in global_config_ids:
            db.collection("agent_configs").document(cid).delete()
        # Clean remaining account docs
        for doc_ref in (
            db.collection("accounts")
            .document(account_id)
            .collection("agent_configs")
            .list_documents()
        ):
            doc_ref.delete()
        db.collection("accounts").document(account_id).delete()

    # ------------------------------------------------------------------
    # recursive_delete covers all Shape B subcollections
    # ------------------------------------------------------------------

    def test_recursive_delete_removes_per_account_agent_config_docs(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """DELETE /api/v1/accounts/{id} removes all per-account agent_config docs via recursive_delete."""
        global_config_id = f"global_unrelated_{uuid.uuid4().hex[:8]}"

        # Seed: 2 overlays + 1 custom under accounts/{account_id}/agent_configs
        overlay_a = f"overlay_a_{uuid.uuid4().hex[:8]}"
        overlay_b = f"overlay_b_{uuid.uuid4().hex[:8]}"
        custom_doc = f"custom_{uuid.uuid4().hex[:8]}"

        self._seed_account_agent_config(emulator_db, account_id, overlay_a)
        self._seed_account_agent_config(emulator_db, account_id, overlay_b)
        self._seed_account_agent_config(emulator_db, account_id, custom_doc)

        # Seed: one global doc at agent_configs/{id} (must NOT be touched)
        self._seed_global_agent_config(emulator_db, global_config_id)

        try:
            resp = client.delete(f"/api/v1/accounts/{account_id}")
            assert resp.status_code == 200

            data = resp.json()["data"]

            # Response must confirm Firestore account was deleted
            assert data["firestore_account_deleted"] is True

            # Verify per-account subcollection is now empty in the emulator
            remaining_docs = list(
                emulator_db.collection("accounts")
                .document(account_id)
                .collection("agent_configs")
                .list_documents()
            )
            assert remaining_docs == [], (
                f"Expected empty agent_configs subcollection, "
                f"found: {[d.id for d in remaining_docs]}"
            )

            # Verify global doc is untouched
            global_doc = (
                emulator_db.collection("agent_configs").document(global_config_id).get()
            )
            assert global_doc.exists, (
                f"Global doc agent_configs/{global_config_id} was incorrectly deleted "
                f"by recursive_delete."
            )

        finally:
            self._cleanup(emulator_db, account_id, [global_config_id])

    def test_recursive_delete_with_no_account_data_reports_success(
        self, client: TestClient, emulator_db, account_id: str
    ) -> None:
        """If no per-account Firestore data exists, recursive_delete still reports success."""
        try:
            resp = client.delete(f"/api/v1/accounts/{account_id}")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["firestore_account_deleted"] is True
        finally:
            self._cleanup(emulator_db, account_id, [])

    # ------------------------------------------------------------------
    # Authorization + graceful-degradation guards
    # ------------------------------------------------------------------

    def test_delete_account_rejects_non_super_admin(
        self, client: TestClient, account_id: str
    ) -> None:
        """A non-super-admin caller is rejected with 403 before any deletion runs."""
        non_admin = UserContext(
            user_id="intruder-uid",
            email="intruder@external.com",
            organization_permissions={},
            account_permissions={},
        )
        app.dependency_overrides[get_current_user_context] = lambda: non_admin

        resp = client.delete(f"/api/v1/accounts/{account_id}")

        assert resp.status_code == 403

    def test_recursive_delete_failure_accumulates_in_cleanup_errors(
        self,
        client: TestClient,
        emulator_db,
        account_id: str,
        _install_app_overrides: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A recursive_delete failure degrades gracefully instead of failing the request.

        The endpoint catches the Firestore error, records it under cleanup_errors,
        leaves firestore_account_deleted False, and still runs the Neo4j cascade.
        """

        def _boom(*_args, **_kwargs):
            raise RuntimeError("emulator recursive_delete exploded")

        monkeypatch.setattr(emulator_db, "recursive_delete", _boom)

        resp = client.delete(f"/api/v1/accounts/{account_id}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["firestore_account_deleted"] is False
        assert any(
            "Firestore recursive delete failed" in e for e in data["cleanup_errors"]
        ), data["cleanup_errors"]
        # Neo4j cascade still runs despite the Firestore failure (3 write ops).
        assert _install_app_overrides["neo4j"].execute_write_operation.await_count == 3
