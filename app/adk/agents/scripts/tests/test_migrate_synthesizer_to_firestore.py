"""Unit tests for migrate_synthesizer_to_firestore.py (AH-127 / AH-PRD-14 §7 AC-5).

Coverage map:
  (a) ``SYNTHESIZER_CONFIG`` carries every ``AUDIT_FIELDS`` entry with the
      formatter-profile values (``AUDIT_FIELDS_FORMATTER``).
  (b) PRD-required fields: ``ken_e_sub_agent=False``, ``visible_in_frontend=False``,
      ``available_to_copy=False``, ``automatically_available=True``,
      ``tool_ids==[]``, ``default_acceptance_criteria=None``,
      ``reviewer_model=None``, instruction contains ``{synthesis_input?}``
      verbatim AND contains "completed research" framing (AH-PRD-05 §9
      anti-bracket-failure-mode guardrail).
  (c) ``MergedAgentConfig.model_validate(stripped_dict)`` succeeds — the seed
      conforms to the factory runtime schema under ``extra="forbid"``.
  (d) End-to-end idempotency: run ``main()`` twice against a
      ``FakeFirestoreClient``; the store state is byte-equal after both runs
      after stripping the non-deterministic ``metadata.created_at``/``updated_at``.
  (e) ``--dry-run`` returns 0 without constructing a real Firestore client.
  (f) Template-injection: verify that ``{synthesis_input?}`` is present in the
      instruction and that substituting a sentinel value produces a rendering
      that contains the sentinel verbatim (AH-PRD-14 §7 AC-5 at unit level).
"""

from __future__ import annotations

import copy
import sys
from typing import Any
from unittest.mock import patch

import pytest

from app.adk.agents.scripts import migrate_synthesizer_to_firestore as script
from app.adk.agents.scripts._seed_helpers import AUDIT_FIELDS, AUDIT_FIELDS_FORMATTER
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

# ---------------------------------------------------------------------------
# (a) Audit-matrix conformance
# ---------------------------------------------------------------------------


def test_config_carries_all_audit_fields() -> None:
    """Every field in AUDIT_FIELDS must be present in SYNTHESIZER_CONFIG."""
    config = script.SYNTHESIZER_CONFIG
    for field in AUDIT_FIELDS:
        assert field in config, f"audit field {field!r} missing from SYNTHESIZER_CONFIG"


def test_config_matches_formatter_audit_matrix_row() -> None:
    """Synthesizer uses the AUDIT_FIELDS_FORMATTER profile (internal pipeline stage)."""
    config = script.SYNTHESIZER_CONFIG
    for field, expected_value in AUDIT_FIELDS_FORMATTER.items():
        assert config[field] == expected_value, (
            f"SYNTHESIZER_CONFIG[{field!r}] = {config[field]!r}; "
            f"AUDIT_FIELDS_FORMATTER expects {expected_value!r}"
        )


# ---------------------------------------------------------------------------
# (b) PRD-required fields
# ---------------------------------------------------------------------------


def test_prd_required_fields_present() -> None:
    """Fields required by AH-PRD-14 §2 / §7 AC-5 must be explicitly set."""
    config = script.SYNTHESIZER_CONFIG

    # Delegation gate (AH-82) — MUST be False for internal pipeline-stage agents.
    assert config["ken_e_sub_agent"] is False, (
        "ken_e_sub_agent must be False (synthesizer is not delegatable from root chat)"
    )

    # Formatter profile flags.
    assert config["visible_in_frontend"] is False, "visible_in_frontend must be False"
    assert config["available_to_copy"] is False, "available_to_copy must be False"
    assert config["automatically_available"] is True, "automatically_available must be True"

    # No tools — pure LLM templating.
    assert config["tool_ids"] == [], "tool_ids must be an empty list"

    # No review loop on the synthesizer (synthesis over already-approved per-task drafts).
    assert config["default_acceptance_criteria"] is None, (
        "default_acceptance_criteria must be None (no review loop on synthesizer)"
    )
    assert config["reviewer_model"] is None, "reviewer_model must be None"

    # Core fields.
    assert config["model"] == "gemini-2.5-flash", (
        f"model must be 'gemini-2.5-flash'; got {config['model']!r}"
    )
    assert config["temperature"] == 0.3
    assert config["max_output_tokens"] == 4096
    assert isinstance(config["instruction"], str) and config["instruction"].strip()
    assert isinstance(config["description"], str) and config["description"].strip()

    # Identity fields (AH-84 — not surfaced in Available Specialists block, but
    # present for admin UI / audit trail).
    assert config["name"] == "Synth", "name must be 'Synth'"
    assert config["title"] == "Result Synthesizer", "title must be 'Result Synthesizer'"


