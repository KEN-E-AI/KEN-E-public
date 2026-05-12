"""Unit tests for migrate_news_agent_to_firestore.py (AH-41)."""

from __future__ import annotations

from unittest.mock import patch

from app.adk.agents.scripts import migrate_news_agent_to_firestore as script
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
    config = script.NEWS_AGENT_CONFIG
    # AH-41 decision matrix row for company_news_agent — uses Vertex AI
    # Search (no MCP toolset) so mcp_servers is empty.
    assert config["code_execution_enabled"] is False
    assert config["mcp_servers"] == []
    assert config["skill_ids"] == []
    assert config["sandbox_code_executor_enabled"] is False
    assert config["response_schema"] is None
    assert config["available_to_copy"] is True
    assert config["automatically_available"] is True
    assert config["visible_in_frontend"] is True


def test_config_dict_retains_pre_ah41_fields() -> None:
    config = script.NEWS_AGENT_CONFIG
    assert config["name"] == "company_news_agent"
    assert config["model"] == "gemini-2.5-pro"
    assert isinstance(config["instruction"], str) and config["instruction"]
    assert config["temperature"] == 0.7
    assert config["max_output_tokens"] == 4096
    assert config["metadata"]["version"] == "v1.1"  # bumped by AH-41


def test_upload_creates_doc_when_missing() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.NEWS_AGENT_CONFIG, "company_news_agent", "test-project"
        )
    assert ok is True
    doc = fake.get_doc("agent_configs", "company_news_agent")
    assert doc is not None
    for field in AUDIT_FIELDS:
        assert field in doc


def test_upload_is_idempotent_across_two_runs() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        script.upload_config_to_firestore(
            script.NEWS_AGENT_CONFIG, "company_news_agent", "test-project"
        )
        first_state = fake.get_doc("agent_configs", "company_news_agent")
        script.upload_config_to_firestore(
            script.NEWS_AGENT_CONFIG, "company_news_agent", "test-project"
        )
        second_state = fake.get_doc("agent_configs", "company_news_agent")
    assert first_state == second_state
