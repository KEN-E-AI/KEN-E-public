"""Integration tests: strategy router Shape B path parity (DM-70).

Locks the five ``/api/v1/strategy/{account_id}/...`` endpoints in
``routers/strategy.py`` to the Shape B Firestore paths.  Any regression that
reverts a path literal back to Shape A (``strategy_docs_{account_id}/``) or
introduces a path typo will cause the matching test to fail on every CI run
without requiring a live Firestore project.

Also ships one cross-write-read parity test asserting that
``log_strategy_action``'s write path and ``get_strategy_audit_log``'s read
path agree — nothing previously enforced this invariant.

Two test classes:
- ``TestStrategyRouterShapeParity``      — six endpoint path-assertion tests
- ``TestStrategyAuditWriteReadParity``   — one write/read parity test

Architecture note:
  ``routers/strategy.py:33`` declares ``db = firestore.Client()`` at module
  level rather than via FastAPI dependency injection.  The tests swap it out
  with ``monkeypatch.setattr`` (the same pattern DM-16 uses for
  ``audit_service.db``), which patches the symbol after module import.
  ``app.dependency_overrides[get_current_user]`` is used for auth; cleaned up
  in every test via ``try/finally`` to avoid cross-test contamination.
"""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import get_current_user
from src.kene_api.auth.models import UserContext
from src.kene_api.main import app
from src.kene_api.services import audit_service

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_ACCOUNT_ID = "acc_test"
_DOC_TYPE = "business_strategy"

# Minimal dict accepted by StrategyDocument Pydantic model.
_STUB_STRATEGY_DOC: dict[str, Any] = {
    "doc_type": _DOC_TYPE,
    "content": {"summary": "test content for shape parity"},
    "version": 2,
    "created_at": datetime(2026, 1, 1).isoformat(),
    "created_by": "u_test",
    "updated_at": datetime(2026, 1, 1).isoformat(),
    "updated_by": "u_test",
    "account_id": _ACCOUNT_ID,
    "is_active": True,
}


# ---------------------------------------------------------------------------
# Test class — router endpoint path assertions
# ---------------------------------------------------------------------------


