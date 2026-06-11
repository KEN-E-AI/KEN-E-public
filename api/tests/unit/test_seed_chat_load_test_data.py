"""Unit tests for the chat-sidebar load-test seed's Neo4j owning-org helpers.

The seed creates the Neo4j ``(:Account)-[:BELONGS_TO]->(:Organization)`` edge
that ``require_account_access_for`` (IN-2) resolves; without it the sidebar load
test 404s every request. These tests pin two things that manual/dry-run checks
missed when the script was first written:

- The dry-run path logs and returns WITHOUT importing ``neo4j`` — documenting the
  dry-run/real-run divergence (dry-run can't prove the real import resolves, so
  the real ``uv run`` env must be checked separately; see deployment/cd/staging.yaml).
- ``_neo4j_connection_params`` fails loudly on a missing URI or an unresolved
  (empty) password rather than attempting a doomed connection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The seed lives in api/scripts/, not an importable package — add it to the path.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_chat_load_test_data as seed  # noqa: E402


def test_dry_run_does_not_import_neo4j(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run must log-and-return before the (real-run-only) neo4j import.

    Poison ``import neo4j`` so any attempt raises; the dry-run early-out must
    return cleanly regardless.
    """
    monkeypatch.setitem(sys.modules, "neo4j", None)
    # Must not raise — dry-run returns before `from neo4j import GraphDatabase`.
    assert seed._seed_neo4j_owning_org(dry_run=True) is None


def test_connection_params_raises_on_missing_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(RuntimeError, match="NEO4J_URI is not set"):
        seed._neo4j_connection_params()


def test_connection_params_raises_on_empty_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A set URI but unresolved password fails loudly (secretAccessor-gap guard)."""
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.test")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD did not resolve"):
        seed._neo4j_connection_params()


def test_connection_params_returns_resolved_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://example.test")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "raw-secret-value")
    monkeypatch.setenv("NEO4J_DATABASE", "neo4j")
    assert seed._neo4j_connection_params() == (
        "neo4j+s://example.test",
        "neo4j",
        "raw-secret-value",
        "neo4j",
    )


def test_cleanup_is_noop_without_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleanup with no NEO4J_URI is a safe no-op returning (0, 0)."""
    monkeypatch.delenv("NEO4J_URI", raising=False)
    assert seed._cleanup_neo4j_owning_org() == (0, 0)


def test_seed_cypher_sets_organization_model_required_fields() -> None:
    """The seeded org node must carry the Organization Pydantic model's required
    strings, else the super-admin GET /api/v1/organizations/ 500s on the fixture.

    Pins the regression where the Cypher set ``org.name`` (not
    ``organization_name``) and omitted ``plan``/``website``. Uses an unconditional
    ``SET`` so an already-MERGEd node missing them heals on the next run.
    """
    import inspect

    src = inspect.getsource(seed._seed_neo4j_owning_org)
    for prop in ("org.organization_name", "org.plan", "org.website"):
        assert prop in src, f"seed Cypher must SET {prop}"
    assert "ON CREATE SET org" not in src, "use unconditional SET so it heals nodes"


def test_seed_cypher_sets_account_model_required_fields() -> None:
    """The seeded account node must carry the Account Pydantic model's required
    strings, else the super-admin GET /api/v1/accounts/ 500s on the same fixture
    (both unfiltered and when filtered by the load-test org via BELONGS_TO).

    Pins the gap where the Cypher set only ``account_name`` and omitted
    ``organization_id``/``industry``/``status``/``timezone``.
    """
    import inspect

    src = inspect.getsource(seed._seed_neo4j_owning_org)
    for prop in (
        "acc.account_name",
        "acc.organization_id",
        "acc.industry",
        "acc.status",
        "acc.timezone",
    ):
        assert prop in src, f"seed Cypher must SET {prop}"
    assert "ON CREATE SET acc" not in src, "use unconditional SET so it heals nodes"
