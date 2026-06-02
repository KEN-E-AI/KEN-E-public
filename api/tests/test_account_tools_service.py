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


class TestAgentToolsInventory:
    """AH-98: agent-as-a-tool entries (``agent.{name}``) in the inventory."""

    @pytest.fixture
    def catalogue_with_agent_tool(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "tools": [],
            "function_tools": [],
            "agent_tools": [
                {
                    "name": "google_search",
                    "description": "Search the web.",
                    "category": "research",
                    "default_global": False,
                }
            ],
        }

    def test_agent_tool_surfaced_as_builtin(
        self, catalogue_with_agent_tool: dict[str, list[dict[str, Any]]]
    ) -> None:
        db = _db_with_connected_integrations()
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=catalogue_with_agent_tool
        )
        gs = next(t for t in response.tools if t.tool_id == "agent.google_search")
        assert gs.name == "google_search"
        assert gs.source == "global_default"
        assert gs.mcp_server is None
        assert gs.integration_platform is None

    def test_agent_tool_surfaced_without_any_integration(
        self, catalogue_with_agent_tool: dict[str, list[dict[str, Any]]]
    ) -> None:
        # Opt-in (default_global False) but still always offered in the picker —
        # no integration required.
        db = _db_with_connected_integrations()
        response = compose_inventory(
            account_id="acc_test", db=db, catalogue=catalogue_with_agent_tool
        )
        assert any(t.tool_id == "agent.google_search" for t in response.tools)

    def test_list_known_tool_ids_includes_agent_tool(
        self, catalogue_with_agent_tool: dict[str, list[dict[str, Any]]]
    ) -> None:
        ids = account_tools_service.list_known_tool_ids(
            catalogue=catalogue_with_agent_tool
        )
        assert "agent.google_search" in ids

    def test_default_catalogue_surfaces_google_search(self) -> None:
        # Smoke: the real tools.yaml surfaces google_search as an agent tool.
        db = _db_with_connected_integrations()
        response = compose_inventory(account_id="acc_test", db=db)
        assert any(t.tool_id == "agent.google_search" for t in response.tools)

    def test_default_catalogue_known_ids_includes_google_search(self) -> None:
        assert "agent.google_search" in account_tools_service.list_known_tool_ids()

    def test_known_agent_ids_match_yaml(self) -> None:
        # Internal-consistency guard against parser drift: the agent ids the
        # router validates against must equal the ``agent_tools:`` entries in the
        # real catalogue. (The ADK-side registry is locked by the ADK suite's
        # test_load_default_config — together they keep both parsers in sync.)
        import yaml

        raw = (
            yaml.safe_load(account_tools_service._resolve_tools_yaml_path().read_text())
            or {}
        )
        yaml_agent_ids = {f"agent.{t['name']}" for t in (raw.get("agent_tools") or [])}
        known_agent_ids = {
            i
            for i in account_tools_service.list_known_tool_ids()
            if i.startswith("agent.")
        }
        assert known_agent_ids == yaml_agent_ids
        assert yaml_agent_ids  # non-empty → google_search present


class TestLoadCatalogue:
    def test_missing_yaml_returns_empty(self, tmp_path) -> None:
        # The service handles a missing catalogue file gracefully — useful in
        # test environments where the file isn't reachable.
        missing = tmp_path / "nonexistent.yaml"
        loaded = account_tools_service._load_catalogue(missing)
        assert loaded == {"tools": [], "function_tools": [], "agent_tools": []}

    def test_path_resolver_walks_up_to_canonical_location(self) -> None:
        # Review item #6: the resolver should locate the catalogue without
        # a hardcoded parents[N] depth, so a repo reshuffle doesn't silently
        # empty the inventory. Smoke check: in the canonical layout the
        # walk-up finds the live catalogue.
        path = account_tools_service._resolve_tools_yaml_path()
        assert path.exists()
        assert path.name == "tools.yaml"

    def test_env_override_takes_precedence(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Setting KENE_TOOLS_YAML_PATH should override the walk-up.
        override = tmp_path / "alt_tools.yaml"
        override.write_text("function_tools: []\ntools: []\n")
        monkeypatch.setenv("KENE_TOOLS_YAML_PATH", str(override))
        path = account_tools_service._resolve_tools_yaml_path()
        assert path == override

    def test_env_override_to_missing_file_raises(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An env var that points at nothing should fail loudly rather than
        # silently fall through to the walk-up (which would mask the
        # operator's intent).
        bogus = tmp_path / "does_not_exist.yaml"
        monkeypatch.setenv("KENE_TOOLS_YAML_PATH", str(bogus))
        with pytest.raises(FileNotFoundError, match="KENE_TOOLS_YAML_PATH"):
            account_tools_service._resolve_tools_yaml_path()

    def test_load_catalogue_uses_import_time_path_without_walk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Review item: _TOOLS_YAML was previously dead. Now _load_catalogue(None)
        # uses it directly when set, so _resolve_tools_yaml_path is NOT called
        # on every request. Patch the resolver to raise — if the code path still
        # walks, this test fails.
        def _fail(*args, **kwargs):
            raise AssertionError(
                "_resolve_tools_yaml_path should not be called when _TOOLS_YAML is set"
            )

        monkeypatch.setattr(account_tools_service, "_resolve_tools_yaml_path", _fail)
        # Sanity: in this test environment _TOOLS_YAML was resolved at import.
        assert account_tools_service._TOOLS_YAML is not None
        loaded = account_tools_service._load_catalogue()
        # Catalogue parse succeeded → the import-time path was used.
        assert "function_tools" in loaded

    def test_load_catalogue_retries_resolution_when_import_failed(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # When import-time resolution failed (`_TOOLS_YAML is None`), the
        # service should retry on each call so a moved file or a
        # late-set env var can recover.
        override = tmp_path / "alt_tools.yaml"
        override.write_text(
            "function_tools:\n"
            "  - name: alt_tool\n"
            "    description: Alt\n"
            "    category: misc\n"
            "    default_global: true\n"
        )
        # Simulate failed import-time resolution.
        monkeypatch.setattr(account_tools_service, "_TOOLS_YAML", None)
        # And a fresh resolver that finds the alt file.
        monkeypatch.setattr(
            account_tools_service,
            "_resolve_tools_yaml_path",
            lambda: override,
        )
        # Clear the parse cache so the override is read fresh.
        account_tools_service._parse_catalogue.cache_clear()

        loaded = account_tools_service._load_catalogue()
        assert any(t["name"] == "alt_tool" for t in loaded["function_tools"])
