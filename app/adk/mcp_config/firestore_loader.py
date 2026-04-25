"""Firestore-backed MCP server config loader.

Drop-in replacement for ``MCPConfigLoader`` that sources configs from the
``mcp_server_configs/{server_id}`` collection instead of YAML. Falls back to
the bundled YAML on Firestore connection errors so the runtime degrades
safely (Harness §11.1.3, Sprint 6 AC-6.4 / AC-6.26).

Public surface mirrors ``MCPConfigLoader`` exactly — ``MCPServerManager``
treats both loaders as interchangeable through the ``get_mcp_config_loader``
factory in ``config.py``.

See Sprint 6 Decision A for the Firestore document shape:
https://www.notion.so/34830fd653028158bb4be8b22622bcb8
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.structured_logging import get_structured_logger, log_context

from .config import MCPConfigLoader, MCPServerConfig, _resolve_env_vars_in_dict

if TYPE_CHECKING:
    from google.cloud import firestore

logger = get_structured_logger(__name__)


MCP_COLLECTION = "mcp_server_configs"

# Registry-level fields stored in Firestore but not part of the runtime
# ``MCPServerConfig`` shape — dropped when translating doc → runtime config.
_REGISTRY_ONLY_FIELDS: frozenset[str] = frozenset(
    {"integration_type", "hosting", "specialist_categories", "metadata"}
)


def _doc_to_runtime_config(doc_id: str, data: dict[str, Any]) -> MCPServerConfig:
    """Translate a Firestore MCP server doc to the runtime MCPServerConfig.

    Firestore stores ``${VAR}`` references as literals; this function
    explicitly resolves them before constructing :class:`MCPServerConfig`
    so the runtime receives usable values. (The admin router path does
    NOT call this — literal ``${VAR}`` strings stay untouched on their
    way through the CRUD endpoints, per the Sprint 6 secret-leak fix.)

    Args:
        doc_id: Firestore document ID (used as the server ``name``)
        data: Document payload (with literal ``${VAR}`` strings)

    Returns:
        Runtime MCPServerConfig with secrets resolved.
    """
    runtime_data: dict[str, Any] = {
        k: v for k, v in data.items() if k not in _REGISTRY_ONLY_FIELDS
    }

    # specialist_categories (plural, Firestore-only) → category (singular, runtime)
    categories = data.get("specialist_categories", [])
    if categories:
        runtime_data["category"] = categories[0]
    elif "category" not in runtime_data:
        runtime_data["category"] = "uncategorized"

    # ``name`` is stored in the doc payload and also derivable from the doc ID.
    # Prefer the payload value but fall back to doc_id for defensive safety.
    runtime_data.setdefault("name", doc_id)

    # Resolve ${VAR} literals everywhere (url, headers, env) before Pydantic
    # construction. Matches the YAML loader's behavior and keeps secret
    # resolution a loader-layer concern, not a model side effect.
    runtime_data = _resolve_env_vars_in_dict(runtime_data)

    return MCPServerConfig(**runtime_data)


class FirestoreMCPLoader:
    """Loads MCP server configs from Firestore with YAML fallback.

    Usage:
        loader = FirestoreMCPLoader()
        configs = loader.load()
        ga = loader.get_server("google_analytics_mcp")

    Tests can inject a fake client::

        loader = FirestoreMCPLoader(client=FakeFirestoreClient(docs))
    """

    def __init__(
        self,
        client: firestore.Client | None = None,
        project_id: str | None = None,
        yaml_fallback_path: Path | None = None,
    ) -> None:
        """Initialize the loader.

        Args:
            client: Optional pre-constructed Firestore client. If omitted, a
                client is lazily created on first load using ``project_id``.
            project_id: GCP project ID (used only when ``client`` is None).
            yaml_fallback_path: Path to the bundled YAML fallback. Defaults to
                ``mcp_config/config/mcp_servers.yaml`` (same as MCPConfigLoader).
        """
        self._injected_client = client
        self._project_id = project_id
        self._yaml_fallback_path = yaml_fallback_path
        self._configs: dict[str, MCPServerConfig] = {}
        self._loaded = False
        self._fallback_active = False

    # -- Public API (mirrors MCPConfigLoader) -------------------------------

    @property
    def configs(self) -> dict[str, MCPServerConfig]:
        """Loaded configs; triggers an initial load on first access."""
        if not self._loaded:
            self.load()
        return dict(self._configs)

    def load(self) -> dict[str, MCPServerConfig]:
        """Load configs from Firestore, falling back to YAML on connection errors.

        An empty Firestore collection is NOT treated as an error — it returns
        an empty config set, which represents the "all servers intentionally
        disabled" state. Only actual connection/query failures trigger
        fallback to YAML.

        Returns:
            Dictionary mapping server names to their ``MCPServerConfig``.
        """
        self._fallback_active = False

        try:
            docs = self._fetch_firestore_docs()
        except Exception as e:
            logger.warning(
                f"Firestore unreachable for MCP config; falling back to YAML: {e}",
                extra=log_context(
                    component="mcp_config",
                    action="firestore_fallback_to_yaml",
                    error_message=str(e),
                ),
            )
            self._fallback_active = True
            self._configs = self._load_from_yaml_fallback()
            self._loaded = True
            return dict(self._configs)

        parsed: dict[str, MCPServerConfig] = {}
        for doc_id, data in docs.items():
            if data is None:
                continue
            try:
                parsed[doc_id] = _doc_to_runtime_config(doc_id, data)
                logger.info(
                    f"Loaded MCP server config from Firestore: {doc_id}",
                    extra=log_context(
                        component="mcp_config",
                        action="firestore_load_server",
                        extra={
                            "server_name": doc_id,
                            "enabled": data.get("enabled", True),
                        },
                    ),
                )
            except Exception as e:
                logger.error(
                    f"Invalid MCP config doc '{doc_id}' in Firestore: {e}",
                    extra=log_context(
                        component="mcp_config",
                        action="firestore_doc_parse_error",
                        error_message=str(e),
                        extra={"server_name": doc_id},
                    ),
                )

        self._configs = parsed
        self._loaded = True
        return dict(self._configs)

    def reload(self) -> dict[str, MCPServerConfig]:
        """Force reload from Firestore (or fallback YAML)."""
        self._configs = {}
        self._loaded = False
        return self.load()

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get configuration for a specific server, or None if missing."""
        if not self._loaded:
            self.load()
        return self._configs.get(name)

    def get_enabled_servers(self) -> list[MCPServerConfig]:
        """Return all enabled server configurations."""
        if not self._loaded:
            self.load()
        return [c for c in self._configs.values() if c.enabled]

    def get_servers_by_category(self, category: str) -> list[MCPServerConfig]:
        """Return enabled servers in the given category."""
        if not self._loaded:
            self.load()
        return [
            c for c in self._configs.values() if c.category == category and c.enabled
        ]

    @property
    def fallback_active(self) -> bool:
        """True if the last load fell back to YAML (for observability)."""
        return self._fallback_active

    # -- Internals ----------------------------------------------------------

    def _fetch_firestore_docs(self) -> dict[str, dict[str, Any] | None]:
        """Fetch every doc under ``mcp_server_configs/`` as a ``{id: data}`` map."""
        client = self._get_client()
        collection = client.collection(MCP_COLLECTION)
        return {doc.id: doc.to_dict() for doc in collection.stream()}

    def _get_client(self) -> Any:
        if self._injected_client is not None:
            return self._injected_client

        # Lazy import so tests that inject a fake client don't require the
        # google.cloud.firestore dependency to be importable.
        from google.cloud import firestore as _firestore

        if self._project_id is not None:
            return _firestore.Client(project=self._project_id)
        return _firestore.Client()

    def _load_from_yaml_fallback(self) -> dict[str, MCPServerConfig]:
        loader = MCPConfigLoader(config_path=self._yaml_fallback_path)
        return loader.load()
