"""Unit tests for migrate_chatbot_to_firestore.py (AH-41)."""

from __future__ import annotations

from unittest.mock import patch

from app.adk.agents.scripts import migrate_chatbot_to_firestore as script
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

AUDIT_FIELDS = (
    "code_execution_enabled",
    "mcp_servers",
    "skill_ids",
    "sandbox_code_executor_enabled",
    "response_schema",
    "available_to_copy",
    "automatically_available",
    "visible_in_frontend",
)


def test_config_dict_has_all_audited_fields_per_matrix() -> None:
    config = script.KEN_E_CHATBOT_CONFIG
    # AH-41 decision matrix row for ken_e_chatbot.
    assert config["code_execution_enabled"] is False
    assert config["mcp_servers"] == []
    assert config["skill_ids"] == []
    assert config["sandbox_code_executor_enabled"] is False
    assert config["response_schema"] is None
    assert config["available_to_copy"] is False  # orchestrator: not forkable
    assert config["automatically_available"] is True
    assert config["visible_in_frontend"] is True


def test_config_dict_retains_pre_ah41_fields() -> None:
    """AH-41 must not regress fields that already exist on the doc."""
    config = script.KEN_E_CHATBOT_CONFIG
    assert config["name"] == "ken_e_chatbot"
    assert config["model"] == "gemini-2.5-pro"
    assert isinstance(config["instruction"], str) and config["instruction"]
    assert config["temperature"] == 0.7
    assert config["max_output_tokens"] == 4096
    assert config["metadata"]["version"] == "v1.2"  # bumped by AH-41


def test_upload_creates_doc_when_missing() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project"
        )
    assert ok is True
    doc = fake.get_doc("agent_configs", "ken_e_chatbot")
    assert doc is not None
    for field in AUDIT_FIELDS:
        assert field in doc, f"audit field {field!r} missing post-upsert"


def test_upload_merges_into_existing_doc_preserving_extra_fields() -> None:
    fake = FakeFirestoreClient(
        stores={
            "agent_configs": {
                "ken_e_chatbot": {
                    "name": "ken_e_chatbot",
                    "model": "gemini-2.0-flash",  # legacy live value
                    "instruction": "legacy instruction",
                    "temperature": 0.5,  # different from seed
                    "an_extra_field_added_via_admin_ui": "value",
                }
            }
        }
    )
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project"
        )
    assert ok is True
    doc = fake.get_doc("agent_configs", "ken_e_chatbot")
    assert doc is not None
    # New fields landed
    for field in AUDIT_FIELDS:
        assert field in doc
    # Seed overrides instruction/temperature etc. — they're in the
    # seed dict so merge=True writes them.
    assert doc["temperature"] == 0.7
    assert doc["model"] == "gemini-2.5-pro"
    # Field added out-of-band (not in seed dict) is preserved.
    assert doc["an_extra_field_added_via_admin_ui"] == "value"


def test_upload_is_idempotent_across_two_runs() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project"
        )
        first_state = fake.get_doc("agent_configs", "ken_e_chatbot")
        script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project"
        )
        second_state = fake.get_doc("agent_configs", "ken_e_chatbot")
    assert first_state == second_state


def test_dry_run_does_not_write() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project", dry_run=True
        )
    assert ok is True
    assert fake.get_doc("agent_configs", "ken_e_chatbot") is None


def test_upload_returns_false_on_firestore_error() -> None:
    with patch.object(
        script.firestore, "Client", side_effect=RuntimeError("boom")
    ):
        ok = script.upload_config_to_firestore(
            script.KEN_E_CHATBOT_CONFIG, "ken_e_chatbot", "test-project"
        )
    assert ok is False