class TestStrategyRouterShapeParity:
    """Verify each strategy-router endpoint uses the Shape B Firestore path."""

    @pytest.fixture(autouse=True)
    def patch_owning_org_resolver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the Neo4j resolver so tests don't require a live database.

        Returns a fixed org_id that matches mock_user's account_permissions.
        """
        from unittest.mock import AsyncMock

        monkeypatch.setattr(
            "src.kene_api.auth.account_org.resolve_owning_organization_id",
            AsyncMock(return_value="org_test"),
        )

    @pytest.fixture
    def mock_user(self) -> UserContext:
        return UserContext(
            user_id="u_test",
            email="tester@example.com",
            organization_permissions={},
            account_permissions={_ACCOUNT_ID: "edit"},
        )

    @pytest.fixture
    def super_admin_user(self) -> UserContext:
        return UserContext(
            user_id="u_admin",
            email="ops@ken-e.ai",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    # ------------------------------------------------------------------
    # Test 1: list_strategy_documents
    # ------------------------------------------------------------------

    def test_list_strategy_documents_uses_shape_b_collection_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """GET /{account_id}/documents queries accounts/{account_id}/strategy_docs."""
        mock_db = MagicMock()
        # stream() returns empty list so the for-loop iterates zero times.
        mock_db.collection.return_value.where.return_value.stream.return_value = []

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_db.collection.assert_any_call(f"accounts/{_ACCOUNT_ID}/strategy_docs")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # ------------------------------------------------------------------
    # Test 2: get_strategy_document (current version)
    # ------------------------------------------------------------------

    def test_get_strategy_document_uses_shape_b_document_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """GET /{account_id}/documents/{doc_type} reads accounts/{account_id}/strategy_docs/{doc_type}."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = dict(_STUB_STRATEGY_DOC)
        mock_doc.id = _DOC_TYPE
        mock_db.document.return_value.get.return_value = mock_doc

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents/{_DOC_TYPE}",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_db.document.assert_any_call(
                f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # ------------------------------------------------------------------
    # Test 3: get_strategy_document (specific version)
    # ------------------------------------------------------------------

    def test_get_strategy_document_versioned_uses_shape_b_versions_subpath(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """GET with ?version=3 reads accounts/{account_id}/strategy_docs/{doc_type}/versions/3."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        versioned_stub = dict(_STUB_STRATEGY_DOC)
        versioned_stub["version"] = 3
        mock_doc.to_dict.return_value = versioned_stub
        mock_doc.id = _DOC_TYPE
        mock_db.document.return_value.get.return_value = mock_doc

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents/{_DOC_TYPE}?version=3",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_db.document.assert_any_call(
                f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}/versions/3"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # ------------------------------------------------------------------
    # Test 4: create_or_update_strategy_document (new doc branch)
    # ------------------------------------------------------------------

    def test_create_strategy_document_writes_to_shape_b_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """POST with a new doc writes to accounts/{account_id}/strategy_docs/{doc_type}."""
        mock_db = MagicMock()
        mock_existing = MagicMock()
        mock_existing.exists = False
        mock_db.document.return_value.get.return_value = mock_existing

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.post(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents/{_DOC_TYPE}",
                headers={"Authorization": "Bearer test_token"},
                json={
                    "doc_type": _DOC_TYPE,
                    "content": {"summary": "new document"},
                },
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_db.document.assert_any_call(
                f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}"
            )
            # .set() was called to persist the new document.
            mock_db.document.return_value.set.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # ------------------------------------------------------------------
    # Test 5: create_or_update_strategy_document (update branch)
    # ------------------------------------------------------------------

    def test_update_strategy_document_archives_to_shape_b_versions_subpath(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """POST on an existing doc writes both the current doc and the versions/{n} archive."""
        mock_db = MagicMock()
        mock_existing = MagicMock()
        mock_existing.exists = True
        mock_existing.to_dict.return_value = dict(_STUB_STRATEGY_DOC)
        mock_db.document.return_value.get.return_value = mock_existing

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.post(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents/{_DOC_TYPE}",
                headers={"Authorization": "Bearer test_token"},
                json={
                    "doc_type": _DOC_TYPE,
                    "content": {"summary": "updated document"},
                },
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            # Both the live doc path and the archive version path must appear.
            live_path = f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}"
            archive_path = (
                f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}"
                f"/versions/{_STUB_STRATEGY_DOC['version']}"
            )
            mock_db.document.assert_any_call(live_path)
            mock_db.document.assert_any_call(archive_path)

            # Two document() calls occurred (current + archive); audit path goes through
            # audit_service.db which is patched separately, so this count is stable.
            assert mock_db.document.call_count == 2, (
                f"Expected exactly 2 db.document() calls, got {mock_db.document.call_count}"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    # ------------------------------------------------------------------
    # Test 6: delete_strategy_document
    # ------------------------------------------------------------------

    def test_delete_strategy_document_targets_shape_b_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        super_admin_user: UserContext,
    ) -> None:
        """DELETE /{account_id}/documents/{doc_type} reads/soft-deletes at Shape B path."""
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = dict(_STUB_STRATEGY_DOC)
        mock_db.document.return_value.get.return_value = mock_doc

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_db)
        monkeypatch.setattr(audit_service, "db", MagicMock())
        app.dependency_overrides[get_current_user] = lambda: super_admin_user

        try:
            response = client.delete(
                f"/api/v1/strategy/{_ACCOUNT_ID}/documents/{_DOC_TYPE}",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_db.document.assert_any_call(
                f"accounts/{_ACCOUNT_ID}/strategy_docs/{_DOC_TYPE}"
            )

            # Soft-delete: .update() is called with is_active=False.
            update_kwargs = mock_db.document.return_value.update.call_args.args[0]
            assert update_kwargs.get("is_active") is False, (
                "Soft-delete did not set is_active=False"
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Test class — write/read path parity
# ---------------------------------------------------------------------------


class TestStrategyAuditWriteReadParity:
    """Assert log_strategy_action write path == get_strategy_audit_log read path."""

    @pytest.fixture(autouse=True)
    def patch_owning_org_resolver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stub the Neo4j resolver so tests don't require a live database."""
        from unittest.mock import AsyncMock

        monkeypatch.setattr(
            "src.kene_api.auth.account_org.resolve_owning_organization_id",
            AsyncMock(return_value="org_test"),
        )

    @pytest.fixture
    def mock_user(self) -> UserContext:
        return UserContext(
            user_id="u_test",
            email="tester@example.com",
            organization_permissions={},
            account_permissions={_ACCOUNT_ID: "edit"},
        )

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    async def test_audit_log_collection_matches_log_strategy_action_write_prefix(
        self,
        monkeypatch: pytest.MonkeyPatch,
        client: TestClient,
        mock_user: UserContext,
    ) -> None:
        """The collection queried by GET /history/{doc_type} must match the write path used
        by log_strategy_action — no test previously enforced this invariant.

        Approach:
          1. Patch audit_service.db → mock_audit_db; call log_strategy_action directly.
          2. Capture the document path written; derive the collection prefix.
          3. Patch routers.strategy.db → mock_router_db; call the GET history endpoint.
          4. Capture the collection queried; assert both collection prefixes match.
        """
        # ---- Step 1: capture the write path via log_strategy_action ----
        mock_audit_db = MagicMock()
        monkeypatch.setattr(audit_service, "db", mock_audit_db)

        await audit_service.log_strategy_action(
            account_id=_ACCOUNT_ID,
            doc_type=_DOC_TYPE,
            action="created",
            user=mock_user,
        )

        write_doc_path: str = mock_audit_db.document.call_args.args[0]
        # Collection prefix = everything up to (but not including) the last segment.
        write_collection_prefix = "/".join(write_doc_path.split("/")[:-1])

        # ---- Step 2: capture the read path via GET /history/{doc_type} ----
        mock_router_db = MagicMock()
        # stream() → empty iterator so the for-loop skips safely.
        mock_router_db.collection.return_value.where.return_value.where.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value = []

        monkeypatch.setattr("src.kene_api.routers.strategy.db", mock_router_db)
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            response = client.get(
                f"/api/v1/strategy/{_ACCOUNT_ID}/history/{_DOC_TYPE}",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            read_collection_path: str = mock_router_db.collection.call_args.args[0]

            assert read_collection_path == write_collection_prefix, (
                f"Write path prefix {write_collection_prefix!r} does not match "
                f"read collection path {read_collection_path!r}. "
                "log_strategy_action and get_strategy_audit_log are out of sync."
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
