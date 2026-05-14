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
    MAX_TOOLS_PER_SPECIALIST,
    SUPPORTED_MODELS,
    AgentConfig,
    AgentConfigCreate,
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
        "name": "Dave",
        "title": "KEN-E Chatbot",
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
        assert dumped["name"] == "Dave"
        assert dumped["title"] == "KEN-E Chatbot"
        assert dumped["model"] == "gemini-2.5-pro"
        assert dumped["instruction"] == "You are KEN-E..."
        assert dumped["description"] == "Frontend-facing chat agent"
        assert dumped["temperature"] == 0.3
        assert dumped["max_output_tokens"] == 2500
        assert "generate_content_config" not in dumped
        assert dumped["metadata"]["version"] == "v1.0.0"

    def test_name_and_title_both_optional(self) -> None:
        """Identity fields are both optional on stored docs to keep legacy
        and in-migration docs loadable. ``config_id`` is the immutable
        identifier and lives on the Firestore document path, not on the
        validated model."""
        payload = _valid_agent_config()
        del payload["name"]
        del payload["title"]

        config = AgentConfig(**payload)

        assert config.name is None
        assert config.title is None

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

    def test_name_and_title_independently_editable(self) -> None:
        """Overlay PUT must support editing each identity field on its own."""
        only_name = AgentConfigOverlayUpdate(name="Dave")
        only_title = AgentConfigOverlayUpdate(title="Business Researcher")

        assert only_name.name == "Dave"
        assert only_name.title is None
        assert only_title.title == "Business Researcher"
        assert only_title.name is None


def _valid_create_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "title": "Business Researcher",
        "instruction": "You are a business researcher. Use tools as needed.",
        "model": "gemini-2.5-pro",
    }
    base.update(overrides)
    return base


class TestToolIds:
    """AH-PRD-06: per-agent tool_ids field on the four agent-config models."""

    def test_agent_config_defaults_tool_ids_to_none(self) -> None:
        config = AgentConfig(**_valid_agent_config())
        assert config.tool_ids is None

    def test_agent_config_accepts_explicit_tool_ids(self) -> None:
        config = AgentConfig(
            **_valid_agent_config(
                tool_ids=[
                    "google_analytics_mcp.list_ga_accounts",
                    "function.create_visualization",
                ]
            )
        )
        assert config.tool_ids == [
            "google_analytics_mcp.list_ga_accounts",
            "function.create_visualization",
        ]

    def test_agent_config_accepts_empty_list(self) -> None:
        # `[]` means "explicitly no tools" — distinct from `None` (legacy).
        config = AgentConfig(**_valid_agent_config(tool_ids=[]))
        assert config.tool_ids == []

    def test_create_accepts_none(self) -> None:
        body = AgentConfigCreate(**_valid_create_payload())
        assert body.tool_ids is None

    def test_create_accepts_valid_list(self) -> None:
        body = AgentConfigCreate(
            **_valid_create_payload(tool_ids=["function.create_visualization"])
        )
        assert body.tool_ids == ["function.create_visualization"]

    @pytest.mark.parametrize(
        "bad_id",
        [
            "noseparator",
            "Two.Capitals",
            "trailing.",
            ".leading",
            "double..dot",
            "spaces in.name",
        ],
    )
    def test_create_rejects_malformed_ids(self, bad_id: str) -> None:
        with pytest.raises(ValidationError, match="tool_ids"):
            AgentConfigCreate(**_valid_create_payload(tool_ids=[bad_id]))

    def test_create_rejects_duplicates(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate"):
            AgentConfigCreate(
                **_valid_create_payload(
                    tool_ids=[
                        "function.create_visualization",
                        "function.create_visualization",
                    ]
                )
            )

    def test_create_dedupes_triple_repeats_in_error_message(self) -> None:
        # Review item #7: ``["x", "x", "x"]`` previously reported
        # ``["x", "x"]`` because each repeat after the first appended to
        # the duplicate list. Now each duplicate ID is reported exactly once.
        with pytest.raises(ValidationError) as exc_info:
            AgentConfigCreate(
                **_valid_create_payload(
                    tool_ids=[
                        "function.create_visualization",
                        "function.create_visualization",
                        "function.create_visualization",
                    ]
                )
            )
        # The error message contains the deduped list.
        assert (
            str(exc_info.value).count("'function.create_visualization'") == 1
        )

    def test_create_rejects_over_cap(self) -> None:
        too_many = [f"server.tool_{i:02d}" for i in range(MAX_TOOLS_PER_SPECIALIST + 1)]
        with pytest.raises(ValidationError):
            AgentConfigCreate(**_valid_create_payload(tool_ids=too_many))

    def test_create_accepts_exactly_cap(self) -> None:
        at_cap = [f"server.tool_{i:02d}" for i in range(MAX_TOOLS_PER_SPECIALIST)]
        body = AgentConfigCreate(**_valid_create_payload(tool_ids=at_cap))
        assert body.tool_ids is not None
        assert len(body.tool_ids) == MAX_TOOLS_PER_SPECIALIST

    def test_overlay_update_accepts_none(self) -> None:
        # Sending `tool_ids=None` on the overlay clears any prior selection to
        # "legacy / no filter" semantics — distinct from `[]`.
        body = AgentConfigOverlayUpdate(tool_ids=None)
        assert body.tool_ids is None

    def test_overlay_update_accepts_empty_list(self) -> None:
        body = AgentConfigOverlayUpdate(tool_ids=[])
        assert body.tool_ids == []

    def test_overlay_update_rejects_per_id_over_limit(self) -> None:
        # Per-ID `max_length=80` on the Annotated[str] guard.
        long_id = "a" * 78 + ".x"  # 80 chars exactly is fine
        AgentConfigOverlayUpdate(tool_ids=[long_id])
        with pytest.raises(ValidationError):
            AgentConfigOverlayUpdate(tool_ids=["a" * 79 + ".x"])  # 81 chars

    def test_merged_config_passes_tool_ids_through(self) -> None:
        merged = MergedAgentConfig(
            config_id="custom_abc12345",
            instruction="You are helpful.",
            model="gemini-2.5-pro",
            tool_ids=["function.create_visualization"],
        )
        assert merged.tool_ids == ["function.create_visualization"]

    def test_merged_config_defaults_to_none(self) -> None:
        merged = MergedAgentConfig(
            config_id="custom_abc12345",
            instruction="You are helpful.",
            model="gemini-2.5-pro",
        )
        assert merged.tool_ids is None


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
