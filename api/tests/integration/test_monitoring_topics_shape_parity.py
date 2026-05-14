"""Integration tests for monitoring endpoint Shape B path parity (DM-26 / DM-PRD-04 §6 AC-3).

These tests lock the `/api/v1/monitoring-topics/{account_id}` contract to the Shape B
Firestore path `accounts/{account_id}/monitoring_topics/default`. Any regression that reverts
the router to the legacy Shape A pattern (`monitoring_topics/{account_id}`) is caught here on
every CI run — without requiring an emulator or a live Firestore project.

Classes:
- TestMonitoringTopicsShapeParity — GET endpoint path contract (added by DM-26)
- TestMonitoringTopicsWriteShapeParity — PUT/POST/DELETE write-endpoint path contract (DM-68)

Pre-migration fixture capture step (referenced in DM-28 PR description):
    The fixture below represents the canonical MonitoringTopics document shape. The actual
    content values (specific keyword strings, org_id, etc.) were modelled on a realistic
    dev-environment account. DM-28 records the exact JSON captured from dev before the
    Shape A → Shape B migration ran, and that JSON is the authoritative content-level
    lockdown. This test file is the *shape* lockdown (fields, types, doc-id pattern).
"""

from typing import Any
from unittest.mock import ANY, MagicMock, call

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app

# ---------------------------------------------------------------------------
# Pre-migration fixture — shape lockdown for MonitoringTopics
# ---------------------------------------------------------------------------
# This dict mirrors the fields declared on MonitoringTopics (monitoring_models.py:146-173).
# Transient timestamp fields (created_at, updated_at) are present so that Pydantic can
# construct a valid MonitoringTopics from this dict; they are excluded from the parity
# assertion because their values legitimately differ across calls.
_ACCOUNT_ID = "acc_test"
_PRE_MIGRATION_FIXTURE: dict[str, Any] = {
    "account_id": _ACCOUNT_ID,
    "organization_id": "org_test_001",
    "industry_keywords": [
        "professional services",
        "b2b",
        "enterprise software",
        "consulting",
    ],
    "company_keywords": ["kene", "marketing analytics", "ai-driven insights"],
    "customer_keywords": ["cmo", "marketing director", "growth hacker"],
    "customer_concepts": [],
    "competitor_entries": [
        {
            "node_id": "comp_node_abc123",
            "name": None,
            "website": "https://competitor.test",
            "keywords": ["competitor brand", "rival product"],
        }
    ],
    "customer_profile_entries": [
        {
            "node_id": "cp_node_def456",
            "name": None,
            "keywords": ["enterprise buyer", "cfo persona"],
        }
    ],
    "created_at": "2026-01-15T10:00:00.000000",
    "updated_at": "2026-03-20T14:30:00.000000",
}

# Fields excluded from the parity comparison — they are transient / server-generated.
_TRANSIENT_FIELDS = {"created_at", "updated_at"}