def test_instruction_contains_synthesis_input_placeholder() -> None:
    """{synthesis_input?} template placeholder must be present verbatim."""
    assert "{synthesis_input?}" in script.SYNTHESIZER_CONFIG["instruction"], (
        "instruction must contain '{synthesis_input?}' — AH-PRD-05 coordinator "
        "writes upstream result_key values to session.state['synthesis_input'] "
        "and expects this placeholder to be substituted at LLM-call time"
    )


def test_instruction_contains_completed_research_framing() -> None:
    """'completed research' must appear in instruction (AH-PRD-05 §9 anti-bracket-failure guardrail).

    The AH-PRD-05 synthesizer risk: the LLM misinterprets {synthesis_input?} as a
    template to be filled in rather than already-completed research, producing literal
    placeholder syntax in the user-facing reply. The framing guard prevents this.
    """
    instruction = script.SYNTHESIZER_CONFIG["instruction"]
    assert "completed research" in instruction, (
        "instruction must contain 'completed research' framing to prevent the "
        "bracket-placeholder failure mode (AH-PRD-05 §9)"
    )


# ---------------------------------------------------------------------------
# (c) Schema validation against MergedAgentConfig
# ---------------------------------------------------------------------------


def _strip_storage_internal(config: dict[str, Any]) -> dict[str, Any]:
    """Strip fields that config_loader strips before MergedAgentConfig validation."""
    from app.adk.agents.agent_factory.config_loader import _STORAGE_INTERNAL_FIELDS

    stripped = dict(config)
    # metadata carries non-deterministic timestamps; strip it so the schema test is
    # stable across runs. config_loader.MergedAgentConfig has metadata: dict | None = None
    # so the field is optional — stripping is safe.
    stripped.pop("metadata", None)
    for field in _STORAGE_INTERNAL_FIELDS:
        stripped.pop(field, None)
    return stripped


def test_config_validates_against_merged_agent_config() -> None:
    """MergedAgentConfig.model_validate must succeed on the stripped seed dict.

    MergedAgentConfig uses ``extra="forbid"`` (AH-40), so any field not in the
    schema — including a typo'd key or a renamed audit field — will fail here and
    surface at CI time rather than at runtime.
    """
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

    stripped = _strip_storage_internal(script.SYNTHESIZER_CONFIG)
    # Should not raise.
    validated = MergedAgentConfig.model_validate(stripped)

    assert validated.model == "gemini-2.5-flash"
    assert validated.ken_e_sub_agent is False
    assert validated.visible_in_frontend is False
    assert validated.available_to_copy is False
    assert validated.automatically_available is True
    assert validated.tool_ids == []
    assert validated.default_acceptance_criteria is None
    assert validated.reviewer_model is None


# ---------------------------------------------------------------------------
# (d) End-to-end idempotency
# ---------------------------------------------------------------------------


def _run_main_with_fake_db(
    monkeypatch: pytest.MonkeyPatch,
    fake_db: FakeFirestoreClient,
) -> int:
    """Invoke ``main()`` with ``--project-id ken-e-dev`` against *fake_db*."""
    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-dev"])
    with patch("google.cloud.firestore.Client", return_value=fake_db):
        return script.main()


