"""Integration tests for ``GET /api/v1/accounts/{account_id}/tools`` (AH-PRD-06).

Covers authorization (any-account-access required) and the happy-path response
shape with mocked Firestore + a small catalogue stubbed into the service. No
emulator required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.dependencies import get_firestore
from src.kene_api.main import app
from src.kene_api.services import account_tools_service

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"

ACCOUNT_ID = "acc_test_001"
URL = f"/api/v1/accounts/{ACCOUNT_ID}/tools"


_FAKE_CATALOGUE: dict[str, list[dict[str, Any]]] = {
    "tools": [
        {
            "name": "list_ga_accounts",
            "description": "List GA accounts.",
            "category": "analytics",
            "mcp_server": "google_analytics_mcp",
        },
    ],
    "function_tools": [
        {
            "name": "create_visualization",
            "description": "Render a chart.",
            "category": "visualization",
            "default_global": True,
        },
    ],
}


def _super_admin() -> UserContext:
    return UserContext(
        user_id="super-uid",
        email="ops@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _account_member() -> UserContext:
    return UserContext(
        user_id="member-uid",
        email="member@example.com",
        organization_permissions={},
        account_permissions={ACCOUNT_ID: "view"},
    )


def _stranger() -> UserContext:
    return UserContext(
        user_id="stranger-uid",
        email="stranger@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _db_with_ga_connected() -> MagicMock:
    db = MagicMock()
    collection_ref = MagicMock()
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = True
    doc_ref.get.return_value = snapshot
    collection_ref.document.return_value = doc_ref
    db.collection.return_value = collection_ref
    return db


def _db_no_integrations() -> MagicMock:
    db = MagicMock()
    collection_ref = MagicMock()
    doc_ref = MagicMock()
    snapshot = MagicMock()
    snapshot.exists = False
    doc_ref.get.return_value = snapshot
    collection_ref.document.return_value = doc_ref
    db.collection.return_value = collection_ref
    return db


@pytest.fixture(autouse=True)
def _stub_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    # Pin the catalogue used by the endpoint so the test doesn't depend on the
    # canonical tools.yaml. The router calls compose_inventory without a
    # `catalogue` arg; monkeypatching the loader gives a stable input.
    monkeypatch.setattr(
        account_tools_service,
        "_load_catalogue",
        lambda path=None: _FAKE_CATALOGUE,
    )


@pytest.fixture(autouse=True)
def _reset_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _patch_owning_org_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub Neo4j resolver so tests don't require a live database."""
    monkeypatch.setattr(_RESOLVER, AsyncMock(return_value="org_test"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _install(user: UserContext, db: MagicMock) -> None:
    async def _get_user() -> UserContext:
        return user

    app.dependency_overrides[get_current_user_context] = _get_user
    app.dependency_overrides[get_firestore] = lambda: db


class TestAccountToolsAuth:
    def test_stranger_is_not_found(self, client: TestClient) -> None:
        _install(_stranger(), _db_no_integrations())
        resp = client.get(URL)
        assert resp.status_code == 404

    def test_account_member_can_read(self, client: TestClient) -> None:
        _install(_account_member(), _db_no_integrations())
        resp = client.get(URL)
        assert resp.status_code == 200

    def test_super_admin_can_read(self, client: TestClient) -> None:
        _install(_super_admin(), _db_no_integrations())
        resp = client.get(URL)
        assert resp.status_code == 200


class TestAccountToolsHappyPath:
    def test_no_integrations_returns_only_function_tools(
        self, client: TestClient
    ) -> None:
        _install(_account_member(), _db_no_integrations())
        resp = client.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert [t["tool_id"] for t in body["tools"]] == [
            "function.create_visualization"
        ]
        assert body["tools"][0]["source"] == "global_default"

    def test_connected_integration_unlocks_mcp_tools(self, client: TestClient) -> None:
        _install(_account_member(), _db_with_ga_connected())
        resp = client.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        tool_ids = sorted(t["tool_id"] for t in body["tools"])
        assert tool_ids == [
            "function.create_visualization",
            "google_analytics_mcp.list_ga_accounts",
        ]
        ga = next(
            t for t in body["tools"] if t["tool_id"].startswith("google_analytics_mcp.")
        )
        assert ga["source"] == "integration"
        assert ga["mcp_server"] == "google_analytics_mcp"
        assert ga["integration_platform"] == "google_analytics"
