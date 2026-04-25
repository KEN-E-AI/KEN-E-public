"""Consistency + fallback tests for the Firestore-backed MCP config loader.

Covers Sprint 6 Story 1.1.4-2 acceptance criteria:

* AC-2 — all 6 YAML entries migrate to mcp_server_configs/{id}
* AC-4 — Firestore-unreachable triggers YAML fallback with WARN log
* AC-6 — YAML and Firestore produce identical runtime MCPServerConfig objects

The loader is exercised with a fake in-memory Firestore client. The migration
helper is exercised by building the same Firestore payload the script would
write, then verifying that the loader round-trips it back to MCPServerConfig
instances equal to the YAML loader's output.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.adk.mcp_config.config import (
    MCPConfigLoader,
    MCPServerConfig,
    SseConnectionConfig,
    StdioConnectionConfig,
)
from app.adk.mcp_config.firestore_loader import FirestoreMCPLoader
from app.adk.mcp_config.scripts.migrate_mcp_to_firestore import (
    build_firestore_payload,
    read_yaml_servers_raw,
)

# ---------------------------------------------------------------------------
# Fake Firestore client (hermetic — no network)
# ---------------------------------------------------------------------------


class _FakeDoc:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class _FakeDocRef:
    def __init__(self, doc_id: str, store: dict[str, dict[str, Any]]) -> None:
        self.id = doc_id
        self._store = store

    def get(self) -> _FakeDoc:
        return _FakeDoc(self.id, self._store.get(self.id))

    def set(self, data: dict[str, Any]) -> None:
        self._store[self.id] = data


class _FakeCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def stream(self) -> Any:
        for doc_id, data in self._store.items():
            yield _FakeDoc(doc_id, data)

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(doc_id, self._store)


class FakeFirestoreClient:
    """Hermetic stand-in for google.cloud.firestore.Client.

    Only implements the subset of the API that FirestoreMCPLoader needs:
    ``.collection(name).stream()`` and ``.collection(name).document(id).set()``.
    """

    def __init__(self, mcp_docs: dict[str, dict[str, Any]] | None = None) -> None:
        self._collections: dict[str, dict[str, Any]] = {
            "mcp_server_configs": dict(mcp_docs or {}),
        }

    def collection(self, name: str) -> _FakeCollection:
        self._collections.setdefault(name, {})
        return _FakeCollection(self._collections[name])

    @property
    def mcp_store(self) -> dict[str, dict[str, Any]]:
        return self._collections["mcp_server_configs"]


class RaisingFirestoreClient:
    """Simulates Firestore being unreachable — every op raises."""

    def collection(self, name: str) -> Any:
        from google.api_core import exceptions as gcp_exc

        raise gcp_exc.ServiceUnavailable("503 Firestore unreachable")


# ---------------------------------------------------------------------------
# Fixtures — env + payloads
# ---------------------------------------------------------------------------


@pytest.fixture
def resolved_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set concrete values for every ${VAR} the YAML references.

    Both the YAML and Firestore loaders resolve ``${VAR}`` at load time via
    ``shared.secrets.get_env_or_secret``. For the consistency test to be
    meaningful, we pin every referenced env var to a known value.
    """
    monkeypatch.setenv("GA_MCP_SERVER_URL", "https://ga.example.com")
    monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
    monkeypatch.setenv("HUBSPOT_API_KEY", "hub-key-123")
    monkeypatch.setenv("META_MCP_URL", "https://meta.example.com/mcp")
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-token-456")
    monkeypatch.setenv("GOOGLE_ADS_MCP_URL", "https://gads.example.com/mcp")
    monkeypatch.setenv("GOOGLE_ADS_TOKEN", "gads-token-789")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-bot-abc")
    monkeypatch.setenv("SLACK_APP_TOKEN", "slack-app-def")
    monkeypatch.setenv("NOTION_API_KEY", "notion-key-xyz")


