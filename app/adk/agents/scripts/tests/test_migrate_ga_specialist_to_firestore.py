"""Unit tests for migrate_ga_specialist_to_firestore.py (AH-25 / AH-PRD-03 Phase 1).

Coverage map:
  (a) ``GA_SPECIALIST_CONFIG`` carries every ``AUDIT_FIELDS`` entry with the
      GA-specialist matrix-row values.
  (b) Required-by-PRD fields present: ``default_acceptance_criteria``
      (non-empty, survives ``sanitise_criteria()`` unchanged),
      ``ken_e_sub_agent=True``, ``tool_ids=None``, ``reviewer_model=None``,
      ``code_execution_enabled=True``, ``name`` / ``title`` populated.
  (c) ``MergedAgentConfig.model_validate(stripped_dict)`` succeeds — the seed
      conforms to the runtime schema under ``extra="forbid"``.
  (d) End-to-end idempotency: run ``main()`` twice against a
      ``FakeFirestoreClient``; the store state is byte-equal after both runs,
      including the ``kind`` field on the MCP doc.
  (e) MCP ``kind`` patch behaviour — table-driven:
        missing key   → "cloud_run"
        kind=None     → "cloud_run"
        kind=""       → "cloud_run"
        kind="cloud_run" → unchanged
        kind="zapier"    → unchanged
  (f) ``--dry-run`` returns 0 without constructing a real Firestore client.
"""

from __future__ import annotations

import copy
import sys
from typing import Any
from unittest.mock import patch

import pytest

from app.adk.agents.scripts import migrate_ga_specialist_to_firestore as script
from app.adk.agents.scripts._seed_helpers import AUDIT_FIELDS
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

# ---------------------------------------------------------------------------
# (a) Audit-matrix conformance
# ---------------------------------------------------------------------------


def test_config_carries_all_audit_fields() -> None:
    """Every field in AUDIT_FIELDS must be present in GA_SPECIALIST_CONFIG."""
    config = script.GA_SPECIALIST_CONFIG
    for field in AUDIT_FIELDS:
        assert field in config, f"audit field {field!r} missing from GA_SPECIALIST_CONFIG"


def test_config_matches_ga_specialist_audit_matrix_row() -> None:
    """GA specialist matrix row: code_execution=True, mcp_servers=[ga_mcp], rest per researcher profile."""
    config = script.GA_SPECIALIST_CONFIG
    assert config["code_execution_enabled"] is True
    assert config["mcp_servers"] == ["google_analytics_mcp"]
    assert config["skill_ids"] == []
    assert config["sandbox_code_executor_enabled"] is False
    assert config["response_schema"] is None
    assert config["available_to_copy"] is True
    assert config["automatically_available"] is True
    assert config["visible_in_frontend"] is True


# ---------------------------------------------------------------------------
# (b) PRD-required fields
# ---------------------------------------------------------------------------


def test_prd_required_fields_present() -> None:
    """Fields required by AH-PRD-03 §4 must be explicitly set."""
    config = script.GA_SPECIALIST_CONFIG

    # Delegation gate (AH-82) — must be explicitly True.
    assert config["ken_e_sub_agent"] is True, "ken_e_sub_agent must be True"

    # Code-execution gate (AH-PRD-03 §4).
    assert config["code_execution_enabled"] is True, "code_execution_enabled must be True"

    # review-loop gate (AH-75 / AH-PRD-09) — non-empty string triggers LoopAgent wrap.
    assert "default_acceptance_criteria" in config
    criteria = config["default_acceptance_criteria"]
    assert isinstance(criteria, str) and criteria.strip(), (
        "default_acceptance_criteria must be a non-empty string"
    )

    # AH-PRD-06: None = all tools from google_analytics_mcp.
    assert config["tool_ids"] is None, "tool_ids must be None (all tools)"

    # AH-92: None = DEFAULT_REVIEWER_MODEL.
    assert config["reviewer_model"] is None, "reviewer_model must be None"

    # AH-84: identity fields for the Available Specialists block.
    assert config["name"] == "Aria", "name must be 'Aria'"
    assert config["title"] == "Analytics Specialist", "title must be 'Analytics Specialist'"

    # Core fields.
    assert config["model"] == "gemini-2.0-flash"
    assert config["temperature"] == 0.2
    assert isinstance(config["instruction"], str) and config["instruction"].strip()
    assert isinstance(config["description"], str) and config["description"].strip()


def test_acceptance_criteria_survives_sanitisation() -> None:
    """GA_SPECIALIST_ACCEPTANCE_CRITERIA must survive sanitise_criteria unchanged.

    What is stored in Firestore must equal what the LLM reviewer actually sees
    in its prompt (no silent mutation by the sanitiser).
    """
    from app.adk.agents.utils.criteria_utils import sanitise_criteria

    raw = script.GA_SPECIALIST_ACCEPTANCE_CRITERIA
    assert sanitise_criteria(raw) == raw, (
        "GA_SPECIALIST_ACCEPTANCE_CRITERIA contains characters that sanitise_criteria modifies; "
        "use only ASCII-safe characters"
    )


