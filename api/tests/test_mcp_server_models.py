"""Unit tests for ``models.mcp_server_models``.

Covers schema invariants for ``mcp_server_configs/{id}`` Firestore documents.
These tests exercise the Pydantic models directly (no HTTP, no Firestore).
The consistency check against YAML configs (AC-6.5) is covered separately in
``test_mcp_config_consistency.py`` during Story 1.1.4-2.

Maps to Sprint 6 Story 1.1.4-1 acceptance criteria:
* AC-2: document contains name, url, auth_type, integration_type,
  specialist_categories, hosting, enabled.
* AC-3: config is validated against Pydantic schema before persistence.
* AC-5: ``auth_type`` correctly identifies the session-state credential key.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.kene_api.models.mcp_server_models import (
    CREDENTIAL_KEYS,
    MCPServerConfigUpdate,
    MCPServerFirestoreConfig,
    MCPServerMetadata,
    SseConnectionConfig,
    StdioConnectionConfig,
)


def _valid_metadata(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": "v1.0.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "2026-04-20T12:00:00+00:00",
        "updated_at": "2026-04-20T12:00:00+00:00",
        "updated_by": "alice@ken-e.ai",
        "notes": "",
    }
    base.update(overrides)
    return base


def _valid_sse_config(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "google_analytics_mcp",
        "description": "Google Analytics 4 data access",
        "integration_type": "mcp",
        "hosting": "provider",
        "specialist_categories": ["analytics"],
        "tool_count": 4,
        "estimated_tokens": 1800,
        "keywords": ["analytics", "ga4"],
        "connection": {
            "connection_type": "sse",
            "url": "https://ga.example.com/mcp/sse",
            "headers": {"Content-Type": "application/json"},
            "timeout_seconds": 30,
        },
        "auth_type": "ga_oauth",
        "enabled": True,
        "metadata": _valid_metadata(),
    }
    base.update(overrides)
    return base


def _valid_stdio_config(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "local_tool_mcp",
        "description": "Local subprocess MCP server",
        "integration_type": "mcp",
        "hosting": "self",
        "specialist_categories": ["testing"],
        "tool_count": 2,
        "estimated_tokens": 500,
        "keywords": ["test"],
        "connection": {
            "connection_type": "stdio",
            "command": "npx",
            "args": ["-y", "test-server"],
            "env": {},
        },
        "auth_type": None,
        "enabled": True,
        "metadata": _valid_metadata(),
    }
    base.update(overrides)
    return base


class TestSseConfigRoundTrip:
    def test_round_trip(self) -> None:
        config = MCPServerFirestoreConfig(**_valid_sse_config())

        assert config.name == "google_analytics_mcp"
        assert isinstance(config.connection, SseConnectionConfig)
        assert config.connection.url == "https://ga.example.com/mcp/sse"
        assert config.hosting == "provider"
        assert config.specialist_categories == ["analytics"]
        assert config.auth_type == "ga_oauth"

    def test_integration_type_defaults_to_mcp(self) -> None:
        payload = _valid_sse_config()
        del payload["integration_type"]

        config = MCPServerFirestoreConfig(**payload)

        assert config.integration_type == "mcp"


class TestStdioConfigRoundTrip:
    def test_round_trip(self) -> None:
        config = MCPServerFirestoreConfig(**_valid_stdio_config())

        assert isinstance(config.connection, StdioConnectionConfig)
        assert config.connection.command == "npx"
        assert config.hosting == "self"
        assert config.auth_type is None


class TestHostingConnectionConsistency:
    """The hosting field must agree with the connection discriminator."""

    def test_stdio_with_provider_hosting_rejected(self) -> None:
        payload = _valid_stdio_config(hosting="provider")

        with pytest.raises(ValidationError) as exc_info:
            MCPServerFirestoreConfig(**payload)

        assert "stdio" in str(exc_info.value)
        assert "self" in str(exc_info.value)

    def test_sse_with_self_hosting_rejected(self) -> None:
        payload = _valid_sse_config(hosting="self")

        with pytest.raises(ValidationError) as exc_info:
            MCPServerFirestoreConfig(**payload)

        assert "sse" in str(exc_info.value)
        assert "provider" in str(exc_info.value)


class TestIntegrationType:
    @pytest.mark.parametrize("integration_type", ["mcp", "sdk", "provider_mcp"])
    def test_enum_values_accepted(self, integration_type: str) -> None:
        config = MCPServerFirestoreConfig(
            **_valid_sse_config(integration_type=integration_type)
        )

        assert config.integration_type == integration_type

    @pytest.mark.parametrize("bad_value", ["MCP", "rest", "grpc", "http", ""])
    def test_unknown_values_rejected(self, bad_value: str) -> None:
        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**_valid_sse_config(integration_type=bad_value))


class TestAuthType:
    """AC-5: ``auth_type`` must map to a known session-state credential key."""

    @pytest.mark.parametrize("auth_type", sorted(CREDENTIAL_KEYS))
    def test_known_auth_types_accepted(self, auth_type: str) -> None:
        config = MCPServerFirestoreConfig(**_valid_sse_config(auth_type=auth_type))

        assert config.auth_type == auth_type

    def test_none_accepted_for_unauthed_servers(self) -> None:
        config = MCPServerFirestoreConfig(**_valid_sse_config(auth_type=None))

        assert config.auth_type is None

    @pytest.mark.parametrize("bad_auth", ["oauth", "bearer", "api_key", "ga_oauth_v2"])
    def test_unknown_auth_types_rejected(self, bad_auth: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            MCPServerFirestoreConfig(**_valid_sse_config(auth_type=bad_auth))

        assert "Unknown auth_type" in str(exc_info.value)

    def test_credential_key_mapping(self) -> None:
        """``auth_type`` → session-state key map is exposed as CREDENTIAL_KEYS."""
        assert CREDENTIAL_KEYS["ga_oauth"] == "ga_credentials"
        assert CREDENTIAL_KEYS["google_ads_oauth"] == "google_ads_credentials"
        assert CREDENTIAL_KEYS["hubspot_oauth"] == "hubspot_credentials"


class TestRequiredFields:
    def test_specialist_categories_must_be_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**_valid_sse_config(specialist_categories=[]))

    def test_estimated_tokens_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**_valid_sse_config(estimated_tokens=-1))

    def test_tool_count_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**_valid_sse_config(tool_count=-1))

    def test_missing_hosting_rejected(self) -> None:
        payload = _valid_sse_config()
        del payload["hosting"]

        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**payload)

    def test_missing_metadata_rejected(self) -> None:
        payload = _valid_sse_config()
        del payload["metadata"]

        with pytest.raises(ValidationError):
            MCPServerFirestoreConfig(**payload)


class TestSseEmptyUrl:
    def test_empty_sse_url_rejected(self) -> None:
        payload = _valid_sse_config()
        payload["connection"] = {
            "connection_type": "sse",
            "url": "",
            "headers": {},
            "timeout_seconds": 30,
        }

        with pytest.raises(ValidationError) as exc_info:
            MCPServerFirestoreConfig(**payload)

        assert "non-empty URL" in str(exc_info.value)


class TestMCPServerConfigUpdate:
    def test_partial_update_allowed(self) -> None:
        update = MCPServerConfigUpdate(
            description="New description",
            updated_by="alice@ken-e.ai",
        )

        assert update.description == "New description"
        assert update.auth_type is None
        assert update.enabled is None

    def test_unknown_auth_type_rejected_in_update(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerConfigUpdate(
                updated_by="alice@ken-e.ai",
                auth_type="bearer",
            )

    def test_empty_specialist_categories_rejected_in_update(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerConfigUpdate(
                updated_by="alice@ken-e.ai",
                specialist_categories=[],
            )

    def test_updated_by_required(self) -> None:
        with pytest.raises(ValidationError):
            MCPServerConfigUpdate(description="x")  # type: ignore[call-arg]


class TestMetadata:
    def test_round_trip(self) -> None:
        metadata = MCPServerMetadata(**_valid_metadata())

        assert metadata.version == "v1.0.0"
        assert metadata.variant_name == "baseline"
        assert metadata.experiment_id == "baseline"

    def test_experiment_id_defaults_to_baseline(self) -> None:
        metadata = MCPServerMetadata(
            version="v1.0.0",
            variant_name="baseline",
            created_at="2026-04-20T12:00:00+00:00",
            updated_at="2026-04-20T12:00:00+00:00",
            updated_by="alice@ken-e.ai",
        )

        assert metadata.experiment_id == "baseline"
        assert metadata.notes == ""