def _without_transient(d: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *d* without transient timestamp fields."""
    return {k: v for k, v in d.items() if k not in _TRANSIENT_FIELDS}


class TestMonitoringTopicsShapeParity:
    """Verify GET /api/v1/monitoring-topics/{account_id} uses Shape B Firestore paths."""

    @pytest.fixture
    def mock_user(self) -> UserContext:
        return UserContext(
            user_id="user_test_001",
            email="tester@client-example.com",
            organization_permissions={},
            account_permissions={_ACCOUNT_ID: "edit"},
        )

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_get_returns_fixture_payload_from_shape_b_path(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """Parity test: endpoint reads from the Shape B path and returns the fixture payload.

        Asserts:
        - Response is HTTP 200.
        - Every non-transient field in response data matches the pre-migration fixture.
        - Firestore was queried exactly once with the Shape B collection + document_id.
        """
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = _PRE_MIGRATION_FIXTURE

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            body = response.json()
            assert body["success"] is True
            data = body["data"]
            assert data is not None, (
                "Response data should not be None when the doc exists"
            )

            # Field-by-field parity (excluding transient timestamps)
            expected = _without_transient(_PRE_MIGRATION_FIXTURE)
            actual = _without_transient(data)
            assert actual == expected, (
                f"Response payload does not match pre-migration fixture.\n"
                f"Expected: {expected}\n"
                f"Actual:   {actual}"
            )

            # Shape B call assertion — exactly one read at the correct path
            mock_firestore.get_document.assert_called_once_with(
                collection=f"accounts/{_ACCOUNT_ID}/monitoring_topics",
                document_id="default",
            )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)

    def test_shape_a_access_pattern_does_not_satisfy_endpoint(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """Regression guard: no Shape A call is ever issued when the router runs.

        Asserts:
        - `get_document` is NEVER called with the legacy Shape A signature
          (collection="monitoring_topics", document_id=_ACCOUNT_ID).
        - When the Shape B document is absent (mock returns None), the endpoint does
          NOT silently fall back to a Shape A read — it falls through to the Neo4j
          creation path (which fails in a test environment, producing a non-200 response
          or `data=None`, both acceptable outcomes of the Shape B miss).

        The load-bearing assertion is the `forbidden_calls` check below: if
        `_monitoring_topics_subcollection()` is reverted to return "monitoring_topics"
        (or a partial revert leaves `document_id="default"` on the legacy collection
        name), `get_document` is called with a Shape A signature and this test fails.
        The "non-200-or-data-None when Shape B misses" check is a weaker sanity floor
        (it would also pass if the endpoint 500'd for an unrelated reason) — it confirms
        there's no Shape A *fallback* serving the response, but the forbidden-calls
        assertion is what actually catches the path regression.
        """
        mock_firestore = MagicMock()
        # Return None for every call — simulates a Shape B miss (doc not yet migrated
        # or route reverted to legacy collection name and missing under new path).
        mock_firestore.get_document.return_value = None

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}",
                headers={"Authorization": "Bearer test_token"},
            )

            # When Shape B returns None, the router falls through to Neo4j (unavailable
            # in CI), resulting in a 500 error or a 200 with data=None.
            # Both outcomes are acceptable here — the point is no Shape A call fired.
            body = response.json()
            shape_b_miss = response.status_code != 200 or body.get("data") is None
            assert shape_b_miss, (
                "Expected the endpoint to fail or return data=None when the Shape B "
                "document is absent, but it returned HTTP 200 with non-None data. "
                "This suggests a Shape A fallback read is serving the response."
            )

            # The critical invariant: Shape A calls must NEVER appear.
            # Guard against two revert patterns:
            # 1. Full pre-DM-23 revert: collection="monitoring_topics", document_id=account_id
            # 2. Partial post-DM-23 revert: collection="monitoring_topics", document_id="default"
            forbidden_calls = [
                call(collection="monitoring_topics", document_id=_ACCOUNT_ID),
                call(collection="monitoring_topics", document_id="default"),
            ]
            actual_calls = mock_firestore.get_document.call_args_list
            for forbidden in forbidden_calls:
                assert forbidden not in actual_calls, (
                    f"Shape A access pattern detected: get_document was called with "
                    f"collection='monitoring_topics'. "
                    "The router must always use the Shape B path "
                    f"'accounts/{_ACCOUNT_ID}/monitoring_topics'."
                )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)


class TestMonitoringTopicsWriteShapeParity:
    """Verify PUT/POST/DELETE write endpoints use Shape B Firestore paths (DM-68).

    Guards against partial reverts of the DM-23 migration that would flip only
    write call-site string literals back to the legacy Shape A pattern while
    leaving `_monitoring_topics_subcollection()` intact — a scenario not caught
    by the TestMonitoringTopicsShapeParity GET test above.

    Each test:
    1. Drives the endpoint through the full FastAPI request path via TestClient.
    2. Mocks `get_document` to return the pre-migration fixture so the Neo4j
       doc-creation branch is skipped.
    3. Asserts the endpoint responds HTTP 200.
    4. Asserts `update_document` was called with the Shape B collection path
       and document_id "default".
    """

    @pytest.fixture
    def mock_user(self) -> UserContext:
        return UserContext(
            user_id="user_test_001",
            email="tester@client-example.com",
            organization_permissions={},
            account_permissions={_ACCOUNT_ID: "edit"},
        )

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_update_company_keywords_uses_shape_b_path(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """PUT /{account_id}/company writes to the Shape B collection path."""
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = _PRE_MIGRATION_FIXTURE

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.put(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}/company",
                headers={"Authorization": "Bearer test_token"},
                json={"account_id": _ACCOUNT_ID, "company_keywords": ["acme brand"]},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_firestore.update_document.assert_called_once_with(
                collection=f"accounts/{_ACCOUNT_ID}/monitoring_topics",
                document_id="default",
                data=ANY,
            )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)

    def test_update_customer_keywords_uses_shape_b_path(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """PUT /{account_id}/customers writes to the Shape B collection path."""
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = _PRE_MIGRATION_FIXTURE

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.put(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}/customers",
                headers={"Authorization": "Bearer test_token"},
                json={
                    "account_id": _ACCOUNT_ID,
                    "customer_keywords": ["cmo", "vp marketing"],
                },
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_firestore.update_document.assert_called_once_with(
                collection=f"accounts/{_ACCOUNT_ID}/monitoring_topics",
                document_id="default",
                data=ANY,
            )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)

    def test_add_competitor_uses_shape_b_path(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """POST /{account_id}/competitors writes to the Shape B collection path."""
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = _PRE_MIGRATION_FIXTURE

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.post(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}/competitors",
                headers={"Authorization": "Bearer test_token"},
                json={
                    "account_id": _ACCOUNT_ID,
                    "competitor_entry": {
                        "node_id": "comp_test_001",
                        "keywords": ["rival product"],
                    },
                },
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_firestore.update_document.assert_called_once_with(
                collection=f"accounts/{_ACCOUNT_ID}/monitoring_topics",
                document_id="default",
                data=ANY,
            )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)

    def test_delete_competitor_uses_shape_b_path(
        self, client: TestClient, mock_user: UserContext
    ) -> None:
        """DELETE /{account_id}/competitors/{index} writes to the Shape B collection path.

        Uses competitor_index=0 — the fixture has exactly one competitor at index 0.
        """
        mock_firestore = MagicMock()
        mock_firestore.get_document.return_value = _PRE_MIGRATION_FIXTURE

        app.dependency_overrides[get_current_user_context] = lambda: mock_user
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.delete(
                f"/api/v1/monitoring-topics/{_ACCOUNT_ID}/competitors/0",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}: {response.text}"
            )

            mock_firestore.update_document.assert_called_once_with(
                collection=f"accounts/{_ACCOUNT_ID}/monitoring_topics",
                document_id="default",
                data=ANY,
            )
        finally:
            app.dependency_overrides.pop(get_current_user_context, None)
            app.dependency_overrides.pop(get_firestore_service, None)