def test_acceptance_criteria_under_max_chars() -> None:
    """GA_SPECIALIST_ACCEPTANCE_CRITERIA must be within the MAX_CRITERIA_CHARS hard cap."""
    from app.adk.agents.utils.criteria_utils import MAX_CRITERIA_CHARS

    raw = script.GA_SPECIALIST_ACCEPTANCE_CRITERIA
    assert len(raw) <= MAX_CRITERIA_CHARS, (
        f"GA_SPECIALIST_ACCEPTANCE_CRITERIA is {len(raw)} chars; "
        f"MAX_CRITERIA_CHARS={MAX_CRITERIA_CHARS}"
    )


# ---------------------------------------------------------------------------
# (c) Schema validation against MergedAgentConfig
# ---------------------------------------------------------------------------


def _strip_storage_internal(config: dict[str, Any]) -> dict[str, Any]:
    """Strip fields that config_loader._STORAGE_INTERNAL_FIELDS removes before validation."""
    from app.adk.agents.agent_factory.config_loader import _STORAGE_INTERNAL_FIELDS

    stripped = dict(config)
    # metadata is not in _STORAGE_INTERNAL_FIELDS (factory wants it) but is not in
    # MergedAgentConfig either — strip it so model_validate does not fail.
    stripped.pop("metadata", None)
    for field in _STORAGE_INTERNAL_FIELDS:
        stripped.pop(field, None)
    return stripped


def test_config_validates_against_merged_agent_config() -> None:
    """MergedAgentConfig.model_validate must succeed on the stripped seed dict.

    MergedAgentConfig uses ``extra="forbid"`` (AH-40), so any field not in the
    schema — including a typo'd key or a new field the model no longer carries
    — will fail here and surface at CI time rather than at runtime.
    """
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

    stripped = _strip_storage_internal(script.GA_SPECIALIST_CONFIG)
    # Should not raise.
    validated = MergedAgentConfig.model_validate(stripped)
    assert validated.model == "gemini-2.0-flash"
    assert validated.code_execution_enabled is True
    assert validated.ken_e_sub_agent is True
    assert validated.default_acceptance_criteria == script.GA_SPECIALIST_ACCEPTANCE_CRITERIA


# ---------------------------------------------------------------------------
# (d) End-to-end idempotency
# ---------------------------------------------------------------------------


def _build_fake_db_with_existing_mcp(kind: str | None = "cloud_run") -> FakeFirestoreClient:
    """Return a FakeFirestoreClient pre-seeded with the AH-PRD-09 Phase 3 backfilled MCP doc."""
    stores: dict[str, dict[str, Any]] = {}
    if kind is not None:
        stores[script.MCP_COLLECTION] = {
            script.MCP_DOC_ID: {
                "description": "Google Analytics 4 data access",
                "category": "analytics",
                "enabled": True,
                "kind": kind,
            }
        }
    else:
        # Doc exists but kind key is absent.
        stores[script.MCP_COLLECTION] = {
            script.MCP_DOC_ID: {
                "description": "Google Analytics 4 data access",
                "category": "analytics",
                "enabled": True,
            }
        }
    return FakeFirestoreClient(stores=stores)


def _run_main_with_fake_db(
    monkeypatch: pytest.MonkeyPatch,
    fake_db: FakeFirestoreClient,
) -> int:
    """Invoke ``main()`` with ``--project-id ken-e-dev`` against *fake_db*.

    Patches ``google.cloud.firestore.Client`` at the module level so both
    ``upsert_agent_config`` (via ``_seed_helpers``) and ``upsert_mcp_patch``
    receive the same ``FakeFirestoreClient`` instance.
    """
    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-dev"])
    with patch("google.cloud.firestore.Client", return_value=fake_db):
        return script.main()