@pytest.fixture
def migrated_firestore_docs(
    resolved_env: None,
) -> dict[str, dict[str, Any]]:
    """Simulate what the migration script writes to Firestore.

    Uses the script's own ``build_firestore_payload`` so the test exercises
    the real migration derivation rules (integration_type=mcp, hosting from
    connection_type, specialist_categories=[category], metadata initialized).
    """
    raw_servers = read_yaml_servers_raw()
    return {
        server_id: build_firestore_payload(
            server_id=server_id,
            raw=raw,
            now_iso="2026-04-20T12:00:00+00:00",
        )
        for server_id, raw in raw_servers.items()
    }


# ---------------------------------------------------------------------------
# Consistency (AC-2, AC-6)
# ---------------------------------------------------------------------------


class TestConsistency:
    def test_all_six_yaml_entries_present_in_migration_payload(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        """AC-2: all 6 MCP server definitions get migrated."""
        expected = {
            "google_analytics_mcp",
            "hubspot_mcp",
            "meta_ads_mcp",
            "google_ads_mcp",
            "slack_mcp",
            "notion_mcp",
        }
        assert set(migrated_firestore_docs.keys()) == expected

    def test_firestore_and_yaml_produce_identical_runtime_configs(
        self,
        migrated_firestore_docs: dict[str, dict[str, Any]],
        resolved_env: None,
    ) -> None:
        """AC-6: YAML and Firestore loaders produce equivalent runtime configs."""
        yaml_loader = MCPConfigLoader()
        yaml_configs = yaml_loader.load()

        fs_loader = FirestoreMCPLoader(
            client=FakeFirestoreClient(migrated_firestore_docs)
        )
        fs_configs = fs_loader.load()

        assert set(yaml_configs.keys()) == set(fs_configs.keys())

        for name in yaml_configs:
            y = yaml_configs[name]
            f = fs_configs[name]

            assert isinstance(f, MCPServerConfig), (
                f"Firestore loader must return MCPServerConfig for '{name}', "
                f"got {type(f).__name__}"
            )

            # Core scalar fields
            assert y.name == f.name == name
            assert y.description == f.description
            assert y.category == f.category
            assert y.tool_count == f.tool_count
            assert y.estimated_tokens == f.estimated_tokens
            assert sorted(y.keywords) == sorted(f.keywords)
            assert y.auth_type == f.auth_type
            assert y.enabled == f.enabled

            # Connection discriminator + resolved URLs/commands
            assert type(y.connection) is type(f.connection)
            if isinstance(y.connection, SseConnectionConfig):
                assert isinstance(f.connection, SseConnectionConfig)
                assert y.connection.url == f.connection.url, (
                    f"URL mismatch for '{name}': YAML={y.connection.url!r} "
                    f"vs FS={f.connection.url!r}"
                )
                assert y.connection.headers == f.connection.headers
                assert y.connection.timeout_seconds == f.connection.timeout_seconds
            elif isinstance(y.connection, StdioConnectionConfig):
                assert isinstance(f.connection, StdioConnectionConfig)
                assert y.connection.command == f.connection.command
                assert y.connection.args == f.connection.args
                assert y.connection.env == f.connection.env

    def test_migration_payload_stores_literal_var_patterns(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        """Secrets must be stored as literal ${VAR} strings, not resolved.

        Rotation is supposed to require env/Secret-Manager update, not
        Firestore write (per Decision A).
        """
        ga_doc = migrated_firestore_docs["google_analytics_mcp"]
        assert "${GA_MCP_SERVER_URL}" in ga_doc["connection"]["url"], (
            f"Expected literal ${{GA_MCP_SERVER_URL}} in migrated URL, got "
            f"{ga_doc['connection']['url']!r}"
        )

        slack_doc = migrated_firestore_docs["slack_mcp"]
        assert "${SLACK_BOT_TOKEN}" in slack_doc["connection"]["env"]["SLACK_BOT_TOKEN"]


class TestMigrationDerivations:
    """Decision A migration rules: integration_type default, hosting from
    connection_type, specialist_categories=[category]."""

    def test_integration_type_defaults_to_mcp(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        for doc in migrated_firestore_docs.values():
            assert doc["integration_type"] == "mcp"

    def test_hosting_matches_connection_type(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        for name, doc in migrated_firestore_docs.items():
            ct = doc["connection"]["connection_type"]
            expected = "self" if ct == "stdio" else "provider"
            assert doc["hosting"] == expected, (
                f"Server '{name}' has connection_type={ct} but "
                f"hosting={doc['hosting']} (expected {expected})"
            )

    def test_specialist_categories_wraps_singular_category(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        assert migrated_firestore_docs["google_analytics_mcp"][
            "specialist_categories"
        ] == ["analytics"]
        assert migrated_firestore_docs["slack_mcp"]["specialist_categories"] == [
            "communication"
        ]

    def test_metadata_initialized_with_defaults(
        self, migrated_firestore_docs: dict[str, dict[str, Any]]
    ) -> None:
        for doc in migrated_firestore_docs.values():
            md = doc["metadata"]
            assert md["version"] == "v1.0.0"
            assert md["variant_name"] == "baseline"
            assert md["experiment_id"] == "baseline"
            assert md["updated_by"] == "migration_script"
            assert md["created_at"] == md["updated_at"]


# ---------------------------------------------------------------------------
# Fallback (AC-4)
# ---------------------------------------------------------------------------


class TestFallback:
    def test_firestore_unreachable_falls_back_to_yaml(
        self,
        resolved_env: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AC-4: on Firestore connection error, loader falls back to YAML with WARN."""
        caplog.set_level(logging.WARNING)

        loader = FirestoreMCPLoader(client=RaisingFirestoreClient())
        configs = loader.load()

        # Same 6 entries the YAML loader would return
        assert len(configs) == 6
        assert "google_analytics_mcp" in configs
        assert isinstance(
            configs["google_analytics_mcp"].connection, SseConnectionConfig
        )

        # WARN log emitted
        warn_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any(
            "firestore" in r.message.lower() and "yaml" in r.message.lower()
            for r in warn_records
        ), (
            "Expected a WARNING log mentioning both 'firestore' and 'yaml' "
            f"for fallback. Got: {[r.message for r in warn_records]}"
        )

    def test_fallback_preserves_public_interface(self, resolved_env: None) -> None:
        """After fallback, .get_server / .get_enabled_servers still work."""
        loader = FirestoreMCPLoader(client=RaisingFirestoreClient())
        loader.load()

        ga = loader.get_server("google_analytics_mcp")
        assert ga is not None
        assert ga.enabled is True

        enabled = loader.get_enabled_servers()
        assert len(enabled) == 1  # Only GA is enabled in YAML
        assert enabled[0].name == "google_analytics_mcp"

    def test_empty_firestore_collection_is_not_treated_as_error(
        self, resolved_env: None
    ) -> None:
        """An empty collection means 'no servers configured' — distinct from
        a connection error. Loader must return empty configs, not fall back.

        This is the guardrail against accidentally re-enabling all YAML
        servers if an admin intentionally disables the entire MCP set.
        """
        loader = FirestoreMCPLoader(client=FakeFirestoreClient({}))
        configs = loader.load()

        assert configs == {}


# ---------------------------------------------------------------------------
# Public interface parity
# ---------------------------------------------------------------------------


class TestLoaderInterface:
    """FirestoreMCPLoader must expose the same public surface as MCPConfigLoader
    so MCPServerManager can swap loaders without code changes."""

    def test_exposes_mcpconfigloader_public_methods(
        self,
        migrated_firestore_docs: dict[str, dict[str, Any]],
        resolved_env: None,
    ) -> None:
        loader = FirestoreMCPLoader(client=FakeFirestoreClient(migrated_firestore_docs))

        assert hasattr(loader, "load")
        assert hasattr(loader, "reload")
        assert hasattr(loader, "configs")
        assert hasattr(loader, "get_server")
        assert hasattr(loader, "get_enabled_servers")
        assert hasattr(loader, "get_servers_by_category")

        loader.load()
        assert isinstance(loader.configs, dict)
        assert isinstance(loader.get_server("google_analytics_mcp"), MCPServerConfig)
        assert loader.get_server("nonexistent_mcp") is None

    def test_reload_refreshes_from_firestore(
        self,
        migrated_firestore_docs: dict[str, dict[str, Any]],
        resolved_env: None,
    ) -> None:
        fake = FakeFirestoreClient(migrated_firestore_docs)
        loader = FirestoreMCPLoader(client=fake)
        loader.load()
        assert len(loader.configs) == 6

        # Remove a doc from the underlying store
        del fake.mcp_store["hubspot_mcp"]

        # Before reload, still sees cached config
        assert "hubspot_mcp" in loader.configs

        # After reload, gone
        loader.reload()
        assert "hubspot_mcp" not in loader.configs
        assert len(loader.configs) == 5


# ---------------------------------------------------------------------------
# Factory selection via MCP_CONFIG_SOURCE env var
# ---------------------------------------------------------------------------


class TestFactorySelection:
    """The ``get_mcp_config_loader`` factory must honor ``MCP_CONFIG_SOURCE``."""

    def test_default_yaml_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        resolved_env: None,
    ) -> None:
        from app.adk.mcp_config.config import (
            MCPConfigLoader,
            get_mcp_config_loader,
            reset_mcp_config_loader,
        )

        monkeypatch.delenv("MCP_CONFIG_SOURCE", raising=False)
        reset_mcp_config_loader()

        loader = get_mcp_config_loader()
        assert isinstance(loader, MCPConfigLoader)
        assert len(loader.configs) == 6

        reset_mcp_config_loader()

    def test_firestore_source_selects_firestore_loader(
        self,
        monkeypatch: pytest.MonkeyPatch,
        resolved_env: None,
    ) -> None:
        """Under MCP_CONFIG_SOURCE=firestore, the factory returns the
        Firestore loader. Without real Firestore creds it immediately falls
        back to YAML, but the returned type is the Firestore loader."""
        from app.adk.mcp_config.config import (
            get_mcp_config_loader,
            reset_mcp_config_loader,
        )
        from app.adk.mcp_config.firestore_loader import FirestoreMCPLoader

        monkeypatch.setenv("MCP_CONFIG_SOURCE", "firestore")
        reset_mcp_config_loader()

        # Patch the FirestoreMCPLoader to use a RaisingFirestoreClient so we
        # don't hit real GCP during tests.
        original_get_client = FirestoreMCPLoader._get_client
        monkeypatch.setattr(
            FirestoreMCPLoader,
            "_get_client",
            lambda self: RaisingFirestoreClient(),
        )

        try:
            loader = get_mcp_config_loader()
            assert isinstance(loader, FirestoreMCPLoader)
            # Fell back to YAML
            assert loader.fallback_active is True
            assert len(loader.configs) == 6
        finally:
            monkeypatch.setattr(FirestoreMCPLoader, "_get_client", original_get_client)
            reset_mcp_config_loader()

    def test_unknown_source_defaults_to_yaml_with_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        resolved_env: None,
    ) -> None:
        from app.adk.mcp_config.config import (
            MCPConfigLoader,
            get_mcp_config_loader,
            reset_mcp_config_loader,
        )

        monkeypatch.setenv("MCP_CONFIG_SOURCE", "sqlite")  # unsupported
        reset_mcp_config_loader()
        caplog.set_level(logging.WARNING)

        loader = get_mcp_config_loader()

        assert isinstance(loader, MCPConfigLoader)
        assert any(
            "sqlite" in r.message.lower()
            for r in caplog.records
            if r.levelno >= logging.WARNING
        )

        reset_mcp_config_loader()
