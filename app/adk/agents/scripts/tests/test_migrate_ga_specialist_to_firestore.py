"""Unit tests for migrate_ga_specialist_to_firestore.py (AH-25 / AH-PRD-03 Phase 1).

AH-149 (Phase 2): assertions updated to reflect the numerical_analyst split:
  - ``code_execution_enabled`` is now ``False`` (was ``True``).
  - ``model`` is now ``gemini-3.5-flash`` (was ``gemini-2.0-flash``, then ``gemini-2.5-flash``).
  - ``tool_ids`` is an explicit 6-item list (was ``None``; AH-140 added function.create_visualization).

Coverage map:
  (a) ``GA_SPECIALIST_CONFIG`` carries every ``AUDIT_FIELDS`` entry with the
      GA-specialist matrix-row values.
  (b) Required-by-PRD fields present: ``default_acceptance_criteria``
      (non-empty, survives ``sanitise_criteria()`` unchanged),
      ``ken_e_sub_agent=True``, explicit ``tool_ids`` list,
      ``reviewer_model=None``, ``code_execution_enabled=False``,
      ``name`` / ``title`` populated.
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
    """GA specialist matrix row: AH-149 — code_execution=False, mcp_servers=[ga_mcp], rest per researcher profile."""
    config = script.GA_SPECIALIST_CONFIG
    # AH-149: code execution moved to numerical_analyst leaf — must be False.
    assert config["code_execution_enabled"] is False
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

    # AH-149: code execution moved to numerical_analyst leaf — must be False on parent.
    assert config["code_execution_enabled"] is False, (
        "code_execution_enabled must be False (AH-149: execution in numerical_analyst leaf)"
    )

    # review-loop gate (AH-75 / AH-PRD-09) — non-empty string triggers LoopAgent wrap.
    assert "default_acceptance_criteria" in config
    criteria = config["default_acceptance_criteria"]
    assert isinstance(criteria, str) and criteria.strip(), (
        "default_acceptance_criteria must be a non-empty string"
    )

    # AH-149: explicit tool_ids list (4 live GA MCP tools + agent.numerical_analyst).
    # AH-140: added function.create_visualization — 6 entries total.
    tool_ids = config["tool_ids"]
    assert isinstance(tool_ids, list), "tool_ids must be a list (AH-149)"
    assert len(tool_ids) == 6, f"tool_ids must have 6 entries; got {len(tool_ids)}: {tool_ids}"
    assert "agent.numerical_analyst" in tool_ids, (
        "tool_ids must contain 'agent.numerical_analyst'"
    )
    assert "function.create_visualization" in tool_ids, (
        "tool_ids must contain 'function.create_visualization' (AH-140)"
    )
    ga_mcp_ids = [t for t in tool_ids if t.startswith("google_analytics_mcp.")]
    assert len(ga_mcp_ids) == 4, (
        f"tool_ids must contain 4 google_analytics_mcp.* entries; got {len(ga_mcp_ids)}"
    )

    # AH-92: None = DEFAULT_REVIEWER_MODEL.
    assert config["reviewer_model"] is None, "reviewer_model must be None"

    # AH-84: identity fields for the Available Specialists block.
    assert config["name"] == "Aria", "name must be 'Aria'"
    assert config["title"] == "Analytics Specialist", "title must be 'Analytics Specialist'"

    # Core fields — AH-149 bumped to gemini-2.5-flash; re-bumped to 3.5-flash
    # (GA 2026-05-19) to match the live staging/prod configs.
    assert config["model"] == "gemini-3.5-flash", (
        f"model must be 'gemini-3.5-flash'; got {config['model']!r}"
    )
    assert config["temperature"] == 0.2
    assert isinstance(config["instruction"], str) and config["instruction"].strip()
    assert isinstance(config["description"], str) and config["description"].strip()

    # AH-149: instruction must mention numerical_analyst delegation.
    assert "numerical_analyst" in config["instruction"], (
        "instruction must contain 'numerical_analyst' delegation guidance"
    )


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
    # AH-149: model bumped; code execution moved to numerical_analyst leaf.
    assert validated.model == "gemini-3.5-flash"
    assert validated.code_execution_enabled is False
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
    # AH-149: model bumped; code execution moved to numerical_analyst leaf.
    assert agent_doc["model"] == "gemini-3.5-flash"
    assert agent_doc["ken_e_sub_agent"] is True
    assert agent_doc["code_execution_enabled"] is False
    assert agent_doc["mcp_servers"] == ["google_analytics_mcp"]
    assert agent_doc["default_acceptance_criteria"] == script.GA_SPECIALIST_ACCEPTANCE_CRITERIA
    # AH-149: tool_ids is the explicit list; AH-140 added function.create_visualization (6 entries).
    tool_ids = agent_doc["tool_ids"]
    assert isinstance(tool_ids, list)
    assert len(tool_ids) == 6
    assert "agent.numerical_analyst" in tool_ids
    assert "function.create_visualization" in tool_ids


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


# ---------------------------------------------------------------------------
# AH-149 guardrail: seed tool_ids must resolve to real catalogue / live tools.
# ---------------------------------------------------------------------------
#
# Regression guard for the bug where the seed listed aspirational catalogue
# names (e.g. ``query_ga_report``) that matched NEITHER the catalogue NOR the
# live ``google_analytics_mcp`` server. Because a non-None ``tool_ids`` becomes
# an ADK ``McpToolset(tool_filter=...)`` matched on the LIVE tool name, a name
# that isn't served is silently dropped — the GA specialist would lose all GA
# tools at runtime. The live server (KEN-E-AI/mcp-google-analytics,
# simple_server.py) exposes exactly the four multi-tenant ``_mt`` tools below.

# The four live GA MCP tool names, mirrored from the deployed server. Keeping
# this list here makes a server/​catalogue rename a deliberate, reviewed edit.
_LIVE_GA_MCP_TOOLS = {
    "get_account_summaries_mt",
    "get_property_details_mt",
    "run_report_mt",
    "run_realtime_report_mt",
}


def _fresh_catalogue_registry() -> Any:
    """Load a fresh ToolRegistry from the canonical tools.yaml (no singleton)."""
    from pathlib import Path

    from app.adk.tools.registry import tool_registry as tr

    registry = tr.ToolRegistry()
    registry.load_from_config(Path(tr.__file__).parent / "config" / "tools.yaml")
    return registry


def test_ga_seed_tool_ids_subset_of_catalogue() -> None:
    """Every id in the seed must be resolvable at runtime:
    - ``google_analytics_mcp.*`` must be a catalogued GA tool.
    - ``agent.*`` must be a catalogued agent tool.
    - ``function.*`` must be registered in the function-tool registry.
    """
    import app.adk.tools.function_tools.create_visualization  # noqa: F401 — side-effect import
    from app.adk.tools.registry.function_tool_registry import (
        snapshot_function_tool_registry,
    )

    registry = _fresh_catalogue_registry()
    ga_catalogue = {
        t.name for t in registry.list_tools() if t.mcp_server == "google_analytics_mcp"
    }
    agent_catalogue = {t.name for t in registry.list_agent_tools()}
    function_catalogue = set(snapshot_function_tool_registry().keys())

    for tid in script._GA_MCP_TOOL_IDS:
        server, _, name = tid.partition(".")
        if server == "google_analytics_mcp":
            assert name in ga_catalogue, (
                f"seed tool_id {tid!r} is not in the google_analytics_mcp catalogue "
                f"{sorted(ga_catalogue)} — the runtime tool_filter would drop it"
            )
        elif server == "agent":
            assert name in agent_catalogue, (
                f"seed agent tool {tid!r} is not catalogued: {sorted(agent_catalogue)}"
            )
        elif server == "function":
            assert name in function_catalogue, (
                f"seed function tool {tid!r} is not in the function-tool registry "
                f"{sorted(function_catalogue)} — roster._filter_function_tools_by_ids "
                "would silently drop it"
            )
        else:  # pragma: no cover - defensive
            raise AssertionError(f"unexpected tool_id namespace in seed: {tid!r}")


def test_ga_catalogue_matches_live_mt_tools() -> None:
    """The ``google_analytics_mcp`` catalogue must equal the live server's tool
    set (the four ``_mt`` tools). Pins the catalogue to deployed reality so a
    future drift is a deliberate, reviewed change rather than a silent break."""
    registry = _fresh_catalogue_registry()
    ga_catalogue = {
        t.name for t in registry.list_tools() if t.mcp_server == "google_analytics_mcp"
    }
    assert ga_catalogue == _LIVE_GA_MCP_TOOLS, (
        f"tools.yaml google_analytics_mcp entries {sorted(ga_catalogue)} must match "
        f"the live server tools {sorted(_LIVE_GA_MCP_TOOLS)}"
    )
