"""Unit tests for ``models.agent_config_models``.

Covers the Pydantic models that back Firestore ``agent_configs/{id}`` docs.
These tests exercise the models directly (not through the router) so that
schema invariants remain intact regardless of HTTP-layer wiring.

Router-level validation + auth + versioning is covered in
``test_agent_configs.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.kene_api.models.agent_config_models import (
    SUPPORTED_MODELS,
    AgentConfig,
    AgentConfigMetadata,
    AgentConfigOverlayUpdate,
    AgentConfigUpdate,
    ConfigAuditEntry,
    MergedAgentConfig,
)


def _valid_metadata(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "version": "v1.0.0",
        "variant_name": "baseline",
        "experiment_id": "baseline",
        "created_at": "2026-04-20T12:00:00+00:00",
        "updated_at": "2026-04-20T12:00:00+00:00",
        "updated_by": "darshan_ken-e_ai",
        "notes": "",
    }
    base.update(overrides)
    return base


def _valid_agent_config(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "ken_e_chatbot",
        "model": "gemini-2.5-pro",
        "description": "Frontend-facing chat agent",
        "instruction": "You are KEN-E...",
        "temperature": 0.3,
        "max_output_tokens": 2500,
        "metadata": _valid_metadata(),
    }
    base.update(overrides)
    return base


class TestAgentConfig:
    """AC-1: ``agent_configs/{id}`` documents contain instruction, model,
    temperature, max_output_tokens, description, version (flat shape per AH-40)."""

    def test_round_trip_from_firestore_dict(self) -> None:
        payload = _valid_agent_config()

        config = AgentConfig(**payload)

        dumped = config.model_dump()
        assert dumped["name"] == "ken_e_chatbot"
        assert dumped["model"] == "gemini-2.5-pro"
        assert dumped["instruction"] == "You are KEN-E..."
        assert dumped["description"] == "Frontend-facing chat agent"
        assert dumped["temperature"] == 0.3
        assert dumped["max_output_tokens"] == 2500
        assert "generate_content_config" not in dumped
        assert dumped["metadata"]["version"] == "v1.0.0"

    def test_defaults_when_temperature_and_tokens_omitted(self) -> None:
        payload = _valid_agent_config()
        del payload["temperature"]
        del payload["max_output_tokens"]

        config = AgentConfig(**payload)

        assert config.temperature == 0.3
        assert config.max_output_tokens == 2500

    @pytest.mark.parametrize("temp", [-0.1, 1.1, 2.0])
    def test_temperature_out_of_range(self, temp: float) -> None:
        payload = _valid_agent_config(temperature=temp)

        with pytest.raises(ValidationError):
            AgentConfig(**payload)

    @pytest.mark.parametrize("tokens", [99, 65536, -1])
    def test_max_output_tokens_out_of_range(self, tokens: int) -> None:
        payload = _valid_agent_config(max_output_tokens=tokens)

        with pytest.raises(ValidationError):
            AgentConfig(**payload)

    def test_missing_required_field_rejected(self) -> None:
        payload = _valid_agent_config()
        del payload["model"]

        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(**payload)

        assert "model" in str(exc_info.value)

    def test_nested_metadata_is_validated(self) -> None:
        payload = _valid_agent_config(metadata={"version": "v1.0.0"})

        # Missing required metadata fields (variant_name, created_at, etc.) must fail.
        with pytest.raises(ValidationError):
            AgentConfig(**payload)


class TestMergedAgentConfigExtraForbid:
    """AH-40 AC-6: ``MergedAgentConfig`` rejects stray ``generate_content_config``
    (or any other unknown key) so backfill misses fail loud at validation time."""

    def _flat_merged_payload(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "config_id": "ken_e_chatbot",
            "instruction": "You are KEN-E...",
            "model": "gemini-2.5-pro",
            "temperature": 0.7,
            "max_output_tokens": 2500,
            "customization_status": "default",
        }
        base.update(overrides)
        return base

    def test_flat_payload_validates(self) -> None:
        merged = MergedAgentConfig(**self._flat_merged_payload())

        assert merged.temperature == 0.7
        assert merged.max_output_tokens == 2500

    def test_nested_generate_content_config_is_rejected(self) -> None:
        payload = self._flat_merged_payload()
        payload["generate_content_config"] = {"temperature": 0.7}

        with pytest.raises(ValidationError) as exc_info:
            MergedAgentConfig(**payload)

        assert "generate_content_config" in str(exc_info.value)

    def test_arbitrary_extra_key_is_rejected(self) -> None:
        payload = self._flat_merged_payload(some_unexpected_key="x")

        with pytest.raises(ValidationError):
            MergedAgentConfig(**payload)


class TestAgentConfigOverlayUpdate:
    """AH-40 AC-5: overlay PUT body accepts ``max_output_tokens`` alongside
    ``temperature``."""

    def test_max_output_tokens_accepted(self) -> None:
        body = AgentConfigOverlayUpdate(temperature=0.5, max_output_tokens=4000)

        assert body.temperature == 0.5
        assert body.max_output_tokens == 4000

    @pytest.mark.parametrize("tokens", [99, 65536])
    def test_max_output_tokens_out_of_range(self, tokens: int) -> None:
        with pytest.raises(ValidationError):
            AgentConfigOverlayUpdate(max_output_tokens=tokens)


class TestAgentConfigMetadata:
    def test_defaults(self) -> None:
        metadata = AgentConfigMetadata(
            version="v2.0.0",
            variant_name="new_variant",
            created_at="2026-04-20T12:00:00+00:00",
            updated_at="2026-04-20T12:00:00+00:00",
            updated_by="alice@ken-e.ai",
        )

        assert metadata.experiment_id == "baseline"
        assert metadata.notes == ""


class TestAgentConfigUpdate:
    """Covers validator paths that ``test_agent_configs.py`` exercises at the
    router boundary. These tests re-verify the model in isolation (no HTTP)."""

    def test_partial_update_allowed(self) -> None:
        update = AgentConfigUpdate(
            instruction="x" * 20,
            updated_by="alice@ken-e.ai",
        )

        assert update.instruction == "x" * 20
        assert update.model is None
        assert update.temperature is None

    @pytest.mark.parametrize(
        "bad_email",
        ["notanemail", "alice@", "@ken-e.ai", "alice ken-e.ai"],
    )
    def test_updated_by_must_be_email(self, bad_email: str) -> None:
        with pytest.raises(ValidationError):
            AgentConfigUpdate(updated_by=bad_email)

    @pytest.mark.parametrize(
        "bad_version",
        ["1", "v1", "v1.0", "vA.B.C", "version1"],
    )
    def test_version_must_be_semver(self, bad_version: str) -> None:
        with pytest.raises(ValidationError):
            AgentConfigUpdate(updated_by="alice@ken-e.ai", version=bad_version)

    def test_version_normalization_adds_v_prefix(self) -> None:
        update = AgentConfigUpdate(updated_by="alice@ken-e.ai", version="1.2.3")

        assert update.version == "v1.2.3"

    def test_unknown_model_rejected_with_helpful_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigUpdate(updated_by="alice@ken-e.ai", model="gemini-99-ultra")

        # Error message should list supported Gemini models.
        assert "Supported Gemini models" in str(exc_info.value)

    @pytest.mark.parametrize("known_model", sorted(SUPPORTED_MODELS))
    def test_every_supported_model_is_accepted(self, known_model: str) -> None:
        update = AgentConfigUpdate(updated_by="alice@ken-e.ai", model=known_model)

        assert update.model == known_model


class TestConfigAuditEntry:
    """AC-7 / Sprint 6 Decision C: audit entries capture prev/new/timestamp/user."""

    def _valid_entry(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "action": "updated",
            "doc_type": "agent_config",
            "doc_id": "ken_e_chatbot",
            "user_id": "firebase-uid-123",
            "user_email": "alice@ken-e.ai",
            "timestamp": "2026-04-20T12:00:00+00:00",
            "request_id": "req-abc",
            "version_before": "v1.0.0",
            "version_after": "v1.0.1",
            "fields_changed": ["instruction", "temperature"],
            "changes": {
                "instruction": {"before": "old", "after": "new"},
                "temperature": {"before": 0.3, "after": 0.5},
            },
        }
        base.update(overrides)
        return base

    def test_round_trip(self) -> None:
        entry = ConfigAuditEntry(**self._valid_entry())

        dumped = entry.model_dump()
        assert dumped["action"] == "updated"
        assert dumped["fields_changed"] == ["instruction", "temperature"]
        assert dumped["changes"]["temperature"]["before"] == 0.3

    def test_creation_has_no_version_before(self) -> None:
        entry = ConfigAuditEntry(
            **self._valid_entry(action="created", version_before=None)
        )

        assert entry.version_before is None
        assert entry.version_after == "v1.0.1"

    def test_both_agent_and_mcp_doc_types_supported(self) -> None:
        for doc_type in ("agent_config", "mcp_server_config"):
            entry = ConfigAuditEntry(**self._valid_entry(doc_type=doc_type))
            assert entry.doc_type == doc_type

    def test_required_fields_enforced(self) -> None:
        payload = self._valid_entry()
        del payload["version_after"]

        with pytest.raises(ValidationError):
            ConfigAuditEntry(**payload)