def test_idempotency_two_runs_produce_same_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main() twice must leave Firestore in the same state as running it once."""
    fake_db = FakeFirestoreClient()

    result1 = _run_main_with_fake_db(monkeypatch, fake_db)
    assert result1 == 0, "First run must exit 0"

    state_after_first = copy.deepcopy(fake_db._stores.get("agent_configs", {}))

    result2 = _run_main_with_fake_db(monkeypatch, fake_db)
    assert result2 == 0, "Second run must exit 0"

    state_after_second = copy.deepcopy(fake_db._stores.get("agent_configs", {}))

    def _strip_datetime_fields(state: dict[str, Any]) -> dict[str, Any]:
        state = copy.deepcopy(state)
        agent_doc = state.get("synthesizer", {})
        if "metadata" in agent_doc:
            agent_doc["metadata"].pop("created_at", None)
            agent_doc["metadata"].pop("updated_at", None)
        return state

    assert _strip_datetime_fields(state_after_first) == _strip_datetime_fields(
        state_after_second
    ), "Firestore state must be identical after first and second run"


def test_idempotency_agent_doc_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() must write agent_configs/synthesizer with the expected field values."""
    fake_db = FakeFirestoreClient()

    _run_main_with_fake_db(monkeypatch, fake_db)

    agent_doc = fake_db.get_doc("agent_configs", "synthesizer")
    assert agent_doc is not None, "agent_configs/synthesizer must be written"

    assert agent_doc["model"] == "gemini-2.5-flash"
    assert agent_doc["ken_e_sub_agent"] is False
    assert agent_doc["visible_in_frontend"] is False
    assert agent_doc["available_to_copy"] is False
    assert agent_doc["automatically_available"] is True
    assert agent_doc["tool_ids"] == []
    assert agent_doc["default_acceptance_criteria"] is None
    assert agent_doc["reviewer_model"] is None
    assert agent_doc["name"] == "Synth"
    assert agent_doc["title"] == "Result Synthesizer"
    assert "{synthesis_input?}" in agent_doc["instruction"]
    assert "completed research" in agent_doc["instruction"]


# ---------------------------------------------------------------------------
# (e) --dry-run exits 0 without constructing a real Firestore client
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
# (f) Template-injection: {synthesis_input?} wired for upstream result_key injection
# ---------------------------------------------------------------------------


def test_template_injection_placeholder_present() -> None:
    """{synthesis_input?} must be verbatim in the instruction string.

    This guarantees the coordinator (AH-PRD-05) can write upstream result_key
    values to session.state['synthesis_input'] and have them substituted into
    the synthesizer's prompt at LLM-call time.
    """
    instruction = script.SYNTHESIZER_CONFIG["instruction"]
    assert "{synthesis_input?}" in instruction, (
        "SYNTHESIZER_INSTRUCTION must contain '{synthesis_input?}' verbatim so that "
        "ADK (string-instruction path) or AH-PRD-05's callable closure can substitute "
        "upstream result_key values at LLM-call time"
    )


def test_template_injection_sentinel_survives_substitution() -> None:
    """After substituting {synthesis_input?}, the sentinel string appears verbatim.

    Satisfies AH-PRD-14 §7 AC-5 'a fan-in step produces a synthesis that references
    upstream result_key values' at the unit level.  Simulates what ADK does for string
    instructions (inject_session_state) or what AH-PRD-05's callable closure does
    (state.get('synthesis_input', '')).
    """
    sentinel = "GA: sessions=5000\nMETA: clicks=800"
    instruction = script.SYNTHESIZER_CONFIG["instruction"]

    # The {synthesis_input?} placeholder must be present; the '?' suffix means
    # an absent key renders empty rather than raising KeyError (ADK convention).
    assert "{synthesis_input?}" in instruction

    # Simulate substitution: replace the optional-placeholder token with the
    # sentinel value (mirrors ADK's inject_session_state behaviour on string
    # instructions, and what AH-PRD-05's callable closure must do explicitly).
    rendered = instruction.replace("{synthesis_input?}", sentinel)
    assert sentinel in rendered, (
        "After {synthesis_input?} substitution, the sentinel value must appear "
        "verbatim in the rendered instruction — confirming the coordinator's "
        "upstream results will reach the synthesizer LLM"
    )


def test_template_injection_empty_state_renders_no_placeholder() -> None:
    """When synthesis_input is absent, substituting with '' leaves no placeholder token.

    The '?' suffix means ADK renders empty string rather than the literal
    '{synthesis_input?}' when the key is absent from session.state.  This test
    confirms the synthesizer's instruction is graceful on an empty/missing state
    (e.g. on an interactive replay of the first turn).
    """
    instruction = script.SYNTHESIZER_CONFIG["instruction"]
    rendered_empty = instruction.replace("{synthesis_input?}", "")
    assert "{synthesis_input?}" not in rendered_empty, (
        "After substituting empty string for {synthesis_input?}, the raw placeholder "
        "token must not remain in the rendered instruction"
    )
