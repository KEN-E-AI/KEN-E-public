"""Unit tests for ``services.account_tools_service`` (AH-PRD-06).

The service composes the per-account tool inventory from the static catalogue
plus the account's connected integrations. These tests mock both inputs to
keep the unit pure.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from src.kene_api.services import account_tools_service
from src.kene_api.services.account_tools_service import compose_inventory


@pytest.fixture
def fake_catalogue() -> dict[str, list[dict[str, Any]]]:
    return {
        "tools": [
            {
                "name": "list_ga_accounts",
                "description": "List GA accounts.",
                "category": "analytics",
                "mcp_server": "google_analytics_mcp",
            },
            {
                "name": "query_ga_report",
                "description": "Query GA.",
                "category": "analytics",
                "mcp_server": "google_analytics_mcp",
            },
            {
                # Uncatalogued server — should be ignored even if added later.
                "name": "list_meta_campaigns",
                "description": "List Meta campaigns.",
                "category": "advertising",
                "mcp_server": "meta_ads_mcp",
            },
        ],
        "function_tools": [
            {
                "name": "create_visualization",
                "description": "Render a chart.",
                "category": "visualization",
                "default_global": True,
            },
            {
                # Non-default function tool — should not appear in inventory.
                "name": "internal_helper",
                "description": "Internal-only function tool.",
                "category": "general",
                "default_global": False,
            },
        ],
    }


def _db_with_connected_integrations(*integration_types: str) -> MagicMock:
    """Build a Firestore mock where the listed integration_types are 'connected'.

    The service reads ``integration_credentials/{account_id}_{integration_type}``
    and treats `doc.exists` as the gate. The mock returns `exists=True` for
    expected doc IDs and `exists=False` otherwise.
    """
    db = MagicMock()
    connected_docs = {f"acc_test_{i}" for i in integration_types}

    def _document(doc_id: str) -> MagicMock:
        doc_ref = MagicMock()
        snapshot = MagicMock()
        snapshot.exists = doc_id in connected_docs
        doc_ref.get.return_value = snapshot
        return doc_ref

    collection_ref = MagicMock()
    collection_ref.document.side_effect = _document
    db.collection.return_value = collection_ref
    return db


class TestComposeInventory:
    def test_function_tools_always_present(
        self, fake_catalogue: dict[str, list[dict[str, Any]]]
    ) -> None:
        # No integrations connected → only default_global function tools.
        db = _db_with_connected_integrations()
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=fake_catalogue
        )

        tool_ids = [t.tool_id for t in response.tools]
        assert tool_ids == ["function.create_visualization"]
        viz = response.tools[0]
        assert viz.source == "global_default"
        assert viz.mcp_server is None
        assert viz.integration_platform is None

    def test_integration_unlocks_mcp_tools(
        self, fake_catalogue: dict[str, list[dict[str, Any]]]
    ) -> None:
        db = _db_with_connected_integrations("google_analytics")
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=fake_catalogue
        )

        tool_ids = sorted(t.tool_id for t in response.tools)
        assert tool_ids == [
            "function.create_visualization",
            "google_analytics_mcp.list_ga_accounts",
            "google_analytics_mcp.query_ga_report",
        ]

        ga_tool = next(
            t for t in response.tools if t.tool_id.startswith("google_analytics_mcp.")
        )
        assert ga_tool.source == "integration"
        assert ga_tool.mcp_server == "google_analytics_mcp"
        assert ga_tool.integration_platform == "google_analytics"

    def test_unmapped_mcp_server_is_skipped(
        self, fake_catalogue: dict[str, list[dict[str, Any]]]
    ) -> None:
        # ``meta_ads_mcp`` is in the catalogue but not in the
        # integration->server map, so its tools never surface even if "meta_ads"
        # were spuriously listed as connected.
        db = _db_with_connected_integrations("google_analytics", "meta_ads")
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=fake_catalogue
        )
        assert not any(t.mcp_server == "meta_ads_mcp" for t in response.tools)

    def test_non_default_function_tool_skipped(
        self, fake_catalogue: dict[str, list[dict[str, Any]]]
    ) -> None:
        db = _db_with_connected_integrations()
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=fake_catalogue
        )
        assert not any(t.name == "internal_helper" for t in response.tools)

    def test_firestore_read_error_treated_as_disconnected(
        self, fake_catalogue: dict[str, list[dict[str, Any]]]
    ) -> None:
        # If Firestore raises for the credential lookup, the integration is
        # treated as disconnected (its tools don't surface) but the response
        # is still produced — function tools still show up.
        db = MagicMock()
        collection_ref = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = RuntimeError("transient firestore error")
        collection_ref.document.return_value = doc_ref
        db.collection.return_value = collection_ref

        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=fake_catalogue
        )
        assert [t.tool_id for t in response.tools] == ["function.create_visualization"]

    def test_default_catalogue_loads_from_yaml(self) -> None:
        # Smoke test: when no `catalogue` arg is passed, the service reads the
        # canonical tools.yaml. We don't assert on every entry — just that the
        # load succeeded and contains the seed function tool.
        db = _db_with_connected_integrations()
        response = compose_inventory(account_id="acc_test", db=db)
        assert any(t.tool_id == "function.create_visualization" for t in response.tools)


class TestLoadCatalogue:
    def test_missing_yaml_returns_empty(self, tmp_path) -> None:
        # The service handles a missing catalogue file gracefully — useful in
        # test environments where the file isn't reachable.
        missing = tmp_path / "nonexistent.yaml"
        loaded = account_tools_service._load_catalogue(missing)
        assert loaded == {"tools": [], "function_tools": []}
