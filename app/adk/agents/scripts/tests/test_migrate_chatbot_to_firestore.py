"""Matrix snapshot tests for migrate_chatbot_to_firestore.py (AH-41).

The upsert / merge / idempotency / sparse-doc-warning behavior is tested
once on the shared helper in ``test_seed_helpers.py``. This file only
asserts the agent-specific ``KEN_E_CHATBOT_CONFIG`` dict matches the
AH-41 decision-matrix row.
"""

from __future__ import annotations

from app.adk.agents.scripts import migrate_chatbot_to_firestore as script
from app.adk.agents.scripts._seed_helpers import AUDIT_FIELDS


def test_config_dict_matches_audit_matrix_row() -> None:
    """AH-41 decision matrix row for ken_e_chatbot."""
    config = script.KEN_E_CHATBOT_CONFIG
    assert config["code_execution_enabled"] is False
    assert config["mcp_servers"] == []
    assert config["skill_ids"] == []
    assert config["sandbox_code_executor_enabled"] is False
    assert config["response_schema"] is None
    # Root orchestrator: visible (users chat with it) but NOT copyable.
    assert config["available_to_copy"] is False
    assert config["automatically_available"] is True
    assert config["visible_in_frontend"] is True


def test_config_dict_carries_all_eight_audit_fields() -> None:
    config = script.KEN_E_CHATBOT_CONFIG
    for field in AUDIT_FIELDS:
        assert field in config, f"audit field {field!r} missing from config dict"


def test_config_dict_retains_pre_ah41_fields() -> None:
    """Sanity: AH-41 must not regress fields that already existed."""
    config = script.KEN_E_CHATBOT_CONFIG
    assert config["name"] == "ken_e_chatbot"
    assert config["model"] == "gemini-2.5-pro"
    assert isinstance(config["instruction"], str) and config["instruction"]
    assert config["temperature"] == 0.7
    assert config["max_output_tokens"] == 4096
    # AH-40: flat shape; the legacy nested wrapper must be gone.
    assert "generate_content_config" not in config
    assert config["metadata"]["version"] == "v1.2"  # bumped by AH-41
