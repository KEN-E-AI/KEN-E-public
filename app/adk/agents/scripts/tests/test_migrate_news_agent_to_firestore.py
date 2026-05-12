"""Matrix snapshot tests for migrate_news_agent_to_firestore.py (AH-41)."""

from __future__ import annotations

from app.adk.agents.scripts import migrate_news_agent_to_firestore as script
from app.adk.agents.scripts._seed_helpers import AUDIT_FIELDS


def test_config_dict_matches_audit_matrix_row() -> None:
    """AH-41 decision matrix row for company_news_agent — uses Vertex AI
    Search (no MCP toolset) so mcp_servers stays empty."""
    config = script.NEWS_AGENT_CONFIG
    assert config["code_execution_enabled"] is False
    assert config["mcp_servers"] == []
    assert config["skill_ids"] == []
    assert config["sandbox_code_executor_enabled"] is False
    assert config["response_schema"] is None
    assert config["available_to_copy"] is True
    assert config["automatically_available"] is True
    assert config["visible_in_frontend"] is True


def test_config_dict_carries_all_eight_audit_fields() -> None:
    config = script.NEWS_AGENT_CONFIG
    for field in AUDIT_FIELDS:
        assert field in config


def test_config_dict_retains_pre_ah41_fields() -> None:
    config = script.NEWS_AGENT_CONFIG
    assert config["name"] == "company_news_agent"
    assert config["model"] == "gemini-2.5-pro"
    assert isinstance(config["instruction"], str) and config["instruction"]
    assert config["temperature"] == 0.7
    assert config["max_output_tokens"] == 4096
    assert "generate_content_config" not in config
    assert config["metadata"]["version"] == "v1.1"