def test_idempotency_two_runs_produce_same_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main() twice must leave Firestore in the same state as running it once.

    Covers AH-25 AC: «Migration script is idempotent — running twice produces
    identical Firestore state».
    """
    fake_db = _build_fake_db_with_existing_mcp(kind="cloud_run")

    # First run.
    result1 = _run_main_with_fake_db(monkeypatch, fake_db)
    assert result1 == 0, "First run must exit 0"

    # Capture store state after first run.
    state_after_first: dict[str, Any] = {
        "agent_configs": copy.deepcopy(
            fake_db._stores.get("agent_configs", {})
        ),
        script.MCP_COLLECTION: copy.deepcopy(
            fake_db._stores.get(script.MCP_COLLECTION, {})
        ),
    }

    # Second run — must not raise and must leave state byte-equal.
    result2 = _run_main_with_fake_db(monkeypatch, fake_db)
    assert result2 == 0, "Second run must exit 0"

    state_after_second: dict[str, Any] = {
        "agent_configs": copy.deepcopy(
            fake_db._stores.get("agent_configs", {})
        ),
        script.MCP_COLLECTION: copy.deepcopy(
            fake_db._stores.get(script.MCP_COLLECTION, {})
        ),
    }

    # Strip datetime fields (metadata.created_at / updated_at) before comparing
    # because datetime.now() changes between the two calls.
    def _strip_datetime_fields(state: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)
        agent_doc = state.get("agent_configs", {}).get("google_analytics_specialist", {})
        if "metadata" in agent_doc:
            agent_doc["metadata"].pop("created_at", None)
            agent_doc["metadata"].pop("updated_at", None)
        return state

    assert _strip_datetime_fields(state_after_first) == _strip_datetime_fields(
        state_after_second
    ), "Firestore state must be identical after first and second run"


def test_idempotency_agent_doc_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() must write agent_configs/google_analytics_specialist."""
    fake_db = _build_fake_db_with_existing_mcp()

    _run_main_with_fake_db(monkeypatch, fake_db)

    agent_doc = fake_db.get_doc("agent_configs", "google_analytics_specialist")
    assert agent_doc is not None, "agent_configs/google_analytics_specialist must be written"
    assert agent_doc["model"] == "gemini-2.0-flash"
    assert agent_doc["ken_e_sub_agent"] is True
    assert agent_doc["code_execution_enabled"] is True
    assert agent_doc["mcp_servers"] == ["google_analytics_mcp"]
    assert agent_doc["default_acceptance_criteria"] == script.GA_SPECIALIST_ACCEPTANCE_CRITERIA


def test_idempotency_mcp_kind_preserved_when_cloud_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kind='cloud_run' must be preserved (not overwritten) by the MCP patch."""
    fake_db = _build_fake_db_with_existing_mcp(kind="cloud_run")
    _run_main_with_fake_db(monkeypatch, fake_db)

    mcp_doc = fake_db.get_doc(script.MCP_COLLECTION, script.MCP_DOC_ID)
    assert mcp_doc is not None
    assert mcp_doc["kind"] == "cloud_run"


# ---------------------------------------------------------------------------
# (e) MCP kind patch behaviour — table-driven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "initial_kind, expected_kind, description",
    [
        (None, "cloud_run", "kind key absent -> set to cloud_run"),
        ("", "cloud_run", "kind='' -> set to cloud_run"),
        ("cloud_run", "cloud_run", "kind='cloud_run' -> unchanged"),
        ("zapier", "zapier", "kind='zapier' -> unchanged"),
        ("unknown_value", "cloud_run", "unrecognised kind -> overwritten with cloud_run"),
    ],
)
def test_mcp_kind_patch_behaviour(
    initial_kind: str | None,
    expected_kind: str,
    description: str,
) -> None:
    """_needs_kind_backfill + upsert_mcp_patch must implement the documented patch rules."""
    # Build an existing MCP doc with the specified kind value.
    existing_doc: dict[str, Any] = {
        "description": "GA MCP server",
        "enabled": True,
    }
    if initial_kind is not None:
        # None tests the "key absent" case - do not add the key at all.
        existing_doc["kind"] = initial_kind

    fake_db = FakeFirestoreClient(
        stores={
            script.MCP_COLLECTION: {
                script.MCP_DOC_ID: existing_doc,
            }
        }
    )

    with patch("google.cloud.firestore.Client", return_value=fake_db):
        ok = script.upsert_mcp_patch(project_id="ken-e-dev", db=fake_db)

    assert ok is True, f"upsert_mcp_patch must return True for: {description}"

    mcp_doc = fake_db.get_doc(script.MCP_COLLECTION, script.MCP_DOC_ID)
    assert mcp_doc is not None
    assert mcp_doc["kind"] == expected_kind, (
        f"{description}: expected kind={expected_kind!r}, got {mcp_doc['kind']!r}"
    )
    # Other fields must always be written.
    assert mcp_doc["specialist_categories"] == ["analytics"]
    assert mcp_doc["auth_type"] == "ga_oauth"
    assert mcp_doc["enabled"] is True


# ---------------------------------------------------------------------------
# (f) --dry-run exits 0 without constructing a real Firestore client
# ---------------------------------------------------------------------------


def test_dry_run_returns_zero_without_real_firestore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--dry-run must short-circuit before any real Firestore Client construction."""
    monkeypatch.setattr(
        sys, "argv", ["script", "--project-id", "ken-e-dev", "--dry-run"]
    )

    firestore_calls: list[bool] = []

    def _never_called(*args: object, **kwargs: object) -> None:
        firestore_calls.append(True)
        raise AssertionError(
            "google.cloud.firestore.Client must not be constructed in --dry-run mode"
        )

    with patch("google.cloud.firestore.Client", side_effect=_never_called):
        result = script.main()

    assert result == 0, "--dry-run must return 0"
    assert firestore_calls == [], "Firestore client must not be constructed in --dry-run"
