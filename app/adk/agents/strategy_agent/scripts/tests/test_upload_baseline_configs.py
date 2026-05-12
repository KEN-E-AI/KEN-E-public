"""Unit tests for upload_baseline_configs.py (AH-41)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient
from app.adk.agents.strategy_agent.scripts import upload_baseline_configs as script

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

ALL_EIGHT_STRATEGY_AGENTS = (
    "business_researcher",
    "business_formatter",
    "competitive_researcher",
    "competitive_formatter",
    "marketing_researcher",
    "marketing_formatter",
    "brand_researcher",
    "brand_formatter",
)

RESEARCHERS = (
    "business_researcher",
    "competitive_researcher",
    "marketing_researcher",
    "brand_researcher",
)

FORMATTERS = (
    "business_formatter",
    "competitive_formatter",
    "marketing_formatter",
    "brand_formatter",
)


def test_seeds_cover_all_eight_strategy_agents() -> None:
    assert set(script.SEEDS) == set(ALL_EIGHT_STRATEGY_AGENTS)


@pytest.mark.parametrize("agent_id", RESEARCHERS)
def test_researcher_audit_fields_match_matrix(agent_id: str) -> None:
    seed = script.SEEDS[agent_id]
    assert seed["code_execution_enabled"] is False
    assert seed["mcp_servers"] == []
    assert seed["skill_ids"] == []
    assert seed["sandbox_code_executor_enabled"] is False
    assert seed["response_schema"] is None
    assert seed["available_to_copy"] is True
    assert seed["automatically_available"] is True
    assert seed["visible_in_frontend"] is True


@pytest.mark.parametrize("agent_id", FORMATTERS)
def test_formatter_audit_fields_match_matrix(agent_id: str) -> None:
    """Formatters are internal review-loop stages: hidden + non-copyable."""
    seed = script.SEEDS[agent_id]
    assert seed["code_execution_enabled"] is False
    assert seed["mcp_servers"] == []
    assert seed["skill_ids"] == []
    assert seed["sandbox_code_executor_enabled"] is False
    assert seed["response_schema"] is None
    assert seed["available_to_copy"] is False  # not forkable
    assert seed["automatically_available"] is True
    assert seed["visible_in_frontend"] is False  # hidden from UI


@pytest.mark.parametrize(
    "agent_id",
    [
        "competitive_researcher",
        "competitive_formatter",
        "marketing_researcher",
        "marketing_formatter",
        "brand_researcher",
        "brand_formatter",
    ],
)
def test_strategy_agents_seed_only_audit_fields(agent_id: str) -> None:
    """The six strategy agents that lack a baseline seed write only the
    eight audited fields — live content is preserved by merge=True."""
    seed = script.SEEDS[agent_id]
    assert set(seed.keys()) == set(AUDIT_FIELDS)


def test_business_agents_carry_full_baseline_plus_audit_fields() -> None:
    """business_researcher and business_formatter retain the v1.0 baseline
    so a clean environment can bootstrap from this script."""
    for agent_id in ("business_researcher", "business_formatter"):
        seed = script.SEEDS[agent_id]
        # Baseline fields (pre-AH-41).
        assert "name" in seed
        assert "model" in seed
        assert "instruction" in seed
        assert "description" in seed
        assert "temperature" in seed
        assert "max_output_tokens" in seed
        assert "metadata" in seed
        # AH-40: flat shape, not nested under generate_content_config.
        assert "generate_content_config" not in seed
        # AH-41 audit fields layered on.
        for field in AUDIT_FIELDS:
            assert field in seed


def test_business_researcher_uses_researcher_profile() -> None:
    seed = script.SEEDS["business_researcher"]
    assert seed["available_to_copy"] is True
    assert seed["visible_in_frontend"] is True


def test_business_formatter_uses_formatter_profile() -> None:
    seed = script.SEEDS["business_formatter"]
    assert seed["available_to_copy"] is False  # hidden + non-copyable
    assert seed["visible_in_frontend"] is False


def test_upload_creates_strategy_agent_doc_with_only_audit_fields() -> None:
    """A clean env writes a sparse doc — only audit fields."""
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.SEEDS["competitive_researcher"],
            "competitive_researcher",
            "test-project",
        )
    assert ok is True
    doc = fake.get_doc("agent_configs", "competitive_researcher")
    assert doc is not None
    assert set(doc.keys()) == set(AUDIT_FIELDS)


def test_upload_merges_audit_fields_onto_existing_strategy_agent() -> None:
    """The realistic case: live env has the full doc but lacks audit
    fields. After seed, audit fields are present and instruction/model/
    temperature/etc. are preserved by merge=True."""
    fake = FakeFirestoreClient(
        stores={
            "agent_configs": {
                "competitive_researcher": {
                    "name": "competitive_researcher",
                    "model": "gemini-2.0-flash",
                    "instruction": "live hand-tuned instruction",
                    "description": "Researches competitors",
                    "temperature": 0.3,
                    "max_output_tokens": 2500,
                    "metadata": {"version": "v1.0.0"},
                }
            }
        }
    )
    with patch.object(script.firestore, "Client", return_value=fake):
        ok = script.upload_config_to_firestore(
            script.SEEDS["competitive_researcher"],
            "competitive_researcher",
            "test-project",
        )
    assert ok is True
    doc = fake.get_doc("agent_configs", "competitive_researcher")
    assert doc is not None
    # Audit fields added.
    for field in AUDIT_FIELDS:
        assert field in doc
    # Live content preserved.
    assert doc["instruction"] == "live hand-tuned instruction"
    assert doc["model"] == "gemini-2.0-flash"
    assert doc["temperature"] == 0.3
    assert doc["metadata"] == {"version": "v1.0.0"}


def test_idempotent_across_two_runs() -> None:
    fake = FakeFirestoreClient()
    with patch.object(script.firestore, "Client", return_value=fake):
        for agent_id in ALL_EIGHT_STRATEGY_AGENTS:
            script.upload_config_to_firestore(
                script.SEEDS[agent_id], agent_id, "test-project"
            )
        first = {a: fake.get_doc("agent_configs", a) for a in ALL_EIGHT_STRATEGY_AGENTS}
        for agent_id in ALL_EIGHT_STRATEGY_AGENTS:
            script.upload_config_to_firestore(
                script.SEEDS[agent_id], agent_id, "test-project"
            )
        second = {a: fake.get_doc("agent_configs", a) for a in ALL_EIGHT_STRATEGY_AGENTS}
    assert first == second


def test_main_subset_via_agents_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--agents flag scopes the seed to a subset of doc_ids."""
    fake = FakeFirestoreClient()
    monkeypatch.setattr(
        "sys.argv",
        [
            "upload_baseline_configs.py",
            "--project-id",
            "test-project",
            "--agents",
            "brand_researcher,brand_formatter",
        ],
    )
    with patch.object(script.firestore, "Client", return_value=fake):
        rc = script.main()
    assert rc == 0
    assert fake.get_doc("agent_configs", "brand_researcher") is not None
    assert fake.get_doc("agent_configs", "brand_formatter") is not None
    # Other agents NOT seeded.
    for agent_id in ALL_EIGHT_STRATEGY_AGENTS:
        if agent_id in ("brand_researcher", "brand_formatter"):
            continue
        assert fake.get_doc("agent_configs", agent_id) is None


def test_main_rejects_unknown_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "upload_baseline_configs.py",
            "--project-id",
            "test-project",
            "--agents",
            "bogus_agent",
        ],
    )
    rc = script.main()
    assert rc == 1
