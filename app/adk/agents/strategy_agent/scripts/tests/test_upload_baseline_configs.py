"""Tests for upload_baseline_configs.py (AH-41).

Upsert / merge / idempotency / sparse-doc-warning behavior is tested
centrally on the shared helper (``test_seed_helpers.py``). This file
focuses on the script-specific concerns:

* The ``SEEDS`` registry covers all 8 strategy agents and obeys the
  decision matrix per agent class (researcher / formatter / business
  full baseline).
* End-to-end behavior wiring SEEDS → the shared helper → fake Firestore
  for one integration smoke (all 8 agents in one pass).
* The ``--agents`` CLI subset filter and unknown-agent rejection in
  ``main()``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.adk.agents.scripts._seed_helpers import (
    AUDIT_FIELDS,
    upsert_agent_config,
)
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient
from app.adk.agents.strategy_agent.scripts import upload_baseline_configs as script

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


# ---------------------------------------------------------------------------
# Matrix snapshot tests — SEEDS registry
# ---------------------------------------------------------------------------


def test_seeds_cover_all_eight_strategy_agents() -> None:
    assert set(script.SEEDS) == set(ALL_EIGHT_STRATEGY_AGENTS)


@pytest.mark.parametrize("agent_id", RESEARCHERS)
def test_researcher_audit_fields_match_matrix(agent_id: str) -> None:
    """AH-PRD-08: strategy-pipeline researchers use the hidden +
    non-copyable profile (matches the formatter discipline) because
    they are account-creation-only and picker-immutable."""
    seed = script.SEEDS[agent_id]
    assert seed["code_execution_enabled"] is False
    assert seed["mcp_servers"] == []
    assert seed["skill_ids"] == []
    assert seed["sandbox_code_executor_enabled"] is False
    assert seed["response_schema"] is None
    assert seed["available_to_copy"] is False
    assert seed["automatically_available"] is True
    assert seed["visible_in_frontend"] is False


@pytest.mark.parametrize("agent_id", FORMATTERS)
def test_formatter_audit_fields_match_matrix(agent_id: str) -> None:
    """Formatters are internal review-loop stages: hidden + non-copyable."""
    seed = script.SEEDS[agent_id]
    assert seed["code_execution_enabled"] is False
    assert seed["mcp_servers"] == []
    assert seed["skill_ids"] == []
    assert seed["sandbox_code_executor_enabled"] is False
    assert seed["response_schema"] is None
    assert seed["available_to_copy"] is False
    assert seed["automatically_available"] is True
    assert seed["visible_in_frontend"] is False


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
    """business_researcher and business_formatter retain the v1.0
    baseline so a clean env can bootstrap from this script."""
    for agent_id in ("business_researcher", "business_formatter"):
        seed = script.SEEDS[agent_id]
        assert "name" in seed
        assert "model" in seed
        assert "instruction" in seed
        assert "description" in seed
        assert "temperature" in seed
        assert "max_output_tokens" in seed
        assert "metadata" in seed
        # AH-40: flat shape; legacy nested wrapper gone.
        assert "generate_content_config" not in seed
        for field in AUDIT_FIELDS:
            assert field in seed


def test_business_researcher_uses_strategy_pipeline_profile() -> None:
    """AH-PRD-08: business_researcher (and its 3 siblings) are
    strategy-pipeline researchers — hidden + non-copyable."""
    seed = script.SEEDS["business_researcher"]
    assert seed["available_to_copy"] is False
    assert seed["visible_in_frontend"] is False


def test_business_formatter_uses_formatter_profile() -> None:
    seed = script.SEEDS["business_formatter"]
    assert seed["available_to_copy"] is False
    assert seed["visible_in_frontend"] is False


# ---------------------------------------------------------------------------
# Integration smoke — SEEDS → shared helper → fake Firestore
# ---------------------------------------------------------------------------


def test_all_eight_seeds_apply_idempotently_via_shared_helper() -> None:
    """Drive every SEEDS entry through the shared upsert helper twice
    and assert the resulting per-doc state is byte-identical between
    runs. Covers the SEEDS dict end-to-end without going through
    ``main()`` / arg parsing."""
    fake = FakeFirestoreClient()
    for agent_id in ALL_EIGHT_STRATEGY_AGENTS:
        upsert_agent_config(script.SEEDS[agent_id], agent_id, "test-project", db=fake)
    first = {a: fake.get_doc("agent_configs", a) for a in ALL_EIGHT_STRATEGY_AGENTS}

    for agent_id in ALL_EIGHT_STRATEGY_AGENTS:
        upsert_agent_config(script.SEEDS[agent_id], agent_id, "test-project", db=fake)
    second = {a: fake.get_doc("agent_configs", a) for a in ALL_EIGHT_STRATEGY_AGENTS}

    assert first == second


# ---------------------------------------------------------------------------
# main() — --agents subset + unknown-agent rejection
# ---------------------------------------------------------------------------


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
    # main() goes through upload_config_to_firestore → upsert_agent_config,
    # which instantiates a live firestore.Client. Patch at the lazy import
    # site inside the helper.
    from google.cloud import firestore

    with patch.object(firestore, "Client", return_value=fake):
        rc = script.main()
    assert rc == 0
    assert fake.get_doc("agent_configs", "brand_researcher") is not None
    assert fake.get_doc("agent_configs", "brand_formatter") is not None
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
